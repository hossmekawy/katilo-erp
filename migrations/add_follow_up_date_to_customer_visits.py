from flask import Flask
from models import db, CustomerVisit
from sqlalchemy import Column, Date
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def run_migration():
    """
    Add follow_up_date column to customer_visits table
    """
    try:
        # Check if the column already exists
        inspector = db.inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('customer_visits')]

        if 'follow_up_date' not in columns:
            # Add the column
            with db.engine.connect() as conn:
                conn.execute(db.text('ALTER TABLE customer_visits ADD COLUMN follow_up_date DATE'))
                conn.commit()
            print("Successfully added follow_up_date column to customer_visits table")
        else:
            print("follow_up_date column already exists in customer_visits table")

        return True
    except Exception as e:
        print(f"Error adding follow_up_date column: {str(e)}")
        return False

if __name__ == "__main__":
    # Create a minimal Flask app
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///katilo.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Initialize the database
    db.init_app(app)

    with app.app_context():
        run_migration()
