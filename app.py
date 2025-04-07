from io import BytesIO
from flask import Flask, request, jsonify, session, redirect, render_template,send_file
from datetime import datetime
import json
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from sqlalchemy import inspect
from werkzeug.security import generate_password_hash
from routes.bom_routes import bom_bp
from routes.supplier_routes import supplier_bp
from routes.purchase_orders import purchase_order_bp
from routes.support_routes import support_bp
from routes.supplier_accounts import supplier_accounts_bp
from routes.warehouse_routes import warehouse_bp
from routes.profile_routes import profile_bp
from routes.quality_control import quality_bp
# from routes.production_routes import production_bp
from routes.chatbot_routes import chatbot_bp 
from flask_migrate import Migrate
from dotenv import load_dotenv
import os 
import tempfile
import subprocess
import socket
import webbrowser
import urllib.request
from models import (
    # Core Entities
    Category, Item, Warehouse,
    
    # Warehouse Layout
    WarehouseSection, WarehouseSlot,
    
    # Inventory & Transactions
    Inventory, InventoryTransaction,
    
    # Manufacturing
    BOM, BOMDetail,
    
    # Supplier Management
    Supplier, SupplierItem, SupplierLedgerEntry, SupplierPayment,
    
    # Purchase Orders
    PurchaseOrder, PurchaseOrderDetail,
    
    # Sales & Customers
    Customer, SalesOrder, SalesOrderDetail,
    
    # Lot/Batch Tracking
    Batch, BatchSlot,
    
    # Quality Control
    QualityCheck, QualityCheckResult, QCParameter,
    
    # Equipment & Maintenance
    Equipment, MaintenanceLog,
    
    # Shipping
    Shipment, ShipmentDetail,
    
    # User Management
    SystemSettings, Role, User, Permission, RolePermission,
    
    # Document Management
    Document,
    
    # Production Planning
    ProductionRun, ProductionRunDetail,
    
    # Packaging
    ProductPackaging, PackagingMaterial,
    
    # Advanced Features
    DemandForecast,
    InventoryReplenishmentPlan,
    EmployeeShift,
    ProductionEfficiency,
    CustomerInteraction,
    DiscountPromotion,
    ProductReturn,
    db
)

# Initialize Flask app
app = Flask(__name__)

# App configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///katilo.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-default-secret-key')
app.config['UPLOAD_FOLDER'] = 'static/uploads/support'
app.config['PROFILE_UPLOAD_FOLDER'] = 'static/uploads/profiles'
app.config['GEMINI_API_KEY'] = os.getenv("GEMINI_API_KEY")
# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)

# Ensure upload directory exists
import os
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['PROFILE_UPLOAD_FOLDER'], exist_ok=True)


# Register blueprints
app.register_blueprint(support_bp)
app.register_blueprint(bom_bp)
app.register_blueprint(supplier_bp)
app.register_blueprint(purchase_order_bp)
app.register_blueprint(supplier_accounts_bp)
app.register_blueprint(warehouse_bp)
app.register_blueprint(profile_bp)
app.register_blueprint(quality_bp)
# app.register_blueprint(production_bp)
app.register_blueprint(chatbot_bp)
# Create database tables

migrate = Migrate(app, db)

with app.app_context():
    db.create_all()
    
    default_permissions = [
        'view_users', 'create_users', 'edit_users', 'delete_users',
        'view_roles', 'create_roles', 'edit_roles', 'delete_roles',
        'view_inventory', 'manage_inventory',
        'view_categories', 'manage_categories',
        'view_items', 'manage_items',
        'view_transactions', 'manage_transactions'
    ]
    for perm_name in default_permissions:
        if not Permission.query.filter_by(permission_name=perm_name).first():
            permission = Permission(permission_name=perm_name)
            db.session.add(permission)
            
    # Create admin role if it doesn't exist
    admin_role = Role.query.filter_by(name='admin').first()
    if not admin_role:
        admin_role = Role(name='admin')
        db.session.add(admin_role)
        db.session.commit()
        
        # Assign all permissions to admin role
        for permission in Permission.query.all():
            role_permission = RolePermission(
                role_id=admin_role.id,
                permission_id=permission.id
            )
            db.session.add(role_permission)
    
    # Create default user role if it doesn't exist
    if not Role.query.filter_by(name='user').first():
        user_role = Role(name='user')
        db.session.add(user_role)
    
    db.session.commit()

    # Create admin user if it doesn't exist
    if not User.query.filter_by(email='hussienmekawy38@gmail.com').first():
        admin_user = User(
            username='hussien',
            email='hussienmekawy38@gmail.com',
            role_id=admin_role.id
        )
        admin_user.set_password('Sahs223344$')
        db.session.add(admin_user)
        db.session.commit()
    
    if inspect(db.engine).has_table(SupplierLedgerEntry.__tablename__) and not SupplierLedgerEntry.query.first():
        # Get all purchase orders
        purchase_orders = PurchaseOrder.query.all()
        
        # Create ledger entries for each purchase order
        for po in purchase_orders:
            if po.status != 'Cancelled':
                ledger_entry = SupplierLedgerEntry(
                    supplier_id=po.supplier_id,
                    entry_date=po.order_date,
                    description="طلب شراء",
                    reference_type='purchase_order',
                    reference_id=po.id,
                    debit=po.total_amount  # Debit increases when we order from supplier
                )
                db.session.add(ledger_entry)
        
        db.session.commit()
        print("Created ledger entries for existing purchase orders")
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.errorhandler(401)
def unauthorized(error):
    return render_template('unauthorized.html'), 401

# Also add a handler for 403 Forbidden errors
@app.errorhandler(403)
def forbidden(error):
    return render_template('unauthorized.html'), 403

# Error handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('errors/404.html'), 404

# Authentication Routes
@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    
    # Check if user already exists
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'message': 'Email already registered'}), 400
        
    # Create new user with default role
    user = User(
        username=data['username'],
        email=data['email'],
        role_id=1  # Default user role
    )
    user.set_password(data['password'])
    
    # Add default user role if not exists
    default_role = Role.query.filter_by(name='user').first()
    if not default_role:
        default_role = Role(name='user')
        db.session.add(default_role)
        
    db.session.add(user)
    db.session.commit()
    
    return jsonify({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'role': default_role.name
    }), 201

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    
    login_identifier = data.get('login_identifier', '')
    password = data.get('password', '')
    
    
    user = User.query.filter(
        (User.email == login_identifier) | (User.username == login_identifier)
    ).first()
    
    
    if user and user.check_password(data['password']):
        login_user(user)
        return jsonify({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.role.name if user.role else 'user',
            'redirect': '/dashboard' 
        })
    
    return jsonify({'message': 'بيانات الدخول غير صحيحة'}), 401

@app.route('/api/auth/logout')
@login_required
def logout():
    logout_user()
    return redirect('/')  # Direct redirect to home page



@app.route('/api/roles', methods=['GET'])
@login_required
def get_roles():
    roles = Role.query.all()
    return jsonify([{
        'id': r.id,
        'name': r.name
    } for r in roles])

@app.route('/api/roles', methods=['POST'])
@login_required
def create_role():
    if not current_user.role or current_user.role.name != 'admin':
        return jsonify({'message': 'Unauthorized'}), 403
        
    data = request.get_json()
    role = Role(name=data['name'])
    db.session.add(role)
    db.session.commit()
    
    return jsonify({
        'id': role.id,
        'name': role.name
    }), 201

