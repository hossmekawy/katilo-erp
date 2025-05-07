from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, current_app, send_file
from flask_login import login_required, current_user
from datetime import datetime, timedelta
import os
import json
import io
import csv
import tempfile
from sqlalchemy import or_, and_, func
from models import (
    db, User, SalesRepresentative, Customer, SalesOrder, SalesOrderDetail,
    SalesInvoice, SalesActivityLog, Item, Inventory
)
from routes.sales_routes import log_activity
from utils.pdf_generator import generate_pdf

# New models for representative route planning
from models import (
    RepresentativeRoute, CustomerVisit, RepresentativePerformance, VisitPhoto
)

# Create a new blueprint for sales representative routes
rep_routes_bp = Blueprint('rep_routes', __name__, url_prefix='/sales/representatives')

# List all representatives
@rep_routes_bp.route('/')
@login_required
def list_representatives():
    representatives = SalesRepresentative.query.all()
    return render_template('sales/representatives/list.html', representatives=representatives)

# Create new representative form
@rep_routes_bp.route('/new', methods=['GET'])
@login_required
def new_representative_form():
    users = db.session.query(User).filter(
        ~User.id.in_(db.session.query(SalesRepresentative.user_id))
    ).all()
    return render_template('sales/representatives/new.html', users=users)

# Create new representative
@rep_routes_bp.route('/', methods=['POST'])
@login_required
def create_representative():
    data = request.json

    # Check if user already has a rep profile
    existing_rep = SalesRepresentative.query.filter_by(user_id=data['user_id']).first()
    if existing_rep:
        return jsonify({
            'success': False,
            'message': 'This user already has a sales representative profile'
        }), 400

    # Create new sales representative
    rep = SalesRepresentative(
        user_id=data['user_id'],
        territory=data.get('territory', ''),
        commission_rate=data.get('commission_rate', 0.0),
        is_active=data.get('is_active', True)
    )

    db.session.add(rep)
    db.session.commit()

    # Log the activity
    log_activity(
        activity_type="Representative Created",
        description=f"Sales representative profile created for user {rep.user_id}"
    )

    return jsonify({
        'success': True,
        'representative_id': rep.id,
        'message': 'Sales representative created successfully'
    })

# Update representative
@rep_routes_bp.route('/<int:rep_id>', methods=['PUT'])
@login_required
def update_representative(rep_id):
    rep = SalesRepresentative.query.get_or_404(rep_id)
    data = request.json

    # Update fields
    if 'territory' in data:
        rep.territory = data['territory']
    if 'commission_rate' in data:
        rep.commission_rate = data['commission_rate']
    if 'is_active' in data:
        rep.is_active = data['is_active']

    db.session.commit()

    # Log the activity
    log_activity(
        activity_type="Representative Updated",
        description=f"Sales representative profile updated for user {rep.user_id}"
    )

    return jsonify({
        'success': True,
        'message': 'Sales representative updated successfully'
    })

# Get representative details
@rep_routes_bp.route('/<int:rep_id>')
@login_required
def get_representative(rep_id):
    try:
        rep = SalesRepresentative.query.get_or_404(rep_id)
        return jsonify({
            'id': rep.id,
            'user_id': rep.user_id,
            'name': rep.user.username if rep.user else None,
            'territory': rep.territory,
            'commission_rate': rep.commission_rate,
            'is_active': rep.is_active
        })
    except Exception as e:
        # Log the error
        print(f"Error fetching representative {rep_id}: {str(e)}")
        return jsonify({
            'error': 'Failed to fetch representative data',
            'message': str(e)
        }), 500

# Helper function to serialize RepresentativeRoute objects
def serialize_route(route):
    """
    Convert a RepresentativeRoute object to a JSON-serializable dictionary
    """
    serialized_route = {
        'id': route.id,
        'representative_id': route.representative_id,
        'route_name': route.route_name,
        'route_date': route.route_date.isoformat() if route.route_date else None,
        'status': route.status,
        'notes': route.notes,
        'visits': []
    }

    # Add representative info if available
    if hasattr(route, 'representative') and route.representative:
        serialized_route['representative'] = {
            'id': route.representative.id,
            'name': route.representative.user.username if route.representative.user else 'Unknown',
            'territory': route.representative.territory if hasattr(route.representative, 'territory') else None
        }

    # Add visits
    for visit in route.visits:
        serialized_visit = {
            'id': visit.id,
            'customer_id': visit.customer_id,
            'scheduled_time': visit.scheduled_time.isoformat() if visit.scheduled_time else None,
            'actual_visit_time': visit.actual_visit_time.isoformat() if visit.actual_visit_time else None,
            'status': visit.status,
            'visit_notes': visit.visit_notes,
            'visit_outcome': visit.visit_outcome,
            'order_id': visit.order_id,
            'location_latitude': visit.location_latitude,
            'location_longitude': visit.location_longitude
        }

        # Add customer info if available
        if hasattr(visit, 'customer') and visit.customer:
            serialized_visit['customer'] = {
                'id': visit.customer.id,
                'customer_name': visit.customer.customer_name
            }

        serialized_route['visits'].append(serialized_visit)

    return serialized_route

# Helper function to serialize SalesRepresentative objects
def serialize_representative(rep):
    """
    Convert a SalesRepresentative object to a JSON-serializable dictionary
    """
    serialized_rep = {
        'id': rep.id,
        'user_id': rep.user_id,
        'name': rep.user.username if hasattr(rep, 'user') and rep.user else 'Unknown',
        'territory': rep.territory if hasattr(rep, 'territory') else None,
        'is_active': rep.is_active if hasattr(rep, 'is_active') else True
    }

    # Add any custom attributes that were added dynamically
    if hasattr(rep, 'last_location'):
        serialized_rep['last_location'] = rep.last_location

    if hasattr(rep, 'is_tracking'):
        serialized_rep['is_tracking'] = rep.is_tracking

    return serialized_rep

# Helper function to serialize CustomerVisit objects
def serialize_visit(visit):
    """
    Convert a CustomerVisit object to a JSON-serializable dictionary
    """
    serialized_visit = {
        'id': visit.id,
        'route_id': visit.route_id,
        'customer_id': visit.customer_id,
        'scheduled_time': visit.scheduled_time.isoformat() if visit.scheduled_time else None,
        'actual_visit_time': visit.actual_visit_time.isoformat() if visit.actual_visit_time else None,
        'status': visit.status,
        'visit_notes': visit.visit_notes,
        'visit_outcome': visit.visit_outcome,
        'order_id': visit.order_id,
        'location_latitude': visit.location_latitude,
        'location_longitude': visit.location_longitude,
        'follow_up_date': visit.follow_up_date.isoformat() if hasattr(visit, 'follow_up_date') and visit.follow_up_date else None
    }

    # Add customer info if available
    if hasattr(visit, 'customer') and visit.customer:
        serialized_visit['customer'] = {
            'id': visit.customer.id,
            'customer_name': visit.customer.customer_name,
            'contact_info': visit.customer.contact_info if hasattr(visit.customer, 'contact_info') else None,
            'shipping_address': visit.customer.shipping_address if hasattr(visit.customer, 'shipping_address') else None
        }

    # Add order info if available
    if hasattr(visit, 'order') and visit.order:
        serialized_visit['order'] = {
            'id': visit.order.id,
            'order_number': visit.order.order_number if hasattr(visit.order, 'order_number') else None,
            'total_amount': float(visit.order.total_amount) if hasattr(visit.order, 'total_amount') else 0.0
        }

    return serialized_visit

