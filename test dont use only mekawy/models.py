from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from sqlalchemy import Enum as SAEnum, CheckConstraint, UniqueConstraint

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

##########################################
# Enumerations for Various Status/Types
##########################################
transaction_type_enum = SAEnum('IN', 'OUT', 'TRANSFER', name='transaction_type_enum')
purchase_order_status_enum = SAEnum('Pending', 'Approved', 'Received', 'Cancelled', name='purchase_order_status_enum')
sales_order_status_enum = SAEnum('Pending', 'Shipped', 'Delivered', 'Cancelled', name='sales_order_status_enum')
qc_status_enum = SAEnum('Passed', 'Failed', 'Retest', name='qc_status_enum')
production_run_status_enum = SAEnum('Planned', 'In Progress', 'Completed', name='production_run_status_enum')
document_category_enum = SAEnum('Recipe', 'Certification', 'Manual', 'Other', name='document_category_enum')

##########################################
# Core Entities and Relationships
##########################################

class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column('CategoryID', db.Integer, primary_key=True)
    name = db.Column('CategoryName', db.String(50), nullable=False)
    description = db.Column('Description', db.String(255))
    
    # One-to-many relationship: A category can have many items.
    items = db.relationship('Item', backref='category', lazy=True)
    
    def __repr__(self):
        return f'<Category {self.name}>'