# Permission Management Routes
@app.route('/api/permissions', methods=['GET'])
@login_required
def get_permissions():
    if not current_user.role or current_user.role.name != 'admin':
        return jsonify({'message': 'Unauthorized'}), 403
        
    permissions = Permission.query.all()
    return jsonify([{
        'id': p.id,
        'permission_name': p.permission_name
    } for p in permissions])

@app.route('/api/roles/<int:role_id>/permissions', methods=['POST'])
@login_required
def assign_permission_to_role(role_id):
    if not current_user.role or current_user.role.name != 'admin':
        return jsonify({'message': 'Unauthorized'}), 403
        
    data = request.get_json()
    role_permission = RolePermission(
        role_id=role_id,
        permission_id=data['permission_id']
    )
    db.session.add(role_permission)
    db.session.commit()
    
    return jsonify({'message': 'Permission assigned successfully'}), 201


# Admin User Management Routes
@app.route('/api/admin/users', methods=['GET'])
@login_required
def get_users():
    if not current_user.role or current_user.role.name != 'admin':
        return jsonify({'message': 'Unauthorized'}), 403
        
    users = User.query.all()
    return jsonify([{
        'id': u.id,
        'username': u.username,
        'email': u.email,
        'role_id': u.role_id,
        'is_active': u.is_active,
        'department': u.department,
        'position': u.position,
        'profile_image': u.profile_image
    } for u in users])

@app.route('/api/admin/users', methods=['POST'])
@login_required
def create_user():
    if not current_user.role or current_user.role.name != 'admin':
        return jsonify({'message': 'Unauthorized'}), 403
        
    data = request.get_json()
    
    # Validate required fields
    if not data.get('username') or not data.get('email') or not data.get('password'):
        return jsonify({'message': 'Missing required fields'}), 400
        
    # Check if user already exists
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'message': 'Email already registered'}), 400
    
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'message': 'Username already taken'}), 400
    
    # Create new user
    user = User(
        username=data['username'],
        email=data['email'],
        role_id=data.get('role_id'),
        is_active=data.get('is_active', True),
        department=data.get('department'),
        position=data.get('position')
    )
    user.set_password(data['password'])
    
    db.session.add(user)
    db.session.commit()
    
    return jsonify({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'role_id': user.role_id,
        'is_active': user.is_active
    }), 201

@app.route('/api/admin/users/<int:id>', methods=['PUT'])
@login_required
def update_user(id):
    if not current_user.role or current_user.role.name != 'admin':
        return jsonify({'message': 'Unauthorized'}), 403
        
    user = User.query.get_or_404(id)
    data = request.get_json()
    
    # Update user fields
    if 'username' in data:
        # Check if username is already taken by another user
        existing_user = User.query.filter_by(username=data['username']).first()
        if existing_user and existing_user.id != id:
            return jsonify({'message': 'Username already taken'}), 400
        user.username = data['username']
        
    if 'email' in data:
        # Check if email is already registered to another user
        existing_user = User.query.filter_by(email=data['email']).first()
        if existing_user and existing_user.id != id:
            return jsonify({'message': 'Email already registered'}), 400
        user.email = data['email']
        
    if 'role_id' in data:
        user.role_id = data['role_id']
        
    if 'is_active' in data:
        user.is_active = data['is_active']
        
    if 'department' in data:
        user.department = data['department']
        
    if 'position' in data:
        user.position = data['position']
    
    # Handle password change if provided
    if 'password' in data and data['password']:
        user.set_password(data['password'])
    
    db.session.commit()
    
    return jsonify({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'role_id': user.role_id,
        'is_active': user.is_active,
        'department': user.department,
        'position': user.position
    })

@app.route('/api/admin/users/<int:id>', methods=['DELETE'])
@login_required
def delete_user(id):
    if not current_user.role or current_user.role.name != 'admin':
        return jsonify({'message': 'Unauthorized'}), 403
        
    user = User.query.get_or_404(id)
    
    # Prevent deleting the current user
    if user.id == current_user.id:
        return jsonify({'message': 'Cannot delete your own account'}), 400
    
    db.session.delete(user)
    db.session.commit()
    
    return '', 204

@app.route('/api/admin/users/<int:id>/toggle-status', methods=['PUT'])
@login_required
def toggle_user_status(id):
    if not current_user.role or current_user.role.name != 'admin':
        return jsonify({'message': 'Unauthorized'}), 403
        
    user = User.query.get_or_404(id)
    
    # Prevent deactivating the current user
    if user.id == current_user.id:
        return jsonify({'message': 'Cannot change status of your own account'}), 400
    
    user.is_active = not user.is_active
    db.session.commit()
    
    return jsonify({
        'id': user.id,
        'is_active': user.is_active
    })

# Admin Role Management Routes
@app.route('/api/admin/role-permissions', methods=['GET'])
@login_required
def get_role_permissions():
    if not current_user.role or current_user.role.name != 'admin':
        return jsonify({'message': 'Unauthorized'}), 403
        
    role_permissions = RolePermission.query.all()
    return jsonify([{
        'role_id': rp.role_id,
        'permission_id': rp.permission_id
    } for rp in role_permissions])

@app.route('/api/admin/roles/<int:id>', methods=['PUT'])
@login_required
def update_role(id):
    if not current_user.role or current_user.role.name != 'admin':
        return jsonify({'message': 'Unauthorized'}), 403
        
    role = Role.query.get_or_404(id)
    data = request.get_json()
    
    # Prevent modifying the admin role
    if role.name == 'admin' and data.get('name') != 'admin':
        return jsonify({'message': 'Cannot modify the admin role name'}), 400
    
    if 'name' in data:
        # Check if role name already exists
        existing_role = Role.query.filter_by(name=data['name']).first()
        if existing_role and existing_role.id != id:
            return jsonify({'message': 'Role name already exists'}), 400
        role.name = data['name']
    
    db.session.commit()
    
    return jsonify({
        'id': role.id,
        'name': role.name
    })

@app.route('/api/admin/roles/<int:id>', methods=['DELETE'])
@login_required
def delete_role(id):
    if not current_user.role or current_user.role.name != 'admin':
        return jsonify({'message': 'Unauthorized'}), 403
        
    role = Role.query.get_or_404(id)
    
    # Prevent deleting the admin role
    if role.name == 'admin':
        return jsonify({'message': 'Cannot delete the admin role'}), 400
    
    # Check if role is assigned to any users
    users_with_role = User.query.filter_by(role_id=id).count()
    if users_with_role > 0:
        return jsonify({'message': 'Cannot delete role assigned to users'}), 400
    
    # Delete role permissions first
    RolePermission.query.filter_by(role_id=id).delete()
    
    db.session.delete(role)
    db.session.commit()
    
    return '', 204

@app.route('/api/admin/roles/<int:role_id>/permissions/<int:permission_id>', methods=['DELETE'])
@login_required
def remove_permission_from_role(role_id, permission_id):
    if not current_user.role or current_user.role.name != 'admin':
        return jsonify({'message': 'Unauthorized'}), 403
        
    role_permission = RolePermission.query.filter_by(
        role_id=role_id, 
        permission_id=permission_id
    ).first_or_404()
    
    db.session.delete(role_permission)
    db.session.commit()
    
    return '', 204





# Category Routes
@app.route('/api/categories', methods=['GET'])
@login_required
def get_categories():
    categories = Category.query.all()
    return jsonify([{
        'id': c.id, 
        'name': c.name, 
        'description': c.description,
        'category_type': c.category_type
    } for c in categories])

