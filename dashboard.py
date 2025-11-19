import streamlit as st
import pandas as pd
import os
import bcrypt
import psycopg
from psycopg.rows import dict_row
from datetime import datetime, timedelta
from io import BytesIO
import html
import re

# ========================================
# DATABASE CONNECTION
# ========================================
DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    """Get database connection"""
    return psycopg.connect(DATABASE_URL)

def extract_tee_time_from_note(note_content):
    """
    Extract tee time from email content.
    Looks for patterns like:
    - Time: 12:20 PM
    - Time: 10:30 AM
    - Tee Time: 3:45 PM
    """
    if not note_content or pd.isna(note_content):
        return None

    # Pattern to match "Time: HH:MM AM/PM"
    patterns = [
        r'Time:\s*(\d{1,2}:\d{2}\s*[AaPp][Mm])',  # Time: 12:20 PM
        r'time:\s*(\d{1,2}:\d{2}\s*[AaPp][Mm])',  # time: 12:20 pm (case insensitive)
        r'Tee\s+Time:\s*(\d{1,2}:\d{2}\s*[AaPp][Mm])',  # Tee Time: 12:20 PM
    ]

    for pattern in patterns:
        match = re.search(pattern, str(note_content), re.IGNORECASE)
        if match:
            tee_time = match.group(1).strip()
            # Normalize to uppercase (12:20 PM)
            return tee_time.upper()

    return None

def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against hash"""
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

def authenticate_user(username: str, password: str):
    """Authenticate user - handles both temp passwords and set passwords
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
        'Inquiry': '',
        'Requested': '',
        'Confirmed': '',
        'Booked': '',
        'Rejected': '',
        'Cancelled': '',
        'Pending': '',
    }
    return status_icons.get(status, '')


def get_status_color(status: str) -> str:
    """Get color class for status badge"""
    status_map = {
        'Inquiry': 'status-inquiry',
        'Requested': 'status-requested',
        'Confirmed': 'status-confirmed',
        'Booked': 'status-booked',
        'Rejected': 'status-rejected',
        'Cancelled': 'status-cancelled',
        'Pending': 'status-requested',
    }
    return status_map.get(status, 'status-inquiry')


def generate_status_progress_bar(current_status: str) -> str:
    """Generate a linear status progress bar showing booking workflow"""

    # Define the workflow stages with Streamsong colors
    stages = [
        {'name': 'Inquiry', 'color': '#87a7b3'},
        {'name': 'Requested', 'color': '#cc8855'},
        {'name': 'Confirmed', 'color': '#8b9456'},
        {'name': 'Booked', 'color': '#6b7c3f'}
    ]

    # Handle special cases
    if current_status == 'Pending':
        current_status = 'Inquiry'

    # Check if rejected or cancelled
    is_rejected = current_status == 'Rejected'
    is_cancelled = current_status == 'Cancelled'

    if is_rejected or is_cancelled:
        status_color = '#a0653f' if is_rejected else '#666666'
        return f"""
        <div style='background: #3d5266; padding: 1rem; border-radius: 8px; border: 2px solid #6b7c3f;'>
            <div style='display: flex; align-items: center; justify-content: center; gap: 0.75rem;'>
                <div style='width: 12px; height: 12px; border-radius: 50%; background: {status_color};'></div>
                <span style='color: {status_color}; font-weight: 700; font-size: 1rem; text-transform: uppercase; letter-spacing: 0.5px;'>{current_status}</span>
            </div>
        </div>
        """

    # Find current stage index
    current_index = next((i for i, s in enumerate(stages) if s['name'] == current_status), 0)

    # Generate HTML
    html = """
    <div style='background: #3d5266; padding: 1.25rem; border-radius: 8px; border: 2px solid #6b7c3f;'>
        <div style='display: flex; align-items: center; justify-content: space-between; position: relative;'>
    """

    # Add connecting line
    html += """
        <div style='position: absolute; top: 1rem; left: 2rem; right: 2rem; height: 3px; background: #4a6278; z-index: 1;'></div>
    """

    # Add progress line (only up to current stage)
    progress_width = (current_index / (len(stages) - 1)) * 100 if len(stages) > 1 else 0
    html += f"""
        <div style='position: absolute; top: 1rem; left: 2rem; width: calc({progress_width}% - 2rem); height: 3px; background: linear-gradient(90deg, #87a7b3, #6b7c3f); z-index: 2;'></div>
    """

    # Add stage nodes
    for i, stage in enumerate(stages):
        is_active = i <= current_index
        is_current = i == current_index

        bg_color = stage['color'] if is_active else '#4a6278'
        text_color = '#f7f5f2' if is_active else '#999999'
        border_color = stage['color'] if is_current else ('#6b7c3f' if is_active else '#4a6278')

        html += f"""
        <div style='display: flex; flex-direction: column; align-items: center; z-index: 3; position: relative;'>
            <div style='
                width: 1.5rem;
                height: 1.5rem;
                border-radius: 50%;
                background: {bg_color};
                border: 3px solid {border_color};
                box-shadow: {('0 0 0 4px rgba(107, 124, 63, 0.2)' if is_current else 'none')};
                transition: all 0.3s ease;
            '>
            </div>
            <div style='
                margin-top: 0.5rem;
                font-size: 0.7rem;
                font-weight: {('700' if is_current else '600')};
                color: {text_color};
                text-transform: uppercase;
                letter-spacing: 0.5px;
                white-space: nowrap;
            '>{stage['name']}</div>
        </div>
        """

    html += """
        </div>
    </div>
    """

    return html


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
    page_title="Streamsong Booking Dashboard",
    page_icon="assets/ssr-logo-notag.png",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ========================================
