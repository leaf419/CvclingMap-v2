"""FastAPI应用入口"""
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from gateway.core.config import settings
from gateway.api.routes import router
from gateway.db.models import create_database_engine, get_db_session

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Creating database engine...")
    engine = create_database_engine(testing=settings.testing)
    app.state.db_engine = engine
    app.state.db_session = get_db_session(engine)
    logger.info("Database ready")
    yield
    logger.info("Closing database...")
    app.state.db_session.close()
    app.state.db_engine.dispose()
    logger.info("Database closed")


def create_app(testing: bool = False) -> FastAPI:
    if testing:
        settings.testing = True

    app = FastAPI(title=settings.app_name, version=settings.version, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    # 挂载 output/ 静态目录，供前端加载 GeoJSON 数据
    output_dir = Path(settings.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/data", StaticFiles(directory=str(output_dir)), name="data")

    @app.get("/")
    async def root():
        return {
            "name": settings.app_name,
            "version": settings.version,
            "docs": "/docs",
            "health": "/api/health",
        }

    logger.info(f"App created: {settings.app_name} v{settings.version}")
    return app


app = create_app()
