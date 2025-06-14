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
category_type_enum = SAEnum('FinalProduct', 'Packaging', 'RawMaterial', 'IntermediateProduct', name='category_type_enum')
transaction_type_enum = SAEnum('IN', 'OUT', 'TRANSFER', name='transaction_type_enum')
purchase_order_status_enum = SAEnum('Pending', 'Approved', 'Received', 'Cancelled', name='purchase_order_status_enum')
sales_order_status_enum = SAEnum('Pending', 'Processing', 'Shipped', 'Delivered', 'Cancelled', name='sales_order_status_enum')
cost_update_source_enum = SAEnum('PurchaseOrder', 'SupplierUpdate', 'ManualUpdate', 'BOMCalculation', name='cost_update_source_enum')

qc_status_enum = SAEnum('Passed', 'Failed', 'Retest', name='qc_status_enum')
production_run_status_enum = SAEnum('Planned', 'In Progress', 'Completed', name='production_run_status_enum')
document_category_enum = SAEnum('Recipe', 'Certification', 'Manual', 'Other', name='document_category_enum')
report_type_enum = SAEnum(
    'Inventory', 'Transactions', 'Suppliers', 'SupplierAccounts',
    'Production', 'QualityControl', 'Warehouses', 'Items',
    'Categories', 'PurchaseOrders', 'BOM', 'Custom',
    name='report_type_enum'
)

report_status_enum = SAEnum(
    'Pending', 'Approved', 'Declined', 'Generated',
    name='report_status_enum'
)

report_format_enum = SAEnum(
    'PDF', 'Excel', 'CSV',
    name='report_format_enum'
)
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
packaging_status_enum = SAEnum('Pending', 'Completed', 'Cancelled', name='packaging_status_enum')
##############################################################################
# CORE ENTITIES AND RELATIONSHIPS
##############################################################################

class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column('CategoryID', db.Integer, primary_key=True)
    name = db.Column('CategoryName', db.String(50), nullable=False)
    description = db.Column('Description', db.String(255))
    category_type = db.Column(category_type_enum, default='RawMaterial')
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

    # Define weight and volume as properties
    _weight = 0
    _volume = 0

    inventories = db.relationship('Inventory', backref='item', lazy=True)
    bom_final = db.relationship('BOM', backref='final_product', lazy=True,
                                foreign_keys='BOM.final_product_id')
    bom_components = db.relationship('BOMDetail', backref='component_item', lazy=True,
                                     foreign_keys='BOMDetail.component_item_id')
    transactions = db.relationship('InventoryTransaction', backref='item', lazy=True)
    slots = db.relationship('WarehouseSlot', backref='item_ref', lazy=True)
    cost_history = db.relationship('ItemCostHistory', backref='item', lazy=True)

    # Weight property
    @property
    def weight(self):
        try:
            # Try to get the weight from the item_weights table
            from app import db
            from sqlalchemy import text
            result = db.session.execute(
                text("SELECT weight FROM item_weights WHERE item_id = :item_id"),
                {"item_id": self.id}
            ).fetchone()
            return result[0] if result else 0
        except Exception as e:
            print(f"Error getting weight for item {self.id}: {str(e)}")
            return 0

    # Volume property
    @property
    def volume(self):
        try:
            # Try to get the volume from the item_weights table
            from app import db
            from sqlalchemy import text
            result = db.session.execute(
                text("SELECT volume FROM item_weights WHERE item_id = :item_id"),
                {"item_id": self.id}
            ).fetchone()
            return result[0] if result else 0
        except Exception as e:
            print(f"Error getting volume for item {self.id}: {str(e)}")
            return 0

    # For backward compatibility
    @property
    def get_weight(self):
        return self.weight

    @property
    def get_volume(self):
        return self.volume

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
        CheckConstraint('"quantity" >= 0', name='chk_slot_qty_nonnegative'),
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
        CheckConstraint('"Quantity" >= 0', name='chk_inventory_qty_nonnegative'),

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
        CheckConstraint('"Quantity" > 0', name='chk_transaction_qty_positive'),

    )

    def __repr__(self):
        return (f'<Transaction {self.transaction_type} of Item {self.item_id} '
                f'in Warehouse {self.warehouse_id} (Qty: {self.quantity})>')