# Route Planning and Management
@rep_routes_bp.route('/routes')
@login_required
def list_routes():
    routes = RepresentativeRoute.query.order_by(RepresentativeRoute.route_date.desc()).all()

    # Serialize routes to make them JSON-serializable
    serialized_routes = [serialize_route(route) for route in routes]

    return render_template('sales/representatives/routes/list.html', routes=serialized_routes)

@rep_routes_bp.route('/routes/new', methods=['GET'])
@login_required
def new_route_form():
    representatives = SalesRepresentative.query.filter_by(is_active=True).all()
    customers = Customer.query.all()

    # Serialize customers to make them JSON-serializable
    serialized_customers = []
    for customer in customers:
        serialized_customers.append({
            'id': customer.id,
            'customer_name': customer.customer_name,
            'contact_info': customer.contact_info,
            'billing_address': customer.billing_address,
            'shipping_address': customer.shipping_address,
            'latitude': None,  # Add these fields if they exist in your Customer model
            'longitude': None  # Add these fields if they exist in your Customer model
        })

    return render_template(
        'sales/representatives/routes/new.html',
        representatives=representatives,
        customers=serialized_customers,
        google_maps_api_key=current_app.config.get('GOOGLE_MAPS_API_KEY')
    )

@rep_routes_bp.route('/routes', methods=['POST'])
@login_required
def create_route_plan():
    data = request.json

    # Create new route
    route = RepresentativeRoute(
        representative_id=data['representative_id'],
        route_name=data['route_name'],
        route_date=datetime.strptime(data['route_date'], '%Y-%m-%d').date(),
        notes=data.get('notes', '')
    )

    db.session.add(route)
    db.session.flush()  # Get the route ID without committing

    # Create customer visits
    for visit in data.get('visits', []):
        customer_visit = CustomerVisit(
            route_id=route.id,
            customer_id=visit['customer_id'],
            scheduled_time=datetime.strptime(visit['scheduled_time'], '%Y-%m-%dT%H:%M') if visit.get('scheduled_time') else None,
            visit_notes=visit.get('notes', ''),
            status='Pending',
            location_latitude=visit.get('location', {}).get('lat') if visit.get('location') else None,
            location_longitude=visit.get('location', {}).get('lng') if visit.get('location') else None
        )
        db.session.add(customer_visit)

    db.session.commit()

    # Log the activity
    log_activity(
        activity_type="Route Created",
        description=f"Route plan created for representative {route.representative_id}"
    )

    return jsonify({
        'success': True,
        'route_id': route.id,
        'message': 'Route plan created successfully'
    })

@rep_routes_bp.route('/routes/<int:route_id>')
@login_required
def view_route(route_id):
    route = RepresentativeRoute.query.get_or_404(route_id)
    serialized_route = serialize_route(route)
    return render_template(
        'sales/representatives/routes/view.html',
        route=serialized_route,
        google_maps_api_key=current_app.config.get('GOOGLE_MAPS_API_KEY')
    )

@rep_routes_bp.route('/routes/<int:route_id>/edit', methods=['GET'])
@login_required
def edit_route_form(route_id):
    route = RepresentativeRoute.query.get_or_404(route_id)
    representatives = SalesRepresentative.query.filter_by(is_active=True).all()
    customers = Customer.query.all()

    # Serialize route to make it JSON-serializable
    serialized_route = serialize_route(route)

    # Serialize customers to make them JSON-serializable
    serialized_customers = []
    for customer in customers:
        serialized_customers.append({
            'id': customer.id,
            'customer_name': customer.customer_name,
            'contact_info': customer.contact_info,
            'billing_address': customer.billing_address,
            'shipping_address': customer.shipping_address,
            'latitude': None,  # Add these fields if they exist in your Customer model
            'longitude': None  # Add these fields if they exist in your Customer model
        })

    return render_template(
        'sales/representatives/routes/edit.html',
        route=serialized_route,
        representatives=representatives,
        customers=serialized_customers,
        google_maps_api_key=current_app.config.get('GOOGLE_MAPS_API_KEY')
    )

@rep_routes_bp.route('/routes/<int:route_id>', methods=['PUT'])
@login_required
def update_route(route_id):
    route = RepresentativeRoute.query.get_or_404(route_id)
    data = request.json

    # Update route fields
    if 'route_name' in data:
        route.route_name = data['route_name']
    if 'route_date' in data:
        route.route_date = datetime.strptime(data['route_date'], '%Y-%m-%d').date()
    if 'status' in data:
        route.status = data['status']
    if 'notes' in data:
        route.notes = data['notes']

    # Update visits if provided
    if 'visits' in data:
        # Remove existing visits
        for visit in route.visits:
            db.session.delete(visit)

        # Add new visits
        for visit in data['visits']:
            customer_visit = CustomerVisit(
                route_id=route.id,
                customer_id=visit['customer_id'],
                scheduled_time=datetime.strptime(visit['scheduled_time'], '%Y-%m-%dT%H:%M') if visit.get('scheduled_time') else None,
                visit_notes=visit.get('notes', ''),
                status='Pending',
                location_latitude=visit.get('location', {}).get('lat') if visit.get('location') else None,
                location_longitude=visit.get('location', {}).get('lng') if visit.get('location') else None
            )
            db.session.add(customer_visit)

    db.session.commit()

    # Log the activity
    log_activity(
        activity_type="Route Updated",
        description=f"Route plan updated for representative {route.representative_id}"
    )

    return jsonify({
        'success': True,
        'message': 'Route plan updated successfully'
    })

@rep_routes_bp.route('/routes/<int:route_id>', methods=['DELETE'])
@login_required
def delete_route(route_id):
    route = RepresentativeRoute.query.get_or_404(route_id)

    # Log before deletion
    log_activity(
        activity_type="Route Deleted",
        description=f"Route plan {route_id} for representative {route.representative_id} was deleted"
    )

    # Delete visits first
    for visit in route.visits:
        db.session.delete(visit)

    # Delete the route
    db.session.delete(route)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Route plan deleted successfully'
    })

