import re

def fix_constraints_in_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # Pattern to find CheckConstraint with unquoted column names
    pattern = r'CheckConstraint\(([\'"]?)([A-Z][a-zA-Z0-9_]*)\s*([><=!]+)\s*([^,\)]+)([\'"]?)'
    
    # Replace with quoted column names
    fixed_content = re.sub(pattern, r'CheckConstraint(\1"\2"\3\4\5', content)
    
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(fixed_content)
    
    print(f"Fixed constraints in {file_path}")

# Run the fix
fix_constraints_in_file('models.py')