#########################################################################################
#################  #  Returns & Refunds Management  ####################################
#########################################################################################
class SalesReturn(db.Model):
    __tablename__ = 'sales_returns'
    id = db.Column(db.Integer, primary_key=True)
    sales_order_id = db.Column(db.Integer, db.ForeignKey('sales_orders.SalesOrderID'), nullable=False)
    invoice_id = db.Column(db.Integer, db.ForeignKey('sales_invoices.id'))
    return_date = db.Column(db.DateTime, default=datetime.utcnow)
    return_reason = db.Column(return_reason_enum, default='Other')
    return_status = db.Column(return_status_enum, default='Pending')
    total_refund_amount = db.Column(db.Float, default=0.0)
    cash_account_id = db.Column(db.Integer, db.ForeignKey('cash_accounts.id'))
    refund_method = db.Column(db.String(50), default='cash')  # cash, credit_card, bank_transfer, etc.
    refund_reference = db.Column(db.String(100))
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_at = db.Column(db.DateTime)

    # Relationships
    sales_order = db.relationship('SalesOrder', backref='returns', lazy=True)
    invoice = db.relationship('SalesInvoice', backref='returns', lazy=True)
    cash_account = db.relationship('CashAccount', backref='sales_returns', lazy=True)
    creator = db.relationship('User', foreign_keys=[created_by], backref='created_returns', lazy=True)
    approver = db.relationship('User', foreign_keys=[approved_by], backref='approved_returns', lazy=True)
    items = db.relationship('SalesReturnItem', backref='sales_return', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f"<SalesReturn {self.id} SO {self.sales_order_id} Amount {self.total_refund_amount}>"

class SalesReturnItem(db.Model):
    __tablename__ = 'sales_return_items'
    id = db.Column(db.Integer, primary_key=True)
    return_id = db.Column(db.Integer, db.ForeignKey('sales_returns.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.ItemID'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    refund_amount = db.Column(db.Float, nullable=False)
    return_reason = db.Column(return_reason_enum, default='Other')
    condition = db.Column(db.String(50), default='Good')  # Good, Damaged, Defective, etc.
    restocked = db.Column(db.Boolean, default=True)

    # Relationships
    item = db.relationship('Item', backref='return_items', lazy=True)

    def __repr__(self):
        return f"<SalesReturnItem {self.id} Item {self.item_id} Qty {self.quantity}>"









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
        CheckConstraint('"QuantityOrdered" > 0', name='chk_po_detail_qty_ordered_positive'),
        CheckConstraint('"QuantityReceived" >= 0', name='chk_po_detail_qty_received_nonnegative'),
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


class ItemCostHistory(db.Model):
    __tablename__ = 'item_cost_history'
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.ItemID'), nullable=False)
    previous_cost = db.Column(db.Float, nullable=False)
    new_cost = db.Column(db.Float, nullable=False)
    change_date = db.Column(db.DateTime, default=datetime.utcnow)
    source = db.Column(cost_update_source_enum, default='ManualUpdate')
    reference_id = db.Column(db.Integer)  # ID of PO, supplier, etc.
    reference_type = db.Column(db.String(50))  # 'purchase_order', 'supplier_item', etc.
    quantity = db.Column(db.Integer)  # For weighted average calculation
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Relationships
    user = db.relationship('User', backref='cost_updates', lazy=True)

    def __repr__(self):
        return f"<ItemCostHistory Item {self.item_id} from {self.previous_cost} to {self.new_cost}>"



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
    interactions = db.relationship('CustomerInteraction', backref='related_customer', lazy=True)



    def __repr__(self):
        return f"<Customer {self.customer_name}>"

class SalesOrder(db.Model):
    __tablename__ = 'sales_orders'
    id = db.Column('SalesOrderID', db.Integer, primary_key=True)
    customer_id = db.Column('CustomerID', db.Integer, db.ForeignKey('customers.CustomerID'), nullable=False)
    order_date = db.Column('OrderDate', db.DateTime, default=datetime.utcnow)
    status = db.Column(sales_order_status_enum, default='Pending')
    total_amount = db.Column('TotalAmount', db.Float)
    sales_rep_id = db.Column(db.Integer, db.ForeignKey('sales_representatives.id'), nullable=True)

    # Make these columns nullable to avoid errors if they don't exist in the database
    payment_method = db.Column(db.String(50), nullable=True)
    cash_account_id = db.Column(db.Integer, db.ForeignKey('cash_accounts.id'), nullable=True)
    payment_status = db.Column(db.String(20), nullable=True)
    payment_reference = db.Column(db.String(100), nullable=True)

    details = db.relationship('SalesOrderDetail', backref='sales_order', lazy=True)
    cash_account = db.relationship('CashAccount', backref='sales_orders', lazy=True, foreign_keys=[cash_account_id])

    def __repr__(self):
        return f"<SalesOrder {self.id} Customer {self.customer_id}>"

class SalesOrderDetail(db.Model):
    __tablename__ = 'sales_order_details'
    id = db.Column('SODetailID', db.Integer, primary_key=True)
    sales_order_id = db.Column('SalesOrderID', db.Integer, db.ForeignKey('sales_orders.SalesOrderID'), nullable=False)
    item_id = db.Column('ItemID', db.Integer, db.ForeignKey('items.ItemID'))
    item = db.relationship('Item', backref='order_details')
    quantity_ordered = db.Column('QuantityOrdered', db.Integer, nullable=False)
    unit_price = db.Column('UnitPrice', db.Float, nullable=False)
    quantity_shipped = db.Column('QuantityShipped', db.Integer, default=0)

    __table_args__ = (
        CheckConstraint('"QuantityOrdered" > 0', name='chk_so_detail_qty_ordered_positive'),
        CheckConstraint('"QuantityShipped" >= 0', name='chk_so_detail_qty_shipped_nonnegative'),
    )

    def __repr__(self):
        return f"<SODetail {self.id} SO {self.sales_order_id} Item {self.item_id}>"


class SalesRepresentative(db.Model):
    __tablename__ = 'sales_representatives'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    territory = db.Column(db.String(100))
    commission_rate = db.Column(db.Float, default=0.0)
    is_active = db.Column(db.Boolean, default=True)

    # Relationships
    user = db.relationship('User', backref='sales_rep_profile', lazy=True)
    # sales_orders = db.relationship('SalesOrder', backref='representative', lazy=True)

    def __repr__(self):
        return f"<SalesRepresentative {self.id} User {self.user_id}>"

# Sales Representative Route Planning Models
class RepresentativeRoute(db.Model):
    __tablename__ = 'representative_routes'
    id = db.Column(db.Integer, primary_key=True)
    representative_id = db.Column(db.Integer, db.ForeignKey('sales_representatives.id'), nullable=False)
    route_name = db.Column(db.String(100), nullable=False)
    route_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(50), default='Planned')  # Planned, In Progress, Completed, Cancelled
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    representative = db.relationship('SalesRepresentative', backref='routes', lazy=True)
    visits = db.relationship('CustomerVisit', backref='route', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f"<RepresentativeRoute {self.id} for Rep {self.representative_id}>"

class CustomerVisit(db.Model):
    __tablename__ = 'customer_visits'
    id = db.Column(db.Integer, primary_key=True)
    route_id = db.Column(db.Integer, db.ForeignKey('representative_routes.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.CustomerID'), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('sales_orders.SalesOrderID'))
    scheduled_time = db.Column(db.DateTime)
    actual_visit_time = db.Column(db.DateTime)
    status = db.Column(db.String(50), default='Pending')  # Pending, Completed, Missed, Rescheduled
    visit_notes = db.Column(db.Text)
    visit_outcome = db.Column(db.String(50))  # Sale, No Sale, Follow-up Required
    follow_up_date = db.Column(db.Date)
    location_latitude = db.Column(db.Float)
    location_longitude = db.Column(db.Float)

    # Relationships
    customer = db.relationship('Customer', backref='visits', lazy=True)
    order = db.relationship('SalesOrder', backref='related_visit', lazy=True)
    photos = db.relationship('VisitPhoto', backref='visit', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f"<CustomerVisit {self.id} for Customer {self.customer_id}>"

class VisitPhoto(db.Model):
    __tablename__ = 'visit_photos'
    id = db.Column(db.Integer, primary_key=True)
    visit_id = db.Column(db.Integer, db.ForeignKey('customer_visits.id'), nullable=False)
    photo_path = db.Column(db.String(255), nullable=False)
    upload_time = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.Text)

    def __repr__(self):
        return f"<VisitPhoto {self.id} for Visit {self.visit_id}>"

class AISuggestion(db.Model):
    __tablename__ = 'ai_suggestions'
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.ItemID'), nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.CategoryID'), nullable=True)
    suggestion_type = db.Column(db.String(50), nullable=False)  # NameImprovement, CategoryMismatch, ReorderLevelAdjustment, InventoryAnomaly
    suggestion_text = db.Column(db.Text, nullable=False)
    suggested_value = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), default='Pending')  # Pending, Applied, Dismissed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    item = db.relationship('Item', backref='ai_suggestions')
    category = db.relationship('Category', backref='ai_suggestions')

    def __repr__(self):
        return f'<AISuggestion {self.id}: {self.suggestion_type}>'

class RepresentativePerformance(db.Model):
    __tablename__ = 'representative_performance'
    id = db.Column(db.Integer, primary_key=True)
    representative_id = db.Column(db.Integer, db.ForeignKey('sales_representatives.id'), nullable=False)
    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)
    total_visits = db.Column(db.Integer, default=0)
    completed_visits = db.Column(db.Integer, default=0)
    total_sales = db.Column(db.Float, default=0.0)
    total_orders = db.Column(db.Integer, default=0)
    conversion_rate = db.Column(db.Float, default=0.0)  # Percentage of visits resulting in sales
    average_order_value = db.Column(db.Float, default=0.0)
    evaluation_score = db.Column(db.Float, default=0.0)  # 0-100 score
    evaluation_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    representative = db.relationship('SalesRepresentative', backref='performance_records', lazy=True)

    def __repr__(self):
        return f"<RepresentativePerformance {self.id} for Rep {self.representative_id}>"


