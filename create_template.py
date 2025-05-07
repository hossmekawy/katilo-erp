import pandas as pd
import os

# Create directory if it doesn't exist
os.makedirs('static/uploads/templates', exist_ok=True)

# Create a sample DataFrame
df = pd.DataFrame({
    'Customer Name': ['عميل نموذجي 1', 'عميل نموذجي 2'],
    'Contact Info': ['0123456789', 'example@email.com'],
    'Billing Address': ['عنوان الفواتير 1', 'عنوان الفواتير 2'],
    'Shipping Address': ['عنوان الشحن 1', 'عنوان الشحن 2']
})

# Save to Excel
df.to_excel('static/uploads/templates/customers_import_template.xlsx', index=False)

print("Template created successfully at static/uploads/templates/customers_import_template.xlsx")
