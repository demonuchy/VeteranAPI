import hmac
import hashlib

secret_key = b"ewevewrvwervwerverveverv"


def hash_password(password : str) -> str:
    """
    Args:
        password : 
    Returns 
        hashed_password : 
    """
    hash_code = hmac.new(secret_key, password.encode(), hashlib.sha256)
    return hash_code.hexdigest()


def is_password_valid(password : str, current_hash_password : str) -> bool:
    """
    Args:
        password :
        current_hash_password : 
    Returns 
        is_valid : 
    """
    hashed_password = hash_password(password)
    is_valid = hmac.compare_digest(hashed_password, current_hash_password)
    return is_valid