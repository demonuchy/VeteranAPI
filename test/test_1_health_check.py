import pytest
import httpx

@pytest.fixture
async def client():
    async with httpx.AsyncClient() as client:
        yield client


@pytest.mark.anyio
async def test_health_auth(client):
    """Проверка здоровья приложения"""
    response = await client.get("http://127.0.0.1:8000/health")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_health_nginx(client):
    """Проверка здоровья приложения"""
    response = await client.get("http://127.0.0.1:8080/health")
    assert response.status_code == 200