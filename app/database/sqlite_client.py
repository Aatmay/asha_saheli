import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Resolve absolute path for local sqlite database file mapping
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, '..', 'asha_local.db')}"

# Explicit engine declaration
sqlite_engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sqlite_engine)

def get_local_db():
    """Dependency provider layer for local FastAPI requests lifecycle"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_postgres_db():
    """Fallback stub for PostgreSQL target isolation testing"""
    # For prototype testing, route warehouse logs directly to SQLite session
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()