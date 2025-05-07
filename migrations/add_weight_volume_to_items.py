from models import db, Item
from sqlalchemy import Column, Float
from flask import current_app

def run_migration():
    """
    Add weight and volume columns to the items table.
    """
    # Check if the columns already exist
    inspector = db.inspect(db.engine)
    columns = [column['name'] for column in inspector.get_columns('items')]
    
    changes_made = False
    
    # Add weight column if it doesn't exist
    if 'Weight' not in columns:
        current_app.logger.info("Adding Weight column to items table")
        db.engine.execute('ALTER TABLE items ADD COLUMN "Weight" FLOAT DEFAULT 0')
        changes_made = True
    
    # Add volume column if it doesn't exist
    if 'Volume' not in columns:
        current_app.logger.info("Adding Volume column to items table")
        db.engine.execute('ALTER TABLE items ADD COLUMN "Volume" FLOAT DEFAULT 0')
        changes_made = True
    
    if changes_made:
        current_app.logger.info("Successfully added weight and volume columns to items table")
    else:
        current_app.logger.info("Weight and volume columns already exist in items table")
    
    return changes_made