@rep_routes_bp.route('/routes/<int:route_id>/assign-orders', methods=['GET', 'POST'])
@login_required
def assign_orders_to_route(route_id):
    route = RepresentativeRoute.query.get_or_404(route_id)

    if request.method == 'GET':
        # Get all visits for this route
        visits = route.visits

        # Get all orders that could be assigned to this route
        # For example, orders from the same customers in the route
        customer_ids = [visit.customer_id for visit in visits]
        orders = SalesOrder.query.filter(
            SalesOrder.customer_id.in_(customer_ids),
            SalesOrder.status.in_(['Draft', 'Pending'])
        ).all()

        # Serialize the data
        serialized_route = serialize_route(route)
        serialized_visits = [serialize_visit(visit) for visit in visits]

        serialized_orders = []
        for order in orders:
            serialized_orders.append({
                'id': order.id,
                'order_number': order.order_number if hasattr(order, 'order_number') else f"Order #{order.id}",
                'customer_id': order.customer_id,
                'customer_name': order.customer.customer_name if hasattr(order, 'customer') and order.customer else 'Unknown',
                'order_date': order.order_date.isoformat() if hasattr(order, 'order_date') and order.order_date else None,
                'total_amount': float(order.total_amount) if hasattr(order, 'total_amount') else 0.0,
                'status': order.status
            })

        return render_template(
            'sales/representatives/routes/assign_orders.html',
            route=serialized_route,
            visits=serialized_visits,
            orders=serialized_orders
        )

    elif request.method == 'POST':
        data = request.json

        for assignment in data.get('assignments', []):
            visit_id = assignment.get('visit_id')
            order_id = assignment.get('order_id')

            if visit_id and order_id:
                visit = CustomerVisit.query.get_or_404(visit_id)
                visit.order_id = order_id

        db.session.commit()

        # Log the activity
        log_activity(
            activity_type="Orders Assigned",
            description=f"Orders assigned to route {route_id}"
        )

        return jsonify({
            'success': True,
            'message': 'Orders assigned to route successfully'
        })

# Representative Tracking
@rep_routes_bp.route('/tracking')
@login_required
def track_representatives():
    representatives = SalesRepresentative.query.filter_by(is_active=True).all()

    # Get today's routes
    today = datetime.now().date()
    active_routes = RepresentativeRoute.query.filter(
        RepresentativeRoute.route_date == today,
        RepresentativeRoute.status.in_(['Planned', 'In Progress'])
    ).all()

    # Add last location data to representatives and serialize them
    serialized_reps = []
    for rep in representatives:
        # In a real implementation, you would fetch this from a location tracking table
        # For now, we'll just add dummy data for demonstration
        rep.last_location = {
            'latitude': 30.0444 + (rep.id * 0.01),  # Dummy coordinates near Cairo
            'longitude': 31.2357 + (rep.id * 0.01),
            'timestamp': datetime.now().isoformat()
        }
        rep.is_tracking = rep.id % 2 == 0  # Dummy tracking status

        # Serialize the representative
        serialized_reps.append(serialize_representative(rep))

    # Serialize routes
    serialized_routes = [serialize_route(route) for route in active_routes]

    return render_template(
        'sales/representatives/tracking.html',
        representatives=serialized_reps,
        active_routes=serialized_routes,
        google_maps_api_key=current_app.config.get('GOOGLE_MAPS_API_KEY')
    )

@rep_routes_bp.route('/tracking/<int:rep_id>')
@login_required
def track_representative(rep_id):
    representative = SalesRepresentative.query.get_or_404(rep_id)

    # Get today's route for this rep
    today = datetime.now().date()
    route = RepresentativeRoute.query.filter(
        RepresentativeRoute.representative_id == rep_id,
        RepresentativeRoute.route_date == today,
        RepresentativeRoute.status.in_(['Planned', 'In Progress'])
    ).first()

    # Add last location data
    representative.last_location = {
        'latitude': 30.0444 + (representative.id * 0.01),  # Dummy coordinates near Cairo
        'longitude': 31.2357 + (representative.id * 0.01),
        'timestamp': datetime.now().isoformat()
    }
    representative.is_tracking = True  # Assume the rep we're tracking is active

    # Serialize the representative
    serialized_rep = serialize_representative(representative)

    # Serialize the route if it exists
    serialized_route = serialize_route(route) if route else None

    return render_template(
        'sales/representatives/tracking.html',
        representatives=[serialized_rep],
        active_routes=[serialized_route] if serialized_route else [],
        selected_rep_id=rep_id,
        google_maps_api_key=current_app.config.get('GOOGLE_MAPS_API_KEY')
    )

@rep_routes_bp.route('/tracking/data')
@login_required
def get_tracking_data():
    representatives = SalesRepresentative.query.filter_by(is_active=True).all()

    # Get today's routes
    today = datetime.now().date()
    active_routes = RepresentativeRoute.query.filter(
        RepresentativeRoute.route_date == today,
        RepresentativeRoute.status.in_(['Planned', 'In Progress'])
    ).all()

    # Add last location data to representatives
    for rep in representatives:
        # In a real implementation, you would fetch this from a location tracking table
        rep.last_location = {
            'latitude': 30.0444 + (rep.id * 0.01),  # Dummy coordinates near Cairo
            'longitude': 31.2357 + (rep.id * 0.01),
            'timestamp': datetime.now().isoformat()
        }
        rep.is_tracking = rep.id % 2 == 0  # Dummy tracking status

    # Serialize representatives using our serialization function
    rep_data = [serialize_representative(rep) for rep in representatives]

    # Format route data using our serialization function
    route_data = [serialize_route(route) for route in active_routes]

    return jsonify({
        'representatives': rep_data,
        'active_routes': route_data
    })

@rep_routes_bp.route('/visits/<int:visit_id>/record', methods=['GET'])
@login_required
def record_visit_form(visit_id):
    visit = CustomerVisit.query.get_or_404(visit_id)
    serialized_visit = serialize_visit(visit)
    return render_template(
        'sales/representatives/visits/record.html',
        visit=serialized_visit,
        google_maps_api_key=current_app.config.get('GOOGLE_MAPS_API_KEY')
    )

