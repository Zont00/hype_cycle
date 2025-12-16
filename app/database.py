from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

from .config import settings

# Create data directory if it doesn't exist
os.makedirs("data", exist_ok=True)

# Create SQLAlchemy engine
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False}  # Needed for SQLite
)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for models
Base = declarative_base()


# Dependency for FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
