#!/usr/bin/env python3
"""
Database Management Commands
Similar to npm run scripts for database operations
"""
import sys
import os
import subprocess
import argparse
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def run_command(command, description=None):
    """Execute a shell command with error handling"""
    if description:
        print(f"🔧 {description}")
    
    print(f"Running: {command}")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        print("✅ Success!\n")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {e}")
        if e.stderr:
            print(f"Error details: {e.stderr}")
        return False

def db_init():
    """Initialize database and run migrations"""
    print("🚀 Initializing database...\n")
    
    # Check if alembic is initialized
    alembic_dir = project_root / "alembic"
    if not alembic_dir.exists():
        print("❌ Alembic not found. Please run 'db:setup' first.")
        return False
    
    # Run initial migration
    return run_command("alembic upgrade head", "Running database migrations")

def db_setup():
    """Setup database for the first time"""
    print("🛠️ Setting up database for the first time...\n")
    
    # Install dependencies
    if not run_command("pip install -r requirements-orm.txt", "Installing ORM dependencies"):
        return False
    
    # Initialize Alembic (if not already done)
    alembic_dir = project_root / "alembic"
    if not (alembic_dir / "versions").exists():
        if not run_command("alembic init alembic", "Initializing Alembic"):
            return False
    
    # Create initial migration
    if not run_command("alembic revision --autogenerate -m 'Initial migration'", "Creating initial migration"):
        return False
    
    # Run migration
    return db_init()

def db_migrate(message="Auto migration"):
    """Create a new migration"""
    print(f"📝 Creating new migration: {message}\n")
    
    command = f"alembic revision --autogenerate -m '{message}'"
    return run_command(command, "Generating migration script")

def db_upgrade():
    """Upgrade database to latest version"""
    print("⬆️ Upgrading database to latest version...\n")
    return run_command("alembic upgrade head", "Applying migrations")

def db_downgrade(revision="base"):
    """Downgrade database to specific revision"""
    print(f"⬇️ Downgrading database to revision: {revision}\n")
    return run_command(f"alembic downgrade {revision}", "Rolling back migrations")

def db_status():
    """Show current database status"""
    print("📊 Database Status\n")
    
    # Show current revision
    if not run_command("alembic current", "Current database revision"):
        return False
    
    # Show migration history
    return run_command("alembic history", "Migration history")

def db_reset():
    """Reset database (WARNING: This will delete all data!)"""
    print("⚠️ WARNING: This will completely reset the database!\n")
    
    confirm = input("Are you sure you want to continue? Type 'yes' to confirm: ")
    if confirm.lower() != 'yes':
        print("Operation cancelled.")
        return False
    
    print("🗑️ Resetting database...\n")
    
    # Downgrade to base
    if not run_command("alembic downgrade base", "Removing all tables"):
        return False
    
    # Upgrade to head
    return run_command("alembic upgrade head", "Recreating tables")

def db_check():
    """Check database connection and status"""
    print("🔍 Checking database connection...\n")
    
    try:
        from src.models.database import get_database_manager
        
        db_manager = get_database_manager()
        if db_manager.check_connection():
            print("✅ Database connection successful")
            
            # Show basic info
            with db_manager.get_session() as session:
                try:
                    # Check if tables exist
                    result = session.execute("""
                        SELECT table_name 
                        FROM information_schema.tables 
                        WHERE table_schema = 'public'
                    """)
                    tables = [row[0] for row in result]
                    
                    if tables:
                        print(f"📊 Found {len(tables)} tables: {', '.join(tables)}")
                    else:
                        print("📊 No tables found. Run 'db:init' to create tables.")
                    
                    return True
                except Exception as e:
                    print(f"⚠️ Connected but unable to query tables: {e}")
                    return False
        else:
            print("❌ Database connection failed")
            return False
            
    except Exception as e:
        print(f"❌ Error checking database: {e}")
        return False

def main():
    """Main command dispatcher"""
    parser = argparse.ArgumentParser(description="Database Management Commands")
    parser.add_argument('command', help='Command to run', choices=[
        'init', 'setup', 'migrate', 'upgrade', 'downgrade', 
        'status', 'reset', 'check'
    ])
    parser.add_argument('--message', '-m', help='Migration message', default='Auto migration')
    parser.add_argument('--revision', '-r', help='Revision for downgrade', default='base')
    
    args = parser.parse_args()
    
    # Change to project directory
    os.chdir(project_root)
    
    # Command routing
    commands = {
        'init': db_init,
        'setup': db_setup,
        'migrate': lambda: db_migrate(args.message),
        'upgrade': db_upgrade,
        'downgrade': lambda: db_downgrade(args.revision),
        'status': db_status,
        'reset': db_reset,
        'check': db_check,
    }
    
    command_func = commands.get(args.command)
    if command_func:
        success = command_func()
        sys.exit(0 if success else 1)
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()