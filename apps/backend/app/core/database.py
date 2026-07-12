"""
Database configuration and connection management.
Handles both direct database connections via SQLAlchemy and Supabase REST API clients.
"""

from typing import Optional, TYPE_CHECKING
from app.core.config import get_settings_lazy
from app.utils.logging import get_logger
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

logger = get_logger(__name__)
settings = get_settings_lazy()

# SQLAlchemy Setup
Base = declarative_base()

db_url = settings.DATABASE_URL
if not db_url:
    db_url = "sqlite:///./reachmagnets.db"

if db_url.startswith("sqlite"):
    from sqlalchemy import event
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()
else:
    engine = create_engine(db_url, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Dependency generator for database sessions"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_tables():
    """Create all registered database tables"""
    try:
        import app.models  # Ensure models are registered
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to create database tables: {str(e)}", exc_info=True)

# Optional import for Supabase - handles environments without supabase module installed
Client = None
try:
    from supabase import create_client, Client as SupabaseClient
    Client = SupabaseClient
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    logger.warning("Supabase module not available. Install with: pip install supabase")
    Client = type('Client', (), {})  # Create dummy type


def create_supabase_client() -> Optional['Client']:
    """Create and return Supabase client instance"""
    if not SUPABASE_AVAILABLE:
        logger.error("Supabase is not available. Cannot create client.")
        return None

    try:
        # Validate settings
        if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
            logger.error("SUPABASE_URL or SUPABASE_KEY not configured")
            return None

        # Create client
        supabase: Client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_KEY
        )

        logger.info("Supabase client created successfully")
        return supabase

    except Exception as e:
        logger.error(f"Failed to create Supabase client: {str(e)}", exc_info=True)
        return None


_supabase_client: Optional['Client'] = None

def get_supabase() -> Optional['Client']:
    """Get Supabase client (with lazy initialization)"""
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = create_supabase_client()
    return _supabase_client


async def test_connection() -> bool:
    """Test database connection"""
    try:
        from sqlalchemy import text
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            return True
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Database connection test failed: {str(e)}")
        return False


async def get_redis():
    """Get Redis client for caching and rate limiting"""
    try:
        import redis.asyncio as redis
        client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            max_connections=settings.DB_POOL_MAX_SIZE
        )
        return client
    except ImportError:
        logger.warning("Redis not available. Install with: pip install redis")
        raise
    except Exception as e:
        logger.error(f"Redis connection error: {str(e)}")
        raise


# Health check function for database
def check_database_health() -> dict:
    """Check database health status"""
    status = {
        "status": "unhealthy",
        "database_type": "SQLAlchemy"
    }

    try:
        from sqlalchemy import text
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            status["status"] = "healthy"
        finally:
            db.close()
    except Exception as e:
        status["error"] = str(e)

    return status
