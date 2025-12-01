"""Waitlist Module for managing tee time waitlist entries"""
import streamlit as st
import pandas as pd
from datetime import datetime
from psycopg.rows import dict_row
from modules.database import get_db_connection


def create_waitlist_table_if_not_exists():
    """Ensure waitlist table exists in database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS waitlist (
                id SERIAL PRIMARY KEY,
                waitlist_id VARCHAR(50) UNIQUE NOT NULL,
                guest_email VARCHAR(255) NOT NULL,
                guest_name VARCHAR(255),
                requested_date DATE NOT NULL,
                preferred_time VARCHAR(50),
                time_flexibility VARCHAR(50) DEFAULT 'Flexible',
                players INTEGER DEFAULT 1,
                golf_course VARCHAR(255),
                status VARCHAR(50) DEFAULT 'Waiting',
                priority INTEGER DEFAULT 5,
                notes TEXT,
                notification_sent BOOLEAN DEFAULT FALSE,
                notification_sent_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                club VARCHAR(100) NOT NULL
            );
        """)
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Error creating waitlist table: {e}")
        return False


def load_waitlist_from_db(club_filter):
    """Load waitlist entries from database"""
    try:
        create_waitlist_table_if_not_exists()
        conn = get_db_connection()
        cursor = conn.cursor(row_factory=dict_row)

        cursor.execute("""
            SELECT * FROM waitlist
            WHERE club = %s
            ORDER BY requested_date ASC, priority DESC, created_at ASC
        """, (club_filter,))

        waitlist = cursor.fetchall()
        cursor.close()
        conn.close()

        if not waitlist:
            return pd.DataFrame()

        df = pd.DataFrame(waitlist)

        for col in ['requested_date', 'created_at', 'updated_at', 'notification_sent_at']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')

        return df
    except Exception as e:
        st.error(f"Error loading waitlist: {e}")
        return pd.DataFrame()


def add_to_waitlist(guest_email, guest_name, requested_date, preferred_time,
                    time_flexibility, players, golf_course, notes, club, priority=5):
    """Add a new entry to the waitlist"""
    try:
        create_waitlist_table_if_not_exists()
        conn = get_db_connection()
        cursor = conn.cursor()

        waitlist_id = f"WL-{datetime.now().strftime('%Y%m%d%H%M%S')}-{hash(guest_email) % 10000:04d}"

        cursor.execute("""
            INSERT INTO waitlist (
                waitlist_id, guest_email, guest_name, requested_date, preferred_time,
                time_flexibility, players, golf_course, notes, club, priority
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (waitlist_id, guest_email, guest_name, requested_date, preferred_time,
              time_flexibility, players, golf_course, notes, club, priority))

        conn.commit()
        cursor.close()
        conn.close()
        return True, waitlist_id
    except Exception as e:
        st.error(f"Error adding to waitlist: {e}")
        return False, None


def update_waitlist_status(waitlist_id, new_status, send_notification=False):
    """Update waitlist entry status"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if send_notification:
            cursor.execute("""
                UPDATE waitlist
                SET status = %s, notification_sent = TRUE,
                    notification_sent_at = NOW(), updated_at = NOW()
                WHERE waitlist_id = %s
            """, (new_status, waitlist_id))
        else:
            cursor.execute("""
                UPDATE waitlist
                SET status = %s, updated_at = NOW()
                WHERE waitlist_id = %s
            """, (new_status, waitlist_id))

        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Error updating waitlist: {e}")
        return False


def delete_waitlist_entry(waitlist_id):
    """Delete a waitlist entry"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM waitlist WHERE waitlist_id = %s", (waitlist_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Error deleting waitlist entry: {e}")
        return False


def get_waitlist_matches(club_filter, available_date, available_time=None):
    """Find waitlist entries that match an available tee time"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(row_factory=dict_row)

        query = """
            SELECT * FROM waitlist
            WHERE club = %s
            AND requested_date = %s
            AND status = 'Waiting'
            ORDER BY priority DESC, created_at ASC
        """
        cursor.execute(query, (club_filter, available_date))

        matches = cursor.fetchall()
        cursor.close()
        conn.close()

        return pd.DataFrame(matches) if matches else pd.DataFrame()
    except Exception as e:
        st.error(f"Error finding waitlist matches: {e}")
        return pd.DataFrame()


def convert_waitlist_to_booking(waitlist_entry, tee_time, total_amount=0):
    """Convert a waitlist entry to a booking"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        booking_id = f"BOOK-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        cursor.execute("""
            INSERT INTO bookings (
                booking_id, guest_email, date, tee_time, players, total,
                status, note, club, timestamp, golf_courses
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s)
        """, (
            booking_id,
            waitlist_entry['guest_email'],
            waitlist_entry['requested_date'],
            tee_time,
            waitlist_entry['players'],
            total_amount,
            'Confirmed',
            f"Converted from waitlist: {waitlist_entry['waitlist_id']}. {waitlist_entry.get('notes', '')}",
            waitlist_entry['club'],
            waitlist_entry.get('golf_course', '')
        ))

        cursor.execute("""
            UPDATE waitlist
            SET status = 'Converted', updated_at = NOW()
            WHERE waitlist_id = %s
        """, (waitlist_entry['waitlist_id'],))

        conn.commit()
        cursor.close()
        conn.close()
        return True, booking_id
    except Exception as e:
        st.error(f"Error converting waitlist to booking: {e}")
        return False, None


__all__ = [
    'create_waitlist_table_if_not_exists',
    'load_waitlist_from_db',
    'add_to_waitlist',
    'update_waitlist_status',
    'delete_waitlist_entry',
    'get_waitlist_matches',
    'convert_waitlist_to_booking'
]
