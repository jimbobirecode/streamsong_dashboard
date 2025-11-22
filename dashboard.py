import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO
import html

# Import modular components
from modules.auth import (
    authenticate_user,
    set_permanent_password,
    update_last_login
)
from modules.database import (
    load_bookings_from_db,
    update_booking_status,
    update_booking_note,
    delete_booking,
    update_booking_tee_time,
    fix_all_tee_times
)
from modules.ui import get_dashboard_css
from modules.utils import (
    extract_tee_time_from_note,
    get_status_icon,
    get_status_color,
    generate_status_progress_bar
)


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
st.markdown(get_dashboard_css(), unsafe_allow_html=True)


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
    # Header with refresh button
    header_col1, header_col2 = st.columns([4, 1])
    with header_col1:
        st.markdown("""
            <h2 style='margin-bottom: 0.5rem;'>Booking Requests</h2>
            <p style='color: #d4b896; margin-bottom: 1rem; font-size: 0.9375rem;'>Manage and track all incoming tee time requests</p>
        """, unsafe_allow_html=True)
    with header_col2:
        if st.button("🔄 Refresh", key="refresh_bookings", use_container_width=True, help="Refresh booking data"):
            st.cache_data.clear()
            st.rerun()

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
    
            # Hotel requirement badge and details
            hotel_required = booking.get('hotel_required', False)
            hotel_badge = ""
            hotel_details_html = ""

            if hotel_required:
                hotel_badge = "<div style='display: inline-block; background: #cc8855; color: #ffffff; padding: 0.4rem 0.8rem; border-radius: 6px; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; margin-left: 0.5rem;'>Hotel Required</div>"

                # Format hotel dates
                hotel_checkin = booking.get('hotel_checkin')
                hotel_checkout = booking.get('hotel_checkout')
                lodging_nights = booking.get('lodging_nights')
                lodging_rooms = booking.get('lodging_rooms')
                lodging_room_type = booking.get('lodging_room_type')
                lodging_preferences = booking.get('lodging_preferences')
                lodging_cost = booking.get('lodging_cost')

                if hotel_checkin and not pd.isna(hotel_checkin):
                    checkin_str = hotel_checkin.strftime('%b %d, %Y')
                else:
                    checkin_str = "Not Set"

                if hotel_checkout and not pd.isna(hotel_checkout):
                    checkout_str = hotel_checkout.strftime('%b %d, %Y')
                else:
                    checkout_str = "Not Set"

                # Build lodging details grid
                details_rows = ""

                # Dates row
                details_rows += f"""
                <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 0.75rem;'>
                    <div>
                        <div style='color: rgba(255,255,255,0.8); font-size: 0.7rem; font-weight: 600; text-transform: uppercase; margin-bottom: 0.25rem;'>Check-In</div>
                        <div style='color: #ffffff; font-size: 0.95rem; font-weight: 700;'>{checkin_str}</div>
                    </div>
                    <div>
                        <div style='color: rgba(255,255,255,0.8); font-size: 0.7rem; font-weight: 600; text-transform: uppercase; margin-bottom: 0.25rem;'>Check-Out</div>
                        <div style='color: #ffffff; font-size: 0.95rem; font-weight: 700;'>{checkout_str}</div>
                    </div>
                </div>
                """

                # Nights and rooms row
                if lodging_nights or lodging_rooms:
                    details_rows += """<div style='display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 0.75rem;'>"""

                    if lodging_nights and not pd.isna(lodging_nights):
                        details_rows += f"""
                        <div>
                            <div style='color: rgba(255,255,255,0.8); font-size: 0.7rem; font-weight: 600; text-transform: uppercase; margin-bottom: 0.25rem;'>Nights</div>
                            <div style='color: #ffffff; font-size: 0.95rem; font-weight: 700;'>{int(lodging_nights)}</div>
                        </div>
                        """

                    if lodging_rooms and not pd.isna(lodging_rooms):
                        details_rows += f"""
                        <div>
                            <div style='color: rgba(255,255,255,0.8); font-size: 0.7rem; font-weight: 600; text-transform: uppercase; margin-bottom: 0.25rem;'>Rooms</div>
                            <div style='color: #ffffff; font-size: 0.95rem; font-weight: 700;'>{int(lodging_rooms)}</div>
                        </div>
                        """

                    details_rows += "</div>"

                # Room type
                if lodging_room_type and not pd.isna(lodging_room_type) and str(lodging_room_type).strip():
                    room_type_display = str(lodging_room_type).replace('_', ' ').title()
                    details_rows += f"""
                    <div style='margin-bottom: 0.75rem;'>
                        <div style='color: rgba(255,255,255,0.8); font-size: 0.7rem; font-weight: 600; text-transform: uppercase; margin-bottom: 0.25rem;'>Room Type</div>
                        <div style='color: #ffffff; font-size: 0.95rem; font-weight: 700;'>{html.escape(room_type_display)}</div>
                    </div>
                    """

                # Lodging cost
                if lodging_cost and not pd.isna(lodging_cost) and float(lodging_cost) > 0:
                    details_rows += f"""
                    <div style='margin-bottom: 0.75rem; padding-top: 0.75rem; border-top: 1px solid rgba(255,255,255,0.3);'>
                        <div style='color: rgba(255,255,255,0.8); font-size: 0.7rem; font-weight: 600; text-transform: uppercase; margin-bottom: 0.25rem;'>Estimated Lodging Cost</div>
                        <div style='color: #ffffff; font-size: 1.25rem; font-weight: 700;'>${float(lodging_cost):,.2f}</div>
                    </div>
                    """

                # Special preferences
                if lodging_preferences and not pd.isna(lodging_preferences) and str(lodging_preferences).strip():
                    prefs_list = str(lodging_preferences).split(';')
                    prefs_html = "<br>".join([f"• {html.escape(pref.strip())}" for pref in prefs_list if pref.strip()])
                    details_rows += f"""
                    <div style='padding-top: 0.75rem; border-top: 1px solid rgba(255,255,255,0.3);'>
                        <div style='color: rgba(255,255,255,0.8); font-size: 0.7rem; font-weight: 600; text-transform: uppercase; margin-bottom: 0.5rem;'>Special Requests</div>
                        <div style='color: rgba(255,255,255,0.9); font-size: 0.875rem; line-height: 1.6;'>{prefs_html}</div>
                    </div>
                    """

                hotel_details_html = f"""
                <div style='background: #cc8855; padding: 1rem; border-radius: 8px; margin-top: 1rem;'>
                    <div style='color: #ffffff; font-weight: 700; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 0.75rem;'>
                        🏨 Hotel Accommodation
                    </div>
                    {details_rows}
                </div>
                """

            # Golf courses and tee times section
            golf_courses = booking.get('golf_courses', '')
            selected_tee_times = booking.get('selected_tee_times', '')
            golf_info_html = ""

            if golf_courses and not pd.isna(golf_courses) and str(golf_courses).strip():
                courses_list = str(golf_courses).strip()
                times_list = str(selected_tee_times).strip() if selected_tee_times and not pd.isna(selected_tee_times) else "Times not specified"

                golf_info_html = f"<div style='background: #6b7c3f; padding: 1rem; border-radius: 8px; margin-top: 1rem;'><div style='color: #ffffff; font-weight: 700; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 0.75rem;'>Golf Courses & Tee Times</div><div style='display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;'><div><div style='color: rgba(255,255,255,0.8); font-size: 0.7rem; font-weight: 600; text-transform: uppercase; margin-bottom: 0.25rem;'>Courses</div><div style='color: #ffffff; font-size: 0.875rem; font-weight: 600; line-height: 1.5;'>{html.escape(courses_list)}</div></div><div><div style='color: rgba(255,255,255,0.8); font-size: 0.7rem; font-weight: 600; text-transform: uppercase; margin-bottom: 0.25rem;'>Tee Times</div><div style='color: #ffffff; font-size: 0.875rem; font-weight: 600; line-height: 1.5;'>{html.escape(times_list)}</div></div></div></div>"

            # Escape and format note content for display
            note_display = html.escape(note_content).replace('\n', '<br>')

            # Build complete card HTML (without notes - notes will be in expander below)
            card_html = f"<div class='booking-card' style='background: linear-gradient(135deg, #3d5266 0%, #4a6278 100%); border: 2px solid #6b7c3f; border-radius: 12px; padding: 1.5rem; margin-bottom: 0.5rem; box-shadow: 0 4px 16px rgba(107, 124, 63, 0.3); transition: all 0.3s ease;'><div style='display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1.25rem;'><div style='flex: 1;'><div style='display: flex; align-items: center;'><div class='booking-id' style='margin-bottom: 0.5rem;'>{html.escape(str(booking['booking_id']))}</div>{hotel_badge}</div><div class='booking-email'>{html.escape(str(booking['guest_email']))}</div></div><div style='text-align: right;'><div class='timestamp'>REQUESTED</div><div class='timestamp-value'>{requested_time}</div></div></div><div style='margin-bottom: 1.5rem;'>{progress_html}</div><div style='height: 1px; background: linear-gradient(90deg, transparent, #6b7c3f, transparent); margin: 1.5rem 0;'></div><div style='display: grid; grid-template-columns: repeat(4, 1fr); gap: 1.5rem; margin-bottom: 1rem;'><div><div class='data-label' style='margin-bottom: 0.5rem;'>TEE DATE</div><div style='font-size: 1rem; font-weight: 600; color: #f7f5f2;'>{booking['date'].strftime('%b %d, %Y')}</div></div><div><div class='data-label' style='margin-bottom: 0.5rem;'>TEE TIME</div><div style='font-size: 1rem; font-weight: 600; color: #f7f5f2;'>{tee_time_display}</div></div><div><div class='data-label' style='margin-bottom: 0.5rem;'>PLAYERS</div><div style='font-size: 1rem; font-weight: 600; color: #f7f5f2;'>{booking['players']}</div></div><div><div class='data-label' style='margin-bottom: 0.5rem;'>TOTAL</div><div style='font-size: 1.5rem; font-weight: 700; color: #6b7c3f;'>${booking['total']:,.2f}</div></div></div>{golf_info_html}{hotel_details_html}</div>"

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
