from datetime import datetime, timedelta
import random
from faker import Faker
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import *
from werkzeug.security import generate_password_hash

# Initialize Faker
fake = Faker('ar_EG')  # Using Arabic locale for more realistic data

# Database connection
engine = create_engine('postgresql://postgres:@localhost:5432/katiloerp')
Session = sessionmaker(bind=engine)
session = Session()

def create_categories():
    categories = []
    category_types = ['FinalProduct', 'Packaging', 'RawMaterial', 'IntermediateProduct']
    for _ in range(10):  # Create 10 categories
        category = Category(
            name=fake.word().capitalize(),
            description=fake.text(max_nb_chars=200),
            category_type=random.choice(category_types)
        )
        categories.append(category)
        session.add(category)
    session.commit()
    return categories

def create_items(categories):
    items = []
    for category in categories:
        for _ in range(20):  # Create 20 items per category
            item = Item(
                name=fake.word().capitalize(),
                category_id=category.id,
                sku=fake.unique.bothify(text='SKU-###-???'),
                description=fake.text(max_nb_chars=200),
                unit_of_measure=random.choice(['kg', 'g', 'l', 'ml', 'pcs']),
                cost=round(random.uniform(10, 1000), 2),
                price=round(random.uniform(20, 2000), 2),
                reorder_level=random.randint(10, 100)
            )
            items.append(item)
            session.add(item)
    session.commit()
    return items

def create_warehouses():
    warehouses = []
    for _ in range(3):  # Create 3 warehouses
        warehouse = Warehouse(
            name=fake.company(),
            location=fake.address(),
            capacity=random.randint(1000, 10000),
            contact_info=fake.phone_number()
        )
        warehouses.append(warehouse)
        session.add(warehouse)
    session.commit()
    return warehouses

def create_warehouse_sections(warehouses):
    sections = []
    for warehouse in warehouses:
        for _ in range(5):  # Create 5 sections per warehouse
            section = WarehouseSection(
                warehouse_id=warehouse.id,
                section_name=fake.word().capitalize(),
                row_count=random.randint(5, 20),
                column_count=random.randint(5, 20)
            )
            sections.append(section)
            session.add(section)
    session.commit()
    return sections

def create_warehouse_slots(sections):
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
                session.add(slot)
    session.commit()
    return slots

def create_suppliers():
    suppliers = []
    for _ in range(10):  # Create 10 suppliers
        supplier = Supplier(
            supplier_name=fake.company(),
            contact_info=fake.text(max_nb_chars=200),
            payment_terms=random.choice(['Net 30', 'Net 60', 'Net 90']),
            rating=round(random.uniform(1, 5), 1),
            email=fake.email(),
            phone=fake.phone_number(),
            address=fake.address(),
            tax_id=fake.bothify(text='TAX-###-???'),
            website=fake.url(),
            contact_person=fake.name(),
            notes=fake.text(max_nb_chars=200)
        )
        suppliers.append(supplier)
        session.add(supplier)
    session.commit()
    return suppliers

def create_supplier_items(suppliers, items):
    for supplier in suppliers:
        # Assign 5-10 random items to each supplier
        supplier_items = random.sample(items, random.randint(5, 10))
        for item in supplier_items:
            supplier_item = SupplierItem(
                supplier_id=supplier.id,
                item_id=item.id,
                supplier_sku=fake.unique.bothify(text='SUP-###-???'),
                cost=round(item.cost * random.uniform(0.8, 1.2), 2)
            )
            session.add(supplier_item)
    session.commit()

def create_customers():
    customers = []
    for _ in range(20):  # Create 20 customers
        customer = Customer(
            customer_name=fake.company(),
            contact_info=fake.text(max_nb_chars=200),
            billing_address=fake.address(),
            shipping_address=fake.address()
        )
        customers.append(customer)
        session.add(customer)
    session.commit()
    return customers

