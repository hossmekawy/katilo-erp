"""
Migration to add font_family column to the system_settings table.
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
    """Add font_family column to the system_settings table if it doesn't exist."""
    db_path = get_database_path()
    
    if not db_path:
        print("Database file not found.")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if the column already exists
    cursor.execute("PRAGMA table_info(system_settings)")
    columns = [column[1] for column in cursor.fetchall()]
    
    # Add font_family column if it doesn't exist
    if 'font_family' not in columns:
        try:
            cursor.execute("ALTER TABLE system_settings ADD COLUMN font_family TEXT DEFAULT 'Tajawal'")
            print("Added column 'font_family' to system_settings table")
        except sqlite3.Error as e:
            print(f"Error adding column 'font_family': {e}")
    else:
        print("Column 'font_family' already exists in system_settings table")
    
    # Commit the changes
    conn.commit()
    conn.close()
    
    return True

if __name__ == "__main__":
    run_migration()
