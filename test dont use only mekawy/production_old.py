from flask import Blueprint, request, jsonify, render_template, abort, current_app, send_file, make_response
from flask_login import current_user, login_required
from models import (
    db, Item, Inventory, InventoryTransaction, Warehouse, Category, BOM, BOMDetail,
    ProductionOrder, ProductionLine, Batch, ProductionStep, ProductionStepRecord,
    ProductionParameter, QCTest, QCTestResult, PackagingOrder, PackagingLine,
    PackagingMaterialUsage, ProductLabel
)
from datetime import datetime, timedelta
from sqlalchemy import func, desc
import uuid
import os
import tempfile
import subprocess
import json
import barcode
from barcode.writer import ImageWriter
from io import BytesIO, _io
import pandas as pd
import base64# Create a Blueprint for Production routes
production_bp = Blueprint('production', __name__)

@production_bp.route('/production/api/items', methods=['GET'])
@login_required
def get_items():
    """Get items based on type"""
    item_type = request.args.get('type')
    
    if item_type == 'product':
        # Get only final products by joining with categories
        items = db.session.query(Item).join(Category).filter(
            Category.category_type == 'FinalProduct'
        ).all()
    elif item_type == 'packaging':
        # Get only packaging materials by joining with categories
        items = db.session.query(Item).join(Category).filter(
            Category.category_type == 'Packaging'
        ).all()
    else:
        items = Item.query.all()
    
    # Get all product IDs that have BOMs in a single efficient query
    products_with_bom = {bom.final_product_id for bom in BOM.query.with_entities(BOM.final_product_id).all()}
    
    result = []
    for item in items:
        result.append({
            'id': item.id,
            'name': item.name,
            'sku': item.sku,
            'category_id': item.category_id,
            'category_name': item.category.name if item.category else None,
            'category_type': item.category.category_type if item.category else None,
            'has_bom': item.id in products_with_bom
        })
    
    return jsonify(result)
# Production Order Management
@production_bp.route('/api/production/orders', methods=['GET'])
@login_required
def get_production_orders():
    """Get all production orders"""
    orders = ProductionOrder.query.all()
    result = []
    
    for order in orders:
        product = Item.query.get(order.product_id)
        production_line = ProductionLine.query.get(order.production_line_id) if order.production_line_id else None
        
        result.append({
            'id': order.id,
            'product_id': order.product_id,
            'product_name': product.name if product else 'Unknown Product',
            'quantity': order.quantity,
            'status': order.status,
            'production_line_id': order.production_line_id,
            'production_line_name': production_line.name if production_line else None,
            'scheduled_start': order.scheduled_start.isoformat() if order.scheduled_start else None,
            'scheduled_end': order.scheduled_end.isoformat() if order.scheduled_end else None,
            'actual_start': order.actual_start.isoformat() if order.actual_start else None,
            'actual_end': order.actual_end.isoformat() if order.actual_end else None,
            'created_at': order.created_at.isoformat(),
            'updated_at': order.updated_at.isoformat()
        })
    
    return jsonify(result)

@production_bp.route('/api/production/check-materials', methods=['POST'])
@login_required
def check_materials():
    try:
        data = request.json
        
        # Validate required fields
        if not data or 'product_id' not in data or 'quantity' not in data or 'warehouse_id' not in data:
            return jsonify({
                'success': False,
                'message': 'Missing required fields: product_id, quantity, warehouse_id'
            }), 400
        
        product_id = data.get('product_id')
        quantity = int(data.get('quantity'))
        warehouse_id = data.get('warehouse_id')
        
        # Get the BOM for this product
        bom = BOM.query.filter_by(final_product_id=product_id).first()
        
        # Check if BOM exists
        has_bom = bom is not None
        
        if not has_bom:
            return jsonify({
                'success': True,
                'has_bom': False,
                'all_materials_available': False,
                'materials': [],
                'message': 'No BOM found for this product'
            })
        
        # Get BOM items
        bom_items = BOMDetail.query.filter_by(bom_id=bom.id).all()
        
        if not bom_items:
            return jsonify({
                'success': True,
                'has_bom': True,
                'all_materials_available': False,
                'materials': [],
                'message': 'BOM has no components'
            })
        
        # Check inventory for each component
        materials = []
        all_materials_available = True
        
        for item in bom_items:
            # Calculate required quantity
            required_qty = item.quantity_required * quantity
            
            # Check inventory
            inventory = Inventory.query.filter_by(
                item_id=item.component_item_id,
                warehouse_id=warehouse_id
            ).first()
            
            available_qty = inventory.quantity if inventory else 0
            is_available = available_qty >= required_qty
            
            if not is_available:
                all_materials_available = False
            
            # Get component details
            component = Item.query.get(item.component_item_id)
            
            materials.append({
                'component_id': item.component_item_id,
                'component_name': component.name if component else f"Component #{item.component_item_id}",
                'required': required_qty,
                'available': available_qty,
                'is_available': is_available
            })
        
        return jsonify({
            'success': True,
            'has_bom': True,
            'all_materials_available': all_materials_available,
            'materials': materials
        })
    
    except Exception as e:
        # Log the error for debugging
        current_app.logger.error(f"Error checking materials: {str(e)}")
        
        # Return a proper JSON error response
        return jsonify({
            'success': False,
            'has_bom': False,
            'all_materials_available': False,
            'materials': [],
            'message': f'Error checking materials: {str(e)}'
        }), 500


@production_bp.route('/api/production/orders/<int:order_id>', methods=['GET'])
@login_required
def get_production_order(order_id):
    """Get a production order by ID with its batches"""
    try:
        # Get the production order
        order = ProductionOrder.query.get_or_404(order_id)
        
        # Get the product
        product = Item.query.get(order.product_id)
        
        # Get the production line if assigned
        production_line = None
        if order.production_line_id:
            production_line = ProductionLine.query.get(order.production_line_id)
        
        # Format the response
        result = {
            'id': order.id,
            'product_id': order.product_id,
            'product_name': product.name if product else 'Unknown Product',
            'quantity': order.quantity,
            'status': order.status,
            'production_line_id': order.production_line_id,
            'production_line_name': production_line.name if production_line else None,
            'scheduled_start': order.scheduled_start.isoformat() if order.scheduled_start else None,
            'scheduled_end': order.scheduled_end.isoformat() if order.scheduled_end else None,
            'actual_start': order.actual_start.isoformat() if order.actual_start else None,
            'actual_end': order.actual_end.isoformat() if order.actual_end else None,
            'created_at': order.created_at.isoformat(),
            'updated_at': order.updated_at.isoformat(),
            'batches': []
        }
        
        # Instead of using the ORM relationship, query batches directly if they exist
        # This is a temporary workaround until the database schema is updated
        try:
            # Try to get batches using the relationship if the column exists
            batches = order.batches
        except:
            # If that fails, return an empty list for batches
            batches = []
        
        # Add batch information
        for batch in batches:
            result['batches'].append({
                'id': batch.id,
                'lot_number': batch.lot_number,
                'quantity': batch.quantity,
                'status': batch.status,
                'production_date': batch.production_date.isoformat() if batch.production_date else None,
                'expiry_date': batch.expiry_date.isoformat() if batch.expiry_date else None
            })
        
        return jsonify(result)
    
    except Exception as e:
        # Log the error
        current_app.logger.error(f"Error fetching production order: {str(e)}")
        return jsonify({'message': f'Error fetching order details: {str(e)}'}), 500

@production_bp.route('/api/production/orders/<int:order_id>/start-production', methods=['POST'])
@login_required
def start_production(order_id):
    """Start production for an order by deducting materials based on BOM"""
    try:
        order = ProductionOrder.query.get_or_404(order_id)
        
        # Check if production line is assigned
        if not order.production_line_id:
            return jsonify({'message': 'Cannot start production without assigning a production line'}), 400
        
        # Check if order is in Planned status
        if order.status != 'Planned':
            return jsonify({'message': f'Cannot start production for order with status: {order.status}'}), 400
        
        # Get the product's BOM
        bom = BOM.query.filter_by(final_product_id=order.product_id).first()
        if not bom:
            return jsonify({'message': 'Product does not have a Bill of Materials (BOM)'}), 400
        
        # Get BOM details
        bom_details = BOMDetail.query.filter_by(bom_id=bom.id).all()
        if not bom_details:
            return jsonify({'message': 'BOM has no components defined'}), 400
        
        data = request.get_json() or {}
        warehouse_id = data.get('warehouse_id')
        
        # Validate warehouse
        if not warehouse_id:
            return jsonify({'message': 'Warehouse ID is required'}), 400
            
        warehouse = Warehouse.query.get(warehouse_id)
        if not warehouse:
            return jsonify({'message': 'Warehouse not found'}), 404
        
        # Check material availability and deduct from inventory
        insufficient_materials = []
        
        for detail in bom_details:
            # Calculate required quantity based on production order quantity
            required_qty = detail.quantity * order.quantity
            
            # Check inventory
            inventory = Inventory.query.filter_by(
                item_id=detail.component_id,
                warehouse_id=warehouse_id
            ).first()
            
            if not inventory or inventory.quantity < required_qty:
                component = Item.query.get(detail.component_id)
                insufficient_materials.append({
                    'component_id': detail.component_id,
                    'component_name': component.name if component else f'Component ID: {detail.component_id}',
                    'required': required_qty,
                    'available': inventory.quantity if inventory else 0
                })
        
        # If any materials are insufficient, return error
        if insufficient_materials:
            return jsonify({
                'message': 'Insufficient materials in inventory',
                'insufficient_materials': insufficient_materials
            }), 400
        
        # Deduct materials from inventory
        for detail in bom_details:
            required_qty = detail.quantity * order.quantity
            
            inventory = Inventory.query.filter_by(
                item_id=detail.component_id,
                warehouse_id=warehouse_id
            ).first()
            
            # Deduct from inventory
            inventory.quantity -= required_qty
            
            # Create inventory transaction
            transaction = InventoryTransaction(
                item_id=detail.component_id,
                warehouse_id=warehouse_id,
                transaction_type='OUT',
                quantity=required_qty,
                reference=f'Production Order #{order.id}',
                transaction_date=datetime.now(),
                created_by=current_user.id
            )
            db.session.add(transaction)
        
        # Update order status
        order.status = 'InProgress'
        order.actual_start = datetime.now()
        
        db.session.commit()
        
        return jsonify({
            'id': order.id,
            'status': order.status,
            'actual_start': order.actual_start.isoformat(),
            'message': 'Production started successfully. Materials deducted from inventory.'
        })
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error starting production: {str(e)}")
        return jsonify({'message': f'Error starting production: {str(e)}'}), 500

