from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import DATABASE_URL
from sqlalchemy import create_engine

# --- Engine setup ---
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
    if DATABASE_URL.startswith("sqlite")
    else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency for getting a SQLAlchemy session."""
    from sqlalchemy.orm import Session
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- ensure models are registered before any table creation ---
import phishguard.models  # ✅ crucial: registers TargetDomain, ScanJob, Candidate

# --- create tables automatically when the app starts ---
Base.metadata.create_all(bind=engine)