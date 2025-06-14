from io import BytesIO
from filters import init_filters
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
from routes.production_routes import production_bp
from routes.production_reports import production_reports
from routes.sales_routes import sales_bp
from routes.chatbot_routes import chatbot_bp
from routes.sales_representative_routes import rep_routes_bp
from routes.cash_management_routes import cash_bp
from routes.inventory_routes import inventory_bp
from routes.distribution_routes import distribution_bp
from routes.ai_suggestions_routes import ai_suggestions_bp
from routes.settings_routes import settings_bp
from routes.alerts_routes import alerts_bp


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
    ProductionRun, ProductionRunDetail, ProductionOrder, ProductionLine,

    # Packaging
    ProductPackaging, PackagingMaterial,

    # Cash Management
    CashAccount, CashTransaction,

    # Distribution
    ShipmentOrder,

    # Advanced Features
    DemandForecast,
    InventoryReplenishmentPlan,
    EmployeeShift,
    ProductionEfficiency,
    CustomerInteraction,
    DiscountPromotion,
    SalesReturn,
    db
)

# Initialize Flask app
app = Flask(__name__)

# App configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:@localhost:5432/katiloerp'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-default-secret-key')
app.config['UPLOAD_FOLDER'] = 'static/uploads/support'
app.config['PROFILE_UPLOAD_FOLDER'] = 'static/uploads/profiles'
app.config['TEMP_FOLDER'] = os.path.join(tempfile.gettempdir(), 'katilo-temp')
app.config['GEMINI_API_KEY'] = os.getenv("GEMINI_API_KEY")
app.config['GOOGLE_MAPS_API_KEY'] = os.getenv("GOOGLE_MAPS_API_KEY", "AIzaSyAwlSE5qHU1tI8wNdwInTcSSzCSYYaa8yk")
# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)

