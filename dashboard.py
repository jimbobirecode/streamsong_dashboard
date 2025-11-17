import streamlit as st
import pandas as pd
import os
import bcrypt
import psycopg
from psycopg.rows import dict_row
from datetime import datetime, timedelta
import plotly.graph_objects as go
from io import BytesIO

# ========================================
# DATABASE CONNECTION
# ========================================
DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    """Get database connection"""
    return psycopg.connect(DATABASE_URL)

def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against hash"""
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

def authenticate_user(username: str, password: str):
    """
    Authenticate user - handles both temp passwords and set passwords
    Returns (success, customer_id, full_name, must_change_password, user_id)
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(row_factory=dict_row)

        cursor.execute("""
            SELECT id, password_hash, temp_password, customer_id, full_name,
                   is_active, must_change_password
            FROM dashboard_users
            WHERE username = %s;
        """, (username,))
        
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            conn.close()
            return False, None, None, False, None
        
        if not user['is_active']:
            cursor.close()
            conn.close()
            return False, None, None, False, None
        
        # Check if using temporary password (first login)
        if user['must_change_password'] and user['temp_password']:
            if password == user['temp_password']:
                cursor.close()
                conn.close()
                return True, user['customer_id'], user['full_name'], True, user['id']
        
        # Check regular password
        if user['password_hash'] and verify_password(password, user['password_hash']):
            cursor.close()
            conn.close()
            return True, user['customer_id'], user['full_name'], False, user['id']
        
        cursor.close()
        conn.close()
        return False, None, None, False, None
    except Exception as e:
        st.error(f"Authentication error: {e}")
        return False, None, None, False, None


def set_permanent_password(user_id: int, new_password: str):
    """Set permanent password and clear temp password"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        password_hash = hash_password(new_password)
        
        cursor.execute("""
            UPDATE dashboard_users
            SET password_hash = %s,
                temp_password = NULL,
                must_change_password = FALSE,
                last_login = NOW()
            WHERE id = %s;
        """, (password_hash, user_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Error setting password: {e}")
        return False


def update_last_login(user_id: int):
    """Update last login timestamp"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE dashboard_users SET last_login = NOW() WHERE id = %s;", (user_id,))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        st.error(f"Error updating last login: {e}")


# ========================================
# BOOKING STATUS HELPERS
# ========================================
def get_status_icon(status: str) -> str:
    """Get timeline icon for booking status"""
    status_icons = {
        'Inquiry': '🔵',
        'Requested': '🟡', 
        'Confirmed': '🟠',
        'Booked': '✅',
        'Rejected': '❌',
        'Cancelled': '⚫',
        'Pending': '🟡',  # Legacy fallback
    }
    return status_icons.get(status, '⚪')


def get_status_color(status: str) -> str:
    """Get color class for status badge"""
    status_map = {
        'Inquiry': 'status-inquiry',
        'Requested': 'status-requested',
        'Confirmed': 'status-confirmed',
        'Booked': 'status-booked',
        'Rejected': 'status-rejected',
        'Cancelled': 'status-cancelled',
        'Pending': 'status-requested',  # Legacy fallback
    }
    return status_map.get(status, 'status-inquiry')


# ========================================
# SESSION STATE
# ========================================
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'customer_id' not in st.session_state:
    st.session_state.customer_id = None
if 'username' not in st.session_state:
    st.session_state.username = None
if 'full_name' not in st.session_state:
    st.session_state.full_name = None
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'must_change_password' not in st.session_state:
    st.session_state.must_change_password = False
if 'show_password_change' not in st.session_state:
    st.session_state.show_password_change = False


# ========================================
# LOGOUT FUNCTION
# ========================================
def logout():
    st.session_state.authenticated = False
    st.session_state.customer_id = None
    st.session_state.username = None
    st.session_state.full_name = None
    st.session_state.user_id = None
    st.session_state.must_change_password = False
    st.session_state.show_password_change = False