class SalesInvoice(db.Model):
    __tablename__ = 'sales_invoices'
    id = db.Column(db.Integer, primary_key=True)
    sales_order_id = db.Column(db.Integer, db.ForeignKey('sales_orders.SalesOrderID'), nullable=False)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False)
    invoice_date = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.DateTime)
    subtotal = db.Column(db.Float, nullable=False)
    tax_amount = db.Column(db.Float, default=0.0)
    discount_amount = db.Column(db.Float, default=0.0)
    total_amount = db.Column(db.Float, nullable=False)
    notes = db.Column(db.Text)
    status = db.Column(db.String(20), default='Unpaid')  # Unpaid, Partially Paid, Paid
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Relationships
    sales_order = db.relationship('SalesOrder', backref='invoices', lazy=True)
    creator = db.relationship('User', backref='created_invoices', lazy=True)
    payments = db.relationship('SalesPayment', backref='invoice', lazy=True)

    def __repr__(self):
        return f"<SalesInvoice {self.id} Invoice# {self.invoice_number}>"

class SalesPayment(db.Model):
    __tablename__ = 'sales_payments'
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('sales_invoices.id'), nullable=False)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)  # Cash, Credit Card, Bank Transfer
    cash_account_id = db.Column(db.Integer, db.ForeignKey('cash_accounts.id'))
    reference_number = db.Column(db.String(100))
    notes = db.Column(db.Text)
    recorded_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Relationships
    recorder = db.relationship('User', backref='recorded_payments', lazy=True)
    cash_account = db.relationship('CashAccount', backref='sales_payments', lazy=True)

    def __repr__(self):
        return f"<SalesPayment {self.id} Invoice {self.invoice_id} Amount {self.amount}>"

class SalesActivityLog(db.Model):
    __tablename__ = 'sales_activity_logs'
    id = db.Column(db.Integer, primary_key=True)
    sales_order_id = db.Column(db.Integer, db.ForeignKey('sales_orders.SalesOrderID'))
    invoice_id = db.Column(db.Integer, db.ForeignKey('sales_invoices.id'))
    activity_type = db.Column(db.String(50), nullable=False)  # Created, Updated, Deleted, Payment, etc.
    description = db.Column(db.Text, nullable=False)
    performed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    sales_order = db.relationship('SalesOrder', backref='activity_logs', lazy=True)
    invoice = db.relationship('SalesInvoice', backref='activity_logs', lazy=True)
    user = db.relationship('User', backref='sales_activities', lazy=True)

    def __repr__(self):
        return f"<SalesActivityLog {self.id} Type {self.activity_type}>"
##############################################################################
# LOT/BATCH TRACKING AND EXPIRY MANAGEMENT
##############################################################################

# Update the Batch model to include production order relationship

class Batch(db.Model):
    __tablename__ = 'batches'
    id = db.Column('BatchID', db.Integer, primary_key=True)
    item_id = db.Column('ItemID', db.Integer, db.ForeignKey('items.ItemID'), nullable=False)
    lot_number = db.Column('LotNumber', db.String(100), unique=True, nullable=False)
    production_date = db.Column('ProductionDate', db.DateTime)
    expiry_date = db.Column('ExpiryDate', db.DateTime)
    quantity = db.Column('Quantity', db.Integer, nullable=False)

    # Keep this relationship to ProductionRun
    production_run_id = db.Column('ProductionRunID', db.Integer,
                                 db.ForeignKey('production_runs.ProductionRunID', name='fk_batch_production_run'))

    # Add a new column for ProductionOrder relationship
    production_order_id = db.Column('production_order_id', db.Integer,
                                   db.ForeignKey('production_orders.id', name='fk_batch_production_order'))

    status = db.Column(db.String(50), default='Created')  # Created, InProduction, QCPending, QCPassed, Packaged, Stored

    # Relationships
    item = db.relationship('Item', backref='batches', lazy=True)

    # Explicitly define the relationship to ProductionRun with foreign_keys
    production_run = db.relationship('ProductionRun',
                                    foreign_keys=[production_run_id],
                                    backref='batches',
                                    lazy=True)

    # Don't define the relationship to ProductionOrder here
    # Let it be defined in the ProductionOrder model

    batch_slots = db.relationship('BatchSlot', backref='batch', lazy=True)

    __table_args__ = (
        CheckConstraint('"Quantity" >= 0', name='chk_batch_qty_nonnegative'),
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
        CheckConstraint('"QuantityInSlot" >= 0', name='chk_batchslot_qty_nonnegative'),
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
        CheckConstraint('"QuantityShipped" > 0', name='chk_shipment_detail_qty_shipped_positive'),

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

    # Relationships
    role = db.relationship('Role', backref=db.backref('role_permissions', lazy=True, cascade='all, delete-orphan'))
    permission = db.relationship('Permission', backref=db.backref('role_permissions', lazy=True))

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

class ReportRequest(db.Model):
    __tablename__ = 'report_requests'
    id = db.Column(db.Integer, primary_key=True)
    report_type = db.Column(report_type_enum, nullable=False)
    report_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    requested_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    requested_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(report_status_enum, default='Pending')
    format = db.Column(report_format_enum, default='PDF')

    # Filters stored as JSON
    filters = db.Column(db.JSON, default={})

    # Date range for report
    date_from = db.Column(db.DateTime)
    date_to = db.Column(db.DateTime)

    # For admin processing
    processed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    processed_at = db.Column(db.DateTime)
    admin_notes = db.Column(db.Text)

    # Generated report file path
    report_file_path = db.Column(db.String(255))

    # Relationships
    requester = db.relationship('User', foreign_keys=[requested_by], backref='requested_reports')
    processor = db.relationship('User', foreign_keys=[processed_by], backref='processed_reports')

    def __repr__(self):
        return f"<ReportRequest {self.id}: {self.report_name} ({self.status})>"

    def to_dict(self):
        return {
            'id': self.id,
            'report_type': self.report_type,
            'report_name': self.report_name,
            'description': self.description,
            'requested_by': self.requested_by,
            'requested_at': self.requested_at.isoformat() if self.requested_at else None,
            'status': self.status,
            'format': self.format,
            'filters': self.filters,
            'date_from': self.date_from.isoformat() if self.date_from else None,
            'date_to': self.date_to.isoformat() if self.date_to else None,
            'processed_by': self.processed_by,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None,
            'admin_notes': self.admin_notes,
            'report_file_path': self.report_file_path
        }

class ReportTemplate(db.Model):
    __tablename__ = 'report_templates'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    report_type = db.Column(report_type_enum, nullable=False)
    description = db.Column(db.Text)
    template_config = db.Column(db.JSON, nullable=False)  # Columns, formatting, etc.
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_default = db.Column(db.Boolean, default=False)

    # Relationship
    creator = db.relationship('User', backref='created_templates')

    def __repr__(self):
        return f"<ReportTemplate {self.id}: {self.name}>"

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
        CheckConstraint('"QuantityPlanned" > 0', name='chk_production_run_detail_qty_planned_positive'),
    )

    def __repr__(self):
        return f"<ProductionRunDetail {self.id} Run {self.production_run_id} Item {self.item_id}>"


class ProductionProcess(db.Model):
    __tablename__ = 'production_processes'

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batches.BatchID'), nullable=False)  # Changed from 'batches.id' to 'batches.BatchID'
    process_type = db.Column(db.String(50), nullable=False)  # pasteurization, curdling, draining, etc.
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    temperature = db.Column(db.Float)
    humidity = db.Column(db.Float)
    ph_level = db.Column(db.Float)
    notes = db.Column(db.Text)
    operator_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    batch = db.relationship('Batch', backref=db.backref('processes', lazy=True))
    operator = db.relationship('User', backref=db.backref('production_processes', lazy=True))