@app.route('/api/categories', methods=['POST'])
@login_required
def create_category():
    data = request.get_json()
    category = Category(
        name=data['name'], 
        description=data.get('description'),
        category_type=data.get('category_type', 'RawMaterial')  # Default to RawMaterial if not specified
    )
    db.session.add(category)
    db.session.commit()
    return jsonify({
        'id': category.id, 
        'name': category.name, 
        'description': category.description,
        'category_type': category.category_type
    }), 201

@app.route('/api/categories/<int:id>', methods=['PUT'])
@login_required
def update_category(id):
    category = Category.query.get_or_404(id)
    data = request.get_json()
    category.name = data.get('name', category.name)
    category.description = data.get('description', category.description)
    category.category_type = data.get('category_type', category.category_type)
    db.session.commit()
    return jsonify({
        'id': category.id, 
        'name': category.name, 
        'description': category.description,
        'category_type': category.category_type
    })
    
@app.route('/api/categories/<int:id>', methods=['DELETE'])
@login_required
def delete_category(id):
    category = Category.query.get_or_404(id)
    db.session.delete(category)
    db.session.commit()
    return '', 204

# Item Routes
@app.route('/api/items', methods=['GET'])
@login_required
def get_items():
    items = Item.query.all()
    return jsonify([{
        'id': i.id,
        'name': i.name,
        'category_id': i.category_id,
        'sku': i.sku,
        'description': i.description,
        'unit_of_measure': i.unit_of_measure,
        'cost': i.cost,
        'price': i.price,
        'reorder_level': i.reorder_level
    } for i in items])

@app.route('/api/items', methods=['POST'])
@login_required
def create_item():
    data = request.get_json()
    existing_item = Item.query.filter_by(sku=data['sku']).first()
    if existing_item:
        return jsonify({'message': 'عنصر بنفس الرمز التعريفي (SKU) موجود بالفعل'}), 400
    item = Item(
        name=data['name'],
        category_id=data['category_id'],
        sku=data['sku'],
        description=data.get('description'),
        unit_of_measure=data['unit_of_measure'],
        cost=data['cost'],
        price=data['price'],
        reorder_level=data['reorder_level']
    )
    db.session.add(item)
    db.session.commit()
    return jsonify({
        'id': item.id,
        'name': item.name,
        'sku': item.sku,
        'category_id': item.category_id
    }), 201

@app.route('/api/items/<int:id>', methods=['PUT'])
@login_required
def update_item(id):
    item = Item.query.get_or_404(id)
    data = request.get_json()
    for key, value in data.items():
        if hasattr(item, key):
            setattr(item, key, value)
    db.session.commit()
    return jsonify({'id': item.id, 'name': item.name, 'sku': item.sku})

@app.route('/api/items/<int:id>', methods=['DELETE'])
@login_required
def delete_item(id):
    item = Item.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    return '', 204

# Inventory Routes
@app.route('/api/inventory', methods=['GET'])
@login_required
def get_inventory():
    inventory = Inventory.query.all()
    return jsonify([{
        'id': inv.id,
        'item_id': inv.item_id,
        'warehouse_id': inv.warehouse_id,
        'quantity': inv.quantity,
        'last_updated': inv.last_updated.isoformat()
    } for inv in inventory])

@app.route('/api/inventory/update', methods=['POST'])
@login_required
def update_inventory():
    data = request.get_json()
    
    # Validate required fields
    if not data.get('item_id') or not data.get('warehouse_id') or 'quantity' not in data:
        return jsonify({'message': 'Missing required fields'}), 400
    
    item_id = data['item_id']
    warehouse_id = data['warehouse_id']
    quantity = data['quantity']
    transaction_type = data.get('transaction_type', 'IN')
    reference = data.get('reference', '')
    
    # Get current inventory record
    inventory = Inventory.query.filter_by(
        item_id=item_id,
        warehouse_id=warehouse_id
    ).first()
    
    # Create new inventory record if it doesn't exist
    if not inventory:
        # For OUT transactions, we can't remove from non-existent inventory
        if transaction_type == 'OUT' or quantity < 0:
            return jsonify({'message': 'لا يوجد مخزون كافٍ لهذا العنصر في المستودع المحدد'}), 400
            
        inventory = Inventory(
            item_id=item_id,
            warehouse_id=warehouse_id,
            quantity=quantity
        )
        db.session.add(inventory)
    else:
        # Update existing inventory
        new_quantity = inventory.quantity + quantity
        
        # Prevent negative inventory for OUT transactions
        if new_quantity < 0:
            return jsonify({'message': f'لا يوجد مخزون كافٍ. الكمية المتاحة: {inventory.quantity}'}), 400
            
        inventory.quantity = new_quantity
    
    # Create transaction record with the absolute quantity value
    transaction = InventoryTransaction(
        item_id=item_id,
        warehouse_id=warehouse_id,
        transaction_type=transaction_type,
        quantity=abs(quantity),
        reference=reference
    )
    db.session.add(transaction)
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Database error: {str(e)}'}), 500
    
    return jsonify({
        'inventory_id': inventory.id,
        'quantity': inventory.quantity,
        'transaction_id': transaction.id
    })


# Inventory Transaction Routes
@app.route('/api/transactions', methods=['GET'])
@login_required
def get_transactions():
    transactions = InventoryTransaction.query.all()
    return jsonify([{
        'id': t.id,
        'item_id': t.item_id,
        'warehouse_id': t.warehouse_id,
        'transaction_type': t.transaction_type,
        'quantity': t.quantity,
        'transaction_date': t.transaction_date.isoformat(),
        'reference': t.reference
    } for t in transactions])


# Warehouse Section Routes
# Dashboard API Endpoints
@app.route('/api/dashboard/stats')
@login_required
def get_dashboard_stats():
    # Get counts
    items_count = Item.query.count()
    warehouses_count = Warehouse.query.count()
    categories_count = Category.query.count()
    transactions_count = InventoryTransaction.query.count()
    
    return jsonify({
        'totalItems': items_count,
        'totalWarehouses': warehouses_count,
        'totalCategories': categories_count,
        'totalTransactions': transactions_count
    })

@app.route('/api/dashboard/low-stock')
@login_required
def get_low_stock_items():
    # Get items with quantity below reorder level
    items = Item.query.all()
    low_stock_items = []
    
    for item in items:
        # Calculate total quantity across all warehouses
        total_quantity = db.session.query(db.func.sum(Inventory.quantity))\
            .filter(Inventory.item_id == item.id).scalar() or 0
        
        if total_quantity <= item.reorder_level:
            low_stock_items.append({
                'id': item.id,
                'name': item.name,
                'quantity': total_quantity,
                'reorder_level': item.reorder_level
            })
    
    return jsonify(low_stock_items)

@app.route('/api/dashboard/recent-transactions')
@login_required
def get_recent_transactions():
    # Get 10 most recent transactions
    transactions = InventoryTransaction.query.order_by(
        InventoryTransaction.transaction_date.desc()
    ).limit(10).all()
    
    result = []
    for txn in transactions:
        item = Item.query.get(txn.item_id)
        result.append({
            'id': txn.id,
            'item_id': txn.item_id,
            'item_name': item.name if item else None,
            'warehouse_id': txn.warehouse_id,
            'transaction_type': txn.transaction_type,
            'quantity': txn.quantity,
            'transaction_date': txn.transaction_date.isoformat(),
            'reference': txn.reference
        })
    
    return jsonify(result)


