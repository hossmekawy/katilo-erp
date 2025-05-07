"""
Migration to add theme-related columns to the system_settings table.
"""

import sqlite3
import os
import sys

# Add the parent directory to sys.path to allow importing from the root directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_database_path():
    """Get the path to the SQLite database file"""
    # Try multiple possible locations
    possible_db_paths = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'katilo.db'),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'instance', 'katilo.db'),
        'katilo.db',
        'instance/katilo.db'
    ]

    # Check each path
    for path in possible_db_paths:
        if os.path.exists(path):
            return path

    # Return None if no database file is found
    return None

def run_migration():
    """Add theme-related columns to the system_settings table if they don't exist."""
    db_path = get_database_path()
    
    if not db_path:
        print("Database file not found.")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if the columns already exist
    cursor.execute("PRAGMA table_info(system_settings)")
    columns = [column[1] for column in cursor.fetchall()]
    
    # Define the columns to add with their default values
    columns_to_add = {
        'theme_mode': "'light'",
        'border_radius': "'medium'",
        'animation_speed': "'normal'",
        'layout_density': "'comfortable'",
        'sidebar_collapsed': "0",
        'favicon_image': "'/static/favicon.ico'"
    }
    
    # Add each column if it doesn't exist
    for column_name, default_value in columns_to_add.items():
        if column_name not in columns:
            try:
                cursor.execute(f"ALTER TABLE system_settings ADD COLUMN {column_name} TEXT DEFAULT {default_value}")
                print(f"Added column '{column_name}' to system_settings table")
            except sqlite3.Error as e:
                print(f"Error adding column '{column_name}': {e}")
    
    # Commit the changes
    conn.commit()
    conn.close()
    
    return True

if __name__ == "__main__":
    run_migration()
