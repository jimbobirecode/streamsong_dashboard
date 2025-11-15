import streamlit as st
import pandas as pd
import os
import bcrypt
import psycopg
from psycopg.rows import dict_row
from datetime import datetime, timedelta
import plotly.graph_objects as go
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
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
        if user['password_hash']:
            if verify_password(password, user['password_hash']):
                # Update last_login
                cursor.execute("""
                    UPDATE dashboard_users 
                    SET last_login = CURRENT_TIMESTAMP
                    WHERE id = %s;
                """, (user['id'],))
                conn.commit()
                
                cursor.close()
                conn.close()
                return True, user['customer_id'], user['full_name'], user['must_change_password'], user['id']
        
        cursor.close()
        conn.close()
        return False, None, None, False, None
            
    except Exception as e:
        st.error(f"Database error: {e}")
        return False, None, None, False, None

def set_new_password(user_id: int, new_password: str):
    """Set new password for user (first time setup)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        password_hash = hash_password(new_password)
        
        cursor.execute("""
            UPDATE dashboard_users 
            SET password_hash = %s,
                temp_password = NULL,
                must_change_password = FALSE,
                password_changed_at = CURRENT_TIMESTAMP,
                last_login = CURRENT_TIMESTAMP
            WHERE id = %s;
        """, (password_hash, user_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        st.error(f"Error setting password: {e}")
        return False

# ========================================
# NOTES FUNCTIONS
# ========================================
def add_booking_note(booking_id: str, note: str, created_by: str, note_type: str = 'general', is_internal: bool = True):
    """Add a note to a booking (using history table if it exists, otherwise update main note field)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Try to use booking_notes table first (if it exists)
        try:
            cursor.execute("""
                INSERT INTO booking_notes (booking_id, note, created_by, note_type, is_internal)
                VALUES (%s, %s, %s, %s, %s)
            """, (booking_id, note, created_by, note_type, is_internal))
            conn.commit()
            cursor.close()
            conn.close()
            return True
        except:
            # If booking_notes table doesn't exist, append to main note field
            cursor.execute("""
                UPDATE bookings 
                SET note = CASE 
                    WHEN note IS NULL OR note = '' THEN %s
                    ELSE note || E'\n---\n' || %s
                END,
                updated_at = CURRENT_TIMESTAMP,
                updated_by = %s
                WHERE booking_id = %s
            """, (f"[{created_by}] {note}", f"[{created_by}] {note}", created_by, booking_id))
            conn.commit()
            cursor.close()
            conn.close()
            return True
            
    except Exception as e:
        st.error(f"Error adding note: {e}")
        return False

def get_booking_notes(booking_id: str):
    """Get all notes for a booking"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(row_factory=dict_row)
        
        # Try booking_notes table first
        try:
            cursor.execute("""
                SELECT note, created_by, created_at, note_type, is_internal
                FROM booking_notes
                WHERE booking_id = %s
                ORDER BY created_at DESC
            """, (booking_id,))
            notes = cursor.fetchall()
            cursor.close()
            conn.close()
            return notes
        except:
            # Fall back to main note field
            cursor.execute("""
                SELECT note, updated_by as created_by, updated_at as created_at
                FROM bookings
                WHERE booking_id = %s
            """, (booking_id,))
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if result and result['note']:
                # Parse concatenated notes
                notes = []
                for note_text in result['note'].split('\n---\n'):
                    notes.append({
                        'note': note_text,
                        'created_by': result.get('created_by', 'Unknown'),
                        'created_at': result.get('created_at'),
                        'note_type': 'general',
                        'is_internal': True
                    })
                return notes
            return []
            
    except Exception as e:
        st.error(f"Error fetching notes: {e}")
        return []

def update_booking_note(booking_id: str, note: str, updated_by: str):
    """Update the main booking note field"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE bookings 
            SET note = %s,
                updated_at = CURRENT_TIMESTAMP,
                updated_by = %s
            WHERE booking_id = %s
        """, (note, updated_by, booking_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        st.error(f"Error updating note: {e}")
        return False

def delete_booking(booking_id: str):
    """Delete a booking permanently"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Delete notes first (foreign key constraint)
        try:
            cursor.execute("DELETE FROM booking_notes WHERE booking_id = %s", (booking_id,))
        except:
            pass  # Table might not exist
        
        # Delete the booking
        cursor.execute("DELETE FROM bookings WHERE booking_id = %s", (booking_id,))
        deleted = cursor.rowcount
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return deleted > 0
        
    except Exception as e:
        st.error(f"Error deleting booking: {e}")
        return False

# ========================================
# CLUB CONFIGURATIONS with TeeMail Branding
# ========================================
CLUBS = {
    "streamsong": {
        "name": "Streamsong Resort",
        "api_url": os.getenv("STREAMSONG_API_URL", "https://streamsong-email-bot.onrender.com/api/bookings"),
        "from_email": "streamsong@bookings.teemail.io",
        "per_player_fee": 380.00,
        "smtp_user": os.getenv("STREAMSONG_SMTP_USER", os.getenv("SENDGRID_API_KEY", "")),
        "smtp_password": os.getenv("STREAMSONG_SMTP_PASSWORD", ""),
        "club_filter": "streamsong",
        "primary_color": "#1a5632",  # Streamsong Green
        "secondary_color": "#2c7a4d"  # Light Streamsong Green
    },
    "skerries": {
        "name": "Skerries Golf Club",
        "api_url": os.getenv("SKERRIES_API_URL", "https://skerries-emailbot.onrender.com/api/bookings"),
        "from_email": "bookings@skerriesgolfclub.ie",
        "per_player_fee": 250.00,
        "smtp_user": os.getenv("SKERRIES_SMTP_USER", ""),
        "smtp_password": os.getenv("SKERRIES_SMTP_PASSWORD", ""),
        "club_filter": "skerries",
        "primary_color": "#10b981",  # Emerald Green
        "secondary_color": "#059669"  # Dark Emerald
    },
    "baltray": {
        "name": "County Louth Golf Club",
        "api_url": os.getenv("COUNTYLOUTH_API_URL", "https://teemailsg-1.onrender.com/api/bookings"),
        "from_email": "teetimes@countylouthgolfclub.com",
        "per_player_fee": 325.00,
        "smtp_user": os.getenv("COUNTYLOUTH_SMTP_USER", ""),
        "smtp_password": os.getenv("COUNTYLOUTH_SMTP_PASSWORD", ""),
        "club_filter": "baltray",
        "primary_color": "#3b82f6",  # Bright Blue
        "secondary_color": "#2563eb"
    },
    "ardglass": {
        "name": "Ardglass Golf Club",
        "api_url": os.getenv("ARDGLASS_API_URL", "https://ardglass-emailbot.onrender.com/api/bookings"),
        "from_email": "bookings@ardglassgolfclub.com",
        "per_player_fee": 200.00,
        "smtp_user": os.getenv("ARDGLASS_SMTP_USER", ""),
        "smtp_password": os.getenv("ARDGLASS_SMTP_PASSWORD", ""),
        "club_filter": "ardglass",
        "primary_color": "#a78bfa",  # Soft Purple
        "secondary_color": "#8b5cf6"
    }
}