def generate_pdf(html_content, output_path=None):
    """Generate a PDF from HTML content using wkhtmltopdf"""
    # Path to wkhtmltopdf executable
    wkhtmltopdf_path = 'pdftool\\wkhtmltopdf\\bin\\wkhtmltopdf.exe'
    
    # If no output path specified, create a temporary file
    if not output_path:
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        output_path = temp_file.name
        temp_file.close()
    
    # Create a temporary HTML file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.html', mode='w', encoding='utf-8') as f:
        f.write(html_content)
        html_path = f.name
    
    try:
        # Run wkhtmltopdf to generate PDF
        subprocess.run([
            wkhtmltopdf_path,
            '--encoding', 'utf-8',
            '--margin-top', '10mm',
            '--margin-right', '10mm',
            '--margin-bottom', '10mm',
            '--margin-left', '10mm',
            '--page-size', 'A4',
            '--enable-local-file-access',
            html_path,
            output_path
        ], check=True)
        
        # Remove temporary HTML file
        os.unlink(html_path)
        
        return output_path
    except Exception as e:
        # Clean up temporary files in case of error
        if os.path.exists(html_path):
            os.unlink(html_path)
        if os.path.exists(output_path):
            os.unlink(output_path)
        raise e
    
    
@app.route('/inventory-reports')
@login_required
def inventory_reports_page():
    # Check if user is admin
    if not current_user.role or current_user.role.name != 'admin':
        return redirect('/dashboard')
    return render_template('inventory_reports.html')


@app.route('/api/inventory/reports/generate', methods=['POST'])
@login_required
def generate_inventory_report():
    data = request.get_json()
    
    # Extract report parameters
    report_type = data.get('report_type', 'full_inventory')
    date_from = data.get('date_from')
    date_to = data.get('date_to')
    warehouse_id = data.get('warehouse_id')
    category_id = data.get('category_id')
    item_id = data.get('item_id')
    include_zero_stock = data.get('include_zero_stock', False)
    format_type = data.get('format', 'pdf')  # pdf, excel, csv
    
    # Convert date strings to datetime objects if provided
    from_date = None
    to_date = None
    
    if date_from:
        try:
            from_date = datetime.strptime(date_from, '%Y-%m-%d')
        except ValueError:
            return jsonify({'message': 'Invalid from date format. Use YYYY-MM-DD'}), 400
    
    if date_to:
        try:
            to_date = datetime.strptime(date_to, '%Y-%m-%d')
        except ValueError:
            return jsonify({'message': 'Invalid to date format. Use YYYY-MM-DD'}), 400
    
    # Generate report based on type
    if report_type == 'full_inventory':
        return generate_full_inventory_report(warehouse_id, category_id, item_id, include_zero_stock, format_type)
    elif report_type == 'low_stock':
        return generate_low_stock_report(warehouse_id, category_id, format_type)
    elif report_type == 'transactions':
        return generate_transactions_report(from_date, to_date, warehouse_id, item_id, format_type)
    elif report_type == 'item_transactions':
        if not item_id:
            return jsonify({'message': 'Item ID is required for item transactions report'}), 400
        return generate_item_transactions_report(item_id, from_date, to_date, warehouse_id, format_type)
    elif report_type == 'warehouse_inventory':
        if not warehouse_id:
            return jsonify({'message': 'Warehouse ID is required for warehouse inventory report'}), 400
        return generate_warehouse_inventory_report(warehouse_id, category_id, include_zero_stock, format_type)
    elif report_type == 'category_inventory':
        if not category_id:
            return jsonify({'message': 'Category ID is required for category inventory report'}), 400
        return generate_category_inventory_report(category_id, warehouse_id, include_zero_stock, format_type)
    else:
        return jsonify({'message': 'Invalid report type'}), 400

def generate_full_inventory_report(warehouse_id=None, category_id=None, item_id=None, include_zero_stock=False, format_type='pdf'):
    """Generate a full inventory report with optional filtering"""
    # Base query for inventory
    query = db.session.query(
        Inventory, Item, Warehouse, Category
    ).join(
        Item, Inventory.item_id == Item.id
    ).join(
        Warehouse, Inventory.warehouse_id == Warehouse.id
    ).join(
        Category, Item.category_id == Category.id
    )
    
    # Apply filters
    if warehouse_id:
        query = query.filter(Inventory.warehouse_id == warehouse_id)
    
    if category_id:
        query = query.filter(Item.category_id == category_id)
    
    if item_id:
        query = query.filter(Inventory.item_id == item_id)
    
    if not include_zero_stock:
        query = query.filter(Inventory.quantity > 0)
    
    # Execute query
    results = query.all()
    
    # Prepare data for the report
    inventory_data = []
    for inv, item, warehouse, category in results:
        inventory_data.append({
            'inventory_id': inv.id,
            'item_id': item.id,
            'item_name': item.name,
            'sku': item.sku,
            'category_name': category.name,
            'warehouse_id': warehouse.id,
            'warehouse_name': warehouse.name,
            'quantity': inv.quantity,
            'reorder_level': item.reorder_level,
            'unit_of_measure': item.unit_of_measure,
            'cost': item.cost,
            'total_cost': item.cost * inv.quantity,
            'last_updated': inv.last_updated.strftime('%Y-%m-%d %H:%M') if inv.last_updated else 'N/A'
        })
    
    # Calculate totals
    total_items = len(inventory_data)
    total_quantity = sum(item['quantity'] for item in inventory_data)
    total_value = sum(item['total_cost'] for item in inventory_data)
    
    # Get filter names for the report title
    warehouse_name = "All Warehouses"
    category_name = "All Categories"
    item_name = "All Items"
    
    if warehouse_id:
        warehouse = Warehouse.query.get(warehouse_id)
        if warehouse:
            warehouse_name = warehouse.name
    
    if category_id:
        category = Category.query.get(category_id)
        if category:
            category_name = category.name
    
    if item_id:
        item = Item.query.get(item_id)
        if item:
            item_name = item.name
    
    # Prepare report context
    report_context = {
        'title': 'تقرير المخزون الكامل',
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'warehouse': warehouse_name,
        'category': category_name,
        'item': item_name,
        'include_zero_stock': include_zero_stock,
        'inventory_data': inventory_data,
        'total_items': total_items,
        'total_quantity': total_quantity,
        'total_value': total_value
    }
    
    # Generate report based on format
    if format_type == 'pdf':
        return generate_inventory_pdf(report_context, 'full_inventory')
    elif format_type == 'excel':
        return generate_inventory_excel(report_context, 'full_inventory')
    elif format_type == 'csv':
        return generate_inventory_csv(report_context, 'full_inventory')
    else:
        return jsonify({'message': 'Invalid format type'}), 400

