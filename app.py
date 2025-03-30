from flask import Flask, request, jsonify, session, redirect, render_template
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from support_routes import support_bp
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
    Supplier, SupplierItem,
    
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
    
    # Advanced Features
    DemandForecast, InventoryReplenishmentPlan,
    EmployeeShift, ProductionEfficiency,
    CustomerInteraction, DiscountPromotion,
    ProductReturn,
    db
)

# Initialize Flask app
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///katilo.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key'
db.init_app(app)  # Connect SQLAlchemy to this Flask app
login_manager = LoginManager()
login_manager.init_app(app)
# Configure upload folder for attachments (needed for support file uploads)
UPLOAD_FOLDER = 'static/uploads/support'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# Ensure upload directory exists
import os
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
app.register_blueprint(support_bp)


# Create database tables
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


@app.route('/api/auth/profile')
@login_required
def get_profile():
    return jsonify({
        'id': current_user.id,
        'username': current_user.username,
        'email': current_user.email,
        'role': current_user.role.name if current_user.role else 'user',
        'phone': current_user.phone,
        'department': current_user.department,
        'position': current_user.position
    })

@app.route('/api/auth/profile', methods=['PUT'])
@login_required
def update_profile():
    data = request.get_json()
    
    # Update user fields
    if 'phone' in data:
        current_user.phone = data['phone']
    if 'department' in data:
        current_user.department = data['department']
    if 'position' in data:
        current_user.position = data['position']
    
    # Handle password change if provided
    if 'password' in data and data['password']:
        current_user.set_password(data['password'])
    
    db.session.commit()
    
    return jsonify({
        'id': current_user.id,
        'username': current_user.username,
        'email': current_user.email,
        'role': current_user.role.name if current_user.role else 'user',
        'phone': current_user.phone,
        'department': current_user.department,
        'position': current_user.position
    })


# Role Management Routes
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
    return jsonify([{'id': c.id, 'name': c.name, 'description': c.description} for c in categories])

@app.route('/api/categories', methods=['POST'])
@login_required
def create_category():
    data = request.get_json()
    category = Category(name=data['name'], description=data.get('description'))
    db.session.add(category)
    db.session.commit()
    return jsonify({'id': category.id, 'name': category.name, 'description': category.description}), 201

@app.route('/api/categories/<int:id>', methods=['PUT'])
@login_required
def update_category(id):
    category = Category.query.get_or_404(id)
    data = request.get_json()
    category.name = data.get('name', category.name)
    category.description = data.get('description', category.description)
    db.session.commit()
    return jsonify({'id': category.id, 'name': category.name, 'description': category.description})

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

# Warehouse Routes
@app.route('/api/warehouses', methods=['GET'])
@login_required
def get_warehouses():
    warehouses = Warehouse.query.all()
    return jsonify([{
        'id': w.id,
        'name': w.name,
        'location': w.location,
        'capacity': w.capacity,
        'contact_info': w.contact_info
    } for w in warehouses])

@app.route('/api/warehouses', methods=['POST'])
@login_required
def create_warehouse():
    data = request.get_json()
    warehouse = Warehouse(
        name=data['name'],
        location=data['location'],
        capacity=data['capacity'],
        contact_info=data.get('contact_info')
    )
    db.session.add(warehouse)
    db.session.commit()
    return jsonify({'id': warehouse.id, 'name': warehouse.name}), 201

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
@app.route('/api/warehouse-sections', methods=['GET'])
@login_required
def get_warehouse_sections():
    sections = WarehouseSection.query.all()
    return jsonify([{
        'id': s.id,
        'warehouse_id': s.warehouse_id,
        'section_name': s.section_name,
        'row_count': s.row_count,
        'column_count': s.column_count
    } for s in sections])

@app.route('/api/warehouse-sections', methods=['POST'])
@login_required
def create_warehouse_section():
    data = request.get_json()
    section = WarehouseSection(
        warehouse_id=data['warehouse_id'],
        section_name=data['section_name'],
        row_count=data.get('row_count', 10),
        column_count=data.get('column_count', 10)
    )
    db.session.add(section)
    db.session.commit()
    return jsonify({
        'id': section.id,
        'section_name': section.section_name,
        'warehouse_id': section.warehouse_id
    }), 201

