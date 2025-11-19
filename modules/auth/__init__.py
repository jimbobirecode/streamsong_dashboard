"""Authentication module"""
from .authentication import (
    hash_password,
    verify_password,
    authenticate_user,
    set_permanent_password,
    update_last_login
)

__all__ = [
    'hash_password',
    'verify_password',
    'authenticate_user',
    'set_permanent_password',
    'update_last_login'
]