def generate_low_stock_report(warehouse_id=None, category_id=None, format_type='pdf'):
    """Generate a report of items with stock below reorder level"""
    # Get all items
    query = db.session.query(
        Item, Category
    ).join(
        Category, Item.category_id == Category.id
    )
    
    # Apply category filter if provided
    if category_id:
        query = query.filter(Item.category_id == category_id)
    
    items = query.all()
    
    # Prepare low stock data
    low_stock_items = []
    
    for item, category in items:
        # Calculate total quantity across all warehouses or specific warehouse
        if warehouse_id:
            total_quantity = db.session.query(db.func.sum(Inventory.quantity))\
                .filter(Inventory.item_id == item.id, Inventory.warehouse_id == warehouse_id).scalar() or 0
        else:
            total_quantity = db.session.query(db.func.sum(Inventory.quantity))\
                .filter(Inventory.item_id == item.id).scalar() or 0
        
        # Check if below reorder level
        if total_quantity <= item.reorder_level:
            # Get supplier information
            suppliers = db.session.query(Supplier, SupplierItem)\
                .join(SupplierItem, Supplier.id == SupplierItem.supplier_id)\
                .filter(SupplierItem.item_id == item.id)\
                .all()
            
            supplier_info = []
            for supplier, supplier_item in suppliers:
                supplier_info.append({
                    'supplier_id': supplier.id,
                    'supplier_name': supplier.supplier_name,
                    'cost': supplier_item.cost
                })
            
            low_stock_items.append({
                'item_id': item.id,
                'item_name': item.name,
                'sku': item.sku,
                'category_name': category.name,
                'current_quantity': total_quantity,
                'reorder_level': item.reorder_level,
                'unit_of_measure': item.unit_of_measure,
                'suppliers': supplier_info
            })
    
    # Get filter names
    warehouse_name = "All Warehouses"
    category_name = "All Categories"
    
    if warehouse_id:
        warehouse = Warehouse.query.get(warehouse_id)
        if warehouse:
            warehouse_name = warehouse.name
    
    if category_id:
        category = Category.query.get(category_id)
        if category:
            category_name = category.name
    
    # Prepare report context
    report_context = {
        'title': 'تقرير العناصر منخفضة المخزون',
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'warehouse': warehouse_name,
        'category': category_name,
        'low_stock_items': low_stock_items,
        'total_items': len(low_stock_items)
    }
    
    # Generate report based on format
    if format_type == 'pdf':
        return generate_inventory_pdf(report_context, 'low_stock')
    elif format_type == 'excel':
        return generate_inventory_excel(report_context, 'low_stock')
    elif format_type == 'csv':
        return generate_inventory_csv(report_context, 'low_stock')
    else:
        return jsonify({'message': 'Invalid format type'}), 400

def generate_transactions_report(from_date=None, to_date=None, warehouse_id=None, item_id=None, format_type='pdf'):
    """Generate a report of inventory transactions with optional filtering"""
    # Base query for transactions
    query = db.session.query(
        InventoryTransaction, Item, Warehouse
    ).join(
        Item, InventoryTransaction.item_id == Item.id
    ).join(
        Warehouse, InventoryTransaction.warehouse_id == Warehouse.id
    )
    
    # Apply filters
    if from_date:
        query = query.filter(InventoryTransaction.transaction_date >= from_date)
    
    if to_date:
        # Add one day to include the end date fully
        to_date = to_date.replace(hour=23, minute=59, second=59)
        query = query.filter(InventoryTransaction.transaction_date <= to_date)
    
    if warehouse_id:
        query = query.filter(InventoryTransaction.warehouse_id == warehouse_id)
    
    if item_id:
        query = query.filter(InventoryTransaction.item_id == item_id)
    
    # Order by date (newest first)
    query = query.order_by(InventoryTransaction.transaction_date.desc())
    
    # Execute query
    results = query.all()
    
    # Prepare data for the report
    transactions_data = []
    for txn, item, warehouse in results:
        transactions_data.append({
            'transaction_id': txn.id,
            'item_id': item.id,
            'item_name': item.name,
            'sku': item.sku,
            'warehouse_id': warehouse.id,
            'warehouse_name': warehouse.name,
            'transaction_type': txn.transaction_type,
            'quantity': txn.quantity,
            'transaction_date': txn.transaction_date.strftime('%Y-%m-%d %H:%M'),
            'reference': txn.reference or 'N/A'
        })
    
    # Get filter names
    warehouse_name = "All Warehouses"
    item_name = "All Items"
    
    if warehouse_id:
        warehouse = Warehouse.query.get(warehouse_id)
        if warehouse:
            warehouse_name = warehouse.name
    
    if item_id:
        item = Item.query.get(item_id)
        if item:
            item_name = item.name
    
    # Format date range for display
    date_range = "All Time"
    if from_date and to_date:
        date_range = f"{from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}"
    elif from_date:
        date_range = f"From {from_date.strftime('%Y-%m-%d')}"
    elif to_date:
        date_range = f"Until {to_date.strftime('%Y-%m-%d')}"
    
    # Prepare report context
    report_context = {
                'title': 'تقرير حركات المخزون',
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'warehouse': warehouse_name,
        'item': item_name,
        'date_range': date_range,
        'transactions_data': transactions_data,
        'total_transactions': len(transactions_data)
    }
    
    # Generate report based on format
    if format_type == 'pdf':
        return generate_inventory_pdf(report_context, 'transactions')
    elif format_type == 'excel':
        return generate_inventory_excel(report_context, 'transactions')
    elif format_type == 'csv':
        return generate_inventory_csv(report_context, 'transactions')
    else:
        return jsonify({'message': 'Invalid format type'}), 400

def generate_item_transactions_report(item_id, from_date=None, to_date=None, warehouse_id=None, format_type='pdf'):
    """Generate a detailed transaction history report for a specific item"""
    # Get the item
    item = Item.query.get_or_404(item_id)
    
    # Base query for transactions
    query = db.session.query(
        InventoryTransaction, Warehouse
    ).join(
        Warehouse, InventoryTransaction.warehouse_id == Warehouse.id
    ).filter(
        InventoryTransaction.item_id == item_id
    )
    
    # Apply filters
    if from_date:
        query = query.filter(InventoryTransaction.transaction_date >= from_date)
    
    if to_date:
        # Add one day to include the end date fully
        to_date = to_date.replace(hour=23, minute=59, second=59)
        query = query.filter(InventoryTransaction.transaction_date <= to_date)
    
    if warehouse_id:
        query = query.filter(InventoryTransaction.warehouse_id == warehouse_id)
    
    # Order by date (oldest first to show the progression)
    query = query.order_by(InventoryTransaction.transaction_date.asc())
    
    # Execute query
    results = query.all()
    
    # Prepare data for the report
    transactions_data = []
    running_balance = 0
    
    for txn, warehouse in results:
        # Update running balance
        if txn.transaction_type == 'IN':
            running_balance += txn.quantity
        elif txn.transaction_type == 'OUT':
            running_balance -= txn.quantity
        
        transactions_data.append({
            'transaction_id': txn.id,
            'warehouse_name': warehouse.name,
            'transaction_type': txn.transaction_type,
            'quantity': txn.quantity,
            'transaction_date': txn.transaction_date.strftime('%Y-%m-%d %H:%M'),
            'reference': txn.reference or 'N/A',
            'running_balance': running_balance
        })
    
    # Get current inventory levels across all warehouses
    current_inventory = db.session.query(
        Warehouse.name, Inventory.quantity
    ).join(
        Inventory, Warehouse.id == Inventory.warehouse_id
    ).filter(
        Inventory.item_id == item_id
    ).all()
    
    inventory_by_warehouse = [
        {'warehouse_name': name, 'quantity': qty}
        for name, qty in current_inventory
    ]
    
    # Get category information
    category = Category.query.get(item.category_id) if item.category_id else None
    
    # Format date range for display
    date_range = "All Time"
    if from_date and to_date:
        date_range = f"{from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}"
    elif from_date:
        date_range = f"From {from_date.strftime('%Y-%m-%d')}"
    elif to_date:
        date_range = f"Until {to_date.strftime('%Y-%m-%d')}"
    
    # Prepare report context
    report_context = {
        'title': f'تقرير حركات المخزون للعنصر: {item.name}',
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'item': {
            'id': item.id,
            'name': item.name,
            'sku': item.sku,
            'category': category.name if category else 'Uncategorized',
            'unit_of_measure': item.unit_of_measure,
            'reorder_level': item.reorder_level,
            'cost': item.cost,
            'price': item.price
        },
        'date_range': date_range,
        'transactions_data': transactions_data,
        'total_transactions': len(transactions_data),
        'current_inventory': inventory_by_warehouse,
        'total_quantity': sum(inv['quantity'] for inv in inventory_by_warehouse)
    }
    
    # Generate report based on format
    if format_type == 'pdf':
        return generate_inventory_pdf(report_context, 'item_transactions')
    elif format_type == 'excel':
        return generate_inventory_excel(report_context, 'item_transactions')
    elif format_type == 'csv':
        return generate_inventory_csv(report_context, 'item_transactions')
    else:
        return jsonify({'message': 'Invalid format type'}), 400