@rep_routes_bp.route('/visits/<int:visit_id>/record', methods=['POST'])
@login_required
def record_visit_results(visit_id):
    visit = CustomerVisit.query.get_or_404(visit_id)

    # Handle form data with file uploads
    if request.content_type and 'multipart/form-data' in request.content_type:
        # Get form data
        actual_visit_time = request.form.get('actual_visit_time')
        status = request.form.get('status', 'Completed')
        visit_outcome = request.form.get('visit_outcome')
        visit_notes = request.form.get('visit_notes', '')
        follow_up_date = request.form.get('follow_up_date')
        location_latitude = request.form.get('location_latitude')
        location_longitude = request.form.get('location_longitude')

        # Update visit data
        if actual_visit_time:
            visit.actual_visit_time = datetime.strptime(actual_visit_time, '%Y-%m-%dT%H:%M')
        else:
            visit.actual_visit_time = datetime.now()

        # If status is Completed, change it to the Arabic equivalent "تم بنجاح"
        if status == 'Completed':
            visit.status = 'تم بنجاح'
        else:
            visit.status = status

        visit.visit_outcome = visit_outcome
        visit.visit_notes = visit_notes

        if follow_up_date and visit_outcome == 'Follow-up Required':
            visit.follow_up_date = datetime.strptime(follow_up_date, '%Y-%m-%d').date()

        # Record location if provided
        if location_latitude and location_longitude:
            visit.location_latitude = float(location_latitude)
            visit.location_longitude = float(location_longitude)

        # Process photo uploads
        for i in range(10):  # Allow up to 10 photos
            photo_key = f'photo_{i}'
            if photo_key in request.files:
                photo_file = request.files[photo_key]
                if photo_file and photo_file.filename:
                    # Create a unique filename
                    filename = f"visit_{visit_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{i}.jpg"
                    file_path = os.path.join('static', 'uploads', 'visits', filename)

                    # Ensure directory exists
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)

                    # Save the file
                    photo_file.save(file_path)

                    # Create photo record
                    photo = VisitPhoto(
                        visit_id=visit.id,
                        photo_path=file_path,
                        upload_time=datetime.now()
                    )
                    db.session.add(photo)
    else:
        # Handle JSON data
        data = request.json

        visit.actual_visit_time = datetime.now()

        # If status is Completed, change it to the Arabic equivalent "تم بنجاح"
        if data.get('status') == 'Completed':
            visit.status = 'تم بنجاح'
        else:
            visit.status = data.get('status', 'Completed')

        visit.visit_outcome = data.get('outcome')
        visit.visit_notes = data.get('notes', '')

        # Record location if provided
        if data.get('latitude') and data.get('longitude'):
            visit.location_latitude = data.get('latitude')
            visit.location_longitude = data.get('longitude')

    # If the visit has an associated order and the visit is completed, update the order status to "Shipped" (تم الشحن)
    if visit.order_id and (visit.status == 'تم بنجاح' or visit.status == 'Completed'):
        order = SalesOrder.query.get(visit.order_id)
        if order:
            order.status = 'Shipped'  # Using the enum value from sales_order_status_enum

    db.session.commit()

    # Log the activity
    log_activity(
        activity_type="Visit Recorded",
        description=f"Visit {visit_id} to customer {visit.customer_id} recorded with outcome: {visit.visit_outcome}"
    )

    return jsonify({
        'success': True,
        'message': 'Visit results recorded successfully'
    })

# Performance Evaluation
@rep_routes_bp.route('/<int:rep_id>/performance')
@login_required
def view_representative_performance(rep_id):
    rep = SalesRepresentative.query.get_or_404(rep_id)

    # Get date range from query parameters or default to last 30 days
    end_date = datetime.now().date()
    start_date = request.args.get('start_date')
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    else:
        start_date = end_date - timedelta(days=30)

    # Serialize representative to make it JSON-compatible
    representative = {
        'id': rep.id,
        'user_id': rep.user_id,
        'user': {
            'id': rep.user.id if rep.user else None,
            'username': rep.user.username if rep.user else 'Unknown'
        } if rep.user else None,
        'territory': rep.territory,
        'is_active': rep.is_active
    }

    return render_template(
        'sales/representatives/performance.html',
        representative=representative,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat()
    )

@rep_routes_bp.route('/<int:rep_id>/performance-data')
@login_required
def get_representative_performance_data(rep_id):
    representative = SalesRepresentative.query.get_or_404(rep_id)

    # Get date range from query parameters or default to last 30 days
    end_date = datetime.now().date()
    start_date = request.args.get('start_date')
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    else:
        start_date = end_date - timedelta(days=30)

    # Get or create performance record
    performance = RepresentativePerformance.query.filter(
        RepresentativePerformance.representative_id == rep_id,
        RepresentativePerformance.period_start == start_date,
        RepresentativePerformance.period_end == end_date
    ).first()

    if not performance:
        performance = evaluate_rep_performance(rep_id, start_date, end_date)

    # Get all performance records for this rep
    performance_records = RepresentativePerformance.query.filter(
        RepresentativePerformance.representative_id == rep_id
    ).order_by(RepresentativePerformance.period_end.desc()).limit(10).all()

    # Get monthly data for charts
    monthly_data = []

    # Calculate 6 months of data
    for i in range(5, -1, -1):
        month_end = datetime.now().date().replace(day=1) - timedelta(days=1)
        month_end = month_end.replace(day=1) - timedelta(days=1) * i
        month_start = month_end.replace(day=1)

        # Get or calculate performance for this month
        month_performance = RepresentativePerformance.query.filter(
            RepresentativePerformance.representative_id == rep_id,
            RepresentativePerformance.period_start == month_start,
            RepresentativePerformance.period_end == month_end
        ).first()

        if not month_performance:
            month_performance = evaluate_rep_performance(rep_id, month_start, month_end)

        # Format month name
        month_name = month_start.strftime('%B %Y')

        monthly_data.append({
            'month': month_name,
            'sales': float(month_performance.total_sales),
            'total_visits': month_performance.total_visits,
            'completed_visits': month_performance.completed_visits
        })

    # Get visit outcomes data
    visit_outcomes = {
        'sale': 0,
        'no_sale': 0,
        'follow_up': 0
    }

    # Get all visits in the date range
    routes = RepresentativeRoute.query.filter(
        RepresentativeRoute.representative_id == rep_id,
        RepresentativeRoute.route_date.between(start_date, end_date)
    ).all()

    route_ids = [route.id for route in routes]
    visits = CustomerVisit.query.filter(
        CustomerVisit.route_id.in_(route_ids),
        CustomerVisit.status == 'Completed'
    ).all() if route_ids else []

    for visit in visits:
        if visit.visit_outcome == 'Sale':
            visit_outcomes['sale'] += 1
        elif visit.visit_outcome == 'No Sale':
            visit_outcomes['no_sale'] += 1
        elif visit.visit_outcome == 'Follow-up Required':
            visit_outcomes['follow_up'] += 1

    # Format performance data
    performance_data = {
        'id': performance.id,
        'representative_id': performance.representative_id,
        'period_start': performance.period_start.isoformat(),
        'period_end': performance.period_end.isoformat(),
        'total_visits': performance.total_visits,
        'completed_visits': performance.completed_visits,
        'total_sales': float(performance.total_sales),
        'total_orders': performance.total_orders,
        'conversion_rate': performance.conversion_rate,
        'average_order_value': float(performance.average_order_value),
        'evaluation_score': performance.evaluation_score,
        'evaluation_notes': performance.evaluation_notes
    }

    return jsonify({
        'current_performance': performance_data,
        'performance_records': [
            {
                'id': record.id,
                'period_start': record.period_start.isoformat(),
                'period_end': record.period_end.isoformat(),
                'total_visits': record.total_visits,
                'completed_visits': record.completed_visits,
                'total_sales': float(record.total_sales),
                'total_orders': record.total_orders,
                'conversion_rate': record.conversion_rate,
                'average_order_value': float(record.average_order_value),
                'evaluation_score': record.evaluation_score
            } for record in performance_records
        ],
        'monthly_data': monthly_data,
        'visit_outcomes': visit_outcomes
    })

