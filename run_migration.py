"""
Standalone script to run migrations
"""
import sqlite3
import os
from datetime import datetime

def run_packaging_material_migration():
    """Add created_at and updated_at columns to packaging_material_usage table"""
    conn = sqlite3.connect('instance/katilo.db')
    cursor = conn.cursor()

    # Check if columns already exist
    cursor.execute("PRAGMA table_info(packaging_material_usage)")
    columns = [column[1] for column in cursor.fetchall()]

    # Add created_at column if it doesn't exist
    if 'created_at' not in columns:
        cursor.execute("ALTER TABLE packaging_material_usage ADD COLUMN created_at TIMESTAMP")
        print("Added created_at column to packaging_material_usage table")

    # Add updated_at column if it doesn't exist
    if 'updated_at' not in columns:
        cursor.execute("ALTER TABLE packaging_material_usage ADD COLUMN updated_at TIMESTAMP")
        print("Added updated_at column to packaging_material_usage table")

    # Update existing rows to have a default timestamp
    current_time = datetime.utcnow().isoformat()
    cursor.execute("UPDATE packaging_material_usage SET created_at = ? WHERE created_at IS NULL", (current_time,))
    cursor.execute("UPDATE packaging_material_usage SET updated_at = ? WHERE updated_at IS NULL", (current_time,))
    print(f"Updated {cursor.rowcount} rows with default timestamps")

    conn.commit()
    conn.close()
    print("Packaging material migration completed successfully")

def run_theme_columns_migration():
    """Add theme-related columns to the system_settings table if they don't exist."""
    conn = sqlite3.connect('instance/katilo.db')
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
    print("Theme columns migration completed successfully")

if __name__ == "__main__":
    print("Running theme columns migration...")
    run_theme_columns_migration()
    print("\nRunning packaging material migration...")
    run_packaging_material_migration()
