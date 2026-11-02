from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, Session, sessionmaker

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

# Session factory - exported at module level for use by seed scripts and other modules
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_session() -> Session:
    """Get a new database session."""
    return SessionLocal()