class AgingRecord(db.Model):
    __tablename__ = 'aging_records'

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batches.BatchID'), nullable=False)  # Changed from 'batches.id' to 'batches.BatchID'
    aging_room = db.Column(db.String(50), nullable=False)
    temperature = db.Column(db.Float, nullable=False)
    humidity = db.Column(db.Float, nullable=False)
    appearance = db.Column(db.String(100))
    texture = db.Column(db.String(100))
    aroma = db.Column(db.String(100))
    notes = db.Column(db.Text)
    inspector_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    batch = db.relationship('Batch', backref=db.backref('aging_records', lazy=True))
    inspector = db.relationship('User', backref=db.backref('inspected_aging_records', lazy=True))

class WorkerProductivity(db.Model):
    __tablename__ = 'worker_productivity'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    production_run_id = db.Column(db.Integer, db.ForeignKey('production_runs.ProductionRunID'), nullable=False)  # Changed from 'production_runs.id' to 'production_runs.ProductionRunID'
    items_produced = db.Column(db.Integer, default=0)
    errors_made = db.Column(db.Integer, default=0)
    hours_worked = db.Column(db.Float, nullable=False)
    efficiency_score = db.Column(db.Float)
    notes = db.Column(db.Text)
    recorded_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('productivity_records', lazy=True))
    production_run = db.relationship('ProductionRun', backref=db.backref('productivity_records', lazy=True))
    recorder = db.relationship('User', foreign_keys=[recorded_by])

class ProductPackaging(db.Model):
    __tablename__ = 'product_packaging'
    id = db.Column(db.Integer, primary_key=True)
    production_run_id = db.Column(db.Integer, db.ForeignKey('production_runs.ProductionRunID'), nullable=False)
    batch_id = db.Column(db.Integer, db.ForeignKey('batches.BatchID'), nullable=False)
    packaging_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(packaging_status_enum, default='Pending')
    packaged_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    notes = db.Column(db.Text)

    # Relationships
    production_run = db.relationship('ProductionRun', backref='packaging_records', lazy=True)
    batch = db.relationship('Batch', backref='packaging_records', lazy=True)
    packager = db.relationship('User', backref='packaging_records', lazy=True)
    packaging_materials = db.relationship('PackagingMaterial', backref='packaging', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f"<ProductPackaging {self.id} for Batch {self.batch_id}>"

class PackagingMaterial(db.Model):
    __tablename__ = 'packaging_materials'
    id = db.Column(db.Integer, primary_key=True)
    packaging_id = db.Column(db.Integer, db.ForeignKey('product_packaging.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.ItemID'), nullable=False)
    quantity_used = db.Column(db.Integer, nullable=False)

    # Relationship
    item = db.relationship('Item', backref='used_in_packaging', lazy=True)

    def __repr__(self):
        return f"<PackagingMaterial {self.id} Item {self.item_id} Qty {self.quantity_used}>"

# Production Line Management
class ProductionLine(db.Model):
    __tablename__ = 'production_lines'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    capacity_per_hour = db.Column(db.Float)
    # Add these three fields:
    capacity_unit = db.Column(db.String(50))
    capacity_period = db.Column(db.String(50))
    location = db.Column(db.String(200))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    production_orders = db.relationship('ProductionOrder', backref='production_line', lazy=True)

    def __repr__(self):
        return f"<ProductionLine {self.name}>"

# Production Order Status Enum
production_order_status_enum = SAEnum(
    'Planned', 'InProgress', 'Completed', 'Cancelled', 'OnHold',
    name='production_order_status_enum'
)

# Production Order
class ProductionOrder(db.Model):
    __tablename__ = 'production_orders'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('items.ItemID'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    status = db.Column(production_order_status_enum, default='Planned')
    production_line_id = db.Column(db.Integer, db.ForeignKey('production_lines.id'))
    production_run_id = db.Column(db.Integer, db.ForeignKey('production_runs.ProductionRunID'))
    scheduled_start = db.Column(db.DateTime)
    scheduled_end = db.Column(db.DateTime)
    actual_start = db.Column(db.DateTime)
    actual_end = db.Column(db.DateTime)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    product = db.relationship('Item', backref='production_orders', lazy=True)
    production_run = db.relationship('ProductionRun', backref='production_orders', lazy=True)
    creator = db.relationship('User', backref='created_production_orders', lazy=True)
    batches = db.relationship('Batch',
                             foreign_keys='Batch.production_order_id',
                             backref=db.backref('production_order', lazy=True),
                             lazy=True)
    def __repr__(self):
        return f"<ProductionOrder {self.id} for Product {self.product_id}>"

# Production Step
class ProductionStep(db.Model):
    __tablename__ = 'production_steps'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    standard_duration = db.Column(db.Integer)  # in minutes
    sequence_number = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, default=True)  # Add this line
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # Add this if you want to track creation time

    # Relationships
    step_records = db.relationship('ProductionStepRecord', backref='step', lazy=True)

    def __repr__(self):
        return f"<ProductionStep {self.name}>"


# Production Step Record
class ProductionStepRecord(db.Model):
    __tablename__ = 'production_step_records'
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batches.BatchID'), nullable=False)
    step_id = db.Column(db.Integer, db.ForeignKey('production_steps.id'), nullable=False)
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    operator_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    notes = db.Column(db.Text)
    parameters = db.Column(db.JSON)  # Store step-specific parameters

    # Relationships
    batch = db.relationship('Batch', backref='step_records', lazy=True)
    operator = db.relationship('User', backref='operated_steps', lazy=True)

    def __repr__(self):
        return f"<ProductionStepRecord {self.id} for Batch {self.batch_id}, Step {self.step_id}>"

# Production Parameter
class ProductionParameter(db.Model):
    __tablename__ = 'production_parameters'
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batches.BatchID'), nullable=False)
    parameter_name = db.Column(db.String(100), nullable=False)
    parameter_value = db.Column(db.String(100))
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)
    recorded_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Relationships
    batch = db.relationship('Batch', backref='parameters', lazy=True)
    recorder = db.relationship('User', backref='recorded_parameters', lazy=True)

    def __repr__(self):
        return f"<ProductionParameter {self.parameter_name}={self.parameter_value} for Batch {self.batch_id}>"

# QC Test Type Enum
qc_test_type_enum = SAEnum(
    'Visual', 'Chemical', 'Physical', 'Microbiological', 'Sensory', 'Other','Comprehensive',
    name='qc_test_type_enum'
)

# QC Test Status Enum
qc_test_status_enum = SAEnum(
    'Pending', 'InProgress', 'Passed', 'Failed', 'Retest',
    name='qc_test_status_enum'
)