@app.route('/api/warehouse-sections/<int:id>', methods=['PUT'])
@login_required
def update_warehouse_section(id):
    section = WarehouseSection.query.get_or_404(id)
    data = request.get_json()
    for key, value in data.items():
        if hasattr(section, key):
            setattr(section, key, value)
    db.session.commit()
    return jsonify({
        'id': section.id,
        'section_name': section.section_name,
        'row_count': section.row_count,
        'column_count': section.column_count
    })

@app.route('/api/warehouse-sections/<int:id>', methods=['DELETE'])
@login_required
def delete_warehouse_section(id):
    section = WarehouseSection.query.get_or_404(id)
    db.session.delete(section)
    db.session.commit()
    return '', 204

# Warehouse Slot Routes
@app.route('/api/warehouse-slots', methods=['GET'])
@login_required
def get_warehouse_slots():
    slots = WarehouseSlot.query.all()
    return jsonify([{
        'id': s.id,
        'section_id': s.section_id,
        'row_number': s.row_number,
        'column_number': s.column_number,
        'item_id': s.item_id,
        'quantity': s.quantity
    } for s in slots])

@app.route('/api/warehouse-slots', methods=['POST'])
@login_required
def create_warehouse_slot():
    data = request.get_json()
    slot = WarehouseSlot(
        section_id=data['section_id'],
        row_number=data['row_number'],
        column_number=data['column_number'],
        item_id=data.get('item_id'),
        quantity=data.get('quantity', 0)
    )
    db.session.add(slot)
    db.session.commit()
    return jsonify({
        'id': slot.id,
        'section_id': slot.section_id,
        'row_number': slot.row_number,
        'column_number': slot.column_number
    }), 201

@app.route('/api/warehouse-slots/<int:id>', methods=['PUT'])
@login_required
def update_warehouse_slot(id):
    slot = WarehouseSlot.query.get_or_404(id)
    data = request.get_json()
    for key, value in data.items():
        if hasattr(slot, key):
            setattr(slot, key, value)
    db.session.commit()
    return jsonify({
        'id': slot.id,
        'section_id': slot.section_id,
        'item_id': slot.item_id,
        'quantity': slot.quantity
    })

@app.route('/api/warehouse-slots/<int:id>', methods=['DELETE'])
@login_required
def delete_warehouse_slot(id):
    slot = WarehouseSlot.query.get_or_404(id)
    db.session.delete(slot)
    db.session.commit()
    return '', 204

# Additional utility endpoints for warehouse layout management
@app.route('/api/warehouse-sections/<int:id>/slots', methods=['GET'])
@login_required
def get_section_slots(id):
    slots = WarehouseSlot.query.filter_by(section_id=id).all()
    return jsonify([{
        'id': s.id,
        'row_number': s.row_number,
        'column_number': s.column_number,
        'item_id': s.item_id,
        'quantity': s.quantity
    } for s in slots])

@app.route('/api/warehouses/<int:id>/sections', methods=['GET'])
@login_required
def get_warehouse_layout(id):
    sections = WarehouseSection.query.filter_by(warehouse_id=id).all()
    return jsonify([{
        'id': s.id,
        'section_name': s.section_name,
        'row_count': s.row_count,
        'column_count': s.column_count,
        'slots': [{
            'id': slot.id,
            'row_number': slot.row_number,
            'column_number': slot.column_number,
            'item_id': slot.item_id,
            'quantity': slot.quantity
        } for slot in s.slots]
    } for s in sections])

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

@app.route('/warehouse-layout')
@login_required
def warehouse_layout_page():
    return render_template('warehouse_layout.html')

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

@app.route('/user-profile')
@login_required
def profile_page():
    return render_template('profile.html')

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





if __name__ == '__main__':
    app.run(debug=True)
