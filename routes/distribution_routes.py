from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from sqlalchemy import or_, and_, func
import json
import os
import base64
import sys

# Add the parent directory to sys.path to allow importing from the root directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import from the models_helper module
from models_helper import (
    db, SalesOrder, SalesOrderDetail, Customer, Shipment, ShipmentDetail, Item,
    Vehicle, VehicleStorage, ShipmentOrder, DeliveryRoute, RouteStop, ShipmentTracking,
    vehicle_status_enum, shipment_status_enum, route_status_enum
)

# Create blueprint
distribution_bp = Blueprint('distribution', __name__, url_prefix='/distribution')

# Dashboard
@distribution_bp.route('/')
@login_required
def index():
    return redirect(url_for('distribution.dashboard'))

@distribution_bp.route('/dashboard')
@login_required
def dashboard():
    # Get statistics for dashboard
    total_vehicles = Vehicle.query.count()
    active_vehicles = Vehicle.query.filter_by(status='Active').count()
    maintenance_vehicles = Vehicle.query.filter_by(status='Maintenance').count()

    # Get shipment statistics
    total_shipments = ShipmentOrder.query.count()
    pending_shipments = ShipmentOrder.query.filter_by(status='Pending').count()
    in_transit_shipments = ShipmentOrder.query.filter_by(status='InTransit').count()
    delivered_shipments = ShipmentOrder.query.filter_by(status='Delivered').count()

    # Get recent shipments
    recent_shipments = ShipmentOrder.query.order_by(ShipmentOrder.created_at.desc()).limit(5).all()

    # Get active routes
    active_routes = DeliveryRoute.query.filter_by(status='InProgress').all()

    # Get vehicles in transit
    vehicles_in_transit = Vehicle.query.join(ShipmentOrder).filter(
        ShipmentOrder.status == 'InTransit'
    ).distinct().all()

    return render_template(
        'distribution/dashboard.html',
        total_vehicles=total_vehicles,
        active_vehicles=active_vehicles,
        maintenance_vehicles=maintenance_vehicles,
        total_shipments=total_shipments,
        pending_shipments=pending_shipments,
        in_transit_shipments=in_transit_shipments,
        delivered_shipments=delivered_shipments,
        recent_shipments=recent_shipments,
        active_routes=active_routes,
        vehicles_in_transit=vehicles_in_transit
    )

# Vehicle Management
@distribution_bp.route('/vehicles')
@login_required
def vehicles():
    return render_template('distribution/vehicles/index.html')

@distribution_bp.route('/vehicles/new')
@login_required
def new_vehicle():
    return render_template('distribution/vehicles/new.html')

@distribution_bp.route('/vehicles/<int:vehicle_id>')
@login_required
def view_vehicle(vehicle_id):
    try:
        # Use eager loading to load all related data in a single query
        vehicle = Vehicle.query.options(
            db.joinedload(Vehicle.storage),
            db.joinedload(Vehicle.shipments).joinedload(ShipmentOrder.sales_order).joinedload(SalesOrder.customer),
            db.joinedload(Vehicle.routes).joinedload(DeliveryRoute.stops)
        ).get_or_404(vehicle_id)

        return render_template('distribution/vehicles/view.html', vehicle=vehicle)
    except Exception as e:
        # Log the error
        current_app.logger.error(f"Error loading vehicle data: {str(e)}")
        flash(f"حدث خطأ أثناء تحميل بيانات المركبة: {str(e)}", "error")
        return redirect(url_for('distribution.vehicles'))

@distribution_bp.route('/vehicles/<int:vehicle_id>/edit')
@login_required
def edit_vehicle(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)
    return render_template('distribution/vehicles/edit.html', vehicle=vehicle)