# Ensure upload and temp directories exist
import os
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['PROFILE_UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['TEMP_FOLDER'], exist_ok=True)


# Register blueprints
app.register_blueprint(support_bp)
app.register_blueprint(bom_bp)
app.register_blueprint(supplier_bp)
app.register_blueprint(purchase_order_bp)
app.register_blueprint(supplier_accounts_bp)
app.register_blueprint(warehouse_bp)
app.register_blueprint(profile_bp)
app.register_blueprint(quality_bp)
app.register_blueprint(production_bp)
app.register_blueprint(chatbot_bp)
app.register_blueprint(sales_bp)  # Register the sales blueprint
app.register_blueprint(rep_routes_bp)
app.register_blueprint(production_reports)
app.register_blueprint(cash_bp)
app.register_blueprint(inventory_bp)  # Register the inventory blueprint
app.register_blueprint(distribution_bp)  # Register the distribution blueprint
app.register_blueprint(ai_suggestions_bp)  # Register the AI suggestions blueprint
app.register_blueprint(settings_bp)  # Register the settings blueprint
app.register_blueprint(alerts_bp)  # Register the alerts blueprint

# Global API routes
@app.route('/api/cash-accounts')
@login_required
def global_api_cash_accounts():
    """Global API endpoint to get all active cash accounts"""
    from models import CashAccount
    from flask import jsonify

    accounts = CashAccount.query.filter_by(is_active=True).all()

    accounts_data = []
    for account in accounts:
        accounts_data.append({
            'id': account.id,
            'name': account.name,
            'account_type': account.account_type,
            'currency': account.currency,
            'current_balance': account.current_balance,
            'is_active': account.is_active
        })

    return jsonify(accounts_data)


"""
Register the production_reports blueprint to the Flask application.

This blueprint likely handles routes and views related to generating and displaying
production-related reports within the application.
"""

init_filters(app)

# Create database tables

migrate = Migrate(app, db)

with app.app_context():
    db.create_all()



    default_permissions = [
        # User Management
        'view_users', 'create_users', 'edit_users', 'delete_users',
        'view_roles', 'create_roles', 'edit_roles', 'delete_roles',

        # Inventory Management
        'view_inventory', 'manage_inventory',
        'view_categories', 'manage_categories',
        'view_items', 'manage_items',
        'view_transactions', 'manage_transactions',

        # Warehouse Management
        'view_warehouses', 'manage_warehouses',
        'view_warehouse_layout', 'manage_warehouse_layout',

        # BOM Management
        'view_bom', 'create_bom', 'edit_bom', 'delete_bom',

        # Supplier Management
        'view_suppliers', 'create_suppliers', 'edit_suppliers', 'delete_suppliers',
        'view_supplier_items', 'manage_supplier_items',

        # Purchase Orders
        'view_purchase_orders', 'create_purchase_orders', 'edit_purchase_orders', 'delete_purchase_orders',

        # Quality Control
        'view_quality_inspections', 'create_quality_inspections', 'edit_quality_inspections',

        # Production Management
        'view_production_orders', 'create_production_orders', 'edit_production_orders',
        'view_production_steps', 'manage_production_steps',
        'view_batches', 'manage_batches',
        'view_production_reports', 'generate_production_reports',

        # Sales Management
        'view_sales_dashboard', 'view_sales_orders', 'create_sales_orders', 'edit_sales_orders',
        'view_customers', 'manage_customers',
        'view_invoices', 'create_invoices', 'manage_payments',

        # Sales Representatives
        'view_sales_representatives', 'manage_sales_representatives',
        'view_representative_routes', 'manage_representative_routes',

        # Distribution Management
        'view_distribution_dashboard', 'view_vehicles', 'manage_vehicles',
        'view_shipments', 'manage_shipments', 'view_delivery_routes', 'manage_delivery_routes',
        'track_shipments', 'confirm_deliveries',

        # Support System
        'view_support_tickets', 'create_support_tickets', 'respond_to_tickets', 'manage_all_tickets',

        # Profile Management
        'view_profile', 'edit_profile',

        # Chatbot Access
        'use_chatbot'
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

@app.route('/api/auth/check-permission', methods=['POST'])
@login_required
def check_permission():
    data = request.get_json()
    permission_name = data.get('permission')

    if not permission_name:
        return jsonify({'message': 'Permission name is required'}), 400

    # Admin role has all permissions
    if current_user.role and current_user.role.name == 'admin':
        return jsonify({
            'has_permission': True,
            'role': current_user.role.name
        })

    # Check specific permission
    has_permission = current_user.has_permission(permission_name)

    return jsonify({
        'has_permission': has_permission,
        'role': current_user.role.name if current_user.role else None,
        'permission': permission_name
    })



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

    # Define permission descriptions in Arabic
    permission_descriptions = {
        # User Management
        'view_users': 'عرض المستخدمين',
        'create_users': 'إنشاء مستخدمين جدد',
        'edit_users': 'تعديل بيانات المستخدمين',
        'delete_users': 'حذف المستخدمين',
        'view_roles': 'عرض الأدوار',
        'create_roles': 'إنشاء أدوار جديدة',
        'edit_roles': 'تعديل الأدوار',
        'delete_roles': 'حذف الأدوار',

        # Inventory Management
        'view_inventory': 'عرض المخزون',
        'manage_inventory': 'إدارة المخزون',
        'view_categories': 'عرض التصنيفات',
        'manage_categories': 'إدارة التصنيفات',
        'view_items': 'عرض العناصر',
        'manage_items': 'إدارة العناصر',
        'view_transactions': 'عرض المعاملات',
        'manage_transactions': 'إدارة المعاملات',

        # Warehouse Management
        'view_warehouses': 'عرض المستودعات',
        'manage_warehouses': 'إدارة المستودعات',
        'view_warehouse_layout': 'عرض تخطيط المستودع',
        'manage_warehouse_layout': 'إدارة تخطيط المستودع',

        # BOM Management
        'view_bom': 'عرض قوائم المواد',
        'create_bom': 'إنشاء قوائم مواد جديدة',
        'edit_bom': 'تعديل قوائم المواد',
        'delete_bom': 'حذف قوائم المواد',

        # Supplier Management
        'view_suppliers': 'عرض الموردين',
        'create_suppliers': 'إضافة موردين جدد',
        'edit_suppliers': 'تعديل بيانات الموردين',
        'delete_suppliers': 'حذف الموردين',
        'view_supplier_items': 'عرض عناصر الموردين',
        'manage_supplier_items': 'إدارة عناصر الموردين',

        # Purchase Orders
        'view_purchase_orders': 'عرض طلبات الشراء',
        'create_purchase_orders': 'إنشاء طلبات شراء جديدة',
        'edit_purchase_orders': 'تعديل طلبات الشراء',
        'delete_purchase_orders': 'حذف طلبات الشراء',

        # Quality Control
        'view_quality_inspections': 'عرض فحوصات الجودة',
        'create_quality_inspections': 'إنشاء فحوصات جودة جديدة',
        'edit_quality_inspections': 'تعديل فحوصات الجودة',

        # Production Management
        'view_production_orders': 'عرض أوامر الإنتاج',
        'create_production_orders': 'إنشاء أوامر إنتاج جديدة',
        'edit_production_orders': 'تعديل أوامر الإنتاج',
        'view_production_steps': 'عرض خطوات الإنتاج',
        'manage_production_steps': 'إدارة خطوات الإنتاج',
        'view_batches': 'عرض الدفعات',
        'manage_batches': 'إدارة الدفعات',
        'view_production_reports': 'عرض تقارير الإنتاج',
        'generate_production_reports': 'إنشاء تقارير الإنتاج',

        # Sales Management
        'view_sales_dashboard': 'عرض لوحة معلومات المبيعات',
        'view_sales_orders': 'عرض طلبات المبيعات',
        'create_sales_orders': 'إنشاء طلبات مبيعات جديدة',
        'edit_sales_orders': 'تعديل طلبات المبيعات',
        'view_customers': 'عرض العملاء',
        'manage_customers': 'إدارة العملاء',
        'view_invoices': 'عرض الفواتير',
        'create_invoices': 'إنشاء فواتير جديدة',
        'manage_payments': 'إدارة المدفوعات',

        # Sales Representatives
        'view_sales_representatives': 'عرض مندوبي المبيعات',
        'manage_sales_representatives': 'إدارة مندوبي المبيعات',
        'view_representative_routes': 'عرض مسارات المندوبين',
        'manage_representative_routes': 'إدارة مسارات المندوبين',

        # Distribution Management
        'view_distribution_dashboard': 'عرض لوحة التوزيع',
        'view_vehicles': 'عرض المركبات',
        'manage_vehicles': 'إدارة المركبات',
        'view_shipments': 'عرض الشحنات',
        'manage_shipments': 'إدارة الشحنات',
        'view_delivery_routes': 'عرض مسارات التوصيل',
        'manage_delivery_routes': 'إدارة مسارات التوصيل',
        'track_shipments': 'تتبع الشحنات',
        'confirm_deliveries': 'تأكيد عمليات التسليم',

        # Support System
        'view_support_tickets': 'عرض تذاكر الدعم',
        'create_support_tickets': 'إنشاء تذاكر دعم جديدة',
        'respond_to_tickets': 'الرد على تذاكر الدعم',
        'manage_all_tickets': 'إدارة جميع تذاكر الدعم',

        # Profile Management
        'view_profile': 'عرض الملف الشخصي',
        'edit_profile': 'تعديل الملف الشخصي',

        # Chatbot Access
        'use_chatbot': 'استخدام المساعد الذكي'
    }

    permissions = Permission.query.order_by(Permission.permission_name).all()
    return jsonify([{
        'id': p.id,
        'permission_name': p.permission_name,
        'description': permission_descriptions.get(p.permission_name, p.permission_name.replace('_', ' ').title())
    } for p in permissions])

# Add this to your app.py or wherever you define your template context processors
@app.context_processor
def inject_sidebar_menu():
    """Inject sidebar menu items into all templates"""
    if current_user.is_authenticated:
        try:
            from models_helper import SidebarItem
            menu_items = SidebarItem.get_main_menu(include_admin=current_user.role and current_user.role.name == 'admin')
            return {'sidebar_menu': menu_items}
        except:
            return {'sidebar_menu': []}
    return {'sidebar_menu': []}

@app.context_processor
def inject_alerts_count():
    """Inject unread alerts count into all templates"""
    if current_user.is_authenticated:
        try:
            from utils.alerts_manager import alerts_manager
            unread_count = alerts_manager.get_unread_count()
            return {'unread_alerts_count': unread_count}
        except:
            return {'unread_alerts_count': 0}
    return {'unread_alerts_count': 0}


@app.route('/api/roles/<int:role_id>/permissions', methods=['POST'])
@login_required
def assign_permission_to_role(role_id):
    if not current_user.role or current_user.role.name != 'admin':
        return jsonify({'message': 'Unauthorized'}), 403

    data = request.get_json()

    # Check if the role and permission exist
    role = Role.query.get_or_404(role_id)
    permission = Permission.query.get_or_404(data['permission_id'])

    # Check if the permission is already assigned to the role
    existing = RolePermission.query.filter_by(
        role_id=role_id,
        permission_id=data['permission_id']
    ).first()

    if existing:
        return jsonify({'message': 'Permission already assigned to this role'}), 400

    # Create new role permission
    role_permission = RolePermission(
        role_id=role_id,
        permission_id=data['permission_id']
    )
    db.session.add(role_permission)
    db.session.commit()

    return jsonify({
        'role_id': role_permission.role_id,
        'permission_id': role_permission.permission_id,
        'message': 'Permission assigned successfully'
    }), 201


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

    # Convert string 'true'/'false' to Python boolean
    is_active = data.get('is_active')
    if isinstance(is_active, str):
        is_active = is_active.lower() == 'true'
    else:
        is_active = bool(is_active) if is_active is not None else True

    # Create new user
    user = User(
        username=data['username'],
        email=data['email'],
        role_id=data.get('role_id'),
        is_active=is_active,
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
        # Convert string 'true'/'false' to Python boolean
        is_active = data['is_active']
        if isinstance(is_active, str):
            is_active = is_active.lower() == 'true'
        else:
            is_active = bool(is_active)
        user.is_active = is_active

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

    # Get all role permissions with role and permission details
    role_permissions = RolePermission.query.all()

    # Format the response
    result = []
    for rp in role_permissions:
        role = Role.query.get(rp.role_id)
        permission = Permission.query.get(rp.permission_id)

        if role and permission:
            result.append({
                'role_id': rp.role_id,
                'permission_id': rp.permission_id,
                'role_name': role.name,
                'permission_name': permission.permission_name
            })

    return jsonify(result)

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

    # Check if the role and permission exist
    role = Role.query.get_or_404(role_id)
    permission = Permission.query.get_or_404(permission_id)

    # Prevent removing permissions from admin role
    if role.name == 'admin':
        return jsonify({'message': 'لا يمكن إزالة الصلاحيات من دور المدير'}), 400

    # Find the role permission relationship
    role_permission = RolePermission.query.filter_by(
        role_id=role_id,
        permission_id=permission_id
    ).first_or_404()

    try:
        db.session.delete(role_permission)
        db.session.commit()

        return jsonify({
            'success': True,
            'role_id': role_id,
            'permission_id': permission_id,
            'message': 'تم إزالة الصلاحية بنجاح'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'حدث خطأ أثناء إزالة الصلاحية: {str(e)}'
        }), 500





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
@app.route('/api/products/<int:product_id>', methods=['GET'])
@login_required
def get_product_details(product_id):
    """API endpoint to get product details - redirects to production endpoint"""
    try:
        product = Item.query.get_or_404(product_id)
        category = Category.query.get(product.category_id) if product.category_id else None

        return jsonify({
            'id': product.id,
            'name': product.name,
            'sku': product.sku,
            'category_id': product.category_id,
            'category_name': category.name if category else 'Uncategorized',
            'category_type': category.category_type if category and hasattr(category, 'category_type') else None,
            'unit_of_measure': product.unit_of_measure
        })
    except Exception as e:
        print(f"Error getting product details: {str(e)}")
        return jsonify({
            'error': str(e)
        }), 500

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

@app.route('/api/items/update-reorder-level', methods=['POST'])
@login_required
def update_item_reorder_level():
    data = request.json
    item_id = data.get('item_id')
    reorder_level = data.get('reorder_level')

    if not item_id or reorder_level is None:
        return jsonify({'success': False, 'message': 'Missing required parameters'}), 400

    try:
        item = Item.query.get_or_404(item_id)
        item.reorder_level = reorder_level
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Reorder level updated successfully',
            'item': {
                'id': item.id,
                'name': item.name,
                'reorder_level': item.reorder_level
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

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

@app.route('/api/items/<int:id>', methods=['GET'])
@login_required
def get_item(id):
    item = Item.query.get_or_404(id)
    category = Category.query.get(item.category_id)

    return jsonify({
        'id': item.id,
        'name': item.name,
        'sku': item.sku,
        'description': item.description,
        'category_id': item.category_id,
        'category_name': category.name if category else None,
        'unit_of_measure': item.unit_of_measure,
        'cost': item.cost,
        'price': item.price,
        'reorder_level': item.reorder_level
    })

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

@app.route('/api/items/<int:id>/inventory', methods=['GET'])
@login_required
def get_item_inventory(id):
    """Get inventory data for a specific item across all warehouses"""
    # Check if item exists
    item = Item.query.get_or_404(id)

    # Get inventory records for this item
    inventory_records = db.session.query(
        Inventory, Warehouse
    ).join(
        Warehouse, Inventory.warehouse_id == Warehouse.id
    ).filter(
        Inventory.item_id == id
    ).all()

    # Format the response
    warehouses = []
    total_quantity = 0

    for inv, warehouse in inventory_records:
        warehouses.append({
            'id': warehouse.id,
            'name': warehouse.name,
            'quantity': inv.quantity,
            'last_updated': inv.last_updated.isoformat() if inv.last_updated else None
        })
        total_quantity += inv.quantity

    return jsonify({
        'item_id': id,
        'total_quantity': total_quantity,
        'warehouses': warehouses
    })

@app.route('/api/items/<int:id>/transactions', methods=['GET'])
@login_required
def get_item_transactions(id):
    """Get transaction history for a specific item"""
    # Check if item exists
    item = Item.query.get_or_404(id)

    # Get recent transactions for this item (limit to 20)
    transactions = db.session.query(
        InventoryTransaction, Warehouse
    ).join(
        Warehouse, InventoryTransaction.warehouse_id == Warehouse.id
    ).filter(
        InventoryTransaction.item_id == id
    ).order_by(
        InventoryTransaction.transaction_date.desc()
    ).limit(20).all()

    # Format the response
    result = []
    for txn, warehouse in transactions:
        result.append({
            'id': txn.id,
            'transaction_type': txn.transaction_type,
            'quantity': txn.quantity,
            'transaction_date': txn.transaction_date.isoformat(),
            'warehouse_id': warehouse.id,
            'warehouse_name': warehouse.name,
            'notes': txn.reference
        })

    return jsonify(result)

@app.route('/api/production/orders', methods=['POST'])
@login_required
def create_production_order_api():
    """Create a new production order"""
    data = request.get_json()

    # Validate required fields
    required_fields = ['item_id', 'quantity', 'production_line_id', 'warehouse_id', 'scheduled_start', 'scheduled_end']
    missing_fields = [field for field in required_fields if not data.get(field)]

    if missing_fields:
        return jsonify({'message': f'Missing required fields: {", ".join(missing_fields)}'}), 400

    # Check if product exists
    product = Item.query.get(data['item_id'])
    if not product:
        return jsonify({'message': 'Product not found'}), 404

    # Verify product is a final or intermediate product
    category = Category.query.get(product.category_id)
    if not category or (category.category_type != 'FinalProduct' and category.category_type != 'IntermediateProduct'):
        return jsonify({'message': 'Selected item is not a final or intermediate product'}), 400

    # Check if production line exists
    production_line = ProductionLine.query.get(data['production_line_id'])
    if not production_line:
        return jsonify({'message': 'Production line not found'}), 404

    # Check if warehouse exists
    warehouse = Warehouse.query.get(data['warehouse_id'])
    if not warehouse:
        return jsonify({'message': 'Warehouse not found'}), 404

    try:
        # Parse scheduled dates
        scheduled_start = datetime.fromisoformat(data['scheduled_start'].replace('Z', '+00:00'))
        scheduled_end = datetime.fromisoformat(data['scheduled_end'].replace('Z', '+00:00'))

        # Create the production order
        order = ProductionOrder(
            product_id=data['item_id'],
            quantity=data['quantity'],
            production_line_id=data['production_line_id'],
            status='Planned',
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            created_by=current_user.id,
            created_at=datetime.now()
        )

        # Add notes if provided
        if data.get('notes'):
            order.notes = data['notes']

        db.session.add(order)
        db.session.commit()

        # Create batch
        batch = Batch(
            item_id=data['item_id'],
            lot_number=f"LOT-{datetime.now().strftime('%Y%m%d')}-{order.id}",
            production_date=datetime.now(),
            quantity=data['quantity'],
            production_order_id=order.id,
            status='Created'
        )
        db.session.add(batch)
        db.session.commit()

        return jsonify({
            'id': order.id,
            'product_id': order.product_id,
            'product_name': product.name,
            'quantity': order.quantity,
            'production_line_id': order.production_line_id,
            'production_line_name': production_line.name,
            'warehouse_id': warehouse.id,
            'warehouse_name': warehouse.name,
            'scheduled_start': order.scheduled_start.isoformat(),
            'scheduled_end': order.scheduled_end.isoformat(),
            'status': order.status,
            'created_at': order.created_at.isoformat()
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Error creating production order: {str(e)}'}), 500

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

        # Add alerts for inventory movements and low stock
        try:
            from utils.alerts_manager import add_inventory_movement_alert, add_low_stock_alert

            # Check if this is a transfer between warehouses (indicated by reference containing "transfer")
            if reference and "transfer" in reference.lower():
                item_name = Item.query.get(item_id).name
                warehouse_name = Warehouse.query.get(warehouse_id).name

                if transaction_type == 'OUT':
                    # This is the source warehouse - we'll create the alert when processing the destination
                    pass
                elif transaction_type == 'IN':
                    # This is the destination warehouse - create movement alert
                    # Try to extract source warehouse from reference or use a generic message
                    add_inventory_movement_alert(item_name, "مستودع آخر", warehouse_name, abs(quantity))

            # Check for low stock after any transaction
            if transaction_type == 'OUT':
                item = Item.query.get(item_id)
                warehouse = Warehouse.query.get(warehouse_id)

                # Check if current quantity is at or below reorder level
                if inventory.quantity <= item.reorder_level:
                    add_low_stock_alert(item.name, inventory.quantity, item.reorder_level, warehouse.name)

        except Exception as e:
            # Don't fail the transaction if alert creation fails
            print(f"Failed to create alerts: {e}")

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


# Warehouse API Endpoints
@app.route('/api/warehouses', methods=['GET'])
@login_required
def get_warehouses():
    """Get all warehouses"""
    warehouses = Warehouse.query.all()
    result = []

    for warehouse in warehouses:
        result.append({
            'id': warehouse.id,
            'name': warehouse.name,
            'location': warehouse.location,
            'capacity': warehouse.capacity
        })

    return jsonify(result)

# Production Line API Endpoints
@app.route('/api/production/lines', methods=['GET'])
@login_required
def get_production_lines_api():
    """Get all production lines"""
    lines = ProductionLine.query.filter_by(is_active=True).all()
    result = []

    for line in lines:
        result.append({
            'id': line.id,
            'name': line.name,
            'description': line.description,
            'capacity_per_hour': line.capacity_per_hour,
            'capacity_unit': line.capacity_unit,
            'location': line.location
        })

    return jsonify(result)

# Dashboard API Endpoints
@app.route('/api/dashboard/stats')
@login_required
def get_dashboard_stats():
    """
    Comprehensive dashboard statistics API endpoint.
    Returns all necessary data for the dashboard in a single call to optimize loading time.
    """
    from sqlalchemy import func, desc
    from datetime import datetime, timedelta
    from models import Vehicle

    result = {
        # Basic inventory stats
        'inventory': {
            'totalItems': 0,
            'totalWarehouses': 0,
            'totalCategories': 0,
            'totalTransactions': 0,
            'totalValue': 0,
            'lowStockCount': 0,
            'valueByCategory': [],
            'recentTransactions': []
        },

        # Sales stats
        'sales': {
            'totalOrders': 0,
            'pendingOrders': 0,
            'completedOrders': 0,
            'totalAmount': 0,
            'monthlySales': [],
            'topProducts': []
        },

        # Production stats
        'production': {
            'totalOrders': 0,
            'activeOrders': 0,
            'completedOrders': 0,
            'statusBreakdown': {},
            'efficiency': 0
        },

        # Cash stats
        'cash': {
            'totalCash': 0,
            'activeAccounts': 0,
            'recentTransactions': [],
            'cashFlow': {'in': 0, 'out': 0}
        },

        # Supplier stats
        'suppliers': {
            'totalSuppliers': 0,
            'totalPurchaseOrders': 0,
            'pendingPurchases': 0,
            'topSuppliers': []
        },

        # Distribution stats
        'distribution': {
            'totalShipments': 0,
            'pendingShipments': 0,
            'deliveredShipments': 0,
            'activeVehicles': 0
        }
    }

    try:
        # Get basic inventory stats
        items_count = Item.query.count()
        warehouses_count = Warehouse.query.count()
        categories_count = Category.query.count()
        transactions_count = InventoryTransaction.query.count()

        # Calculate total inventory value
        total_inventory_value = 0
        try:
            inventory_items = db.session.query(Inventory, Item).join(Item, Inventory.item_id == Item.id).all()
            for inv, item in inventory_items:
                total_inventory_value += inv.quantity * item.cost
        except Exception as e:
            app.logger.error(f"Error calculating inventory value: {str(e)}")

        # Get low stock items count
        low_stock_count = 0
        try:
            item_quantities = {}
            inventory_records = Inventory.query.all()
            for inv in inventory_records:
                if inv.item_id not in item_quantities:
                    item_quantities[inv.item_id] = 0
                item_quantities[inv.item_id] += inv.quantity

            for item in Item.query.all():
                quantity = item_quantities.get(item.id, 0)
                if quantity <= item.reorder_level:
                    low_stock_count += 1
        except Exception as e:
            app.logger.error(f"Error calculating low stock count: {str(e)}")

        # Get inventory value by category
        try:
            category_values = {}
            for inv, item in inventory_items:
                if item.category_id not in category_values:
                    category_values[item.category_id] = 0
                category_values[item.category_id] += inv.quantity * item.cost

            value_by_category = []
            for cat_id, value in category_values.items():
                category = Category.query.get(cat_id)
                if category:
                    value_by_category.append({
                        'id': cat_id,
                        'name': category.name,
                        'value': round(value, 2)
                    })

            # Sort by value (highest first)
            value_by_category.sort(key=lambda x: x['value'], reverse=True)
        except Exception as e:
            app.logger.error(f"Error calculating inventory value by category: {str(e)}")
            value_by_category = []

        # Get recent transactions
        try:
            recent_txns = InventoryTransaction.query.order_by(
                InventoryTransaction.transaction_date.desc()
            ).limit(5).all()

            recent_transactions = []
            for txn in recent_txns:
                item = Item.query.get(txn.item_id)
                warehouse = Warehouse.query.get(txn.warehouse_id)
                recent_transactions.append({
                    'id': txn.id,
                    'item_name': item.name if item else 'Unknown',
                    'warehouse_name': warehouse.name if warehouse else 'Unknown',
                    'transaction_type': txn.transaction_type,
                    'quantity': txn.quantity,
                    'date': txn.transaction_date.isoformat()
                })
        except Exception as e:
            app.logger.error(f"Error getting recent transactions: {str(e)}")
            recent_transactions = []

        # Update inventory stats in result
        result['inventory'] = {
            'totalItems': items_count,
            'totalWarehouses': warehouses_count,
            'totalCategories': categories_count,
            'totalTransactions': transactions_count,
            'totalValue': round(total_inventory_value, 2),
            'lowStockCount': low_stock_count,
            'valueByCategory': value_by_category,
            'recentTransactions': recent_transactions
        }
    except Exception as e:
        app.logger.error(f"Error getting inventory stats: {str(e)}")

    # Sales stats
    try:
        total_sales_orders = SalesOrder.query.count()
        pending_sales = SalesOrder.query.filter_by(status='Pending').count()
        completed_sales = SalesOrder.query.filter_by(status='Delivered').count()
        total_sales_amount = db.session.query(func.sum(SalesOrder.total_amount)).scalar() or 0

        # Get monthly sales for the last 6 months
        try:
            today = datetime.now()
            monthly_sales = []

            for i in range(5, -1, -1):
                month_start = datetime(today.year, today.month, 1) - timedelta(days=30*i)
                month_end = datetime(month_start.year, month_start.month + 1, 1) - timedelta(days=1) if month_start.month < 12 else datetime(month_start.year + 1, 1, 1) - timedelta(days=1)

                month_sales = db.session.query(func.sum(SalesOrder.total_amount)).filter(
                    SalesOrder.order_date >= month_start,
                    SalesOrder.order_date <= month_end
                ).scalar() or 0

                monthly_sales.append({
                    'month': month_start.strftime('%Y-%m'),
                    'monthName': month_start.strftime('%b %Y'),
                    'amount': round(month_sales, 2)
                })
        except Exception as e:
            app.logger.error(f"Error calculating monthly sales: {str(e)}")
            monthly_sales = []

        # Get top selling products
        try:
            # Query to get total quantity sold for each product
            top_products_query = db.session.query(
                SalesOrderDetail.item_id,
                func.sum(SalesOrderDetail.quantity_ordered).label('total_sold')
            ).group_by(SalesOrderDetail.item_id).order_by(desc('total_sold')).limit(5).all()

            top_products = []
            for item_id, total_sold in top_products_query:
                item = Item.query.get(item_id)
                if item:
                    top_products.append({
                        'id': item.id,
                        'name': item.name,
                        'sku': item.sku,
                        'totalSold': total_sold,
                        'revenue': round(total_sold * item.price, 2)
                    })
        except Exception as e:
            app.logger.error(f"Error getting top products: {str(e)}")
            top_products = []

        # Update sales stats in result
        result['sales'] = {
            'totalOrders': total_sales_orders,
            'pendingOrders': pending_sales,
            'completedOrders': completed_sales,
            'totalAmount': round(total_sales_amount, 2),
            'monthlySales': monthly_sales,
            'topProducts': top_products
        }
    except Exception as e:
        app.logger.error(f"Error getting sales stats: {str(e)}")

    # Production stats
    try:
        total_production_orders = ProductionOrder.query.count()
        active_production = ProductionOrder.query.filter_by(status='InProgress').count()
        completed_production = ProductionOrder.query.filter_by(status='Completed').count()

        # Get production status breakdown
        try:
            status_counts = {}
            for status in ['Planned', 'InProgress', 'Completed', 'Cancelled', 'OnHold']:
                count = ProductionOrder.query.filter_by(status=status).count()
                status_counts[status] = count
        except Exception as e:
            app.logger.error(f"Error getting production status breakdown: {str(e)}")
            status_counts = {}

        # Calculate production efficiency (if available)
        production_efficiency = 0
        try:
            efficiency_records = ProductionEfficiency.query.order_by(
                ProductionEfficiency.id.desc()
            ).limit(30).all()

            if efficiency_records:
                production_efficiency = sum(record.efficiency_score for record in efficiency_records) / len(efficiency_records)
        except Exception as e:
            app.logger.error(f"Error calculating production efficiency: {str(e)}")

        # Update production stats in result
        result['production'] = {
            'totalOrders': total_production_orders,
            'activeOrders': active_production,
            'completedOrders': completed_production,
            'statusBreakdown': status_counts,
            'efficiency': round(production_efficiency, 2)
        }
    except Exception as e:
        app.logger.error(f"Error getting production stats: {str(e)}")

    # Cash stats
    try:
        accounts = CashAccount.query.filter_by(is_active=True).all()
        total_cash = sum(account.current_balance for account in accounts)
        active_accounts = len(accounts)

        # Get recent cash transactions
        try:
            recent_cash_txns = CashTransaction.query.order_by(
                CashTransaction.transaction_date.desc()
            ).limit(5).all()

            recent_cash_transactions = []
            for txn in recent_cash_txns:
                account = CashAccount.query.get(txn.account_id)
                recent_cash_transactions.append({
                    'id': txn.id,
                    'account': account.name if account else 'Unknown',
                    'amount': txn.amount,
                    'type': txn.transaction_type,
                    'description': txn.description,
                    'date': txn.transaction_date.isoformat()
                })
        except Exception as e:
            app.logger.error(f"Error getting recent cash transactions: {str(e)}")
            recent_cash_transactions = []

        # Calculate cash flow (last 30 days)
        try:
            thirty_days_ago = datetime.now() - timedelta(days=30)

            cash_in = db.session.query(func.sum(CashTransaction.amount)).filter(
                CashTransaction.transaction_type == 'IN',
                CashTransaction.transaction_date >= thirty_days_ago
            ).scalar() or 0

            cash_out = db.session.query(func.sum(CashTransaction.amount)).filter(
                CashTransaction.transaction_type == 'OUT',
                CashTransaction.transaction_date >= thirty_days_ago
            ).scalar() or 0

            cash_flow = {
                'in': round(cash_in, 2),
                'out': round(cash_out, 2),
                'net': round(cash_in - cash_out, 2)
            }
        except Exception as e:
            app.logger.error(f"Error calculating cash flow: {str(e)}")
            cash_flow = {'in': 0, 'out': 0, 'net': 0}

        # Update cash stats in result
        result['cash'] = {
            'totalCash': round(total_cash, 2),
            'activeAccounts': active_accounts,
            'recentTransactions': recent_cash_transactions,
            'cashFlow': cash_flow
        }
    except Exception as e:
        app.logger.error(f"Error getting cash stats: {str(e)}")

    # Supplier stats
    try:
        total_suppliers = Supplier.query.count()
        total_purchase_orders = PurchaseOrder.query.count()
        pending_purchases = PurchaseOrder.query.filter_by(status='Pending').count()

        # Get top suppliers by purchase volume
        try:
            top_suppliers_query = db.session.query(
                PurchaseOrder.supplier_id,
                func.sum(PurchaseOrder.total_amount).label('total_purchased')
            ).group_by(PurchaseOrder.supplier_id).order_by(desc('total_purchased')).limit(5).all()

            top_suppliers = []
            for supplier_id, total_purchased in top_suppliers_query:
                supplier = Supplier.query.get(supplier_id)
                if supplier:
                    top_suppliers.append({
                        'id': supplier.id,
                        'name': supplier.supplier_name,
                        'totalPurchased': round(total_purchased, 2)
                    })
        except Exception as e:
            app.logger.error(f"Error getting top suppliers: {str(e)}")
            top_suppliers = []

        # Update supplier stats in result
        result['suppliers'] = {
            'totalSuppliers': total_suppliers,
            'totalPurchaseOrders': total_purchase_orders,
            'pendingPurchases': pending_purchases,
            'topSuppliers': top_suppliers
        }
    except Exception as e:
        app.logger.error(f"Error getting supplier stats: {str(e)}")

    # Distribution stats
    try:
        total_shipments = ShipmentOrder.query.count()
        pending_shipments = ShipmentOrder.query.filter_by(status='Pending').count()
        delivered_shipments = ShipmentOrder.query.filter_by(status='Delivered').count()

        # Get active vehicles count
        try:
            active_vehicles = Vehicle.query.filter_by(status='Active').count()
        except Exception as e:
            app.logger.error(f"Error getting active vehicles count: {str(e)}")
            active_vehicles = 0

        # Update distribution stats in result
        result['distribution'] = {
            'totalShipments': total_shipments,
            'pendingShipments': pending_shipments,
            'deliveredShipments': delivered_shipments,
            'activeVehicles': active_vehicles
        }
    except Exception as e:
        app.logger.error(f"Error getting distribution stats: {str(e)}")

    return jsonify(result)

@app.route('/api/dashboard/products-by-category-type')
@login_required
def get_products_by_category_type():
    category_type = request.args.get('category_type', None)

    if not category_type:
        return jsonify({'error': 'Category type is required'}), 400

    # Get categories of the specified type
    categories = Category.query.filter_by(category_type=category_type).all()
    category_ids = [cat.id for cat in categories]

    # Get items in these categories
    items = Item.query.filter(Item.category_id.in_(category_ids)).all()

    # Get inventory quantities for each item
    item_quantities = {}
    inventory_records = Inventory.query.all()
    for inv in inventory_records:
        if inv.item_id not in item_quantities:
            item_quantities[inv.item_id] = 0
        item_quantities[inv.item_id] += inv.quantity

    # Format the response
    result = []
    for item in items:
        # Get the category
        category = next((cat for cat in categories if cat.id == item.category_id), None)

        # Calculate profit margin
        profit = item.price - item.cost
        margin_percentage = (profit / item.cost * 100) if item.cost > 0 else 0

        result.append({
            'id': item.id,
            'name': item.name,
            'sku': item.sku,
            'category_id': item.category_id,
            'category_name': category.name if category else '',
            'description': item.description,
            'unit_of_measure': item.unit_of_measure,
            'cost': item.cost,
            'price': item.price,
            'profit_margin': round(margin_percentage, 2),
            'quantity': item_quantities.get(item.id, 0),
            'reorder_level': item.reorder_level,
            'is_low_stock': item_quantities.get(item.id, 0) <= item.reorder_level
        })

    return jsonify(result)

@app.route('/api/dashboard/comprehensive-stats')
@login_required
def get_comprehensive_dashboard_stats():
    result = {
        'inventory': {
            'totalItems': 0,
            'totalWarehouses': 0,
            'totalCategories': 0,
            'totalTransactions': 0,
            'totalValue': 0,
            'lowStockCount': 0
        },
        'sales': {
            'totalOrders': 0,
            'pendingOrders': 0,
            'completedOrders': 0,
            'totalAmount': 0
        },
        'production': {
            'totalOrders': 0,
            'activeOrders': 0,
            'completedOrders': 0
        },
        'cash': {
            'totalCash': 0,
            'activeAccounts': 0
        },
        'suppliers': {
            'totalSuppliers': 0,
            'totalPurchaseOrders': 0,
            'pendingPurchases': 0
        },
        'distribution': {
            'totalShipments': 0,
            'pendingShipments': 0,
            'deliveredShipments': 0
        }
    }

    # Inventory stats
    try:
        items_count = Item.query.count()
        warehouses_count = Warehouse.query.count()
        categories_count = Category.query.count()
        transactions_count = InventoryTransaction.query.count()

        # Calculate total inventory value
        total_inventory_value = 0
        try:
            inventory_items = db.session.query(Inventory, Item).join(Item, Inventory.item_id == Item.id).all()
            for inv, item in inventory_items:
                total_inventory_value += inv.quantity * item.cost
        except Exception as e:
            app.logger.error(f"Error calculating inventory value: {str(e)}")

        # Get low stock items count
        low_stock_count = 0
        try:
            item_quantities = {}
            inventory_records = Inventory.query.all()
            for inv in inventory_records:
                if inv.item_id not in item_quantities:
                    item_quantities[inv.item_id] = 0
                item_quantities[inv.item_id] += inv.quantity

            for item in Item.query.all():
                quantity = item_quantities.get(item.id, 0)
                if quantity <= item.reorder_level:
                    low_stock_count += 1
        except Exception as e:
            app.logger.error(f"Error calculating low stock count: {str(e)}")

        # Update inventory stats in result
        result['inventory'] = {
            'totalItems': items_count,
            'totalWarehouses': warehouses_count,
            'totalCategories': categories_count,
            'totalTransactions': transactions_count,
            'totalValue': round(total_inventory_value, 2),
            'lowStockCount': low_stock_count
        }
    except Exception as e:
        app.logger.error(f"Error getting inventory stats: {str(e)}")

    # Sales stats
    try:
        total_sales_orders = SalesOrder.query.count()
        pending_sales = SalesOrder.query.filter_by(status='Pending').count()
        completed_sales = SalesOrder.query.filter_by(status='Delivered').count()
        total_sales_amount = db.session.query(db.func.sum(SalesOrder.total_amount)).scalar() or 0

        # Update sales stats in result
        result['sales'] = {
            'totalOrders': total_sales_orders,
            'pendingOrders': pending_sales,
            'completedOrders': completed_sales,
            'totalAmount': round(total_sales_amount, 2)
        }
    except Exception as e:
        app.logger.error(f"Error getting sales stats: {str(e)}")

    # Production stats
    try:
        total_production_orders = ProductionOrder.query.count()
        active_production = ProductionOrder.query.filter_by(status='InProgress').count()
        completed_production = ProductionOrder.query.filter_by(status='Completed').count()

        # Update production stats in result
        result['production'] = {
            'totalOrders': total_production_orders,
            'activeOrders': active_production,
            'completedOrders': completed_production
        }
    except Exception as e:
        app.logger.error(f"Error getting production stats: {str(e)}")

    # Cash stats
    try:
        accounts = CashAccount.query.filter_by(is_active=True).all()
        total_cash = sum(account.current_balance for account in accounts)
        active_accounts = len(accounts)

        # Update cash stats in result
        result['cash'] = {
            'totalCash': round(total_cash, 2),
            'activeAccounts': active_accounts
        }
    except Exception as e:
        app.logger.error(f"Error getting cash stats: {str(e)}")

    # Supplier stats
    try:
        total_suppliers = Supplier.query.count()
        total_purchase_orders = PurchaseOrder.query.count()
        pending_purchases = PurchaseOrder.query.filter_by(status='Pending').count()

        # Update supplier stats in result
        result['suppliers'] = {
            'totalSuppliers': total_suppliers,
            'totalPurchaseOrders': total_purchase_orders,
            'pendingPurchases': pending_purchases
        }
    except Exception as e:
        app.logger.error(f"Error getting supplier stats: {str(e)}")

    # Distribution stats
    try:
        total_shipments = ShipmentOrder.query.count()
        pending_shipments = ShipmentOrder.query.filter_by(status='Pending').count()
        delivered_shipments = ShipmentOrder.query.filter_by(status='Delivered').count()

        # Update distribution stats in result
        result['distribution'] = {
            'totalShipments': total_shipments,
            'pendingShipments': pending_shipments,
            'deliveredShipments': delivered_shipments
        }
    except Exception as e:
        app.logger.error(f"Error getting distribution stats: {str(e)}")

    return jsonify(result)

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
            # Get category information
            category = Category.query.get(item.category_id)

            low_stock_items.append({
                'id': item.id,
                'name': item.name,
                'sku': item.sku,
                'quantity': total_quantity,
                'reorder_level': item.reorder_level,
                'category_id': item.category_id,
                'category_type': category.category_type if category else None
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

@app.route('/low-stock-items')
@login_required
def low_stock_items_page():
    return render_template('low_stock_items.html')

@app.route('/items/<int:id>')
@login_required
def item_details_page(id):
    # Check if the item exists
    item = Item.query.get_or_404(id)
    return render_template('item_details.html', item_id=id)

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

    port = 5005
    url = f"http://{local_ip}:{port}"
    print(f" * Katilo System running on {url}")
    context = ('cert.pem', 'key.pem')

    # webbrowser.open(url) # Keep or remove auto-open as preferred
    app.run(host='0.0.0.0', port=port,  ssl_context=context  ,debug=True)