def generate_warehouse_inventory_report(warehouse_id, category_id=None, include_zero_stock=False, format_type='pdf'):
    """Generate a detailed inventory report for a specific warehouse"""
    # Get the warehouse
    warehouse = Warehouse.query.get_or_404(warehouse_id)
    
    # Base query for inventory in this warehouse
    query = db.session.query(
        Inventory, Item, Category
    ).join(
        Item, Inventory.item_id == Item.id
    ).join(
        Category, Item.category_id == Category.id
    ).filter(
        Inventory.warehouse_id == warehouse_id
    )
    
    # Apply category filter if provided
    if category_id:
        query = query.filter(Item.category_id == category_id)
    
    # Filter out zero stock items if requested
    if not include_zero_stock:
        query = query.filter(Inventory.quantity > 0)
    
    # Execute query
    results = query.all()
    
    # Prepare data for the report
    inventory_data = []
    for inv, item, category in results:
        inventory_data.append({
            'item_id': item.id,
            'item_name': item.name,
            'sku': item.sku,
            'category_name': category.name,
            'quantity': inv.quantity,
            'reorder_level': item.reorder_level,
            'unit_of_measure': item.unit_of_measure,
            'cost': item.cost,
            'total_cost': item.cost * inv.quantity,
            'last_updated': inv.last_updated.strftime('%Y-%m-%d %H:%M') if inv.last_updated else 'N/A',
            'status': 'Low Stock' if inv.quantity <= item.reorder_level else 'In Stock'
        })
    
    # Group by category for summary
    categories = {}
    for item in inventory_data:
        category = item['category_name']
        if category not in categories:
            categories[category] = {
                'name': category,
                'item_count': 0,
                'total_quantity': 0,
                'total_value': 0
            }
        
        categories[category]['item_count'] += 1
        categories[category]['total_quantity'] += item['quantity']
        categories[category]['total_value'] += item['total_cost']
    
    category_summary = list(categories.values())
    
    # Calculate totals
    total_items = len(inventory_data)
    total_quantity = sum(item['quantity'] for item in inventory_data)
    total_value = sum(item['total_cost'] for item in inventory_data)
    low_stock_count = sum(1 for item in inventory_data if item['status'] == 'Low Stock')
    
    # Get category name if filter applied
    category_name = "All Categories"
    if category_id:
        category = Category.query.get(category_id)
        if category:
            category_name = category.name
    
    # Prepare report context
    report_context = {
        'title': f'تقرير مخزون المستودع: {warehouse.name}',
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'warehouse': {
            'id': warehouse.id,
            'name': warehouse.name,
            'location': warehouse.location,
            'capacity': warehouse.capacity,
            'contact_info': warehouse.contact_info
        },
        'category': category_name,
        'include_zero_stock': include_zero_stock,
        'inventory_data': inventory_data,
        'category_summary': category_summary,
        'total_items': total_items,
        'total_quantity': total_quantity,
        'total_value': total_value,
        'low_stock_count': low_stock_count
    }
    
    # Generate report based on format
    if format_type == 'pdf':
        return generate_inventory_pdf(report_context, 'warehouse_inventory')
    elif format_type == 'excel':
        return generate_inventory_excel(report_context, 'warehouse_inventory')
    elif format_type == 'csv':
        return generate_inventory_csv(report_context, 'warehouse_inventory')
    else:
        return jsonify({'message': 'Invalid format type'}), 400

def generate_category_inventory_report(category_id, warehouse_id=None, include_zero_stock=False, format_type='pdf'):
    """Generate a detailed inventory report for a specific category"""
    # Get the category
    category = Category.query.get_or_404(category_id)
    
    # Base query for inventory in this category
    query = db.session.query(
        Inventory, Item, Warehouse
    ).join(
        Item, Inventory.item_id == Item.id
    ).join(
        Warehouse, Inventory.warehouse_id == Warehouse.id
    ).filter(
        Item.category_id == category_id
    )
    
    # Apply warehouse filter if provided
    if warehouse_id:
        query = query.filter(Inventory.warehouse_id == warehouse_id)
    
    # Filter out zero stock items if requested
    if not include_zero_stock:
        query = query.filter(Inventory.quantity > 0)
    
    # Execute query
    results = query.all()
    
    # Prepare data for the report
    inventory_data = []
    for inv, item, warehouse in results:
        inventory_data.append({
            'item_id': item.id,
            'item_name': item.name,
            'sku': item.sku,
            'warehouse_name': warehouse.name,
            'quantity': inv.quantity,
            'reorder_level': item.reorder_level,
            'unit_of_measure': item.unit_of_measure,
            'cost': item.cost,
            'total_cost': item.cost * inv.quantity,
            'last_updated': inv.last_updated.strftime('%Y-%m-%d %H:%M') if inv.last_updated else 'N/A',
            'status': 'Low Stock' if inv.quantity <= item.reorder_level else 'In Stock'
        })
    
    # Group by warehouse for summary
    warehouses = {}
    for item in inventory_data:
        wh_name = item['warehouse_name']
        if wh_name not in warehouses:
            warehouses[wh_name] = {
                'name': wh_name,
                'item_count': 0,
                'total_quantity': 0,
                'total_value': 0
            }
        
        warehouses[wh_name]['item_count'] += 1
        warehouses[wh_name]['total_quantity'] += item['quantity']
        warehouses[wh_name]['total_value'] += item['total_cost']
    
    warehouse_summary = list(warehouses.values())
    
    # Calculate totals
    total_items = len(inventory_data)
    total_quantity = sum(item['quantity'] for item in inventory_data)
    total_value = sum(item['total_cost'] for item in inventory_data)
    low_stock_count = sum(1 for item in inventory_data if item['status'] == 'Low Stock')
    
    # Get warehouse name if filter applied
    warehouse_name = "All Warehouses"
    if warehouse_id:
        warehouse = Warehouse.query.get(warehouse_id)
        if warehouse:
            warehouse_name = warehouse.name
    
    # Prepare report context
    report_context = {
        'title': f'تقرير مخزون الفئة: {category.name}',
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'category': {
            'id': category.id,
            'name': category.name,
            'description': category.description
        },
        'warehouse': warehouse_name,
        'include_zero_stock': include_zero_stock,
        'inventory_data': inventory_data,
        'warehouse_summary': warehouse_summary,
        'total_items': total_items,
        'total_quantity': total_quantity,
        'total_value': total_value,
        'low_stock_count': low_stock_count
    }
    
    # Generate report based on format
    if format_type == 'pdf':
        return generate_inventory_pdf(report_context, 'category_inventory')
    elif format_type == 'excel':
        return generate_inventory_excel(report_context, 'category_inventory')
    elif format_type == 'csv':
        return generate_inventory_csv(report_context, 'category_inventory')
    else:
        return jsonify({'message': 'Invalid format type'}), 400