# API endpoints for vehicles
@distribution_bp.route('/api/vehicles', methods=['GET'])
@login_required
def get_vehicles():  # This function name is used in templates with url_for
    try:
        # Use eager loading to load storage data
        vehicles = Vehicle.query.options(db.joinedload(Vehicle.storage)).all()

        result = []
        for v in vehicles:
            vehicle_data = {
                'id': v.id,
                'name': v.name,
                'vehicle_type': v.vehicle_type,
                'plate_number': v.plate_number,
                'model': v.model,
                'year': v.year,
                'status': v.status,
                'max_weight': v.max_weight,
                'max_volume': v.max_volume,
                'max_length': v.max_length,
                'max_height': v.max_height,
                'image_path': v.image_path,
                'image_data': None,  # Default to None since it might not exist in the model
                'storage': {
                    'weight_utilization': v.storage.weight_utilization if v.storage else 0,
                    'volume_utilization': v.storage.volume_utilization if v.storage else 0,
                    'current_weight': v.storage.current_weight if v.storage else 0,
                    'current_volume': v.storage.current_volume if v.storage else 0
                } if v.storage else {
                    'weight_utilization': 0,
                    'volume_utilization': 0,
                    'current_weight': 0,
                    'current_volume': 0
                }
            }

            # Check if image_data attribute exists before trying to access it
            if hasattr(v, 'image_data'):
                vehicle_data['image_data'] = v.image_data

            result.append(vehicle_data)

        return jsonify(result)
    except Exception as e:
        # Log the error
        current_app.logger.error(f"Error loading vehicles data: {str(e)}")
        return jsonify({'error': 'حدث خطأ أثناء تحميل بيانات المركبات', 'vehicles': []}), 500

@distribution_bp.route('/api/vehicles', methods=['POST'])
@login_required
def create_vehicle():  # This function name is used in templates with url_for
    # Check if the request contains form data with files
    if request.files and 'vehicle_image' in request.files:
        data = request.form.to_dict()
        image_file = request.files['vehicle_image']
        current_app.logger.info(f"Received image file: {image_file.filename}")

        # Process the image if it exists
        image_data = None
        if image_file and image_file.filename:
            try:
                # Read the file and encode it
                image_data = base64.b64encode(image_file.read()).decode('utf-8')
                current_app.logger.info(f"Successfully processed image: {image_file.filename}")
            except Exception as e:
                current_app.logger.error(f"Error processing image: {str(e)}")
    else:
        data = request.json
        image_data = data.get('image_data')

    # Validate required fields
    if not data.get('name') or not data.get('plate_number') or not data.get('vehicle_type'):
        return jsonify({'success': False, 'message': 'Name, plate number, and vehicle type are required'}), 400

    # Check if plate number already exists
    if Vehicle.query.filter_by(plate_number=data['plate_number']).first():
        return jsonify({'success': False, 'message': 'A vehicle with this plate number already exists'}), 400

    try:
        # Create vehicle with basic attributes
        vehicle_attrs = {
            'name': data['name'],
            'vehicle_type': data['vehicle_type'],
            'plate_number': data['plate_number'],
            'model': data.get('model'),
            'year': data.get('year'),
            'status': data.get('status', 'Active'),
            'max_weight': data.get('max_weight'),
            'max_volume': data.get('max_volume'),
            'max_length': data.get('max_length'),
            'max_height': data.get('max_height'),
            'notes': data.get('notes'),
            'image_path': data.get('image_path')
        }

        # Always try to set image_data if it exists
        if image_data:
            vehicle_attrs['image_data'] = image_data
            current_app.logger.info("Image data added to vehicle attributes")

        vehicle = Vehicle(**vehicle_attrs)

        db.session.add(vehicle)
        db.session.flush()  # Get the vehicle ID

        # Create vehicle storage
        storage = VehicleStorage(
            vehicle_id=vehicle.id,
            current_weight=0,
            current_volume=0,
            weight_utilization=0,
            volume_utilization=0
        )

        db.session.add(storage)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Vehicle created successfully',
            'vehicle_id': vehicle.id
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@distribution_bp.route('/api/vehicles/<int:vehicle_id>', methods=['PUT'])
@login_required
def update_vehicle(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)

    # Check if the request contains form data with files
    if request.files and 'vehicle_image' in request.files:
        data = request.form.to_dict()
        image_file = request.files['vehicle_image']
        current_app.logger.info(f"Received image file for update: {image_file.filename}")

        # Process the image if it exists
        if image_file and image_file.filename:
            try:
                # Read the file and encode it
                image_data = base64.b64encode(image_file.read()).decode('utf-8')
                # Always try to set image_data
                vehicle.image_data = image_data
                current_app.logger.info(f"Successfully processed image for vehicle {vehicle_id}: {image_file.filename}")
            except Exception as e:
                current_app.logger.error(f"Error processing image for vehicle {vehicle_id}: {str(e)}")
    else:
        data = request.json
        if 'image_data' in data:
            try:
                vehicle.image_data = data['image_data']
                current_app.logger.info(f"Image data updated for vehicle {vehicle_id} from JSON")
            except Exception as e:
                current_app.logger.error(f"Error setting image_data for vehicle {vehicle_id}: {str(e)}")

    try:
        # Update vehicle fields
        if 'name' in data:
            vehicle.name = data['name']
        if 'vehicle_type' in data:
            vehicle.vehicle_type = data['vehicle_type']
        if 'plate_number' in data:
            # Check if plate number already exists for another vehicle
            existing = Vehicle.query.filter_by(plate_number=data['plate_number']).first()
            if existing and existing.id != vehicle_id:
                return jsonify({'success': False, 'message': 'A vehicle with this plate number already exists'}), 400
            vehicle.plate_number = data['plate_number']
        if 'model' in data:
            vehicle.model = data['model']
        if 'year' in data:
            vehicle.year = data['year']
        if 'status' in data:
            vehicle.status = data['status']
        if 'max_weight' in data:
            vehicle.max_weight = data['max_weight']
        if 'max_volume' in data:
            vehicle.max_volume = data['max_volume']
        if 'max_length' in data:
            vehicle.max_length = data['max_length']
        if 'max_height' in data:
            vehicle.max_height = data['max_height']
        if 'notes' in data:
            vehicle.notes = data['notes']
        if 'image_path' in data:
            vehicle.image_path = data['image_path']

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Vehicle updated successfully'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@distribution_bp.route('/api/vehicles/<int:vehicle_id>', methods=['DELETE'])
@login_required
def delete_vehicle(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)

    # Check if vehicle has active shipments
    active_shipments = ShipmentOrder.query.filter_by(vehicle_id=vehicle_id).filter(
        ShipmentOrder.status.in_(['Assigned', 'InTransit'])
    ).first()

    if active_shipments:
        return jsonify({
            'success': False,
            'message': 'Cannot delete vehicle with active shipments'
        }), 400

    try:
        db.session.delete(vehicle)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Vehicle deleted successfully'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# Shipment Management
