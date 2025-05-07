"""
Migration script to add company information and payment terms columns to system_settings table
"""
from models import db

def run_migration():
    """
    Add company information and payment terms columns to system_settings table
    """
    try:
        # Check if the columns already exist
        inspector = db.inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('system_settings')]
        
        # Company information columns
        columns_to_add = {
            'company_name': "company_name VARCHAR(100) DEFAULT 'شركة قاتيلو'",
            'company_address': "company_address VARCHAR(255) DEFAULT '123 شارع الأعمال'",
            'company_city': "company_city VARCHAR(100) DEFAULT 'المدينة، المنطقة، الرمز البريدي'",
            'company_email': "company_email VARCHAR(100) DEFAULT 'info@katilo.com'",
            'company_phone': "company_phone VARCHAR(50) DEFAULT '+20 123 456 7890'",
            'company_website': "company_website VARCHAR(100) DEFAULT 'www.katilo.com'",
            'company_tax_id': "company_tax_id VARCHAR(50) DEFAULT ''",
            'payment_terms_days': "payment_terms_days INTEGER DEFAULT 30",
            'payment_terms_text': "payment_terms_text VARCHAR(255) DEFAULT 'يستحق الدفع خلال {days} يوم من تاريخ الفاتورة.'"
        }
        
        # Add columns if they don't exist
        with db.engine.connect() as conn:
            for column_name, column_def in columns_to_add.items():
                if column_name not in columns:
                    conn.execute(db.text(f'ALTER TABLE system_settings ADD COLUMN {column_def}'))
                    print(f"Added '{column_name}' column to system_settings table")
                else:
                    print(f"Column '{column_name}' already exists in system_settings table")
            
            conn.commit()
        
        return True
    except Exception as e:
        print(f"Error adding company information columns: {str(e)}")
        return False
