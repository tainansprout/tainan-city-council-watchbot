#!/usr/bin/env python3
"""
Main application entry point.
- Provides the 'application' object for WSGI servers (Gunicorn).
- Can be run directly to start a local development server.
"""
import os
import atexit
from src.app import MultiPlatformChatBot
from src.core.logger import logger
from src.core.config import load_config

def create_app():
    """Creates and configures the Flask application."""
    try:
        bot = MultiPlatformChatBot()
        logger.info("Flask application created successfully via factory.")
        return bot.get_flask_app()
    except Exception as e:
        logger.error(f"FATAL: Failed to create application in factory: {e}", exc_info=True)
        # If app creation fails, we must raise the exception to prevent
        # Gunicorn from starting with a broken application.
        raise

# --- WSGI Application Instance ---
# Gunicorn looks for this 'application' variable.
# It's created once when the module is imported for production.
application = create_app()

# --- Development Server ---
if __name__ == "__main__":
    # This block runs only when the script is executed directly
    # (e.g., `python main.py`) for local testing.
    print("🔧 Starting in development mode...")
    
    # Load config to get host/port for the dev server
    config = load_config()
    app_config = config.get('app', {})
    
    application.run(
        host=os.getenv('HOST', app_config.get('host', '0.0.0.0')),
        port=int(os.getenv('PORT', app_config.get('port', 8080))),
        debug=True,  # Debug mode is useful for development
        use_reloader=True # Automatically reload on code changes
    )

# --- Cleanup Hook ---
def cleanup():
    """A hook to run on application shutdown.""""""A hook to run on application shutdown."""
    logger.info("Application is shutting down.")
    # Future cleanup logic can go here.
    logger.info("Cleanup complete.")

atexit.register(cleanup)