@distribution_bp.route('/shipments')
@login_required
def shipments():
    return render_template('distribution/shipments/index.html')

@distribution_bp.route('/shipments/assign')
@login_required
def assign_shipment_page():
    # Get available vehicles and pending sales orders
    vehicles = Vehicle.query.filter_by(status='Active').all()

    # Make sure we're using the correct field names
    pending_orders = SalesOrder.query.filter_by(status='Processing').all()

    # Debug information
    current_app.logger.debug(f"Found {len(pending_orders)} pending orders")
    for order in pending_orders:
        current_app.logger.debug(f"Order ID: {order.id}, Customer: {order.customer.customer_name if order.customer else 'None'}")

    # Pass the correct data to the template
    return render_template(
        'distribution/shipments/assign.html',
        vehicles=vehicles,
        pending_orders=pending_orders
    )

@distribution_bp.route('/api/shipments/assign', methods=['POST'])
@login_required
def assign_shipment():
    data = request.json
    current_app.logger.debug(f"Received shipment assignment data: {data}")

    # Validate required fields
    if not data.get('sales_order_id') or not data.get('vehicle_id'):
        return jsonify({'success': False, 'message': 'Sales order ID and vehicle ID are required'}), 400

    try:
        # Get the sales order
        sales_order = SalesOrder.query.get_or_404(data['sales_order_id'])

        # Check if order already has a shipment
        existing_shipment = ShipmentOrder.query.filter_by(sales_order_id=sales_order.id).first()
        if existing_shipment:
            return jsonify({'success': False, 'message': 'This order already has a shipment assigned'}), 400

        # Get the vehicle and its storage
        vehicle = Vehicle.query.get_or_404(data['vehicle_id'])
        vehicle_storage = vehicle.storage

        if not vehicle_storage:
            # Create storage if it doesn't exist
            vehicle_storage = VehicleStorage(
                vehicle_id=vehicle.id,
                current_weight=0,
                current_volume=0,
                weight_utilization=0,
                volume_utilization=0
            )
            db.session.add(vehicle_storage)
            db.session.flush()

        # Calculate total weight and volume of the shipment
        total_weight = 0
        total_volume = 0

        for detail in sales_order.details:
            item = detail.item
            if item:
                # Use item weight and volume if available, otherwise default to 0
                item_weight = item.weight or 0
                item_volume = item.volume or 0

                # Multiply by quantity
                total_weight += item_weight * detail.quantity_ordered
                total_volume += item_volume * detail.quantity_ordered

        # Check if vehicle has enough capacity
        new_weight = vehicle_storage.current_weight + total_weight
        new_volume = vehicle_storage.current_volume + total_volume

        # Calculate utilization percentages
        weight_utilization = 0
        volume_utilization = 0

        if vehicle.max_weight and vehicle.max_weight > 0:
            weight_utilization = (new_weight / vehicle.max_weight) * 100

        if vehicle.max_volume and vehicle.max_volume > 0:
            volume_utilization = (new_volume / vehicle.max_volume) * 100

        # Check if exceeding capacity
        if weight_utilization > 100:
            return jsonify({
                'success': False,
                'message': f'Vehicle weight capacity exceeded. Required: {new_weight:.2f} kg, Available: {vehicle.max_weight:.2f} kg'
            }), 400

        if volume_utilization > 100:
            return jsonify({
                'success': False,
                'message': f'Vehicle volume capacity exceeded. Required: {new_volume:.2f} m³, Available: {vehicle.max_volume:.2f} m³'
            }), 400

        # Parse the estimated delivery date if provided
        estimated_delivery_date = None
        if data.get('estimated_delivery_date'):
            try:
                estimated_delivery_date = datetime.fromisoformat(data['estimated_delivery_date'])
            except ValueError:
                # If parsing fails, use default (tomorrow)
                estimated_delivery_date = datetime.now() + timedelta(days=1)
        else:
            estimated_delivery_date = datetime.now() + timedelta(days=1)

        # Create a new shipment
        shipment = Shipment(
            carrier_name=data.get('carrier_name', 'Internal Delivery'),
            tracking_number=f"SHIP-{datetime.now().strftime('%Y%m%d')}-{sales_order.id}",
            shipment_date=datetime.now(),
            estimated_arrival=estimated_delivery_date,
            customer_id=sales_order.customer_id
        )

        db.session.add(shipment)
        db.session.flush()  # Get the shipment ID

        # Create shipment details for each order item
        for detail in sales_order.details:
            shipment_detail = ShipmentDetail(
                shipment_id=shipment.id,
                item_id=detail.item_id,
                quantity_shipped=detail.quantity_ordered
            )
            db.session.add(shipment_detail)

        # Create shipment order
        shipment_order = ShipmentOrder(
            sales_order_id=sales_order.id,
            shipment_id=shipment.id,
            vehicle_id=data['vehicle_id'],
            status='Assigned',
            assigned_date=datetime.now(),
            estimated_delivery_date=estimated_delivery_date,
            notes=data.get('notes', '')
        )

        db.session.add(shipment_order)

        # Update sales order status
        sales_order.status = 'Shipped'

        # Update vehicle storage
        vehicle_storage.current_weight = new_weight
        vehicle_storage.current_volume = new_volume
        vehicle_storage.weight_utilization = weight_utilization
        vehicle_storage.volume_utilization = volume_utilization

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Shipment assigned successfully',
            'shipment_id': shipment.id,
            'shipment_order_id': shipment_order.id,
            'vehicle_capacity': {
                'weight_utilization': weight_utilization,
                'volume_utilization': volume_utilization
            }
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error assigning shipment: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@distribution_bp.route('/api/shipments', methods=['GET'])
@login_required
def get_shipments():  # This function name is used in templates with url_for
    # Use eager loading to load related data efficiently
    shipments = ShipmentOrder.query.options(
        db.joinedload(ShipmentOrder.sales_order).joinedload(SalesOrder.customer),
        db.joinedload(ShipmentOrder.vehicle),
        db.joinedload(ShipmentOrder.route)
    ).all()

    result = []
    for s in shipments:
        # Get customer information
        customer = s.sales_order.customer if s.sales_order else None
        customer_data = {
            'id': customer.id if customer else None,
            'name': customer.customer_name if customer else None,
            'address': customer.shipping_address if customer else None,
        }

        # Try to extract coordinates from route stops if available
        customer_latitude = None
        customer_longitude = None

        # Check if this shipment is part of a route with stops
        if s.route_id and s.route:
            # Find the stop for this shipment
            for stop in s.route.stops:
                if stop.shipment_order_id == s.id:
                    customer_latitude = stop.latitude
                    customer_longitude = stop.longitude
                    break

        shipment_data = {
            'id': s.id,
            'sales_order_id': s.sales_order_id,
            'shipment_id': s.shipment_id,
            'vehicle_id': s.vehicle_id,
            'vehicle_name': s.vehicle.name if s.vehicle else None,
            'status': s.status,
            'assigned_date': s.assigned_date.isoformat() if s.assigned_date else None,
            'estimated_delivery_date': s.estimated_delivery_date.isoformat() if s.estimated_delivery_date else None,
            'actual_delivery_date': s.actual_delivery_date.isoformat() if s.actual_delivery_date else None,
            'customer_id': customer_data['id'],
            'customer_name': customer_data['name'],
            'customer_address': customer_data['address'],
            'customer_latitude': customer_latitude,
            'customer_longitude': customer_longitude,
            'route_id': s.route_id,
            'route_name': s.route.name if s.route else None
        }

        result.append(shipment_data)

    return jsonify(result)

