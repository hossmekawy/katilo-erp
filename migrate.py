import sqlite3

# Connect to the SQLite database
conn = sqlite3.connect('instance/katilo.db')
cursor = conn.cursor()

# Check if columns exist
cursor.execute("PRAGMA table_info(sales_orders)")
columns = [column[1] for column in cursor.fetchall()]
print("Current columns in sales_orders table:", columns)

# Add missing columns
try:
    if 'payment_method' not in columns:
        cursor.execute("ALTER TABLE sales_orders ADD COLUMN payment_method TEXT DEFAULT 'cash'")
        print("Added payment_method column")
    
    if 'cash_account_id' not in columns:
        cursor.execute("ALTER TABLE sales_orders ADD COLUMN cash_account_id INTEGER")
        print("Added cash_account_id column")
    
    if 'payment_status' not in columns:
        cursor.execute("ALTER TABLE sales_orders ADD COLUMN payment_status TEXT DEFAULT 'Unpaid'")
        print("Added payment_status column")
    
    if 'payment_reference' not in columns:
        cursor.execute("ALTER TABLE sales_orders ADD COLUMN payment_reference TEXT")
        print("Added payment_reference column")
    
    # Commit changes
    conn.commit()
    print("Database migration completed successfully")
except Exception as e:
    print(f"Error during migration: {e}")
finally:
    # Close connection
    conn.close()