@rep_routes_bp.route('/<int:rep_id>/performance-report')
@login_required
def generate_performance_report(rep_id):
    representative = SalesRepresentative.query.get_or_404(rep_id)

    # Get date range from query parameters or default to last 30 days
    end_date = datetime.now().date()
    start_date = request.args.get('start_date')
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    else:
        start_date = end_date - timedelta(days=30)

    # Get or create performance record
    performance = RepresentativePerformance.query.filter(
        RepresentativePerformance.representative_id == rep_id,
        RepresentativePerformance.period_start == start_date,
        RepresentativePerformance.period_end == end_date
    ).first()

    if not performance:
        performance = evaluate_rep_performance(rep_id, start_date, end_date)

    # Get routes in the date range
    routes = RepresentativeRoute.query.filter(
        RepresentativeRoute.representative_id == rep_id,
        RepresentativeRoute.route_date.between(start_date, end_date)
    ).all()

    # Get orders associated with this representative in the date range
    orders = SalesOrder.query.filter(
        SalesOrder.sales_rep_id == rep_id,
        SalesOrder.order_date.between(start_date, end_date)
    ).all()

    # Calculate metrics for the template
    total_routes = len(routes)
    total_visits = performance.total_visits
    completed_visits = performance.completed_visits
    completion_rate = round((completed_visits / total_visits * 100) if total_visits > 0 else 0, 1)
    total_orders = performance.total_orders
    conversion_rate = round(performance.conversion_rate, 1)
    average_order_value = round(performance.average_order_value, 2)
    total_sales = round(performance.total_sales, 2)

    metrics = {
        'total_routes': total_routes,
        'total_visits': total_visits,
        'completed_visits': completed_visits,
        'completion_rate': completion_rate,
        'total_orders': total_orders,
        'conversion_rate': conversion_rate,
        'average_order_value': average_order_value,
        'total_sales': total_sales
    }

    # Generate PDF report
    html = render_template(
        'sales/representatives/reports/performance_report_pdf.html',
        representative=representative,
        performance=performance,
        routes=routes,
        orders=orders,
        metrics=metrics,
        start_date=start_date,
        end_date=end_date,
        current_year=datetime.now().year
    )

    # Generate PDF using wkhtmltopdf
    pdf_file = generate_pdf(html)

    # Create a response with the PDF
    filename = f"performance_report_{representative.user.username}_{start_date.isoformat()}_{end_date.isoformat()}.pdf"
    return send_file(
        io.BytesIO(pdf_file),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )

@rep_routes_bp.route('/performance/evaluate', methods=['POST'])
@login_required
def evaluate_representative_performance():
    data = request.json
    rep_id = data.get('representative_id')

    start_date = datetime.strptime(data.get('start_date'), '%Y-%m-%d').date()
    end_date = datetime.strptime(data.get('end_date'), '%Y-%m-%d').date()

    performance = evaluate_rep_performance(rep_id, start_date, end_date)

    return jsonify({
        'success': True,
        'performance_id': performance.id,
        'message': 'Performance evaluation completed successfully'
    })

# Routes Report
@rep_routes_bp.route('/routes/report')
@login_required
def routes_report():
    # Get date range from query parameters or default to last 30 days
    end_date = datetime.now().date()
    start_date = request.args.get('start_date')
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    else:
        start_date = end_date - timedelta(days=30)

    # Get routes in the date range
    routes_query = RepresentativeRoute.query.filter(
        RepresentativeRoute.route_date.between(start_date, end_date)
    ).order_by(RepresentativeRoute.route_date.desc()).all()

    # Serialize routes to make them JSON-compatible
    routes = []
    for route in routes_query:
        # Serialize visits
        visits = []
        for visit in route.visits:
            visits.append({
                'id': visit.id,
                'customer_id': visit.customer_id,
                'customer_name': visit.customer.customer_name if visit.customer else 'Unknown',
                'scheduled_time': visit.scheduled_time.isoformat() if visit.scheduled_time else None,
                'actual_visit_time': visit.actual_visit_time.isoformat() if visit.actual_visit_time else None,
                'status': visit.status,
                'visit_outcome': visit.visit_outcome,
                'order_id': visit.order_id
            })

        # Serialize route
        routes.append({
            'id': route.id,
            'representative_id': route.representative_id,
            'representative': {
                'id': route.representative.id,
                'user': {
                    'id': route.representative.user.id if route.representative.user else None,
                    'username': route.representative.user.username if route.representative.user else 'Unknown'
                }
            } if route.representative else None,
            'route_name': route.route_name,
            'route_date': route.route_date.isoformat(),
            'status': route.status,
            'notes': route.notes,
            'visits': visits
        })

    # Serialize representatives
    reps = []
    for rep in SalesRepresentative.query.all():
        reps.append({
            'id': rep.id,
            'user_id': rep.user_id,
            'user': {
                'id': rep.user.id if rep.user else None,
                'username': rep.user.username if rep.user else 'Unknown'
            } if rep.user else None,
            'territory': rep.territory,
            'is_active': rep.is_active
        })

    return render_template(
        'sales/representatives/reports/routes_report.html',
        routes=routes,
        representatives=reps,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat()
    )

@rep_routes_bp.route('/routes/export')
@login_required
def export_routes_report():
    # Get parameters
    export_format = request.args.get('format', 'pdf')
    rep_id = request.args.get('representative', 'all')
    status = request.args.get('status', 'all')

    # Get date range
    end_date = datetime.now().date()
    start_date = request.args.get('start_date')
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    else:
        start_date = end_date - timedelta(days=30)

    # Build query
    query = RepresentativeRoute.query.filter(
        RepresentativeRoute.route_date.between(start_date, end_date)
    )

    if rep_id != 'all':
        query = query.filter_by(representative_id=int(rep_id))

    if status != 'all':
        query = query.filter_by(status=status)

    # Get routes
    routes = query.order_by(RepresentativeRoute.route_date.desc()).all()

    # Generate filename
    filename_base = f"routes_report_{start_date.isoformat()}_{end_date.isoformat()}"

    if export_format == 'pdf':
        # Generate PDF report
        html = render_template(
            'sales/representatives/reports/routes_report_pdf.html',
            routes=routes,
            start_date=start_date,
            end_date=end_date,
            current_year=datetime.now().year
        )

        # Generate PDF using wkhtmltopdf
        pdf_file = generate_pdf(html)

        # Create a response with the PDF
        filename = f"{filename_base}.pdf"
        return send_file(
            io.BytesIO(pdf_file),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )

    elif export_format == 'excel':
        # Create CSV data
        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow([
            'Route ID', 'Representative', 'Route Name', 'Date', 'Status',
            'Total Visits', 'Completed Visits', 'Orders', 'Notes'
        ])

        # Write data
        for route in routes:
            writer.writerow([
                route.id,
                route.representative.user.username if route.representative and route.representative.user else 'Unknown',
                route.route_name,
                route.route_date.isoformat(),
                route.status,
                len(route.visits),
                sum(1 for visit in route.visits if visit.status == 'Completed'),
                sum(1 for visit in route.visits if visit.order_id),
                route.notes
            ])

        # Create response
        output.seek(0)
        filename = f"{filename_base}.csv"
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )

    else:
        return jsonify({
            'success': False,
            'message': 'Invalid export format'
        }), 400

