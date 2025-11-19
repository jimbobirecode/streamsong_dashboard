"""User authentication functions"""
import bcrypt
import streamlit as st
from psycopg.rows import dict_row
from ..database.connection import get_db_connection


def hash_password(password: str) -> str:
    """
    Hash password using bcrypt

    Args:
        password (str): Plain text password

    Returns:
        str: Hashed password
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verify password against hash

    Args:
        password (str): Plain text password
        password_hash (str): Hashed password

    Returns:
        bool: True if password matches, False otherwise
    """
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))


def authenticate_user(username: str, password: str):
    """
    Authenticate user - handles both temp passwords and set passwords

    Args:
        username (str): Username
        password (str): Password

    Returns:
        tuple: (success, customer_id, full_name, must_change_password, user_id)
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
    """
    Set permanent password and clear temp password

    Args:
        user_id (int): User ID
        new_password (str): New password

    Returns:
        bool: True if successful, False otherwise
    """
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
    """
    Update last login timestamp

    Args:
        user_id (int): User ID
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE dashboard_users SET last_login = NOW() WHERE id = %s;", (user_id,))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        st.error(f"Error updating last login: {e}")
