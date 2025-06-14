import random
import string
import datetime
import logging
import sys
from faker import Faker
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text
from app import app, db
from models import (
    # Core Entities
    Category, Item, Warehouse, WarehouseSection, WarehouseSlot,
    Inventory, InventoryTransaction, BOM, BOMDetail,

    # Supplier Management
    Supplier, SupplierItem, SupplierLedgerEntry, SupplierPayment,

    # Purchase Orders
    PurchaseOrder, PurchaseOrderDetail,

    # Sales & Customers
    Customer, SalesOrder, SalesOrderDetail, SalesInvoice, SalesPayment,
    SalesActivityLog, SalesReturn, SalesReturnItem,

    # Lot/Batch Tracking
    Batch, BatchSlot,

    # Quality Control
    QualityCheck, QualityCheckResult, QCParameter, QualityInspection,
    QualityInspectionCriteria, QCTest, QCTestResult,

    # Equipment & Maintenance
    Equipment, MaintenanceLog,

    # Shipping & Distribution
    Shipment, ShipmentDetail, Vehicle, VehicleStorage, ShipmentOrder,
    DeliveryRoute, RouteStop, ShipmentTracking,

    # User Management
    SystemSettings, Role, User, Permission, RolePermission,

    # Document Management
    Document,

    # Production Planning
    ProductionRun, ProductionRunDetail, ProductionOrder, ProductionLine,
    ProductionStep, ProductionStepRecord, ProductionParameter, ProductionProcess,

    # Packaging
    ProductPackaging, PackagingMaterial, PackagingOrder, PackagingLine,
    PackagingMaterialUsage, ProductLabel,

    # Cash Management
    CashAccount, CashTransaction, CashTransferVoucher, CashReconciliation,

    # Sales Representatives
    SalesRepresentative, RepresentativeRoute, CustomerVisit,
    RepresentativePerformance, VisitPhoto,

    # Advanced Features
    DemandForecast, InventoryReplenishmentPlan, EmployeeShift,
    ProductionEfficiency, CustomerInteraction, DiscountPromotion,
    AgingRecord, SupportTicket, TicketResponse, WorkerProductivity,
    ItemCostHistory, AISuggestion
)