# QC Test
class QCTest(db.Model):
    __tablename__ = 'qc_tests'
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batches.BatchID'), nullable=False)
    test_type = db.Column(qc_test_type_enum, default='Visual')
    status = db.Column(qc_test_status_enum, default='Pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    inspector_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    notes = db.Column(db.Text)

    # Relationships
    batch = db.relationship('Batch', backref='qc_tests', lazy=True)
    inspector = db.relationship('User', backref='conducted_tests', lazy=True)
    results = db.relationship('QCTestResult', backref='test', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f"<QCTest {self.id} for Batch {self.batch_id}, Type {self.test_type}>"

# QC Test Result
class QCTestResult(db.Model):
    __tablename__ = 'qc_test_results'
    id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey('qc_tests.id'), nullable=False)
    parameter_id = db.Column(db.Integer, db.ForeignKey('qc_parameters.QCParamID'))
    parameter_name = db.Column(db.String(100), nullable=False)
    expected_value = db.Column(db.String(100))
    actual_value = db.Column(db.String(100))
    is_passed = db.Column(db.Boolean)
    notes = db.Column(db.Text)

    # Relationships
    parameter = db.relationship('QCParameter', backref='test_results', lazy=True)

    def __repr__(self):
        return f"<QCTestResult {self.id} for Test {self.test_id}, Parameter {self.parameter_name}>"

# Packaging Order Status Enum
packaging_order_status_enum = SAEnum(
    'Pending', 'InProgress', 'Completed', 'Cancelled',
    name='packaging_order_status_enum'
)

# Packaging Order
class PackagingOrder(db.Model):
    __tablename__ = 'packaging_orders'
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batches.BatchID'), nullable=False)
    packaging_type = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    status = db.Column(packaging_order_status_enum, default='Pending')
    packaging_line_id = db.Column(db.Integer, db.ForeignKey('packaging_lines.id'))
    scheduled_date = db.Column(db.DateTime)
    completed_date = db.Column(db.DateTime)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    batch = db.relationship('Batch', backref='packaging_orders', lazy=True)
    packaging_line = db.relationship('PackagingLine', backref='packaging_orders', lazy=True)
    creator = db.relationship('User', backref='created_packaging_orders', lazy=True)
    materials = db.relationship('PackagingMaterialUsage', backref='packaging_order', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f"<PackagingOrder {self.id} for Batch {self.batch_id}>"

# Packaging Line
class PackagingLine(db.Model):
    __tablename__ = 'packaging_lines'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    capacity_per_hour = db.Column(db.Float)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<PackagingLine {self.name}>"

# Packaging Material Usage
class PackagingMaterialUsage(db.Model):
    __tablename__ = 'packaging_material_usage'
    id = db.Column(db.Integer, primary_key=True)
    packaging_order_id = db.Column(db.Integer, db.ForeignKey('packaging_orders.id'), nullable=False)
    material_id = db.Column(db.Integer, db.ForeignKey('items.ItemID'), nullable=False)
    quantity_used = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    material = db.relationship('Item', backref='packaging_usages', lazy=True)

    def __repr__(self):
        return f"<PackagingMaterialUsage {self.id} Material {self.material_id} Qty {self.quantity_used}>"

# Product Label
class ProductLabel(db.Model):
    __tablename__ = 'product_labels'
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batches.BatchID'), nullable=False)
    label_template = db.Column(db.String(100))
    quantity = db.Column(db.Integer, nullable=False)
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
    generated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    label_data = db.Column(db.JSON)  # Store label-specific data

    # Relationships
    batch = db.relationship('Batch', backref='labels', lazy=True)
    generator = db.relationship('User', backref='generated_labels', lazy=True)

    def __repr__(self):
        return f"<ProductLabel {self.id} for Batch {self.batch_id}>"


##############################################################################
# SYSTEM SETTINGS, ROLES, AND USER MANAGEMENT
##############################################################################

class SystemSettings(db.Model):
    __tablename__ = 'system_settings'
    id = db.Column(db.Integer, primary_key=True)
    system_title = db.Column(db.String(100), default="EL7amla")

    # Theme settings
    theme_mode = db.Column(db.String(20), default="light")  # light, dark, auto
    theme_color = db.Column(db.String(50), default="blue")
    background_color = db.Column(db.String(50), default="blue")
    sidebar_color = db.Column(db.String(50), default="blue")

    # UI settings
    font_family = db.Column(db.String(50), default="Tajawal")
    font_size = db.Column(db.String(20), default="medium")
    border_radius = db.Column(db.String(20), default="medium")  # small, medium, large
    animation_speed = db.Column(db.String(20), default="normal")  # slow, normal, fast, none

    # Layout settings
    layout_density = db.Column(db.String(20), default="comfortable")  # compact, comfortable, spacious
    sidebar_collapsed = db.Column(db.Boolean, default=False)
    rtl_enabled = db.Column(db.Boolean, default=True)

    # Image settings
    login_bg_image = db.Column(db.String(255), default="/static/uploads/20250227_154020_el7amlaDesktop_Wallpaper.png")
    logo_image = db.Column(db.String(255), default="/static/uploads/20250227_153609_png")
    favicon_image = db.Column(db.String(255), default="/static/favicon.ico")

    # Company information
    company_name = db.Column(db.String(100), default="شركة قاتيلو")
    company_address = db.Column(db.String(255), default="123 شارع الأعمال")
    company_city = db.Column(db.String(100), default="المدينة، المنطقة، الرمز البريدي")
    company_email = db.Column(db.String(100), default="info@katilo.com")
    company_phone = db.Column(db.String(50), default="+20 123 456 7890")
    company_website = db.Column(db.String(100), default="www.katilo.com")
    company_tax_id = db.Column(db.String(50), default="")

    # Invoice settings
    payment_terms_days = db.Column(db.Integer, default=30)
    payment_terms_text = db.Column(db.String(255), default="يستحق الدفع خلال {days} يوم من تاريخ الفاتورة.")

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

            # Theme settings
            'theme_mode': self.theme_mode,
            'theme_color': self.theme_color,
            'background_color': self.background_color,
            'sidebar_color': self.sidebar_color,

            # UI settings
            'font_family': self.font_family,
            'font_size': self.font_size,
            'border_radius': self.border_radius,
            'animation_speed': self.animation_speed,

            # Layout settings
            'layout_density': self.layout_density,
            'sidebar_collapsed': self.sidebar_collapsed,
            'rtl_enabled': self.rtl_enabled,

            # Image settings
            'logo_image': self.logo_image,
            'login_bg_image': self.login_bg_image,
            'favicon_image': self.favicon_image,

            # Company information
            'company_name': self.company_name,
            'company_address': self.company_address,
            'company_city': self.company_city,
            'company_email': self.company_email,
            'company_phone': self.company_phone,
            'company_website': self.company_website,
            'company_tax_id': self.company_tax_id,

            # Invoice settings
            'payment_terms_days': self.payment_terms_days,
            'payment_terms_text': self.payment_terms_text,

            # Other settings
            'visible_widgets': self.visible_widgets,
            'dashboard_layout': self.dashboard_layout,
            'custom_colors': self.custom_colors
        }

class SidebarItem(db.Model):
    __tablename__ = 'sidebar_items'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    icon = db.Column(db.String(50), nullable=False)
    url = db.Column(db.String(255))
    order = db.Column(db.Integer, default=0)
    parent_id = db.Column(db.Integer, db.ForeignKey('sidebar_items.id'), nullable=True)
    is_dropdown = db.Column(db.Boolean, default=False)
    admin_only = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationship for parent-child structure
    children = db.relationship('SidebarItem', 
                              backref=db.backref('parent', remote_side=[id]),
                              cascade="all, delete-orphan")
    
    # Add this method to your SidebarItem class
    def to_dict(self):
        """Convert the model to a dictionary"""
        return {
            'id': self.id,
            'title': self.title,
            'icon': self.icon,
            'url': self.url or '',
            'order': self.order,
            'parent_id': self.parent_id,
            'is_dropdown': self.is_dropdown,
            'admin_only': self.admin_only,
            'is_active': self.is_active
        }

    @classmethod
    def get_default_menu(cls):
        """Create default menu structure if none exists"""
        # First, delete all existing sidebar items
        cls.query.delete()
        db.session.commit()
        
        # Create default menu structure
        dashboard = cls(title="لوحة التحكم", icon="fa-tachometer-alt", url="/dashboard", order=1)
        db.session.add(dashboard)
        
        # Inventory Management
        inventory = cls(title="إدارة المخزون", icon="fa-boxes", is_dropdown=True, order=2)
        db.session.add(inventory)
        db.session.flush()  # To get the ID
        
        inventory_items = [
            cls(title="المخزون", icon="fa-box-open", url="/inventory-management", parent_id=inventory.id, order=1),
            cls(title="فحص الجودة", icon="fa-clipboard-check", url="/quality-inspections", parent_id=inventory.id, order=2),
            cls(title="تخطيط المستودع", icon="fa-th", url="/warehouse-layout", parent_id=inventory.id, order=3),
            cls(title="إدارة المستودعات", icon="fa-warehouse", url="/warehouses-management", parent_id=inventory.id, order=4),
            cls(title="التقارير", icon="fa-file-alt", url="/inventory-reports", parent_id=inventory.id, order=5, admin_only=True)
        ]
        db.session.add_all(inventory_items)
        
        # Products Management
        products = cls(title="إدارة المنتجات", icon="fa-cubes", is_dropdown=True, order=3)
        db.session.add(products)
        db.session.flush()
        
        product_items = [
            cls(title="التصنيفات", icon="fa-tags", url="/categories-management", parent_id=products.id, order=1),
            cls(title="العناصر", icon="fa-cube", url="/items-management", parent_id=products.id, order=2),
            cls(title="أوزان وأحجام المنتجات", icon="fa-weight-hanging", url="/inventory/item-weights", parent_id=products.id, order=3)
        ]
        db.session.add_all(product_items)
        
        # Production Management
        production = cls(title="إدارة الإنتاج", icon="fa-industry", is_dropdown=True, order=4)
        db.session.add(production)
        db.session.flush()
        
        production_items = [
            cls(title="لوحة التحكم", icon="fa-tachometer-alt", url="/production/dashboard", parent_id=production.id, order=1),
            cls(title="أوامر الإنتاج", icon="fa-clipboard-list", url="/production/orders", parent_id=production.id, order=2),
            cls(title="قوائم المواد", icon="fa-project-diagram", url="/bom-management", parent_id=production.id, order=3),
            cls(title="إدارة الدفعات", icon="fa-cubes", url="/production/batches", parent_id=production.id, order=4),
            cls(title="خطوط الإنتاج", icon="fa-stream", url="/production/lines", parent_id=production.id, order=5),
            cls(title="تتبع الأنشطة", icon="fa-tasks", url="/production/logs", parent_id=production.id, order=6),
            cls(title="مراقبة الجودة", icon="fa-check-circle", url="/production/qc/tests", parent_id=production.id, order=7),
            cls(title="تعبئة المنتجات", icon="fa-box", url="/production/packaging/orders", parent_id=production.id, order=8),
            cls(title="تقارير الإنتاج", icon="fa-chart-bar", url="/production/timeline", parent_id=production.id, order=9)
        ]
        db.session.add_all(production_items)
        
        # Sales Management
        sales = cls(title="إدارة المبيعات", icon="fa-shopping-cart", is_dropdown=True, order=5)
        db.session.add(sales)
        db.session.flush()
        
        sales_items = [
            cls(title="لوحة المبيعات", icon="fa-tachometer-alt", url="/sales", parent_id=sales.id, order=1),
            cls(title="طلبات المبيعات", icon="fa-file-invoice", url="/sales/orders", parent_id=sales.id, order=2),
            cls(title="الفواتير", icon="fa-file-invoice-dollar", url="/sales/invoices", parent_id=sales.id, order=3),
            cls(title="العملاء", icon="fa-users", url="/sales/customers", parent_id=sales.id, order=4),
            cls(title="المرتجعات", icon="fa-undo", url="/sales/returns", parent_id=sales.id, order=5),
            cls(title="سجل الأنشطة", icon="fa-history", url="/sales/activity-logs", parent_id=sales.id, order=6)
        ]
        db.session.add_all(sales_items)
        
        # Sales Representatives
        reps = cls(title="مندوبي المبيعات", icon="fa-user-tie", is_dropdown=True, parent_id=sales.id, order=5)
        db.session.add(reps)
        db.session.flush()
        
        reps_items = [
            cls(title="قائمة المندوبين", icon="fa-users", url="/sales/representatives", parent_id=reps.id, order=1),
            cls(title="خطط المسارات", icon="fa-route", url="/sales/representatives/routes", parent_id=reps.id, order=2),
            cls(title="تتبع المندوبين", icon="fa-map-marker-alt", url="/sales/representatives/tracking", parent_id=reps.id, order=3),
            cls(title="تقارير المسارات", icon="fa-chart-line", url="/sales/representatives/routes/report", parent_id=reps.id, order=4)
        ]
        db.session.add_all(reps_items)
        
        # Suppliers Management
        suppliers = cls(title="إدارة الموردين", icon="fa-truck", is_dropdown=True, order=6)
        db.session.add(suppliers)
        db.session.flush()
        
        suppliers_items = [
            cls(title="الموردين", icon="fa-address-book", url="/suppliers-management", parent_id=suppliers.id, order=1),
            cls(title="حسابات الموردين", icon="fa-file-invoice-dollar", url="/supplier-accounts", parent_id=suppliers.id, order=2),
            cls(title="طلبات الشراء", icon="fa-shopping-cart", url="/purchase-orders", parent_id=suppliers.id, order=3)
        ]
        db.session.add_all(suppliers_items)
        
        # Cash Management
        cash = cls(title="إدارة الخزينة", icon="fa-money-bill-wave", is_dropdown=True, order=7)
        db.session.add(cash)
        db.session.flush()
        
        cash_items = [
            cls(title="لوحة التحكم", icon="fa-tachometer-alt", url="/cash/dashboard", parent_id=cash.id, order=1),
            cls(title="الحسابات", icon="fa-wallet", url="/cash/accounts", parent_id=cash.id, order=2),
            cls(title="المعاملات", icon="fa-exchange-alt", url="/cash/transactions", parent_id=cash.id, order=3),
            cls(title="التحويلات", icon="fa-random", url="/cash/transfers", parent_id=cash.id, order=4),
            cls(title="جرد الخزينة", icon="fa-balance-scale", url="/cash/reconciliations", parent_id=cash.id, order=5),
            cls(title="دفعات الموردين", icon="fa-truck", url="/cash/supplier-payments", parent_id=cash.id, order=6),
            cls(title="التقارير", icon="fa-chart-bar", url="/cash/reports", parent_id=cash.id, order=7)
        ]
        db.session.add_all(cash_items)
        
        # Distribution Management
        distribution = cls(title="إدارة التوزيع", icon="fa-truck-loading", is_dropdown=True, order=8)
        db.session.add(distribution)
        db.session.flush()
        
        distribution_items = [
            cls(title="لوحة التحكم", icon="fa-tachometer-alt", url="/distribution/dashboard", parent_id=distribution.id, order=1),
            cls(title="المركبات", icon="fa-truck", url="/distribution/vehicles", parent_id=distribution.id, order=2),
            cls(title="الشحنات", icon="fa-shipping-fast", url="/distribution/shipments", parent_id=distribution.id, order=3),
            cls(title="مسارات التوصيل", icon="fa-route", url="/distribution/routes", parent_id=distribution.id, order=4),
            cls(title="تتبع الشحنات", icon="fa-map-marked-alt", url="/distribution/tracking", parent_id=distribution.id, order=5)
        ]
        db.session.add_all(distribution_items)
        
        # Transactions
        transactions = cls(title="المعاملات", icon="fa-exchange-alt", url="/transactions-history", order=9)
        db.session.add(transactions)
        
        # Admin Section
        admin = cls(title="إدارة النظام", icon="fa-user-shield", is_dropdown=True, order=10, admin_only=True)
        db.session.add(admin)
        db.session.flush()
        
        admin_items = [
            cls(title="المستخدمين", icon="fa-users", url="/admin/users", parent_id=admin.id, order=1, admin_only=True),
            cls(title="الأدوار", icon="fa-user-tag", url="/admin/roles", parent_id=admin.id, order=2, admin_only=True),
            cls(title="تذاكر الدعم", icon="fa-ticket-alt", url="/admin/support-tickets", parent_id=admin.id, order=3, admin_only=True),
            cls(title="اقتراحات الذكاء الاصطناعي", icon="fa-robot", url="/ai-suggestions-dashboard", parent_id=admin.id, order=4, admin_only=True)
        ]
        db.session.add_all(admin_items)
        
        # Settings Section
        settings = cls(title="إعدادات النظام", icon="fa-cogs", is_dropdown=True, order=11, admin_only=True)
        db.session.add(settings)
        db.session.flush()
        
        settings_items = [
            cls(title="الإعدادات العامة", icon="fa-sliders-h", url="/settings/", parent_id=settings.id, order=1, admin_only=True),
            cls(title="إعدادات النظام", icon="fa-cogs", url="/settings/system", parent_id=settings.id, order=2, admin_only=True),
            cls(title="إعدادات المظهر", icon="fa-palette", url="/settings/themes", parent_id=settings.id, order=3, admin_only=True),
            cls(title="مفاتيح API", icon="fa-key", url="/settings/api-keys", parent_id=settings.id, order=4, admin_only=True),
            cls(title="قاعدة البيانات", icon="fa-database", url="/settings/database", parent_id=settings.id, order=5, admin_only=True),
            cls(title="الصلاحيات", icon="fa-user-lock", url="/settings/permissions", parent_id=settings.id, order=6, admin_only=True),
            cls(title="القائمة الجانبية", icon="fa-bars", url="/settings/sidebar", parent_id=settings.id, order=7, admin_only=True)
        ]
        db.session.add_all(settings_items)
        
        # Alerts
        alerts = cls(title="التنبيهات", icon="fa-bell", url="/alerts", order=12)
        db.session.add(alerts)

        # Help Guide
        help_guide = cls(title="دليل المستخدم", icon="fa-lightbulb", url="/tips", order=13)
        db.session.add(help_guide)

        # AI Assistant
        ai_assistant = cls(title="المساعد الذكي", icon="fa-robot", url="/chat-assistant", order=14, admin_only=True)
        db.session.add(ai_assistant)
        
        db.session.commit()
        
        return cls.query.order_by(cls.order).all()

    @classmethod
    def get_main_menu(cls, include_admin=False):
        """Get all top-level menu items"""
        query = cls.query.filter(cls.parent_id == None, cls.is_active == True)
        
        if not include_admin:
            query = query.filter(cls.admin_only == False)
            
        return query.order_by(cls.order).all()
    
    

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
        """Check if the user has a specific permission.

        Args:
            permission_name (str): The name of the permission to check

        Returns:
            bool: True if the user has the permission, False otherwise
        """
        # Admin role has all permissions
        if self.role and self.role.name == 'admin':
            return True

        if not self.role:
            return False

        # Use the relationship instead of querying
        role_perms = self.role.role_permissions

        # Get permissions directly through the relationship
        permissions = [rp.permission for rp in role_perms]

        # Check if any permission matches the requested permission name
        return any(p.permission_name == permission_name for p in permissions)

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
        CheckConstraint('"forecasted_quantity" >= 0', name='chk_forecast_qty_nonnegative'),
        CheckConstraint('"accuracy_rate" >= 0', name='chk_accuracy_rate_positive'),
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
        CheckConstraint('"recommended_order_quantity" >= 0', name='chk_replenish_qty_nonnegative'),
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
        CheckConstraint('"items_produced" >= 0', name='chk_items_produced_nonnegative'),
        CheckConstraint('"errors_made" >= 0', name='chk_errors_made_nonnegative'),
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
    # Change this line to reference the correct column name
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.CustomerID'), nullable=False)
    interaction_type = db.Column(db.String(50), nullable=False)
    notes = db.Column(db.Text, nullable=False)
    follow_up_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Relationships
    user = db.relationship('User')




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

# Add to models.py
# Add to models.py
class QualityInspection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    purchase_order_detail_id = db.Column(db.Integer, db.ForeignKey('purchase_order_details.PODetailID'))
    inspection_date = db.Column(db.DateTime, default=datetime.utcnow)
    inspector_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    status = db.Column(db.String(20))  # Passed, Failed, Partially Passed
    notes = db.Column(db.Text)

    # Relationships
    purchase_order_detail = db.relationship('PurchaseOrderDetail', backref='quality_inspections')
    inspector = db.relationship('User')
    criteria = db.relationship('QualityInspectionCriteria', backref='inspection', cascade='all, delete-orphan')


class QualityInspectionCriteria(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    inspection_id = db.Column(db.Integer, db.ForeignKey('quality_inspection.id'))
    criterion_name = db.Column(db.String(100))
    expected_value = db.Column(db.String(100))
    actual_value = db.Column(db.String(100))
    passed = db.Column(db.Boolean)
    importance = db.Column(db.String(20))  # Critical, Major, Minor


# Cash Management Models
class CashAccount(db.Model):
    __tablename__ = 'cash_accounts'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    account_type = db.Column(db.String(50), default='cash')  # cash, bank, etc.
    currency = db.Column(db.String(3), default='EGP')
    initial_balance = db.Column(db.Float, default=0.0)
    current_balance = db.Column(db.Float, default=0.0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Relationships
    creator = db.relationship('User', backref='created_cash_accounts', lazy=True)
    transactions = db.relationship('CashTransaction', backref='account', lazy=True)

    def __repr__(self):
        return f"<CashAccount {self.name} Balance: {self.current_balance}>"

class CashTransaction(db.Model):
    __tablename__ = 'cash_transactions'
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('cash_accounts.id'), nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False)  # deposit, withdrawal, transfer
    amount = db.Column(db.Float, nullable=False)
    reference_type = db.Column(db.String(50))  # supplier_payment, sales_receipt, expense, etc.
    reference_id = db.Column(db.Integer)
    description = db.Column(db.Text)
    transaction_date = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    creator = db.relationship('User', backref='cash_transactions', lazy=True)

    def __repr__(self):
        return f"<CashTransaction {self.id} Type: {self.transaction_type} Amount: {self.amount}>"

class CashTransferVoucher(db.Model):
    __tablename__ = 'cash_transfer_vouchers'
    id = db.Column(db.Integer, primary_key=True)
    voucher_number = db.Column(db.String(50), unique=True, nullable=False)
    from_account_id = db.Column(db.Integer, db.ForeignKey('cash_accounts.id'), nullable=False)
    to_account_id = db.Column(db.Integer, db.ForeignKey('cash_accounts.id'))
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.SupplierID'))
    amount = db.Column(db.Float, nullable=False)
    transfer_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='pending')  # pending, completed, cancelled
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    from_account = db.relationship('CashAccount', foreign_keys=[from_account_id])
    to_account = db.relationship('CashAccount', foreign_keys=[to_account_id])
    supplier = db.relationship('Supplier', backref='cash_transfers', lazy=True)
    creator = db.relationship('User', backref='created_vouchers', lazy=True)

    def __repr__(self):
        return f"<CashTransferVoucher {self.voucher_number} Amount: {self.amount}>"

class CashReconciliation(db.Model):
    __tablename__ = 'cash_reconciliations'
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('cash_accounts.id'), nullable=False)
    reconciliation_date = db.Column(db.DateTime, default=datetime.utcnow)
    system_balance = db.Column(db.Float, nullable=False)
    counted_balance = db.Column(db.Float, nullable=False)
    difference = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    notes = db.Column(db.Text)
    performed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    account = db.relationship('CashAccount', backref='reconciliations', lazy=True)
    performer = db.relationship('User', foreign_keys=[performed_by], backref='performed_reconciliations', lazy=True)
    approver = db.relationship('User', foreign_keys=[approved_by], backref='approved_reconciliations', lazy=True)

    def __repr__(self):
        return f"<CashReconciliation {self.id} Account: {self.account_id} Difference: {self.difference}>"

