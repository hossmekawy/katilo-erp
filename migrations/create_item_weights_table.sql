-- Create item_weights table migration
-- This script creates the missing item_weights table that is referenced in the Item model.

-- Check if table already exists and create it if it doesn't
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = 'item_weights'
    ) THEN
        -- Create the item_weights table
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

        -- Create an index on item_id for better performance
        CREATE INDEX idx_item_weights_item_id ON item_weights(item_id);

        -- Create a trigger to update the updated_at timestamp
        CREATE OR REPLACE FUNCTION update_item_weights_updated_at()
        RETURNS TRIGGER AS $trigger$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $trigger$ LANGUAGE plpgsql;

        CREATE TRIGGER trigger_update_item_weights_updated_at
            BEFORE UPDATE ON item_weights
            FOR EACH ROW
            EXECUTE FUNCTION update_item_weights_updated_at();

        -- Insert default weight and volume data for existing items
        INSERT INTO item_weights (item_id, weight, volume)
        SELECT "ItemID", 0.000, 0.000
        FROM items
        WHERE "ItemID" NOT IN (SELECT item_id FROM item_weights);

        RAISE NOTICE 'Successfully created item_weights table and inserted default data.';
    ELSE
        RAISE NOTICE 'Table item_weights already exists. Skipping creation.';
    END IF;
END
$$;
