import secrets
import hmac
import uuid
import hashlib
from datetime import datetime, timedelta

"""
не используем 
"""


secret_key = b"scrt"



def generate_session_pair(phone : str, ttl : int) -> dict:

    """
    Генерация данных для сохранения сесии 
    Args:
        phone : номер телефона
        ttl : время жизни сессии
    Returns:
        session : обьект сессии 
    """

    session_id = str(uuid.uuid4())
    code = _generate_verification_code()
    hash_code = _hash_code(code)
    sign = _sign_session(session_id, phone, hash_code)
    exp = datetime.now() + timedelta(minutes=ttl)
    session = {
        "id" : session_id,
        "phone" : phone,
        "sign" : sign,
        "hash_code" : hash_code,
        "exp" : exp
    }
    response = {
        "id" : session_id,
        "phone" : phone,
        "code" : code
    }
    return session, response


def verify_session(input_session_data : dict, original_session_data : dict) -> bool:

    """
    Вереикация сессии 
    Args:
        input_session_data : Данные о сесси из запроса 
        original_session_data : Оригинальные данные о сессии с хранилища
    Returns:
        True : если сессия валидна 
    """

    try:
        current_time = datetime.now()
        if original_session_data["exp"] <= current_time:
            return False
        input_session_data["hash_code"] = _hash_code(input_session_data.get("code"))
        if not _verefy_sign(input_session_data, original_session_data["sign"]):
            return False 
        is_code_valid = hmac.compare_digest(input_session_data["hash_code"], original_session_data.get('hash_code'))
        if not is_code_valid:
            return False
        return True
    except ValueError:
        return False


def _generate_verification_code(length : int = 4) -> str:

    """
    Генерация сырого кода верефикации 
    Args:
        length : длинна кода опционально
    Returns:
        code : сырой код 
    """

    digits = [str(secrets.randbelow(10)) for _ in range(length)]
    if digits[0] == '0':
        digits[0] = str(secrets.randbelow(9) + 1)  # 1-9
    code = ''.join(digits)
    return code


def _hash_code(code : str, secret_key : str = secret_key) -> str: 

    """
    Хеширование сырого  кода 
    Args:
        secret_key : ключ для хеширования 
        code : Код для проверки
    Returns:
        hash_code : Хешированный код
    """

    hash_code = hmac.new(secret_key, code.encode(), hashlib.sha256)
    return hash_code.hexdigest()


def _sign_session(session_id : str, phone : str, hash_code : str, secret_key : str = secret_key) -> str:

    """
    Подпись сесии 
    Args:
        session_id : id сесии
        phone : номер телефона
        hash_code : хешированный код
        secret_key : секретный ключ
    Returns:
        sign : подпись
    """

    data_to_sign = f"{session_id}:{phone}:{hash_code}"
    sign = hmac.new(secret_key, data_to_sign.encode(), hashlib.sha256)
    return sign.hexdigest()


def _verefy_sign(session_data : dict, sign : str) -> bool: 

    """
    Проверяем валидность подписи 
    Args:
        session_data : данные о сесии
    Returns:
        True : если подпись валидна 
    """
    
    expected_signature = _sign_session(
        session_data['id'],
        session_data['phone'],
        session_data['hash_code']
        )
    is_valid = hmac.compare_digest(expected_signature, sign)
    return is_valid
    
r, u = generate_session_pair("79185447361", 10)
print(verify_session(u, r))