def create_sales_orders(customers, items):
    orders = []
    for customer in customers:
        # Create 1-3 orders per customer
        for _ in range(random.randint(1, 3)):
            order = SalesOrder(
                customer_id=customer.id,
                order_date=fake.date_time_between(start_date='-30d', end_date='now'),
                status=random.choice(['Pending', 'Processing', 'Shipped', 'Delivered', 'Cancelled']),
                total_amount=0  # Will be calculated after adding details
            )
            session.add(order)
            session.flush()  # To get the order ID
            
            # Add 2-5 items to each order
            order_items = random.sample(items, random.randint(2, 5))
            total_amount = 0
            for item in order_items:
                quantity = random.randint(1, 10)
                unit_price = item.price
                total_amount += quantity * unit_price
                
                detail = SalesOrderDetail(
                    sales_order_id=order.id,
                    item_id=item.id,
                    quantity_ordered=quantity,
                    unit_price=unit_price,
                    quantity_shipped=quantity if order.status in ['Shipped', 'Delivered'] else 0
                )
                session.add(detail)
            
            order.total_amount = total_amount
            orders.append(order)
    session.commit()
    return orders

def create_inventory(items, warehouses):
    for item in items:
        for warehouse in warehouses:
            inventory = Inventory(
                item_id=item.id,
                warehouse_id=warehouse.id,
                quantity=random.randint(0, 1000)
            )
            session.add(inventory)
    session.commit()

def create_inventory_transactions(items, warehouses):
    for item in items:
        for warehouse in warehouses:
            # Create 5-10 transactions per item per warehouse
            for _ in range(random.randint(5, 10)):
                transaction = InventoryTransaction(
                    item_id=item.id,
                    warehouse_id=warehouse.id,
                    transaction_type=random.choice(['IN', 'OUT', 'TRANSFER']),
                    quantity=random.randint(1, 100),
                    transaction_date=fake.date_time_between(start_date='-30d', end_date='now'),
                    reference=fake.bothify(text='TRX-###-???')
                )
                session.add(transaction)
    session.commit()

def create_cash_accounts():
    account_types = ['cash', 'bank']
    for _ in range(5):  # Create 5 cash accounts
        account = CashAccount(
            name=fake.company(),
            account_type=random.choice(account_types),
            currency='EGP',
            initial_balance=round(random.uniform(1000, 10000), 2),
            current_balance=round(random.uniform(1000, 10000), 2),
            is_active=True
        )
        session.add(account)
    session.commit()

def create_vehicles():
    vehicles = []
    vehicle_types = ['Van', 'Truck', 'Pickup']
    for _ in range(5):  # Create 5 vehicles
        vehicle = Vehicle(
            name=fake.company(),
            vehicle_type=random.choice(vehicle_types),
            plate_number=fake.unique.bothify(text='###-???'),
            model=fake.word().capitalize(),
            year=random.randint(2015, 2024),
            status='Active',
            max_weight=random.randint(1000, 5000),
            max_volume=random.randint(5, 20),
            max_length=random.randint(3000, 6000),
            max_height=random.randint(2000, 3000),
            last_maintenance_date=fake.date_time_between(start_date='-30d', end_date='now'),
            next_maintenance_date=fake.date_time_between(start_date='+30d', end_date='+90d'),
            notes=fake.text(max_nb_chars=200)
        )
        vehicles.append(vehicle)
        session.add(vehicle)
    session.commit()
    return vehicles

