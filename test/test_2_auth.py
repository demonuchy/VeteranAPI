import pytest
import httpx

@pytest.fixture
async def client():
    async with httpx.AsyncClient() as client:
        yield client


@pytest.fixture
async def user_data():
    return {
        "username": "demodayn@gmail.com",
        "password": "D2i0m0a5",
    }


@pytest.fixture
async def device_id():
    """Фикстура возвращает тестовый device_id"""
    return "test-device-123456"


@pytest.mark.anyio
async def test_register(client, user_data, device_id):
    """Тест регистрации с device_id"""
    headers = {"X-Device-Id": device_id}
    response = await client.post(
        "http://127.0.0.1:8080/api/v1/auth/register", 
        json=user_data,
        headers=headers
    )
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data["data"]
    assert "refresh_token" in data["data"]


@pytest.fixture
async def auth_tokens(client, user_data, device_id) -> dict[str, str]:
    """Фикстура возвращает токены авторизации"""
    headers = {"X-Device-Id": device_id}
    response = await client.post(
        "http://127.0.0.1:8080/api/v1/auth/login",
        json=user_data,
        headers=headers
    )
    assert response.status_code == 200
    
    data = response.json()
    return {
        "access_token": data["data"]["access_token"],
        "refresh_token": data["data"]["refresh_token"]
    }


@pytest.fixture
async def auth_headers_access(auth_tokens, device_id) -> dict[str, str]:
    """Фикстура возвращает заголовки авторизации с access токеном и device_id"""
    return {
        "Authorization": f"Bearer {auth_tokens['access_token']}",
        "X-Device-Id": device_id
    }


@pytest.fixture
async def auth_headers_refresh(auth_tokens, device_id) -> dict[str, str]:
    """Фикстура возвращает заголовки авторизации с refresh токеном и device_id"""
    return {
        "Authorization": f"Bearer {auth_tokens['refresh_token']}",
        "X-Device-Id": device_id
    }


@pytest.mark.anyio
async def test_login(client, user_data, device_id):
    """Тест логина с device_id"""
    headers = {"X-Device-Id": device_id}
    response = await client.post(
        "http://127.0.0.1:8080/api/v1/auth/login",
        json=user_data,
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data["data"]
    assert "refresh_token" in data["data"]


@pytest.mark.anyio
async def test_private_path(client, auth_headers_access):
    """Тест доступа к приватному маршруту с access токеном и device_id"""
    response = await client.get(
        "http://127.0.0.1:8080/api/v1/news/private",
        headers=auth_headers_access
    )
    assert response.status_code == 200


@pytest.mark.anyio
async def test_refresh(client, auth_headers_refresh, device_id):
    """Тест обновления токена с refresh токеном и device_id"""
    response = await client.post(
        "http://127.0.0.1:8080/api/v1/auth/refresh",
        headers=auth_headers_refresh
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data["data"]


@pytest.mark.anyio
async def test_verify_with_device_id(client, auth_headers_access):
    """Тест верификации токена с device_id"""
    response = await client.post(
        "http://127.0.0.1:8080/api/v1/auth/verify",
        headers=auth_headers_access
    )
    assert response.status_code == 200
    assert response.headers.get("X-User-Id") is not None
    assert response.headers.get("X-User_Role") is not None


@pytest.mark.anyio
async def test_register_without_device_id(client, user_data):
    """Тест регистрации без device_id (должен вернуть ошибку)"""
    response = await client.post(
        "http://127.0.0.1:8080/api/v1/auth/register", 
        json=user_data
        # Без headers, значит без X-Device-Id
    )
    assert response.status_code == 422  # Unprocessable Entity - ошибка валидации


@pytest.mark.anyio
async def test_login_without_device_id(client, user_data):
    """Тест логина без device_id (должен вернуть ошибку)"""
    response = await client.post(
        "http://127.0.0.1:8080/api/v1/auth/login",
        json=user_data
        # Без headers, значит без X-Device-Id
    )
    assert response.status_code == 422  # Unprocessable Entity - ошибка валидации


@pytest.mark.anyio
async def test_multiple_devices(client, user_data):
    """Тест работы с разными device_id"""
    device_1 = "device-iphone-123"
    device_2 = "device-android-456"
    
    # Логин с первого устройства
    headers_1 = {"X-Device-Id": device_1}
    response_1 = await client.post(
        "http://127.0.0.1:8080/api/v1/auth/login",
        json=user_data,
        headers=headers_1
    )
    assert response_1.status_code == 200
    token_1 = response_1.json()["data"]["access_token"]
    
    # Логин со второго устройства
    headers_2 = {"X-Device-Id": device_2}
    response_2 = await client.post(
        "http://127.0.0.1:8080/api/v1/auth/login",
        json=user_data,
        headers=headers_2
    )
    assert response_2.status_code == 200
    token_2 = response_2.json()["data"]["access_token"]
    
    # Оба токена должны быть валидны
    assert token_1 != token_2
    
    # Проверка доступа с первого устройства
    private_headers_1 = {
        "Authorization": f"Bearer {token_1}",
        "X-Device-Id": device_1
    }
    private_response_1 = await client.get(
        "http://127.0.0.1:8080/api/v1/news/private",
        headers=private_headers_1
    )
    assert private_response_1.status_code == 200
    
    # Проверка доступа со второго устройства
    private_headers_2 = {
        "Authorization": f"Bearer {token_2}",
        "X-Device-Id": device_2
    }
    private_response_2 = await client.get(
        "http://127.0.0.1:8080/api/v1/news/private",
        headers=private_headers_2
    )
    assert private_response_2.status_code == 200