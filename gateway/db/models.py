"""SQLAlchemy ORM模型 — SQLite缓存层"""
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Text,
    DateTime, Boolean, Index,
)
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from gateway.core.config import settings

Base = declarative_base()


class RouteCache(Base):
    """路线搜索缓存表"""
    __tablename__ = "route_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cache_key = Column(String(256), unique=True, nullable=False, index=True)
    source_lon = Column(Float, nullable=False)
    source_lat = Column(Float, nullable=False)
    target_lon = Column(Float, nullable=False)
    target_lat = Column(Float, nullable=False)
    user_template = Column(String(64), nullable=False)
    result_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    is_valid = Column(Boolean, default=True)
    num_pareto_routes = Column(Integer, default=0)
    pipeline_duration_sec = Column(Float, default=0.0)

    __table_args__ = (
        Index("idx_cache_key", "cache_key"),
        Index("idx_created_at", "created_at"),
    )


class RouteDetail(Base):
    """路线详情表"""
    __tablename__ = "route_detail"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cache_id = Column(Integer, nullable=False, index=True)
    route_id = Column(Integer, nullable=False)
    is_best = Column(Boolean, default=False)
    coordinates_json = Column(Text, nullable=False)

    # 指标
    total_length = Column(Float, default=0.0)
    total_cost = Column(Float, default=0.0)
    avg_safety = Column(Float, default=0.0)
    avg_comfort = Column(Float, default=0.0)
    avg_scenery = Column(Float, default=0.0)
    avg_traffic_stress = Column(Float, default=0.0)
    avg_beauty = Column(Float, default=0.0)
    avg_pref_score = Column(Float, default=0.0)
    num_segments = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (Index("idx_route_cache_id", "cache_id"),)


def create_database_engine(testing: bool = False):
    """创建数据库引擎"""
    db_url = "sqlite:///:memory:" if testing else settings.database_url
    engine = create_engine(db_url, connect_args={"check_same_thread": False}, echo=False)
    Base.metadata.create_all(engine)
    return engine


def get_db_session(engine) -> Session:
    """获取数据库Session"""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