def create_users():
    # First check if the sales representative role exists
    sales_role = session.query(Role).filter_by(name='sales_representative').first()
    if not sales_role:
        # Create the role if it doesn't exist
        sales_role = Role(name='sales_representative')
        session.add(sales_role)
        session.flush()  # To get the role ID
    
    users = []
    for i in range(5):  # Create 5 users for sales representatives
        # Generate unique username (max 80 chars)
        username = f"sales_rep_{i+1}"
        
        # Check if user already exists
        existing_user = session.query(User).filter_by(username=username).first()
        if existing_user:
            users.append(existing_user)
            continue
            
        # Generate unique email (max 120 chars)
        email = f"sales_rep_{i+1}@katilo.com"
        
        # Generate unique identification number (max 50 chars)
        identification_number = f"ID-{i+1:03d}-{fake.bothify(text='???')}"
        
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash('password123'),  # Default password
            role_id=sales_role.id,
            is_active=True,
            phone=fake.numerify(text='01########'),  # Egyptian phone format
            birthdate=fake.date_of_birth(minimum_age=18, maximum_age=60),
            hire_date=fake.date_between(start_date='-2y', end_date='now'),
            identification_number=identification_number,
            gender=random.choice(['Male', 'Female']),
            nationality='Egyptian',
            address=fake.address(),
            department='Sales',
            position='Sales Representative',
            salary=round(random.uniform(5000, 15000), 2)
        )
        users.append(user)
        session.add(user)
    session.commit()
    return users

def create_sales_representatives(users):
    reps = []
    for user in users:
        rep = SalesRepresentative(
            user_id=user.id,
            territory=fake.city(),
            commission_rate=round(random.uniform(0.05, 0.15), 2),
            is_active=True
        )
        reps.append(rep)
        session.add(rep)
    session.commit()
    return reps

def create_representative_routes(reps, customers):
    routes = []
    for rep in reps:
        # Create 2-4 routes per representative
        for _ in range(random.randint(2, 4)):
            route = RepresentativeRoute(
                representative_id=rep.id,
                route_name=f"Route {fake.word().capitalize()}",
                route_date=fake.date_between(start_date='-30d', end_date='+30d'),
                status=random.choice(['Planned', 'In Progress', 'Completed', 'Cancelled']),
                notes=fake.text(max_nb_chars=200)
            )
            session.add(route)
            session.flush()  # Flush to get the route ID
            routes.append(route)
            
            # Add 3-8 customer visits to each route
            route_customers = random.sample(customers, min(random.randint(3, 8), len(customers)))
            for i, customer in enumerate(route_customers):
                visit = CustomerVisit(
                    route_id=route.id,  # Now we have the route ID
                    customer_id=customer.id,
                    scheduled_time=fake.date_time_between(start_date='-30d', end_date='+30d'),
                    actual_visit_time=fake.date_time_between(start_date='-30d', end_date='+30d') if route.status != 'Planned' else None,
                    status=route.status,
                    visit_notes=fake.text(max_nb_chars=200),
                    visit_outcome=random.choice(['Sale', 'No Sale', 'Follow-up Required']),
                    follow_up_date=fake.date_between(start_date='+1d', end_date='+30d') if random.random() > 0.7 else None,
                    location_latitude=float(fake.latitude()),
                    location_longitude=float(fake.longitude())
                )
                session.add(visit)
            session.commit()  # Commit after each route and its visits
    return routes

def create_shipments(orders, vehicles):
    shipments = []
    for order in orders:
        if order.status in ['Shipped', 'Delivered']:
            shipment = Shipment(
                carrier_name=random.choice(['Local Delivery', 'Express', 'Standard']),
                tracking_number=fake.unique.bothify(text='TRK-###-???'),
                shipment_date=order.order_date + timedelta(days=random.randint(1, 5)),
                estimated_arrival=order.order_date + timedelta(days=random.randint(2, 7)),
                customer_id=order.customer_id
            )
            shipments.append(shipment)
            session.add(shipment)
            
            # Create shipment details
            for detail in order.details:
                shipment_detail = ShipmentDetail(
                    shipment_id=shipment.id,
                    item_id=detail.item_id,
                    quantity_shipped=detail.quantity_shipped
                )
                session.add(shipment_detail)
            
            # Create shipment order with correct status
            shipment_order = ShipmentOrder(
                sales_order_id=order.id,
                shipment_id=shipment.id,
                vehicle_id=random.choice(vehicles).id if vehicles else None,
                status='InTransit' if order.status == 'Shipped' else 'Delivered',
                assigned_date=shipment.shipment_date,
                estimated_delivery_date=shipment.estimated_arrival,
                actual_delivery_date=shipment.estimated_arrival + timedelta(days=random.randint(-1, 1)) if order.status == 'Delivered' else None
            )
            session.add(shipment_order)
    session.commit()
    return shipments