# Route Management
@distribution_bp.route('/routes')
@login_required
def routes():
    return render_template('distribution/routes/index.html')

@distribution_bp.route('/routes/new')
@login_required
def new_route():
    # Get available vehicles and assigned shipments
    vehicles = Vehicle.query.filter_by(status='Active').all()
    assigned_shipments = ShipmentOrder.query.filter_by(status='Assigned').all()

    # Check if default customer for custom stations exists, create if not
    default_customer = Customer.query.filter_by(customer_name='Custom Stations').first()
    if not default_customer:
        try:
            default_customer = Customer(
                customer_name='Custom Stations',
                contact_info='System generated customer for custom stations',
                shipping_address='Custom station locations',
                billing_address='N/A'
            )
            db.session.add(default_customer)
            db.session.commit()
            current_app.logger.info("Created default customer for custom stations with ID: %s", default_customer.id)
        except Exception as e:
            current_app.logger.error("Error creating default customer: %s", str(e))
            db.session.rollback()
            # If we can't create it, we'll use ID 1 as fallback
            default_customer_id = 1

    default_customer_id = default_customer.id if default_customer else 1

    return render_template(
        'distribution/routes/new.html',
        vehicles=vehicles,
        assigned_shipments=assigned_shipments,
        default_customer_id=default_customer_id,
        google_maps_api_key=current_app.config.get('GOOGLE_MAPS_API_KEY')
    )

