from models import db

def run_migration():
    """Add image_data column to vehicles table"""
    try:
        # Check if the column already exists
        db.engine.execute("SELECT image_data FROM vehicles LIMIT 1")
        print("Column 'image_data' already exists in vehicles table")
    except Exception as e:
        # Column doesn't exist, add it
        db.engine.execute("ALTER TABLE vehicles ADD COLUMN image_data TEXT")
        print("Added 'image_data' column to vehicles table")