@production_bp.route('/api/production/orders/<int:order_id>/check-materials', methods=['POST'])
@login_required
def check_material_availability(order_id):
    """Check if all materials required for production are available"""
    try:
        order = ProductionOrder.query.get_or_404(order_id)
        data = request.get_json() or {}
        warehouse_id = data.get('warehouse_id')
        
        # Validate warehouse
        if not warehouse_id:
            return jsonify({'message': 'Warehouse ID is required'}), 400
            
        warehouse = Warehouse.query.get(warehouse_id)
        if not warehouse:
            return jsonify({'message': 'Warehouse not found'}), 404
        
        # Get the product's BOM
        bom = BOM.query.filter_by(final_product_id=order.product_id).first()
        if not bom:
            return jsonify({'message': 'Product does not have a Bill of Materials (BOM)'}), 400
        
        # Get BOM details
        bom_details = BOMDetail.query.filter_by(bom_id=bom.id).all()
        if not bom_details:
            return jsonify({'message': 'BOM has no components defined'}), 400
        
        # Check material availability
        material_status = []
        all_available = True
        
        for detail in bom_details:
            # Calculate required quantity based on production order quantity
            required_qty = detail.quantity * order.quantity
            
            # Check inventory
            inventory = Inventory.query.filter_by(
                item_id=detail.component_id,
                warehouse_id=warehouse_id
            ).first()
            
            component = Item.query.get(detail.component_id)
            available_qty = inventory.quantity if inventory else 0
            is_available = available_qty >= required_qty
            
            if not is_available:
                all_available = False
            
            material_status.append({
                'component_id': detail.component_id,
                'component_name': component.name if component else f'Component ID: {detail.component_id}',
                'required': required_qty,
                'available': available_qty,
                'is_available': is_available
            })
        
        return jsonify({
            'order_id': order.id,
            'all_materials_available': all_available,
            'materials': material_status
        })
    
    except Exception as e:
        current_app.logger.error(f"Error checking material availability: {str(e)}")
        return jsonify({'message': f'Error checking material availability: {str(e)}'}), 500


@production_bp.route('/api/production/orders', methods=['POST'])
@login_required
def create_production_order():
    """Create a new production order"""
    data = request.get_json()
    
    # Validate required fields
    if not data.get('product_id') or not data.get('quantity'):
        return jsonify({'message': 'Missing required fields: product_id or quantity'}), 400
    
    # Check if product exists and is a final product
    product = Item.query.get(data['product_id'])
    if not product:
        return jsonify({'message': 'Product not found'}), 404
    
    # Verify product is a final product
    category = Category.query.get(product.category_id)
    if not category or category.category_type != 'FinalProduct':
        return jsonify({'message': 'Selected item is not a final product'}), 400
    
    # Check if product has a BOM
    bom = BOM.query.filter_by(final_product_id=product.id).first()
    if not bom:
        return jsonify({'message': 'Product does not have a Bill of Materials (BOM)'}), 400
    
    # Check if quantity is positive
    if int(data['quantity']) <= 0:
        return jsonify({'message': 'Quantity must be positive'}), 400
    
    # Create new production order
    order = ProductionOrder(
        product_id=data['product_id'],
        quantity=int(data['quantity']),
        status='Planned',
        scheduled_start=datetime.fromisoformat(data['scheduled_start']) if data.get('scheduled_start') else None,
        scheduled_end=datetime.fromisoformat(data['scheduled_end']) if data.get('scheduled_end') else None,
        created_by=current_user.id
    )
    
    db.session.add(order)
    db.session.commit()
    
    return jsonify({
        'id': order.id,
        'product_id': order.product_id,
        'product_name': product.name,
        'quantity': order.quantity,
        'status': order.status,
        'scheduled_start': order.scheduled_start.isoformat() if order.scheduled_start else None,
        'scheduled_end': order.scheduled_end.isoformat() if order.scheduled_end else None,
        'created_at': order.created_at.isoformat(),
        'message': 'Production order created successfully'
    }), 201