@distribution_bp.route('/routes/<int:route_id>')
@login_required
def view_route(route_id):
    route = DeliveryRoute.query.get_or_404(route_id)
    return render_template(
        'distribution/routes/view.html',
        route=route,
        google_maps_api_key=current_app.config.get('GOOGLE_MAPS_API_KEY')
    )

@distribution_bp.route('/api/routes', methods=['POST'])
@login_required
def create_route():  # This function name is used in templates with url_for
    data = request.json

    # Validate required fields
    if not data.get('name') or not data.get('vehicle_id') or not data.get('planned_date'):
        return jsonify({'success': False, 'message': 'Name, vehicle ID, and planned date are required'}), 400

    if not data.get('stops') or len(data['stops']) == 0:
        return jsonify({'success': False, 'message': 'At least one stop is required'}), 400

    try:
        # Create new route
        route = DeliveryRoute(
            name=data['name'],
            vehicle_id=data['vehicle_id'],
            status='Planned',
            planned_date=datetime.fromisoformat(data['planned_date'].replace('Z', '+00:00')),
            total_distance=data.get('total_distance'),
            estimated_duration=data.get('estimated_duration'),
            notes=data.get('notes', '')
        )

        db.session.add(route)
        db.session.flush()  # Get the route ID

        # Create route stops
        for i, stop in enumerate(data['stops']):
            route_stop = RouteStop(
                route_id=route.id,
                customer_id=stop['customer_id'],
                shipment_order_id=stop.get('shipment_order_id'),
                stop_number=i + 1,
                planned_arrival_time=datetime.fromisoformat(stop['planned_arrival_time'].replace('Z', '+00:00')) if stop.get('planned_arrival_time') else None,
                address=stop.get('address', ''),
                latitude=stop.get('latitude'),
                longitude=stop.get('longitude'),
                status='Pending',
                notes=stop.get('notes', '')
            )

            db.session.add(route_stop)

            # Update shipment order with route information
            if stop.get('shipment_order_id'):
                shipment_order = ShipmentOrder.query.get(stop['shipment_order_id'])
                if shipment_order:
                    shipment_order.route_id = route.id
                    shipment_order.route_position = i + 1

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Route created successfully',
            'route_id': route.id
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@distribution_bp.route('/api/routes', methods=['GET'])
@login_required
def get_routes():  # This function name is used in templates with url_for
    routes = DeliveryRoute.query.all()

    return jsonify([{
        'id': r.id,
        'name': r.name,
        'vehicle_id': r.vehicle_id,
        'vehicle_name': r.vehicle.name if r.vehicle else None,
        'status': r.status,
        'planned_date': r.planned_date.isoformat() if r.planned_date else None,
        'start_time': r.start_time.isoformat() if r.start_time else None,
        'end_time': r.end_time.isoformat() if r.end_time else None,
        'total_distance': r.total_distance,
        'estimated_duration': r.estimated_duration,
        'actual_duration': r.actual_duration,
        'stops_count': len(r.stops),
        'completed_stops_count': len([s for s in r.stops if s.status == 'Completed'])
    } for r in routes])

