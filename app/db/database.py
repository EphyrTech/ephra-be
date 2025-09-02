import traceback

from sqlalchemy import create_engine, pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# Alembic-related imports and configuration - only used during migrations
try:
    from alembic import context
    target_metadata = None
    config = context.config if hasattr(context, 'config') else None
except (ImportError, AttributeError):
    # When not in Alembic context, these will be None
    context = None
    target_metadata = None
    config = None

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def do_run_migrations(connection) -> None:
    """Run migrations - only works when called from Alembic context"""
    if context is None or config is None:
        raise RuntimeError("This function can only be called from Alembic migration context")

    try:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()
    except Exception:
        print(traceback.format_exc())

async def run_async_migrations() -> None:
    """Run async migrations - only works when called from Alembic context"""
    if context is None or config is None:
        raise RuntimeError("This function can only be called from Alembic migration context")

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()