@rep_routes_bp.route('/routes/<int:route_id>/report')
@login_required
def single_route_report(route_id):
    route = RepresentativeRoute.query.get_or_404(route_id)

    # Generate PDF report
    html = render_template(
        'sales/representatives/reports/single_route_report_pdf.html',
        route=route,
        current_year=datetime.now().year
    )

    # Generate PDF using wkhtmltopdf
    pdf_file = generate_pdf(html)

    # Create a response with the PDF
    filename = f"route_report_{route.id}_{route.route_date.isoformat()}.pdf"
    return send_file(
        io.BytesIO(pdf_file),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )

@rep_routes_bp.route('/routes/reports/generate', methods=['POST'])
@login_required
def generate_routes_reports():
    data = request.json
    report_type = data.get('report_type')
    start_date = datetime.strptime(data.get('start_date'), '%Y-%m-%d').date()
    end_date = datetime.strptime(data.get('end_date'), '%Y-%m-%d').date()

    # Generate report based on type
    if report_type == 'performance':
        # Generate performance report
        representatives = SalesRepresentative.query.filter_by(is_active=True).all()
        performance_data = []

        for rep in representatives:
            performance = evaluate_rep_performance(rep.id, start_date, end_date)
            performance_data.append({
                'representative_id': rep.id,
                'representative_name': rep.user.username if rep.user else 'Unknown',
                'total_visits': performance.total_visits,
                'completed_visits': performance.completed_visits,
                'total_sales': performance.total_sales,
                'total_orders': performance.total_orders,
                'conversion_rate': performance.conversion_rate,
                'average_order_value': performance.average_order_value,
                'evaluation_score': performance.evaluation_score
            })

        return jsonify({
            'success': True,
            'report_type': report_type,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'data': performance_data
        })

    elif report_type == 'visits':
        # Generate visits report
        visits = CustomerVisit.query.join(RepresentativeRoute).filter(
            RepresentativeRoute.route_date.between(start_date, end_date)
        ).all()

        visits_data = [{
            'visit_id': visit.id,
            'route_id': visit.route_id,
            'customer_id': visit.customer_id,
            'customer_name': visit.customer.customer_name,
            'representative_id': visit.route.representative_id,
            'representative_name': visit.route.representative.user.username if visit.route.representative.user else 'Unknown',
            'scheduled_time': visit.scheduled_time.isoformat() if visit.scheduled_time else None,
            'actual_visit_time': visit.actual_visit_time.isoformat() if visit.actual_visit_time else None,
            'status': visit.status,
            'outcome': visit.visit_outcome,
            'order_id': visit.order_id
        } for visit in visits]

        return jsonify({
            'success': True,
            'report_type': report_type,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'data': visits_data
        })

    elif report_type == 'routes':
        # Generate routes report
        routes = RepresentativeRoute.query.filter(
            RepresentativeRoute.route_date.between(start_date, end_date)
        ).all()

        routes_data = [{
            'route_id': route.id,
            'representative_id': route.representative_id,
            'representative_name': route.representative.user.username if route.representative.user else 'Unknown',
            'route_name': route.route_name,
            'route_date': route.route_date.isoformat(),
            'status': route.status,
            'visits_count': len(route.visits),
            'completed_visits': sum(1 for visit in route.visits if visit.status == 'Completed'),
            'successful_visits': sum(1 for visit in route.visits if visit.visit_outcome == 'Sale'),
            'notes': route.notes
        } for route in routes]

        return jsonify({
            'success': True,
            'report_type': report_type,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'data': routes_data
        })

    else:
        return jsonify({
            'success': False,
            'message': 'Invalid report type'
        }), 400

# Helper function to evaluate representative performance
def evaluate_rep_performance(rep_id, start_date, end_date):
    representative = SalesRepresentative.query.get_or_404(rep_id)

    # Check if evaluation already exists
    existing_performance = RepresentativePerformance.query.filter(
        RepresentativePerformance.representative_id == rep_id,
        RepresentativePerformance.period_start == start_date,
        RepresentativePerformance.period_end == end_date
    ).first()

    if existing_performance:
        return existing_performance

    # Get routes in the date range
    routes = RepresentativeRoute.query.filter(
        RepresentativeRoute.representative_id == rep_id,
        RepresentativeRoute.route_date.between(start_date, end_date)
    ).all()

    # Calculate metrics
    total_visits = 0
    completed_visits = 0
    total_sales = 0.0
    total_orders = 0

    # Get all visits from these routes
    route_ids = [route.id for route in routes]
    visits = CustomerVisit.query.filter(CustomerVisit.route_id.in_(route_ids)).all() if route_ids else []

    total_visits = len(visits)
    completed_visits = sum(1 for visit in visits if visit.status == 'Completed')

    # Get orders associated with these visits
    order_ids = [visit.order_id for visit in visits if visit.order_id is not None]
    orders = SalesOrder.query.filter(SalesOrder.id.in_(order_ids)).all() if order_ids else []

    total_orders = len(orders)
    total_sales = sum(order.total_amount for order in orders)

    # Calculate derived metrics
    conversion_rate = (completed_visits / total_visits * 100) if total_visits > 0 else 0
    average_order_value = (total_sales / total_orders) if total_orders > 0 else 0

    # Calculate evaluation score (example formula)
    # 40% based on conversion rate, 30% on total sales, 30% on visit completion rate
    visit_completion_rate = (completed_visits / total_visits * 100) if total_visits > 0 else 0

    # Normalize total sales (example: 10,000 EGP = 100%)
    sales_score = min(100, (total_sales / 10000) * 100)

    evaluation_score = (
        0.4 * conversion_rate +
        0.3 * sales_score +
        0.3 * visit_completion_rate
    )

    # Create or update performance record
    performance = RepresentativePerformance(
        representative_id=rep_id,
        period_start=start_date,
        period_end=end_date,
        total_visits=total_visits,
        completed_visits=completed_visits,
        total_sales=total_sales,
        total_orders=total_orders,
        conversion_rate=conversion_rate,
        average_order_value=average_order_value,
        evaluation_score=evaluation_score,
        evaluation_notes=f"Automatic evaluation for period {start_date} to {end_date}"
    )

    db.session.add(performance)
    db.session.commit()

    return performance

# API endpoints for AJAX requests
# Add this new route to get representative details via API
@rep_routes_bp.route('/api/representatives/<int:rep_id>')
@login_required
def api_get_representative(rep_id):
    try:
        rep = SalesRepresentative.query.get_or_404(rep_id)
        return jsonify({
            'id': rep.id,
            'user_id': rep.user_id,
            'name': rep.user.username if rep.user else None,
            'territory': rep.territory,
            'commission_rate': rep.commission_rate,
            'is_active': rep.is_active
        })
    except Exception as e:
        # Log the error
        print(f"Error fetching representative {rep_id}: {str(e)}")
        return jsonify({
            'error': 'Failed to fetch representative data',
            'message': str(e)
        }), 500

