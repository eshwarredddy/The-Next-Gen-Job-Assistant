from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import config
from app.database.models import Base

connect_args = {"check_same_thread": False} if config.database_url.startswith("sqlite") else {}

engine = create_engine(
    config.database_url,
    connect_args=connect_args,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
