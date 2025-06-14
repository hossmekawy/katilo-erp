#!/usr/bin/env python3
"""
Flask-based migration script to create the item_weights table
This script uses the existing Flask app configuration to connect to the database.
"""

import sys
import os

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from sqlalchemy import text

def create_item_weights_table():
    """Create the item_weights table using Flask app context"""
    
    with app.app_context():
        try:
            # Check if table already exists
            result = db.session.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'item_weights'
                );
            """)).fetchone()
            
            table_exists = result[0] if result else False
            
            if table_exists:
                print("Table 'item_weights' already exists. Skipping creation.")
                return True
            
            print("Creating 'item_weights' table...")
            
            # Create the item_weights table
            db.session.execute(text("""
                CREATE TABLE item_weights (
                    id SERIAL PRIMARY KEY,
                    item_id INTEGER NOT NULL,
                    weight DECIMAL(10, 3) DEFAULT 0.000,
                    volume DECIMAL(10, 3) DEFAULT 0.000,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (item_id) REFERENCES items("ItemID") ON DELETE CASCADE,
                    UNIQUE(item_id)
                );
            """))
            
            # Create an index on item_id for better performance
            db.session.execute(text("""
                CREATE INDEX idx_item_weights_item_id ON item_weights(item_id);
            """))
            
            # Create a trigger to update the updated_at timestamp
            db.session.execute(text("""
                CREATE OR REPLACE FUNCTION update_item_weights_updated_at()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = CURRENT_TIMESTAMP;
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
            """))
            
            db.session.execute(text("""
                CREATE TRIGGER trigger_update_item_weights_updated_at
                    BEFORE UPDATE ON item_weights
                    FOR EACH ROW
                    EXECUTE FUNCTION update_item_weights_updated_at();
            """))
            
            # Commit the schema changes
            db.session.commit()
            
            print("Successfully created 'item_weights' table with indexes and triggers.")
            
            # Insert default weight and volume data for existing items
            result = db.session.execute(text("""
                INSERT INTO item_weights (item_id, weight, volume)
                SELECT "ItemID", 0.000, 0.000
                FROM items
                WHERE "ItemID" NOT IN (SELECT item_id FROM item_weights);
            """))
            
            db.session.commit()
            
            # Get count of inserted records
            count_result = db.session.execute(text("SELECT COUNT(*) FROM item_weights;")).fetchone()
            count = count_result[0] if count_result else 0
            print(f"Inserted default weight/volume data for {count} items.")
            
            return True
            
        except Exception as e:
            print(f"Error creating item_weights table: {e}")
            db.session.rollback()
            return False

def drop_item_weights_table():
    """Drop the item_weights table (for rollback purposes)"""
    
    with app.app_context():
        try:
            print("Dropping 'item_weights' table...")
            
            # Drop the table and related objects
            db.session.execute(text("DROP TABLE IF EXISTS item_weights CASCADE;"))
            db.session.execute(text("DROP FUNCTION IF EXISTS update_item_weights_updated_at() CASCADE;"))
            
            db.session.commit()
            
            print("Successfully dropped 'item_weights' table and related objects.")
            
            return True
            
        except Exception as e:
            print(f"Error dropping item_weights table: {e}")
            db.session.rollback()
            return False

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        print("Rolling back: Dropping item_weights table...")
        success = drop_item_weights_table()
    else:
        print("Creating item_weights table...")
        success = create_item_weights_table()
    
    if success:
        print("Migration completed successfully!")
        sys.exit(0)
    else:
        print("Migration failed!")
        sys.exit(1)
