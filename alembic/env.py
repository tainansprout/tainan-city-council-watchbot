"""
Alembic Environment Configuration for ChatGPT-Line-Bot
This file is the entry point for all Alembic operations.
"""
import os
import sys
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# --- Project-specific setup ---
# This is the most important part of the setup.
# We need to make sure Alembic can find our application's models.

# 1. Add the project's root directory to the Python path.
# This allows us to import modules from the `src` directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 2. Import the Base model from our application.
# All of our SQLAlchemy models inherit from this Base, so it holds the
# complete schema information (metadata).
from src.database.models import Base

# --- Alembic standard setup ---

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 3. Set the target metadata.
# This tells Alembic what the target database schema should look like.
# For autogenerate to work, this must be set to our application's Base.metadata.
target_metadata = Base.metadata

def get_database_url():
    """
    Dynamically get the database URL from the application's configuration.
    This is a best practice to ensure migrations run against the same
    database as the application.
    """
    # Try environment variable first (for production/CI)
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        return database_url
    
    # If not found, load from the application's config file (config.yml)
    try:
        from src.core.config import load_config
        app_config = load_config()
        db_config = app_config.get('db', {})
        
        host = db_config.get('host', 'localhost')
        port = db_config.get('port', 5432)
        database = db_config.get('db_name', 'chatbot')
        username = db_config.get('user', 'postgres')
        password = db_config.get('password', 'password')
        
        # Build the connection string
        url = f"postgresql://{username}:{password}@{host}:{port}/{database}"
        
        # Handle SSL parameters if they exist
        ssl_params = []
        if 'sslmode' in db_config:
            ssl_params.append(f"sslmode={db_config['sslmode']}")
        if 'sslrootcert' in db_config:
            ssl_params.append(f"sslrootcert={db_config['sslrootcert']}")
        if 'sslcert' in db_config:
            ssl_params.append(f"sslcert={db_config['sslcert']}")
        if 'sslkey' in db_config:
            ssl_params.append(f"sslkey={db_config['sslkey']}")
        
        if ssl_params:
            url += "?" + "&".join(ssl_params)
            
        return url
        
    except Exception as e:
        print(f"Warning: Could not load application config to get DB URL. Falling back to default. Error: {e}")
        return "postgresql://postgres:password@localhost:5432/chatbot"

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    # Get the database URL from our dynamic function
    database_url = get_database_url()
    
    # Create a configuration dictionary for the engine
    # and override the sqlalchemy.url from alembic.ini
    configuration = config.get_section(config.config_ini_section)
    configuration['sqlalchemy.url'] = database_url
    
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()

# --- Main execution logic ---
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
