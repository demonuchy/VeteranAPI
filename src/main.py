import uvicorn
import asyncio
from fastapi import FastAPI, status
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from starlette.middleware.sessions import SessionMiddleware

from api.auth import auth_route
from api.news import news_route
from api.user import user_route
from admin.setup import AdminSetup
from database.engine import engine
from shared.config import config
from utils.cleanup_token import TokenCleanupService


token_cleanup = TokenCleanupService(
    database_url=config.DatabaseUrl,
    interval_minutes=config.TOKEN_CEANUP_INTERVAL,  # Для теста 1 минута
    batch_size=config.TOKEN_CLEANUP_BATCH,
    name="TokenCleanup"
)

@asynccontextmanager
async def lifespan(app : FastAPI):
    """Жизненный цикл приложения"""
    token_cleanup.start()
    yield
    token_cleanup.stop()


app = FastAPI(lifespan=lifespan)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # или ["*"] для всех доменов (не рекомендуется для продакшена)
    allow_credentials=True,
    allow_methods=["*"],  # Разрешить все методы
    allow_headers=["*"],  # Разрешить все заголовки
    expose_headers=["X-User-Id", "X-User-Role", "X-Device-Id"]
)


app.add_middleware(
    SessionMiddleware,
    secret_key=config.ADMIN_SECRET_TOKEN,  
    session_cookie="sqladmin_session",  
    max_age=3600 * 24,  
    https_only=True,
    same_site="lax"
)


admin = AdminSetup(app, engine)


app.include_router(auth_route)
app.include_router(news_route)
app.include_router(user_route)

@app.get("/health")
async def health(request : Request):
    return JSONResponse(content={"detail" : "API health"}, status_code=status.HTTP_200_OK)


if __name__ == "__main__":
    uvicorn.run("main:app", port=8000, host="0.0.0.0", reload=True)
    
    
