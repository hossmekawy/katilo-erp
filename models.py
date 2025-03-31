from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from sqlalchemy import Enum as SAEnum, CheckConstraint, UniqueConstraint

db = SQLAlchemy()

##############################################################################
# ENUMERATIONS
##############################################################################

transaction_type_enum = SAEnum('IN', 'OUT', 'TRANSFER', name='transaction_type_enum')
purchase_order_status_enum = SAEnum('Pending', 'Approved', 'Received', 'Cancelled', name='purchase_order_status_enum')
sales_order_status_enum = SAEnum('Pending', 'Shipped', 'Delivered', 'Cancelled', name='sales_order_status_enum')
qc_status_enum = SAEnum('Passed', 'Failed', 'Retest', name='qc_status_enum')
production_run_status_enum = SAEnum('Planned', 'In Progress', 'Completed', name='production_run_status_enum')
document_category_enum = SAEnum('Recipe', 'Certification', 'Manual', 'Other', name='document_category_enum')

# Additional enumerations for new features
waste_reason_enum = SAEnum('Expired', 'Spoiled', 'Damaged', 'Other', name='waste_reason_enum')
compliance_status_enum = SAEnum('Passed', 'Warning', 'Failed', name='compliance_status_enum')
movement_type_enum = SAEnum('ScannedIn', 'ScannedOut', name='movement_type_enum')
device_type_enum = SAEnum('RFIDScanner', 'TemperatureSensor', 'Other', name='device_type_enum')
subscription_status_enum = SAEnum('Active', 'Paused', 'Canceled', name='subscription_status_enum')
alert_status_enum = SAEnum('Pending', 'Resolved', name='alert_status_enum')
alert_type_enum = SAEnum('FakeOrder', 'ExcessiveRefunds', 'Other', name='alert_type_enum')
action_type_enum = SAEnum('UnauthorizedAccess', 'InventoryChange', 'Login', 'Other', name='action_type_enum')
recurring_frequency_enum = SAEnum('Daily', 'Weekly', 'Monthly', 'Yearly', name='recurring_frequency_enum')
return_status_enum = SAEnum('Pending', 'Approved', 'Denied', name='return_status_enum')
return_reason_enum = SAEnum('Defective', 'WrongItem', 'Damaged', 'Other', name='return_reason_enum')
interaction_type_enum = SAEnum('Call', 'Email', 'Visit', 'Other', name='interaction_type_enum')

##############################################################################
# CORE ENTITIES AND RELATIONSHIPS
##############################################################################

class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column('CategoryID', db.Integer, primary_key=True)
    name = db.Column('CategoryName', db.String(50), nullable=False)
    description = db.Column('Description', db.String(255))
    
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
    
    inventories = db.relationship('Inventory', backref='item', lazy=True)
    bom_final = db.relationship('BOM', backref='final_product', lazy=True,
                                foreign_keys='BOM.final_product_id')
    bom_components = db.relationship('BOMDetail', backref='component_item', lazy=True,
                                     foreign_keys='BOMDetail.component_item_id')
    transactions = db.relationship('InventoryTransaction', backref='item', lazy=True)
    slots = db.relationship('WarehouseSlot', backref='item_ref', lazy=True)

    def __repr__(self):
        return f'<Item {self.name}>'

class Warehouse(db.Model):
    __tablename__ = 'warehouses'
    id = db.Column('WarehouseID', db.Integer, primary_key=True)
    name = db.Column('WarehouseName', db.String(100), nullable=False)
    location = db.Column('Location', db.String(255))
    capacity = db.Column('Capacity', db.Integer)
    contact_info = db.Column('ContactInfo', db.String(255))
    item_location = db.Column('ItemLocation', db.String(100))  # Example custom field
    
    inventories = db.relationship('Inventory', backref='warehouse', lazy=True)
    transactions = db.relationship('InventoryTransaction', backref='warehouse', lazy=True)
    sections = db.relationship('WarehouseSection', backref='warehouse', lazy=True)
    
    def __repr__(self):
        return f'<Warehouse {self.name}>'