fake = Faker()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('database_seeder.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def random_date(start_date, end_date):
    """Generate a random date between start_date and end_date"""
    time_between_dates = end_date - start_date
    days_between_dates = time_between_dates.days
    random_number_of_days = random.randrange(days_between_dates)
    return start_date + datetime.timedelta(days=random_number_of_days)

def cleanup_existing_data():
    """Clean up existing test data to make the script idempotent"""
    logger.info("Cleaning up existing test data...")

    try:
        # Disable foreign key constraints temporarily
        db.session.execute(text('SET session_replication_role = replica;'))

        # List of tables to clean in reverse dependency order
        tables_to_clean = [
            'ai_suggestions', 'worker_productivity', 'visit_photos', 'representative_performance',
            'customer_visits', 'representative_routes', 'sales_representatives',
            'cash_reconciliation', 'cash_transfer_voucher', 'cash_transactions', 'cash_accounts',
            'product_labels', 'packaging_material_usage', 'packaging_lines', 'packaging_orders',
            'production_step_records', 'production_steps', 'production_parameters',
            'production_processes', 'production_lines', 'production_orders',
            'qc_test_results', 'qc_tests', 'quality_inspection_criteria', 'quality_inspection',
            'quality_check_results', 'quality_checks', 'qc_parameters',
            'aging_records', 'support_ticket_responses', 'support_tickets',
            'sales_return_items', 'sales_returns', 'sales_activity_logs',
            'sales_payments', 'sales_invoices', 'customer_interactions',
            'discount_promotions', 'demand_forecasts', 'inventory_replenishment_plans',
            'employee_shifts', 'production_efficiency', 'item_cost_history',
            'shipment_tracking', 'route_stops', 'delivery_routes', 'shipment_orders',
            'vehicle_storage', 'vehicles', 'shipment_details', 'shipments',
            'maintenance_logs', 'equipment', 'batch_slots', 'batches',
            'sales_order_details', 'sales_orders', 'purchase_order_details', 'purchase_orders',
            'supplier_payments', 'supplier_ledger_entries', 'supplier_items',
            'bom_details', 'boms', 'inventory_transactions', 'inventory',
            'warehouse_slots', 'warehouse_sections', 'production_run_details', 'production_runs',
            'product_packaging', 'packaging_materials', 'documents', 'role_permissions',
            'users', 'permissions', 'roles', 'customers', 'suppliers', 'items', 'categories',
            'warehouses'
        ]

        for table in tables_to_clean:
            try:
                db.session.execute(text(f'TRUNCATE TABLE {table} RESTART IDENTITY CASCADE;'))
                logger.info(f"Cleaned table: {table}")
            except Exception as e:
                logger.warning(f"Could not clean table {table}: {str(e)}")

        # Re-enable foreign key constraints
        db.session.execute(text('SET session_replication_role = DEFAULT;'))
        db.session.commit()
        logger.info("Database cleanup completed successfully")

    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")
        db.session.rollback()
        raise

def safe_add_and_commit(objects, description="objects"):
    """Safely add objects to database with error handling"""
    try:
        if isinstance(objects, list):
            db.session.add_all(objects)
        else:
            db.session.add(objects)
        db.session.commit()
        logger.info(f"Successfully added {len(objects) if isinstance(objects, list) else 1} {description}")
        return True
    except Exception as e:
        logger.error(f"Error adding {description}: {str(e)}")
        db.session.rollback()
        return False

def random_phone():
    """Generate a random Egyptian phone number"""
    return f"+20 1{random.randint(0, 2)}{random.randint(0, 9)} {random.randint(1000, 9999)} {random.randint(1000, 9999)}"

def random_sku():
    """Generate a random SKU"""
    return ''.join(random.choices(string.ascii_uppercase, k=3)) + '-' + ''.join(random.choices(string.digits, k=5))

def seed_categories(count=10):
    """Seed categories table"""
    print(f"Seeding {count} categories...")
    category_types = ['FinalProduct', 'Packaging', 'RawMaterial', 'IntermediateProduct']
    categories = []
    
    for i in range(count):
        category = Category(
            name=fake.word().capitalize() + " " + fake.word().capitalize(),
            description=fake.sentence(),
            category_type=random.choice(category_types)
        )
        categories.append(category)
    
    db.session.add_all(categories)
    db.session.commit()
    return categories

def seed_items(count=50, categories=None):
    """Seed items table"""
    print(f"Seeding {count} items...")
    if not categories:
        categories = Category.query.all()
        if not categories:
            categories = seed_categories()
    
    items = []
    units = ['kg', 'g', 'l', 'ml', 'piece', 'box', 'pack']
    
    for i in range(count):
        cost = round(random.uniform(5, 500), 2)
        price = round(cost * random.uniform(1.2, 2.5), 2)
        
        item = Item(
            name=fake.word().capitalize() + " " + fake.word().capitalize(),
            category_id=random.choice(categories).id,
            sku=random_sku(),
            description=fake.paragraph(),
            unit_of_measure=random.choice(units),
            cost=cost,
            price=price,
            reorder_level=random.randint(10, 100),
            created_at=fake.date_time_this_year(),
            updated_at=fake.date_time_this_month()
        )
        items.append(item)
    
    db.session.add_all(items)
    db.session.commit()
    return items

def seed_warehouses(count=5):
    """Seed warehouses table"""
    print(f"Seeding {count} warehouses...")
    warehouses = []
    
    for i in range(count):
        warehouse = Warehouse(
            name=f"Warehouse {fake.city()}",
            location=fake.address(),
            capacity=random.randint(1000, 10000),
            contact_info=random_phone(),
            item_location=fake.word()
        )
        warehouses.append(warehouse)
    
    db.session.add_all(warehouses)
    db.session.commit()
    return warehouses

def seed_warehouse_sections(warehouses=None):
    """Seed warehouse sections"""
    print("Seeding warehouse sections...")
    if not warehouses:
        warehouses = Warehouse.query.all()
        if not warehouses:
            warehouses = seed_warehouses()
    
    sections = []
    
    for warehouse in warehouses:
        section_count = random.randint(2, 5)
        for i in range(section_count):
            section = WarehouseSection(
                warehouse_id=warehouse.id,
                section_name=f"Section {chr(65+i)}",
                row_count=random.randint(5, 15),
                column_count=random.randint(5, 15)
            )
            sections.append(section)
    
    db.session.add_all(sections)
    db.session.commit()
    return sections

def seed_warehouse_slots(sections=None):
    """Seed warehouse slots"""
    print("Seeding warehouse slots...")
    if not sections:
        sections = WarehouseSection.query.all()
        if not sections:
            sections = seed_warehouse_sections()
    
    slots = []
    
    for section in sections:
        for row in range(1, section.row_count + 1):
            for col in range(1, section.column_count + 1):
                slot = WarehouseSlot(
                    section_id=section.id,
                    row_number=row,
                    column_number=col
                )
                slots.append(slot)
    
    db.session.add_all(slots)
    db.session.commit()
    return slots

def seed_suppliers(count=20):
    """Seed suppliers table"""
    print(f"Seeding {count} suppliers...")
    suppliers = []
    
    for i in range(count):
        supplier = Supplier(
            supplier_name=fake.company(),
            contact_info=fake.paragraph(),
            payment_terms=random.choice(['Net 30', 'Net 60', 'Net 90', 'Immediate']),
            rating=round(random.uniform(1, 5), 1),
            email=fake.company_email(),
            phone=random_phone(),
            address=fake.address(),
            tax_id=f"TAX-{fake.numerify('#####')}",
            website=fake.url(),
            contact_person=fake.name(),
            notes=fake.paragraph()
        )
        suppliers.append(supplier)
    
    db.session.add_all(suppliers)
    db.session.commit()
    return suppliers

def seed_supplier_items(suppliers=None, items=None):
    """Seed supplier items"""
    print("Seeding supplier items...")
    if not suppliers:
        suppliers = Supplier.query.all()
        if not suppliers:
            suppliers = seed_suppliers()
    
    if not items:
        items = Item.query.all()
        if not items:
            items = seed_items()
    
    supplier_items = []
    
    for supplier in suppliers:
        # Each supplier provides 3-10 items
        item_count = random.randint(3, 10)
        supplier_item_ids = random.sample([item.id for item in items], min(item_count, len(items)))
        
        for item_id in supplier_item_ids:
            item = next((i for i in items if i.id == item_id), None)
            if item:
                supplier_item = SupplierItem(
                    supplier_id=supplier.id,
                    item_id=item_id,
                    supplier_sku=f"S-{random_sku()}",
                    cost=round(item.cost * random.uniform(0.8, 0.95), 2)  # Supplier cost is lower than our cost
                )
                supplier_items.append(supplier_item)
    
    db.session.add_all(supplier_items)
    db.session.commit()
    return supplier_items

def seed_customers(count=30):
    """Seed customers table"""
    print(f"Seeding {count} customers...")
    customers = []
    
    for i in range(count):
        customer = Customer(
            customer_name=fake.company() if random.random() > 0.5 else fake.name(),
            contact_info=f"Phone: {random_phone()}, Email: {fake.email()}",
            billing_address=fake.address(),
            shipping_address=fake.address() if random.random() > 0.7 else None
        )
        customers.append(customer)
    
    db.session.add_all(customers)
    db.session.commit()
    return customers

def seed_boms(items=None):
    """Seed BOM and BOM details"""
    print("Seeding BOMs...")
    if not items:
        items = Item.query.all()
        if not items:
            items = seed_items()
    
    # Get final products
    final_products = [item for item in items if item.category.category_type == 'FinalProduct']
    if not final_products:
        # If no final products, use some random items
        final_products = random.sample(items, min(10, len(items)))
    
    # Get components (raw materials and packaging)
    components = [item for item in items if item.category.category_type in ['RawMaterial', 'Packaging', 'IntermediateProduct']]
    if not components:
        # If no components, use some random items different from final products
        all_ids = set(item.id for item in items)
        final_product_ids = set(item.id for item in final_products)
        component_ids = all_ids - final_product_ids
        components = [item for item in items if item.id in component_ids]
    
    boms = []
    bom_details = []
    
    for product in final_products:
        bom = BOM(
            final_product_id=product.id,
            description=f"BOM for {product.name}",
            created_at=fake.date_time_this_year(),
            updated_at=fake.date_time_this_month()
        )
        db.session.add(bom)
        db.session.flush()  # Get the ID without committing
        
        # Add 2-6 components to each BOM
        component_count = random.randint(2, min(6, len(components)))
        selected_components = random.sample(components, component_count)
        
        for component in selected_components:
            detail = BOMDetail(
                bom_id=bom.id,
                component_item_id=component.id,
                quantity_required=round(random.uniform(0.1, 10), 2),
                unit_of_measure=component.unit_of_measure
            )
            bom_details.append(detail)
    
    db.session.add_all(bom_details)
    db.session.commit()
    return boms

def seed_inventory(items=None, warehouses=None):
    """Seed inventory"""
    print("Seeding inventory...")
    if not items:
        items = Item.query.all()
        if not items:
            items = seed_items()
    
    if not warehouses:
        warehouses = Warehouse.query.all()
        if not warehouses:
            warehouses = seed_warehouses()
    
    inventories = []
    
    for item in items:
        # Each item is in 1-3 warehouses
        warehouse_count = random.randint(1, min(3, len(warehouses)))
        selected_warehouses = random.sample(warehouses, warehouse_count)
        
        for warehouse in selected_warehouses:
            inventory = Inventory(
                item_id=item.id,
                warehouse_id=warehouse.id,
                quantity=random.randint(10, 1000),
                last_updated=fake.date_time_this_month()
            )
            inventories.append(inventory)
    
    db.session.add_all(inventories)
    db.session.commit()
    return inventories

def seed_purchase_orders(suppliers=None, items=None):
    """Seed purchase orders"""
    print("Seeding purchase orders...")
    if not suppliers:
        suppliers = Supplier.query.all()
        if not suppliers:
            suppliers = seed_suppliers()
    
    if not items:
        items = Item.query.all()
        if not items:
            items = seed_items()
    
    # Get supplier items mapping
    supplier_items_map = {}
    for supplier in suppliers:
        supplier_items = SupplierItem.query.filter_by(supplier_id=supplier.id).all()
        if supplier_items:
            supplier_items_map[supplier.id] = [si.item_id for si in supplier_items]
        else:
            # If no supplier items, assign random items
            supplier_items_map[supplier.id] = random.sample([item.id for item in items], min(5, len(items)))
    
    purchase_orders = []
    po_details = []
    statuses = ['Pending', 'Approved', 'Received', 'Cancelled']
    
    # Create 30-50 purchase orders
    po_count = random.randint(30, 50)
    
    for i in range(po_count):
        supplier = random.choice(suppliers)
        status = random.choice(statuses)
        order_date = fake.date_time_this_year()
        
        po = PurchaseOrder(
            supplier_id=supplier.id,
            order_date=order_date,
            status=status
        )
        db.session.add(po)
        db.session.flush()  # Get the ID without committing
        
        # Add 1-5 items to each PO
        available_items = supplier_items_map.get(supplier.id, [])
        if not available_items:
            continue
            
        item_count = random.randint(1, min(5, len(available_items)))
        selected_item_ids = random.sample(available_items, item_count)
        
        total_amount = 0
        
        for item_id in selected_item_ids:
            item = next((i for i in items if i.id == item_id), None)
            if not item:
                continue
                
            quantity = random.randint(5, 100)
            unit_price = round(item.cost * random.uniform(0.8, 1.1), 2)
            
            detail = PurchaseOrderDetail(
                po_id=po.id,
                item_id=item_id,
                quantity_ordered=quantity,
                unit_price=unit_price,
                quantity_received=quantity if status == 'Received' else (
                    random.randint(0, quantity) if status == 'Approved' else 0
                )
            )
            po_details.append(detail)
            total_amount += quantity * unit_price
        
        po.total_amount = round(total_amount, 2)
    
    db.session.add_all(po_details)
    db.session.commit()
    
    # Create ledger entries for purchase orders
    ledger_entries = []
    for po in purchase_orders:
        if po.status != 'Cancelled':
            ledger_entry = SupplierLedgerEntry(
                supplier_id=po.supplier_id,
                entry_date=po.order_date,
                description=f"Purchase Order #{po.id}",
                reference_type='purchase_order',
                reference_id=po.id,
                debit=po.total_amount  # Debit increases when we order from supplier
            )
            ledger_entries.append(ledger_entry)
    
    db.session.add_all(ledger_entries)
    db.session.commit()
    return purchase_orders

def seed_supplier_payments(suppliers=None):
    """Seed supplier payments"""
    print("Seeding supplier payments...")
    if not suppliers:
        suppliers = Supplier.query.all()
        if not suppliers:
            suppliers = seed_suppliers()
    
    payments = []
    ledger_entries = []
    payment_methods = ['Bank Transfer', 'Cash', 'Check', 'Credit Card']
    
    for supplier in suppliers:
        # Get total debits for this supplier
        total_debit = db.session.query(db.func.sum(SupplierLedgerEntry.debit)).filter_by(supplier_id=supplier.id).scalar() or 0
        
        # Make 1-3 payments for each supplier
        payment_count = random.randint(1, 3)
        for i in range(payment_count):
            # Pay between 20% and 100% of the total debit
            if total_debit > 0:
                amount = round(total_debit * random.uniform(0.2, 1.0), 2)
                payment_date = fake.date_time_this_month()
                
                payment = SupplierPayment(
                    supplier_id=supplier.id,
                    amount=amount,
                    payment_date=payment_date,
                    payment_method=random.choice(payment_methods),
                    reference=f"PAY-{fake.numerify('#####')}",
                    notes=fake.sentence(),
                    created_at=payment_date
                )
                payments.append(payment)
                
                # Create ledger entry for this payment
                ledger_entry = SupplierLedgerEntry(
                    supplier_id=supplier.id,
                    entry_date=payment_date,
                    description=f"Payment {payment.reference}",
                    reference_type='payment',
                    reference_id=payment.id,
                    credit=amount  # Credit increases when we pay the supplier
                )
                ledger_entries.append(ledger_entry)
                
                total_debit -= amount
    
    db.session.add_all(payments)
    db.session.flush()  # Get IDs without committing
    
    # Update reference_id in ledger entries
    for i, payment in enumerate(payments):
        ledger_entries[i].reference_id = payment.id
    
    db.session.add_all(ledger_entries)
    db.session.commit()
    return payments

def seed_sales_orders(customers=None, items=None):
    """Seed sales orders"""
    print("Seeding sales orders...")
    if not customers:
        customers = Customer.query.all()
        if not customers:
            customers = seed_customers()
    
    if not items:
        items = Item.query.all()
        if not items:
            items = seed_items()
    
    # Get final products for sales
    final_products = [item for item in items if item.category.category_type == 'FinalProduct']
    if not final_products:
        # If no final products, use some random items
        final_products = random.sample(items, min(10, len(items)))
    
    sales_orders = []
    so_details = []
    statuses = ['Pending', 'Processing', 'Shipped', 'Delivered', 'Cancelled']
    
    # Create 50-100 sales orders
    so_count = random.randint(50, 100)
    
    for i in range(so_count):
        customer = random.choice(customers)
        status = random.choice(statuses)
        order_date = fake.date_time_this_year()
        
        so = SalesOrder(
            customer_id=customer.id,
            order_date=order_date,
            status=status
        )
        db.session.add(so)
        db.session.flush()  # Get the ID without committing
        
        # Add 1-5 items to each SO
        item_count = random.randint(1, 5)
        selected_products = random.sample(final_products, min(item_count, len(final_products)))
        
        total_amount = 0
        
        for product in selected_products:
            quantity = random.randint(1, 20)
            unit_price = round(product.price * random.uniform(0.9, 1.2), 2)  # Some discount or markup
            
            detail = SalesOrderDetail(
                sales_order_id=so.id,
                item_id=product.id,
                quantity_ordered=quantity,
                unit_price=unit_price,
                quantity_shipped=quantity if status in ['Shipped', 'Delivered'] else (
                    random.randint(0, quantity) if status == 'Processing' else 0
                )
            )
            so_details.append(detail)
            total_amount += quantity * unit_price
        
        so.total_amount = round(total_amount, 2)
    
    db.session.add_all(so_details)
    db.session.commit()
    return sales_orders

def seed_batches(items=None):
    """Seed batches"""
    print("Seeding batches...")
    if not items:
        items = Item.query.all()
        if not items:
            items = seed_items()
    
    # Get final products for batches
    final_products = [item for item in items if item.category.category_type == 'FinalProduct']
    if not final_products:
        # If no final products, use some random items
        final_products = random.sample(items, min(10, len(items)))
    
    batches = []
    
    for product in final_products:
        # Create 1-3 batches for each product
        batch_count = random.randint(1, 3)
        
        for i in range(batch_count):
            production_date = fake.date_time_this_year()
            expiry_date = production_date + datetime.timedelta(days=random.randint(30, 365))
            
            batch = Batch(
                item_id=product.id,
                lot_number=f"LOT-{product.id}-{fake.numerify('######')}",
                production_date=production_date,
                expiry_date=expiry_date,
                quantity=random.randint(50, 500),
                status=random.choice(['Created', 'InProduction', 'QCPending', 'QCPassed', 'Packaged', 'Stored'])
            )
            batches.append(batch)
    
    db.session.add_all(batches)
    db.session.commit()
    return batches

def seed_quality_checks(batches=None):
    """Seed quality checks"""
    print("Seeding quality checks...")
    if not batches:
        batches = Batch.query.all()
        if not batches:
            batches = seed_batches()
    
    # Create QC parameters if they don't exist
    parameters = QCParameter.query.all()
    if not parameters:
        param_names = ['pH', 'Temperature', 'Weight', 'Color', 'Texture', 'Moisture', 'Density']
        parameters = []
        
        for name in param_names:
            param = QCParameter(
                param_name=name,
                reference_range=f"{random.randint(1, 5)}-{random.randint(6, 10)}"
            )
            parameters.append(param)
        
        db.session.add_all(parameters)
        db.session.commit()
    
    quality_checks = []
    qc_results = []
    
    for batch in batches:
        # 80% chance of having a quality check
        if random.random() < 0.8:
            check_date = batch.production_date + datetime.timedelta(days=random.randint(1, 5))
            status = random.choice(['Passed', 'Failed', 'Retest'])
            
            qc = QualityCheck(
                batch_id=batch.id,
                check_date=check_date,
                inspector_name=fake.name(),
                status=status
            )
            db.session.add(qc)
            db.session.flush()  # Get the ID without committing
            
            # Add results for each parameter
            for param in parameters:
                result = QualityCheckResult(
                    qc_id=qc.id,
                    param_name=param.param_name,
                    param_value=str(round(random.uniform(1, 10), 2))
                )
                qc_results.append(result)
            
            quality_checks.append(qc)
    
    db.session.add_all(qc_results)
    db.session.commit()
    return quality_checks

def seed_equipment(count=10):
    """Seed equipment"""
    print(f"Seeding {count} equipment...")
    equipment_list = []
    
    for i in range(count):
        last_maintenance = fake.date_time_this_year()
        
        equipment = Equipment(
            name=f"{fake.word().capitalize()} Machine {i+1}",
            serial_number=fake.numerify('SN-######'),
            location=fake.word().capitalize() + " Area",
            last_maintenance_date=last_maintenance,
            maintenance_interval=random.randint(30, 180)  # days
        )
        equipment_list.append(equipment)
    
    db.session.add_all(equipment_list)
    db.session.commit()
    return equipment_list

def seed_maintenance_logs(equipment=None):
    """Seed maintenance logs"""
    print("Seeding maintenance logs...")
    if not equipment:
        equipment = Equipment.query.all()
        if not equipment:
            equipment = seed_equipment()
    
    logs = []
    
    for eq in equipment:
        # Create 1-5 maintenance logs for each equipment
        log_count = random.randint(1, 5)
        
        for i in range(log_count):
            maintenance_date = fake.date_time_this_year()
            
            log = MaintenanceLog(
                equipment_id=eq.id,
                maintenance_date=maintenance_date,
                technician_name=fake.name(),
                notes=fake.paragraph()
            )
            logs.append(log)
    
    db.session.add_all(logs)
    db.session.commit()
    return logs

def seed_shipments(sales_orders=None):
    """Seed shipments"""
    print("Seeding shipments...")
    if not sales_orders:
        sales_orders = SalesOrder.query.all()
        if not sales_orders:
            sales_orders = seed_sales_orders()
    
    # Get shipped or delivered orders
    shipped_orders = [so for so in sales_orders if so.status in ['Shipped', 'Delivered']]
    
    shipments = []
    shipment_details = []
    
    for order in shipped_orders:
        shipment_date = order.order_date + datetime.timedelta(days=random.randint(1, 5))
        estimated_arrival = shipment_date + datetime.timedelta(days=random.randint(1, 7))
        
        shipment = Shipment(
            carrier_name=fake.company(),
            tracking_number=fake.numerify('TRK-#########'),
            shipment_date=shipment_date,
            estimated_arrival=estimated_arrival,
            customer_id=order.customer_id
        )
        db.session.add(shipment)
        db.session.flush()  # Get the ID without committing
        
        # Add details for each order item
        order_details = SalesOrderDetail.query.filter_by(sales_order_id=order.id).all()
        
        for detail in order_details:
            if detail.quantity_shipped > 0:
                shipment_detail = ShipmentDetail(
                    shipment_id=shipment.id,
                    item_id=detail.item_id,
                    quantity_shipped=detail.quantity_shipped
                )
                shipment_details.append(shipment_detail)
        
        shipments.append(shipment)
    
    db.session.add_all(shipment_details)
    db.session.commit()
    return shipments

def seed_production_runs(items=None):
    """Seed production runs"""
    print("Seeding production runs...")
    if not items:
        items = Item.query.all()
        if not items:
            items = seed_items()
    
    # Get final products
    final_products = [item for item in items if item.category.category_type == 'FinalProduct']
    if not final_products:
        # If no final products, use some random items
        final_products = random.sample(items, min(10, len(items)))
    
    # Get BOMs
    boms = BOM.query.all()
    bom_map = {bom.final_product_id: bom.id for bom in boms}
    
    production_runs = []
    run_details = []
    
    # Create 20-30 production runs
    run_count = random.randint(20, 30)
    
    for i in range(run_count):
        start_date = fake.date_time_this_year()
        end_date = start_date + datetime.timedelta(days=random.randint(1, 14))
        status = random.choice(['Planned', 'In Progress', 'Completed'])
        
        run = ProductionRun(
            planned_start_date=start_date,
            planned_end_date=end_date,
            status=status
        )
        db.session.add(run)
        db.session.flush()  # Get the ID without committing
        
        # Add 1-3 products to each run
        product_count = random.randint(1, 3)
        selected_products = random.sample(final_products, min(product_count, len(final_products)))
        
        for product in selected_products:
            bom_id = bom_map.get(product.id)
            
            detail = ProductionRunDetail(
                production_run_id=run.id,
                item_id=product.id,
                quantity_planned=random.randint(50, 500),
                bom_id=bom_id
            )
            run_details.append(detail)
        
        production_runs.append(run)
    
    db.session.add_all(run_details)
    db.session.commit()
    return production_runs

def seed_cash_accounts(count=3):
    """Seed cash accounts"""
    print(f"Seeding {count} cash accounts...")
    accounts = []
    account_types = ['cash', 'bank', 'credit_card']
    currencies = ['EGP', 'USD', 'EUR']
    
    for i in range(count):
        initial_balance = round(random.uniform(1000, 100000), 2)
        
        account = CashAccount(
            name=f"{random.choice(['Main', 'Secondary', 'Reserve', 'Petty'])} {random.choice(account_types).capitalize()} Account",
            account_type=random.choice(account_types),
            currency=random.choice(currencies),
            initial_balance=initial_balance,
            current_balance=initial_balance,
            is_active=True,
            created_at=fake.date_time_this_year()
        )
        accounts.append(account)
    
    db.session.add_all(accounts)
    db.session.commit()
    return accounts

def seed_cash_transactions(accounts=None, count=50):
    """Seed cash transactions"""
    print(f"Seeding {count} cash transactions...")
    if not accounts:
        accounts = CashAccount.query.all()
        if not accounts:
            accounts = seed_cash_accounts()
    
    transactions = []
    transaction_types = ['deposit', 'withdrawal', 'transfer']
    reference_types = ['supplier_payment', 'sales_receipt', 'expense', 'salary', 'other']
    
    for i in range(count):
        account = random.choice(accounts)
        transaction_type = random.choice(transaction_types)
        amount = round(random.uniform(100, 5000), 2)
        
        transaction = CashTransaction(
            account_id=account.id,
            transaction_type=transaction_type,
            amount=amount,
            reference_type=random.choice(reference_types),
            reference_id=random.randint(1, 1000),
            description=fake.sentence(),
            transaction_date=fake.date_time_this_year()
        )
        transactions.append(transaction)
        
        # Update account balance
        if transaction_type == 'deposit':
            account.current_balance += amount
        elif transaction_type == 'withdrawal':
            account.current_balance -= amount
    
    db.session.add_all(transactions)
    db.session.commit()
    return transactions

def seed_roles_and_permissions():
    """Seed roles and permissions"""
    print("Seeding roles and permissions...")
    
    # Create roles if they don't exist
    roles = Role.query.all()
    if not roles:
        role_names = ['admin', 'manager', 'inventory_manager', 'sales_rep', 'production_manager', 'quality_control', 'warehouse_worker']
        roles = []
        
        for name in role_names:
            role = Role(name=name)
            roles.append(role)
        
        db.session.add_all(roles)
        db.session.commit()
    
    # Create permissions if they don't exist
    permissions = Permission.query.all()
    if not permissions:
        permission_names = [
            'view_inventory', 'edit_inventory',
            'view_sales', 'create_sales', 'edit_sales',
            'view_purchases', 'create_purchases', 'edit_purchases',
            'view_production', 'create_production', 'edit_production',
            'view_quality', 'create_quality', 'edit_quality',
            'view_reports', 'create_reports',
            'view_users', 'create_users', 'edit_users',
            'view_settings', 'edit_settings'
        ]
        permissions = []
        
        for name in permission_names:
            permission = Permission(permission_name=name)
            permissions.append(permission)
        
        db.session.add_all(permissions)
        db.session.commit()
    
    # Assign permissions to roles
    role_permissions = RolePermission.query.all()
    if not role_permissions:
        # Admin has all permissions
        admin_role = Role.query.filter_by(name='admin').first()
        if admin_role:
            for permission in permissions:
                role_permission = RolePermission(role_id=admin_role.id, permission_id=permission.id)
                db.session.add(role_permission)
        
        # Manager has most permissions
        manager_role = Role.query.filter_by(name='manager').first()
        if manager_role:
            manager_permissions = [p for p in permissions if 'edit_settings' not in p.permission_name and 'edit_users' not in p.permission_name]
            for permission in manager_permissions:
                role_permission = RolePermission(role_id=manager_role.id, permission_id=permission.id)
                db.session.add(role_permission)
        
        # Inventory manager permissions
        inventory_role = Role.query.filter_by(name='inventory_manager').first()
        if inventory_role:
            inventory_permissions = [p for p in permissions if any(x in p.permission_name for x in ['inventory', 'purchases', 'view_reports'])]
            for permission in inventory_permissions:
                role_permission = RolePermission(role_id=inventory_role.id, permission_id=permission.id)
                db.session.add(role_permission)
        
        # Sales rep permissions
        sales_role = Role.query.filter_by(name='sales_rep').first()
        if sales_role:
            sales_permissions = [p for p in permissions if any(x in p.permission_name for x in ['sales', 'view_inventory', 'view_reports'])]
            for permission in sales_permissions:
                role_permission = RolePermission(role_id=sales_role.id, permission_id=permission.id)
                db.session.add(role_permission)
        
        db.session.commit()
    
    return roles, permissions

def seed_users(count=10, roles=None):
    """Seed users"""
    print(f"Seeding {count} users...")
    if not roles:
        roles = Role.query.all()
        if not roles:
            roles, _ = seed_roles_and_permissions()
    
    # Create admin user if it doesn't exist
    admin_user = User.query.filter_by(username='admin').first()
    if not admin_user:
        admin_role = Role.query.filter_by(name='admin').first()
        admin_user = User(
            username='admin',
            email='admin@example.com',
            role_id=admin_role.id if admin_role else None,
            is_active=True,
            phone=random_phone(),
            hire_date=datetime.datetime.now().date(),
            department='Administration',
            position='System Administrator'
        )
        admin_user.set_password('admin123')
        db.session.add(admin_user)
        db.session.commit()
    
    users = []
    departments = ['Sales', 'Production', 'Warehouse', 'QC', 'Purchasing', 'Finance', 'HR']
    positions = ['Manager', 'Supervisor', 'Specialist', 'Assistant', 'Coordinator']
    
    for i in range(count):
        role = random.choice(roles)
        department = random.choice(departments)
        position = random.choice(positions)
        
        # Ensure username is unique and within length limit (50 chars)
        username = (fake.user_name() + str(random.randint(1, 999)))[:50]
        
        # Ensure email is within length limit (50 chars)
        email = fake.email()[:50]
        
        # Check if username or email already exists
        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            continue
        
        # Ensure other string fields are within limits
        identification_number = fake.numerify('ID-#######')[:50]
        nationality = fake.country()[:50]
        address = fake.address()[:255]  # Assuming address has a larger limit
        department_str = department[:50]
        position_str = f"{department} {position}"[:50]
        
        # Create emergency contact with limited string lengths
        emergency_contact = {
            'name': fake.name()[:50],
            'phone': random_phone()[:20],
            'relation': random.choice(['Spouse', 'Parent', 'Sibling', 'Friend'])[:20]
        }
        
        user = User(
            username=username,
            email=email,
            role_id=role.id,
            is_active=True,
            phone=random_phone()[:20],
            birthdate=fake.date_of_birth(minimum_age=18, maximum_age=65),
            hire_date=fake.date_this_decade(),
            identification_number=identification_number,
            gender=random.choice(['Male', 'Female']),
            nationality=nationality,
            address=address,
            department=department_str,
            position=position_str,
            salary=round(random.uniform(3000, 15000), 2),
            emergency_contact=emergency_contact,
            created_at=fake.date_time_this_year()
        )
        user.set_password('password123')
        users.append(user)
    
    # Add users in smaller batches to avoid large parameter lists
    batch_size = 10
    for i in range(0, len(users), batch_size):
        batch = users[i:i+batch_size]
        db.session.add_all(batch)
        db.session.commit()
    
    return users


def seed_documents(count=20, users=None):
    """Seed documents"""
    print(f"Seeding {count} documents...")
    if not users:
        users = User.query.all()
        if not users:
            users = seed_users()
    
    documents = []
    categories = ['Recipe', 'Certification', 'Manual', 'Other']
    
    for i in range(count):
        document = Document(
            title=fake.sentence(nb_words=4),
            file_path=f"/static/uploads/{fake.file_name(extension='pdf')}",
            category=random.choice(categories),
            uploaded_by=random.choice(users).id,
            upload_date=fake.date_time_this_year()
        )
        documents.append(document)
    
    db.session.add_all(documents)
    db.session.commit()
    return documents

def seed_sales_representatives(users=None):
    """Seed sales representatives"""
    print("Seeding sales representatives...")
    if not users:
        users = User.query.all()
        if not users:
            users = seed_users()
    
    # Get users with sales_rep role
    sales_role = Role.query.filter_by(name='sales_rep').first()
    if sales_role:
        sales_users = [user for user in users if user.role_id == sales_role.id]
    else:
        # If no sales_rep role, use random users
        sales_users = random.sample(users, min(5, len(users)))
    
    representatives = []
    territories = ['North', 'South', 'East', 'West', 'Central', 'Northeast', 'Southeast', 'Northwest', 'Southwest']
    
    for user in sales_users:
        # Check if user already has a sales rep profile
        existing_rep = SalesRepresentative.query.filter_by(user_id=user.id).first()
        if existing_rep:
            continue
        
        rep = SalesRepresentative(
            user_id=user.id,
            territory=random.choice(territories),
            commission_rate=round(random.uniform(0.01, 0.1), 2),
            is_active=True
        )
        representatives.append(rep)
    
    db.session.add_all(representatives)
    db.session.commit()
    return representatives

def seed_representative_routes(representatives=None, customers=None):
    """Seed representative routes"""
    print("Seeding representative routes...")
    if not representatives:
        representatives = SalesRepresentative.query.all()
        if not representatives:
            representatives = seed_sales_representatives()
    
    if not customers:
        customers = Customer.query.all()
        if not customers:
            customers = seed_customers()
    
    routes = []
    visits = []
    
    for rep in representatives:
        # Create 1-5 routes for each representative
        route_count = random.randint(1, 5)
        
        for i in range(route_count):
            route_date = fake.date_this_month()
            status = random.choice(['Planned', 'In Progress', 'Completed', 'Cancelled'])
            
            route = RepresentativeRoute(
                representative_id=rep.id,
                route_name=f"Route {fake.city()} {i+1}",
                route_date=route_date,
                status=status,
                notes=fake.paragraph(),
                created_at=fake.date_time_this_month()
            )
            db.session.add(route)
            db.session.flush()  # Get the ID without committing
            
            # Add 3-10 customer visits to each route
            visit_count = random.randint(3, 10)
            selected_customers = random.sample(customers, min(visit_count, len(customers)))
            
            for j, customer in enumerate(selected_customers):
                scheduled_time = datetime.datetime.combine(
                    route_date,
                    datetime.time(hour=9 + j, minute=random.randint(0, 59))
                )
                
                visit = CustomerVisit(
                    route_id=route.id,
                    customer_id=customer.id,
                    scheduled_time=scheduled_time,
                    actual_visit_time=scheduled_time + datetime.timedelta(minutes=random.randint(-30, 30)) if status == 'Completed' else None,
                    status='Completed' if status == 'Completed' else 'Pending',
                    visit_notes=fake.paragraph(),
                    visit_outcome=random.choice(['Sale', 'No Sale', 'Follow-up Required']),
                    follow_up_date=route_date + datetime.timedelta(days=random.randint(7, 30)) if random.random() > 0.5 else None,
                    location_latitude=float(fake.latitude()),
                    location_longitude=float(fake.longitude())
                )
                visits.append(visit)
            
            routes.append(route)
    
    db.session.add_all(visits)
    db.session.commit()
    return routes

def seed_ai_suggestions(items=None, categories=None):
    """Seed AI suggestions"""
    print("Seeding AI suggestions...")
    if not items:
        items = Item.query.all()
        if not items:
            items = seed_items()
    
    if not categories:
        categories = Category.query.all()
        if not categories:
            categories = seed_categories()
    
    suggestions = []
    suggestion_types = ['NameImprovement', 'CategoryMismatch', 'ReorderLevelAdjustment', 'InventoryAnomaly']
    
    # Create 10-20 suggestions
    suggestion_count = random.randint(10, 20)
    
    for i in range(suggestion_count):
        suggestion_type = random.choice(suggestion_types)
        
        if suggestion_type in ['NameImprovement', 'ReorderLevelAdjustment', 'InventoryAnomaly']:
            item = random.choice(items)
            category = None
            
            if suggestion_type == 'NameImprovement':
                suggestion_text = f"The item name '{item.name}' could be improved for better searchability and clarity."
                suggested_value = f"{item.name} {fake.word().capitalize()}"
            elif suggestion_type == 'ReorderLevelAdjustment':
                suggestion_text = f"Based on historical data, the reorder level for '{item.name}' should be adjusted."
                suggested_value = str(item.reorder_level + random.randint(-10, 20))
            else:  # InventoryAnomaly
                suggestion_text = f"Unusual inventory movement detected for '{item.name}'. Please verify recent transactions."
                suggested_value = None
        else:  # CategoryMismatch
            item = random.choice(items)
            category = random.choice(categories)
            if category.id != item.category_id:
                suggestion_text = f"The item '{item.name}' might be better categorized under '{category.name}' instead of its current category."
                suggested_value = str(category.id)
            else:
                # Find a different category
                other_categories = [c for c in categories if c.id != item.category_id]
                if other_categories:
                    category = random.choice(other_categories)
                    suggestion_text = f"The item '{item.name}' might be better categorized under '{category.name}' instead of its current category."
                    suggested_value = str(category.id)
                else:
                    continue
        
        suggestion = AISuggestion(
            item_id=item.id if item else None,
            category_id=category.id if category else None,
            suggestion_type=suggestion_type,
            suggestion_text=suggestion_text,
            suggested_value=suggested_value,
            status=random.choice(['Pending', 'Applied', 'Dismissed']),
            created_at=fake.date_time_this_month()
        )
        suggestions.append(suggestion)
    
    db.session.add_all(suggestions)
    db.session.commit()
    return suggestions

def seed_inventory_transactions(items=None, warehouses=None, count=100):
    """Seed inventory transactions"""
    print(f"Seeding {count} inventory transactions...")
    if not items:
        items = Item.query.all()
        if not items:
            items = seed_items()
    
    if not warehouses:
        warehouses = Warehouse.query.all()
        if not warehouses:
            warehouses = seed_warehouses()
    
    transactions = []
    transaction_types = ['IN', 'OUT', 'TRANSFER']
    references = ['Purchase', 'Sale', 'Production', 'Adjustment', 'Return', 'Transfer']
    
    for i in range(count):
        item = random.choice(items)
        warehouse = random.choice(warehouses)
        transaction_type = random.choice(transaction_types)
        
        transaction = InventoryTransaction(
            item_id=item.id,
            warehouse_id=warehouse.id,
            transaction_type=transaction_type,
            quantity=random.randint(1, 100),
            transaction_date=fake.date_time_this_year(),
            reference=f"{random.choice(references)}-{fake.numerify('####')}"
        )
        transactions.append(transaction)
    
    db.session.add_all(transactions)
    db.session.commit()
    
    # Update inventory quantities based on transactions
    for item in items:
        for warehouse in warehouses:
            # Calculate total IN and OUT for this item in this warehouse
            in_qty = db.session.query(db.func.sum(InventoryTransaction.quantity)).filter(
                InventoryTransaction.item_id == item.id,
                InventoryTransaction.warehouse_id == warehouse.id,
                InventoryTransaction.transaction_type == 'IN'
            ).scalar() or 0
            
            out_qty = db.session.query(db.func.sum(InventoryTransaction.quantity)).filter(
                InventoryTransaction.item_id == item.id,
                InventoryTransaction.warehouse_id == warehouse.id,
                InventoryTransaction.transaction_type == 'OUT'
            ).scalar() or 0
            
            # Get or create inventory record
            inventory = Inventory.query.filter_by(item_id=item.id, warehouse_id=warehouse.id).first()
            if inventory:
                inventory.quantity = max(0, in_qty - out_qty)
                inventory.last_updated = datetime.datetime.now()
            else:
                if in_qty > out_qty:
                    inventory = Inventory(
                        item_id=item.id,
                        warehouse_id=warehouse.id,
                        quantity=in_qty - out_qty,
                        last_updated=datetime.datetime.now()
                    )
                    db.session.add(inventory)
    
    db.session.commit()
    return transactions

def seed_batch_slots(batches=None, slots=None):
    """Seed batch slots"""
    print("Seeding batch slots...")
    if not batches:
        batches = Batch.query.all()
        if not batches:
            batches = seed_batches()
    
    if not slots:
        slots = WarehouseSlot.query.all()
        if not slots:
            slots = seed_warehouse_slots()
    
    batch_slots = []
    
    for batch in batches:
        # Assign each batch to 1-3 slots
        slot_count = random.randint(1, min(3, len(slots)))
        selected_slots = random.sample(slots, slot_count)
        
        remaining_quantity = batch.quantity
        
        for i, slot in enumerate(selected_slots):
            # Last slot gets all remaining quantity, others get random portions
            if i == len(selected_slots) - 1:
                quantity_in_slot = remaining_quantity
            else:
                quantity_in_slot = random.randint(1, remaining_quantity // 2)
                remaining_quantity -= quantity_in_slot
            
            batch_slot = BatchSlot(
                batch_id=batch.id,
                slot_id=slot.id,
                quantity_in_slot=quantity_in_slot
            )
            batch_slots.append(batch_slot)
            
            # Update slot with item and quantity
            slot.item_id = batch.item_id
            slot.quantity += quantity_in_slot
    
    db.session.add_all(batch_slots)
    db.session.commit()
    return batch_slots

def seed_product_packaging(batches=None, items=None, production_runs=None):
    """Seed product packaging"""
    print("Seeding product packaging...")
    if not batches:
        batches = Batch.query.all()
        if not batches:
            batches = seed_batches()
    
    if not items:
        items = Item.query.all()
        if not items:
            items = seed_items()
            
    if not production_runs:
        production_runs = ProductionRun.query.all()
        if not production_runs:
            production_runs = seed_production_runs(items)
    
    # Get packaging materials
    packaging_items = [item for item in items if item.category.category_type == 'Packaging']
    if not packaging_items:
        # If no packaging items, use some random items
        packaging_items = random.sample(items, min(5, len(items)))
    
    packagings = []
    packaging_materials = []
    
    # Only process batches that have a production_run_id
    valid_batches = [batch for batch in batches if batch.production_run_id is not None]
    
    # If no valid batches, assign random production runs to some batches
    if not valid_batches and production_runs:
        for batch in random.sample(batches, min(len(batches), len(production_runs))):
            batch.production_run_id = random.choice(production_runs).id
            valid_batches.append(batch)
        db.session.commit()
    
    for batch in valid_batches:
        # 70% chance of having packaging records
        if random.random() < 0.7:
            packaging_date = batch.production_date + datetime.timedelta(days=random.randint(1, 5))
            status = random.choice(['Pending', 'Completed', 'Cancelled'])
            
            packaging = ProductPackaging(
                production_run_id=batch.production_run_id,  # This is now guaranteed to be non-null
                batch_id=batch.id,
                packaging_date=packaging_date,
                status=status,
                notes=fake.paragraph()
            )
            db.session.add(packaging)
            db.session.flush()  # Get the ID without committing
            
            # Add 1-3 packaging materials
            material_count = random.randint(1, 3)
            selected_materials = random.sample(packaging_items, min(material_count, len(packaging_items)))
            
            for material in selected_materials:
                material_usage = PackagingMaterial(
                    packaging_id=packaging.id,
                    item_id=material.id,
                    quantity_used=random.randint(1, 100)
                )
                packaging_materials.append(material_usage)
            
            packagings.append(packaging)
    
    db.session.add_all(packaging_materials)
    db.session.commit()
    return packagings

def seed_all(scale='medium'):
    """Seed all tables with sample data"""
    print(f"Seeding database with {scale} scale data...")
    
    # Define scale factors
    if scale == 'small':
        category_count = 5
        item_count = 20
        warehouse_count = 2
        supplier_count = 10
        customer_count = 15
        equipment_count = 5
        user_count = 5
        document_count = 10
        transaction_count = 50
    elif scale == 'large':
        category_count = 20
        item_count = 200
        warehouse_count = 10
        supplier_count = 50
        customer_count = 100
        equipment_count = 20
        user_count = 30
        document_count = 50
        transaction_count = 500
    else:  # medium
        category_count = 10
        item_count = 50
        warehouse_count = 5
        supplier_count = 20
        customer_count = 30
        equipment_count = 10
        user_count = 10
        document_count = 20
        transaction_count = 100
    
    # Seed data in order of dependencies
    categories = seed_categories(category_count)
    items = seed_items(item_count, categories)
    warehouses = seed_warehouses(warehouse_count)
    sections = seed_warehouse_sections(warehouses)
    slots = seed_warehouse_slots(sections)
    suppliers = seed_suppliers(supplier_count)
    supplier_items = seed_supplier_items(suppliers, items)
    customers = seed_customers(customer_count)
    boms = seed_boms(items)
    purchase_orders = seed_purchase_orders(suppliers, items)
    supplier_payments = seed_supplier_payments(suppliers)
    sales_orders = seed_sales_orders(customers, items)
    production_runs = seed_production_runs(items)
    batches = seed_batches(items)
    quality_checks = seed_quality_checks(batches)
    equipment = seed_equipment(equipment_count)
    maintenance_logs = seed_maintenance_logs(equipment)
    shipments = seed_shipments(sales_orders)
    roles, permissions = seed_roles_and_permissions()
    users = seed_users(user_count, roles)
    documents = seed_documents(document_count, users)
    cash_accounts = seed_cash_accounts()
    cash_transactions = seed_cash_transactions(cash_accounts)
    representatives = seed_sales_representatives(users)
    routes = seed_representative_routes(representatives, customers)
    suggestions = seed_ai_suggestions(items, categories)
    transactions = seed_inventory_transactions(items, warehouses, transaction_count)
    batch_slots = seed_batch_slots(batches, slots)
    packagings = seed_product_packaging(batches, items, production_runs)
    
    print("Database seeding completed successfully!")

if __name__ == "__main__":
    with app.app_context():
        # Choose scale: 'small', 'medium', or 'large'
        seed_all('large')