##############################################################################
# DISTRIBUTION MANAGEMENT
##############################################################################

# Enumerations for Distribution Management
vehicle_status_enum = SAEnum('Active', 'Maintenance', 'Inactive', name='vehicle_status_enum')
shipment_status_enum = SAEnum('Pending', 'Assigned', 'InTransit', 'Delivered', 'Failed', name='shipment_status_enum')
route_status_enum = SAEnum('Planned', 'InProgress', 'Completed', 'Cancelled', name='route_status_enum')

class Vehicle(db.Model):
    __tablename__ = 'vehicles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    vehicle_type = db.Column(db.String(50), nullable=False)
    plate_number = db.Column(db.String(20), unique=True, nullable=False)
    model = db.Column(db.String(100))
    year = db.Column(db.Integer)
    status = db.Column(vehicle_status_enum, default='Active')

    # Capacity details
    max_weight = db.Column(db.Float, comment='Maximum weight capacity in kg')
    max_volume = db.Column(db.Float, comment='Maximum volume capacity in cubic meters')
    max_length = db.Column(db.Float, comment='Maximum load length in mm')
    max_height = db.Column(db.Float, comment='Maximum load height in mm')

    # Tracking and maintenance
    last_maintenance_date = db.Column(db.DateTime)
    next_maintenance_date = db.Column(db.DateTime)
    notes = db.Column(db.Text)

    # Image of the vehicle
    image_path = db.Column(db.String(255))
    image_data = db.Column(db.Text, nullable=True, comment='Base64 encoded image data')

    # Relationships
    storage = db.relationship('VehicleStorage', backref='vehicle', uselist=False, cascade='all, delete-orphan')
    shipments = db.relationship('ShipmentOrder', backref='vehicle', lazy=True)
    routes = db.relationship('DeliveryRoute', backref='vehicle', lazy=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Vehicle {self.name} ({self.plate_number})>"

class VehicleStorage(db.Model):
    __tablename__ = 'vehicle_storage'
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicles.id'), nullable=False, unique=True)

    # Current usage
    current_weight = db.Column(db.Float, default=0, comment='Current weight in kg')
    current_volume = db.Column(db.Float, default=0, comment='Current volume in cubic meters')

    # Percentage of capacity used
    weight_utilization = db.Column(db.Float, default=0, comment='Percentage of weight capacity used')
    volume_utilization = db.Column(db.Float, default=0, comment='Percentage of volume capacity used')

    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<VehicleStorage for Vehicle {self.vehicle_id}>"

class ShipmentOrder(db.Model):
    __tablename__ = 'shipment_orders'
    id = db.Column(db.Integer, primary_key=True)
    sales_order_id = db.Column(db.Integer, db.ForeignKey('sales_orders.SalesOrderID'), nullable=False)
    shipment_id = db.Column(db.Integer, db.ForeignKey('shipments.ShipmentID'), nullable=False)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicles.id'), nullable=True)

    status = db.Column(shipment_status_enum, default='Pending')
    assigned_date = db.Column(db.DateTime)
    estimated_delivery_date = db.Column(db.DateTime)
    actual_delivery_date = db.Column(db.DateTime)

    # Relationships
    sales_order = db.relationship('SalesOrder', backref='shipment_orders')
    shipment = db.relationship('Shipment', backref='shipment_orders')

    # Route information
    route_id = db.Column(db.Integer, db.ForeignKey('delivery_routes.id'), nullable=True)
    route_position = db.Column(db.Integer, comment='Position in the delivery route')

    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<ShipmentOrder {self.id} for Order {self.sales_order_id}>"

class DeliveryRoute(db.Model):
    __tablename__ = 'delivery_routes'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicles.id'), nullable=False)

    status = db.Column(route_status_enum, default='Planned')
    planned_date = db.Column(db.DateTime, nullable=False)
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)

    # Route details
    total_distance = db.Column(db.Float, comment='Total distance in km')
    estimated_duration = db.Column(db.Integer, comment='Estimated duration in minutes')
    actual_duration = db.Column(db.Integer, comment='Actual duration in minutes')

    # Relationships
    stops = db.relationship('RouteStop', backref='route', lazy=True, cascade='all, delete-orphan')
    shipments = db.relationship('ShipmentOrder', backref='route', lazy=True)

    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<DeliveryRoute {self.name} on {self.planned_date}>"