##############################################################################
# WAREHOUSE LAYOUT (SECTIONS & SLOTS)
##############################################################################

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

    __table_args__ = (
        UniqueConstraint('section_id', 'row_number', 'column_number', name='uq_slot_position'),
        CheckConstraint('quantity >= 0', name='chk_slot_qty_nonnegative'),
    )

    def __repr__(self):
        return (f"<WarehouseSlot (Section {self.section_id}, "
                f"Row {self.row_number}, Col {self.column_number}, "
                f"Item {self.item_id}, Qty {self.quantity})>")

##############################################################################
# INVENTORY & TRANSACTIONS
##############################################################################

class Inventory(db.Model):
    __tablename__ = 'inventory'
    id = db.Column('InventoryID', db.Integer, primary_key=True)
    item_id = db.Column('ItemID', db.Integer, db.ForeignKey('items.ItemID'), index=True, nullable=False)
    warehouse_id = db.Column('WarehouseID', db.Integer, db.ForeignKey('warehouses.WarehouseID'), index=True, nullable=False)
    quantity = db.Column('Quantity', db.Integer, nullable=False)
    last_updated = db.Column('LastUpdated', db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
    transaction_type = db.Column(transaction_type_enum, nullable=False)
    quantity = db.Column('Quantity', db.Integer, nullable=False)
    transaction_date = db.Column('TransactionDate', db.DateTime, default=datetime.utcnow)
    reference = db.Column('Reference', db.String(255))

    __table_args__ = (
        CheckConstraint('Quantity > 0', name='chk_transaction_qty_positive'),
    )

    def __repr__(self):
        return (f'<Transaction {self.transaction_type} of Item {self.item_id} '
                f'in Warehouse {self.warehouse_id} (Qty: {self.quantity})>')

#########################################################################################
#################  #  Returns & Refunds Management  ####################################
#########################################################################################
class ProductReturn(db.Model):
    __tablename__ = 'product_returns'
    id = db.Column(db.Integer, primary_key=True)
    sales_order_id = db.Column(db.Integer, db.ForeignKey('sales_orders.SalesOrderID'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.ItemID'), nullable=False)
    return_reason = db.Column(return_reason_enum, default='Other')
    return_status = db.Column(return_status_enum, default='Pending')
    refund_amount = db.Column(db.Float, default=0.0)
    return_date = db.Column(db.DateTime, default=datetime.utcnow)

    sales_order = db.relationship('SalesOrder', backref='product_returns', lazy=True)
    item = db.relationship('Item', backref='product_returns', lazy=True)

    def __repr__(self):
        return f"<ProductReturn {self.id} SO {self.sales_order_id} Item {self.item_id}>"









##############################################################################
# MANUFACTURING (BOM)
##############################################################################

class BOM(db.Model):
    __tablename__ = 'bom'
    id = db.Column('BOMID', db.Integer, primary_key=True)
    final_product_id = db.Column('FinalProductID', db.Integer, db.ForeignKey('items.ItemID'), nullable=False)
    description = db.Column('Description', db.Text)
    created_at = db.Column('CreatedAt', db.DateTime, default=datetime.utcnow)
    updated_at = db.Column('UpdatedAt', db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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


##############################################################################
# PURCHASE ORDERS (PO)
##############################################################################

class PurchaseOrder(db.Model):
    __tablename__ = 'purchase_orders'
    id = db.Column('POID', db.Integer, primary_key=True)
    supplier_id = db.Column('SupplierID', db.Integer, db.ForeignKey('suppliers.SupplierID'), nullable=False)
    order_date = db.Column('OrderDate', db.DateTime, default=datetime.utcnow)
    status = db.Column(purchase_order_status_enum, default='Pending')
    total_amount = db.Column('TotalAmount', db.Float)

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

##############################################################################
# SUPPLIER MANAGEMENT
##############################################################################
class SupplierPayment(db.Model):
    __tablename__ = 'supplier_payments'
    id = db.Column('PaymentID', db.Integer, primary_key=True)
    supplier_id = db.Column('SupplierID', db.Integer, db.ForeignKey('suppliers.SupplierID'), nullable=False)
    amount = db.Column('Amount', db.Float, nullable=False)
    payment_date = db.Column('PaymentDate', db.DateTime, default=datetime.utcnow)
    payment_method = db.Column('PaymentMethod', db.String(50))
    reference = db.Column('Reference', db.String(100))
    notes = db.Column('Notes', db.Text)
    created_by = db.Column('CreatedBy', db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column('CreatedAt', db.DateTime, default=datetime.utcnow)
    
    # Relationships
    supplier = db.relationship('Supplier', backref='payments', lazy=True)
    created_by_user = db.relationship('User', backref='supplier_payments_created', lazy=True)
    
    def __repr__(self):
        return f"<SupplierPayment {self.id} Supplier {self.supplier_id} Amount {self.amount}>"
    
class SupplierLedgerEntry(db.Model):
    __tablename__ = 'supplier_ledger'
    id = db.Column('EntryID', db.Integer, primary_key=True)
    supplier_id = db.Column('SupplierID', db.Integer, db.ForeignKey('suppliers.SupplierID'), nullable=False)
    entry_date = db.Column('EntryDate', db.DateTime, default=datetime.utcnow)
    description = db.Column('Description', db.String(255))
    reference_type = db.Column('ReferenceType', db.String(50))  # 'purchase_order', 'payment', etc.
    reference_id = db.Column('ReferenceID', db.Integer)
    debit = db.Column('Debit', db.Float, default=0)  # Amount owed to supplier
    credit = db.Column('Credit', db.Float, default=0)  # Amount paid to supplier
    
    # Relationships
    supplier = db.relationship('Supplier', backref='ledger_entries', lazy=True)
    
    def __repr__(self):
        return f"<SupplierLedgerEntry {self.id} Supplier {self.supplier_id} Debit {self.debit} Credit {self.credit}>"

class Supplier(db.Model):
    __tablename__ = 'suppliers'
    id = db.Column('SupplierID', db.Integer, primary_key=True)
    supplier_name = db.Column('SupplierName', db.String(100), nullable=False)
    contact_info = db.Column('ContactInfo', db.Text)
    payment_terms = db.Column('PaymentTerms', db.String(50))
    rating = db.Column('Rating', db.Float)
    email = db.Column('Email', db.String(100))
    phone = db.Column('Phone', db.String(50))
    address = db.Column('Address', db.Text)
    tax_id = db.Column('TaxID', db.String(50))
    website = db.Column('Website', db.String(100))
    contact_person = db.Column('ContactPerson', db.String(100))
    notes = db.Column('Notes', db.Text)
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



##############################################################################
# SALES ORDERS AND CUSTOMER MANAGEMENT
##############################################################################

class Customer(db.Model):
    __tablename__ = 'customers'
    id = db.Column('CustomerID', db.Integer, primary_key=True)
    customer_name = db.Column('CustomerName', db.String(100), nullable=False)
    contact_info = db.Column('ContactInfo', db.Text)
    billing_address = db.Column('BillingAddress', db.Text)
    shipping_address = db.Column('ShippingAddress', db.Text)

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

##############################################################################
# LOT/BATCH TRACKING AND EXPIRY MANAGEMENT
##############################################################################

class Batch(db.Model):
    __tablename__ = 'batches'
    id = db.Column('BatchID', db.Integer, primary_key=True)
    item_id = db.Column('ItemID', db.Integer, db.ForeignKey('items.ItemID'), nullable=False)
    lot_number = db.Column('LotNumber', db.String(100), unique=True, nullable=False)
    production_date = db.Column('ProductionDate', db.DateTime)
    expiry_date = db.Column('ExpiryDate', db.DateTime)
    quantity = db.Column('Quantity', db.Integer, nullable=False)

    item = db.relationship('Item', backref='batches', lazy=True)
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
    )

    def __repr__(self):
        return f"<BatchSlot {self.id} Batch {self.batch_id} Slot {self.slot_id}>"

##############################################################################
# QUALITY CONTROL (QC) & INSPECTIONS
##############################################################################

class QualityCheck(db.Model):
    __tablename__ = 'quality_checks'
    id = db.Column('QCID', db.Integer, primary_key=True)
    batch_id = db.Column('BatchID', db.Integer, db.ForeignKey('batches.BatchID'), nullable=False)
    check_date = db.Column('CheckDate', db.DateTime, default=datetime.utcnow)
    inspector_name = db.Column('InspectorName', db.String(100))
    status = db.Column(qc_status_enum, default='Retest')

    batch = db.relationship('Batch', backref='quality_checks', lazy=True)
    qc_results = db.relationship('QualityCheckResult', backref='quality_check', lazy=True)

    def __repr__(self):
        return f"<QualityCheck {self.id} Batch {self.batch_id}>"

class QualityCheckResult(db.Model):
    __tablename__ = 'quality_check_results'
    id = db.Column(db.Integer, primary_key=True)
    qc_id = db.Column(db.Integer, db.ForeignKey('quality_checks.QCID'), nullable=False)
    param_name = db.Column(db.String(100), nullable=False)
    param_value = db.Column(db.String(100))

    def __repr__(self):
        return f"<QualityCheckResult {self.id} QC {self.qc_id} {self.param_name}={self.param_value}>"

class QCParameter(db.Model):
    __tablename__ = 'qc_parameters'
    id = db.Column('QCParamID', db.Integer, primary_key=True)
    param_name = db.Column('ParamName', db.String(100), nullable=False)
    reference_range = db.Column('ReferenceRange', db.String(50))

    def __repr__(self):
        return f"<QCParameter {self.param_name}>"

##############################################################################
# EQUIPMENT & MAINTENANCE
##############################################################################

class Equipment(db.Model):
    __tablename__ = 'equipment'
    id = db.Column('EquipmentID', db.Integer, primary_key=True)
    name = db.Column('Name', db.String(100), nullable=False)
    serial_number = db.Column('SerialNumber', db.String(100), unique=True)
    location = db.Column('Location', db.String(255))
    last_maintenance_date = db.Column('LastMaintenanceDate', db.DateTime)
    maintenance_interval = db.Column('MaintenanceInterval', db.Integer)

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

##############################################################################
# SHIPPING AND LOGISTICS
##############################################################################

class Shipment(db.Model):
    __tablename__ = 'shipments'
    id = db.Column('ShipmentID', db.Integer, primary_key=True)
    carrier_name = db.Column('CarrierName', db.String(100))
    tracking_number = db.Column('TrackingNumber', db.String(100), unique=True)
    shipment_date = db.Column('ShipmentDate', db.DateTime, default=datetime.utcnow)
    estimated_arrival = db.Column('EstimatedArrival', db.DateTime)

    # Link to a customer for address info
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

##############################################################################
# ADVANCED USER PERMISSIONS (RBAC)
##############################################################################

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

##############################################################################
# DOCUMENT MANAGEMENT
##############################################################################

class Document(db.Model):
    __tablename__ = 'documents'
    id = db.Column('DocumentID', db.Integer, primary_key=True)
    title = db.Column('Title', db.String(200), nullable=False)
    file_path = db.Column('FilePath', db.String(255), nullable=False)
    category = db.Column(document_category_enum, default='Other')
    uploaded_by = db.Column('UploadedBy', db.Integer, db.ForeignKey('users.id'))
    upload_date = db.Column('UploadDate', db.DateTime, default=datetime.utcnow)

    uploader = db.relationship('User', backref='documents', lazy=True)

    def __repr__(self):
        return f"<Document {self.title}>"

##############################################################################
# PRODUCTION PLANNING & SCHEDULING
##############################################################################

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
    bom_id = db.Column('BOMID', db.Integer, db.ForeignKey('bom.BOMID'))

    item = db.relationship('Item', backref='production_run_details', lazy=True)
    bom = db.relationship('BOM', backref='production_run_details', lazy=True)

    __table_args__ = (
        CheckConstraint('QuantityPlanned > 0', name='chk_production_run_detail_qty_planned_positive'),
    )

    def __repr__(self):
        return f"<ProductionRunDetail {self.id} Run {self.production_run_id} Item {self.item_id}>"

##############################################################################
# SYSTEM SETTINGS, ROLES, AND USER MANAGEMENT
##############################################################################

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

    users = db.relationship('User', backref='role', lazy=True)
    
    def __repr__(self):
        return f'<Role {self.name}>'

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
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
        if not self.role:
            return False
        role_perms = RolePermission.query.filter_by(role_id=self.role.id).all()
        perm_ids = [rp.permission_id for rp in role_perms]
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

##############################################################################
# ADDITIONAL ADVANCED FEATURES
##############################################################################

# 1. Advanced Inventory Forecasting & Demand Planning

class DemandForecast(db.Model):
    __tablename__ = 'demand_forecasts'
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.ItemID'), nullable=False)
    forecasted_quantity = db.Column(db.Integer, default=0)
    forecast_date = db.Column(db.DateTime, default=datetime.utcnow)
    accuracy_rate = db.Column(db.Float, default=0.0)  # 0-100 or 0-1

    __table_args__ = (
        CheckConstraint('forecasted_quantity >= 0', name='chk_forecast_qty_nonnegative'),
        CheckConstraint('accuracy_rate >= 0', name='chk_accuracy_rate_positive'),
    )

    item = db.relationship('Item', backref='demand_forecasts', lazy=True)

    def __repr__(self):
        return f"<DemandForecast {self.id} Item {self.item_id} Qty {self.forecasted_quantity}>"

class InventoryReplenishmentPlan(db.Model):
    __tablename__ = 'inventory_replenishment_plans'
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.ItemID'), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.SupplierID'))
    recommended_order_quantity = db.Column(db.Integer, default=0)
    replenishment_date = db.Column(db.DateTime)
    status = db.Column(db.String(50), default='Pending')  # or use an Enum

    __table_args__ = (
        CheckConstraint('recommended_order_quantity >= 0', name='chk_replenish_qty_nonnegative'),
    )

    item = db.relationship('Item', backref='replenishment_plans', lazy=True)
    supplier = db.relationship('Supplier', backref='replenishment_plans', lazy=True)

    def __repr__(self):
        return f"<ReplenishPlan {self.id} Item {self.item_id} Qty {self.recommended_order_quantity}>"

# 2. Employee Shift & Productivity Tracking

class EmployeeShift(db.Model):
    __tablename__ = 'employee_shifts'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    shift_start = db.Column(db.DateTime, nullable=False)
    shift_end = db.Column(db.DateTime)
    role_during_shift = db.Column(db.String(50))  # e.g., Packaging, Production

    user = db.relationship('User', backref='shifts', lazy=True)

    def __repr__(self):
        return f"<EmployeeShift {self.id} User {self.user_id}>"

class ProductionEfficiency(db.Model):
    __tablename__ = 'production_efficiencies'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    production_run_id = db.Column(db.Integer, db.ForeignKey('production_runs.ProductionRunID'))
    items_produced = db.Column(db.Integer, default=0)
    errors_made = db.Column(db.Integer, default=0)
    efficiency_score = db.Column(db.Float, default=0.0)

    __table_args__ = (
        CheckConstraint('items_produced >= 0', name='chk_items_produced_nonnegative'),
        CheckConstraint('errors_made >= 0', name='chk_errors_made_nonnegative'),
    )

    user = db.relationship('User', backref='production_efficiencies', lazy=True)
    production_run = db.relationship('ProductionRun', backref='efficiencies', lazy=True)

    def __repr__(self):
        return f"<ProductionEfficiency {self.id} User {self.user_id}>"

# 3. Production Waste & Loss Tracking

# class WasteTracking(db.Model):
#     __tablename__ = 'waste_tracking'
#     id = db.Column(db.Integer, primary_key=True)
#     item_id = db.Column(db.Integer, db.ForeignKey('items.ItemID'), nullable=False)
#     batch_id = db.Column(db.Integer, db.ForeignKey('batches.BatchID'))
#     quantity_wasted = db.Column(db.Integer, default=0)
#     waste_reason = db.Column(waste_reason_enum, default='Other')
#     waste_date = db.Column(db.DateTime, default=datetime.utcnow)
#     responsible_employee_id = db.Column(db.Integer, db.ForeignKey('users.id'))

#     __table_args__ = (
#         CheckConstraint('quantity_wasted >= 0', name='chk_waste_qty_nonnegative'),
#     )

#     item = db.relationship('Item', backref='waste_entries', lazy=True)
#     batch = db.relationship('Batch', backref='waste_entries', lazy=True)
#     responsible_employee = db.relationship('User', backref='waste_entries', lazy=True)

#     def __repr__(self):
#         return f"<WasteTracking {self.id} Item {self.item_id} QtyWasted {self.quantity_wasted}>"

# 4. Compliance & Food Safety Audits

# class AuditRecord(db.Model):
#     __tablename__ = 'audit_records'
#     id = db.Column(db.Integer, primary_key=True)
#     auditor_name = db.Column(db.String(100))
#     audit_date = db.Column(db.DateTime, default=datetime.utcnow)
#     compliance_status = db.Column(compliance_status_enum, default='Warning')
#     notes = db.Column(db.Text)
#     next_audit_date = db.Column(db.DateTime)

#     def __repr__(self):
#         return f"<AuditRecord {self.id} Auditor {self.auditor_name}>"

# class TemperatureLog(db.Model):
#     __tablename__ = 'temperature_logs'
#     id = db.Column(db.Integer, primary_key=True)
#     warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.WarehouseID'), nullable=False)
#     temperature = db.Column(db.Float)
#     recorded_at = db.Column(db.DateTime, default=datetime.utcnow)

#     warehouse = db.relationship('Warehouse', backref='temperature_logs', lazy=True)

#     def __repr__(self):
#         return f"<TemperatureLog {self.id} Warehouse {self.warehouse_id} Temp {self.temperature}>"

# 5. IoT Integration for Smart Warehouses

# class IoTDevice(db.Model):
#     __tablename__ = 'iot_devices'
#     id = db.Column(db.Integer, primary_key=True)
#     device_type = db.Column(device_type_enum, default='Other')
#     warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.WarehouseID'))
#     location_description = db.Column(db.String(255))

#     warehouse = db.relationship('Warehouse', backref='iot_devices', lazy=True)

#     def __repr__(self):
#         return f"<IoTDevice {self.id} Type {self.device_type}>"

# class SmartInventoryLog(db.Model):
#     __tablename__ = 'smart_inventory_logs'
#     id = db.Column(db.Integer, primary_key=True)
#     item_id = db.Column(db.Integer, db.ForeignKey('items.ItemID'), nullable=False)
#     warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.WarehouseID'), nullable=False)
#     movement_type = db.Column(movement_type_enum, default='ScannedIn')
#     device_id = db.Column(db.Integer, db.ForeignKey('iot_devices.id'))
#     timestamp = db.Column(db.DateTime, default=datetime.utcnow)

#     item = db.relationship('Item', backref='smart_logs', lazy=True)
#     warehouse = db.relationship('Warehouse', backref='smart_logs', lazy=True)
#     device = db.relationship('IoTDevice', backref='smart_logs', lazy=True)

#     def __repr__(self):
#         return f"<SmartInventoryLog {self.id} Item {self.item_id} {self.movement_type}>"




# 6. Customer & Distributor Relationship Management (CRM)

class CustomerInteraction(db.Model):
    __tablename__ = 'customer_interactions'
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.CustomerID'), nullable=False)
    interaction_type = db.Column(interaction_type_enum, default='Other')
    notes = db.Column(db.Text)
    follow_up_date = db.Column(db.DateTime)

    customer = db.relationship('Customer', backref='interactions', lazy=True)

    def __repr__(self):
        return f"<CustomerInteraction {self.id} Customer {self.customer_id}>"

class DiscountPromotion(db.Model):
    __tablename__ = 'discount_promotions'
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.CustomerID'))  # NULL if general
    discount_percentage = db.Column(db.Float, default=0.0)
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    end_date = db.Column(db.DateTime)
    min_order_quantity = db.Column(db.Integer, default=0)

    customer = db.relationship('Customer', backref='discount_promotions', lazy=True)

    def __repr__(self):
        return f"<DiscountPromotion {self.id} % {self.discount_percentage}>"

# 7. Supplier Performance Tracking

# class SupplierPerformance(db.Model):
#     __tablename__ = 'supplier_performance'
#     id = db.Column(db.Integer, primary_key=True)
#     supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.SupplierID'), nullable=False)
#     delivery_time_rating = db.Column(db.Integer, default=3)  # 1-5
#     product_quality_rating = db.Column(db.Integer, default=3)  # 1-5
#     communication_rating = db.Column(db.Integer, default=3)  # 1-5
#     notes = db.Column(db.Text)

#     supplier = db.relationship('Supplier', backref='performance_records', lazy=True)

#     def __repr__(self):
#         return f"<SupplierPerformance {self.id} Supplier {self.supplier_id}>"


# # 9. Subscription & Auto-Ordering System

# class SubscriptionOrder(db.Model):
#     __tablename__ = 'subscription_orders'
#     id = db.Column(db.Integer, primary_key=True)
#     customer_id = db.Column(db.Integer, db.ForeignKey('customers.CustomerID'), nullable=False)
#     item_id = db.Column(db.Integer, db.ForeignKey('items.ItemID'), nullable=False)
#     recurring_frequency = db.Column(recurring_frequency_enum, default='Monthly')
#     next_delivery_date = db.Column(db.DateTime)
#     status = db.Column(subscription_status_enum, default='Active')

#     quantity_each_delivery = db.Column(db.Integer, default=1)

#     customer = db.relationship('Customer', backref='subscriptions', lazy=True)
#     item = db.relationship('Item', backref='subscriptions', lazy=True)

#     def __repr__(self):
#         return f"<SubscriptionOrder {self.id} Cust {self.customer_id} Item {self.item_id}>"

# 10. Fraud Detection & Security Logs

# class SecurityLog(db.Model):
#     __tablename__ = 'security_logs'
#     id = db.Column(db.Integer, primary_key=True)
#     user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
#     action_type = db.Column(action_type_enum, default='Other')
#     action_date = db.Column(db.DateTime, default=datetime.utcnow)
#     ip_address = db.Column(db.String(50))

#     user = db.relationship('User', backref='security_logs', lazy=True)

#     def __repr__(self):
#         return f"<SecurityLog {self.id} User {self.user_id} Action {self.action_type}>"

# class FraudAlert(db.Model):
#     __tablename__ = 'fraud_alerts'
#     id = db.Column(db.Integer, primary_key=True)
#     item_id = db.Column(db.Integer, db.ForeignKey('items.ItemID'))
#     unusual_transaction_id = db.Column(db.Integer, db.ForeignKey('inventory_transactions.TransactionID'))
#     alert_type = db.Column(alert_type_enum, default='Other')
#     reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
#     status = db.Column(alert_status_enum, default='Pending')
#     created_at = db.Column(db.DateTime, default=datetime.utcnow)

#     item = db.relationship('Item', backref='fraud_alerts', lazy=True)
#     unusual_transaction = db.relationship('InventoryTransaction', backref='fraud_alerts', lazy=True)
#     reviewer = db.relationship('User', backref='fraud_alerts', lazy=True)

#     def __repr__(self):
#         return f"<FraudAlert {self.id} Item {self.item_id} Txn {self.unusual_transaction_id}>"

##############################################################################
# INIT DB
##############################################################################

# Support Ticket System Models
class SupportTicket(db.Model):
    __tablename__ = 'support_tickets'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    subject = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    ticket_type = db.Column(db.String(50), default='general')  # general, technical, billing, etc.
    status = db.Column(db.String(50), default='open')  # open, in_progress, closed
    priority = db.Column(db.String(50), default='medium')  # low, medium, high, urgent
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='support_tickets', lazy=True)
    responses = db.relationship('TicketResponse', backref='ticket', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<SupportTicket {self.id}: {self.subject}>"

class TicketResponse(db.Model):
    __tablename__ = 'ticket_responses'
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('support_tickets.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    message = db.Column(db.Text, nullable=False)
    is_staff_response = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='ticket_responses', lazy=True)
    
    def __repr__(self):
        return f"<TicketResponse {self.id} for Ticket {self.ticket_id}>"