@rep_routes_bp.route('/api/routes')
@login_required
def api_get_routes():
    rep_id = request.args.get('representative_id', type=int)
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')

    query = RepresentativeRoute.query

    if rep_id:
        query = query.filter_by(representative_id=rep_id)

    if date_from:
        date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
        query = query.filter(RepresentativeRoute.route_date >= date_from)

    if date_to:
        date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
        query = query.filter(RepresentativeRoute.route_date <= date_to)

    routes = query.order_by(RepresentativeRoute.route_date.desc()).all()

    return jsonify([{
        'id': route.id,
        'representative_id': route.representative_id,
        'representative_name': route.representative.user.username if route.representative.user else 'Unknown',
        'route_name': route.route_name,
        'route_date': route.route_date.isoformat(),
        'status': route.status,
        'visits_count': len(route.visits),
        'completed_visits': sum(1 for visit in route.visits if visit.status == 'Completed')
    } for route in routes])

@rep_routes_bp.route('/api/visits')
@login_required
def api_get_visits():
    route_id = request.args.get('route_id', type=int)

    if not route_id:
        return jsonify([])

    visits = CustomerVisit.query.filter_by(route_id=route_id).all()

    return jsonify([{
        'id': visit.id,
        'customer_id': visit.customer_id,
        'customer_name': visit.customer.customer_name if visit.customer else 'Unknown',
        'scheduled_time': visit.scheduled_time.isoformat() if visit.scheduled_time else None,
        'actual_visit_time': visit.actual_visit_time.isoformat() if visit.actual_visit_time else None,
        'status': visit.status,
        'outcome': visit.visit_outcome,
        'order_id': visit.order_id,
        'location': {
            'latitude': visit.location_latitude,
            'longitude': visit.location_longitude
        } if visit.location_latitude and visit.location_longitude else None
    } for visit in visits])

@rep_routes_bp.route('/api/current-location/<int:rep_id>', methods=['POST'])
@login_required
def update_rep_location(rep_id):
    data = request.json

    # In a real implementation, you would store this in a location tracking table
    # For simplicity, we'll just return success

    return jsonify({
        'success': True,
        'message': 'Location updated successfully'
    })

# Mobile app API endpoints
@rep_routes_bp.route('/api/mobile/login', methods=['POST'])
def mobile_login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    # Authenticate user
    user = User.query.filter_by(username=username).first()

    if not user or not user.check_password(password):
        return jsonify({
            'success': False,
            'message': 'Invalid username or password'
        }), 401

    # Check if user is a sales representative
    rep = SalesRepresentative.query.filter_by(user_id=user.id, is_active=True).first()

    if not rep:
        return jsonify({
            'success': False,
            'message': 'User is not an active sales representative'
        }), 403

    # Generate token (in a real app, use JWT or similar)
    token = 'sample_token_' + str(user.id)

    return jsonify({
        'success': True,
        'token': token,
        'user': {
            'id': user.id,
            'username': user.username,
            'rep_id': rep.id,
            'territory': rep.territory
        }
    })

@rep_routes_bp.route('/api/mobile/today-route', methods=['GET'])
def mobile_get_today_route():
    # In a real app, authenticate with token
    rep_id = request.args.get('rep_id', type=int)

    if not rep_id:
        return jsonify({
            'success': False,
            'message': 'Representative ID is required'
        }), 400

    # Get today's route
    today = datetime.now().date()
    route = RepresentativeRoute.query.filter(
        RepresentativeRoute.representative_id == rep_id,
        RepresentativeRoute.route_date == today
    ).first()

    if not route:
        return jsonify({
            'success': False,
            'message': 'No route planned for today'
        }), 404

    # Get visits
    visits = [{
        'id': visit.id,
        'customer_id': visit.customer_id,
        'customer_name': visit.customer.customer_name if visit.customer else 'Unknown',
        'contact_info': visit.customer.contact_info if visit.customer else None,
        'address': visit.customer.billing_address if visit.customer else None,
        'scheduled_time': visit.scheduled_time.isoformat() if visit.scheduled_time else None,
        'status': visit.status,
        'notes': visit.visit_notes,
        'location': {
            'latitude': visit.location_latitude,
            'longitude': visit.location_longitude
        } if visit.location_latitude and visit.location_longitude else None
    } for visit in route.visits]

    return jsonify({
        'success': True,
        'route': {
            'id': route.id,
            'name': route.route_name,
            'date': route.route_date.isoformat(),
            'status': route.status,
            'notes': route.notes,
            'visits': visits
        }
    })

@rep_routes_bp.route('/api/mobile/record-visit', methods=['POST'])
def mobile_record_visit():
    # In a real app, authenticate with token
    data = request.json
    visit_id = data.get('visit_id')

    if not visit_id:
        return jsonify({
            'success': False,
            'message': 'Visit ID is required'
        }), 400

    visit = CustomerVisit.query.get_or_404(visit_id)

    # Update visit data
    visit.actual_visit_time = datetime.now()
    visit.status = data.get('status', 'Completed')
    visit.visit_outcome = data.get('outcome')
    visit.visit_notes = data.get('notes', '')

    # Record location
    if data.get('latitude') and data.get('longitude'):
        visit.location_latitude = data.get('latitude')
        visit.location_longitude = data.get('longitude')

    # If an order was created
    if data.get('order'):
        order_data = data.get('order')

        # Create a new sales order
        order = SalesOrder(
            customer_id=visit.customer_id,
            representative_id=visit.route.representative_id,
            order_date=datetime.now(),
            status='Pending',
            total_amount=order_data.get('total_amount', 0)
        )

        db.session.add(order)
        db.session.flush()  # Get the order ID without committing

        # Create order details
        for item in order_data.get('items', []):
            detail = SalesOrderDetail(
                sales_order_id=order.id,
                item_id=item.get('item_id'),
                quantity_ordered=item.get('quantity', 0),
                unit_price=item.get('unit_price', 0)
            )
            db.session.add(detail)

        # Link the order to the visit
        visit.order_id = order.id

    db.session.commit()

    # Log the activity
    log_activity(
        activity_type="Visit Recorded",
        description=f"Visit {visit_id} to customer {visit.customer_id} recorded with outcome: {visit.visit_outcome}"
    )

    return jsonify({
        'success': True,
        'message': 'Visit recorded successfully',
        'order_id': visit.order_id
    })

@rep_routes_bp.route('/api/mobile/available-products', methods=['GET'])
def mobile_get_products():
    # In a real app, authenticate with token

    # Get all available products for sale
    products = Item.query.join(Inventory).filter(
        Inventory.quantity > 0
    ).distinct().all()

    return jsonify({
        'success': True,
        'products': [{
            'id': product.id,
            'name': product.name,
            'sku': product.sku,
            'price': float(product.price) if product.price else 0,
            'unit': product.unit_of_measure,
            'description': product.description,
            'available': sum(inv.quantity for inv in product.inventory)
        } for product in products]
    })

@rep_routes_bp.route('/api/mobile/customers', methods=['GET'])
def mobile_get_customers():
    # In a real app, authenticate with token
    rep_id = request.args.get('rep_id', type=int)

    if not rep_id:
        return jsonify({
            'success': False,
            'message': 'Representative ID is required'
        }), 400

    # Get the representative's territory
    rep = SalesRepresentative.query.get_or_404(rep_id)

    # Get all customers in the representative's territory
    # This is a simplified example - in a real app, you'd have territory-customer mapping
    customers = Customer.query.all()

    return jsonify({
        'success': True,
        'customers': [{
            'id': customer.id,
            'name': customer.customer_name,
            'contact_info': customer.contact_info,
            'address': customer.billing_address,
            'location': {
                'latitude': None,  # You would store this in your Customer model
                'longitude': None
            }
        } for customer in customers]
    })