class RouteStop(db.Model):
    __tablename__ = 'route_stops'
    id = db.Column(db.Integer, primary_key=True)
    route_id = db.Column(db.Integer, db.ForeignKey('delivery_routes.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.CustomerID'), nullable=False)
    shipment_order_id = db.Column(db.Integer, db.ForeignKey('shipment_orders.id'), nullable=True)

    stop_number = db.Column(db.Integer, nullable=False, comment='Order of stop in the route')
    planned_arrival_time = db.Column(db.DateTime)
    actual_arrival_time = db.Column(db.DateTime)

    # Location details
    address = db.Column(db.Text)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)

    # Status
    status = db.Column(db.String(50), default='Pending')  # Pending, Completed, Skipped

    # Relationships
    customer = db.relationship('Customer', backref='route_stops')
    shipment_order = db.relationship('ShipmentOrder', backref='route_stop')

    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<RouteStop {self.stop_number} for Route {self.route_id}>"

class ShipmentTracking(db.Model):
    __tablename__ = 'shipment_tracking'
    id = db.Column(db.Integer, primary_key=True)
    shipment_order_id = db.Column(db.Integer, db.ForeignKey('shipment_orders.id'), nullable=False)

    status = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    # Location details
    location_name = db.Column(db.String(255))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)

    # Additional details
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Relationships
    shipment_order = db.relationship('ShipmentOrder', backref='tracking_updates')

    def __repr__(self):
        return f"<ShipmentTracking {self.id} for ShipmentOrder {self.shipment_order_id}>"