# STYLING - STREAMSONG BRAND
# ========================================
st.markdown("""
    <style>
    .main {
        background: #2a3a4a;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
    }

    [data-testid="stSidebar"] {
        background: #3d5266;
        border-right: 2px solid #6b7c3f;
    }

    .metric-card {
        background: linear-gradient(135deg, #3d5266 0%, #4a6278 100%);
        padding: 1.75rem;
        border-radius: 12px;
        border: 2px solid #6b7c3f;
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
    }

    .metric-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: linear-gradient(90deg, #6b7c3f, #a0653f);
        opacity: 0;
        transition: opacity 0.3s ease;
    }

    .metric-card:hover {
        border-color: #a0653f;
        box-shadow: 0 8px 24px rgba(107, 124, 63, 0.5);
        transform: translateY(-2px);
    }

    .metric-card:hover::before {
        opacity: 1;
    }
    
    .booking-id {
        font-size: 1rem;
        font-weight: 600;
        color: #f7f5f2;
        margin: 0;
        font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
        letter-spacing: 0.5px;
    }

    .booking-email {
        color: #d4b896;
        font-size: 0.875rem;
        margin: 0.375rem 0 0 0;
    }

    .timestamp {
        color: #d4b896;
        font-size: 0.8125rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        font-weight: 500;
    }

    .timestamp-value {
        color: #f7f5f2;
        font-size: 0.875rem;
        font-weight: 600;
        margin-top: 0.25rem;
    }
    
    .stTextArea textarea {
        background: #3d5266 !important;
        border: 2px solid #6b7c3f !important;
        border-radius: 0 0 8px 8px !important;
        color: #f7f5f2 !important;
        font-family: 'SF Mono', 'Monaco', 'Consolas', monospace !important;
        font-size: 0.8125rem !important;
        line-height: 1.7 !important;
        padding: 1rem !important;
    }

    .stTextArea textarea:disabled {
        background: #4a6278 !important;
        color: #d4b896 !important;
        opacity: 1 !important;
        -webkit-text-fill-color: #d4b896 !important;
    }

    .status-timeline {
        display: inline-flex;
        align-items: center;
        gap: 0.625rem;
        background: #3d5266;
        padding: 0.5rem 1rem;
        border-radius: 8px;
        border: 2px solid #6b7c3f;
    }
    
    .status-icon {
        font-size: 1.125rem;
        line-height: 1;
    }
    
    .status-badge {
        padding: 0.375rem 0.875rem;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.8125rem;
        display: inline-flex;
        align-items: center;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .status-inquiry {
        background: #87a7b3;
        color: #ffffff;
        border: 2px solid #87a7b3;
    }

    .status-requested {
        background: #cc8855;
        color: #ffffff;
        border: 2px solid #cc8855;
    }

    .status-confirmed {
        background: #8b9456;
        color: #ffffff;
        border: 2px solid #8b9456;
    }

    .status-booked {
        background: #6b7c3f;
        color: #ffffff;
        border: 2px solid #6b7c3f;
    }

    .status-rejected {
        background: #a0653f;
        color: #ffffff;
        border: 2px solid #a0653f;
    }

    .status-cancelled {
        background: #666666;
        color: #ffffff;
        border: 2px solid #666666;
    }
    
    .stButton > button {
        background: #6b7c3f;
        color: white;
        border: none;
        padding: 0.625rem 1.25rem;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.875rem;
        transition: all 0.2s ease;
        width: 100%;
        letter-spacing: 0.3px;
        cursor: pointer;
    }

    .stButton > button:hover {
        background: #8b9456;
        box-shadow: 0 4px 12px rgba(107, 124, 63, 0.3);
        transform: translateY(-1px);
    }

    .stButton > button:active {
        transform: translateY(0px);
    }
    
    h1 {
        color: #f7f5f2 !important;
        font-weight: 700 !important;
        font-size: 1.875rem !important;
        letter-spacing: -0.5px !important;
    }

    h2, h3, h4, h5, h6 {
        color: #f7f5f2 !important;
        font-weight: 600 !important;
    }

    p, span, div, label {
        color: #d4b896 !important;
    }
    
    .user-badge {
        background: #6b7c3f;
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 6px;
        font-size: 0.8125rem;
        font-weight: 600;
        display: inline-block;
        margin-bottom: 0.5rem;
        letter-spacing: 0.3px;
    }

    .club-badge {
        background: #a0653f;
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 6px;
        font-size: 0.8125rem;
        font-weight: 600;
        display: inline-block;
        margin-bottom: 1rem;
        letter-spacing: 0.3px;
    }
    
    .data-label {
        color: #d4b896;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 0.5rem;
    }

    .streamlit-expanderHeader {
        background: #3d5266 !important;
        border-radius: 8px !important;
        border: 2px solid #6b7c3f !important;
        font-weight: 600 !important;
        font-size: 0.875rem !important;
        color: #f7f5f2 !important;
        transition: all 0.2s ease !important;
    }

    .streamlit-expanderHeader:hover {
        border-color: #a0653f !important;
        background: #4a6278 !important;
    }

    .streamlit-expanderContent {
        background: #3d5266 !important;
        border: 2px solid #6b7c3f !important;
        border-top: none !important;
        border-radius: 0 0 8px 8px !important;
    }

    /* Card Animation */
    @keyframes slideUp {
        from {
            opacity: 0;
            transform: translateY(20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    .booking-card {
        animation: slideUp 0.3s ease-out;
    }
    
    .stMultiSelect > div > div {
        background: #3d5266 !important;
        border: 2px solid #6b7c3f !important;
        border-radius: 6px !important;
        color: #f7f5f2 !important;
    }

    .stDateInput > div > div {
        background: #3d5266 !important;
        border: 2px solid #6b7c3f !important;
        border-radius: 6px !important;
        color: #f7f5f2 !important;
    }
    
    #MainMenu {visibility: hidden;} 
    footer {visibility: hidden;} 
    header {visibility: hidden;}
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
            background: linear-gradient(135deg, #3d5266 0%, #5a6f85 100%);
            border-radius: 16px;
            border: 1px solid rgba(107, 124, 63, 0.3);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        }
        .password-title {
            color: #f7f5f2;
            font-size: 1.8rem;
            font-weight: 700;
            text-align: center;
            margin-bottom: 0.5rem;
        }
        .password-subtitle {
            color: #e8e3d9;
            text-align: center;
            margin-bottom: 2rem;
            font-size: 0.95rem;
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("""
        <div class="password-container">
            <div class="password-title">Set Your Password</div>
            <div class="password-subtitle">First-time setup - create your secure password</div>
        </div>
    """, unsafe_allow_html=True)

    with st.form("password_setup_form"):
        st.info(f"Welcome, **{st.session_state.full_name}**! Please create a secure password for your account.")

        new_password = st.text_input("New Password", type="password", key="new_pass")
        confirm_password = st.text_input("Confirm Password", type="password", key="confirm_pass")

        col1, col2 = st.columns([1, 1])
        with col1:
            submit = st.form_submit_button("Set Password", use_container_width=True)
        with col2:
            cancel = st.form_submit_button("Cancel", use_container_width=True)

        if cancel:
            logout()
            st.rerun()

        if submit:
            if not new_password or not confirm_password:
                st.error("Please fill in both password fields")
            elif new_password != confirm_password:
                st.error("Passwords do not match")
            elif len(new_password) < 8:
                st.error("Password must be at least 8 characters")
            else:
                if set_permanent_password(st.session_state.user_id, new_password):
                    update_last_login(st.session_state.user_id)
                    st.session_state.show_password_change = False
                    st.session_state.must_change_password = False
                    st.success("Password set successfully!")
                    st.rerun()
                else:
                    st.error("Error setting password. Please try again.")
    
    st.stop()


# ========================================
# LOGIN SCREEN
# ========================================
if not st.session_state.authenticated:
    st.markdown("""
        <style>
        .login-logo-container {
            text-align: center;
            margin-top: 80px;
            margin-bottom: 2rem;
        }
        .login-subtitle {
            color: #d4b896;
            text-align: center;
            margin-bottom: 3rem;
            font-size: 1.1rem;
            font-weight: 500;
        }
        </style>
    """, unsafe_allow_html=True)

    # Center the logo with reduced size
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.markdown("<div class='login-logo-container'>", unsafe_allow_html=True)
        st.image("assets/ssr-logo-notag.png", use_column_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("""
        <div class="login-subtitle">Booking Management System</div>
    """, unsafe_allow_html=True)
    
    with st.form("login_form"):
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        submit = st.form_submit_button("Login", use_container_width=True)
        
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
                        st.success("Please set your password...")
                        st.rerun()
                    else:
                        update_last_login(user_id)
                        st.success("Login successful!")
                        st.rerun()
                else:
                    st.error("Invalid username or password")
            else:
                st.error("Please enter username and password")
    
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
                id, booking_id, guest_email, date, tee_time, players, total,
                status, note, club, timestamp, customer_confirmed_at,
                updated_at, updated_by, created_at, hotel_required,
                hotel_checkin, hotel_checkout
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

        # Ensure all datetime columns are properly converted
        for col in ['timestamp', 'customer_confirmed_at', 'updated_at', 'created_at']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')

        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'], errors='coerce')

        # Ensure tee_time exists and handle None/NaN values
        if 'tee_time' not in df.columns:
            df['tee_time'] = 'Not Specified'
        else:
            df['tee_time'] = df['tee_time'].fillna('Not Specified')

        # Extract tee times from note content if not already set
        for idx in df.index:
            current_tee_time = df.at[idx, 'tee_time']
            if current_tee_time in ['Not Specified', None, ''] or pd.isna(current_tee_time):
                note_content = df.at[idx, 'note']
                extracted_time = extract_tee_time_from_note(note_content)
                if extracted_time:
                    df.at[idx, 'tee_time'] = extracted_time

        # Ensure note column exists and handle None/NaN
        if 'note' not in df.columns:
            df['note'] = 'No additional information provided'
        else:
            df['note'] = df['note'].fillna('No additional information provided')

        # Ensure all required columns have proper defaults
        if 'status' not in df.columns:
            df['status'] = 'Inquiry'

        if 'players' not in df.columns:
            df['players'] = 1
        else:
            df['players'] = df['players'].fillna(1)

        if 'total' not in df.columns:
            df['total'] = 0.0
        else:
            df['total'] = df['total'].fillna(0.0)

        if 'guest_email' not in df.columns:
            df['guest_email'] = 'No email provided'
        else:
            df['guest_email'] = df['guest_email'].fillna('No email provided')

        if 'booking_id' not in df.columns:
            df['booking_id'] = df.index.map(lambda x: f'BOOK-{x:04d}')

        if 'hotel_required' not in df.columns:
            df['hotel_required'] = False
        else:
            df['hotel_required'] = df['hotel_required'].fillna(False)

        # Ensure hotel date columns exist
        for col in ['hotel_checkin', 'hotel_checkout']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
            else:
                df[col] = None

        return df, 'postgresql'
    except Exception as e:
        st.error(f"Database error: {e}")
        import traceback
        st.error(f"Details: {traceback.format_exc()}")
        return pd.DataFrame(), 'error'


def update_booking_status(booking_id: str, new_status: str, updated_by: str):
    """Update booking status in database and return True to trigger filter adjustment"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE bookings
            SET status = %s, updated_at = NOW(), updated_by = %s
            WHERE booking_id = %s;
        """, (new_status, updated_by, booking_id))

        conn.commit()
        cursor.close()
        conn.close()

        # Store the new status in session state to auto-include in filter
        if 'auto_include_status' not in st.session_state:
            st.session_state.auto_include_status = set()
        st.session_state.auto_include_status.add(new_status)

        return True
    except Exception as e:
        st.error(f"Error updating status: {e}")
        return False


def update_booking_tee_time(booking_id: str, tee_time: str):
    """Update booking tee_time in database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE bookings
            SET tee_time = %s, updated_at = NOW()
            WHERE booking_id = %s;
        """, (tee_time, booking_id))

        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Error updating tee time: {e}")
        return False


def fix_all_tee_times(club_filter):
    """Extract and update tee times for all bookings with missing tee times"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(row_factory=dict_row)

        # Get all bookings with missing or "Not Specified" tee times
        cursor.execute("""
            SELECT id, booking_id, note, tee_time
            FROM bookings
            WHERE club = %s
              AND (tee_time IS NULL OR tee_time = 'Not Specified' OR tee_time = '');
        """, (club_filter,))

        bookings = cursor.fetchall()

        if not bookings:
            cursor.close()
            conn.close()
            return 0, 0

        updated_count = 0
        not_found_count = 0

        for booking in bookings:
            note = booking['note']
            extracted_time = extract_tee_time_from_note(note)

            if extracted_time:
                # Update the booking
                cursor.execute("""
                    UPDATE bookings
                    SET tee_time = %s, updated_at = NOW()
                    WHERE id = %s;
                """, (extracted_time, booking['id']))
                updated_count += 1
            else:
                not_found_count += 1

        # Commit all updates
        conn.commit()
        cursor.close()
        conn.close()

        return updated_count, not_found_count

    except Exception as e:
        st.error(f"Error fixing tee times: {e}")
        return 0, 0


def delete_booking(booking_id: str):
    """Delete a booking from the database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM bookings
            WHERE booking_id = %s;
        """, (booking_id,))

        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Error deleting booking: {e}")
        return False


