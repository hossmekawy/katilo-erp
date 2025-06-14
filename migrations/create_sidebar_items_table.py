"""
Migration script to create the sidebar_items table
"""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import sys
import os
from sqlalchemy import inspect

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the app and db
from app import app, db
from models_helper import SidebarItem

def run_migration():
    """Run the migration to create the sidebar_items table and populate it with default values"""
    with app.app_context():
        # Create an inspector to check if the table exists
        inspector = inspect(db.engine)
        
        # Check if the table exists
        if 'sidebar_items' not in inspector.get_table_names():
            db.create_all(tables=[SidebarItem.__table__])
            print("Created sidebar_items table")
            
            # Populate with default values
            SidebarItem.create_default_menu()
            print("Populated sidebar_items table with default values")
        else:
            print("sidebar_items table already exists")

if __name__ == "__main__":
    run_migration()