@rep_routes_bp.route('/api/mobile/performance', methods=['GET'])
def mobile_get_performance():
    # In a real app, authenticate with token
    rep_id = request.args.get('rep_id', type=int)

    if not rep_id:
        return jsonify({
            'success': False,
            'message': 'Representative ID is required'
        }), 400

    # Get date range - default to current month
    today = datetime.now().date()
    start_date = datetime(today.year, today.month, 1).date()
    end_date = today

    # Get or calculate performance
    performance = RepresentativePerformance.query.filter(
        RepresentativePerformance.representative_id == rep_id,
        RepresentativePerformance.period_start == start_date,
        RepresentativePerformance.period_end == end_date
    ).first()

    if not performance:
        performance = evaluate_rep_performance(rep_id, start_date, end_date)

    return jsonify({
        'success': True,
        'performance': {
            'period_start': performance.period_start.isoformat(),
            'period_end': performance.period_end.isoformat(),
            'total_visits': performance.total_visits,
            'completed_visits': performance.completed_visits,
            'total_sales': float(performance.total_sales),
            'total_orders': performance.total_orders,
            'conversion_rate': performance.conversion_rate,
            'average_order_value': float(performance.average_order_value),
            'evaluation_score': performance.evaluation_score
        }
    })

# Webhook for real-time location updates
@rep_routes_bp.route('/api/mobile/location-webhook', methods=['POST'])
def location_webhook():
    data = request.json
    rep_id = data.get('rep_id')
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    timestamp = data.get('timestamp')

    if not all([rep_id, latitude, longitude]):
        return jsonify({
            'success': False,
            'message': 'Missing required fields'
        }), 400

    # In a real implementation, you would store this in a location tracking table
    # For simplicity, we'll just return success

    return jsonify({
        'success': True,
        'message': 'Location updated successfully'
    })

# Integration with other systems
@rep_routes_bp.route('/api/integration/export-routes', methods=['GET'])
@login_required
def export_routes():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    else:
        start_date = datetime.now().date() - timedelta(days=30)

    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    else:
        end_date = datetime.now().date()

    # Get routes in the date range
    routes = RepresentativeRoute.query.filter(
        RepresentativeRoute.route_date.between(start_date, end_date)
    ).all()

    # Format data for export
    export_data = []

    for route in routes:
        route_data = {
            'route_id': route.id,
            'representative_id': route.representative_id,
            'representative_name': route.representative.user.username if route.representative.user else 'Unknown',
            'route_name': route.route_name,
            'route_date': route.route_date.isoformat(),
            'status': route.status,
            'notes': route.notes,
            'visits': []
        }

        for visit in route.visits:
            visit_data = {
                'visit_id': visit.id,
                'customer_id': visit.customer_id,
                'customer_name': visit.customer.customer_name if visit.customer else 'Unknown',
                'scheduled_time': visit.scheduled_time.isoformat() if visit.scheduled_time else None,
                'actual_visit_time': visit.actual_visit_time.isoformat() if visit.actual_visit_time else None,
                'status': visit.status,
                'outcome': visit.visit_outcome,
                'notes': visit.visit_notes,
                'order_id': visit.order_id,
                'location': {
                    'latitude': visit.location_latitude,
                    'longitude': visit.location_longitude
                } if visit.location_latitude and visit.location_longitude else None
            }

            route_data['visits'].append(visit_data)

        export_data.append(route_data)

    return jsonify({
        'success': True,
        'data': export_data
    })

# Route optimization
@rep_routes_bp.route('/routes/optimize/<int:route_id>', methods=['POST'])
@login_required
def optimize_route(route_id):
    route = RepresentativeRoute.query.get_or_404(route_id)

    # In a real implementation, you would use a routing algorithm
    # For simplicity, we'll just sort visits by customer name
    visits = sorted(route.visits, key=lambda v: v.customer.customer_name if v.customer else '')

    # Update visit order
    for i, visit in enumerate(visits):
        visit.visit_order = i + 1

    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Route optimized successfully'
    })

# Batch route creation
@rep_routes_bp.route('/routes/batch-create', methods=['POST'])
@login_required
def batch_create_routes():
    data = request.json

    rep_ids = data.get('representative_ids', [])
    start_date = datetime.strptime(data.get('start_date'), '%Y-%m-%d').date()
    end_date = datetime.strptime(data.get('end_date'), '%Y-%m-%d').date()
    route_template = data.get('route_template', {})

    created_routes = []

    # Create routes for each representative for each day in the date range
    current_date = start_date
    while current_date <= end_date:
        for rep_id in rep_ids:
            # Skip weekends if specified
            if data.get('skip_weekends') and current_date.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
                continue

            # Create route
            route = RepresentativeRoute(
                representative_id=rep_id,
                route_name=f"Route for {current_date.strftime('%Y-%m-%d')}",
                route_date=current_date,
                notes=route_template.get('notes', '')
            )

            db.session.add(route)
            db.session.flush()  # Get the route ID without committing

            # Create visits from template if provided
            for visit_template in route_template.get('visits', []):
                customer_visit = CustomerVisit(
                    route_id=route.id,
                    customer_id=visit_template.get('customer_id'),
                    scheduled_time=datetime.combine(current_date, datetime.strptime(visit_template.get('time', '09:00'), '%H:%M').time()) if visit_template.get('time') else None,
                    visit_notes=visit_template.get('notes', '')
                )
                db.session.add(customer_visit)

            created_routes.append(route.id)

        current_date += timedelta(days=1)

    db.session.commit()

    # Log the activity
    log_activity(
        activity_type="Batch Routes Created",
        description=f"Batch created {len(created_routes)} routes for {len(rep_ids)} representatives from {start_date} to {end_date}"
    )

    return jsonify({
        'success': True,
        'route_ids': created_routes,
        'message': f'Successfully created {len(created_routes)} routes'
    })

# Add this new API endpoint for fetching representative data
@rep_routes_bp.route('/api/<int:rep_id>')
@login_required
def api_get_rep_short(rep_id):  # Different function name
    try:
        rep = SalesRepresentative.query.get_or_404(rep_id)
        return jsonify({
            'id': rep.id,
            'user_id': rep.user_id,
            'name': rep.user.username if rep.user else None,
            'territory': rep.territory,
            'commission_rate': rep.commission_rate,
            'is_active': rep.is_active
        })
    except Exception as e:
        # Log the error
        print(f"Error fetching representative {rep_id}: {str(e)}")
        return jsonify({
            'error': 'Failed to fetch representative data',
            'message': str(e)
        }), 500



# Now we need to register this blueprint in the main app.py file
# Add this to app.py:
# from routes.sales_representative_routes import rep_routes_bp
# app.register_blueprint(rep_routes_bp)