# API Configuration
API_URL = os.getenv("API_URL", "https://teemailsg-1.onrender.com/api/bookings")

# Global SMTP settings
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))

# ========================================
# SESSION STATE INITIALIZATION
# ========================================
if 'authenticated' not in st.session_state:
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
# PASSWORD CHANGE SCREEN
# ========================================
if st.session_state.show_password_change:
    st.markdown("""
        <style>
        .main { background: linear-gradient(135deg, #0a0e1a 0%, #1e293b 100%); }
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
        .stButton > button {
            background: linear-gradient(135deg, #059669 0%, #10b981 100%) !important;
            color: white !important;
            border: none !important;
            padding: 0.75rem 2rem !important;
            border-radius: 12px !important;
            font-weight: 600 !important;
            width: 100% !important;
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
        
        new_password = st.text_input("New Password", type="password", help="Minimum 8 characters")
        confirm_password = st.text_input("Confirm Password", type="password")
        
        submit = st.form_submit_button("Set Password", use_container_width=True)
        
        if submit:
            if not new_password or not confirm_password:
                st.error("❌ Please enter a password")
            elif len(new_password) < 8:
                st.error("❌ Password must be at least 8 characters")
            elif new_password != confirm_password:
                st.error("❌ Passwords do not match")
            else:
                if set_new_password(st.session_state.user_id, new_password):
                    st.success("✅ Password set successfully! Redirecting to dashboard...")
                    st.session_state.show_password_change = False
                    st.session_state.authenticated = True
                    st.session_state.must_change_password = False
                    st.balloons()
                    st.rerun()
                else:
                    st.error("❌ Error setting password. Please try again.")
    
    st.markdown("""
        <div style='text-align: center; color: #6b7280; font-size: 0.85rem; margin-top: 2rem;'>
            <p>Your password is encrypted and stored securely</p>
            <p style='font-size: 0.75rem; margin-top: 0.5rem;'>Powered by TeeMail</p>
        </div>
    """, unsafe_allow_html=True)
    
    st.stop()

# ========================================
# LOGIN SCREEN
# ========================================
if not st.session_state.authenticated:
    st.markdown("""
        <style>
        .main { background: linear-gradient(135deg, #0a0e1a 0%, #1e293b 100%); }
        .login-container {
            max-width: 400px;
            margin: 100px auto;
            padding: 2.5rem;
            background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
            border-radius: 16px;
            border: 1px solid rgba(16, 185, 129, 0.2);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        }
        .login-title {
            color: #f9fafb;
            font-size: 2.5rem;
            font-weight: 700;
            text-align: center;
            margin-bottom: 0.5rem;
        }
        .login-subtitle {
            color: #94a3b8;
            text-align: center;
            margin-bottom: 2rem;
            font-size: 1rem;
        }
        .stButton > button {
            background: linear-gradient(135deg, #059669 0%, #10b981 100%) !important;
            color: white !important;
            border: none !important;
            padding: 0.75rem 2rem !important;
            border-radius: 12px !important;
            font-weight: 600 !important;
            width: 100% !important;
            transition: all 0.3s ease !important;
        }
        .stButton > button:hover {
            transform: translateY(-2px) !important;
            box-shadow: 0 8px 20px rgba(16, 185, 129, 0.4) !important;
        }
        .stTextInput > div > div > input {
            background: #0a0e1a !important;
            border: 1px solid #334155 !important;
            border-radius: 10px !important;
            color: #f9fafb !important;
            padding: 0.75rem !important;
        }
        .stTextInput > div > div > input:focus {
            border-color: #10b981 !important;
            box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.2) !important;
        }
        </style>
    """, unsafe_allow_html=True)
    
    st.markdown("""
        <div class="login-container">
            <div class="login-title">🏌️ TeeMail</div>
            <div class="login-subtitle">Dashboard Login</div>
        </div>
    """, unsafe_allow_html=True)
    
    with st.form("login_form"):
        username = st.text_input("Username", placeholder="Enter your username")
        password = st.text_input("Password", type="password", placeholder="Enter your password", help="Use your temporary password for first login")
        submit = st.form_submit_button("Login", use_container_width=True)
        
        if submit:
            if username and password:
                success, customer_id, full_name, must_change, user_id = authenticate_user(username, password)
                
                if success:
                    st.session_state.customer_id = customer_id
                    st.session_state.username = username
                    st.session_state.full_name = full_name or username
                    st.session_state.user_id = user_id
                    st.session_state.must_change_password = must_change
                    
                    if must_change:
                        # Redirect to password change screen
                        st.session_state.show_password_change = True
                        st.success("✅ Login successful! Please set your password...")
                        st.rerun()
                    else:
                        # Normal login
                        st.session_state.authenticated = True
                        st.success("✅ Login successful!")
                        st.rerun()
                else:
                    st.error("❌ Invalid username or password")
            else:
                st.error("❌ Please enter username and password")
    
    st.markdown("""
        <div style='text-align: center; color: #6b7280; font-size: 0.85rem; margin-top: 2rem;'>
            <p>First time? Use the temporary password provided by your administrator</p>
            <p style='font-size: 0.75rem; margin-top: 0.5rem;'>Powered by TeeMail</p>
        </div>
    """, unsafe_allow_html=True)
    
    st.stop()

# ========================================
# GET CUSTOMER CONFIG
# ========================================
CUSTOMER_ID = st.session_state.customer_id
CLUB_CONFIG = CLUBS.get(CUSTOMER_ID, CLUBS['baltray'])

CLUB_NAME = CLUB_CONFIG['name']
FROM_EMAIL = CLUB_CONFIG['from_email']
PER_PLAYER_FEE = CLUB_CONFIG['per_player_fee']
CLUB_FILTER = CLUB_CONFIG['club_filter']
PRIMARY_COLOR = CLUB_CONFIG['primary_color']
SECONDARY_COLOR = CLUB_CONFIG['secondary_color']
EMAIL_BOT_API_URL = CLUB_CONFIG['api_url']
SMTP_USER = CLUB_CONFIG['smtp_user']
SMTP_PASSWORD = CLUB_CONFIG['smtp_password']

# ========================================
# OPTE BRANDING STYLES
# ========================================
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    * {{ font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }}
    
    /* TeeMail Dark Theme */
    .main {{ background: #0a0e1a; }}
    .block-container {{ padding-top: 2rem; padding-bottom: 2rem; }}
    
    /* Dashboard Header with Customer Branding */
    .dashboard-header {{
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
        padding: 2rem 2.5rem;
        border-radius: 16px;
        margin-bottom: 2rem;
        border: 1px solid rgba(16, 185, 129, 0.2);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
    }}
    
    .dashboard-title {{ 
        color: #f9fafb; 
        font-size: 2.25rem; 
        font-weight: 700; 
        margin: 0; 
        letter-spacing: -0.02em; 
    }}
    
    .dashboard-subtitle {{ 
        color: #94a3b8; 
        font-size: 1rem; 
        margin-top: 0.5rem; 
        font-weight: 400; 
    }}
    
    /* Notes Styling */
    .note-card {{
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        transition: all 0.2s ease;
    }}
    
    .note-card:hover {{
        border-color: {PRIMARY_COLOR};
        background: #1a2332;
    }}
    
    .note-header {{
        display: flex;
        justify-content: space-between;
        color: #94a3b8;
        font-size: 0.75rem;
        margin-bottom: 0.5rem;
    }}
    
    .note-content {{
        color: #f9fafb;
        font-size: 0.9rem;
        line-height: 1.5;
    }}
    
    /* Form Styling */
    .stTextArea > div > div > textarea {{
        background: #1e293b !important;
        border: 1px solid #334155 !important;
        border-radius: 8px !important;
        color: #f9fafb !important;
        font-family: inherit !important;
    }}
    
    .stTextArea > div > div > textarea:focus {{
        border-color: {PRIMARY_COLOR} !important;
        box-shadow: 0 0 0 2px rgba({int(PRIMARY_COLOR[1:3], 16)}, {int(PRIMARY_COLOR[3:5], 16)}, {int(PRIMARY_COLOR[5:7], 16)}, 0.2) !important;
    }}
    
    .stSelectbox > div > div {{
        background: #1e293b !important;
        border: 1px solid #334155 !important;
        border-radius: 8px !important;
    }}
    
    .stSelectbox > div > div:hover {{
        border-color: {PRIMARY_COLOR} !important;
    }}
    
    /* Metric Cards */
    [data-testid="stMetricValue"] {{ 
        font-size: 2.5rem; 
        font-weight: 700; 
        color: #f9fafb; 
    }}
    
    [data-testid="stMetricLabel"] {{ 
        font-size: 0.875rem; 
        font-weight: 600; 
        text-transform: uppercase; 
        letter-spacing: 0.05em; 
        color: #94a3b8; 
    }}
    
    div[data-testid="metric-container"] {{
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid #334155;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        transition: all 0.3s ease;
    }}
    
    div[data-testid="metric-container"]:hover {{ 
        transform: translateY(-4px); 
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4); 
        border-color: {PRIMARY_COLOR}; 
    }}
    
    /* Buttons with Customer Branding */
    .stButton > button {{
        background: linear-gradient(135deg, {SECONDARY_COLOR} 0%, {PRIMARY_COLOR} 100%);
        color: white;
        border: none;
        padding: 0.75rem 1.5rem;
        border-radius: 10px;
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
    
    .stDownloadButton > button {{
        background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%) !important;
        color: #1f2937 !important;
    }}
    
    /* Typography */
    h1, h2, h3, h4, h5, h6 {{ 
        color: #f9fafb !important; 
        font-weight: 700 !important; 
    }}
    
    p, span, div {{ 
        color: #f9fafb !important; 
    }}
    
    /* DataFrames */
    .dataframe {{
        background: #1e293b !important;
        border: 1px solid #334155 !important;
        border-radius: 12px !important;
        overflow: hidden !important;
    }}
    
    .dataframe thead tr th {{
        background: linear-gradient(135deg, #334155 0%, #475569 100%) !important;
        color: #f9fafb !important;
        font-weight: 600 !important;
        padding: 1rem !important;
        border-bottom: 2px solid {PRIMARY_COLOR} !important;
    }}
    
    .dataframe tbody tr {{ 
        border-bottom: 1px solid #2d3748 !important; 
        background: #1e293b !important; 
    }}
    
    .dataframe tbody tr:hover {{ 
        background: #2d3748 !important; 
    }}
    
    .dataframe tbody tr td {{ 
        padding: 1rem !important; 
        color: #f9fafb !important; 
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
    
    /* Status Badges */
    .status-badge {{
        padding: 0.375rem 0.875rem;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.8rem;
        display: inline-block;
    }}
    
    .status-pending {{ 
        background: rgba(251, 191, 36, 0.2); 
        color: #fbbf24; 
        border: 1px solid rgba(251, 191, 36, 0.3); 
    }}
    
    .status-confirmed {{ 
        background: rgba(16, 185, 129, 0.2); 
        color: #10b981; 
        border: 1px solid rgba(16, 185, 129, 0.3); 
    }}
    
    .status-rejected {{ 
        background: rgba(239, 68, 68, 0.2); 
        color: #ef4444; 
        border: 1px solid rgba(239, 68, 68, 0.3); 
    }}
    
    .status-cancelled {{ 
        background: rgba(156, 163, 175, 0.2); 
        color: #9ca3af; 
        border: 1px solid rgba(156, 163, 175, 0.3); 
    }}
    
    /* Hide Streamlit branding */
    #MainMenu {{visibility: hidden;}} 
    footer {{visibility: hidden;}} 
    header {{visibility: hidden;}}
    </style>
""", unsafe_allow_html=True)

# ========================================
# LOAD BOOKINGS (FILTERED BY CUSTOMER)
# ========================================
@st.cache_data(ttl=10)
def load_bookings_from_db(club_filter):
    """Load bookings directly from PostgreSQL database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(row_factory=dict_row)
        
        # Query bookings filtered by club
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
        
        # Convert to DataFrame
        df = pd.DataFrame(bookings)
        
        # Convert timestamp columns
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
        
        if 'customer_confirmed_at' in df.columns:
            df['customer_confirmed_at'] = pd.to_datetime(df['customer_confirmed_at'], errors='coerce')
        
        if 'updated_at' in df.columns:
            df['updated_at'] = pd.to_datetime(df['updated_at'], errors='coerce')
        
        if 'created_at' in df.columns:
            df['created_at'] = pd.to_datetime(df['created_at'], errors='coerce')
        
        # Ensure tee_time column exists
        if 'tee_time' not in df.columns:
            df['tee_time'] = None
        
        # Ensure booking_id exists (use id as fallback)
        if 'booking_id' not in df.columns:
            df['booking_id'] = df['id'].astype(str)
        
        # Ensure numeric columns
        df['total'] = pd.to_numeric(df['total'], errors='coerce').fillna(0)
        df['players'] = pd.to_numeric(df['players'], errors='coerce').fillna(0).astype(int)
        
        return df, 'postgresql'
        
    except Exception as e:
        st.error(f"❌ Database error loading bookings: {e}")
        return pd.DataFrame(), 'error'

def update_booking_status(booking_id, status, note=None, updated_by=None):
    """Update booking status directly in PostgreSQL database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Build update query
        if note and updated_by:
            cursor.execute("""
                UPDATE bookings 
                SET status = %s,
                    note = %s,
                    updated_at = CURRENT_TIMESTAMP,
                    updated_by = %s
                WHERE booking_id = %s
            """, (status, note, updated_by, booking_id))
        elif updated_by:
            cursor.execute("""
                UPDATE bookings 
                SET status = %s,
                    updated_at = CURRENT_TIMESTAMP,
                    updated_by = %s
                WHERE booking_id = %s
            """, (status, updated_by, booking_id))
        elif note:
            cursor.execute("""
                UPDATE bookings 
                SET status = %s,
                    note = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE booking_id = %s
            """, (status, note, booking_id))
        else:
            cursor.execute("""
                UPDATE bookings 
                SET status = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE booking_id = %s
            """, (status, booking_id))
        
        rows_updated = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()
        
        if rows_updated > 0:
            return True
        else:
            st.error(f"❌ Booking {booking_id} not found in database")
            return False
            
    except Exception as e:
        st.error(f"❌ Database error updating booking: {str(e)}")
        return False

def send_confirmation_email(booking_data, status):
    """Send confirmation email to guest"""
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"Booking {status}: {CLUB_NAME}"
        msg['From'] = FROM_EMAIL
        msg['To'] = booking_data['guest_email']
        
        if status == "Confirmed":
            html = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #1f2937; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #059669 0%, #10b981 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                    <h1 style="color: white; margin: 0;">🏌️ Booking Confirmed!</h1>
                </div>
                <div style="background: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px;">
                    <p style="font-size: 18px; color: #1f2937;"><strong>Great news!</strong> Your tee time has been confirmed.</p>
                    <div style="background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #10b981;">
                        <h3 style="color: #1f2937; margin-top: 0;">Booking Details</h3>
                        <p><strong>Date:</strong> {booking_data['date']}</p>
                        <p><strong>Players:</strong> {booking_data['players']}</p>
                        <p><strong>Total:</strong> €{booking_data['total']:,.2f}</p>
                    </div>
                    <p>We look forward to welcoming you to {CLUB_NAME}!</p>
                    <p style="color: #6b7280; font-size: 0.875rem; margin-top: 2rem;">Powered by TeeMail</p>
                </div>
            </body>
            </html>
            """
        else:
            html = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #1f2937; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                    <h1 style="color: white; margin: 0;">Booking Update</h1>
                </div>
                <div style="background: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px;">
                    <p style="font-size: 18px; color: #1f2937;">Your booking status: <strong>{status}</strong></p>
                    <p>Questions? Contact us at {FROM_EMAIL}</p>
                    <p style="color: #6b7280; font-size: 0.875rem; margin-top: 2rem;">Powered by TeeMail</p>
                </div>
            </body>
            </html>
            """
        
        msg.attach(MIMEText(html, 'html'))
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        st.error(f"Failed to send email: {str(e)}")
        return False

def generate_excel_report(df, report_name="Booking_Report"):
    """Generate Excel report with multiple sheets"""
    output = BytesIO()
    
    try:
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Prepare export dataframe
            df_export = df.copy()
            
            # Format datetime columns
            if 'timestamp' in df_export.columns:
                df_export['timestamp'] = df_export['timestamp'].apply(
                    lambda x: x.strftime('%Y-%m-%d %H:%M') if pd.notnull(x) else ''
                )
            
            if 'date' in df_export.columns:
                df_export['date'] = df_export['date'].apply(
                    lambda x: x.strftime('%Y-%m-%d') if pd.notnull(x) else ''
                )
            
            # Format confirmed_at if exists
            if 'customer_confirmed_at' in df_export.columns:
                df_export['customer_confirmed_at'] = df_export['customer_confirmed_at'].apply(
                    lambda x: x.strftime('%Y-%m-%d %H:%M') if pd.notnull(x) and hasattr(x, 'strftime') else (str(x) if pd.notnull(x) else '')
                )
            
            # Write bookings sheet
            df_export.to_excel(writer, sheet_name='Bookings', index=False)
            
            # Create summary sheet
            summary_data = {
                'Metric': [
                    'Total Bookings', 
                    'Pending', 
                    'Confirmed', 
                    'Rejected', 
                    'Cancelled',
                    'Total Revenue (Confirmed)', 
                    'Potential Revenue (Pending)', 
                    'Average Booking Value', 
                    'Total Players'
                ],
                'Value': [
                    len(df),
                    len(df[df['status'] == 'Pending']),
                    len(df[df['status'] == 'Confirmed']),
                    len(df[df['status'] == 'Rejected']),
                    len(df[df['status'] == 'Cancelled']),
                    f"€{df[df['status'] == 'Confirmed']['total'].sum():,.2f}",
                    f"€{df[df['status'] == 'Pending']['total'].sum():,.2f}",
                    f"€{df['total'].mean():,.2f}",
                    int(df['players'].sum())
                ]
            }
            
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # Make sure at least one sheet is visible
            workbook = writer.book
            if workbook.sheetnames:
                workbook.active = 0  # Set first sheet as active
        
        output.seek(0)
        return output
        
    except Exception as e:
        st.error(f"Error generating Excel report: {e}")
        # Return empty BytesIO on error
        output = BytesIO()
        return output

def generate_csv_report(df):
    """Generate CSV report"""
    df_export = df.copy()
    
    if 'timestamp' in df_export.columns:
        df_export['timestamp'] = df_export['timestamp'].apply(
            lambda x: x.strftime('%Y-%m-%d %H:%M') if pd.notnull(x) else ''
        )
    
    if 'date' in df_export.columns:
        df_export['date'] = df_export['date'].apply(
            lambda x: x.strftime('%Y-%m-%d') if pd.notnull(x) else ''
        )
    
    if 'customer_confirmed_at' in df_export.columns:
        df_export['customer_confirmed_at'] = df_export['customer_confirmed_at'].apply(
            lambda x: x.strftime('%Y-%m-%d %H:%M') if pd.notnull(x) and hasattr(x, 'strftime') else (str(x) if pd.notnull(x) else '')
        )
    
    return df_export.to_csv(index=False).encode('utf-8')

# ========================================
# MAIN DASHBOARD
# ========================================
df, storage_type = load_bookings_from_db(CLUB_FILTER)

st.markdown(f"""
    <div class="dashboard-header">
        <h1 class="dashboard-title">🏌️ {CLUB_NAME}</h1>
        <p class="dashboard-subtitle">Intelligent Booking Management • Powered by TeeMail</p>
    </div>
""", unsafe_allow_html=True)

# ========================================
# APPLY DATE AND STATUS FILTERS BEFORE SIDEBAR
# ========================================
# Initialize session state for dates if not exists
if 'filter_start_date' not in st.session_state:
    st.session_state.filter_start_date = datetime.now().date()
if 'filter_end_date' not in st.session_state:
    st.session_state.filter_end_date = datetime.now().date() + timedelta(days=30)

# Apply filters early so both sidebar and main use same filtered data
if not df.empty:
    # Get available statuses from current data
    available_statuses = sorted(df['status'].unique())
    
    # Initialize or validate status filter
    if 'status_filter' not in st.session_state:
        st.session_state.status_filter = available_statuses
    else:
        # Clean invalid statuses and ensure at least one exists
        valid_filters = [s for s in st.session_state.status_filter if s in available_statuses]
        st.session_state.status_filter = valid_filters if valid_filters else available_statuses
    
    # Apply filters
    df_filtered = df[
        (df['status'].isin(st.session_state.status_filter)) &
        (df['date'].dt.date >= st.session_state.filter_start_date) &
        (df['date'].dt.date <= st.session_state.filter_end_date)
    ]
else:
    df_filtered = df

# Sidebar
with st.sidebar:
    st.markdown(f"<div class='user-badge'>👤 {st.session_state.full_name}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='club-badge'>🏌️ {CLUB_NAME}</div>", unsafe_allow_html=True)
    
    st.markdown("---")
    
    if st.button("🚪 Logout", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
    
    st.markdown("---")
    st.markdown("### 🎯 Quick Stats")
    
    if not df_filtered.empty:
        st.metric("Total Bookings", f"{len(df_filtered):,}")
        st.metric("Pending", f"{len(df_filtered[df_filtered['status'] == 'Pending']):,}")
        st.metric("Confirmed", f"{len(df_filtered[df_filtered['status'] == 'Confirmed']):,}")
    
    st.markdown("---")
    st.markdown("### 🔍 Filters")
    
    if not df.empty:
        date_col1, date_col2 = st.columns(2)
        with date_col1:
            start_date = st.date_input(
                "From", 
                value=st.session_state.filter_start_date,
                key="start_date_input"
            )
            
            if start_date != st.session_state.filter_start_date:
                st.session_state.filter_start_date = start_date
                if st.session_state.filter_end_date < start_date:
                    st.session_state.filter_end_date = start_date + timedelta(days=30)
                st.rerun()
                
        with date_col2:
            end_date = st.date_input(
                "To", 
                value=st.session_state.filter_end_date,
                min_value=start_date,
                key="end_date_input"
            )
            
            if end_date != st.session_state.filter_end_date:
                st.session_state.filter_end_date = end_date
                st.rerun()
        
        # Status filter with dynamic validation
        available_statuses = sorted(df['status'].unique())
        
        status_filter = st.multiselect(
            "Status", 
            options=available_statuses,
            default=st.session_state.status_filter,
            key="status_multiselect"
        )
        
        if status_filter != st.session_state.status_filter:
            st.session_state.status_filter = status_filter if status_filter else available_statuses
            st.rerun()
    
    st.markdown("---")
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# Load bookings
if df.empty:
    st.info(f"📭 No bookings found for {CLUB_NAME}")
    st.markdown(f"""
        **Booking email:** `{CUSTOMER_ID}@booking.teemail.io`
        
        Bookings will appear here when guests email your booking address.
    """)
    st.stop()

# Connection status
if storage_type == "postgresql":
    st.success(f"✅ Connected to PostgreSQL Database")
elif storage_type == "error":
    st.error(f"❌ Cannot connect to PostgreSQL Database")

# Tabs
tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "📋 Manage Bookings", "📊 Reports & Export"])

with tab1:
    if not df_filtered.empty:
        col1, col2, col3, col4 = st.columns(4)
        
        total_bookings = len(df_filtered)
        pending_count = len(df_filtered[df_filtered['status'] == 'Pending'])
        confirmed_count = len(df_filtered[df_filtered['status'] == 'Confirmed'])
        total_revenue = df_filtered[df_filtered['status'] == 'Confirmed']['total'].sum()
        pending_revenue = df_filtered[df_filtered['status'] == 'Pending']['total'].sum()
        
        with col1:
            st.metric("Total Bookings", f"{total_bookings:,}")
        with col2:
            st.metric("Pending", f"{pending_count:,}")
        with col3:
            st.metric("Confirmed", f"{confirmed_count:,}")
        with col4:
            st.metric("Revenue", f"€{total_revenue:,.0f}", f"€{pending_revenue:,.0f} pending")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 📊 Status Distribution")
            status_counts = df_filtered['status'].value_counts()
            fig = go.Figure(data=[go.Pie(labels=status_counts.index, values=status_counts.values, hole=0.5)])
            fig.update_layout(
                height=350, 
                paper_bgcolor='rgba(0,0,0,0)', 
                font=dict(color='#f9fafb'),
                showlegend=True
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.markdown("#### 📈 Booking Timeline")
            timeline = df_filtered.groupby(df_filtered['timestamp'].dt.date).size().reset_index()
            timeline.columns = ['Date', 'Count']
            fig = go.Figure(data=[go.Scatter(
                x=timeline['Date'], 
                y=timeline['Count'], 
                mode='lines+markers', 
                line=dict(color=PRIMARY_COLOR, width=3),
                marker=dict(size=8)
            )])
            fig.update_layout(
                height=350, 
                paper_bgcolor='rgba(0,0,0,0)', 
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#f9fafb'),
                xaxis=dict(gridcolor='#334155'),
                yaxis=dict(gridcolor='#334155')
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("📭 No bookings match current filters")

with tab2:
    st.markdown("### 📋 Booking Management")
    
    if not df_filtered.empty:
        pending_bookings = df_filtered[df_filtered['status'] == 'Pending']
        
        if len(pending_bookings) > 0:
            st.markdown(f"#### ⏳ {len(pending_bookings)} Pending Bookings")
            
            for idx, booking in pending_bookings.iterrows():
                booking_id = booking.get('booking_id', booking.get('id', f"{booking['timestamp']}_{booking['guest_email']}"))
                tee_time_display = booking.get('tee_time', 'Not specified')
                
                with st.expander(f"📧 {booking['guest_email']} • 🗓️ {booking['date'].strftime('%Y-%m-%d')} {tee_time_display} • 👥 {booking['players']} players • 💰 €{booking['total']:,.2f}"):
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.markdown(f"""
                        **📧 Guest Email:** {booking['guest_email']}  
                        **📅 Date:** {booking['date'].strftime('%Y-%m-%d')}  
                        **🕐 Tee Time:** {tee_time_display}  
                        **👥 Players:** {booking['players']}  
                        **💰 Total:** €{booking['total']:,.2f}  
                        **🔖 Booking Ref:** `{booking_id}`  
                        **📝 Current Note:** {booking.get('note', 'N/A')}
                        """)
                        
                        # Notes section
                        st.markdown("---")
                        st.markdown("#### 📝 Notes")
                        
                        # Display existing notes
                        existing_notes = get_booking_notes(booking_id)
                        if existing_notes:
                            for note in existing_notes:
                                note_time = note['created_at'].strftime('%Y-%m-%d %H:%M') if note['created_at'] else 'Unknown'
                                note_type = note.get('note_type', 'general')
                                
                                # Determine badge color based on note type
                                badge_colors = {
                                    'general': '#818cf8',
                                    'follow_up': '#fbbf24',
                                    'customer_request': '#10b981',
                                    'internal': '#94a3b8'
                                }
                                badge_color = badge_colors.get(note_type, '#94a3b8')
                                
                                st.markdown(f"""
                                <div style="background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 1rem; margin: 0.75rem 0; transition: all 0.2s;">
                                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                                        <div>
                                            <span style="color: #94a3b8; font-size: 0.8rem; font-weight: 500;">👤 {note['created_by']}</span>
                                            <span style="background: rgba({int(badge_color[1:3], 16)}, {int(badge_color[3:5], 16)}, {int(badge_color[5:7], 16)}, 0.2); color: {badge_color}; padding: 0.2rem 0.6rem; border-radius: 12px; font-size: 0.7rem; font-weight: 600; margin-left: 0.5rem;">{note_type}</span>
                                        </div>
                                        <span style="color: #94a3b8; font-size: 0.75rem;">🕐 {note_time}</span>
                                    </div>
                                    <div style="color: #f9fafb; font-size: 0.9rem; line-height: 1.5;">{note['note']}</div>
                                </div>
                                """, unsafe_allow_html=True)
                        else:
                            st.markdown("""
                            <div style="color: #94a3b8; font-style: italic; padding: 1rem; text-align: center; background: #1e293b; border-radius: 8px; border: 1px dashed #334155;">
                                No notes yet
                            </div>
                            """, unsafe_allow_html=True)
                        
                        # Add new note
                        st.markdown("""
                        <div style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid #334155;">
                            <p style="color: #94a3b8; font-size: 0.875rem; font-weight: 600; margin-bottom: 1rem;">➕ Add New Note</p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        with st.form(f"add_note_{booking_id}"):
                            new_note = st.text_area("Note", placeholder="Enter internal note about this booking...", key=f"note_{booking_id}", height=80, label_visibility="collapsed")
                            note_type = st.selectbox("Type", ["general", "follow_up", "customer_request", "internal"], key=f"note_type_{booking_id}")
                            
                            if st.form_submit_button("💾 Add Note", use_container_width=True):
                                if new_note:
                                    if add_booking_note(booking_id, new_note, st.session_state.username, note_type):
                                        st.success("✅ Note added!")
                                        st.cache_data.clear()
                                        st.rerun()
                                else:
                                    st.error("❌ Please enter a note")
                    
                    with col2:
                        action = st.radio("Action", ["No Change", "✅ Confirm", "❌ Reject"], key=f"pending_action_{idx}")
                        send_email = st.checkbox("Send Email", value=True, key=f"pending_email_{idx}")
                        
                        # Delete button with confirmation
                        st.markdown("---")
                        delete_confirm = st.checkbox(f"⚠️ Enable Delete", key=f"enable_delete_{idx}")
                        
                        if delete_confirm:
                            if st.button("🗑️ Delete Permanently", key=f"delete_{idx}", type="secondary"):
                                with st.spinner("Deleting booking..."):
                                    if delete_booking(booking_id):
                                        st.success("✅ Booking deleted!")
                                        st.cache_data.clear()
                                        st.rerun()
                                    else:
                                        st.error("❌ Failed to delete booking")
                        
                        st.markdown("---")
                        
                        if st.button("💾 Update Status", key=f"pending_update_{idx}", use_container_width=True):
                            if action == "✅ Confirm":
                                with st.spinner(f"⏳ Confirming booking for {booking['guest_email']}..."):
                                    if update_booking_status(booking_id, 'Confirmed', updated_by=st.session_state.username):
                                        # Add automatic note
                                        add_booking_note(booking_id, f"Booking confirmed via dashboard", st.session_state.username, 'general')
                                        
                                        if send_email:
                                            with st.spinner("📧 Sending confirmation email..."):
                                                booking_data = {
                                                    'guest_email': booking['guest_email'],
                                                    'date': booking['date'].strftime('%Y-%m-%d'),
                                                    'players': booking['players'],
                                                    'total': booking['total']
                                                }
                                                send_confirmation_email(booking_data, 'Confirmed')
                                        
                                        st.success("✅ Booking confirmed!")
                                        st.cache_data.clear()
                                        st.rerun()
                                    
                            elif action == "❌ Reject":
                                with st.spinner(f"⏳ Rejecting booking for {booking['guest_email']}..."):
                                    if update_booking_status(booking_id, 'Rejected', updated_by=st.session_state.username):
                                        # Add automatic note
                                        add_booking_note(booking_id, f"Booking rejected via dashboard", st.session_state.username, 'general')
                                        
                                        if send_email:
                                            with st.spinner("📧 Sending rejection email..."):
                                                booking_data = {
                                                    'guest_email': booking['guest_email'],
                                                    'date': booking['date'].strftime('%Y-%m-%d'),
                                                    'players': booking['players'],
                                                    'total': booking['total']
                                                }
                                                send_confirmation_email(booking_data, 'Rejected')
                                        
                                        st.success("❌ Booking rejected")
                                        st.cache_data.clear()
                                        st.rerun()
        
        st.markdown("---")
        st.markdown(f"#### ✏️ All Bookings ({len(df_filtered)} records)")
        
        search_term = st.text_input("🔍 Search bookings", placeholder="Search by email, date, booking ref, note content, or staff name...", key="search_all")
        
        df_searchable = df_filtered.copy()
        if search_term:
            # Search in main booking fields
            mask = df_searchable.astype(str).apply(lambda x: x.str.contains(search_term, case=False, na=False)).any(axis=1)
            
            # Also search in notes if booking_notes table exists
            matching_booking_ids = []
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT DISTINCT booking_id 
                    FROM booking_notes 
                    WHERE note ILIKE %s OR created_by ILIKE %s
                """, (f'%{search_term}%', f'%{search_term}%'))
                results = cursor.fetchall()
                matching_booking_ids = [row[0] for row in results]
                cursor.close()
                conn.close()
            except:
                pass  # Table might not exist yet
            
            # Combine results
            if matching_booking_ids:
                notes_mask = df_searchable['booking_id'].isin(matching_booking_ids)
                mask = mask | notes_mask
            
            df_searchable = df_searchable[mask]
        
        st.markdown(f"**{len(df_searchable)} bookings shown**")
        
        # Create display dataframe with booking ref and tee time
        display_df = df_searchable[['booking_id', 'timestamp', 'guest_email', 'date', 'tee_time', 'players', 'total', 'status']].copy()
        display_df.columns = ['Booking Ref', 'Timestamp', 'Guest Email', 'Date', 'Tee Time', 'Players', 'Total (€)', 'Status']
        display_df['Timestamp'] = display_df['Timestamp'].dt.strftime('%Y-%m-%d %H:%M')
        display_df['Date'] = display_df['Date'].dt.strftime('%Y-%m-%d')
        display_df['Tee Time'] = display_df['Tee Time'].fillna('Not specified')
        
        st.dataframe(display_df, use_container_width=True)
        
        # Show confirmed bookings with details and notes
        confirmed_bookings = df_searchable[df_searchable['status'] == 'Confirmed']
        if len(confirmed_bookings) > 0:
            st.markdown("---")
            st.markdown(f"#### ✅ Confirmed Bookings ({len(confirmed_bookings)} bookings)")
            
            for idx, booking in confirmed_bookings.iterrows():
                booking_id = booking.get('booking_id', booking.get('id', 'N/A'))
                tee_time_display = booking.get('tee_time', 'Not specified')
                
                # Handle confirmed_at for both datetime objects and strings
                confirmed_at = booking.get('customer_confirmed_at')
                if pd.notnull(confirmed_at) and confirmed_at != '':
                    try:
                        # Convert to datetime if it's a string
                        if isinstance(confirmed_at, str):
                            confirmed_at_dt = pd.to_datetime(confirmed_at)
                            confirmed_at_str = confirmed_at_dt.strftime('%Y-%m-%d %H:%M')
                        # Use directly if it's already a datetime object
                        elif hasattr(confirmed_at, 'strftime'):
                            confirmed_at_str = confirmed_at.strftime('%Y-%m-%d %H:%M')
                        else:
                            confirmed_at_str = str(confirmed_at)
                    except:
                        # Fallback if parsing fails
                        confirmed_at_str = str(confirmed_at) if confirmed_at else 'Via dashboard'
                else:
                    confirmed_at_str = 'Via dashboard'
                
                with st.expander(f"✅ {booking['guest_email']} • {booking['date'].strftime('%Y-%m-%d')} {tee_time_display} • {booking['players']} players"):
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.markdown(f"""
                        **📧 Customer Email:** {booking['guest_email']}  
                        **🔖 Booking Reference:** `{booking_id}`  
                        **📅 Date:** {booking['date'].strftime('%Y-%m-%d')}  
                        **🕐 Tee Time:** {tee_time_display}  
                        **👥 Players:** {booking['players']}  
                        **💰 Total:** €{booking['total']:,.2f}  
                        **✅ Confirmed At:** {confirmed_at_str}  
                        **📝 Note:** {booking.get('note', 'N/A')}
                        """)
                        
                        # Notes section for confirmed bookings
                        st.markdown("---")
                        st.markdown("#### 📝 Booking Notes")
                        
                        # Display existing notes
                        existing_notes = get_booking_notes(booking_id)
                        if existing_notes:
                            for note in existing_notes:
                                note_time = note['created_at'].strftime('%Y-%m-%d %H:%M') if note['created_at'] else 'Unknown'
                                note_type = note.get('note_type', 'general')
                                
                                # Determine badge color based on note type
                                badge_colors = {
                                    'general': '#818cf8',
                                    'follow_up': '#fbbf24',
                                    'customer_request': '#10b981',
                                    'internal': '#94a3b8'
                                }
                                badge_color = badge_colors.get(note_type, '#94a3b8')
                                
                                st.markdown(f"""
                                <div style="background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 1rem; margin: 0.75rem 0; transition: all 0.2s;">
                                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                                        <div>
                                            <span style="color: #94a3b8; font-size: 0.8rem; font-weight: 500;">👤 {note['created_by']}</span>
                                            <span style="background: rgba({int(badge_color[1:3], 16)}, {int(badge_color[3:5], 16)}, {int(badge_color[5:7], 16)}, 0.2); color: {badge_color}; padding: 0.2rem 0.6rem; border-radius: 12px; font-size: 0.7rem; font-weight: 600; margin-left: 0.5rem;">{note_type}</span>
                                        </div>
                                        <span style="color: #94a3b8; font-size: 0.75rem;">🕐 {note_time}</span>
                                    </div>
                                    <div style="color: #f9fafb; font-size: 0.9rem; line-height: 1.5;">{note['note']}</div>
                                </div>
                                """, unsafe_allow_html=True)
                        else:
                            st.markdown("""
                            <div style="color: #94a3b8; font-style: italic; padding: 1rem; text-align: center; background: #1e293b; border-radius: 8px; border: 1px dashed #334155;">
                                No notes for this booking
                            </div>
                            """, unsafe_allow_html=True)
                        
                        # Add new note to confirmed booking
                        st.markdown("""
                        <div style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid #334155;">
                            <p style="color: #94a3b8; font-size: 0.875rem; font-weight: 600; margin-bottom: 1rem;">➕ Add Follow-up Note</p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        with st.form(f"add_note_confirmed_{booking_id}"):
                            new_note = st.text_area("Note", placeholder="Add follow-up note or customer communications...", key=f"note_confirmed_{booking_id}", height=60, label_visibility="collapsed")
                            
                            if st.form_submit_button("💾 Add Note", use_container_width=True):
                                if new_note:
                                    if add_booking_note(booking_id, new_note, st.session_state.username):
                                        st.success("✅ Note added!")
                                        st.cache_data.clear()
                                        st.rerun()
                                else:
                                    st.error("❌ Please enter a note")
                    
                    with col2:
                        st.success("✅ Confirmed")
                        
                        # Show who updated it
                        updated_by = booking.get('updated_by', 'Unknown')
                        updated_at = booking.get('updated_at')
                        
                        if updated_by and updated_by != 'Unknown':
                            st.info(f"👤 Updated by: **{updated_by}**")
                        
                        if updated_at:
                            try:
                                if isinstance(updated_at, str):
                                    updated_dt = pd.to_datetime(updated_at)
                                    st.caption(f"🕐 {updated_dt.strftime('%Y-%m-%d %H:%M')}")
                                elif hasattr(updated_at, 'strftime'):
                                    st.caption(f"🕐 {updated_at.strftime('%Y-%m-%d %H:%M')}")
                            except:
                                pass
    else:
        st.info("No bookings match current filters")

with tab3:
    st.markdown("### 📊 Reports & Export")
    
    if not df_filtered.empty:
        col1, col2, col3, col4 = st.columns(4)
        
        total_bookings = len(df_filtered)
        confirmed_revenue = df_filtered[df_filtered['status'] == 'Confirmed']['total'].sum()
        pending_revenue = df_filtered[df_filtered['status'] == 'Pending']['total'].sum()
        avg_booking_value = df_filtered['total'].mean()
        
        with col1:
            st.metric("Total Bookings", f"{total_bookings:,}")
        with col2:
            st.metric("Confirmed Revenue", f"€{confirmed_revenue:,.2f}")
        with col3:
            st.metric("Pending Revenue", f"€{pending_revenue:,.2f}")
        with col4:
            st.metric("Avg Booking Value", f"€{avg_booking_value:,.2f}")
        
        st.markdown("---")
        st.markdown("#### 📥 Export Options")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**📊 Excel Report**")
            st.markdown("Multi-sheet report with summary and analytics")
            excel_data = generate_excel_report(df_filtered, f"{CLUB_NAME.replace(' ', '_')}_Report")
            st.download_button(
                label="📊 Download Excel",
                data=excel_data,
                file_name=f"{CLUB_NAME.replace(' ', '_')}_Bookings_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        
        with col2:
            st.markdown("**📄 CSV Export**")
            st.markdown("Simple CSV for importing elsewhere")
            csv_data = generate_csv_report(df_filtered)
            st.download_button(
                label="📄 Download CSV",
                data=csv_data,
                file_name=f"{CLUB_NAME.replace(' ', '_')}_Bookings_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        st.markdown("---")
        st.markdown("#### 📈 Revenue Timeline")
        
        revenue_timeline = df_filtered[df_filtered['status'] == 'Confirmed'].groupby(df_filtered['date'].dt.date)['total'].sum().reset_index()
        revenue_timeline.columns = ['Date', 'Revenue']
        
        fig_revenue = go.Figure(data=[go.Bar(
            x=revenue_timeline['Date'],
            y=revenue_timeline['Revenue'],
            marker_color=PRIMARY_COLOR,
            text=[f"€{x:,.0f}" for x in revenue_timeline['Revenue']],
            textposition='auto'
        )])
        fig_revenue.update_layout(
            height=300,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#f9fafb'),
            xaxis=dict(gridcolor='#334155'),
            yaxis=dict(gridcolor='#334155', title='Revenue (€)')
        )
        st.plotly_chart(fig_revenue, use_container_width=True)
    else:
        st.info("📭 No bookings available for reporting")