# ========================================
# STREAMLIT PAGE CONFIG
# ========================================
st.set_page_config(
    page_title="TeeMail Dashboard",
    page_icon="🏌️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ========================================
# STYLING
# ========================================
PRIMARY_COLOR = "#10b981"
SECONDARY_COLOR = "#059669"
DARK_BG = "#0f172a"

st.markdown(f"""
    <style>
    /* Global Styles */
    .main {{
        background: linear-gradient(135deg, {DARK_BG} 0%, #1e293b 100%);
    }}
    
    /* Sidebar */
    [data-testid="stSidebar"] {{
        background: linear-gradient(180deg, #1e293b 0%, #334155 100%);
        border-right: 1px solid rgba(16, 185, 129, 0.2);
    }}
    
    /* Cards */
    .metric-card {{
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
        padding: 1.5rem;
        border-radius: 16px;
        border: 1px solid rgba(16, 185, 129, 0.2);
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
        transition: all 0.3s ease;
    }}
    
    .metric-card:hover {{
        transform: translateY(-2px);
        box-shadow: 0 8px 28px rgba(16, 185, 129, 0.2);
    }}
    
    .booking-card {{
        background: linear-gradient(135deg, #1e293b 0%, #2d3748 100%);
        padding: 1.5rem;
        border-radius: 16px;
        border: 1px solid rgba(16, 185, 129, 0.15);
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
    }}
    
    /* Email Content Styling */
    .email-section {{
        background: #0f172a;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1rem;
        margin-top: 1rem;
    }}
    
    .email-header {{
        color: #10b981;
        font-size: 0.9rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }}
    
    .email-content {{
        background: #1e293b;
        border-left: 3px solid #10b981;
        padding: 1rem;
        border-radius: 8px;
        color: #e5e7eb;
        font-family: 'Courier New', monospace;
        font-size: 0.85rem;
        line-height: 1.6;
        max-height: 300px;
        overflow-y: auto;
        white-space: pre-wrap;
        word-wrap: break-word;
    }}
    
    /* Timeline Status */
    .status-timeline {{
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-bottom: 1rem;
    }}
    
    .status-icon {{
        font-size: 1.5rem;
        line-height: 1;
    }}
    
    /* Status Badges */
    .status-badge {{
        padding: 0.5rem 1rem;
        border-radius: 24px;
        font-weight: 600;
        font-size: 0.85rem;
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
    }}

    .status-inquiry {{
        background: rgba(147, 197, 253, 0.15);
        color: #60a5fa;
        border: 2px solid rgba(147, 197, 253, 0.3);
    }}

    .status-requested {{
        background: rgba(251, 191, 36, 0.15);
        color: #fbbf24;
        border: 2px solid rgba(251, 191, 36, 0.3);
    }}

    .status-confirmed {{
        background: rgba(251, 146, 60, 0.15);
        color: #fb923c;
        border: 2px solid rgba(251, 146, 60, 0.3);
    }}

    .status-booked {{
        background: rgba(16, 185, 129, 0.15);
        color: #10b981;
        border: 2px solid rgba(16, 185, 129, 0.3);
    }}

    .status-rejected {{
        background: rgba(239, 68, 68, 0.15);
        color: #ef4444;
        border: 2px solid rgba(239, 68, 68, 0.3);
    }}

    .status-cancelled {{
        background: rgba(156, 163, 175, 0.15);
        color: #9ca3af;
        border: 2px solid rgba(156, 163, 175, 0.3);
    }}
    
    /* Buttons */
    .stButton > button {{
        background: linear-gradient(135deg, {SECONDARY_COLOR} 0%, {PRIMARY_COLOR} 100%);
        color: white;
        border: none;
        padding: 0.75rem 1.5rem;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.95rem;
        transition: all 0.3s ease;
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
        width: 100%;
    }}
    
    .stButton > button:hover {{ 
        transform: translateY(-2px); 
        box-shadow: 0 8px 20px rgba(16, 185, 129, 0.4); 
    }}
    
    /* Typography */
    h1, h2, h3, h4, h5, h6 {{ 
        color: #f9fafb !important; 
        font-weight: 700 !important; 
    }}
    
    p, span, div, label {{ 
        color: #e5e7eb !important; 
    }}
    
    /* Badges */
    .user-badge {{
        background: linear-gradient(135deg, {SECONDARY_COLOR} 0%, {PRIMARY_COLOR} 100%);
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        display: inline-block;
        margin-bottom: 0.5rem;
    }}
    
    .club-badge {{
        background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%);
        color: #1f2937;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        display: inline-block;
        margin-bottom: 1rem;
    }}
    
    /* Info boxes */
    .info-row {{
        display: flex;
        justify-content: space-between;
        padding: 0.5rem 0;
        border-bottom: 1px solid #334155;
    }}
    
    .info-label {{
        color: #94a3b8;
        font-weight: 600;
        font-size: 0.85rem;
    }}
    
    .info-value {{
        color: #f9fafb;
        font-weight: 500;
    }}
    
    /* Hide Streamlit branding */
    #MainMenu {{visibility: hidden;}} 
    footer {{visibility: hidden;}} 
    header {{visibility: hidden;}}
    </style>
""", unsafe_allow_html=True)


# ========================================
# PASSWORD CHANGE SCREEN
# ========================================
if st.session_state.show_password_change:
    st.markdown("""
        <style>
        .password-container {
            max-width: 500px;
            margin: 100px auto;
            padding: 2.5rem;
            background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
            border-radius: 16px;
            border: 1px solid rgba(16, 185, 129, 0.2);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        }
        .password-title {
            color: #f9fafb;
            font-size: 1.8rem;
            font-weight: 700;
            text-align: center;
            margin-bottom: 0.5rem;
        }
        .password-subtitle {
            color: #94a3b8;
            text-align: center;
            margin-bottom: 2rem;
            font-size: 0.95rem;
        }
        </style>
    """, unsafe_allow_html=True)
    
    st.markdown("""
        <div class="password-container">
            <div class="password-title">🔐 Set Your Password</div>
            <div class="password-subtitle">First-time setup - create your secure password</div>
        </div>
    """, unsafe_allow_html=True)
    
    with st.form("password_setup_form"):
        st.info(f"👋 Welcome, **{st.session_state.full_name}**! Please create a secure password for your account.")
        
        new_password = st.text_input("New Password", type="password", key="new_pass")
        confirm_password = st.text_input("Confirm Password", type="password", key="confirm_pass")
        
        col1, col2 = st.columns([1, 1])
        with col1:
            submit = st.form_submit_button("✅ Set Password", use_container_width=True)
        with col2:
            cancel = st.form_submit_button("Cancel", use_container_width=True)
        
        if cancel:
            logout()
            st.rerun()
        
        if submit:
            if not new_password or not confirm_password:
                st.error("❌ Please fill in both password fields")
            elif new_password != confirm_password:
                st.error("❌ Passwords do not match")
            elif len(new_password) < 8:
                st.error("❌ Password must be at least 8 characters")
            else:
                if set_permanent_password(st.session_state.user_id, new_password):
                    update_last_login(st.session_state.user_id)
                    st.session_state.show_password_change = False
                    st.session_state.must_change_password = False
                    st.success("✅ Password set successfully!")
                    st.rerun()
                else:
                    st.error("❌ Error setting password. Please try again.")
    
    st.stop()


# ========================================
# LOGIN SCREEN
# ========================================
if not st.session_state.authenticated:
    st.markdown("""
        <style>
        .login-container {
            max-width: 450px;
            margin: 100px auto;
            padding: 2.5rem;
            background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
            border-radius: 16px;
            border: 1px solid rgba(16, 185, 129, 0.2);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        }
        .login-title {
            color: #f9fafb;
            font-size: 2rem;
            font-weight: 700;
            text-align: center;
            margin-bottom: 0.5rem;
        }
        .login-subtitle {
            color: #94a3b8;
            text-align: center;
            margin-bottom: 2rem;
        }
        </style>
    """, unsafe_allow_html=True)
    
    st.markdown("""
        <div class="login-container">
            <div class="login-title">🏌️ TeeMail Dashboard</div>
            <div class="login-subtitle">Booking Management System</div>
        </div>
    """, unsafe_allow_html=True)
    
    with st.form("login_form"):
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        submit = st.form_submit_button("🔐 Login", use_container_width=True)
        
        if submit:
            if username and password:
                success, customer_id, full_name, must_change, user_id = authenticate_user(username, password)
                
                if success:
                    st.session_state.authenticated = True
                    st.session_state.customer_id = customer_id
                    st.session_state.username = username
                    st.session_state.full_name = full_name
                    st.session_state.user_id = user_id
                    
                    if must_change:
                        st.session_state.must_change_password = True
                        st.session_state.show_password_change = True
                        st.success("✅ Please set your password...")
                        st.rerun()
                    else:
                        update_last_login(user_id)
                        st.success("✅ Login successful!")
                        st.rerun()
                else:
                    st.error("❌ Invalid username or password")
            else:
                st.error("❌ Please enter username and password")
    
    st.markdown("""
        <div style='text-align: center; color: #6b7280; font-size: 0.85rem; margin-top: 2rem;'>
            <p>First time? Use your temporary password</p>
        </div>
    """, unsafe_allow_html=True)
    
    st.stop()


# ========================================
# LOAD BOOKINGS
# ========================================
@st.cache_data(ttl=10)
def load_bookings_from_db(club_filter):
    """Load bookings directly from PostgreSQL database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(row_factory=dict_row)
        
        cursor.execute("""
            SELECT 
                id,
                booking_id,
                guest_email,
                date,
                tee_time,
                players,
                total,
                status,
                note,
                club,
                timestamp,
                customer_confirmed_at,
                updated_at,
                updated_by,
                created_at
            FROM bookings
            WHERE club = %s
            ORDER BY timestamp DESC
        """, (club_filter,))
        
        bookings = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if not bookings:
            return pd.DataFrame(), 'postgresql'
        
        df = pd.DataFrame(bookings)
        
        # Convert timestamp columns
        for col in ['timestamp', 'customer_confirmed_at', 'updated_at', 'created_at']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
        
        if 'tee_time' not in df.columns:
            df['tee_time'] = 'TBD'
        
        return df, 'postgresql'
    except Exception as e:
        st.error(f"❌ Database error: {e}")
        return pd.DataFrame(), 'error'


def update_booking_status(booking_id: str, new_status: str, updated_by: str):
    """Update booking status in database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE bookings
            SET status = %s,
                updated_at = NOW(),
                updated_by = %s
            WHERE booking_id = %s;
        """, (new_status, updated_by, booking_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Error updating status: {e}")
        return False


# ========================================
# MAIN DASHBOARD
# ========================================

# Sidebar
with st.sidebar:
    st.markdown(f"""
        <div style='text-align: center; padding: 1rem;'>
            <h2 style='color: {PRIMARY_COLOR}; margin: 0;'>🏌️ TeeMail</h2>
            <p style='color: #94a3b8; font-size: 0.9rem; margin-top: 0.5rem;'>Booking Dashboard</p>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown(f"<div class='user-badge'>👤 {st.session_state.full_name}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='club-badge'>🏌️ {st.session_state.customer_id.title()}</div>", unsafe_allow_html=True)
    
    st.markdown("---")
    
    if st.button("🚪 Logout", use_container_width=True):
        logout()
        st.rerun()
    
    st.markdown("---")
    
    # Filters
    st.subheader("📊 Filters")
    
    status_filter = st.multiselect(
        "Status",
        ["Inquiry", "Requested", "Confirmed", "Booked", "Rejected", "Cancelled", "Pending"],
        default=["Inquiry", "Requested", "Confirmed", "Booked", "Pending"]
    )
    
    date_range = st.date_input(
        "Date Range",
        value=(datetime.now().date(), datetime.now().date() + timedelta(days=30))
    )

# Main content
st.title("📧 Booking Requests Dashboard")

# Load bookings
df, source = load_bookings_from_db(st.session_state.customer_id)

if df.empty:
    st.info("📭 No bookings found")
    st.stop()

# Apply filters
filtered_df = df.copy()
if status_filter:
    filtered_df = filtered_df[filtered_df['status'].isin(status_filter)]

if len(date_range) == 2:
    start_date, end_date = date_range
    filtered_df = filtered_df[
        (filtered_df['date'].dt.date >= start_date) & 
        (filtered_df['date'].dt.date <= end_date)
    ]

# Metrics
col1, col2, col3, col4 = st.columns(4)

with col1:
    inquiry_count = len(filtered_df[filtered_df['status'].isin(['Inquiry', 'Pending'])])
    st.markdown(f"""
        <div class='metric-card'>
            <div style='font-size: 2rem;'>🔵</div>
            <div style='font-size: 1.5rem; font-weight: 700; color: #60a5fa;'>{inquiry_count}</div>
            <div style='color: #94a3b8; font-size: 0.9rem;'>New Inquiries</div>
        </div>
    """, unsafe_allow_html=True)

with col2:
    requested_count = len(filtered_df[filtered_df['status'] == 'Requested'])
    st.markdown(f"""
        <div class='metric-card'>
            <div style='font-size: 2rem;'>🟡</div>
            <div style='font-size: 1.5rem; font-weight: 700; color: #fbbf24;'>{requested_count}</div>
            <div style='color: #94a3b8; font-size: 0.9rem;'>Requested</div>
        </div>
    """, unsafe_allow_html=True)

with col3:
    confirmed_count = len(filtered_df[filtered_df['status'] == 'Confirmed'])
    st.markdown(f"""
        <div class='metric-card'>
            <div style='font-size: 2rem;'>🟠</div>
            <div style='font-size: 1.5rem; font-weight: 700; color: #fb923c;'>{confirmed_count}</div>
            <div style='color: #94a3b8; font-size: 0.9rem;'>Confirmed</div>
        </div>
    """, unsafe_allow_html=True)

with col4:
    booked_count = len(filtered_df[filtered_df['status'] == 'Booked'])
    st.markdown(f"""
        <div class='metric-card'>
            <div style='font-size: 2rem;'>✅</div>
            <div style='font-size: 1.5rem; font-weight: 700; color: #10b981;'>{booked_count}</div>
            <div style='color: #94a3b8; font-size: 0.9rem;'>Booked</div>
        </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# Booking cards
st.subheader(f"📋 {len(filtered_df)} Booking Requests")

for idx, booking in filtered_df.iterrows():
    with st.container():
        # Status timeline with icon
        status_icon = get_status_icon(booking['status'])
        status_class = get_status_color(booking['status'])
        
        st.markdown(f"""
            <div class='booking-card'>
                <div class='status-timeline'>
                    <span class='status-icon'>{status_icon}</span>
                    <span class='status-badge {status_class}'>{booking['status']}</span>
                </div>
                
                <div style='display: flex; justify-content: space-between; align-items: start; margin-bottom: 1rem;'>
                    <div>
                        <h3 style='margin: 0; color: #10b981;'>{booking['booking_id']}</h3>
                        <p style='color: #94a3b8; margin: 0.25rem 0 0 0; font-size: 0.9rem;'>{booking['guest_email']}</p>
                    </div>
                    <div style='text-align: right;'>
                        <div style='color: #94a3b8; font-size: 0.85rem;'>Received</div>
                        <div style='color: #f9fafb; font-weight: 600;'>{booking['timestamp'].strftime('%b %d, %Y %I:%M %p')}</div>
                    </div>
                </div>
                
                <div class='info-row'>
                    <span class='info-label'>📅 Tee Time Date</span>
                    <span class='info-value'>{booking['date'].strftime('%A, %B %d, %Y')}</span>
                </div>
                
                <div class='info-row'>
                    <span class='info-label'>⏰ Time</span>
                    <span class='info-value'>{booking.get('tee_time', 'TBD')}</span>
                </div>
                
                <div class='info-row'>
                    <span class='info-label'>👥 Players</span>
                    <span class='info-value'>{booking['players']}</span>
                </div>
                
                <div class='info-row' style='border-bottom: none;'>
                    <span class='info-label'>💰 Total</span>
                    <span class='info-value' style='color: #10b981; font-weight: 700; font-size: 1.1rem;'>${booking['total']:,.2f}</span>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        # Expandable section for details
        with st.expander("📄 View Full Details", expanded=False):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                # Email content section
                if booking.get('note'):
                    st.markdown(f"""
                        <div class='email-section'>
                            <div class='email-header'>
                                📧 Original Email Request
                            </div>
                            <div class='email-content'>{booking['note']}</div>
                        </div>
                    """, unsafe_allow_html=True)
                
                # Additional info
                if booking.get('updated_by'):
                    st.markdown(f"""
                        <div style='margin-top: 1rem; padding: 0.75rem; background: #0f172a; border-radius: 8px;'>
                            <div style='color: #94a3b8; font-size: 0.85rem;'>Last Updated</div>
                            <div style='color: #f9fafb;'>{booking['updated_at'].strftime('%b %d, %Y %I:%M %p')} by {booking['updated_by']}</div>
                        </div>
                    """, unsafe_allow_html=True)
            
            with col2:
                st.markdown("#### ⚡ Quick Actions")
                
                # Status update buttons
                current_status = booking['status']
                
                if current_status in ['Inquiry', 'Pending']:
                    if st.button("🟡 Mark as Requested", key=f"req_{booking['booking_id']}", use_container_width=True):
                        if update_booking_status(booking['booking_id'], 'Requested', st.session_state.username):
                            st.success("✅ Status updated to Requested")
                            st.cache_data.clear()
                            st.rerun()
                
                if current_status == 'Requested':
                    if st.button("🟠 Mark as Confirmed", key=f"conf_{booking['booking_id']}", use_container_width=True):
                        if update_booking_status(booking['booking_id'], 'Confirmed', st.session_state.username):
                            st.success("✅ Status updated to Confirmed")
                            st.cache_data.clear()
                            st.rerun()
                
                if current_status == 'Confirmed':
                    if st.button("✅ Mark as Booked", key=f"book_{booking['booking_id']}", use_container_width=True):
                        if update_booking_status(booking['booking_id'], 'Booked', st.session_state.username):
                            st.success("✅ Status updated to Booked")
                            st.cache_data.clear()
                            st.rerun()
                
                # Reject/Cancel options
                if current_status not in ['Rejected', 'Cancelled', 'Booked']:
                    if st.button("❌ Reject", key=f"rej_{booking['booking_id']}", use_container_width=True):
                        if update_booking_status(booking['booking_id'], 'Rejected', st.session_state.username):
                            st.warning("Booking rejected")
                            st.cache_data.clear()
                            st.rerun()
        
        st.markdown("<div style='margin-bottom: 1.5rem;'></div>", unsafe_allow_html=True)

# Export options
st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("📊 Export to Excel", use_container_width=True):
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            filtered_df.to_excel(writer, index=False, sheet_name='Bookings')
        
        st.download_button(
            label="⬇️ Download Excel",
            data=output.getvalue(),
            file_name=f"bookings_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

with col2:
    if st.button("📄 Export to CSV", use_container_width=True):
        csv = filtered_df.to_csv(index=False)
        st.download_button(
            label="⬇️ Download CSV",
            data=csv,
            file_name=f"bookings_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )

with col3:
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