@distribution_bp.route('/api/routes/<int:route_id>/start', methods=['POST'])
@distribution_bp.route('/distribution/api/routes/<int:route_id>/start', methods=['POST'])  # Add alternative URL
@login_required
def start_route(route_id):  # This function name is used in templates with url_for
    route = DeliveryRoute.query.get_or_404(route_id)

    if route.status != 'Planned':
        return jsonify({'success': False, 'message': 'Only planned routes can be started'}), 400

    try:
        # Update route status
        route.status = 'InProgress'
        route.start_time = datetime.now()

        # Update shipment orders status
        for shipment in route.shipments:
            shipment.status = 'InTransit'

            # Create tracking update
            tracking = ShipmentTracking(
                shipment_order_id=shipment.id,
                status='InTransit',
                location_name='Route Started',
                notes='Delivery route started',
                created_by=current_user.id
            )
            db.session.add(tracking)

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Route started successfully'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@distribution_bp.route('/api/routes/<int:route_id>/complete', methods=['POST'])
@distribution_bp.route('/distribution/api/routes/<int:route_id>/complete', methods=['POST'])  # Add alternative URL
@login_required
def complete_route(route_id):  # This function name is used in templates with url_for
    route = DeliveryRoute.query.get_or_404(route_id)

    if route.status != 'InProgress':
        return jsonify({'success': False, 'message': 'Only in-progress routes can be completed'}), 400

    try:
        # Update route status
        route.status = 'Completed'
        route.end_time = datetime.now()

        # Calculate actual duration
        if route.start_time:
            duration = route.end_time - route.start_time
            route.actual_duration = int(duration.total_seconds() / 60)  # Convert to minutes

        # Update any remaining stops
        for stop in route.stops:
            if stop.status == 'Pending':
                stop.status = 'Skipped'

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Route completed successfully'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# Delivery Confirmation
@distribution_bp.route('/api/stops/<int:stop_id>/complete', methods=['POST'])
@distribution_bp.route('/distribution/api/stops/<int:stop_id>/complete', methods=['POST'])  # Add alternative URL
@login_required
def complete_stop(stop_id):
    stop = RouteStop.query.get_or_404(stop_id)
    data = request.json

    if stop.status != 'Pending':
        return jsonify({'success': False, 'message': 'This stop has already been processed'}), 400

    try:
        # Update stop status
        stop.status = 'Completed'
        stop.actual_arrival_time = datetime.now()
        stop.notes = data.get('notes', stop.notes)

        # If stop has a shipment, update it
        if stop.shipment_order:
            # Update shipment status
            stop.shipment_order.status = 'Delivered'
            stop.shipment_order.actual_delivery_date = datetime.now()

            # Update sales order status
            if stop.shipment_order.sales_order:
                stop.shipment_order.sales_order.status = 'Delivered'

            # Create tracking update
            tracking = ShipmentTracking(
                shipment_order_id=stop.shipment_order.id,
                status='Delivered',
                location_name=stop.address or f'Stop #{stop.stop_number}',
                latitude=stop.latitude,
                longitude=stop.longitude,
                notes=data.get('delivery_notes', 'Delivery completed'),
                created_by=current_user.id
            )
            db.session.add(tracking)

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Stop completed successfully'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# Tracking
@distribution_bp.route('/tracking')
@login_required
def tracking_index():
    return render_template('distribution/tracking/index.html',
                          google_maps_api_key=current_app.config.get('GOOGLE_MAPS_API_KEY'))

