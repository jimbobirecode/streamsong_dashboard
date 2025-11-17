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
    /* Global Styles - Enterprise Clean */
    .main {{
        background: #0a0f1e;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Helvetica', 'Arial', sans-serif;
    }}
    
    /* Sidebar - Minimal & Professional */
    [data-testid="stSidebar"] {{
        background: #0f1419;
        border-right: 1px solid #1e293b;
    }}
    
    /* Metric Cards - Clean & Modern */
    .metric-card {{
        background: #141b2b;
        padding: 1.75rem;
        border-radius: 12px;
        border: 1px solid #1e293b;
        transition: all 0.2s ease;
    }}
    
    .metric-card:hover {{
        border-color: #2d3748;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }}
    
    /* Booking Cards - Enterprise Grade */
    .booking-card {{
        background: #141b2b;
        padding: 0;
        border-radius: 12px;
        border: 1px solid #1e293b;
        margin-bottom: 1rem;
        overflow: hidden;
    }}
    
    .booking-header {{
        background: #0f1419;
        padding: 1.25rem 1.5rem;
        border-bottom: 1px solid #1e293b;
    }}
    
    .booking-body {{
        padding: 1.5rem;
    }}
    
    .booking-id {{
        font-size: 1rem;
        font-weight: 600;
        color: #f9fafb;
        margin: 0;
        font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
        letter-spacing: 0.5px;
    }}
    
    .booking-email {{
        color: #64748b;
        font-size: 0.875rem;
        margin: 0.375rem 0 0 0;
    }}
    
    .timestamp {{
        color: #64748b;
        font-size: 0.8125rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        font-weight: 500;
    }}
    
    .timestamp-value {{
        color: #94a3b8;
        font-size: 0.875rem;
        font-weight: 600;
        margin-top: 0.25rem;
    }}
    
    /* Email Content - Professional Display */
    .email-section {{
        background: #0a0f1e;
        border: 1px solid #1e293b;
        border-radius: 8px;
        padding: 0;
        margin-top: 1.5rem;
        overflow: hidden;
    }}
    
    .email-header {{
        background: #0f1419;
        color: #64748b;
        font-size: 0.8125rem;
        font-weight: 600;
        padding: 0.75rem 1rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        border-bottom: 1px solid #1e293b;
    }}
    
    .email-content {{
        background: #0a0f1e;
        padding: 1rem;
        color: #cbd5e1;
        font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
        font-size: 0.8125rem;
        line-height: 1.7;
        max-height: 400px;
        overflow-y: auto;
        white-space: pre-wrap;
        word-wrap: break-word;
    }}
    
    /* Status Timeline - Minimalist */
    .status-timeline {{
        display: inline-flex;
        align-items: center;
        gap: 0.625rem;
        background: #0a0f1e;
        padding: 0.5rem 1rem;
        border-radius: 8px;
        border: 1px solid #1e293b;
    }}
    
    .status-icon {{
        font-size: 1.125rem;
        line-height: 1;
    }}
    
    /* Status Badges - Corporate Style */
    .status-badge {{
        padding: 0.375rem 0.875rem;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.8125rem;
        display: inline-flex;
        align-items: center;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }}

    .status-inquiry {{
        background: rgba(59, 130, 246, 0.1);
        color: #60a5fa;
        border: 1px solid rgba(59, 130, 246, 0.2);
    }}

    .status-requested {{
        background: rgba(234, 179, 8, 0.1);
        color: #eab308;
        border: 1px solid rgba(234, 179, 8, 0.2);
    }}

    .status-confirmed {{
        background: rgba(249, 115, 22, 0.1);
        color: #f97316;
        border: 1px solid rgba(249, 115, 22, 0.2);
    }}

    .status-booked {{
        background: rgba(16, 185, 129, 0.1);
        color: #10b981;
        border: 1px solid rgba(16, 185, 129, 0.2);
    }}

    .status-rejected {{
        background: rgba(239, 68, 68, 0.1);
        color: #ef4444;
        border: 1px solid rgba(239, 68, 68, 0.2);
    }}

    .status-cancelled {{
        background: rgba(100, 116, 139, 0.1);
        color: #64748b;
        border: 1px solid rgba(100, 116, 139, 0.2);
    }}
    
    /* Buttons - Enterprise Style */
    .stButton > button {{
        background: #10b981;
        color: white;
        border: none;
        padding: 0.625rem 1.25rem;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.875rem;
        transition: all 0.2s ease;
        width: 100%;
        letter-spacing: 0.3px;
    }}
    
    .stButton > button:hover {{ 
        background: #059669;
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.25);
    }}
    
    /* Typography - Professional */
    h1 {{ 
        color: #f9fafb !important; 
        font-weight: 700 !important;
        font-size: 1.875rem !important;
        letter-spacing: -0.5px !important;
    }}
    
    h2, h3, h4, h5, h6 {{ 
        color: #f9fafb !important; 
        font-weight: 600 !important; 
    }}
    
    p, span, div, label {{ 
        color: #cbd5e1 !important; 
    }}
    
    /* Badges - Refined */
    .user-badge {{
        background: #10b981;
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 6px;
        font-size: 0.8125rem;
        font-weight: 600;
        display: inline-block;
        margin-bottom: 0.5rem;
        letter-spacing: 0.3px;
    }}
    
    .club-badge {{
        background: #eab308;
        color: #0f1419;
        padding: 0.5rem 1rem;
        border-radius: 6px;
        font-size: 0.8125rem;
        font-weight: 600;
        display: inline-block;
        margin-bottom: 1rem;
        letter-spacing: 0.3px;
    }}
    
    /* Data Grid - Enterprise */
    .data-grid {{
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 1rem;
        padding: 0;
    }}
    
    .data-cell {{
        padding: 1rem;
        border-radius: 8px;
        background: #0f1419;
        border: 1px solid #1e293b;
    }}
    
    .data-label {{
        color: #64748b;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 0.5rem;
    }}
    
    .data-value {{
        color: #f9fafb;
        font-size: 1rem;
        font-weight: 600;
    }}
    
    .data-value-large {{
        color: #10b981;
        font-size: 1.5rem;
        font-weight: 700;
    }}
    
    /* Expander Override */
    .streamlit-expanderHeader {{
        background: #0f1419 !important;
        border-radius: 8px !important;
        border: 1px solid #1e293b !important;
        font-weight: 600 !important;
        font-size: 0.875rem !important;
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
        <div style='text-align: center; padding: 1.5rem 1rem; border-bottom: 1px solid #1e293b; margin-bottom: 1.5rem;'>
            <h2 style='color: #10b981; margin: 0; font-size: 1.5rem; font-weight: 700; letter-spacing: -0.5px;'>TeeMail</h2>
            <p style='color: #64748b; font-size: 0.8125rem; margin-top: 0.375rem; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;'>Booking Dashboard</p>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown(f"<div class='user-badge'>👤 {st.session_state.full_name}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='club-badge'>🏌️ {st.session_state.customer_id.title()}</div>", unsafe_allow_html=True)
    
    st.markdown("<div style='height: 1px; background: #1e293b; margin: 1.5rem 0;'></div>", unsafe_allow_html=True)
    
    if st.button("🚪 Logout", use_container_width=True):
        logout()
        st.rerun()
    
    st.markdown("<div style='height: 1px; background: #1e293b; margin: 1.5rem 0;'></div>", unsafe_allow_html=True)
    
    # Filters
    st.markdown("#### 📊 Filters")
    
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
st.markdown("""
    <h1 style='margin-bottom: 0.5rem;'>Booking Requests</h1>
    <p style='color: #64748b; margin-bottom: 2rem; font-size: 0.9375rem;'>Manage and track all incoming tee time requests</p>
""", unsafe_allow_html=True)

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
            <div style='display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.75rem;'>
                <div style='font-size: 1.75rem; opacity: 0.9;'>🔵</div>
                <div style='color: #64748b; font-size: 0.75rem; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px;'>Inquiry</div>
            </div>
            <div style='font-size: 2rem; font-weight: 700; color: #60a5fa; line-height: 1;'>{inquiry_count}</div>
        </div>
    """, unsafe_allow_html=True)

with col2:
    requested_count = len(filtered_df[filtered_df['status'] == 'Requested'])
    st.markdown(f"""
        <div class='metric-card'>
            <div style='display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.75rem;'>
                <div style='font-size: 1.75rem; opacity: 0.9;'>🟡</div>
                <div style='color: #64748b; font-size: 0.75rem; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px;'>Requested</div>
            </div>
            <div style='font-size: 2rem; font-weight: 700; color: #eab308; line-height: 1;'>{requested_count}</div>
        </div>
    """, unsafe_allow_html=True)

with col3:
    confirmed_count = len(filtered_df[filtered_df['status'] == 'Confirmed'])
    st.markdown(f"""
        <div class='metric-card'>
            <div style='display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.75rem;'>
                <div style='font-size: 1.75rem; opacity: 0.9;'>🟠</div>
                <div style='color: #64748b; font-size: 0.75rem; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px;'>Confirmed</div>
            </div>
            <div style='font-size: 2rem; font-weight: 700; color: #f97316; line-height: 1;'>{confirmed_count}</div>
        </div>
    """, unsafe_allow_html=True)

with col4:
    booked_count = len(filtered_df[filtered_df['status'] == 'Booked'])
    st.markdown(f"""
        <div class='metric-card'>
            <div style='display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.75rem;'>
                <div style='font-size: 1.75rem; opacity: 0.9;'>✅</div>
                <div style='color: #64748b; font-size: 0.75rem; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px;'>Booked</div>
            </div>
            <div style='font-size: 2rem; font-weight: 700; color: #10b981; line-height: 1;'>{booked_count}</div>
        </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='height: 1px; background: #1e293b; margin: 2rem 0;'></div>", unsafe_allow_html=True)

# Booking cards
st.markdown(f"""
    <div style='margin-bottom: 1.5rem;'>
        <h3 style='color: #f9fafb; font-weight: 600; font-size: 1.125rem;'>{len(filtered_df)} Active Requests</h3>
        <p style='color: #64748b; font-size: 0.875rem; margin-top: 0.25rem;'>Showing bookings from {date_range[0].strftime('%b %d')} to {date_range[1].strftime('%b %d, %Y')}</p>
    </div>
""", unsafe_allow_html=True)

for idx, booking in filtered_df.iterrows():
    with st.container():
        # Status timeline with icon
        status_icon = get_status_icon(booking['status'])
        status_class = get_status_color(booking['status'])
        
        tee_time_display = booking.get('tee_time', 'Not Specified')
        if tee_time_display == 'None' or tee_time_display is None:
            tee_time_display = 'Not Specified'
        
        st.markdown(f"""
            <div class='booking-card'>
                <div class='booking-header'>
                    <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;'>
                        <div class='status-timeline'>
                            <span class='status-icon'>{status_icon}</span>
                            <span class='status-badge {status_class}'>{booking['status']}</span>
                        </div>
                        <div style='text-align: right;'>
                            <div class='timestamp'>Received</div>
                            <div class='timestamp-value'>{booking['timestamp'].strftime('%b %d, %Y • %I:%M %p')}</div>
                        </div>
                    </div>
                    
                    <div style='display: flex; justify-content: space-between; align-items: baseline;'>
                        <div>
                            <div class='booking-id'>{booking['booking_id']}</div>
                            <div class='booking-email'>{booking['guest_email']}</div>
                        </div>
                    </div>
                </div>
                
                <div class='booking-body'>
                    <div class='data-grid'>
                        <div class='data-cell'>
                            <div class='data-label'>📅 Tee Time Date</div>
                            <div class='data-value'>{booking['date'].strftime('%b %d, %Y')}</div>
                        </div>
                        
                        <div class='data-cell'>
                            <div class='data-label'>⏰ Time</div>
                            <div class='data-value'>{tee_time_display}</div>
                        </div>
                        
                        <div class='data-cell'>
                            <div class='data-label'>👥 Players</div>
                            <div class='data-value'>{booking['players']} Player{'s' if booking['players'] != 1 else ''}</div>
                        </div>
                        
                        <div class='data-cell'>
                            <div class='data-label'>💰 Total Amount</div>
                            <div class='data-value-large'>${booking['total']:,.2f}</div>
                        </div>
                    </div>
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
                                📧 Original Request
                            </div>
                            <div class='email-content'>{booking['note']}</div>
                        </div>
                    """, unsafe_allow_html=True)
                
                # Additional info
                if booking.get('updated_by'):
                    st.markdown(f"""
                        <div style='margin-top: 1.5rem; padding: 1rem; background: #0f1419; border-radius: 8px; border: 1px solid #1e293b;'>
                            <div style='color: #64748b; font-size: 0.75rem; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px; margin-bottom: 0.5rem;'>Last Updated</div>
                            <div style='color: #cbd5e1; font-size: 0.875rem;'>{booking['updated_at'].strftime('%b %d, %Y • %I:%M %p')}</div>
                            <div style='color: #64748b; font-size: 0.8125rem; margin-top: 0.25rem;'>by {booking['updated_by']}</div>
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
        
        st.markdown("<div style='margin-bottom: 0.5rem;'></div>", unsafe_allow_html=True)

# Export options
st.markdown("<div style='height: 1px; background: #1e293b; margin: 2rem 0;'></div>", unsafe_allow_html=True)
st.markdown("#### 📤 Export Options")
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
