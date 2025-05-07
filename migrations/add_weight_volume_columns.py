import sqlite3
import os
import logging
from flask import current_app

def run_migration():
    """
    Add Weight and Volume columns to the items table.
    This is a direct SQLite migration that doesn't rely on SQLAlchemy.
    """
    try:
        # Get the database path from the app config or use the default
        db_path = 'katilo.db'  # Default path

        try:
            db_path = current_app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        except (RuntimeError, KeyError):
            # If we're not in an application context or the key doesn't exist
            # Use the default path
            pass

        print(f"Using database at: {db_path}")

        # Connect to the SQLite database directly
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if the items table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='items'")
        if not cursor.fetchone():
            print("Items table does not exist. Skipping migration.")
            conn.close()
            return False

        # Check if the Weight column exists
        cursor.execute("PRAGMA table_info(items)")
        columns = [column[1] for column in cursor.fetchall()]

        changes_made = False

        # Add Weight column if it doesn't exist
        if 'Weight' not in columns:
            print("Adding Weight column to items table")
            cursor.execute('ALTER TABLE items ADD COLUMN "Weight" FLOAT DEFAULT 0')
            changes_made = True

        # Add Volume column if it doesn't exist
        if 'Volume' not in columns:
            print("Adding Volume column to items table")
            cursor.execute('ALTER TABLE items ADD COLUMN "Volume" FLOAT DEFAULT 0')
            changes_made = True

        # Commit the changes
        conn.commit()
        conn.close()

        if changes_made:
            print("Successfully added Weight and Volume columns to items table")
        else:
            print("Weight and Volume columns already exist in items table")

        return changes_made

    except Exception as e:
        print(f"Error adding Weight and Volume columns to items table: {str(e)}")
        return False

if __name__ == "__main__":
    # This allows the script to be run directly
    run_migration()
