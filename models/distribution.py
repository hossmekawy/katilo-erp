from datetime import datetime
from sqlalchemy import CheckConstraint, ForeignKey, Enum as SAEnum
from models import db, SalesOrder, Shipment, Customer

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