def generate_inventory_pdf(report_context, report_type):
    """Generate a PDF report for inventory data"""
    # Select the appropriate template based on report type
    template_name = f'reports/{report_type}_report.html'
    
    # Render the HTML template with the report context
    html_content = render_template(template_name, report=report_context)
    
    # Generate the PDF
    try:
        pdf_path = generate_pdf(html_content)
        
        # Generate a meaningful filename
        filename = f"{report_type}_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        # Send the PDF file
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
    except Exception as e:
        return jsonify({'message': f'Error generating PDF: {str(e)}'}), 500

def generate_inventory_excel(report_context, report_type):
    """Generate an Excel report for inventory data"""
    import pandas as pd
    from io import BytesIO
    
    # Create a BytesIO object to store the Excel file
    output = BytesIO()
    
    # Create Excel writer
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # Create different sheets based on report type
        if report_type == 'full_inventory':
            # Main inventory data
            df = pd.DataFrame(report_context['inventory_data'])
            df.to_excel(writer, sheet_name='Inventory', index=False)
            
            # Add summary sheet
            summary_data = {
                'Metric': ['Total Items', 'Total Quantity', 'Total Value'],
                'Value': [
                    report_context['total_items'],
                    report_context['total_quantity'],
                    report_context['total_value']
                ]
            }
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
        elif report_type == 'low_stock':
            # Low stock items
            df = pd.DataFrame(report_context['low_stock_items'])
            df.to_excel(writer, sheet_name='Low Stock Items', index=False)
            
            # Format the suppliers column if it exists
            if 'suppliers' in df.columns:
                # Create a new sheet for supplier details
                supplier_data = []
                for item in report_context['low_stock_items']:
                    for supplier in item.get('suppliers', []):
                        supplier_data.append({
                            'item_id': item['item_id'],
                            'item_name': item['item_name'],
                            'supplier_id': supplier['supplier_id'],
                            'supplier_name': supplier['supplier_name'],
                            'cost': supplier['cost']
                        })
                
                if supplier_data:
                    supplier_df = pd.DataFrame(supplier_data)
                    supplier_df.to_excel(writer, sheet_name='Supplier Details', index=False)
            
        elif report_type == 'transactions':
            # Transaction data
            df = pd.DataFrame(report_context['transactions_data'])
            df.to_excel(writer, sheet_name='Transactions', index=False)
            
        elif report_type == 'item_transactions':
            # Item details
            item_data = {
                'Property': [
                    'Item ID', 'Name', 'SKU', 'Category', 
                    'Unit of Measure', 'Reorder Level', 'Cost', 'Price'
                ],
                'Value': [
                    report_context['item']['id'],
                    report_context['item']['name'],
                    report_context['item']['sku'],
                    report_context['item']['category'],
                    report_context['item']['unit_of_measure'],
                    report_context['item']['reorder_level'],
                    report_context['item']['cost'],
                    report_context['item']['price']
                ]
            }
            item_df = pd.DataFrame(item_data)
            item_df.to_excel(writer, sheet_name='Item Details', index=False)
            
            # Transaction history
            transactions_df = pd.DataFrame(report_context['transactions_data'])
            transactions_df.to_excel(writer, sheet_name='Transaction History', index=False)
            
            # Current inventory
            inventory_df = pd.DataFrame(report_context['current_inventory'])
            inventory_df.to_excel(writer, sheet_name='Current Inventory', index=False)
            
        elif report_type == 'warehouse_inventory':
            # Warehouse details
            warehouse_data = {
                'Property': ['Warehouse ID', 'Name', 'Location', 'Capacity', 'Contact Info'],
                'Value': [
                    report_context['warehouse']['id'],
                    report_context['warehouse']['name'],
                    report_context['warehouse']['location'],
                    report_context['warehouse']['capacity'],
                    report_context['warehouse']['contact_info']
                ]
            }
            warehouse_df = pd.DataFrame(warehouse_data)
            warehouse_df.to_excel(writer, sheet_name='Warehouse Details', index=False)
            
            # Inventory data
            inventory_df = pd.DataFrame(report_context['inventory_data'])
            inventory_df.to_excel(writer, sheet_name='Inventory', index=False)
            
            # Category summary
            category_df = pd.DataFrame(report_context['category_summary'])
            category_df.to_excel(writer, sheet_name='Category Summary', index=False)
            
        elif report_type == 'category_inventory':
            # Category details
            category_data = {
                'Property': ['Category ID', 'Name', 'Description'],
                'Value': [
                    report_context['category']['id'],
                    report_context['category']['name'],
                    report_context['category']['description']
                ]
            }
            category_df = pd.DataFrame(category_data)
            category_df.to_excel(writer, sheet_name='Category Details', index=False)
            
            # Inventory data
            inventory_df = pd.DataFrame(report_context['inventory_data'])
            inventory_df.to_excel(writer, sheet_name='Inventory', index=False)
            
            # Warehouse summary
            warehouse_df = pd.DataFrame(report_context['warehouse_summary'])
            warehouse_df.to_excel(writer, sheet_name='Warehouse Summary', index=False)
        
        # Add report metadata
        metadata = {
            'Property': ['Report Type', 'Generated At', 'Total Items'],
            'Value': [
                report_context['title'],
                report_context['generated_at'],
                report_context.get('total_items', 0)
            ]
        }
        metadata_df = pd.DataFrame(metadata)
        metadata_df.to_excel(writer, sheet_name='Metadata', index=False)
        
        # Format the workbook
        workbook = writer.book
        
        # Add a format for headers
        header_format = workbook.add_format({
            'bold': True,
            'text_wrap': True,
            'valign': 'top',
            'fg_color': '#D7E4BC',
            'border': 1
        })
        
        # Apply the header format to all sheets
        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]
            # Get the column headers from the dataframe
            for col_num, value in enumerate(pd.DataFrame(metadata_df if sheet_name == 'Metadata' else 
                                           df if sheet_name == 'Inventory' or sheet_name == 'Low Stock Items' or sheet_name == 'Transactions' else 
                                           summary_df if sheet_name == 'Summary' else 
                                           item_df if sheet_name == 'Item Details' else 
                                           transactions_df if sheet_name == 'Transaction History' else 
                                           inventory_df if sheet_name == 'Current Inventory' else 
                                           warehouse_df if sheet_name == 'Warehouse Details' else 
                                           category_df if sheet_name == 'Category Details' else 
                                           supplier_df if sheet_name == 'Supplier Details' else pd.DataFrame()).columns):
                worksheet.write(0, col_num, value, header_format)
                worksheet.set_column(col_num, col_num, 15)  # Set column width
    
    # Seek to the beginning of the BytesIO object
    output.seek(0)
    
    # Generate a meaningful filename
    filename = f"{report_type}_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    # Send the Excel file
    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

def generate_inventory_csv(report_context, report_type):
    """Generate a CSV report for inventory data"""
    import pandas as pd
    from io import StringIO
    
    # Create a StringIO object to store the CSV data
    output = StringIO()
    
    # Create different CSV content based on report type
    if report_type == 'full_inventory':
        df = pd.DataFrame(report_context['inventory_data'])
        df.to_csv(output, index=False)
        
    elif report_type == 'low_stock':
        # For low stock, we need to flatten the suppliers data
        data = []
        for item in report_context['low_stock_items']:
            item_data = item.copy()
            # Remove the suppliers list and add a supplier count
            suppliers = item_data.pop('suppliers', [])
            item_data['supplier_count'] = len(suppliers)
            data.append(item_data)
        
        df = pd.DataFrame(data)
        df.to_csv(output, index=False)
        
    elif report_type == 'transactions':
        df = pd.DataFrame(report_context['transactions_data'])
        df.to_csv(output, index=False)
        
    elif report_type == 'item_transactions':
        # For item transactions, we'll just export the transaction history
        df = pd.DataFrame(report_context['transactions_data'])
        df.to_csv(output, index=False)
        
    elif report_type == 'warehouse_inventory':
        df = pd.DataFrame(report_context['inventory_data'])
        df.to_csv(output, index=False)
        
    elif report_type == 'category_inventory':
        df = pd.DataFrame(report_context['inventory_data'])
        df.to_csv(output, index=False)
    
    # Seek to the beginning of the StringIO object
    output.seek(0)
    
    # Generate a meaningful filename
    filename = f"{report_type}_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    # Create a response with the CSV data
    return send_file(
        BytesIO(output.getvalue().encode('utf-8')),
        as_attachment=True,
        download_name=filename,
        mimetype='text/csv'
    )