@production_bp.route('/api/production/orders/<int:order_id>', methods=['PUT'])
@login_required
def update_production_order(order_id):
    """Update a production order"""
    order = ProductionOrder.query.get_or_404(order_id)
    data = request.get_json()
    
    # Update fields if provided
    if data.get('quantity'):
        if int(data['quantity']) <= 0:
            return jsonify({'message': 'Quantity must be positive'}), 400
        order.quantity = int(data['quantity'])
    
    if data.get('status'):
        valid_statuses = ['Planned', 'InProgress', 'Completed', 'Cancelled', 'OnHold']
        if data['status'] not in valid_statuses:
            return jsonify({'message': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'}), 400
        order.status = data['status']
    
    if data.get('scheduled_start'):
        order.scheduled_start = datetime.fromisoformat(data['scheduled_start'])
    
    if data.get('scheduled_end'):
        order.scheduled_end = datetime.fromisoformat(data['scheduled_end'])
    
    if data.get('actual_start'):
        order.actual_start = datetime.fromisoformat(data['actual_start'])
    
    if data.get('actual_end'):
        order.actual_end = datetime.fromisoformat(data['actual_end'])
    
    db.session.commit()
    
    return jsonify({
        'id': order.id,
        'status': order.status,
        'quantity': order.quantity,
        'scheduled_start': order.scheduled_start.isoformat() if order.scheduled_start else None,
        'scheduled_end': order.scheduled_end.isoformat() if order.scheduled_end else None,
        'actual_start': order.actual_start.isoformat() if order.actual_start else None,
        'actual_end': order.actual_end.isoformat() if order.actual_end else None,
        'updated_at': order.updated_at.isoformat(),
        'message': 'Production order updated successfully'
    })

@production_bp.route('/api/production/orders/<int:order_id>', methods=['DELETE'])
@login_required
def delete_production_order(order_id):
    """Delete a production order"""
    order = ProductionOrder.query.get_or_404(order_id)
    
    # Check if order can be deleted (only if it's in Planned status)
    if order.status != 'Planned':
        return jsonify({'message': 'Only orders in Planned status can be deleted'}), 400
    
    # Check if there are any batches associated with this order
    batches = Batch.query.filter_by(production_order_id=order_id).all()
    if batches:
        return jsonify({'message': 'Cannot delete order with associated batches'}), 400
    
    db.session.delete(order)
    db.session.commit()
    
    return '', 204

@production_bp.route('/api/production/orders/<int:order_id>/assign-line', methods=['POST'])
@login_required
def assign_production_line(order_id):
    """Assign a production line to an order"""
    order = ProductionOrder.query.get_or_404(order_id)
    data = request.get_json()
    
    # Validate required fields
    if not data.get('production_line_id'):
        return jsonify({'message': 'Missing required field: production_line_id'}), 400
    
    # Check if production line exists
    production_line = ProductionLine.query.get(data['production_line_id'])
    if not production_line:
        return jsonify({'message': 'Production line not found'}), 404
    
    # Check if production line is active
    if not production_line.is_active:
        return jsonify({'message': 'Production line is not active'}), 400
    
    # Assign production line to order
    order.production_line_id = data['production_line_id']
    
    db.session.commit()
    
    return jsonify({
        'id': order.id,
        'production_line_id': order.production_line_id,
        'production_line_name': production_line.name,
        'status': order.status,
        'message': 'Production line assigned successfully'
    })


@production_bp.route('/api/production/lines', methods=['GET'])
@login_required
def get_production_lines():
    """Get all production lines"""
    lines = ProductionLine.query.all()
    result = []
    
    for line in lines:
        result.append({
            'id': line.id,
            'name': line.name,
            'description': line.description,
            'capacity_per_hour': line.capacity_per_hour,
            'is_active': line.is_active,
            'created_at': line.created_at.isoformat()
        })
    
    return jsonify(result)

# Batch Management
@production_bp.route('/api/production/batches', methods=['GET'])
@login_required
def get_batches():
    """Get all production batches"""
    batches = Batch.query.all()
    result = []
    
    for batch in batches:
        item = Item.query.get(batch.item_id)
        result.append({
            'id': batch.id,
            'item_id': batch.item_id,
            'item_name': item.name if item else 'Unknown Item',
            'lot_number': batch.lot_number,
            'production_date': batch.production_date.isoformat() if batch.production_date else None,
            'expiry_date': batch.expiry_date.isoformat() if batch.expiry_date else None,
            'quantity': batch.quantity,
            'status': batch.status,
            'production_order_id': batch.production_order_id
        })
    
    return jsonify(result)

@production_bp.route('/api/production/batches/<int:batch_id>', methods=['GET'])
@login_required
def get_batch(batch_id):
    """Get a specific batch"""
    batch = Batch.query.get_or_404(batch_id)
    item = Item.query.get(batch.item_id)
    
    # Get production steps for this batch
    step_records = ProductionStepRecord.query.filter_by(batch_id=batch_id).all()
    steps_data = []
    
    for record in step_records:
        step = ProductionStep.query.get(record.step_id)
        steps_data.append({
            'id': record.id,
            'step_id': record.step_id,
            'step_name': step.name if step else 'Unknown Step',
            'start_time': record.start_time.isoformat() if record.start_time else None,
            'end_time': record.end_time.isoformat() if record.end_time else None,
            'operator_id': record.operator_id,
            'notes': record.notes,
            'parameters': record.parameters
        })
    
    # Get QC tests for this batch
    qc_tests = QCTest.query.filter_by(batch_id=batch_id).all()
    tests_data = []
    
    for test in qc_tests:
        test_results = QCTestResult.query.filter_by(test_id=test.id).all()
        results_data = []
        
        for result in test_results:
            results_data.append({
                'id': result.id,
                'parameter_name': result.parameter_name,
                'expected_value': result.expected_value,
                'actual_value': result.actual_value,
                'is_passed': result.is_passed
            })
        
        tests_data.append({
            'id': test.id,
            'test_type': test.test_type,
            'status': test.status,
            'created_at': test.created_at.isoformat(),
            'completed_at': test.completed_at.isoformat() if test.completed_at else None,
            'inspector_id': test.inspector_id,
            'notes': test.notes,
            'results': results_data
        })
    
    # Get packaging orders for this batch
    packaging_orders = PackagingOrder.query.filter_by(batch_id=batch_id).all()
    packaging_data = []
    
    for order in packaging_orders:
        packaging_line = PackagingLine.query.get(order.packaging_line_id) if order.packaging_line_id else None
        
        # Get materials used in this packaging order
        materials = PackagingMaterialUsage.query.filter_by(packaging_order_id=order.id).all()
        materials_data = []
        
        for material in materials:
            item = Item.query.get(material.material_id)
            materials_data.append({
                'id': material.id,
                'material_id': material.material_id,
                'material_name': item.name if item else 'Unknown Material',
                'quantity_used': material.quantity_used
            })
        
        packaging_data.append({
            'id': order.id,
            'packaging_type': order.packaging_type,
            'quantity': order.quantity,
            'status': order.status,
            'packaging_line_id': order.packaging_line_id,
            'packaging_line_name': packaging_line.name if packaging_line else None,
            'scheduled_date': order.scheduled_date.isoformat() if order.scheduled_date else None,
            'completed_date': order.completed_date.isoformat() if order.completed_date else None,
            'materials': materials_data
        })
    
    # Get product labels for this batch
    labels = ProductLabel.query.filter_by(batch_id=batch_id).all()
    labels_data = []
    
    for label in labels:
        labels_data.append({
            'id': label.id,
            'label_template': label.label_template,
            'quantity': label.quantity,
            'generated_at': label.generated_at.isoformat(),
            'label_data': label.label_data
        })
    
    return jsonify({
        'id': batch.id,
        'item_id': batch.item_id,
        'item_name': item.name if item else 'Unknown Item',
        'lot_number': batch.lot_number,
        'production_date': batch.production_date.isoformat() if batch.production_date else None,
        'expiry_date': batch.expiry_date.isoformat() if batch.expiry_date else None,
        'quantity': batch.quantity,
        'status': batch.status,
        'production_order_id': batch.production_order_id,
        'production_steps': steps_data,
        'qc_tests': tests_data,
        'packaging_orders': packaging_data,
        'labels': labels_data
    })

# In routes/production_routes.py

@production_bp.route('/api/production/orders/<int:order_id>/batches', methods=['POST'])
@login_required
def create_batch(order_id):
    """Create a new batch for a production order"""
    order = ProductionOrder.query.get_or_404(order_id)
    data = request.get_json()
    
    if not order.production_line_id:
        return jsonify({'message': 'Cannot create batch without assigning a production line'}), 400
    
    # Validate required fields
    if 'quantity' not in data:
        return jsonify({'message': 'Missing required field: quantity'}), 400
    
    # Check if quantity is positive and doesn't exceed order quantity
    quantity = int(data['quantity'])
    if quantity <= 0:
        return jsonify({'message': 'Quantity must be positive'}), 400
    
    # Calculate total quantity of existing batches
    existing_batches_quantity = db.session.query(func.sum(Batch.quantity)).filter(
        Batch.production_order_id == order_id
    ).scalar() or 0
    
    # Check if new batch would exceed order quantity
    if existing_batches_quantity + quantity > order.quantity:
        return jsonify({
            'message': 'Batch quantity would exceed production order quantity',
            'order_quantity': order.quantity,
            'existing_batches_quantity': existing_batches_quantity,
            'remaining_quantity': order.quantity - existing_batches_quantity,
            'requested_quantity': quantity
        }), 400
    
    # Get the product for this order
    product = Item.query.get(order.product_id)
    if not product:
        return jsonify({'message': 'Product not found'}), 404
    
    # Generate a unique lot number
    current_date = datetime.now().strftime('%Y%m%d')
    lot_number = f"{current_date}-{product.sku}-{uuid.uuid4().hex[:6].upper()}"
    
    # Calculate expiry date if provided
    production_date = datetime.now()
    expiry_date = None
    if data.get('shelf_life_days'):
        shelf_life = int(data['shelf_life_days'])
        if shelf_life > 0:
            from datetime import timedelta
            expiry_date = production_date + timedelta(days=shelf_life)
    
    # Create new batch
    batch = Batch(
        item_id=product.id,
        lot_number=lot_number,
        production_date=production_date,
        expiry_date=expiry_date,
        quantity=quantity,
        production_order_id=order_id,
        status='Created'
    )
    
    db.session.add(batch)
    
    # Update order status if it's the first batch
    if order.status == 'Planned':
        order.status = 'InProgress'
        order.actual_start = datetime.now()
    
    db.session.commit()
    
    return jsonify({
        'id': batch.id,
        'item_id': batch.item_id,
        'item_name': product.name,
        'lot_number': batch.lot_number,
        'production_date': batch.production_date.isoformat(),
        'expiry_date': batch.expiry_date.isoformat() if batch.expiry_date else None,
        'quantity': batch.quantity,
        'status': batch.status,
        'production_order_id': order_id,
        'message': 'Batch created successfully'
    }), 201



@production_bp.route('/api/production/batches/<int:batch_id>/steps', methods=['POST'])
@login_required
def record_production_steps(batch_id):
    """Record production steps for a batch"""
    batch = Batch.query.get_or_404(batch_id)
    data = request.get_json()
    
    # Validate required fields
    if not data.get('step_id') or not data.get('start_time'):
        return jsonify({'message': 'Missing required fields: step_id or start_time'}), 400
    
    # Check if step exists
    step = ProductionStep.query.get(data['step_id'])
    if not step:
        return jsonify({'message': 'Production step not found'}), 404
    
    # Create new step record
    step_record = ProductionStepRecord(
        batch_id=batch_id,
        step_id=data['step_id'],
        start_time=datetime.fromisoformat(data['start_time']),
        end_time=datetime.fromisoformat(data['end_time']) if data.get('end_time') else None,
        operator_id=current_user.id,
        notes=data.get('notes'),
        parameters=data.get('parameters', {})
    )
    
    db.session.add(step_record)
    
    # Update batch status to InProduction if it's the first step
    if batch.status == 'Created':
        batch.status = 'InProduction'
    
    db.session.commit()
    
    return jsonify({
        'id': step_record.id,
        'batch_id': step_record.batch_id,
        'step_id': step_record.step_id,
        'step_name': step.name,
        'start_time': step_record.start_time.isoformat(),
        'end_time': step_record.end_time.isoformat() if step_record.end_time else None,
        'operator_id': step_record.operator_id,
        'notes': step_record.notes,
        'parameters': step_record.parameters,
        'message': 'Production step recorded successfully'
    }), 201

@production_bp.route('/api/production/steps/<int:record_id>', methods=['PUT'])
@login_required
def update_production_step(record_id):
    """Update a production step record"""
    step_record = ProductionStepRecord.query.get_or_404(record_id)
    data = request.get_json()
    
    # Update fields if provided
    if data.get('end_time'):
        step_record.end_time = datetime.fromisoformat(data['end_time'])
    
    if data.get('notes'):
        step_record.notes = data['notes']
    
    if data.get('parameters'):
        # Merge with existing parameters
        current_params = step_record.parameters or {}
        current_params.update(data['parameters'])
        step_record.parameters = current_params
    
    db.session.commit()
    
    step = ProductionStep.query.get(step_record.step_id)
    
    return jsonify({
        'id': step_record.id,
        'batch_id': step_record.batch_id,
        'step_id': step_record.step_id,
        'step_name': step.name if step else 'Unknown Step',
        'start_time': step_record.start_time.isoformat(),
        'end_time': step_record.end_time.isoformat() if step_record.end_time else None,
        'operator_id': step_record.operator_id,
        'notes': step_record.notes,
        'parameters': step_record.parameters,
        'message': 'Production step updated successfully'
    })

@production_bp.route('/api/production/steps/<int:step_id>/complete', methods=['POST'])
@login_required
def complete_production_step(step_id):
    """Complete a production step record"""
    try:
        # Find the step record
        step_record = ProductionStepRecord.query.get_or_404(step_id)
        
        # Handle the case where no JSON data is sent
        try:
            data = request.get_json() or {}
        except Exception:
            data = {}
        
        # Set the end time if not already set
        if not step_record.end_time:
            step_record.end_time = datetime.now()
        
        # Update notes if provided
        if 'notes' in data:
            step_record.notes = data['notes']
        
        # Update parameters if provided
        if 'parameters' in data and isinstance(data['parameters'], dict):
            current_params = step_record.parameters or {}
            current_params.update(data['parameters'])
            step_record.parameters = current_params
        
        # Get the batch to check if all steps are completed
        batch = Batch.query.get(step_record.batch_id)
        
        # Check if this is the last step for this batch
        if data.get('is_last_step') and batch:
            # Update batch status if needed
            if batch.status == 'InProduction':
                batch.status = 'QCPending'
        
        db.session.commit()
        
        return jsonify({
            'id': step_record.id,
            'batch_id': step_record.batch_id,
            'step_id': step_record.step_id,
            'start_time': step_record.start_time.isoformat(),
            'end_time': step_record.end_time.isoformat() if step_record.end_time else None,
            'operator_id': step_record.operator_id,
            'notes': step_record.notes,
            'parameters': step_record.parameters,
            'message': 'Production step completed successfully'
        })
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error completing production step: {str(e)}")
        return jsonify({'message': f'Error completing production step: {str(e)}'}), 500
    
@production_bp.route('/api/items/<int:item_id>/has-bom', methods=['GET'])
def check_item_has_bom(item_id):
    # Check if the item has a BOM
    bom = BOM.query.filter_by(final_product_id=item_id).first()
    
    if bom:
        return jsonify({'has_bom': True})
    else:
        return jsonify({'has_bom': False})


@production_bp.route('/api/production/qc/tests/<int:test_id>/complete', methods=['POST'])
@login_required
def complete_qc_test_alt(test_id):
    """Complete a QC test (alternative endpoint)"""
    qc_test = QCTest.query.get_or_404(test_id)
    data = request.get_json()
    
    # Update test status
    if data and data.get('status'):
        valid_statuses = ['Passed', 'Failed', 'Retest']
        if data['status'] not in valid_statuses:
            return jsonify({'message': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'}), 400
        qc_test.status = data['status']
    else:
        # Default to Passed if not specified
        qc_test.status = 'Passed'
    
    qc_test.completed_at = datetime.now()
    
    # Update batch status based on test result
    batch = Batch.query.get(qc_test.batch_id)
    if batch:
        if qc_test.status == 'Passed':
            # Check if all tests are passed
            all_tests_passed = True
            for test in QCTest.query.filter_by(batch_id=batch.id).all():
                if test.id != qc_test.id and (test.status != 'Passed' or test.status is None):
                    all_tests_passed = False
                    break
            
            if all_tests_passed:
                batch.status = 'QCPassed'
        elif qc_test.status == 'Failed':
            batch.status = 'QCFailed'
    
    db.session.commit()
    
    return jsonify({
        'id': qc_test.id,
        'status': qc_test.status,
        'completed_at': qc_test.completed_at.isoformat(),
        'batch_status': batch.status if batch else None,
        'message': 'QC test completed successfully'
    })


@production_bp.route('/api/production/batches/<int:batch_id>/parameters', methods=['POST'])
@login_required
def monitor_production_parameters(batch_id):
    """Record production parameters for a batch"""
    batch = Batch.query.get_or_404(batch_id)
    data = request.get_json()
    
    # Validate required fields
    if not data.get('parameter_name') or 'parameter_value' not in data:
        return jsonify({'message': 'Missing required fields: parameter_name or parameter_value'}), 400
    
    # Create new parameter record
    parameter = ProductionParameter(
        batch_id=batch_id,
        parameter_name=data['parameter_name'],
        parameter_value=str(data['parameter_value']),
        recorded_by=current_user.id
    )
    
    db.session.add(parameter)
    db.session.commit()
    
    return jsonify({
        'id': parameter.id,
        'batch_id': parameter.batch_id,
        'parameter_name': parameter.parameter_name,
        'parameter_value': parameter.parameter_value,
        'recorded_at': parameter.recorded_at.isoformat(),
        'recorded_by': parameter.recorded_by,
        'message': 'Production parameter recorded successfully'
    }), 201

@production_bp.route('/api/production/batches/<int:batch_id>/complete', methods=['POST'])
@login_required
def complete_production_batch(batch_id):
    """Complete a production batch"""
    batch = Batch.query.get_or_404(batch_id)
    
    # Check if batch can be completed
    if batch.status not in ['Created', 'InProduction']:
        return jsonify({'message': f'Cannot complete batch with status: {batch.status}'}), 400
    
    # Update batch status
    batch.status = 'QCPending'
    
    # Get the production order
    order = ProductionOrder.query.get(batch.production_order_id) if batch.production_order_id else None
    
    # Check if all batches for this order are completed
    if order:
        all_batches_completed = True
        total_produced = 0
        
        for b in Batch.query.filter_by(production_order_id=order.id).all():
            if b.status in ['Created', 'InProduction']:
                all_batches_completed = False
                break
            total_produced += b.quantity
        
        # If all batches are completed and total quantity matches or exceeds order quantity
        if all_batches_completed and total_produced >= order.quantity:
            order.status = 'Completed'
            order.actual_end = datetime.now()
    
    db.session.commit()
    
    return jsonify({
        'id': batch.id,
        'status': batch.status,
        'message': 'Production batch completed successfully'
    })

# Quality Control Management
@production_bp.route('/api/production/batches/<int:batch_id>/qc-tests', methods=['POST'])
@login_required
def create_qc_test(batch_id):
    """Create a new QC test for a batch"""
    batch = Batch.query.get_or_404(batch_id)
    data = request.get_json()
    
    # Validate required fields
    if not data.get('test_type'):
        return jsonify({'message': 'Missing required field: test_type'}), 400
    
    # Validate test type
    valid_test_types = ['Visual', 'Chemical', 'Physical', 'Microbiological', 'Sensory', 'Other']
    if data['test_type'] not in valid_test_types:
        return jsonify({'message': f'Invalid test type. Must be one of: {", ".join(valid_test_types)}'}), 400
    
    # Create new QC test
    qc_test = QCTest(
        batch_id=batch_id,
        test_type=data['test_type'],
        status='Pending',
        inspector_id=current_user.id,
        notes=data.get('notes')
    )
    
    db.session.add(qc_test)
    
    # Update batch status if it's the first QC test
    if batch.status == 'InProduction':
        batch.status = 'QCPending'
    
    db.session.commit()
    
    return jsonify({
        'id': qc_test.id,
        'batch_id': qc_test.batch_id,
        'test_type': qc_test.test_type,
        'status': qc_test.status,
        'created_at': qc_test.created_at.isoformat(),
        'inspector_id': qc_test.inspector_id,
        'notes': qc_test.notes,
        'message': 'QC test created successfully'
    }), 201

@production_bp.route('/api/production/qc-tests/<int:test_id>/results', methods=['POST'])
@login_required
def record_test_result(test_id):
    """Record results for a QC test"""
    qc_test = QCTest.query.get_or_404(test_id)
    data = request.get_json()
    
    # Validate required fields
    if not data.get('parameter_name') or 'actual_value' not in data:
        return jsonify({'message': 'Missing required fields: parameter_name or actual_value'}), 400
    
    # Convert is_passed to proper boolean if it exists
    is_passed = None
    if 'is_passed' in data:
        if isinstance(data['is_passed'], bool):
            is_passed = data['is_passed']
        elif isinstance(data['is_passed'], str):
            is_passed = data['is_passed'].lower() == 'true'
    
    # Create new test result
    test_result = QCTestResult(
        test_id=test_id,
        parameter_id=data.get('parameter_id'),
        parameter_name=data['parameter_name'],
        expected_value=data.get('expected_value'),
        actual_value=str(data['actual_value']),
        is_passed=is_passed,  # Use the properly converted boolean value
        notes=data.get('notes')
    )
    
    db.session.add(test_result)
    db.session.commit()
    
    return jsonify({
        'id': test_result.id,
        'test_id': test_result.test_id,
        'parameter_name': test_result.parameter_name,
        'expected_value': test_result.expected_value,
        'actual_value': test_result.actual_value,
        'is_passed': test_result.is_passed,
        'notes': test_result.notes,
        'message': 'Test result recorded successfully'
    }), 201

@production_bp.route('/api/production/qc-tests/<int:test_id>/complete', methods=['POST'])
@login_required
def complete_qc_test(test_id):
    """Complete a QC test"""
    qc_test = QCTest.query.get_or_404(test_id)
    data = request.get_json()
    
    # Update test status
    if data.get('status'):
        valid_statuses = ['Passed', 'Failed', 'Retest']
        if data['status'] not in valid_statuses:
            return jsonify({'message': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'}), 400
        qc_test.status = data['status']
    else:
        # Default to Passed if not specified
        qc_test.status = 'Passed'
    
    qc_test.completed_at = datetime.now()
    
    # Update batch status based on test result
    batch = Batch.query.get(qc_test.batch_id)
    if batch:
        if qc_test.status == 'Passed':
            # Check if all tests are passed
            all_tests_passed = True
            for test in QCTest.query.filter_by(batch_id=batch.id).all():
                if test.id != qc_test.id and (test.status != 'Passed' or test.status is None):
                    all_tests_passed = False
                    break
            
            if all_tests_passed:
                batch.status = 'QCPassed'
        elif qc_test.status == 'Failed':
            batch.status = 'QCFailed'
    
    db.session.commit()
    
    return jsonify({
        'id': qc_test.id,
        'status': qc_test.status,
        'completed_at': qc_test.completed_at.isoformat(),
        'batch_status': batch.status if batch else None,
        'message': 'QC test completed successfully'
    })

@production_bp.route('/api/production/batches/<int:batch_id>/approve', methods=['POST'])
@login_required
def approve_product_batch(batch_id):
    """Approve a batch after QC"""
    batch = Batch.query.get_or_404(batch_id)
    
    # Check if batch can be approved
    if batch.status != 'QCPassed' and batch.status != 'QCPending':
        return jsonify({'message': f'Cannot approve batch with status: {batch.status}'}), 400
    
    # Update batch status
    batch.status = 'Approved'
    
    # Add to inventory if specified
    data = request.get_json() or {}
    if data.get('add_to_inventory') and data.get('warehouse_id'):
        warehouse_id = data['warehouse_id']
        
        # Check if warehouse exists
        warehouse = Warehouse.query.get(warehouse_id)
        if not warehouse:
            return jsonify({'message': 'Warehouse not found'}), 404
        
        # Check if inventory record exists
        inventory = Inventory.query.filter_by(
            item_id=batch.item_id,
            warehouse_id=warehouse_id
        ).first()
        
        if inventory:
            inventory.quantity += batch.quantity
        else:
            inventory = Inventory(
                item_id=batch.item_id,
                warehouse_id=warehouse_id,
                quantity=batch.quantity
            )
            db.session.add(inventory)
        
        # Create inventory transaction
        transaction = InventoryTransaction(
            item_id=batch.item_id,
            warehouse_id=warehouse_id,
            transaction_type='IN',
            quantity=batch.quantity,
            reference=f'Production Batch {batch.lot_number}'
        )
        db.session.add(transaction)
    
    db.session.commit()
    
    return jsonify({
        'id': batch.id,
        'status': batch.status,
        'message': 'Batch approved successfully'
    })

@production_bp.route('/api/production/batches/<int:batch_id>/reject', methods=['POST'])
@login_required
def reject_product_batch(batch_id):
    """Reject a batch after QC"""
    batch = Batch.query.get_or_404(batch_id)
    data = request.get_json()
    
    # Validate required fields
    if not data.get('reason'):
        return jsonify({'message': 'Missing required field: reason'}), 400
    
    # Check if batch can be rejected
    if batch.status not in ['QCPending', 'QCPassed', 'QCFailed']:
        return jsonify({'message': f'Cannot reject batch with status: {batch.status}'}), 400
    
    # Update batch status
    batch.status = 'Rejected'
    
    # Record rejection reason as a parameter
    rejection_param = ProductionParameter(
        batch_id=batch_id,
        parameter_name='Rejection Reason',
        parameter_value=data['reason'],
        recorded_by=current_user.id
    )
    db.session.add(rejection_param)
    
    db.session.commit()
    
    return jsonify({
        'id': batch.id,
        'status': batch.status,
        'reason': data['reason'],
        'message': 'Batch rejected successfully'
    })

@production_bp.route('/api/production/qc-report', methods=['GET'])
@login_required
def generate_qc_report():
    """Generate a QC report based on parameters"""
    # Get query parameters
    batch_id = request.args.get('batch_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    test_type = request.args.get('test_type')
    status = request.args.get('status')
    
    # Build query
    query = QCTest.query
    
    if batch_id:
        query = query.filter(QCTest.batch_id == batch_id)
    
    if start_date:
        start_datetime = datetime.fromisoformat(start_date)
        query = query.filter(QCTest.created_at >= start_datetime)
    
    if end_date:
        end_datetime = datetime.fromisoformat(end_date)
        query = query.filter(QCTest.created_at <= end_datetime)
    
    if test_type:
        query = query.filter(QCTest.test_type == test_type)
    
    if status:
        query = query.filter(QCTest.status == status)
    
    # Execute query
    tests = query.all()
    result = []
    
    for test in tests:
        batch = Batch.query.get(test.batch_id)
        item = Item.query.get(batch.item_id) if batch else None
        
        # Get test results
        test_results = QCTestResult.query.filter_by(test_id=test.id).all()
        results_data = []
        
        for result_item in test_results:
            results_data.append({
                'parameter_name': result_item.parameter_name,
                'expected_value': result_item.expected_value,
                'actual_value': result_item.actual_value,
                'is_passed': result_item.is_passed
            })
        
        result.append({
            'id': test.id,
            'batch_id': test.batch_id,
            'batch_lot_number': batch.lot_number if batch else None,
            'item_id': batch.item_id if batch else None,
            'item_name': item.name if item else 'Unknown Item',
            'test_type': test.test_type,
            'status': test.status,
            'created_at': test.created_at.isoformat(),
            'completed_at': test.completed_at.isoformat() if test.completed_at else None,
            'inspector_id': test.inspector_id,
            'results': results_data
        })
    
    return jsonify(result)

# Packaging Management
@production_bp.route('/api/production/packaging-orders', methods=['POST'])
@login_required
def create_packaging_order():
    """Create a new packaging order for a batch"""
    data = request.get_json()
    
    # Validate required fields
    if not data.get('batch_id') or not data.get('packaging_type') or not data.get('quantity'):
        return jsonify({'message': 'Missing required fields: batch_id, packaging_type, or quantity'}), 400
    
    # Check if batch exists and is in appropriate status
    batch = Batch.query.get_or_404(data['batch_id'])
    if batch.status not in ['Approved', 'QCPassed']:
        return jsonify({'message': f'Batch must be Approved or QCPassed for packaging, current status: {batch.status}'}), 400
    
    # Check if quantity is positive and doesn't exceed batch quantity
    quantity = int(data['quantity'])
    if quantity <= 0:
        return jsonify({'message': 'Quantity must be positive'}), 400
    
    if quantity > batch.quantity:
        return jsonify({'message': f'Packaging quantity ({quantity}) exceeds batch quantity ({batch.quantity})'}), 400
    
    # Create new packaging order
    packaging_order = PackagingOrder(
        batch_id=data['batch_id'],
        packaging_type=data['packaging_type'],
        quantity=quantity,
        status='Pending',
        scheduled_date=datetime.fromisoformat(data['scheduled_date']) if data.get('scheduled_date') else None,
        created_by=current_user.id
    )
    
    db.session.add(packaging_order)
    
    # Update batch status
    batch.status = 'Packaging'
    
    db.session.commit()
    
    return jsonify({
        'id': packaging_order.id,
        'batch_id': packaging_order.batch_id,
        'packaging_type': packaging_order.packaging_type,
        'quantity': packaging_order.quantity,
        'status': packaging_order.status,
        'scheduled_date': packaging_order.scheduled_date.isoformat() if packaging_order.scheduled_date else None,
        'message': 'Packaging order created successfully'
    }), 201

@production_bp.route('/api/production/packaging-orders/<int:order_id>/assign-line', methods=['POST'])
@login_required
def assign_packaging_line(order_id):
    """Assign a packaging line to an order"""
    packaging_order = PackagingOrder.query.get_or_404(order_id)
    data = request.get_json()
    
    # Validate required fields
    if not data.get('packaging_line_id'):
        return jsonify({'message': 'Missing required field: packaging_line_id'}), 400
    
    # Check if packaging line exists
    packaging_line = PackagingLine.query.get(data['packaging_line_id'])
    if not packaging_line:
        return jsonify({'message': 'Packaging line not found'}), 404
    
    # Check if packaging line is active
    if not packaging_line.is_active:
        return jsonify({'message': 'Packaging line is not active'}), 400
    
    # Assign packaging line to order
    packaging_order.packaging_line_id = data['packaging_line_id']
    
    # If order is in Pending status, update to InProgress
    if packaging_order.status == 'Pending':
        packaging_order.status = 'InProgress'
    
    db.session.commit()
    
    return jsonify({
        'id': packaging_order.id,
        'packaging_line_id': packaging_order.packaging_line_id,
        'packaging_line_name': packaging_line.name,
        'status': packaging_order.status,
        'message': 'Packaging line assigned successfully'
    })

@production_bp.route('/api/production/packaging-orders/<int:order_id>/materials', methods=['POST'])
@login_required
def record_packaging_material(order_id):
    """Record packaging material usage for an order"""
    packaging_order = PackagingOrder.query.get_or_404(order_id)
    data = request.get_json()
    
    # Validate required fields
    if not data.get('material_id') or not data.get('quantity_used'):
        return jsonify({'message': 'Missing required fields: material_id or quantity_used'}), 400
    
    # Check if material exists
    material = Item.query.get(data['material_id'])
    if not material:
        return jsonify({'message': 'Material not found'}), 404
    
    # Check if material is a packaging material
    material_category = Category.query.get(material.category_id) if material.category_id else None
    if not material_category or getattr(material_category, 'category_type', None) != 'Packaging':
        return jsonify({'message': 'Item must be categorized as Packaging material'}), 400
    
    # Check if quantity is positive
    quantity_used = int(data['quantity_used'])
    if quantity_used <= 0:
        return jsonify({'message': 'Quantity used must be positive'}), 400
    
    # Always check inventory regardless of check_inventory flag
    warehouse_id = data.get('warehouse_id')
    if not warehouse_id:
        return jsonify({'message': 'Warehouse ID is required'}), 400
        
    inventory = Inventory.query.filter_by(
        item_id=data['material_id'],
        warehouse_id=warehouse_id
    ).first()
    
    # If inventory doesn't exist or is insufficient, return error
    if not inventory or inventory.quantity < quantity_used:
        return jsonify({
            'message': 'Not enough inventory for this material',
            'available': inventory.quantity if inventory else 0,
            'required': quantity_used
        }), 400
    
    # Deduct from inventory
    inventory.quantity -= quantity_used
    
    # Create inventory transaction
    transaction = InventoryTransaction(
        item_id=data['material_id'],
        warehouse_id=warehouse_id,
        transaction_type='OUT',
        quantity=quantity_used,
        reference=f'Packaging Order {packaging_order.id}',
        transaction_date=datetime.now(),
        created_by=current_user.id
    )
    db.session.add(transaction)
    
    # Create new packaging material usage record
    material_usage = PackagingMaterialUsage(
        packaging_order_id=order_id,
        material_id=data['material_id'],
        quantity_used=quantity_used
    )
    
    db.session.add(material_usage)
    db.session.commit()
    
    return jsonify({
        'id': material_usage.id,
        'packaging_order_id': material_usage.packaging_order_id,
        'material_id': material_usage.material_id,
        'material_name': material.name,
        'quantity_used': material_usage.quantity_used,
        'message': 'Packaging material recorded and deducted from inventory successfully'
    }), 201
    
    
@production_bp.route('/api/production/batches/<int:batch_id>/labels', methods=['POST'])
@login_required
def generate_product_label(batch_id):
    """Generate product labels for a batch"""
    batch = Batch.query.get_or_404(batch_id)
    data = request.get_json()
    
    # Validate required fields
    if not data.get('quantity'):
        return jsonify({'message': 'Missing required field: quantity'}), 400
    
    # Check if quantity is positive
    quantity = int(data['quantity'])
    if quantity <= 0:
        return jsonify({'message': 'Quantity must be positive'}), 400
    
    # Get product information
    item = Item.query.get(batch.item_id)
    if not item:
        return jsonify({'message': 'Product not found'}), 404
    
    # Generate label data
    label_data = {
        'product_name': item.name,
        'product_sku': item.sku,
        'lot_number': batch.lot_number,
        'production_date': batch.production_date.strftime('%Y-%m-%d') if batch.production_date else None,
        'expiry_date': batch.expiry_date.strftime('%Y-%m-%d') if batch.expiry_date else None,
        'barcode': f"{item.sku}-{batch.lot_number}"
    }
    
    # Create new product label record
    product_label = ProductLabel(
        batch_id=batch_id,
        label_template=data.get('label_template', 'standard'),
        quantity=quantity,
        generated_by=current_user.id,
        label_data=label_data
    )
    
    db.session.add(product_label)
    db.session.commit()
    
    return jsonify({
        'id': product_label.id,
        'batch_id': product_label.batch_id,
        'label_template': product_label.label_template,
        'quantity': product_label.quantity,
        'generated_at': product_label.generated_at.isoformat(),
        'label_data': product_label.label_data,
        'message': 'Product labels generated successfully'
    }), 201

@production_bp.route('/api/production/labels/<int:label_id>/print', methods=['GET'])
@login_required
def print_product_label(label_id):
    """Generate a printable PDF for product labels"""
    label = ProductLabel.query.get_or_404(label_id)
    batch = Batch.query.get(label.batch_id)
    item = Item.query.get(batch.item_id) if batch else None
    
    # Generate barcode image
    barcode_value = label.label_data.get('barcode', f"{item.sku if item else 'UNKNOWN'}-{batch.lot_number if batch else 'UNKNOWN'}")
    
    try:
        # Generate barcode as SVG
        from barcode import Code128
        from barcode.writer import ImageWriter
        from io import BytesIO
        import base64
        
        # Create barcode
        rv = BytesIO()
        Code128(barcode_value, writer=ImageWriter()).write(rv)
        
        # Convert to base64 for embedding in HTML
        barcode_base64 = base64.b64encode(rv.getvalue()).decode('utf-8')
        barcode_data_uri = f"data:image/png;base64,{barcode_base64}"
        
        # Prepare label data for template
        label_context = {
            'product_name': item.name if item else 'Unknown Product',
            'product_sku': item.sku if item else 'Unknown SKU',
            'lot_number': batch.lot_number if batch else 'Unknown Lot',
            'production_date': batch.production_date.strftime('%Y-%m-%d') if batch and batch.production_date else 'N/A',
            'expiry_date': batch.expiry_date.strftime('%Y-%m-%d') if batch and batch.expiry_date else 'N/A',
            'barcode_data_uri': barcode_data_uri,
            'barcode_value': barcode_value,
            'quantity': label.quantity
        }
        
        # Render label template
        html_content = render_template('product_label_template.html', label=label_context)
        
        # Generate PDF
        pdf_path = generate_pdf(html_content)
        
        # Send the PDF file
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=f'product-labels-{label.id}.pdf',
            mimetype='application/pdf'
        )
    
    except Exception as e:
        return jsonify({'message': f'Error generating label PDF: {str(e)}'}), 500

@production_bp.route('/api/production/packaging-orders/<int:order_id>/complete', methods=['POST'])
@login_required
def complete_packaging(order_id):
    """Complete a packaging order"""
    packaging_order = PackagingOrder.query.get_or_404(order_id)
    
    # Check if order can be completed
    if packaging_order.status not in ['Pending', 'InProgress']:
        return jsonify({'message': f'Cannot complete order with status: {packaging_order.status}'}), 400
    
    # Update order status
    packaging_order.status = 'Completed'
    packaging_order.completed_date = datetime.now()
    
    # Update batch status
    batch = Batch.query.get(packaging_order.batch_id)
    if not batch:
        return jsonify({'message': 'Associated batch not found'}), 404
        
    batch.status = 'Packaged'
    
    # Add to inventory if specified
    data = request.get_json() or {}
    if data.get('add_to_inventory') and data.get('warehouse_id'):
        warehouse_id = data.get('warehouse_id')
        
        # Check if warehouse exists
        warehouse = Warehouse.query.get(warehouse_id)
        if not warehouse:
            return jsonify({'message': 'Warehouse not found'}), 404
        
        # Get the product's BOM to deduct materials
        product_id = batch.item_id
        bom = BOM.query.filter_by(final_product_id=product_id).first()
        
        if bom:
            # Get BOM details
            bom_details = BOMDetail.query.filter_by(bom_id=bom.id).all()
            
            # Calculate and deduct materials based on packaged quantity
            for detail in bom_details:
                # Calculate required quantity for this packaging order
                required_qty = detail.quantity_required * packaging_order.quantity
                
                # Find inventory for this component
                component_inventory = Inventory.query.filter_by(
                    item_id=detail.component_item_id,
                    warehouse_id=warehouse_id
                ).first()
                
                # If inventory exists and has sufficient quantity, deduct it
                if component_inventory and component_inventory.quantity >= required_qty:
                    component_inventory.quantity -= required_qty
                    
                    # Create inventory transaction for material consumption
                    # FIXED: Removed 'created_by' parameter if it's not in the model
                    material_transaction = InventoryTransaction(
                        item_id=detail.component_item_id,
                        warehouse_id=warehouse_id,
                        transaction_type='OUT',
                        quantity=required_qty,
                        reference=f'Material for Packaging Order {packaging_order.id}',
                        transaction_date=datetime.now()
                        # Removed: created_by=current_user.id
                    )
                    db.session.add(material_transaction)
                else:
                    # Log warning but continue - we're completing the order anyway
                    current_app.logger.warning(
                        f"Insufficient inventory for component {detail.component_item_id} "
                        f"in warehouse {warehouse_id} for packaging order {packaging_order.id}"
                    )
        
        # Check if inventory record exists for the finished product
        inventory = Inventory.query.filter_by(
            item_id=batch.item_id,
            warehouse_id=warehouse_id
        ).first()
        
        if inventory:
            inventory.quantity += packaging_order.quantity
        else:
            inventory = Inventory(
                item_id=batch.item_id,
                warehouse_id=warehouse_id,
                quantity=packaging_order.quantity
            )
            db.session.add(inventory)
        
        # Create inventory transaction for the finished product
        # FIXED: Removed 'created_by' parameter if it's not in the model
        transaction = InventoryTransaction(
            item_id=batch.item_id,
            warehouse_id=warehouse_id,
            transaction_type='IN',
            quantity=packaging_order.quantity,
            reference=f'Packaged Product Batch {batch.lot_number}',
            transaction_date=datetime.now()
            # Removed: created_by=current_user.id
        )
        db.session.add(transaction)
    
    db.session.commit()
    
    return jsonify({
        'id': packaging_order.id,
        'status': packaging_order.status,
        'completed_date': packaging_order.completed_date.isoformat(),
        'batch_status': batch.status,
        'message': 'Packaging order completed successfully'
    })

@production_bp.route('/api/production/packaging-lines', methods=['GET'])
@login_required
def get_packaging_lines():
    """Get all packaging lines"""
    lines = PackagingLine.query.all()
    result = []
    
    for line in lines:
        result.append({
            'id': line.id,
            'name': line.name,
            'description': line.description,
            'capacity_per_hour': line.capacity_per_hour,
            'is_active': line.is_active,
            'created_at': line.created_at.isoformat()
        })
    
    return jsonify(result)
# In your route handler for packaging lines in production_routes.py
@production_bp.route('/api/production/packaging-lines', methods=['POST'])
@login_required
def create_packaging_line():
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('name'):
            return jsonify({'message': 'Missing required field: name'}), 400
        
        # Create new packaging line
        line = PackagingLine(
            name=data['name'],
            description=data.get('description', ''),
            capacity_per_hour=data.get('capacity_per_hour', 0),
            is_active=data.get('is_active', True)
        )
        
        db.session.add(line)
        db.session.commit()
        
        return jsonify({
            'id': line.id,
            'name': line.name,
            'description': line.description,
            'capacity_per_hour': line.capacity_per_hour,
            'is_active': line.is_active,
            'created_at': line.created_at.isoformat(),
            'message': 'Packaging line created successfully'
        }), 201
    
    except Exception as e:
        # Log the error
        current_app.logger.error(f"Error creating packaging line: {str(e)}")
        # Return JSON error instead of letting it propagate to HTML error page
        return jsonify({'message': f'Error creating packaging line: {str(e)}'}), 500


@production_bp.route('/api/production/steps', methods=['GET'])
@login_required
def get_production_steps():
    """Get all production steps"""
    steps = ProductionStep.query.order_by(ProductionStep.sequence_number).all()
    result = []
    
    for step in steps:
        result.append({
            'id': step.id,
            'name': step.name,
            'description': step.description,
            'standard_duration': step.standard_duration,
            'sequence_number': step.sequence_number
        })
    
    return jsonify(result)

from datetime import timedelta
from flask import jsonify, request

@production_bp.route('/api/production/labels', methods=['GET'])
@login_required
def get_product_labels():
    """Get all product labels"""
    labels = ProductLabel.query.all()
    result = []
    
    for label in labels:
        batch = Batch.query.get(label.batch_id)
        item = Item.query.get(batch.item_id) if batch else None
        
        result.append({
            'id': label.id,
            'batch_id': label.batch_id,
            'batch_lot_number': batch.lot_number if batch else None,
            'product_name': item.name if item else 'Unknown Product',
            'label_template': label.label_template,
            'quantity': label.quantity,
            'generated_at': label.generated_at.isoformat(),
            'label_data': label.label_data
        })
    
    return jsonify(result)

@production_bp.route('/api/production/packaging-orders/<int:order_id>/cancel', methods=['POST'])
@login_required
def cancel_packaging_order(order_id):
    """Cancel a packaging order"""
    order = PackagingOrder.query.get_or_404(order_id)
    
    # Check if order can be cancelled (only if it's in Pending status)
    if order.status != 'Pending':
        return jsonify({'message': 'Only orders in Pending status can be cancelled'}), 400
    
    # Update order status
    order.status = 'Cancelled'
    
    # Update batch status if needed
    batch = Batch.query.get(order.batch_id)
    if batch and batch.status == 'Packaging':
        # Check if there are other active packaging orders for this batch
        other_orders = PackagingOrder.query.filter(
            PackagingOrder.batch_id == batch.id,
            PackagingOrder.id != order.id,
            PackagingOrder.status.in_(['Pending', 'InProgress'])
        ).count()
        
        if other_orders == 0:
            batch.status = 'Approved'  # Revert to previous status
    
    db.session.commit()
    
    return jsonify({
        'id': order.id,
        'status': order.status,
        'message': 'Packaging order cancelled successfully'
    })

@production_bp.route('/api/production/packaging-lines/<int:line_id>/toggle-status', methods=['POST'])
@login_required
def toggle_packaging_line_status(line_id):
    """Toggle the active status of a packaging line"""
    line = PackagingLine.query.get_or_404(line_id)
    
    # Toggle status
    line.is_active = not line.is_active
    
    db.session.commit()
    
    return jsonify({
        'id': line.id,
        'is_active': line.is_active,
        'message': f'Packaging line {"activated" if line.is_active else "deactivated"} successfully'
    })


@production_bp.route('/api/production/packaging-orders/<int:order_id>/materials', methods=['GET'])
@login_required
def get_packaging_materials(order_id):
    """Get materials used in a packaging order"""
    materials = PackagingMaterialUsage.query.filter_by(packaging_order_id=order_id).all()
    result = []
    
    for material in materials:
        item = Item.query.get(material.material_id)
        result.append({
            'id': material.id,
            'material_id': material.material_id,
            'material_name': item.name if item else 'Unknown Material',
            'quantity_used': material.quantity_used
        })
    
    return jsonify(result)

@production_bp.route('/api/warehouses', methods=['GET'])
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
            'is_active': warehouse.is_active
        })
    
    return jsonify(result)

@production_bp.route('/api/production/packaging-orders', methods=['GET'])
@login_required
def get_packaging_orders():
    """Get all packaging orders"""
    # Get query parameters for filtering
    status = request.args.get('status')
    packaging_type = request.args.get('packaging_type')
    scheduled_date = request.args.get('scheduled_date')
    
    # Build query
    query = PackagingOrder.query
    
    if status:
        query = query.filter(PackagingOrder.status == status)
    
    if packaging_type:
        query = query.filter(PackagingOrder.packaging_type == packaging_type)
    
    if scheduled_date:
        scheduled_date_obj = datetime.fromisoformat(scheduled_date)
        query = query.filter(PackagingOrder.scheduled_date >= scheduled_date_obj,
                            PackagingOrder.scheduled_date < scheduled_date_obj + timedelta(days=1))
    
    # Execute query
    orders = query.all()
    result = []
    
    for order in orders:
        batch = Batch.query.get(order.batch_id)
        product = Item.query.get(batch.item_id) if batch else None
        packaging_line = PackagingLine.query.get(order.packaging_line_id) if order.packaging_line_id else None
        
        result.append({
            'id': order.id,
            'batch_id': order.batch_id,
            'batch_lot_number': batch.lot_number if batch else None,
            'product_id': batch.item_id if batch else None,
            'product_name': product.name if product else 'Unknown Product',
            'packaging_type': order.packaging_type,
            'quantity': order.quantity,
            'status': order.status,
            'packaging_line_id': order.packaging_line_id,
            'packaging_line_name': packaging_line.name if packaging_line else None,
            'scheduled_date': order.scheduled_date.isoformat() if order.scheduled_date else None,
            'completed_date': order.completed_date.isoformat() if order.completed_date else None,
            'created_at': order.created_at.isoformat()
        })
    
    return jsonify(result)

@production_bp.route('/api/categories', methods=['GET'])
@login_required
def get_categories():
    """Get categories based on type"""
    category_type = request.args.get('type')
    
    if category_type:
        categories = Category.query.filter_by(category_type=category_type).all()
    else:
        categories = Category.query.all()
    
    result = []
    for category in categories:
        result.append({
            'id': category.id,
            'name': category.name,
            'description': category.description,
            'category_type': category.category_type
        })
    
    return jsonify(result)

@production_bp.route('/api/items', methods=['POST'])
@login_required
def create_item():
    """Create a new item"""
    data = request.get_json()
    
    # Validate required fields
    if not data.get('name') or not data.get('sku') or not data.get('category_id'):
        return jsonify({'message': 'Missing required fields: name, sku, or category_id'}), 400
    
    # Check if SKU already exists
    existing_item = Item.query.filter_by(sku=data['sku']).first()
    if existing_item:
        return jsonify({'message': 'An item with this SKU already exists'}), 400
    
    # Create new item
    item = Item(
        name=data['name'],
        sku=data['sku'],
        category_id=data['category_id'],
        description=data.get('description', ''),
        unit_of_measure=data.get('unit_of_measure', ''),
        cost=data.get('cost', 0),
        price=data.get('price', 0),
        reorder_level=data.get('reorder_level', 0)
    )
    
    db.session.add(item)
    db.session.commit()
    
    return jsonify({
        'id': item.id,
        'name': item.name,
        'sku': item.sku,
        'category_id': item.category_id,
        'message': 'Item created successfully'
    }), 201


# Add these imports if not already present
from sqlalchemy import func, desc
from datetime import datetime, timedelta
import json

# Add these API endpoints to support the dashboard

@production_bp.route('/api/production/stats', methods=['GET'])
@login_required
def get_production_stats():
    """Get production statistics for the dashboard"""
    try:
        # Count production orders
        production_orders_count = ProductionOrder.query.count()
        
        # Count batches
        batches_count = Batch.query.count()
        
        # Count BOMs
        boms_count = BOM.query.count()
        
        # Count packaging orders
        packaging_orders_count = PackagingOrder.query.count()
        
        return jsonify({
            'productionOrders': production_orders_count,
            'batches': batches_count,
            'boms': boms_count,
            'packagingOrders': packaging_orders_count
        })
    
    except Exception as e:
        current_app.logger.error(f"Error fetching production stats: {str(e)}")
        return jsonify({'message': f'Error fetching production stats: {str(e)}'}), 500

@production_bp.route('/api/production/orders/status', methods=['GET'])
@login_required
def get_production_orders_status():
    """Get production orders count by status"""
    try:
        # Count orders by status
        planned_count = ProductionOrder.query.filter_by(status='Planned').count()
        in_progress_count = ProductionOrder.query.filter_by(status='InProgress').count()
        completed_count = ProductionOrder.query.filter_by(status='Completed').count()
        cancelled_count = ProductionOrder.query.filter_by(status='Cancelled').count()
        on_hold_count = ProductionOrder.query.filter_by(status='OnHold').count()
        
        return jsonify({
            'Planned': planned_count,
            'InProgress': in_progress_count,
            'Completed': completed_count,
            'Cancelled': cancelled_count,
            'OnHold': on_hold_count
        })
    
    except Exception as e:
        current_app.logger.error(f"Error fetching production orders status: {str(e)}")
        return jsonify({'message': f'Error fetching production orders status: {str(e)}'}), 500

@production_bp.route('/api/production/activities/recent', methods=['GET'])
@login_required
def get_recent_activities():
    """Get recent production activities"""
    try:
        # Get recent production orders
        recent_orders = ProductionOrder.query.order_by(desc(ProductionOrder.created_at)).limit(5).all()
        
        # Get recent batches
        recent_batches = Batch.query.order_by(desc(Batch.production_date)).limit(5).all()
        
        # Get recent QC tests
        recent_tests = QCTest.query.order_by(desc(QCTest.created_at)).limit(5).all()
        
        # Get recent packaging orders
        recent_packaging = PackagingOrder.query.order_by(desc(PackagingOrder.created_at)).limit(5).all()
        
        activities = []
        
        # Add production orders to activities
        for order in recent_orders:
            product = Item.query.get(order.product_id)
            activities.append({
                'id': f'order_{order.id}',
                'activity_type': 'إنشاء أمر إنتاج',
                'product_name': product.name if product else 'منتج غير معروف',
                'batch_number': None,
                'timestamp': order.created_at.isoformat(),
                'status': order.status
            })
        
        # Add batches to activities
        for batch in recent_batches:
            item = Item.query.get(batch.item_id)
            activities.append({
                'id': f'batch_{batch.id}',
                'activity_type': 'إنشاء دفعة إنتاج',
                'product_name': item.name if item else 'منتج غير معروف',
                'batch_number': batch.lot_number,
                'timestamp': batch.production_date.isoformat() if batch.production_date else datetime.now().isoformat(),
                'status': batch.status
            })
        
        # Add QC tests to activities
        for test in recent_tests:
            batch = Batch.query.get(test.batch_id)
            item = Item.query.get(batch.item_id) if batch else None
            activities.append({
                'id': f'test_{test.id}',
                'activity_type': 'اختبار جودة',
                'product_name': item.name if item else 'منتج غير معروف',
                'batch_number': batch.lot_number if batch else None,
                'timestamp': test.created_at.isoformat(),
                'status': test.status
            })
        
        # Add packaging orders to activities
        for packaging in recent_packaging:
            batch = Batch.query.get(packaging.batch_id)
            item = Item.query.get(batch.item_id) if batch else None
            activities.append({
                'id': f'packaging_{packaging.id}',
                'activity_type': 'أمر تعبئة',
                'product_name': item.name if item else 'منتج غير معروف',
                'batch_number': batch.lot_number if batch else None,
                'timestamp': packaging.created_at.isoformat(),
                'status': packaging.status
            })
        
        # Sort activities by timestamp (newest first)
        activities.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # Return only the 10 most recent activities
        return jsonify(activities[:10])
    
    except Exception as e:
        current_app.logger.error(f"Error fetching recent activities: {str(e)}")
        return jsonify({'message': f'Error fetching recent activities: {str(e)}'}), 500

@production_bp.route('/api/production/lines/efficiency', methods=['GET'])
@login_required
def get_production_lines_efficiency():
    """Get production lines with their efficiency metrics"""
    try:
        lines = ProductionLine.query.all()
        result = []
        
        for line in lines:
            # Get completed orders for this line in the last 30 days
            thirty_days_ago = datetime.now() - timedelta(days=30)
            completed_orders = ProductionOrder.query.filter(
                ProductionOrder.production_line_id == line.id,
                ProductionOrder.status == 'Completed',
                ProductionOrder.actual_end >= thirty_days_ago
            ).all()
            
            # Calculate efficiency based on actual vs scheduled time
            total_efficiency = 0
            order_count = len(completed_orders)
            
            for order in completed_orders:
                if order.scheduled_end and order.actual_end and order.scheduled_start and order.actual_start:
                    scheduled_duration = (order.scheduled_end - order.scheduled_start).total_seconds() / 3600  # in hours
                    actual_duration = (order.actual_end - order.actual_start).total_seconds() / 3600  # in hours
                    
                    if scheduled_duration > 0:
                        # Efficiency = scheduled time / actual time (capped at 100%)
                        efficiency = min(100, (scheduled_duration / actual_duration) * 100) if actual_duration > 0 else 100
                        total_efficiency += efficiency
            
            # Calculate average efficiency
            avg_efficiency = round(total_efficiency / order_count) if order_count > 0 else 0
            
            result.append({
                'id': line.id,
                'name': line.name,
                'capacity_per_hour': line.capacity_per_hour,
                'is_active': line.is_active,
                'efficiency': avg_efficiency,
                'orders_count': order_count
            })
        
        return jsonify(result)
    
    except Exception as e:
        current_app.logger.error(f"Error fetching production lines efficiency: {str(e)}")
        return jsonify({'message': f'Error fetching production lines efficiency: {str(e)}'}), 500

@production_bp.route('/api/production/quality/stats', methods=['GET'])
@login_required
def get_quality_stats():
    """Get quality control statistics"""
    try:
        # Get all QC tests
        all_tests = QCTest.query.all()
        
        # Count tests by status
        passed_tests = sum(1 for test in all_tests if test.status == 'Passed')
        failed_tests = sum(1 for test in all_tests if test.status == 'Failed')
        pending_tests = sum(1 for test in all_tests if test.status == 'Pending')
        total_tests = len(all_tests)
        
        # Calculate test pass rate
        test_pass_rate = round((passed_tests / total_tests) * 100) if total_tests > 0 else 0
        
        # Calculate test completion rate
        completed_tests = passed_tests + failed_tests
        test_completion_rate = round((completed_tests / total_tests) * 100) if total_tests > 0 else 0
        
        # Get batches with QC status
        passed_batches = Batch.query.filter_by(status='QCPassed').count()
        failed_batches = Batch.query.filter_by(status='QCFailed').count()
        pending_batches = Batch.query.filter_by(status='QCPending').count()
        total_batches = passed_batches + failed_batches + pending_batches
        
        # Calculate batch pass rate
        pass_rate = round((passed_batches / total_batches) * 100) if total_batches > 0 else 0
        
        # Calculate batch rejection rate
        batch_rejection_rate = round((failed_batches / total_batches) * 100) if total_batches > 0 else 0
        
        # Get common issues (from test results)
        common_issues = []
        try:
            # Get failed test results
            test_results = QCTestResult.query.filter_by(is_passed=False).all()
            
            # Count occurrences of each parameter
            issue_counts = {}
            for result in test_results:
                if result.parameter_name not in issue_counts:
                    issue_counts[result.parameter_name] = 0
                issue_counts[result.parameter_name] += 1
            
            # Convert to list and sort by count
            common_issues = [
                {"name": param, "count": count}
                for param, count in issue_counts.items()
            ]
            common_issues.sort(key=lambda x: x["count"], reverse=True)
            
            # Take top 3
            common_issues = common_issues[:3]
        except:
            # If there's an error getting common issues, just return an empty list
            common_issues = []
        
        return jsonify({
            'passRate': pass_rate,
            'passedTests': passed_tests,
            'failedTests': failed_tests,
            'totalTests': total_tests,
            'passedBatches': passed_batches,
            'failedBatches': failed_batches,
            'pendingBatches': pending_batches,
            'testPassRate': test_pass_rate,
            'testCompletionRate': test_completion_rate,
            'batchRejectionRate': batch_rejection_rate,
            'commonIssues': common_issues,
            'lastUpdated': datetime.now().isoformat()
        })
    
    except Exception as e:
        current_app.logger.error(f"Error fetching quality stats: {str(e)}")
        return jsonify({'message': f'Error fetching quality stats: {str(e)}'}), 500


@production_bp.route('/api/production/lines', methods=['POST'])
@login_required
def create_production_line():
    """Create a new production line"""
    data = request.get_json()
    
    # Validate required fields
    if not data.get('name'):
        return jsonify({'message': 'Missing required field: name'}), 400
    
    # Create new production line
    line = ProductionLine(
        name=data['name'],
        description=data.get('description', ''),
        capacity_per_hour=data.get('capacity_per_hour', 0),
        is_active=data.get('is_active', True)
    )
    
    db.session.add(line)
    db.session.commit()
    
    return jsonify({
        'id': line.id,
        'name': line.name,
        'description': line.description,
        'capacity_per_hour': line.capacity_per_hour,
        'is_active': line.is_active,
        'created_at': line.created_at.isoformat(),
        'message': 'Production line created successfully'
    }), 201

@production_bp.route('/api/production/lines/<int:line_id>', methods=['PUT'])
@login_required
def update_production_line(line_id):
    """Update a production line"""
    line = ProductionLine.query.get_or_404(line_id)
    data = request.get_json()
    
    # Update fields if provided
    if 'name' in data:
        line.name = data['name']
    
    if 'description' in data:
        line.description = data['description']
    
    if 'capacity_per_hour' in data:
        line.capacity_per_hour = data['capacity_per_hour']
    
    if 'is_active' in data:
        line.is_active = data['is_active']
    
    db.session.commit()
    
    return jsonify({
        'id': line.id,
        'name': line.name,
        'description': line.description,
        'capacity_per_hour': line.capacity_per_hour,
        'is_active': line.is_active,
        'updated_at': datetime.now().isoformat(),
        'message': 'Production line updated successfully'
    })

@production_bp.route('/api/production/lines/<int:line_id>', methods=['DELETE'])
@login_required
def delete_production_line(line_id):
    """Delete a production line"""
    line = ProductionLine.query.get_or_404(line_id)
    
    # Check if there are any production orders using this line
    orders_using_line = ProductionOrder.query.filter_by(production_line_id=line_id).count()
    if orders_using_line > 0:
        return jsonify({'message': 'Cannot delete production line that is used by production orders'}), 400
    
    db.session.delete(line)
    db.session.commit()
    
    return jsonify({'message': 'Production line deleted successfully'})



@production_bp.route('/api/production/activities', methods=['GET'])
@login_required
def get_production_activities():
    """Get all production activities with filtering options"""
    try:
        # Get query parameters for filtering
        activity_type = request.args.get('type')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        status = request.args.get('status')
        
        # Initialize activities list
        activities = []
        
        # Get production orders
        orders_query = ProductionOrder.query
        if status:
            orders_query = orders_query.filter(ProductionOrder.status == status)
        if start_date:
            start_datetime = datetime.fromisoformat(start_date)
            orders_query = orders_query.filter(ProductionOrder.created_at >= start_datetime)
        if end_date:
            end_datetime = datetime.fromisoformat(end_date)
            orders_query = orders_query.filter(ProductionOrder.created_at <= end_datetime)
        
        orders = orders_query.order_by(desc(ProductionOrder.created_at)).all()
        
        # Get batches
        batches_query = Batch.query
        if status:
            batches_query = batches_query.filter(Batch.status == status)
        if start_date:
            batches_query = batches_query.filter(Batch.production_date >= start_datetime)
        if end_date:
            batches_query = batches_query.filter(Batch.production_date <= end_datetime)
        
        batches = batches_query.order_by(desc(Batch.production_date)).all()
        
        # Get QC tests
        tests_query = QCTest.query
        if status:
            tests_query = tests_query.filter(QCTest.status == status)
        if start_date:
            tests_query = tests_query.filter(QCTest.created_at >= start_datetime)
        if end_date:
            tests_query = tests_query.filter(QCTest.created_at <= end_datetime)
        
        tests = tests_query.order_by(desc(QCTest.created_at)).all()
        
        # Get packaging orders
        packaging_query = PackagingOrder.query
        if status:
            packaging_query = packaging_query.filter(PackagingOrder.status == status)
        if start_date:
            packaging_query = packaging_query.filter(PackagingOrder.created_at >= start_datetime)
        if end_date:
            packaging_query = packaging_query.filter(PackagingOrder.created_at <= end_datetime)
        
        packaging_orders = packaging_query.order_by(desc(PackagingOrder.created_at)).all()
        
        # Add production orders to activities if type filter matches or not specified
        if not activity_type or activity_type == 'order':
            for order in orders:
                product = Item.query.get(order.product_id)
                activities.append({
                    'id': f'order_{order.id}',
                    'activity_type': 'إنشاء أمر إنتاج',
                    'product_name': product.name if product else 'منتج غير معروف',
                    'product_id': order.product_id,
                    'batch_number': None,
                    'quantity': order.quantity,
                    'timestamp': order.created_at.isoformat(),
                    'status': order.status,
                    'details_url': f'/production-orders?id={order.id}',
                    'created_by': order.created_by
                })
        
        # Add batches to activities if type filter matches or not specified
        if not activity_type or activity_type == 'batch':
            for batch in batches:
                item = Item.query.get(batch.item_id)
                activities.append({
                    'id': f'batch_{batch.id}',
                    'activity_type': 'إنشاء دفعة إنتاج',
                    'product_name': item.name if item else 'منتج غير معروف',
                    'product_id': batch.item_id,
                    'batch_number': batch.lot_number,
                    'quantity': batch.quantity,
                    'timestamp': batch.production_date.isoformat() if batch.production_date else datetime.now().isoformat(),
                    'status': batch.status,
                    'details_url': f'/production-batches?id={batch.id}',
                    'expiry_date': batch.expiry_date.isoformat() if batch.expiry_date else None
                })
        
        # Add QC tests to activities if type filter matches or not specified
        if not activity_type or activity_type == 'qc':
            for test in tests:
                batch = Batch.query.get(test.batch_id)
                item = Item.query.get(batch.item_id) if batch else None
                activities.append({
                    'id': f'test_{test.id}',
                    'activity_type': 'اختبار جودة',
                    'product_name': item.name if item else 'منتج غير معروف',
                    'product_id': batch.item_id if batch else None,
                    'batch_number': batch.lot_number if batch else None,
                    'timestamp': test.created_at.isoformat(),
                    'status': test.status,
                    'details_url': f'/quality-control?test_id={test.id}',
                    'inspector_id': test.inspector_id,
                    'completed_at': test.completed_at.isoformat() if test.completed_at else None
                })
        
        # Add packaging orders to activities if type filter matches or not specified
        if not activity_type or activity_type == 'packaging':
            for packaging in packaging_orders:
                batch = Batch.query.get(packaging.batch_id)
                item = Item.query.get(batch.item_id) if batch else None
                activities.append({
                    'id': f'packaging_{packaging.id}',
                    'activity_type': 'أمر تعبئة',
                    'product_name': item.name if item else 'منتج غير معروف',
                    'product_id': batch.item_id if batch else None,
                    'batch_number': batch.lot_number if batch else None,
                    'quantity': packaging.quantity,
                    'timestamp': packaging.created_at.isoformat(),
                    'status': packaging.status,
                    'details_url': f'/packaging-management?id={packaging.id}',
                    'packaging_type': packaging.packaging_type,
                    'scheduled_date': packaging.scheduled_date.isoformat() if packaging.scheduled_date else None
                })
        
        # Sort activities by timestamp (newest first)
        activities.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return jsonify(activities)
    
    except Exception as e:
        current_app.logger.error(f"Error fetching production activities: {str(e)}")
        return jsonify({'message': f'Error fetching production activities: {str(e)}'}), 500
@production_bp.route('/api/production/orders/status-counts', methods=['GET'])
@login_required
def get_order_status_counts():
    """Get counts of production orders by status"""
    # Count orders by status
    planned_count = ProductionOrder.query.filter_by(status='Planned').count()
    in_progress_count = ProductionOrder.query.filter_by(status='InProgress').count()
    completed_count = ProductionOrder.query.filter_by(status='Completed').count()
    cancelled_count = ProductionOrder.query.filter_by(status='Cancelled').count()
    
    return jsonify({
        'Planned': planned_count,
        'InProgress': in_progress_count,
        'Completed': completed_count,
        'Cancelled': cancelled_count
    })
    
# Production Stages Management
@production_bp.route('/api/production/stages', methods=['GET'])
@login_required
def get_production_stages():
    """Get all production stages"""
    try:
        stages = ProductionStep.query.order_by(ProductionStep.sequence_number).all()
        result = []
        
        for stage in stages:
            result.append({
                'id': stage.id,
                'name': stage.name,
                'description': stage.description,
                'standard_duration': stage.standard_duration,
                'sequence_number': stage.sequence_number,
                'is_active': stage.is_active if hasattr(stage, 'is_active') else True,
                'created_at': stage.created_at.isoformat() if hasattr(stage, 'created_at') else None
            })
        
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error fetching production stages: {str(e)}")
        return jsonify({'message': f'Error fetching production stages: {str(e)}'}), 500

@production_bp.route('/api/production/stages', methods=['POST'])
@login_required
def create_production_stage():
    """Create a new production stage"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('name'):
            return jsonify({'message': 'Missing required field: name'}), 400
        
        # Get the highest sequence number to add the new stage at the end
        highest_seq = db.session.query(func.max(ProductionStep.sequence_number)).scalar() or 0
        
        # Create new production stage
        stage = ProductionStep(
            name=data['name'],
            description=data.get('description', ''),
            standard_duration=data.get('standard_duration', 0),
            sequence_number=highest_seq + 1,
            is_active=data.get('is_active', True) if hasattr(ProductionStep, 'is_active') else None
        )
        
        db.session.add(stage)
        db.session.commit()
        
        return jsonify({
            'id': stage.id,
            'name': stage.name,
            'description': stage.description,
            'standard_duration': stage.standard_duration,
            'sequence_number': stage.sequence_number,
            'is_active': stage.is_active if hasattr(stage, 'is_active') else True,
            'message': 'Production stage created successfully'
        }), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating production stage: {str(e)}")
        return jsonify({'message': f'Error creating production stage: {str(e)}'}), 500

@production_bp.route('/api/production/stages/<int:stage_id>', methods=['PUT'])
@login_required
def update_production_stage(stage_id):
    """Update a production stage"""
    try:
        stage = ProductionStep.query.get_or_404(stage_id)
        data = request.get_json()
        
        # Update fields if provided
        if 'name' in data:
            stage.name = data['name']
        
        if 'description' in data:
            stage.description = data['description']
        
        if 'standard_duration' in data:
            stage.standard_duration = data['standard_duration']
        
        if 'is_active' in data and hasattr(stage, 'is_active'):
            stage.is_active = data['is_active']
        
        db.session.commit()
        
        return jsonify({
            'id': stage.id,
            'name': stage.name,
            'description': stage.description,
            'standard_duration': stage.standard_duration,
            'sequence_number': stage.sequence_number,
            'is_active': stage.is_active if hasattr(stage, 'is_active') else True,
            'message': 'Production stage updated successfully'
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating production stage: {str(e)}")
        return jsonify({'message': f'Error updating production stage: {str(e)}'}), 500

@production_bp.route('/api/production/stages/<int:stage_id>', methods=['DELETE'])
@login_required
def delete_production_stage(stage_id):
    """Delete a production stage"""
    try:
        stage = ProductionStep.query.get_or_404(stage_id)
        
        # Check if there are any production step records using this stage
        step_records = ProductionStepRecord.query.filter_by(step_id=stage_id).count()
        if step_records > 0:
            return jsonify({
                'message': 'Cannot delete stage that is used in production records. Consider deactivating it instead.'
            }), 400
        
        # Get the sequence number for reordering
        deleted_seq = stage.sequence_number
        
        # Delete the stage
        db.session.delete(stage)
        
        # Reorder the remaining stages
        stages_to_update = ProductionStep.query.filter(
            ProductionStep.sequence_number > deleted_seq
        ).all()
        
        for s in stages_to_update:
            s.sequence_number -= 1
        
        db.session.commit()
        
        return jsonify({'message': 'Production stage deleted successfully'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting production stage: {str(e)}")
        return jsonify({'message': f'Error deleting production stage: {str(e)}'}), 500

@production_bp.route('/api/production/stages/reorder', methods=['POST'])
@login_required
def reorder_production_stages():
    """Reorder production stages"""
    try:
        data = request.get_json()
        
        if not data or not isinstance(data, list):
            return jsonify({'message': 'Invalid data format. Expected a list of stage IDs.'}), 400
        
        # Validate that all IDs exist
        for i, stage_id in enumerate(data):
            stage = ProductionStep.query.get(stage_id)
            if not stage:
                return jsonify({'message': f'Stage with ID {stage_id} not found'}), 404
            
            # Update sequence number
            stage.sequence_number = i + 1
        
        db.session.commit()
        
        return jsonify({'message': 'Production stages reordered successfully'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error reordering production stages: {str(e)}")
        return jsonify({'message': f'Error reordering production stages: {str(e)}'}), 500

@production_bp.route('/api/products/<int:product_id>/has-bom', methods=['GET'])
def check_product_has_bom(product_id):
    try:
        # Query your database to check if the product has BOM entries
        bom_exists = db.session.query(BOM).filter_by(product_id=product_id).first() is not None
        
        return jsonify({
            'has_bom': bom_exists
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Helper function for generating PDFs
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

########################################################################
########################################################################
########################################################################
########################################################################
########################################################################
########################################################################
########################################################################
########################################################################
########################################################################
########################################################################
########################################################################
########################################################################
########################################################################
########################################################################
########################################################################
########################################################################
########################################################################

# Production Dashboard
@production_bp.route('/production-dashboard')
@login_required
def production_dashboard():
    """Render the production dashboard page"""
    return render_template('production/production_dashboard.html')

# Production Order Management Page
@production_bp.route('/production-orders')
@login_required
def production_orders_page():
    """Render the production orders management page"""
    return render_template('production/production_orders.html')

# Batch Management Page
@production_bp.route('/production-batches')
@login_required
def production_batches_page():
    """Render the batch management page"""
    return render_template('production/production_batches.html')

# Quality Control Page
@production_bp.route('/quality-control')
@login_required
def quality_control_page():
    """Render the quality control page"""
    return render_template('production/quality_control.html')

# Packaging Management Page
@production_bp.route('/packaging-management')
@login_required
def packaging_management_page():
    """Render the packaging management page"""
    return render_template('production/packaging_management.html')          

@production_bp.route('/production-lines')
@login_required
def production_lines_page():
    """Render the production lines management page"""
    return render_template('production/production_lines.html')

@production_bp.route('/production-management')
@login_required
def production_management_page():
    """Render the production management landing page"""
    return render_template('production/production_management.html')


@production_bp.route('/production-activities')
@login_required
def production_activities_page():
    """Render the production activities tracking page"""
    return render_template('production/production_activities.html')

@production_bp.route('/production-stages')
@login_required
def production_stages_page():
    """Render the production stages management page"""
    return render_template('production/production_stages.html')