def create_delivery_routes(vehicles, shipments):
    routes = []
    for vehicle in vehicles:
        # Create a route for each vehicle
        route = DeliveryRoute(
            name=f"Route {vehicle.plate_number} - {fake.date_between(start_date='+1d', end_date='+7d').strftime('%Y-%m-%d')}",
            vehicle_id=vehicle.id,
            status='Planned',
            planned_date=fake.date_between(start_date='+1d', end_date='+7d'),
            total_distance=round(random.uniform(50, 200), 2),
            estimated_duration=random.randint(120, 480),  # 2-8 hours in minutes
            notes=fake.text(max_nb_chars=200)
        )
        routes.append(route)
        session.add(route)
        session.flush()  # Get the route ID before creating stops
        
        # Get shipment orders for this vehicle
        vehicle_shipment_orders = [so for so in session.query(ShipmentOrder).filter_by(vehicle_id=vehicle.id).all()]
        if not vehicle_shipment_orders:
            continue
            
        # Create stops for each shipment order
        for i, shipment_order in enumerate(vehicle_shipment_orders, 1):
            # Update shipment order with route information
            shipment_order.route_id = route.id
            shipment_order.route_position = i
            
            # Create route stop
            stop = RouteStop(
                route_id=route.id,  # Set the route_id
                customer_id=shipment_order.sales_order.customer_id,
                shipment_order_id=shipment_order.id,
                stop_number=i,
                planned_arrival_time=route.planned_date + timedelta(hours=i*2),  # 2 hours between stops
                address=shipment_order.sales_order.customer.shipping_address,  # Use shipping_address instead of address
                latitude=float(fake.latitude()),
                longitude=float(fake.longitude()),
                status='Planned',
                notes=fake.text(max_nb_chars=200)
            )
            session.add(stop)
        
        session.commit()  # Commit after each route and its stops
    return routes

def main():
    try:
        print("Starting database population...")
        
        # Create base data
        print("Creating categories...")
        categories = create_categories()
        
        print("Creating items...")
        items = create_items(categories)
        
        print("Creating warehouses...")
        warehouses = create_warehouses()
        
        print("Creating warehouse sections...")
        sections = create_warehouse_sections(warehouses)
        
        print("Creating warehouse slots...")
        slots = create_warehouse_slots(sections)
        
        print("Creating suppliers...")
        suppliers = create_suppliers()
        
        print("Creating supplier items...")
        create_supplier_items(suppliers, items)
        
        print("Creating customers...")
        customers = create_customers()
        
        print("Creating sales orders...")
        orders = create_sales_orders(customers, items)
        
        print("Creating inventory...")
        create_inventory(items, warehouses)
        
        print("Creating inventory transactions...")
        create_inventory_transactions(items, warehouses)
        
        print("Creating cash accounts...")
        create_cash_accounts()
        
        print("Creating vehicles...")
        vehicles = create_vehicles()
        
        print("Creating users...")
        users = create_users()
        
        print("Creating sales representatives...")
        reps = create_sales_representatives(users)
        
        print("Creating representative routes...")
        routes = create_representative_routes(reps, customers)
        
        print("Creating shipments...")
        shipments = create_shipments(orders, vehicles)
        
        print("Creating delivery routes...")
        delivery_routes = create_delivery_routes(vehicles, shipments)
        
        print("Database population completed successfully!")
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    main()