@distribution_bp.route('/tracking/<tracking_number>')
@login_required
def tracking(tracking_number):
    try:
        # Get shipment by tracking number
        shipment = Shipment.query.filter_by(tracking_number=tracking_number).first_or_404()

        # Get shipment order
        shipment_order = ShipmentOrder.query.filter_by(shipment_id=shipment.id).first()

        # Get tracking updates
        tracking_updates = []
        if shipment_order:
            tracking_updates = ShipmentTracking.query.filter_by(
                shipment_order_id=shipment_order.id
            ).order_by(ShipmentTracking.timestamp.desc()).all()

        # Convert objects to dictionaries for JSON serialization in the template
        shipment_dict = {
            'id': shipment.id,
            'tracking_number': shipment.tracking_number,
            'carrier_name': shipment.carrier_name,
            'shipment_date': shipment.shipment_date.isoformat() if shipment.shipment_date else None,
            'estimated_arrival': shipment.estimated_arrival.isoformat() if shipment.estimated_arrival else None,
            'customer_id': shipment.customer_id,
            'customer_name': shipment.customer.customer_name if shipment.customer else None
        }

        shipment_order_dict = None
        if shipment_order:
            shipment_order_dict = {
                'id': shipment_order.id,
                'status': shipment_order.status,
                'vehicle_id': shipment_order.vehicle_id,
                'vehicle_name': shipment_order.vehicle.name if shipment_order.vehicle else None,
                'route_id': shipment_order.route_id,
                'route_name': shipment_order.route.name if shipment_order.route else None,
                'estimated_delivery_date': shipment_order.estimated_delivery_date.isoformat() if shipment_order.estimated_delivery_date else None,
                'actual_delivery_date': shipment_order.actual_delivery_date.isoformat() if shipment_order.actual_delivery_date else None
            }

        tracking_updates_list = []
        for update in tracking_updates:
            tracking_updates_list.append({
                'id': update.id,
                'status': update.status,
                'timestamp': update.timestamp.isoformat(),
                'location_name': update.location_name,
                'latitude': update.latitude,
                'longitude': update.longitude,
                'notes': update.notes
            })

        current_app.logger.info(f"Rendering tracking page for shipment {tracking_number}")

        return render_template(
            'distribution/tracking/index.html',
            tracking_number=tracking_number,
            shipment=shipment_dict,
            shipment_order=shipment_order_dict,
            tracking_updates=tracking_updates_list,
            google_maps_api_key=current_app.config.get('GOOGLE_MAPS_API_KEY')
        )
    except Exception as e:
        current_app.logger.error(f"Error rendering tracking page for {tracking_number}: {str(e)}")
        flash(f"حدث خطأ أثناء تحميل بيانات التتبع: {str(e)}", "error")
        return redirect(url_for('distribution.tracking_index'))

# Public tracking route (no login required)
@distribution_bp.route('/public-tracking/<tracking_number>')
def public_tracking(tracking_number):
    try:
        # This route can be public for customers to track their shipments
        shipment = Shipment.query.filter_by(tracking_number=tracking_number).first_or_404()

        # Get the shipment order
        shipment_order = ShipmentOrder.query.filter_by(shipment_id=shipment.id).first()

        # Get tracking updates
        tracking_updates = []
        if shipment_order:
            tracking_updates = ShipmentTracking.query.filter_by(
                shipment_order_id=shipment_order.id
            ).order_by(ShipmentTracking.timestamp.desc()).all()

        # Get current date for footer
        now = datetime.now()

        # Check if any tracking updates have coordinates
        has_coordinates = any(update.latitude and update.longitude for update in tracking_updates)

        current_app.logger.info(f"Rendering public tracking page for shipment {tracking_number}")

        return render_template(
            'distribution/tracking/public.html',
            shipment=shipment,
            shipment_order=shipment_order,
            tracking_updates=tracking_updates,
            google_maps_api_key=current_app.config.get('GOOGLE_MAPS_API_KEY'),
            now=now,
            has_coordinates=has_coordinates
        )
    except Exception as e:
        current_app.logger.error(f"Error rendering public tracking page for {tracking_number}: {str(e)}")
        return render_template(
            'distribution/tracking/public_error.html',
            tracking_number=tracking_number,
            error_message=str(e),
            now=datetime.now()
        )

