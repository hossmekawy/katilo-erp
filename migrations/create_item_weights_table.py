"""
Create item_weights table migration script
This script creates the missing item_weights table that is referenced in the Item model.
"""

import psycopg2
import os
from urllib.parse import urlparse

def create_item_weights_table():
    """Create the item_weights table in the database"""

    # Get database URL from environment or use default
    database_url = os.getenv('DATABASE_URL', 'postgresql://postgres:@localhost:5432/katiloerp')
    print(f"Using database URL: {database_url}")
    
    try:
        # Parse the database URL
        parsed_url = urlparse(database_url)
        
        # Connect to the database
        conn = psycopg2.connect(
            host=parsed_url.hostname,
            port=parsed_url.port or 5432,
            database=parsed_url.path[1:],  # Remove leading slash
            user=parsed_url.username,
            password=parsed_url.password
        )
        
        cursor = conn.cursor()
        
        # Check if table already exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'item_weights'
            );
        """)
        
        table_exists = cursor.fetchone()[0]
        
        if table_exists:
            print("Table 'item_weights' already exists. Skipping creation.")
            cursor.close()
            conn.close()
            return True
        
        # Create the item_weights table
        create_table_sql = """
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
        """
        
        cursor.execute(create_table_sql)
        
        # Create an index on item_id for better performance
        cursor.execute("""
            CREATE INDEX idx_item_weights_item_id ON item_weights(item_id);
        """)
        
        # Create a trigger to update the updated_at timestamp
        cursor.execute("""
            CREATE OR REPLACE FUNCTION update_item_weights_updated_at()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = CURRENT_TIMESTAMP;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """)
        
        cursor.execute("""
            CREATE TRIGGER trigger_update_item_weights_updated_at
                BEFORE UPDATE ON item_weights
                FOR EACH ROW
                EXECUTE FUNCTION update_item_weights_updated_at();
        """)
        
        # Commit the changes
        conn.commit()
        
        print("Successfully created 'item_weights' table with indexes and triggers.")
        
        # Insert default weight and volume data for existing items
        cursor.execute("""
            INSERT INTO item_weights (item_id, weight, volume)
            SELECT "ItemID", 0.000, 0.000
            FROM items
            WHERE "ItemID" NOT IN (SELECT item_id FROM item_weights);
        """)
        
        conn.commit()
        
        # Get count of inserted records
        cursor.execute("SELECT COUNT(*) FROM item_weights;")
        count = cursor.fetchone()[0]
        print(f"Inserted default weight/volume data for {count} items.")
        
        cursor.close()
        conn.close()
        
        return True
        
    except psycopg2.Error as e:
        print(f"Database error: {e}")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False

def drop_item_weights_table():
    """Drop the item_weights table (for rollback purposes)"""

    # Get database URL from environment or use default
    database_url = os.getenv('DATABASE_URL', 'postgresql://postgres:@localhost:5432/katiloerp')
    print(f"Using database URL: {database_url}")
    
    try:
        # Parse the database URL
        parsed_url = urlparse(database_url)
        
        # Connect to the database
        conn = psycopg2.connect(
            host=parsed_url.hostname,
            port=parsed_url.port or 5432,
            database=parsed_url.path[1:],  # Remove leading slash
            user=parsed_url.username,
            password=parsed_url.password
        )
        
        cursor = conn.cursor()
        
        # Drop the table and related objects
        cursor.execute("DROP TABLE IF EXISTS item_weights CASCADE;")
        cursor.execute("DROP FUNCTION IF EXISTS update_item_weights_updated_at() CASCADE;")
        
        conn.commit()
        
        print("Successfully dropped 'item_weights' table and related objects.")
        
        cursor.close()
        conn.close()
        
        return True
        
    except psycopg2.Error as e:
        print(f"Database error: {e}")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    import sys
    
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