# # # # # # # # # # # # # # # # # # # # # # 
# # # # # # # # # # # # # # # # # # # # # # 
# # # # # # # # # # # # # # # # # # # # # # 
# # # # # # # # # # # # # # # # # # # # # # 
# # # # # # # # # # # # # # # # # # # # # # 
# # # # # # # # # # # # # # # # # # # # # # 
# # # # # # # # # # # # # # # # # # # # # # 
# # # # # # # # # # # # # # # # # # # # # # 
# # # # # # # # # # # # # # # # # # # # # # 
# # # # # # # # # # # # # # # # # # # # # # 
# # # # # # # # # # # # # # # # # # # # # # 
# # # # # # # # # # # # # # # # # # # # # # 
# # # # # # # # # # # # # # # # # # # # # # 
# # # # # # # # # # # # # # # # # # # # # # 
# # # # # # # # # # # # # # # # # # # # # # 
# # # # # # # # # # # # # # # # # # # # # # 

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/register')
@login_required

def register_page():
    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/inventory-management')
@login_required
def inventory_page():
    return render_template('inventory.html')





@app.route('/categories-management')
@login_required
def categories_page():
    return render_template('categories.html')

@app.route('/items-management')
@login_required
def items_page():
    return render_template('items.html')

@app.route('/transactions-history')
@login_required
def transactions_page():
    return render_template('transactions.html')

@app.route('/tips')
@login_required
def tips_page():
    return render_template('tips.html')

@app.route('/chat-assistant')
@login_required
def chat_assistant():
    return render_template('chat.html')





@app.route('/admin/users')
@login_required
def admin_users_page():
    if not current_user.role or current_user.role.name != 'admin':
        return redirect('/dashboard')
    return render_template('admin_users.html')

@app.route('/admin/roles')
@login_required
def admin_roles_page():
    if not current_user.role or current_user.role.name != 'admin':
        return redirect('/dashboard')
    return render_template('admin_roles.html')


# @app.route('/check-schema')
# def check_schema():
#     from sqlalchemy import inspect
#     inspector = inspect(db.engine)
#     columns = inspector.get_columns('categories')
#     return jsonify([col['name'] for col in columns])


def check_internet():
    # ... (keep existing function) ...
    try:
        urllib.request.urlopen('http://google.com', timeout=1)
        return True
    except:
        return False



@app.route('/api/reports/inventory/full_inventory')
@login_required
def api_full_inventory_report():
    warehouse_id = request.args.get('warehouse_id', type=int)
    category_id = request.args.get('category_id', type=int)
    item_id = request.args.get('item_id', type=int)
    include_zero_stock = request.args.get('include_zero_stock', 'false').lower() == 'true'
    format_type = request.args.get('format', 'pdf')
    
    return generate_full_inventory_report(
        warehouse_id=warehouse_id,
        category_id=category_id,
        item_id=item_id,
        include_zero_stock=include_zero_stock,
        format_type=format_type
    )

@app.route('/api/reports/inventory/low_stock')
@login_required
def api_low_stock_report():
    warehouse_id = request.args.get('warehouse_id', type=int)
    category_id = request.args.get('category_id', type=int)
    format_type = request.args.get('format', 'pdf')
    
    return generate_low_stock_report(
        warehouse_id=warehouse_id,
        category_id=category_id,
        format_type=format_type
    )

@app.route('/api/reports/inventory/transactions')
@login_required
def api_transactions_report():
    warehouse_id = request.args.get('warehouse_id', type=int)
    item_id = request.args.get('item_id', type=int)
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    format_type = request.args.get('format', 'pdf')
    
    # Convert date strings to datetime objects
    from_date = datetime.strptime(date_from, '%Y-%m-%d') if date_from else None
    to_date = datetime.strptime(date_to, '%Y-%m-%d') if date_to else None
    
    return generate_transactions_report(
        warehouse_id=warehouse_id,
        item_id=item_id,
        from_date=from_date,
        to_date=to_date,
        format_type=format_type
    )

@app.route('/api/reports/inventory/item_transactions')
@login_required
def api_item_transactions_report():
    item_id = request.args.get('item_id', type=int)
    warehouse_id = request.args.get('warehouse_id', type=int)
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    format_type = request.args.get('format', 'pdf')
    
    if not item_id:
        return jsonify({'message': 'Item ID is required'}), 400
    
    # Convert date strings to datetime objects
    from_date = datetime.strptime(date_from, '%Y-%m-%d') if date_from else None
    to_date = datetime.strptime(date_to, '%Y-%m-%d') if date_to else None
    
    return generate_item_transactions_report(
        item_id=item_id,
        warehouse_id=warehouse_id,
        from_date=from_date,
        to_date=to_date,
        format_type=format_type
    )

@app.route('/api/reports/inventory/warehouse_inventory')
@login_required
def api_warehouse_inventory_report():
    warehouse_id = request.args.get('warehouse_id', type=int)
    category_id = request.args.get('category_id', type=int)
    include_zero_stock = request.args.get('include_zero_stock', 'false').lower() == 'true'
    format_type = request.args.get('format', 'pdf')
    
    if not warehouse_id:
        return jsonify({'message': 'Warehouse ID is required'}), 400
    
    return generate_warehouse_inventory_report(
        warehouse_id=warehouse_id,
        category_id=category_id,
        include_zero_stock=include_zero_stock,
        format_type=format_type
    )

@app.route('/api/reports/inventory/category_inventory')
@login_required
def api_category_inventory_report():
    category_id = request.args.get('category_id', type=int)
    warehouse_id = request.args.get('warehouse_id', type=int)
    include_zero_stock = request.args.get('include_zero_stock', 'false').lower() == 'true'
    format_type = request.args.get('format', 'pdf')
    
    if not category_id:
        return jsonify({'message': 'Category ID is required'}), 400
    
    return generate_category_inventory_report(
        category_id=category_id,
        warehouse_id=warehouse_id,
        include_zero_stock=include_zero_stock,
        format_type=format_type
    )

if __name__ == '__main__':
    # --- Check for Gemini API Key before starting ---
    if not os.getenv("GEMINI_API_KEY"):
        print("\n" + "="*50)
        print(" FATAL ERROR: Gemini API Key not found! ")
        print(" Please set the GEMINI_API_KEY in your .env file.")
        print(" Chatbot functionality will NOT work.")
        print("="*50 + "\n")
        # Decide if you want to exit or just warn
        # exit(1) # Uncomment to force exit if key is missing

    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)

    if check_internet():
        print("Internet connection successful")
    else:
        print("No internet connection (required for Gemini)") # Warn about Gemini

    port = 5000
    url = f"http://{local_ip}:{port}"
    print(f" * Katilo System running on {url}")
    # webbrowser.open(url) # Keep or remove auto-open as preferred
    app.run(host='0.0.0.0', port=port, debug=True)