def update_booking_note(booking_id: str, note: str):
    """Update booking note in database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE bookings
            SET note = %s, updated_at = NOW()
            WHERE booking_id = %s;
        """, (note, booking_id))

        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Error updating note: {e}")
        return False


# ========================================
# MAIN DASHBOARD
# ========================================

with st.sidebar:
    # Small logo in sidebar - stacked vertically
    st.image("assets/ssr-logo-notag.png", use_column_width=True)
    st.markdown("""
        <div style='text-align: center; margin-top: 0.5rem;'>
            <p style='color: #e8e3d9; font-size: 0.9rem; margin: 0; font-weight: 600; letter-spacing: 0.5px;'>Booking Dashboard</p>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='height: 1px; background: #6b7c3f; margin: 1rem 0 1.5rem 0;'></div>", unsafe_allow_html=True)

    st.markdown(f"<div class='user-badge'>{st.session_state.full_name}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='club-badge'>{st.session_state.customer_id.title()}</div>", unsafe_allow_html=True)

    st.markdown("<div style='height: 1px; background: #6b7c3f; margin: 1.5rem 0;'></div>", unsafe_allow_html=True)

    if st.button("Logout", use_container_width=True):
        logout()
        st.rerun()

    st.markdown("<div style='height: 1px; background: #6b7c3f; margin: 1.5rem 0;'></div>", unsafe_allow_html=True)

    st.markdown("#### Filters")

    # Initialize filter state
    if 'auto_include_status' not in st.session_state:
        st.session_state.auto_include_status = set()
    if 'clicked_status_filter' not in st.session_state:
        st.session_state.clicked_status_filter = None
    if 'date_filter_preset' not in st.session_state:
        st.session_state.date_filter_preset = "Next 30 Days"

    # Date preset selector
    date_preset = st.selectbox(
        "Date Preset",
        ["Today", "Next 7 Days", "Next 30 Days", "Next 60 Days", "Next 90 Days", "All Upcoming", "Custom"],
        index=2  # Default to "Next 30 Days"
    )

    # Calculate date range based on preset
    if date_preset == "Today":
        date_range = (datetime.now().date(), datetime.now().date())
    elif date_preset == "Next 7 Days":
        date_range = (datetime.now().date(), datetime.now().date() + timedelta(days=7))
    elif date_preset == "Next 30 Days":
        date_range = (datetime.now().date(), datetime.now().date() + timedelta(days=30))
    elif date_preset == "Next 60 Days":
        date_range = (datetime.now().date(), datetime.now().date() + timedelta(days=60))
    elif date_preset == "Next 90 Days":
        date_range = (datetime.now().date(), datetime.now().date() + timedelta(days=90))
    elif date_preset == "All Upcoming":
        date_range = (datetime.now().date(), datetime.now().date() + timedelta(days=365))
    else:  # Custom
        date_range = st.date_input(
            "Custom Date Range",
            value=(datetime.now().date(), datetime.now().date() + timedelta(days=30))
        )

    # Status filter - if clicked from metric card, use that
    if st.session_state.clicked_status_filter:
        default_statuses = [st.session_state.clicked_status_filter]
    else:
        # Merge default statuses with auto-included ones
        default_statuses = ["Inquiry", "Requested", "Confirmed", "Booked", "Pending"]
        default_statuses = list(set(default_statuses) | st.session_state.auto_include_status)

    status_filter = st.multiselect(
        "Status",
        ["Inquiry", "Requested", "Confirmed", "Booked", "Rejected", "Cancelled", "Pending"],
        default=default_statuses
    )

    # Hotel requirement filter
    hotel_filter = st.selectbox(
        "Hotel Requirement",
        ["All", "Hotel Required", "No Hotel"],
        index=0
    )

    # Clear filter button
    if st.button("Clear All Filters", use_container_width=True):
        st.session_state.clicked_status_filter = None
        st.cache_data.clear()
        st.rerun()

st.markdown("""
    <h1 style='margin-bottom: 1rem;'>Streamsong Dashboard</h1>
""", unsafe_allow_html=True)

# Create tabs for different sections
tab1, tab2, tab3 = st.tabs(["Bookings", "Analytics", "Reports"])

with tab1:
    st.markdown("""
        <h2 style='margin-bottom: 0.5rem;'>Booking Requests</h2>
        <p style='color: #d4b896; margin-bottom: 1rem; font-size: 0.9375rem;'>Manage and track all incoming tee time requests</p>
    """, unsafe_allow_html=True)

    # Show active filter indicator
    if st.session_state.clicked_status_filter:
        st.markdown(f"""
            <div style='background: #3d5266; border: 2px solid #6b7c3f; border-radius: 8px; padding: 0.75rem 1rem; margin-bottom: 1.5rem; display: flex; align-items: center; justify-content: space-between;'>
                <div style='display: flex; align-items: center; gap: 0.5rem;'>
                    <span style='color: #6b7c3f; font-weight: 600; font-size: 1rem;'>Filtering by: {st.session_state.clicked_status_filter}</span>
                </div>
            </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("<div style='margin-bottom: 1rem;'></div>", unsafe_allow_html=True)

    df, source = load_bookings_from_db(st.session_state.customer_id)

    if df.empty:
        st.info("No bookings found")
        st.stop()

    filtered_df = df.copy()
    if status_filter:
        filtered_df = filtered_df[filtered_df['status'].isin(status_filter)]

    # Handle date range filtering
    if date_range:
        if isinstance(date_range, tuple) and len(date_range) == 2:
            start_date, end_date = date_range
            filtered_df = filtered_df[
                (filtered_df['date'].dt.date >= start_date) &
                (filtered_df['date'].dt.date <= end_date)
            ]
        elif hasattr(date_range, '__len__') and len(date_range) == 2:
            start_date, end_date = date_range[0], date_range[1]
            filtered_df = filtered_df[
                (filtered_df['date'].dt.date >= start_date) &
                (filtered_df['date'].dt.date <= end_date)
            ]

    # Handle hotel requirement filtering
    if hotel_filter == "Hotel Required":
        filtered_df = filtered_df[filtered_df['hotel_required'] == True]
    elif hotel_filter == "No Hotel":
        filtered_df = filtered_df[filtered_df['hotel_required'] == False]

    col1, col2, col3, col4 = st.columns(4)

    # Calculate counts for all statuses (before filtering)
    all_inquiry_count = len(df[df['status'].isin(['Inquiry', 'Pending'])])
    all_requested_count = len(df[df['status'] == 'Requested'])
    all_confirmed_count = len(df[df['status'] == 'Confirmed'])
    all_booked_count = len(df[df['status'] == 'Booked'])

    with col1:
        inquiry_count = len(filtered_df[filtered_df['status'].isin(['Inquiry', 'Pending'])])
        if st.button(f"Inquiry\n{all_inquiry_count}", key="filter_inquiry", use_container_width=True, help="Click to filter Inquiry status"):
            st.session_state.clicked_status_filter = "Inquiry"
            st.cache_data.clear()
            st.rerun()
        st.markdown(f"<div style='text-align: center; color: #d4b896; font-size: 0.75rem; margin-top: -0.5rem;'>Showing: {inquiry_count}</div>", unsafe_allow_html=True)
    
    with col2:
        requested_count = len(filtered_df[filtered_df['status'] == 'Requested'])
        if st.button(f"Requested\n{all_requested_count}", key="filter_requested", use_container_width=True, help="Click to filter Requested status"):
            st.session_state.clicked_status_filter = "Requested"
            st.cache_data.clear()
            st.rerun()
        st.markdown(f"<div style='text-align: center; color: #d4b896; font-size: 0.75rem; margin-top: -0.5rem;'>Showing: {requested_count}</div>", unsafe_allow_html=True)
    
    with col3:
        confirmed_count = len(filtered_df[filtered_df['status'] == 'Confirmed'])
        if st.button(f"Confirmed\n{all_confirmed_count}", key="filter_confirmed", use_container_width=True, help="Click to filter Confirmed status"):
            st.session_state.clicked_status_filter = "Confirmed"
            st.cache_data.clear()
            st.rerun()
        st.markdown(f"<div style='text-align: center; color: #d4b896; font-size: 0.75rem; margin-top: -0.5rem;'>Showing: {confirmed_count}</div>", unsafe_allow_html=True)
    
    with col4:
        booked_count = len(filtered_df[filtered_df['status'] == 'Booked'])
        if st.button(f"Booked\n{all_booked_count}", key="filter_booked", use_container_width=True, help="Click to filter Booked status"):
            st.session_state.clicked_status_filter = "Booked"
            st.cache_data.clear()
            st.rerun()
        st.markdown(f"<div style='text-align: center; color: #d4b896; font-size: 0.75rem; margin-top: -0.5rem;'>Showing: {booked_count}</div>", unsafe_allow_html=True)
    
    st.markdown("<div style='height: 2px; background: #6b7c3f; margin: 2rem 0;'></div>", unsafe_allow_html=True)
    
    # Format date range string
    if date_range:
        if isinstance(date_range, tuple) and len(date_range) == 2:
            date_str = f"{date_range[0].strftime('%b %d')} to {date_range[1].strftime('%b %d, %Y')}"
        elif hasattr(date_range, '__len__') and len(date_range) == 2:
            date_str = f"{date_range[0].strftime('%b %d')} to {date_range[1].strftime('%b %d, %Y')}"
        else:
            date_str = "all dates"
    else:
        date_str = "all dates"
    
    st.markdown(f"""
        <div style='margin-bottom: 1.5rem;'>
            <h3 style='color: #f9fafb; font-weight: 600; font-size: 1.125rem;'>{len(filtered_df)} Active Requests</h3>
            <p style='color: #64748b; font-size: 0.875rem; margin-top: 0.25rem;'>Showing bookings from {date_str}</p>
        </div>
    """, unsafe_allow_html=True)
    
    # ========================================
    # BOOKING CARDS - ENHANCED VERSION
    # ========================================
    for idx, booking in filtered_df.iterrows():
        status_icon = get_status_icon(booking['status'])
        status_class = get_status_color(booking['status'])
    
        tee_time_display = booking.get('tee_time', 'Not Specified')
        if tee_time_display == 'None' or tee_time_display is None or pd.isna(tee_time_display):
            tee_time_display = 'Not Specified'
    
        note_content = booking.get('note', '')
        if note_content is None or pd.isna(note_content) or str(note_content).strip() == '':
            note_content = 'No additional information provided'

        # Strip whitespace and ensure we have actual content
        note_content = str(note_content).strip()
        if not note_content:
            note_content = 'No additional information provided'
    
        # Prepare progress bar data
        current_status = booking['status']
        if current_status == 'Pending':
            current_status = 'Inquiry'
    
        stages = [
            {'name': 'Inquiry', 'color': '#87a7b3'},
            {'name': 'Requested', 'color': '#cc8855'},
            {'name': 'Confirmed', 'color': '#8b9456'},
            {'name': 'Booked', 'color': '#6b7c3f'}
        ]
    
        is_rejected = current_status == 'Rejected'
        is_cancelled = current_status == 'Cancelled'
        current_index = next((i for i, s in enumerate(stages) if s['name'] == current_status), 0)
        progress_width = (current_index / (len(stages) - 1)) * 100 if len(stages) > 1 else 0
    
        # Format requested time
        requested_time = booking['timestamp'].strftime('%b %d • %I:%M %p')
    
        with st.container():
            # Build progress bar HTML inline
            if is_rejected or is_cancelled:
                status_color = '#a0653f' if is_rejected else '#666666'
                progress_html = f"<div style='background: #3d5266; padding: 1rem; border-radius: 8px; border: 2px solid #6b7c3f;'><div style='display: flex; align-items: center; justify-content: center; gap: 0.75rem;'><div style='width: 12px; height: 12px; border-radius: 50%; background: {status_color};'></div><span style='color: {status_color}; font-weight: 700; font-size: 1rem; text-transform: uppercase; letter-spacing: 0.5px;'>{current_status}</span></div></div>"
            else:
                # Build stage nodes HTML
                stages_html = ""
                for i, stage in enumerate(stages):
                    is_active = i <= current_index
                    is_current = i == current_index
                    bg_color = stage['color'] if is_active else '#4a6278'
                    text_color = '#f7f5f2' if is_active else '#999999'
                    border_color = stage['color'] if is_current else ('#6b7c3f' if is_active else '#4a6278')
                    box_shadow = '0 0 0 4px rgba(107, 124, 63, 0.4)' if is_current else 'none'
                    font_weight = '700' if is_current else '600'
    
                    stages_html += f"<div style='display: flex; flex-direction: column; align-items: center; z-index: 3; position: relative;'><div style='width: 1.5rem; height: 1.5rem; border-radius: 50%; background: {bg_color}; border: 3px solid {border_color}; box-shadow: {box_shadow}; transition: all 0.3s ease;'></div><div style='margin-top: 0.5rem; font-size: 0.7rem; font-weight: {font_weight}; color: {text_color}; text-transform: uppercase; letter-spacing: 0.5px; white-space: nowrap;'>{stage['name']}</div></div>"
    
                progress_html = f"<div style='background: #3d5266; padding: 1.25rem; border-radius: 8px; border: 2px solid #6b7c3f;'><div style='display: flex; align-items: center; justify-content: space-between; position: relative;'><div style='position: absolute; top: 0.75rem; left: 2rem; right: 2rem; height: 3px; background: #4a6278; z-index: 1;'></div><div style='position: absolute; top: 0.75rem; left: 2rem; width: calc({progress_width}% - 2rem); height: 3px; background: linear-gradient(90deg, #87a7b3, #6b7c3f); z-index: 2;'></div>{stages_html}</div></div>"
    
            # Hotel requirement badge and dates
            hotel_required = booking.get('hotel_required', False)
            hotel_badge = ""
            hotel_dates_html = ""

            if hotel_required:
                hotel_badge = "<div style='display: inline-block; background: #cc8855; color: #ffffff; padding: 0.4rem 0.8rem; border-radius: 6px; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; margin-left: 0.5rem;'>Hotel Required</div>"

                # Format hotel dates if available
                hotel_checkin = booking.get('hotel_checkin')
                hotel_checkout = booking.get('hotel_checkout')

                if hotel_checkin and not pd.isna(hotel_checkin):
                    checkin_str = hotel_checkin.strftime('%b %d, %Y')
                else:
                    checkin_str = "Not Set"

                if hotel_checkout and not pd.isna(hotel_checkout):
                    checkout_str = hotel_checkout.strftime('%b %d, %Y')
                else:
                    checkout_str = "Not Set"

                hotel_dates_html = f"<div style='background: #cc8855; padding: 1rem; border-radius: 8px; margin-top: 1rem;'><div style='color: #ffffff; font-weight: 700; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 0.75rem;'>Hotel Accommodation</div><div style='display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;'><div><div style='color: rgba(255,255,255,0.8); font-size: 0.7rem; font-weight: 600; text-transform: uppercase; margin-bottom: 0.25rem;'>Check-In</div><div style='color: #ffffff; font-size: 0.95rem; font-weight: 700;'>{checkin_str}</div></div><div><div style='color: rgba(255,255,255,0.8); font-size: 0.7rem; font-weight: 600; text-transform: uppercase; margin-bottom: 0.25rem;'>Check-Out</div><div style='color: #ffffff; font-size: 0.95rem; font-weight: 700;'>{checkout_str}</div></div></div></div>"

            # Escape and format note content for display
            note_display = html.escape(note_content).replace('\n', '<br>')

            # Build complete card HTML (without notes - notes will be in expander below)
            card_html = f"<div class='booking-card' style='background: linear-gradient(135deg, #3d5266 0%, #4a6278 100%); border: 2px solid #6b7c3f; border-radius: 12px; padding: 1.5rem; margin-bottom: 0.5rem; box-shadow: 0 4px 16px rgba(107, 124, 63, 0.3); transition: all 0.3s ease;'><div style='display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1.25rem;'><div style='flex: 1;'><div style='display: flex; align-items: center;'><div class='booking-id' style='margin-bottom: 0.5rem;'>{html.escape(str(booking['booking_id']))}</div>{hotel_badge}</div><div class='booking-email'>{html.escape(str(booking['guest_email']))}</div></div><div style='text-align: right;'><div class='timestamp'>REQUESTED</div><div class='timestamp-value'>{requested_time}</div></div></div><div style='margin-bottom: 1.5rem;'>{progress_html}</div><div style='height: 1px; background: linear-gradient(90deg, transparent, #6b7c3f, transparent); margin: 1.5rem 0;'></div><div style='display: grid; grid-template-columns: repeat(4, 1fr); gap: 1.5rem; margin-bottom: 1rem;'><div><div class='data-label' style='margin-bottom: 0.5rem;'>TEE DATE</div><div style='font-size: 1rem; font-weight: 600; color: #f7f5f2;'>{booking['date'].strftime('%b %d, %Y')}</div></div><div><div class='data-label' style='margin-bottom: 0.5rem;'>TEE TIME</div><div style='font-size: 1rem; font-weight: 600; color: #f7f5f2;'>{tee_time_display}</div></div><div><div class='data-label' style='margin-bottom: 0.5rem;'>PLAYERS</div><div style='font-size: 1rem; font-weight: 600; color: #f7f5f2;'>{booking['players']}</div></div><div><div class='data-label' style='margin-bottom: 0.5rem;'>TOTAL</div><div style='font-size: 1.5rem; font-weight: 700; color: #6b7c3f;'>${booking['total']:,.2f}</div></div></div>{hotel_dates_html}</div>"

            # Render the complete card
            st.markdown(card_html, unsafe_allow_html=True)

            # Notes dropdown/expander
            with st.expander("📝 View/Edit Booking Notes & Email Content", expanded=False):
                # Display current notes
                st.markdown("""
                    <div style='background: #4a6278; padding: 0.75rem 1rem; border-radius: 8px 8px 0 0; border: 2px solid #6b7c3f; border-bottom: none; margin-bottom: 0;'>
                        <div style='color: #d4b896; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; margin: 0;'>Current Notes</div>
                    </div>
                """, unsafe_allow_html=True)

                # Editable notes text area
                updated_note = st.text_area(
                    label="Edit notes",
                    value=note_content,
                    height=250,
                    disabled=False,
                    label_visibility="collapsed",
                    key=f"note_edit_{booking['booking_id']}"
                )

                # Save notes button
                if updated_note != note_content:
                    if st.button("💾 Save Notes", key=f"save_note_{booking['booking_id']}", use_container_width=True):
                        if update_booking_note(booking['booking_id'], updated_note):
                            st.success("Notes saved successfully!")
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error("Failed to save notes")

                # Show last updated info if available
                if booking.get('updated_by') and not pd.isna(booking.get('updated_by')):
                    st.markdown(f"""
                        <div style='margin-top: 1rem; padding: 0.75rem; background: #3d5266; border-radius: 8px; border: 2px solid #6b7c3f;'>
                            <div style='color: #d4b896; font-size: 0.7rem; font-weight: 600; text-transform: uppercase;'>Last Updated</div>
                            <div style='color: #f7f5f2; font-size: 0.875rem; margin-top: 0.25rem;'>{booking['updated_at'].strftime('%b %d, %Y • %I:%M %p')} by {booking['updated_by']}</div>
                        </div>
                    """, unsafe_allow_html=True)

            # Status navigation buttons - single row at bottom
            current_status = booking['status']

            # Create consistent button row for all statuses
            btn_cols = st.columns(6)

            # Column 0: Previous Stage (if applicable)
            with btn_cols[0]:
                if current_status == 'Requested':
                    if st.button("← Inquiry", key=f"nav_back_inq_{booking['booking_id']}", use_container_width=True):
                        if update_booking_status(booking['booking_id'], 'Inquiry', st.session_state.username):
                            st.cache_data.clear()
                            st.rerun()
                elif current_status == 'Confirmed':
                    if st.button("← Requested", key=f"nav_back_req_{booking['booking_id']}", use_container_width=True):
                        if update_booking_status(booking['booking_id'], 'Requested', st.session_state.username):
                            st.cache_data.clear()
                            st.rerun()
                elif current_status == 'Booked':
                    if st.button("← Confirmed", key=f"nav_back_conf_{booking['booking_id']}", use_container_width=True):
                        if update_booking_status(booking['booking_id'], 'Confirmed', st.session_state.username):
                            st.cache_data.clear()
                            st.rerun()

            # Column 1: To Requested
            with btn_cols[1]:
                if current_status in ['Inquiry', 'Pending']:
                    if st.button("→ Requested", key=f"nav_req_{booking['booking_id']}", use_container_width=True):
                        if update_booking_status(booking['booking_id'], 'Requested', st.session_state.username):
                            st.cache_data.clear()
                            st.rerun()

            # Column 2: To Confirmed
            with btn_cols[2]:
                if current_status == 'Requested':
                    if st.button("→ Confirmed", key=f"nav_conf_{booking['booking_id']}", use_container_width=True):
                        if update_booking_status(booking['booking_id'], 'Confirmed', st.session_state.username):
                            st.cache_data.clear()
                            st.rerun()

            # Column 3: To Booked
            with btn_cols[3]:
                if current_status == 'Confirmed':
                    if st.button("→ Booked", key=f"nav_book_{booking['booking_id']}", use_container_width=True):
                        if update_booking_status(booking['booking_id'], 'Booked', st.session_state.username):
                            st.cache_data.clear()
                            st.rerun()

            # Column 4: Reject/Cancel
            with btn_cols[4]:
                if current_status not in ['Rejected', 'Cancelled', 'Booked']:
                    if st.button("✕ Reject", key=f"nav_rej_{booking['booking_id']}", use_container_width=True):
                        if update_booking_status(booking['booking_id'], 'Rejected', st.session_state.username):
                            st.cache_data.clear()
                            st.rerun()
                elif current_status == 'Booked':
                    if st.button("✕ Cancel", key=f"nav_cancel_{booking['booking_id']}", use_container_width=True):
                        if update_booking_status(booking['booking_id'], 'Cancelled', st.session_state.username):
                            st.cache_data.clear()
                            st.rerun()

            # Column 5: Restore (for rejected/cancelled)
            with btn_cols[5]:
                if current_status in ['Rejected', 'Cancelled']:
                    if st.button("↻ Restore", key=f"nav_restore_{booking['booking_id']}", use_container_width=True):
                        if update_booking_status(booking['booking_id'], 'Inquiry', st.session_state.username):
                            st.cache_data.clear()
                            st.rerun()

            # Add visual separator between bookings
            st.markdown("<div style='height: 1.5rem;'></div>", unsafe_allow_html=True)

    # End of booking cards loop

    st.markdown("<div style='height: 2px; background: #6b7c3f; margin: 2rem 0;'></div>", unsafe_allow_html=True)

    # Remove old expander code - everything is now in the main card
    if False:  # Placeholder to maintain structure
        with st.expander("View Full Details", expanded=False):
                # Status Change Actions
                st.markdown("### Status Management")

                current_status = booking['status']

                if current_status in ['Inquiry', 'Pending']:
                    exp_col1, exp_col2 = st.columns(2)
                    with exp_col1:
                        if st.button("→ Move to Requested", key=f"exp_req_{booking['booking_id']}", use_container_width=True):
                            if update_booking_status(booking['booking_id'], 'Requested', st.session_state.username):
                                st.success("Moved to Requested")
                                st.cache_data.clear()
                                st.rerun()
                    with exp_col2:
                        if st.button("✕ Reject Booking", key=f"exp_rej_inq_{booking['booking_id']}", use_container_width=True):
                            if update_booking_status(booking['booking_id'], 'Rejected', st.session_state.username):
                                st.warning("Booking Rejected")
                                st.cache_data.clear()
                                st.rerun()

                elif current_status == 'Requested':
                    exp_col1, exp_col2, exp_col3 = st.columns(3)
                    with exp_col1:
                        if st.button("← Back to Inquiry", key=f"exp_back_inq_{booking['booking_id']}", use_container_width=True):
                            if update_booking_status(booking['booking_id'], 'Inquiry', st.session_state.username):
                                st.success("Moved to Inquiry")
                                st.cache_data.clear()
                                st.rerun()
                    with exp_col2:
                        if st.button("→ Move to Confirmed", key=f"exp_conf_{booking['booking_id']}", use_container_width=True):
                            if update_booking_status(booking['booking_id'], 'Confirmed', st.session_state.username):
                                st.success("Moved to Confirmed")
                                st.cache_data.clear()
                                st.rerun()
                    with exp_col3:
                        if st.button("✕ Reject Booking", key=f"exp_rej_req_{booking['booking_id']}", use_container_width=True):
                            if update_booking_status(booking['booking_id'], 'Rejected', st.session_state.username):
                                st.warning("Booking Rejected")
                                st.cache_data.clear()
                                st.rerun()

                elif current_status == 'Confirmed':
                    exp_col1, exp_col2, exp_col3 = st.columns(3)
                    with exp_col1:
                        if st.button("← Back to Requested", key=f"exp_back_req_{booking['booking_id']}", use_container_width=True):
                            if update_booking_status(booking['booking_id'], 'Requested', st.session_state.username):
                                st.success("Moved to Requested")
                                st.cache_data.clear()
                                st.rerun()
                    with exp_col2:
                        if st.button("→ Mark as Booked", key=f"exp_book_{booking['booking_id']}", use_container_width=True):
                            if update_booking_status(booking['booking_id'], 'Booked', st.session_state.username):
                                st.success("Marked as Booked")
                                st.cache_data.clear()
                                st.rerun()
                    with exp_col3:
                        if st.button("✕ Reject Booking", key=f"exp_rej_conf_{booking['booking_id']}", use_container_width=True):
                            if update_booking_status(booking['booking_id'], 'Rejected', st.session_state.username):
                                st.warning("Booking Rejected")
                                st.cache_data.clear()
                                st.rerun()

                elif current_status == 'Booked':
                    exp_col1, exp_col2 = st.columns(2)
                    with exp_col1:
                        if st.button("← Back to Confirmed", key=f"exp_back_conf_{booking['booking_id']}", use_container_width=True):
                            if update_booking_status(booking['booking_id'], 'Confirmed', st.session_state.username):
                                st.success("Moved to Confirmed")
                                st.cache_data.clear()
                                st.rerun()
                    with exp_col2:
                        if st.button("✕ Cancel Booking", key=f"exp_cancel_{booking['booking_id']}", use_container_width=True):
                            if update_booking_status(booking['booking_id'], 'Cancelled', st.session_state.username):
                                st.warning("Booking Cancelled")
                                st.cache_data.clear()
                                st.rerun()

                elif current_status in ['Rejected', 'Cancelled']:
                    exp_col1, exp_col2 = st.columns(2)
                    with exp_col1:
                        if st.button("↻ Restore to Inquiry", key=f"exp_restore_{booking['booking_id']}", use_container_width=True):
                            if update_booking_status(booking['booking_id'], 'Inquiry', st.session_state.username):
                                st.success("Restored to Inquiry")
                                st.cache_data.clear()
                                st.rerun()

                st.markdown("<div style='height: 2px; background: #6b7c3f; margin: 1.5rem 0;'></div>", unsafe_allow_html=True)
    
                # Booking notes section
                st.markdown("""
                    <div style='background: #3d5266; padding: 0.75rem 1rem; border-radius: 8px 8px 0 0; border: 2px solid #6b7c3f; border-bottom: none; margin-bottom: 0;'>
                        <div class='data-label' style='margin: 0;'>BOOKING NOTES</div>
                    </div>
                """, unsafe_allow_html=True)
    
                # Editable notes text area
                updated_note = st.text_area(
                    label="Notes",
                    value=note_content,
                    height=200,
                    disabled=False,
                    label_visibility="collapsed",
                    key=f"note_{booking['booking_id']}"
                )
    
                # Save notes button
                if updated_note != note_content:
                    if st.button("Save Notes", key=f"save_note_{booking['booking_id']}", use_container_width=True):
                        if update_booking_note(booking['booking_id'], updated_note):
                            st.success("Notes saved successfully!")
                            st.cache_data.clear()
                            st.rerun()
    
                if booking.get('updated_by') and not pd.isna(booking.get('updated_by')):
                    st.markdown(f"""
                        <div style='margin-top: 1.5rem; padding: 1rem; background: #3d5266; border-radius: 8px; border: 2px solid #6b7c3f;'>
                            <div class='data-label'>LAST UPDATED</div>
                            <div style='color: #f7f5f2; font-size: 0.875rem; margin-top: 0.5rem;'>{booking['updated_at'].strftime('%b %d, %Y • %I:%M %p')}</div>
                            <div style='color: #d4b896; font-size: 0.8125rem; margin-top: 0.25rem;'>by {booking['updated_by']}</div>
                        </div>
                    """, unsafe_allow_html=True)
    
                # Delete booking button (with confirmation)
                st.markdown("<div style='margin-top: 1.5rem; border-top: 2px solid #6b7c3f; padding-top: 1rem;'></div>", unsafe_allow_html=True)
                st.markdown("<div style='color: #cc8855; font-weight: 600; font-size: 0.875rem; margin-bottom: 0.5rem;'>Danger Zone</div>", unsafe_allow_html=True)
    
                # Initialize session state for delete confirmation
                if f"confirm_delete_{booking['booking_id']}" not in st.session_state:
                    st.session_state[f"confirm_delete_{booking['booking_id']}"] = False
    
                if not st.session_state[f"confirm_delete_{booking['booking_id']}"]:
                    if st.button("Delete Booking", key=f"del_{booking['booking_id']}", use_container_width=True, type="secondary"):
                        st.session_state[f"confirm_delete_{booking['booking_id']}"] = True
                        st.rerun()
                else:
                    st.warning("Are you sure? This action cannot be undone.")
                    col_confirm1, col_confirm2 = st.columns(2)
                    with col_confirm1:
                        if st.button("Yes, Delete", key=f"confirm_del_{booking['booking_id']}", use_container_width=True):
                            if delete_booking(booking['booking_id']):
                                st.success("Booking deleted successfully!")
                                st.cache_data.clear()
                                st.session_state[f"confirm_delete_{booking['booking_id']}"] = False
                                st.rerun()
                    with col_confirm2:
                        if st.button("Cancel", key=f"cancel_del_{booking['booking_id']}", use_container_width=True):
                            st.session_state[f"confirm_delete_{booking['booking_id']}"] = False
                            st.rerun()
    
    st.markdown("<div style='height: 2px; background: #6b7c3f; margin: 2rem 0;'></div>", unsafe_allow_html=True)
    st.markdown("#### Export Options")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("Export to Excel", use_container_width=True):
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                filtered_df.to_excel(writer, index=False, sheet_name='Bookings')
    
            st.download_button(
                label="Download Excel",
                data=output.getvalue(),
                file_name=f"bookings_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
    
    with col2:
        if st.button("Export to CSV", use_container_width=True):
            csv = filtered_df.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"bookings_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
    
    with col3:
        if st.button("Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    
    with col4:
        if st.button("Fix Tee Times", use_container_width=True):
            with st.spinner("Extracting tee times from email content..."):
                updated, not_found = fix_all_tee_times(st.session_state.customer_id)
                if updated > 0:
                    st.success(f"Updated {updated} booking(s) with extracted tee times!")
                    st.cache_data.clear()
                    st.rerun()
                elif not_found > 0:
                    st.warning(f"Could not extract tee times from {not_found} booking(s)")
                else:
                    st.info("All bookings already have tee times set")

with tab2:
    st.markdown("""
        <h2 style='margin-bottom: 0.5rem;'>Analytics</h2>
        <p style='color: #d4b896; margin-bottom: 1rem; font-size: 0.9375rem;'>Booking trends and performance metrics</p>
    """, unsafe_allow_html=True)

    # Load data for analytics
    df_analytics, _ = load_bookings_from_db(st.session_state.customer_id)

    if not df_analytics.empty:
        # Metrics row
        metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)

        with metric_col1:
            total_bookings = len(df_analytics)
            st.markdown(f"""
                <div class='metric-card'>
                    <div class='data-label'>TOTAL BOOKINGS</div>
                    <div style='font-size: 2rem; font-weight: 700; color: #f7f5f2; margin-top: 0.5rem;'>{total_bookings}</div>
                </div>
            """, unsafe_allow_html=True)

        with metric_col2:
            booked_count = len(df_analytics[df_analytics['status'] == 'Booked'])
            st.markdown(f"""
                <div class='metric-card'>
                    <div class='data-label'>CONFIRMED BOOKINGS</div>
                    <div style='font-size: 2rem; font-weight: 700; color: #6b7c3f; margin-top: 0.5rem;'>{booked_count}</div>
                </div>
            """, unsafe_allow_html=True)

        with metric_col3:
            total_revenue = df_analytics[df_analytics['status'] == 'Booked']['total'].sum()
            st.markdown(f"""
                <div class='metric-card'>
                    <div class='data-label'>TOTAL REVENUE</div>
                    <div style='font-size: 2rem; font-weight: 700; color: #6b7c3f; margin-top: 0.5rem;'>${total_revenue:,.2f}</div>
                </div>
            """, unsafe_allow_html=True)

        with metric_col4:
            conversion_rate = (booked_count / total_bookings * 100) if total_bookings > 0 else 0
            st.markdown(f"""
                <div class='metric-card'>
                    <div class='data-label'>CONVERSION RATE</div>
                    <div style='font-size: 2rem; font-weight: 700; color: #f7f5f2; margin-top: 0.5rem;'>{conversion_rate:.1f}%</div>
                </div>
            """, unsafe_allow_html=True)

        st.markdown("<div style='height: 2px; background: #6b7c3f; margin: 2rem 0;'></div>", unsafe_allow_html=True)

        # Status breakdown
        st.markdown("### Booking Status Breakdown")
        status_counts = df_analytics['status'].value_counts()

        status_col1, status_col2, status_col3 = st.columns(3)

        with status_col1:
            for status in ['Inquiry', 'Pending']:
                if status in status_counts.index:
                    count = status_counts[status]
                    st.markdown(f"""
                        <div style='padding: 1rem; background: #3d5266; border-radius: 8px; border: 2px solid #87a7b3; margin-bottom: 1rem;'>
                            <div class='data-label'>{status.upper()}</div>
                            <div style='font-size: 1.5rem; font-weight: 700; color: #87a7b3;'>{count}</div>
                        </div>
                    """, unsafe_allow_html=True)

        with status_col2:
            for status in ['Requested', 'Confirmed']:
                if status in status_counts.index:
                    count = status_counts[status]
                    color = '#cc8855' if status == 'Requested' else '#8b9456'
                    st.markdown(f"""
                        <div style='padding: 1rem; background: #3d5266; border-radius: 8px; border: 2px solid {color}; margin-bottom: 1rem;'>
                            <div class='data-label'>{status.upper()}</div>
                            <div style='font-size: 1.5rem; font-weight: 700; color: {color};'>{count}</div>
                        </div>
                    """, unsafe_allow_html=True)

        with status_col3:
            for status in ['Booked', 'Rejected', 'Cancelled']:
                if status in status_counts.index:
                    count = status_counts[status]
                    color = '#6b7c3f' if status == 'Booked' else ('#a0653f' if status == 'Rejected' else '#666666')
                    st.markdown(f"""
                        <div style='padding: 1rem; background: #3d5266; border-radius: 8px; border: 2px solid {color}; margin-bottom: 1rem;'>
                            <div class='data-label'>{status.upper()}</div>
                            <div style='font-size: 1.5rem; font-weight: 700; color: {color};'>{count}</div>
                        </div>
                    """, unsafe_allow_html=True)
    else:
        st.info("No data available for analytics")

with tab3:
    st.markdown("""
        <h2 style='margin-bottom: 0.5rem;'>Reports</h2>
        <p style='color: #d4b896; margin-bottom: 1rem; font-size: 0.9375rem;'>Generate and export detailed reports</p>
    """, unsafe_allow_html=True)

    # Load data for reports
    df_reports, _ = load_bookings_from_db(st.session_state.customer_id)

    if not df_reports.empty:
        # Report date range selector
        st.markdown("### Report Period")
        report_col1, report_col2 = st.columns(2)

        with report_col1:
            report_start = st.date_input("Start Date", value=datetime.now().date() - timedelta(days=30))

        with report_col2:
            report_end = st.date_input("End Date", value=datetime.now().date())

        # Filter data by report period
        report_df = df_reports[
            (df_reports['date'].dt.date >= report_start) &
            (df_reports['date'].dt.date <= report_end)
        ]

        st.markdown("<div style='height: 2px; background: #6b7c3f; margin: 2rem 0;'></div>", unsafe_allow_html=True)

        # Report summary
        st.markdown("### Report Summary")

        summary_col1, summary_col2, summary_col3 = st.columns(3)

        with summary_col1:
            total_in_period = len(report_df)
            st.metric("Total Bookings", total_in_period)

        with summary_col2:
            booked_in_period = len(report_df[report_df['status'] == 'Booked'])
            st.metric("Confirmed Bookings", booked_in_period)

        with summary_col3:
            revenue_in_period = report_df[report_df['status'] == 'Booked']['total'].sum()
            st.metric("Revenue", f"${revenue_in_period:,.2f}")

        st.markdown("<div style='height: 2px; background: #6b7c3f; margin: 2rem 0;'></div>", unsafe_allow_html=True)

        # Export options
        st.markdown("### Export Report")

        export_col1, export_col2, export_col3 = st.columns(3)

        with export_col1:
            if st.button("Export Full Report (Excel)", use_container_width=True):
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    report_df.to_excel(writer, index=False, sheet_name='Bookings Report')

                st.download_button(
                    label="Download Excel Report",
                    data=output.getvalue(),
                    file_name=f"streamsong_report_{report_start}_{report_end}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

        with export_col2:
            if st.button("Export Summary (CSV)", use_container_width=True):
                csv = report_df.to_csv(index=False)
                st.download_button(
                    label="Download CSV Report",
                    data=csv,
                    file_name=f"streamsong_report_{report_start}_{report_end}.csv",
                    mime="text/csv",
                    use_container_width=True
                )

        # Data preview
        st.markdown("<div style='height: 2px; background: #6b7c3f; margin: 2rem 0;'></div>", unsafe_allow_html=True)
        st.markdown("### Data Preview")
        st.dataframe(report_df[['booking_id', 'guest_email', 'date', 'tee_time', 'players', 'hotel_required', 'total', 'status']], use_container_width=True)
    else:
        st.info("No data available for reports")
