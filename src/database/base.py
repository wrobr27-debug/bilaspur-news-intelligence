from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, Session

# Import settings
from src.config import settings

# Create engine based on DATABASE_URL
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=False,  # Set to True for SQL debugging
)

Base = declarative_base()


def get_session() -> Session:
    """Get a new database session."""
    from sqlalchemy.orm import sessionmaker
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()