class Item(db.Model):
    __tablename__ = 'items'
    id = db.Column('ItemID', db.Integer, primary_key=True)
    name = db.Column('ItemName', db.String(100), nullable=False)
    category_id = db.Column('CategoryID', db.Integer, db.ForeignKey('categories.CategoryID'), nullable=False)
    sku = db.Column('SKU', db.String(50), unique=True, nullable=False)
    description = db.Column('Description', db.Text)
    unit_of_measure = db.Column('UnitOfMeasure', db.String(20))
    cost = db.Column('Cost', db.Float, nullable=False)
    price = db.Column('Price', db.Float, nullable=False)
    reorder_level = db.Column('ReorderLevel', db.Integer, nullable=False)
    created_at = db.Column('CreatedAt', db.DateTime, default=datetime.utcnow)
    updated_at = db.Column('UpdatedAt', db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships for inventory, BOM (as final product), and transactions.
    inventories = db.relationship('Inventory', backref='item', lazy=True)
    bom_final = db.relationship('BOM', backref='final_product', lazy=True,
                                foreign_keys='BOM.final_product_id')
    bom_components = db.relationship('BOMDetail', backref='component_item', lazy=True,
                                     foreign_keys='BOMDetail.component_item_id')
    transactions = db.relationship('InventoryTransaction', backref='item', lazy=True)

    # For slot-based layout
    slots = db.relationship('WarehouseSlot', backref='item_ref', lazy=True)
    
    def __repr__(self):
        return f'<Item {self.name}>'

class Warehouse(db.Model):
    __tablename__ = 'warehouses'
    id = db.Column('WarehouseID', db.Integer, primary_key=True)
    name = db.Column('WarehouseName', db.String(100), nullable=False)
    location = db.Column('Location', db.String(255))
    capacity = db.Column('Capacity', db.Integer)
    contact_info = db.Column('ContactInfo', db.String(255))  # Additional contact/manager info.
    item_location = db.Column('ItemLocation', db.String(100))  # Example custom field
    
    inventories = db.relationship('Inventory', backref='warehouse', lazy=True)
    transactions = db.relationship('InventoryTransaction', backref='warehouse', lazy=True)
    sections = db.relationship('WarehouseSection', backref='warehouse', lazy=True)
    
    def __repr__(self):
        return f'<Warehouse {self.name}>'

##########################################
# Warehouse Layout (Sections & Slots)
##########################################

class WarehouseSection(db.Model):
    __tablename__ = 'warehouse_sections'
    id = db.Column(db.Integer, primary_key=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.WarehouseID'), nullable=False)
    section_name = db.Column(db.String(100), nullable=False)
    row_count = db.Column(db.Integer, nullable=False, default=10)
    column_count = db.Column(db.Integer, nullable=False, default=10)

    slots = db.relationship('WarehouseSlot', backref='section', lazy=True)

    def __repr__(self):
        return f"<WarehouseSection {self.section_name} in Warehouse {self.warehouse_id}>"

class WarehouseSlot(db.Model):
    __tablename__ = 'warehouse_slots'
    id = db.Column(db.Integer, primary_key=True)
    section_id = db.Column(db.Integer, db.ForeignKey('warehouse_sections.id'), nullable=False)
    row_number = db.Column(db.Integer, nullable=False)
    column_number = db.Column(db.Integer, nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.ItemID'))
    quantity = db.Column(db.Integer, default=0)

    # Ensure row_number + column_number is unique per section
    __table_args__ = (
        UniqueConstraint('section_id', 'row_number', 'column_number', name='uq_slot_position'),
        CheckConstraint('quantity >= 0', name='chk_slot_qty_nonnegative'),
    )

    def __repr__(self):
        return (f"<WarehouseSlot (Section {self.section_id}, "
                f"Row {self.row_number}, Col {self.column_number}, "
                f"Item {self.item_id}, Qty {self.quantity})>")

##########################################
# Inventory & Transactions
##########################################

class Inventory(db.Model):
    __tablename__ = 'inventory'
    id = db.Column('InventoryID', db.Integer, primary_key=True)
    item_id = db.Column('ItemID', db.Integer, db.ForeignKey('items.ItemID'), index=True, nullable=False)
    warehouse_id = db.Column('WarehouseID', db.Integer, db.ForeignKey('warehouses.WarehouseID'), index=True, nullable=False)
    quantity = db.Column('Quantity', db.Integer, nullable=False)
    last_updated = db.Column('LastUpdated', db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # (Optional) Ensure quantity is nonnegative
    __table_args__ = (
        CheckConstraint('Quantity >= 0', name='chk_inventory_qty_nonnegative'),
    )

    def __repr__(self):
        return f'<Inventory Item {self.item_id} at Warehouse {self.warehouse_id}>'

class InventoryTransaction(db.Model):
    __tablename__ = 'inventory_transactions'
    id = db.Column('TransactionID', db.Integer, primary_key=True)
    item_id = db.Column('ItemID', db.Integer, db.ForeignKey('items.ItemID'), index=True, nullable=False)
    warehouse_id = db.Column('WarehouseID', db.Integer, db.ForeignKey('warehouses.WarehouseID'), index=True, nullable=False)
    transaction_type = db.Column(transaction_type_enum, nullable=False)  # Use enum instead of free text
    quantity = db.Column('Quantity', db.Integer, nullable=False)
    transaction_date = db.Column('TransactionDate', db.DateTime, default=datetime.utcnow)
    reference = db.Column('Reference', db.String(255))  # e.g., link to orders or production batches
    
    __table_args__ = (
        CheckConstraint('Quantity > 0', name='chk_transaction_qty_positive'),
    )

    def __repr__(self):
        return (f'<Transaction {self.transaction_type} of Item {self.item_id} '
                f'in Warehouse {self.warehouse_id} (Qty: {self.quantity})>')

##########################################
# Manufacturing (BOM)
##########################################

class BOM(db.Model):
    __tablename__ = 'bom'
    id = db.Column('BOMID', db.Integer, primary_key=True)
    final_product_id = db.Column('FinalProductID', db.Integer, db.ForeignKey('items.ItemID'), nullable=False)
    description = db.Column('Description', db.Text)
    created_at = db.Column('CreatedAt', db.DateTime, default=datetime.utcnow)
    updated_at = db.Column('UpdatedAt', db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # One-to-many: A BOM can have multiple BOM details.
    details = db.relationship('BOMDetail', backref='bom', lazy=True)
    
    def __repr__(self):
        return f'<BOM for Final Product {self.final_product_id}>'

class BOMDetail(db.Model):
    __tablename__ = 'bom_details'
    id = db.Column('BOMDetailID', db.Integer, primary_key=True)
    bom_id = db.Column('BOMID', db.Integer, db.ForeignKey('bom.BOMID'), nullable=False)
    component_item_id = db.Column('ComponentItemID', db.Integer, db.ForeignKey('items.ItemID'), nullable=False)
    quantity_required = db.Column('QuantityRequired', db.Float, nullable=False)
    unit_of_measure = db.Column('UnitOfMeasure', db.String(20))
    
    def __repr__(self):
        return f'<BOMDetail for BOM {self.bom_id} Component {self.component_item_id}>'

##########################################
# 1. Supplier Management
##########################################

class Supplier(db.Model):
    __tablename__ = 'suppliers'
    id = db.Column('SupplierID', db.Integer, primary_key=True)
    supplier_name = db.Column('SupplierName', db.String(100), nullable=False)
    contact_info = db.Column('ContactInfo', db.Text)  # phone, email, address
    payment_terms = db.Column('PaymentTerms', db.String(50))  # e.g., net 30
    rating = db.Column('Rating', db.Float)  # optional rating

    # Relationship: A supplier can have many SupplierItems
    supplier_items = db.relationship('SupplierItem', backref='supplier', lazy=True)

    def __repr__(self):
        return f"<Supplier {self.supplier_name}>"

class SupplierItem(db.Model):
    __tablename__ = 'supplier_items'
    id = db.Column('SupplierItemID', db.Integer, primary_key=True)
    supplier_id = db.Column('SupplierID', db.Integer, db.ForeignKey('suppliers.SupplierID'), nullable=False)
    item_id = db.Column('ItemID', db.Integer, db.ForeignKey('items.ItemID'), nullable=False)
    supplier_sku = db.Column('SupplierSKU', db.String(50))
    cost = db.Column('Cost', db.Float, nullable=False)

    def __repr__(self):
        return f"<SupplierItem Supplier {self.supplier_id}, Item {self.item_id}>"

##########################################
# 2. Purchase Orders (PO)
##########################################

class PurchaseOrder(db.Model):
    __tablename__ = 'purchase_orders'
    id = db.Column('POID', db.Integer, primary_key=True)
    supplier_id = db.Column('SupplierID', db.Integer, db.ForeignKey('suppliers.SupplierID'), nullable=False)
    order_date = db.Column('OrderDate', db.DateTime, default=datetime.utcnow)
    status = db.Column(purchase_order_status_enum, default='Pending')
    total_amount = db.Column('TotalAmount', db.Float)  
    # Note: total_amount is a derived field. Use triggers or app logic to keep it in sync.

    supplier = db.relationship('Supplier', backref='purchase_orders', lazy=True)
    details = db.relationship('PurchaseOrderDetail', backref='purchase_order', lazy=True)

    def __repr__(self):
        return f"<PurchaseOrder {self.id} Supplier {self.supplier_id} Status {self.status}>"

class PurchaseOrderDetail(db.Model):
    __tablename__ = 'purchase_order_details'
    id = db.Column('PODetailID', db.Integer, primary_key=True)
    po_id = db.Column('POID', db.Integer, db.ForeignKey('purchase_orders.POID'), nullable=False)
    item_id = db.Column('ItemID', db.Integer, db.ForeignKey('items.ItemID'), nullable=False)
    quantity_ordered = db.Column('QuantityOrdered', db.Integer, nullable=False)
    unit_price = db.Column('UnitPrice', db.Float, nullable=False)
    quantity_received = db.Column('QuantityReceived', db.Integer, default=0)

    __table_args__ = (
        CheckConstraint('QuantityOrdered > 0', name='chk_po_detail_qty_ordered_positive'),
        CheckConstraint('QuantityReceived >= 0', name='chk_po_detail_qty_received_nonnegative'),
    )

    def __repr__(self):
        return f"<PODetail {self.id} PO {self.po_id} Item {self.item_id}>"

##########################################
# 3. Sales Orders and Customer Management
##########################################

class Customer(db.Model):
    __tablename__ = 'customers'
    id = db.Column('CustomerID', db.Integer, primary_key=True)
    customer_name = db.Column('CustomerName', db.String(100), nullable=False)
    contact_info = db.Column('ContactInfo', db.Text)
    billing_address = db.Column('BillingAddress', db.Text)
    shipping_address = db.Column('ShippingAddress', db.Text)

    # Relationship: a customer can have many sales orders
    sales_orders = db.relationship('SalesOrder', backref='customer', lazy=True)

    def __repr__(self):
        return f"<Customer {self.customer_name}>"

class SalesOrder(db.Model):
    __tablename__ = 'sales_orders'
    id = db.Column('SalesOrderID', db.Integer, primary_key=True)
    customer_id = db.Column('CustomerID', db.Integer, db.ForeignKey('customers.CustomerID'), nullable=False)
    order_date = db.Column('OrderDate', db.DateTime, default=datetime.utcnow)
    status = db.Column(sales_order_status_enum, default='Pending')
    total_amount = db.Column('TotalAmount', db.Float)  
    # Derived field: update via triggers or application logic

    details = db.relationship('SalesOrderDetail', backref='sales_order', lazy=True)

    def __repr__(self):
        return f"<SalesOrder {self.id} Customer {self.customer_id}>"

class SalesOrderDetail(db.Model):
    __tablename__ = 'sales_order_details'
    id = db.Column('SODetailID', db.Integer, primary_key=True)
    sales_order_id = db.Column('SalesOrderID', db.Integer, db.ForeignKey('sales_orders.SalesOrderID'), nullable=False)
    item_id = db.Column('ItemID', db.Integer, db.ForeignKey('items.ItemID'), nullable=False)
    quantity_ordered = db.Column('QuantityOrdered', db.Integer, nullable=False)
    unit_price = db.Column('UnitPrice', db.Float, nullable=False)
    quantity_shipped = db.Column('QuantityShipped', db.Integer, default=0)

    __table_args__ = (
        CheckConstraint('QuantityOrdered > 0', name='chk_so_detail_qty_ordered_positive'),
        CheckConstraint('QuantityShipped >= 0', name='chk_so_detail_qty_shipped_nonnegative'),
    )

    def __repr__(self):
        return f"<SODetail {self.id} SO {self.sales_order_id} Item {self.item_id}>"

##########################################
# 4. Lot/Batch Tracking and Expiry Management
##########################################

class Batch(db.Model):
    __tablename__ = 'batches'
    id = db.Column('BatchID', db.Integer, primary_key=True)
    item_id = db.Column('ItemID', db.Integer, db.ForeignKey('items.ItemID'), nullable=False)
    lot_number = db.Column('LotNumber', db.String(100), unique=True, nullable=False)
    production_date = db.Column('ProductionDate', db.DateTime)
    expiry_date = db.Column('ExpiryDate', db.DateTime)
    quantity = db.Column('Quantity', db.Integer, nullable=False)

    # Relationship: A batch is for one item
    item = db.relationship('Item', backref='batches', lazy=True)
    # Relationship: A batch can be stored in multiple slots
    batch_slots = db.relationship('BatchSlot', backref='batch', lazy=True)

    __table_args__ = (
        CheckConstraint('Quantity >= 0', name='chk_batch_qty_nonnegative'),
    )

    def __repr__(self):
        return f"<Batch {self.id} Item {self.item_id} Lot {self.lot_number}>"

class BatchSlot(db.Model):
    __tablename__ = 'batch_slots'
    id = db.Column('BatchSlotID', db.Integer, primary_key=True)
    batch_id = db.Column('BatchID', db.Integer, db.ForeignKey('batches.BatchID'), nullable=False)
    slot_id = db.Column('SlotID', db.Integer, db.ForeignKey('warehouse_slots.id'), nullable=False)
    quantity_in_slot = db.Column('QuantityInSlot', db.Integer, default=0)

    __table_args__ = (
        CheckConstraint('QuantityInSlot >= 0', name='chk_batchslot_qty_nonnegative'),
        # Ideally, also ensure sum(QuantityInSlot) <= Batch.quantity (via triggers or app logic)
    )

    def __repr__(self):
        return f"<BatchSlot {self.id} Batch {self.batch_id} Slot {self.slot_id}>"

##########################################
# 5. Quality Control (QC) & Inspections
##########################################

class QualityCheck(db.Model):
    __tablename__ = 'quality_checks'
    id = db.Column('QCID', db.Integer, primary_key=True)
    batch_id = db.Column('BatchID', db.Integer, db.ForeignKey('batches.BatchID'), nullable=False)
    check_date = db.Column('CheckDate', db.DateTime, default=datetime.utcnow)
    inspector_name = db.Column('InspectorName', db.String(100))
    status = db.Column(qc_status_enum, default='Retest')  # e.g., Passed, Failed, Retest

    # Relationship: QC belongs to a batch
    batch = db.relationship('Batch', backref='quality_checks', lazy=True)
    # One-to-many relationship with separate QC results
    qc_results = db.relationship('QualityCheckResult', backref='quality_check', lazy=True)

    def __repr__(self):
        return f"<QualityCheck {self.id} Batch {self.batch_id}>"

class QualityCheckResult(db.Model):
    """
    Stores individual test parameters and values instead of using a JSON column.
    """
    __tablename__ = 'quality_check_results'
    id = db.Column(db.Integer, primary_key=True)
    qc_id = db.Column(db.Integer, db.ForeignKey('quality_checks.QCID'), nullable=False)
    param_name = db.Column(db.String(100), nullable=False)  # e.g., 'pH', 'Moisture'
    param_value = db.Column(db.String(100))  # e.g., '6.2'

    def __repr__(self):
        return f"<QualityCheckResult {self.id} QC {self.qc_id} {self.param_name}={self.param_value}>"

class QCParameter(db.Model):
    __tablename__ = 'qc_parameters'
    id = db.Column('QCParamID', db.Integer, primary_key=True)
    param_name = db.Column('ParamName', db.String(100), nullable=False)  # e.g. 'pH'
    reference_range = db.Column('ReferenceRange', db.String(50))  # e.g. '6.0-6.5'

    def __repr__(self):
        return f"<QCParameter {self.param_name}>"

##########################################
# 6. Maintenance and Calibration (Equipment)
##########################################

class Equipment(db.Model):
    __tablename__ = 'equipment'
    id = db.Column('EquipmentID', db.Integer, primary_key=True)
    name = db.Column('Name', db.String(100), nullable=False)
    serial_number = db.Column('SerialNumber', db.String(100), unique=True)
    location = db.Column('Location', db.String(255))  # e.g. 'Warehouse A', 'Production Floor'
    last_maintenance_date = db.Column('LastMaintenanceDate', db.DateTime)
    maintenance_interval = db.Column('MaintenanceInterval', db.Integer)  # days or hours

    maintenance_logs = db.relationship('MaintenanceLog', backref='equipment', lazy=True)

    def __repr__(self):
        return f"<Equipment {self.id} {self.name}>"

class MaintenanceLog(db.Model):
    __tablename__ = 'maintenance_logs'
    id = db.Column('MaintenanceLogID', db.Integer, primary_key=True)
    equipment_id = db.Column('EquipmentID', db.Integer, db.ForeignKey('equipment.EquipmentID'), nullable=False)
    maintenance_date = db.Column('MaintenanceDate', db.DateTime, default=datetime.utcnow)
    technician_name = db.Column('TechnicianName', db.String(100))
    notes = db.Column('Notes', db.Text)

    def __repr__(self):
        return f"<MaintenanceLog {self.id} Equipment {self.equipment_id}>"

##########################################
# 7. Shipping and Logistics
##########################################

class Shipment(db.Model):
    __tablename__ = 'shipments'
    id = db.Column('ShipmentID', db.Integer, primary_key=True)
    carrier_name = db.Column('CarrierName', db.String(100))
    tracking_number = db.Column('TrackingNumber', db.String(100), unique=True)
    shipment_date = db.Column('ShipmentDate', db.DateTime, default=datetime.utcnow)
    estimated_arrival = db.Column('EstimatedArrival', db.DateTime)

    # Link to a customer for address info instead of storing it in each detail
    customer_id = db.Column('CustomerID', db.Integer, db.ForeignKey('customers.CustomerID'))
    customer = db.relationship('Customer', backref='shipments', lazy=True)

    details = db.relationship('ShipmentDetail', backref='shipment', lazy=True)

    def __repr__(self):
        return f"<Shipment {self.id} Tracking {self.tracking_number}>"

class ShipmentDetail(db.Model):
    __tablename__ = 'shipment_details'
    id = db.Column('ShipmentDetailID', db.Integer, primary_key=True)
    shipment_id = db.Column('ShipmentID', db.Integer, db.ForeignKey('shipments.ShipmentID'), nullable=False)
    item_id = db.Column('ItemID', db.Integer, db.ForeignKey('items.ItemID'), nullable=False)
    quantity_shipped = db.Column('QuantityShipped', db.Integer, nullable=False)

    __table_args__ = (
        CheckConstraint('QuantityShipped > 0', name='chk_shipment_detail_qty_shipped_positive'),
    )

    def __repr__(self):
        return f"<ShipmentDetail {self.id} Shipment {self.shipment_id} Item {self.item_id}>"

##########################################
# 8. Advanced User Permissions (RBAC)
##########################################

class Permission(db.Model):
    __tablename__ = 'permissions'
    id = db.Column('PermissionID', db.Integer, primary_key=True)
    permission_name = db.Column('PermissionName', db.String(100), unique=True, nullable=False)

    def __repr__(self):
        return f"<Permission {self.permission_name}>"

class RolePermission(db.Model):
    __tablename__ = 'role_permissions'
    role_id = db.Column('RoleID', db.Integer, db.ForeignKey('roles.id'), primary_key=True)
    permission_id = db.Column('PermissionID', db.Integer, db.ForeignKey('permissions.PermissionID'), primary_key=True)

##########################################
# 9. Document Management
##########################################

class Document(db.Model):
    __tablename__ = 'documents'
    id = db.Column('DocumentID', db.Integer, primary_key=True)
    title = db.Column('Title', db.String(200), nullable=False)
    file_path = db.Column('FilePath', db.String(255), nullable=False)
    category = db.Column(document_category_enum, default='Other')  # e.g., 'Recipe', 'Certification'
    uploaded_by = db.Column('UploadedBy', db.Integer, db.ForeignKey('users.id'))
    upload_date = db.Column('UploadDate', db.DateTime, default=datetime.utcnow)

    uploader = db.relationship('User', backref='documents', lazy=True)

    def __repr__(self):
        return f"<Document {self.title}>"

##########################################
# 10. Production Planning & Scheduling
##########################################

class ProductionRun(db.Model):
    __tablename__ = 'production_runs'
    id = db.Column('ProductionRunID', db.Integer, primary_key=True)
    planned_start_date = db.Column('PlannedStartDate', db.DateTime)
    planned_end_date = db.Column('PlannedEndDate', db.DateTime)
    status = db.Column(production_run_status_enum, default='Planned')
    responsible_user_id = db.Column('ResponsibleUserID', db.Integer, db.ForeignKey('users.id'))

    details = db.relationship('ProductionRunDetail', backref='production_run', lazy=True)
    responsible_user = db.relationship('User', backref='production_runs', lazy=True)

    def __repr__(self):
        return f"<ProductionRun {self.id} Status {self.status}>"

class ProductionRunDetail(db.Model):
    __tablename__ = 'production_run_details'
    id = db.Column('RunDetailID', db.Integer, primary_key=True)
    production_run_id = db.Column('ProductionRunID', db.Integer, db.ForeignKey('production_runs.ProductionRunID'), nullable=False)
    item_id = db.Column('ItemID', db.Integer, db.ForeignKey('items.ItemID'), nullable=False)
    quantity_planned = db.Column('QuantityPlanned', db.Integer, nullable=False)
    bom_id = db.Column('BOMID', db.Integer, db.ForeignKey('bom.BOMID'))  # If relevant

    item = db.relationship('Item', backref='production_run_details', lazy=True)
    bom = db.relationship('BOM', backref='production_run_details', lazy=True)

    __table_args__ = (
        CheckConstraint('QuantityPlanned > 0', name='chk_production_run_detail_qty_planned_positive'),
    )

    def __repr__(self):
        return f"<ProductionRunDetail {self.id} Run {self.production_run_id} Item {self.item_id}>"

##########################################
# System Settings, Roles, and User Management
##########################################

class SystemSettings(db.Model):
    __tablename__ = 'system_settings'
    id = db.Column(db.Integer, primary_key=True)
    system_title = db.Column(db.String(100), default="EL7amla")
    theme_color = db.Column(db.String(50), default="blue")
    background_color = db.Column(db.String(50), default="blue")
    login_bg_image = db.Column(db.String(255), default="/static/uploads/20250227_154020_el7amlaDesktop_Wallpaper.png")
    logo_image = db.Column(db.String(255), default="/static/uploads/20250227_153609_png")
    sidebar_color = db.Column(db.String(50), default="blue")
    font_size = db.Column(db.String(20), default="medium")
    rtl_enabled = db.Column(db.Boolean, default=True)
    
    visible_widgets = db.Column(db.JSON, default={
        "users_card": True,
        "revenue_card": True,
        "sessions_card": True,
        "conversion_card": True,
        "sales_chart": True,
        "users_chart": True,
        "activities": True,
        "recent_orders": True,
        "top_products": True
    })
    
    dashboard_layout = db.Column(db.JSON, default={
        "layout_type": "grid",
        "columns": 4,
        "spacing": "normal",
        "widget_order": [
            "users_card",
            "revenue_card",
            "sessions_card",
            "conversion_card",
            "sales_chart",
            "users_chart",
            "activities",
            "recent_orders",
            "top_products"
        ],
        "widget_sizes": {
            "sales_chart": "large",
            "users_chart": "large",
            "activities": "medium"
        }
    })
    
    custom_colors = db.Column(db.JSON, default={
        "primary": "#4F46E5",
        "secondary": "#6B7280",
        "accent": "#10B981",
        "success": "#059669",
        "warning": "#D97706",
        "error": "#DC2626",
        "info": "#3B82F6"
    })

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def get_settings():
        settings = SystemSettings.query.first()
        if not settings:
            settings = SystemSettings()
            db.session.add(settings)
            db.session.commit()
        return settings

    def update_settings(self, settings_data):
        for key, value in settings_data.items():
            if hasattr(self, key):
                # If it's a nested dict, merge instead of overwrite
                if isinstance(value, dict) and getattr(self, key) is not None:
                    current_value = getattr(self, key)
                    current_value.update(value)
                    value = current_value
                setattr(self, key, value)
        self.updated_at = datetime.utcnow()
        db.session.commit()
        return self

    def to_dict(self):
        return {
            'id': self.id,
            'system_title': self.system_title,
            'theme_color': self.theme_color,
            'background_color': self.background_color,
            'sidebar_color': self.sidebar_color,
            'font_size': self.font_size,
            'rtl_enabled': self.rtl_enabled,
            'visible_widgets': self.visible_widgets,
            'dashboard_layout': self.dashboard_layout,
            'custom_colors': self.custom_colors,
            'logo_image': self.logo_image,
            'login_bg_image': self.login_bg_image
        }

class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True)

    # Removed JSON permissions; use RolePermission table
    users = db.relationship('User', backref='role', lazy=True)
    
    def __repr__(self):
        return f'<Role {self.name}>'

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    is_active = db.Column(db.Boolean, default=True)

    phone = db.Column(db.String(20))
    birthdate = db.Column(db.Date)
    hire_date = db.Column(db.Date)
    identification_number = db.Column(db.String(50), unique=True)
    gender = db.Column(db.String(10))
    nationality = db.Column(db.String(50))
    address = db.Column(db.Text)
    profile_image = db.Column(db.String(255))
    id_image = db.Column(db.String(255))
    cv_file = db.Column(db.String(255))
    department = db.Column(db.String(50))
    position = db.Column(db.String(50))
    salary = db.Column(db.Float)
    emergency_contact = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def has_permission(self, permission_name):
        """
        Example check using RolePermission:
          1) Find the role's ID
          2) Check if there's a RolePermission with that role_id and a Permission whose name == permission_name
        """
        if not self.role:
            return False
        role_perms = RolePermission.query.filter_by(role_id=self.role.id).all()
        # Collect the permission_ids
        perm_ids = [rp.permission_id for rp in role_perms]
        # See if any of those match the requested permission
        perms = Permission.query.filter(Permission.id.in_(perm_ids)).all()
        return any(p.permission_name == permission_name for p in perms)

    def update_profile(self, data):
        if data.get('phone'):
            self.phone = data['phone']
        if data.get('identification_number'):
            self.identification_number = data['identification_number']
        if data.get('gender'):
            self.gender = data['gender']
        if data.get('nationality'):
            self.nationality = data['nationality']
        if data.get('address'):
            self.address = data['address']
        if data.get('department'):
            self.department = data['department']
        if data.get('position'):
            self.position = data['position']

        if data.get('birthdate'):
            try:
                self.birthdate = datetime.strptime(data['birthdate'], '%Y-%m-%d').date()
            except ValueError:
                pass
    
        if data.get('hire_date'):
            try:
                self.hire_date = datetime.strptime(data['hire_date'], '%Y-%m-%d').date()
            except ValueError:
                pass

        if data.get('salary'):
            try:
                self.salary = float(data['salary'])
            except ValueError:
                pass

        if data.get('emergency_contact'):
            self.emergency_contact = {
                'name': data['emergency_contact'].get('name', ''),
                'phone': data['emergency_contact'].get('phone', ''),
                'relation': data['emergency_contact'].get('relation', '')
            }

        if data.get('profile_image'):
            self.profile_image = data['profile_image']
        if data.get('id_image'):
            self.id_image = data['id_image']
        if data.get('cv_file'):
            self.cv_file = data['cv_file']

        self.updated_at = datetime.utcnow()
        db.session.commit()

##########################################
# Initialize the Database (for testing)
##########################################

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    print("Database tables created successfully.")