@distribution_bp.route('/api/tracking/<tracking_number>', methods=['GET'])
@distribution_bp.route('/distribution/api/tracking/<tracking_number>', methods=['GET'])  # Add alternative URL
def get_tracking(tracking_number):  # This function name is used in templates with url_for
    try:
        current_app.logger.info(f"API request for tracking number: {tracking_number}")

        shipment = Shipment.query.filter_by(tracking_number=tracking_number).first_or_404()
        current_app.logger.info(f"Found shipment with ID: {shipment.id}")

        # Get the shipment order
        shipment_order = ShipmentOrder.query.filter_by(shipment_id=shipment.id).first()
        if shipment_order:
            current_app.logger.info(f"Found shipment order with ID: {shipment_order.id}, status: {shipment_order.status}")
        else:
            current_app.logger.warning(f"No shipment order found for shipment ID: {shipment.id}")

        # Get tracking updates
        tracking_updates = []
        if shipment_order:
            tracking_updates = ShipmentTracking.query.filter_by(
                shipment_order_id=shipment_order.id
            ).order_by(ShipmentTracking.timestamp.desc()).all()
            current_app.logger.info(f"Found {len(tracking_updates)} tracking updates")

        # Prepare response data
        response_data = {
            'shipment': {
                'id': shipment.id,
                'tracking_number': shipment.tracking_number,
                'carrier_name': shipment.carrier_name,
                'shipment_date': shipment.shipment_date.isoformat() if shipment.shipment_date else None,
                'estimated_arrival': shipment.estimated_arrival.isoformat() if shipment.estimated_arrival else None,
                'customer_id': shipment.customer_id,
                'customer_name': shipment.customer.customer_name if shipment.customer else None
            },
            'shipment_order': None,
            'tracking_updates': []
        }

        if shipment_order:
            response_data['shipment_order'] = {
                'id': shipment_order.id,
                'status': shipment_order.status,
                'vehicle_id': shipment_order.vehicle_id,
                'vehicle_name': shipment_order.vehicle.name if shipment_order.vehicle else None,
                'route_id': shipment_order.route_id,
                'route_name': shipment_order.route.name if shipment_order.route else None,
                'estimated_delivery_date': shipment_order.estimated_delivery_date.isoformat() if shipment_order.estimated_delivery_date else None,
                'actual_delivery_date': shipment_order.actual_delivery_date.isoformat() if shipment_order.actual_delivery_date else None
            }

        for update in tracking_updates:
            update_data = {
                'id': update.id,
                'status': update.status,
                'timestamp': update.timestamp.isoformat(),
                'location_name': update.location_name,
                'latitude': update.latitude,
                'longitude': update.longitude,
                'notes': update.notes
            }
            response_data['tracking_updates'].append(update_data)

        return jsonify(response_data)

    except Exception as e:
        current_app.logger.error(f"Error in get_tracking API for {tracking_number}: {str(e)}")
        return jsonify({
            'error': True,
            'message': f"Error retrieving tracking information: {str(e)}"
        }), 500

@distribution_bp.route('/api/tracking/update', methods=['POST'])
@login_required
def update_tracking():  # This function name is used in templates with url_for
    data = request.json

    # Validate required fields
    if not data.get('shipment_order_id') or not data.get('status'):
        return jsonify({'success': False, 'message': 'Shipment order ID and status are required'}), 400

    try:
        # Create tracking update
        tracking = ShipmentTracking(
            shipment_order_id=data['shipment_order_id'],
            status=data['status'],
            location_name=data.get('location_name', ''),
            latitude=data.get('latitude'),
            longitude=data.get('longitude'),
            notes=data.get('notes', ''),
            created_by=current_user.id
        )

        db.session.add(tracking)

        # Update shipment order status if needed
        shipment_order = ShipmentOrder.query.get(data['shipment_order_id'])
        if shipment_order and data.get('update_shipment_status', False):
            shipment_order.status = data['status']

            # If delivered, update sales order status and set actual delivery date
            if data['status'] == 'Delivered':
                shipment_order.actual_delivery_date = datetime.now()

                if shipment_order.sales_order:
                    shipment_order.sales_order.status = 'Delivered'

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Tracking updated successfully',
            'tracking_id': tracking.id
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
