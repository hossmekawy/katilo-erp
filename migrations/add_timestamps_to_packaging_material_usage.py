"""
Migration script to add created_at and updated_at columns to packaging_material_usage table
"""
import sqlite3
from datetime import datetime

def run_migration():
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
    print("Migration completed successfully")

if __name__ == "__main__":
    run_migration()
