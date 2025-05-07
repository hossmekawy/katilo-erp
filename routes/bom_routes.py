from flask import Blueprint, request, jsonify, render_template, abort, current_app, send_file, flash, redirect, url_for
from flask_login import current_user, login_required
import sys
import os
import uuid
import pandas as pd
import numpy as np
from werkzeug.utils import secure_filename

# Add the parent directory to sys.path to allow importing from the root directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import from the models_helper module
from models_helper import db, BOM, BOMDetail, Item, Inventory, InventoryTransaction, Warehouse, Category
import os
import tempfile
import subprocess
from datetime import datetime


# Create a Blueprint for BOM routes
bom_bp = Blueprint('bom', __name__)

# BOM Routes
@bom_bp.route('/api/bom', methods=['GET'])
@login_required
def get_boms():
    boms = BOM.query.all()
    result = []
    for bom in boms:
        # Get the final product name and category
        final_product = Item.query.get(bom.final_product_id)
        final_product_category = Category.query.get(final_product.category_id) if final_product and final_product.category_id else None

        result.append({
            'id': bom.id,
            'final_product_id': bom.final_product_id,
            'final_product_name': final_product.name if final_product else 'Unknown Product',
            'final_product_category_id': final_product.category_id if final_product else None,
            'final_product_category_name': final_product_category.name if final_product_category else 'Uncategorized',
            'final_product_category_type': final_product_category.category_type if final_product_category else None,
            'description': bom.description,
            'created_at': bom.created_at.isoformat(),
            'updated_at': bom.updated_at.isoformat()
        })
    return jsonify(result)

@bom_bp.route('/api/bom/<int:id>', methods=['GET'])
@login_required
def get_bom(id):
    bom = BOM.query.get_or_404(id)
    final_product = Item.query.get(bom.final_product_id)
    final_product_category = Category.query.get(final_product.category_id) if final_product and final_product.category_id else None

    # Get all details for this BOM
    details = []
    total_cost = 0

    # Track costs by individual component
    component_costs = []

    for detail in bom.details:
        component = Item.query.get(detail.component_item_id)
        component_category = Category.query.get(component.category_id) if component and component.category_id else None

        # Calculate component cost
        component_cost = component.cost * detail.quantity_required if component else 0
        total_cost += component_cost

        # Add to component costs list
        component_costs.append({
            'component_id': detail.component_item_id,
            'component_name': component.name if component else 'Unknown Component',
            'cost': component_cost,
            'percentage': 0  # Will calculate after we have total
        })

        details.append({
            'id': detail.id,
            'component_item_id': detail.component_item_id,
            'component_name': component.name if component else 'Unknown Component',
            'component_category_id': component.category_id if component else None,
            'component_category_name': component_category.name if component_category else 'Uncategorized',
            'quantity_required': detail.quantity_required,
            'unit_of_measure': detail.unit_of_measure,
            'component_cost': component.cost if component else 0,
            'total_component_cost': component_cost
        })

    # Calculate percentages for component costs
    if total_cost > 0:
        for cost_item in component_costs:
            cost_item['percentage'] = (cost_item['cost'] / total_cost * 100)

    # Sort component costs by percentage (descending)
    component_costs.sort(key=lambda x: x['percentage'], reverse=True)

    # Calculate selling price and profit
    selling_price = final_product.price if final_product else 0
    profit = selling_price - total_cost
    profit_margin = (profit / selling_price * 100) if selling_price > 0 else 0

    # Count how many times this BOM has been produced
    production_count = 0
    if final_product:
        production_count = InventoryTransaction.query.filter_by(
            item_id=final_product.id,
            transaction_type='IN',
            reference='Production from BOM'
        ).count()

    return jsonify({
        'id': bom.id,
        'final_product_id': bom.final_product_id,
        'final_product_name': final_product.name if final_product else 'Unknown Product',
        'final_product_category_id': final_product.category_id if final_product else None,
        'final_product_category_name': final_product_category.name if final_product_category else 'Uncategorized',
        'description': bom.description,
        'created_at': bom.created_at.isoformat(),
        'updated_at': bom.updated_at.isoformat(),
        'details': details,
        'total_cost': total_cost,
        'selling_price': selling_price,
        'profit': profit,
        'profit_margin': profit_margin,
        'production_count': production_count,
        'component_costs': component_costs  # New field with component-based cost breakdown
    })


@bom_bp.route('/api/bom/categories', methods=['GET'])
@login_required
def get_item_categories():
    """Get items grouped by their categories for BOM management"""
    items = Item.query.join(Category, isouter=True).all()

    # Group items by category
    categorized_items = {}
    for item in items:
        category_name = item.category.name if item.category else "Uncategorized"
        category_type = item.category.category_type if item.category else None

        if category_name not in categorized_items:
            categorized_items[category_name] = {
                'items': [],
                'category_type': category_type
            }

        categorized_items[category_name]['items'].append({
            'id': item.id,
            'name': item.name,
            'sku': item.sku,
            'unit_of_measure': item.unit_of_measure,
            'category_id': item.category_id
        })

    # Convert to list format for the frontend
    result = [
        {
            'category_name': category,
            'category_type': data['category_type'],
            'items': data['items']
        }
        for category, data in categorized_items.items()
    ]

    return jsonify(result)

@bom_bp.route('/api/bom/final-products', methods=['GET'])
@login_required
def get_final_products():
    """Get only items categorized as final products"""
    # Join Item with Category and filter by category_type
    items = Item.query.all()

    # Filter for final products based on category type
    final_products = []
    for item in items:
        category = Category.query.get(item.category_id) if item.category_id else None
        if category and hasattr(category, 'category_type') and category.category_type == 'FinalProduct':
            final_products.append(item)

    # If no final products found, return all items as fallback
    if not final_products:
        final_products = items

    result = [{
        'id': item.id,
        'name': item.name,
        'sku': item.sku,
        'category_id': item.category_id,
        'category_name': item.category.name if item.category else 'Uncategorized'
    } for item in final_products]

    return jsonify(result)

@bom_bp.route('/api/bom/raw-materials', methods=['GET'])
@login_required
def get_raw_materials():
    """Get only items categorized as raw materials"""
    # Join Item with Category and filter by category_type
    raw_materials = Item.query.join(
        Category,
        Item.category_id == Category.id
    ).filter(
        Category.category_type == 'RawMaterial'
    ).all()

    result = [{
        'id': item.id,
        'name': item.name,
        'sku': item.sku,
        'category_id': item.category_id,
        'category_name': item.category.name if item.category else 'Uncategorized'
    } for item in raw_materials]

    return jsonify(result)

@bom_bp.route('/api/bom/packaging-materials', methods=['GET'])
@login_required
def get_packaging_materials():
    """Get only items categorized as packaging materials"""
    # Join Item with Category and filter by category_type
    packaging_materials = Item.query.join(
        Category,
        Item.category_id == Category.id
    ).filter(
        Category.category_type == 'Packaging'
    ).all()

    result = [{
        'id': item.id,
        'name': item.name,
        'sku': item.sku,
        'category_id': item.category_id,
        'category_name': item.category.name if item.category else 'Uncategorized'
    } for item in packaging_materials]

    return jsonify(result)

@bom_bp.route('/api/bom/intermediate-products', methods=['GET'])
@login_required
def get_intermediate_products():
    """Get only items categorized as intermediate products"""
    # Join Item with Category and filter by category_type
    items = Item.query.all()

    # Filter for intermediate products based on category type
    intermediate_products = []
    for item in items:
        category = Category.query.get(item.category_id) if item.category_id else None
        if category and hasattr(category, 'category_type') and category.category_type == 'IntermediateProduct':
            intermediate_products.append(item)

    result = [{
        'id': item.id,
        'name': item.name,
        'sku': item.sku,
        'category_id': item.category_id,
        'category_name': item.category.name if item.category else 'Uncategorized'
    } for item in intermediate_products]

    return jsonify(result)

@bom_bp.route('/api/bom', methods=['POST'])
@login_required
def create_bom():
    data = request.get_json()

    # Validate required fields
    if not data.get('final_product_id'):
        return jsonify({'message': 'Missing required field: final_product_id'}), 400

    # Check if the final product exists
    final_product = Item.query.get(data['final_product_id'])
    if not final_product:
        return jsonify({'message': 'Final product not found'}), 404

    # Check if the item is categorized as a final product
    if final_product.category and hasattr(final_product.category, 'category_type'):
        if final_product.category.category_type != 'FinalProduct' and final_product.category.category_type != 'IntermediateProduct':
            return jsonify({'message': 'Selected item must be categorized as a final product or intermediate product'}), 400

    # Check if a BOM already exists for this product
    existing_bom = BOM.query.filter_by(final_product_id=data['final_product_id']).first()
    if existing_bom:
        return jsonify({'message': 'A BOM already exists for this product'}), 400

    # Create new BOM
    bom = BOM(
        final_product_id=data['final_product_id'],
        description=data.get('description', '')
    )

    db.session.add(bom)
    db.session.commit()

    # Initialize the cost calculation (will be 0 since no components yet)
    update_item_cost_from_bom(bom.id)


    # Get category information for response
    final_product_category = Category.query.get(final_product.category_id) if final_product.category_id else None

    return jsonify({
        'id': bom.id,
        'final_product_id': bom.final_product_id,
        'final_product_name': final_product.name,
        'final_product_category_id': final_product.category_id,
        'final_product_category_name': final_product_category.name if final_product_category else 'Uncategorized',
        'final_product_category_type': final_product_category.category_type if final_product_category else None,
        'description': bom.description,
        'created_at': bom.created_at.isoformat(),
        'updated_at': bom.updated_at.isoformat()
    }), 201

@bom_bp.route('/api/bom/<int:id>', methods=['PUT'])
@login_required
def update_bom(id):
    bom = BOM.query.get_or_404(id)
    data = request.get_json()

    # Update description if provided
    if 'description' in data:
        bom.description = data['description']

    # Update final product if provided
    if 'final_product_id' in data:
        # Check if the final product exists
        final_product = Item.query.get(data['final_product_id'])
        if not final_product:
            return jsonify({'message': 'Final product not found'}), 404

        # Check if the item is categorized as a final product
        if final_product.category and hasattr(final_product.category, 'category_type'):
            if final_product.category.category_type != 'FinalProduct' and final_product.category.category_type != 'IntermediateProduct':
                return jsonify({'message': 'Selected item must be categorized as a final product or intermediate product'}), 400

        # Check if another BOM already uses this product
        existing_bom = BOM.query.filter_by(final_product_id=data['final_product_id']).first()
        if existing_bom and existing_bom.id != id:
            return jsonify({'message': 'A BOM already exists for this product'}), 400

        bom.final_product_id = data['final_product_id']

    db.session.commit()

    update_item_cost_from_bom(id)

    # Get updated product and category information
    final_product = Item.query.get(bom.final_product_id)
    final_product_category = Category.query.get(final_product.category_id) if final_product and final_product.category_id else None

    return jsonify({
        'id': bom.id,
        'final_product_id': bom.final_product_id,
        'final_product_name': final_product.name if final_product else 'Unknown Product',
        'final_product_category_id': final_product.category_id if final_product else None,
        'final_product_category_name': final_product_category.name if final_product_category else 'Uncategorized',
        'final_product_category_type': final_product_category.category_type if final_product_category else None,
        'description': bom.description,
        'updated_at': bom.updated_at.isoformat()
    })

@bom_bp.route('/api/bom/<int:id>', methods=['DELETE'])
@login_required
def delete_bom(id):
    bom = BOM.query.get_or_404(id)

    # Delete all BOM details first
    BOMDetail.query.filter_by(bom_id=id).delete()

    # Delete the BOM
    db.session.delete(bom)
    db.session.commit()

    return '', 204

# BOM Detail Routes
@bom_bp.route('/api/bom/<int:bom_id>/details', methods=['GET'])
@login_required
def get_bom_details(bom_id):
    # Check if BOM exists
    bom = BOM.query.get_or_404(bom_id)

    details = BOMDetail.query.filter_by(bom_id=bom_id).all()
    result = []

    for detail in details:
        component = Item.query.get(detail.component_item_id)
        component_category = Category.query.get(component.category_id) if component and component.category_id else None

        result.append({
            'id': detail.id,
            'bom_id': detail.bom_id,
            'component_item_id': detail.component_item_id,
            'component_name': component.name if component else 'Unknown Component',
            'component_category_id': component.category_id if component else None,
            'component_category_name': component_category.name if component_category else 'Uncategorized',
            'component_category_type': component_category.category_type if component_category else None,
            'quantity_required': detail.quantity_required,
            'unit_of_measure': detail.unit_of_measure
        })

    return jsonify(result)

@bom_bp.route('/api/bom/<int:bom_id>/details', methods=['POST'])
@login_required
def add_bom_detail(bom_id):
    # Check if BOM exists
    bom = BOM.query.get_or_404(bom_id)

    data = request.get_json()

    # Validate required fields
    if not data.get('component_item_id') or 'quantity_required' not in data:
        return jsonify({'message': 'Missing required fields: component_item_id or quantity_required'}), 400

    # Check if component exists
    component = Item.query.get(data['component_item_id'])
    if not component:
        return jsonify({'message': 'Component item not found'}), 404

    # Check if component is not the same as the final product
    if component.id == bom.final_product_id:
        return jsonify({'message': 'Component cannot be the same as the final product'}), 400

    # Check if component is a valid type (raw material, packaging, or intermediate product)
    if component.category and hasattr(component.category, 'category_type'):
        valid_component_types = ['RawMaterial', 'Packaging', 'IntermediateProduct']
        if component.category.category_type not in valid_component_types:
            return jsonify({
                'message': f'Component must be categorized as one of: {", ".join(valid_component_types)}'
            }), 400

    # Check if component already exists in this BOM
    existing_detail = BOMDetail.query.filter_by(
        bom_id=bom_id,
        component_item_id=data['component_item_id']
    ).first()

    if existing_detail:
        return jsonify({'message': 'This component is already part of the BOM'}), 400

    # Create new BOM detail
    detail = BOMDetail(
        bom_id=bom_id,
        component_item_id=data['component_item_id'],
        quantity_required=data['quantity_required'],
        unit_of_measure=data.get('unit_of_measure', component.unit_of_measure)
    )

    db.session.add(detail)
    db.session.commit()

    # Update the final product's cost based on the BOM
    update_item_cost_from_bom(bom_id)

    # Get category information for response
    component_category = Category.query.get(component.category_id) if component.category_id else None

    return jsonify({
        'id': detail.id,
        'bom_id': detail.bom_id,
        'component_item_id': detail.component_item_id,
        'component_name': component.name,
        'component_category_id': component.category_id,
        'component_category_name': component_category.name if component_category else 'Uncategorized',
        'component_category_type': component_category.category_type if component_category else None,
        'quantity_required': detail.quantity_required,
        'unit_of_measure': detail.unit_of_measure
    }), 201

@bom_bp.route('/api/bom/details/<int:detail_id>', methods=['PUT'])
@login_required
def update_bom_detail(detail_id):
    detail = BOMDetail.query.get_or_404(detail_id)
    data = request.get_json()

    # Update quantity if provided
    if 'quantity_required' in data:
        detail.quantity_required = data['quantity_required']

    # Update unit of measure if provided
    if 'unit_of_measure' in data:
        detail.unit_of_measure = data['unit_of_measure']

    # Update component if provided
    if 'component_item_id' in data:
        # Check if component exists
        component = Item.query.get(data['component_item_id'])
        if not component:
            return jsonify({'message': 'Component item not found'}), 404

        # Get the BOM to check if component is not the final product
        bom = BOM.query.get(detail.bom_id)
        if component.id == bom.final_product_id:
            return jsonify({'message': 'Component cannot be the same as the final product'}), 400

        # Check if component is a valid type (raw material, packaging, or intermediate product)
        if component.category and hasattr(component.category, 'category_type'):
            valid_component_types = ['RawMaterial', 'Packaging', 'IntermediateProduct']
            if component.category.category_type not in valid_component_types:
                return jsonify({
                    'message': f'Component must be categorized as one of: {", ".join(valid_component_types)}'
                }), 400

        # Check if component already exists in this BOM
        existing_detail = BOMDetail.query.filter_by(
            bom_id=detail.bom_id,
            component_item_id=data['component_item_id']
        ).first()

        if existing_detail and existing_detail.id != detail_id:
            return jsonify({'message': 'This component is already part of the BOM'}), 400

        detail.component_item_id = data['component_item_id']

    db.session.commit()
    update_item_cost_from_bom(detail.bom_id)
    component = Item.query.get(detail.component_item_id)
    component_category = Category.query.get(component.category_id) if component and component.category_id else None

    return jsonify({
        'id': detail.id,
        'bom_id': detail.bom_id,
        'component_item_id': detail.component_item_id,
        'component_name': component.name if component else 'Unknown Component',
        'component_category_id': component.category_id if component else None,
        'component_category_name': component_category.name if component_category else 'Uncategorized',
        'component_category_type': component_category.category_type if component_category else None,
        'quantity_required': detail.quantity_required,
        'unit_of_measure': detail.unit_of_measure
    })

@bom_bp.route('/api/bom/details/<int:detail_id>', methods=['DELETE'])
@login_required
def delete_bom_detail(detail_id):
    detail = BOMDetail.query.get_or_404(detail_id)
    db.session.delete(detail)
    db.session.commit()
    update_item_cost_from_bom(detail.bom_id)

    return '', 204

# Production from BOM endpoint
@bom_bp.route('/api/bom/<int:bom_id>/produce', methods=['POST'])
@login_required
def produce_from_bom(bom_id):
    bom = BOM.query.get_or_404(bom_id)
    data = request.get_json()

    # Validate required fields
    if 'quantity' not in data or not data.get('warehouse_id'):
        return jsonify({'message': 'Missing required fields: quantity or warehouse_id'}), 400

    if not bom.details or len(bom.details) == 0:
        return jsonify({'message': 'لا يمكن الإنتاج من قائمة مواد فارغة. لا توجد مكونات محددة.'}), 400
    quantity = int(data['quantity'])
    warehouse_id = data['warehouse_id']

    # Check if warehouse exists
    warehouse = Warehouse.query.get(warehouse_id)
    if not warehouse:
        return jsonify({'message': 'Warehouse not found'}), 404

    # Check if quantity is positive
    if quantity <= 0:
        return jsonify({'message': 'Quantity must be positive'}), 400

    # Get all components needed for production
    components_needed = []
    total_cost = 0  # Track the total cost of components

    for detail in bom.details:
        component = Item.query.get(detail.component_item_id)
        if not component:
            return jsonify({'message': f'Component with ID {detail.component_item_id} not found'}), 404

        # Calculate required quantity
        required_qty = detail.quantity_required * quantity

        # Calculate component cost
        component_cost = component.cost * detail.quantity_required
        total_cost += component_cost

        # Check if enough inventory is available
        inventory = Inventory.query.filter_by(
            item_id=detail.component_item_id,
            warehouse_id=warehouse_id
        ).first()

        available_qty = inventory.quantity if inventory else 0

        if available_qty < required_qty:
            component_category = Category.query.get(component.category_id) if component.category_id else None
            return jsonify({
                'message': f'Not enough inventory for component: {component.name}',
                'component': {
                    'id': component.id,
                    'name': component.name,
                    'category': component_category.name if component_category else 'Uncategorized',
                    'category_type': component_category.category_type if component_category else None
                },
                'required': required_qty,
                'available': available_qty,
                'unit_of_measure': detail.unit_of_measure
            }), 400

        components_needed.append({
            'item_id': detail.component_item_id,
            'quantity': required_qty
        })

    # Begin transaction
    try:
        # Deduct components from inventory
        for component in components_needed:
            # Update inventory
            inventory = Inventory.query.filter_by(
                item_id=component['item_id'],
                warehouse_id=warehouse_id
            ).first()

            inventory.quantity -= component['quantity']

            # Create transaction record
            transaction = InventoryTransaction(
                item_id=component['item_id'],
                warehouse_id=warehouse_id,
                transaction_type='OUT',
                quantity=component['quantity'],
                reference=f'Production of {quantity} units of Item #{bom.final_product_id}'
            )
            db.session.add(transaction)

        # Add final product to inventory
        final_product_inventory = Inventory.query.filter_by(
            item_id=bom.final_product_id,
            warehouse_id=warehouse_id
        ).first()

        if not final_product_inventory:
            final_product_inventory = Inventory(
                item_id=bom.final_product_id,
                warehouse_id=warehouse_id,
                quantity=0
            )
            db.session.add(final_product_inventory)

        final_product_inventory.quantity += quantity

        # Create transaction record for final product
        transaction = InventoryTransaction(
            item_id=bom.final_product_id,
            warehouse_id=warehouse_id,
            transaction_type='IN',
            quantity=quantity,
            reference='Production from BOM'
        )
        db.session.add(transaction)

        # Update the final product's cost with the calculated total cost
        final_product = Item.query.get(bom.final_product_id)
        if final_product:
            final_product.cost = total_cost
            db.session.commit()

        db.session.commit()

        # Get final product details for response
        final_product = Item.query.get(bom.final_product_id)
        final_product_category = Category.query.get(final_product.category_id) if final_product and final_product.category_id else None

        return jsonify({
            'message': f'Successfully produced {quantity} units of Item #{bom.final_product_id}',
            'components_used': components_needed,
            'final_product': {
                'item_id': bom.final_product_id,
                'item_name': final_product.name if final_product else 'Unknown Product',
                'category': final_product_category.name if final_product_category else 'Uncategorized',
                'category_type': final_product_category.category_type if final_product_category else None,
                'quantity_produced': quantity,
                'updated_cost': total_cost  # Include the updated cost in the response
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Error during production: {str(e)}'}), 500


def update_item_cost_from_bom(bom_id):
    """Helper function to update an item's cost based on its BOM"""
    bom = BOM.query.get(bom_id)
    if not bom:
        return False

    # Calculate total cost from BOM components
    total_cost = 0
    for detail in bom.details:
        component = Item.query.get(detail.component_item_id)
        if component:
            component_cost = component.cost * detail.quantity_required
            total_cost += component_cost

    # Update the final product's cost
    final_product = Item.query.get(bom.final_product_id)
    if final_product:
        final_product.cost = total_cost
        db.session.commit()
        return True

    return False


@bom_bp.route('/api/bom/<int:bom_id>/check-availability', methods=['POST'])
@login_required
def check_bom_availability(bom_id):
    bom = BOM.query.get_or_404(bom_id)
    data = request.get_json()

    # Validate required fields
    if 'quantity' not in data or not data.get('warehouse_id'):
        return jsonify({'message': 'Missing required fields: quantity or warehouse_id'}), 400

    quantity = int(data['quantity'])
    warehouse_id = data['warehouse_id']

    # Check if warehouse exists
    warehouse = Warehouse.query.get(warehouse_id)
    if not warehouse:
        return jsonify({'message': 'Warehouse not found'}), 404

    # Check if quantity is positive
    if quantity <= 0:
        return jsonify({'message': 'Quantity must be positive'}), 400

    # Check availability of all components
    availability_results = []
    all_available = True

    for detail in bom.details:
        component = Item.query.get(detail.component_item_id)
        if not component:
            return jsonify({'message': f'Component with ID {detail.component_item_id} not found'}), 404

        component_category = Category.query.get(component.category_id) if component and component.category_id else None

        # Calculate required quantity
        required_qty = detail.quantity_required * quantity

        # Check inventory
        inventory = Inventory.query.filter_by(
            item_id=detail.component_item_id,
            warehouse_id=warehouse_id
        ).first()

        available_qty = inventory.quantity if inventory else 0
        is_available = available_qty >= required_qty

        if not is_available:
            all_available = False

        availability_results.append({
            'component_id': detail.component_item_id,
            'component_name': component.name,
            'component_category': component_category.name if component_category else 'Uncategorized',
            'component_category_type': component_category.category_type if component_category else None,
            'required_quantity': required_qty,
            'available_quantity': available_qty,
            'unit_of_measure': detail.unit_of_measure,
            'is_available': is_available
        })

    return jsonify({
        'all_available': all_available,
        'components': availability_results
    })

@bom_bp.route('/api/bom/<int:bom_id>/calculate-cost', methods=['GET'])
@login_required
def calculate_bom_cost(bom_id):
    bom = BOM.query.get_or_404(bom_id)

    # Get the final product
    final_product = Item.query.get(bom.final_product_id)
    if not final_product:
        return jsonify({'message': 'Final product not found'}), 404

    final_product_category = Category.query.get(final_product.category_id) if final_product and final_product.category_id else None

    # Calculate component costs
    component_costs = []
    total_cost = 0

    for detail in bom.details:
        component = Item.query.get(detail.component_item_id)
        if not component:
            return jsonify({'message': f'Component with ID {detail.component_item_id} not found'}), 404

        component_category = Category.query.get(component.category_id) if component and component.category_id else None
        category_name = component_category.name if component_category else 'Uncategorized'

        component_cost = component.cost * detail.quantity_required
        total_cost += component_cost

        component_costs.append({
            'component_id': detail.component_item_id,
            'component_name': component.name,
            'component_category': category_name,
            'quantity_required': detail.quantity_required,
            'unit_cost': component.cost,
            'total_cost': component_cost
        })

    # Calculate profit margin
    selling_price = final_product.price
    profit = selling_price - total_cost
    profit_margin = (profit / selling_price * 100) if selling_price > 0 else 0

    # Calculate component cost percentages
    component_cost_breakdown = []
    for component in component_costs:
        percentage = (component['total_cost'] / total_cost * 100) if total_cost > 0 else 0
        component_cost_breakdown.append({
            'component_id': component['component_id'],
            'component_name': component['component_name'],
            'cost': component['total_cost'],
            'percentage': percentage
        })

    # Sort by percentage (descending)
    component_cost_breakdown.sort(key=lambda x: x['percentage'], reverse=True)

    return jsonify({
        'final_product': {
            'id': final_product.id,
            'name': final_product.name,
            'category': final_product_category.name if final_product_category else 'Uncategorized',
            'selling_price': selling_price
        },
        'components': component_costs,
        'component_cost_breakdown': component_cost_breakdown,
        'total_cost': total_cost,
        'profit': profit,
        'profit_margin': profit_margin
    })

@bom_bp.route('/api/bom/components-by-category', methods=['GET'])
@login_required
def get_components_by_category():
    """Get all potential components grouped by category"""
    items = Item.query.all()
    categories = Category.query.all()

    # Create a dictionary of categories
    category_dict = {category.id: {
        'name': category.name,
        'type': category.category_type if hasattr(category, 'category_type') else None
    } for category in categories}

    # Group items by category
    categorized_items = {}
    for item in items:
        category_info = category_dict.get(item.category_id, {'name': 'Uncategorized', 'type': None})
        category_name = category_info['name']
        category_type = category_info['type']

        if category_name not in categorized_items:
            categorized_items[category_name] = {
                'items': [],
                'category_type': category_type
            }

        categorized_items[category_name]['items'].append({
            'id': item.id,
            'name': item.name,
            'sku': item.sku,
            'unit_of_measure': item.unit_of_measure,
            'cost': item.cost
        })

    # Convert to list format for the frontend
    result = []
    for category_name, data in categorized_items.items():
        result.append({
            'category_name': category_name,
            'category_type': data['category_type'],
            'items': sorted(data['items'], key=lambda x: x['name'])
        })

    # Sort categories alphabetically
    result.sort(key=lambda x: x['category_name'])

    return jsonify(result)

@bom_bp.route('/api/bom/components-by-type', methods=['GET'])
@login_required
def get_components_by_type():
    """Get all potential components grouped by type"""
    items = Item.query.all()
    categories = Category.query.all()

    # Create a dictionary of categories with their types
    category_dict = {}
    for category in categories:
        # Use category_type instead of type
        category_type = category.category_type if hasattr(category, 'category_type') else 'Unknown'
        category_dict[category.id] = {
            'name': category.name,
            'type': category_type
        }

    # Group items by category type
    categorized_items = {
        'RawMaterial': {'category_type': 'RawMaterial', 'items': []},
        'IntermediateProduct': {'category_type': 'IntermediateProduct', 'items': []},
        'FinalProduct': {'category_type': 'FinalProduct', 'items': []},
        'Packaging': {'category_type': 'Packaging', 'items': []},
        'Unknown': {'category_type': 'Unknown', 'items': []}
    }

    for item in items:
        category_info = category_dict.get(item.category_id, {'name': 'Uncategorized', 'type': 'Unknown'})
        category_type = category_info['type']

        if category_type not in categorized_items:
            categorized_items[category_type] = {'category_type': category_type, 'items': []}

        categorized_items[category_type]['items'].append({
            'id': item.id,
            'name': item.name,
            'sku': item.sku,
            'unit_of_measure': item.unit_of_measure,
            'cost': item.cost
        })

    # Convert to list format for the frontend
    result = [value for key, value in categorized_items.items() if value['items']]

    return jsonify(result)

# Add a route for the BOM management page
@bom_bp.route('/bom-management')
@login_required
def bom_management_page():
    return render_template('bom_management.html')

# BOM Excel Import Routes
@bom_bp.route('/bom/import-excel')
@login_required
def import_excel_form():
    """Display the form for uploading Excel file for BOM import"""
    # Get all categories for the dropdown
    categories = Category.query.all()
    return render_template('bom/import_excel.html', categories=categories)

@bom_bp.route('/bom/upload-excel', methods=['POST'])
@login_required
def upload_excel():
    """Upload Excel file and show sheet selection if multiple sheets exist"""
    if 'excel_file' not in request.files:
        flash('لم يتم تحديد ملف', 'error')
        return redirect(url_for('bom.import_excel_form'))

    file = request.files['excel_file']
    raw_material_category = request.form.get('raw_material_category')
    final_product_category = request.form.get('final_product_category')
    default_unit = request.form.get('default_unit', 'وحدة')  # Default to 'وحدة' if not provided

    if not raw_material_category or not final_product_category:
        flash('يجب اختيار تصنيف المواد الخام والمنتجات النهائية', 'error')
        return redirect(url_for('bom.import_excel_form'))

    if file.filename == '':
        flash('لم يتم تحديد ملف', 'error')
        return redirect(url_for('bom.import_excel_form'))

    if file and file.filename.endswith(('.xlsx', '.xls')):
        # Create a unique filename
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4()}_{filename}"

        # Ensure the upload directory exists
        upload_dir = os.path.join(current_app.config.get('TEMP_FOLDER', 'temp'), 'excel_imports')
        os.makedirs(upload_dir, exist_ok=True)

        # Save the file
        file_path = os.path.join(upload_dir, unique_filename)
        file.save(file_path)

        # Read the Excel file and check for multiple sheets
        try:
            # Get the sheet names from the Excel file
            excel_file = pd.ExcelFile(file_path)
            sheet_names = excel_file.sheet_names

            # If there are multiple sheets, show the sheet selection page
            if len(sheet_names) > 1:
                return render_template('bom/select_sheet.html',
                                      sheet_names=sheet_names,
                                      file_path=file_path,
                                      raw_material_category=raw_material_category,
                                      final_product_category=final_product_category,
                                      default_unit=default_unit)
            else:
                # If there's only one sheet, process it directly
                sheet_name = sheet_names[0]
                return process_excel_sheet(file_path, sheet_name, raw_material_category, final_product_category, default_unit)

        except Exception as e:
            flash(f'خطأ في قراءة ملف Excel: {str(e)}', 'error')
            return redirect(url_for('bom.import_excel_form'))
    else:
        flash('يجب أن يكون الملف بصيغة Excel (.xlsx أو .xls)', 'error')
        return redirect(url_for('bom.import_excel_form'))

@bom_bp.route('/bom/select-sheet', methods=['POST'])
@login_required
def select_sheet():
    """Process the selected sheet from the Excel file"""
    file_path = request.form.get('file_path')
    sheet_name = request.form.get('sheet_name')
    raw_material_category = request.form.get('raw_material_category')
    final_product_category = request.form.get('final_product_category')
    default_unit = request.form.get('default_unit', 'وحدة')  # Default to 'وحدة' if not provided

    if not file_path or not sheet_name:
        flash('بيانات غير صالحة', 'error')
        return redirect(url_for('bom.import_excel_form'))

    return process_excel_sheet(file_path, sheet_name, raw_material_category, final_product_category, default_unit)

def process_excel_sheet(file_path, sheet_name, raw_material_category, final_product_category, default_unit='وحدة'):
    """Process the Excel sheet and prepare data for preview"""
    try:
        # Read the Excel file with the specified sheet
        df = pd.read_excel(file_path, sheet_name=sheet_name)

        # Check if the dataframe is empty
        if df.empty:
            flash('ملف Excel فارغ', 'error')
            return redirect(url_for('bom.import_excel_form'))

        # Get the first column (product names) and first row (material names)
        product_names = df.iloc[1:, 0].dropna().tolist()
        material_names = df.columns[1:].tolist()

        # Get quantities matrix (excluding first row and first column)
        quantities = df.iloc[1:, 1:].values.tolist()

        # Check if we have valid data
        if not product_names or not material_names:
            flash('تنسيق ملف Excel غير صالح. يجب أن يحتوي على أسماء المنتجات في العمود الأول وأسماء المواد الخام في الصف الأول.', 'error')
            return redirect(url_for('bom.import_excel_form'))

        # Process products (check if they exist in the database)
        products_data = []
        for product_name in product_names:
            # Check if product exists
            product = Item.query.filter(Item.name.like(f"%{product_name}%")).first()
            if product:
                products_data.append({
                    'id': product.id,
                    'name': product.name,
                    'is_new': False
                })
            else:
                # Generate a temporary negative ID for new products
                products_data.append({
                    'id': -len(products_data) - 1,  # Negative ID to indicate new product
                    'name': product_name,
                    'is_new': True
                })

        # Process materials (check if they exist in the database)
        materials_data = []
        for material_name in material_names:
            # Check if material exists
            material = Item.query.filter(Item.name.like(f"%{material_name}%")).first()
            if material:
                materials_data.append({
                    'id': material.id,
                    'name': material.name,
                    'is_new': False
                })
            else:
                # Generate a temporary negative ID for new materials
                materials_data.append({
                    'id': -len(materials_data) - 1000,  # Negative ID to indicate new material, offset to avoid collision with products
                    'name': material_name,
                    'is_new': True
                })

        # Prepare data for the template
        bom_data = {
            'products': products_data,
            'materials': materials_data,
            'quantities': quantities,
            'default_unit': default_unit
        }

        return render_template('bom/preview_bom_import.html',
                              bom_data=bom_data,
                              file_path=file_path,
                              sheet_name=sheet_name,
                              raw_material_category=raw_material_category,
                              final_product_category=final_product_category,
                              default_unit=default_unit)

    except Exception as e:
        flash(f'خطأ في معالجة ملف Excel: {str(e)}', 'error')
        return redirect(url_for('bom.import_excel_form'))

@bom_bp.route('/bom/process-excel-import', methods=['POST'])
@login_required
def process_excel_import():
    """Process the Excel import data and create BOMs"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({'success': False, 'message': 'بيانات غير صالحة'}), 400

        # Extract data
        file_path = data.get('file_path')
        raw_material_category_id = data.get('raw_material_category_id')
        final_product_category_id = data.get('final_product_category_id')
        new_raw_materials = data.get('new_raw_materials', [])
        new_final_products = data.get('new_final_products', [])
        bom_data = data.get('bom_data', [])

        # Validate required data
        if not raw_material_category_id or not final_product_category_id:
            return jsonify({'success': False, 'message': 'تصنيف المواد الخام أو المنتجات النهائية غير محدد'}), 400

        # Create new raw materials
        material_id_mapping = {}  # Map temporary IDs to actual database IDs
        for material in new_raw_materials:
            # Skip if material has a positive ID (already exists in database)
            if material.get('id', 0) > 0:
                continue

            # Generate a unique SKU
            sku = f"RM-{uuid.uuid4().hex[:8].upper()}"

            # Create new material
            new_material = Item(
                name=material.get('name', ''),
                category_id=raw_material_category_id,
                sku=sku,
                description=material.get('description', 'أضيف عند استيراد قائمة المواد من ملف Excel'),
                unit_of_measure=material.get('unit_of_measure', ''),
                cost=material.get('cost', 0),
                price=material.get('price', 0),
                reorder_level=10  # Default reorder level
            )

            db.session.add(new_material)
            db.session.flush()  # Get the ID without committing

            # Map temporary ID to actual database ID
            material_id_mapping[material['id']] = new_material.id

        # Create new final products
        product_id_mapping = {}  # Map temporary IDs to actual database IDs
        for product in new_final_products:
            # Skip if product has a positive ID (already exists in database)
            if product.get('id', 0) > 0:
                continue

            # Generate a unique SKU
            sku = f"FP-{uuid.uuid4().hex[:8].upper()}"

            # Create new product
            new_product = Item(
                name=product.get('name', ''),
                category_id=final_product_category_id,
                sku=sku,
                description=product.get('description', 'أضيف عند استيراد قائمة المواد من ملف Excel'),
                unit_of_measure=product.get('unit_of_measure', ''),
                cost=product.get('cost', 0),
                price=product.get('price', 0),
                reorder_level=5  # Default reorder level
            )

            db.session.add(new_product)
            db.session.flush()  # Get the ID without committing

            # Map temporary ID to actual database ID
            product_id_mapping[product['id']] = new_product.id

        # Create BOMs
        created_boms = 0
        created_components = 0

        for bom_item in bom_data:
            product_id = bom_item.get('product_id')
            is_new_product = bom_item.get('is_new_product', False)
            components = bom_item.get('components', [])

            # Skip if no components
            if not components:
                continue

            # Get actual product ID (map from temporary ID if new)
            if is_new_product and product_id < 0:
                product_id = product_id_mapping.get(product_id, product_id)

            # Check if product exists
            product = Item.query.get(product_id)
            if not product:
                continue

            # Check if BOM already exists for this product
            existing_bom = BOM.query.filter_by(final_product_id=product_id).first()
            if existing_bom:
                # Delete existing BOM details
                BOMDetail.query.filter_by(bom_id=existing_bom.id).delete()
                bom = existing_bom
            else:
                # Create new BOM
                bom = BOM(
                    final_product_id=product_id,
                    description=f"تم استيراده من ملف Excel بتاريخ {datetime.now().strftime('%Y-%m-%d')}"
                )
                db.session.add(bom)
                db.session.flush()  # Get the ID without committing
                created_boms += 1

            # Add components to BOM
            for component in components:
                material_id = component.get('material_id')
                is_new_material = component.get('is_new_material', False)
                quantity = component.get('quantity', 0)

                # Skip if quantity is zero or negative
                if quantity <= 0:
                    continue

                # Get actual material ID (map from temporary ID if new)
                if is_new_material and material_id < 0:
                    material_id = material_id_mapping.get(material_id, material_id)

                # Check if material exists
                material = Item.query.get(material_id)
                if not material:
                    continue

                # Get unit of measure from component data or use material's unit
                unit_of_measure = component.get('unit_of_measure') or material.unit_of_measure or 'وحدة'

                # Add component to BOM
                bom_detail = BOMDetail(
                    bom_id=bom.id,
                    component_item_id=material_id,
                    quantity_required=quantity,
                    unit_of_measure=unit_of_measure
                )

                db.session.add(bom_detail)
                created_components += 1

        # Update product costs based on BOMs
        for bom_item in bom_data:
            product_id = bom_item.get('product_id')
            is_new_product = bom_item.get('is_new_product', False)

            # Get actual product ID (map from temporary ID if new)
            if is_new_product and product_id < 0:
                product_id = product_id_mapping.get(product_id, product_id)

            # Get the BOM for this product
            bom = BOM.query.filter_by(final_product_id=product_id).first()
            if bom:
                update_item_cost_from_bom(bom.id)

        # Commit all changes
        db.session.commit()

        # Clean up the temporary file
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

        return jsonify({
            'success': True,
            'message': f'تم استيراد {created_boms} من قوائم المواد بنجاح مع {created_components} من المكونات.',
            'created_boms': created_boms,
            'created_components': created_components
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'حدث خطأ أثناء الاستيراد: {str(e)}'}), 500


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

@bom_bp.route('/api/bom/<int:bom_id>/pdf', methods=['GET'])
@login_required
def generate_bom_pdf(bom_id):
    """Generate a PDF report for a BOM"""
    bom = BOM.query.get_or_404(bom_id)
    final_product = Item.query.get(bom.final_product_id)
    final_product_category = Category.query.get(final_product.category_id) if final_product and final_product.category_id else None

    # Get all details for this BOM
    details = []
    total_cost = 0

    # Track costs by individual component
    component_costs = []

    for detail in bom.details:
        component = Item.query.get(detail.component_item_id)
        component_category = Category.query.get(component.category_id) if component and component.category_id else None

        # Calculate component cost
        component_cost = component.cost * detail.quantity_required if component else 0
        total_cost += component_cost

        # Add to component costs list
        component_costs.append({
            'component_id': detail.component_item_id,
            'component_name': component.name if component else 'Unknown Component',
            'cost': component_cost,
            'percentage': 0  # Will calculate after we have total
        })

        details.append({
            'id': detail.id,
            'component_item_id': detail.component_item_id,
            'component_name': component.name if component else 'Unknown Component',
            'component_category_id': component.category_id if component else None,
            'component_category_name': component_category.name if component_category else 'Uncategorized',
            'component_category_type': getattr(component_category, 'category_type', 'Unknown') if component_category else 'Unknown',
            'quantity_required': detail.quantity_required,
            'unit_of_measure': detail.unit_of_measure,
            'component_cost': component.cost if component else 0,
            'total_component_cost': component_cost
        })

    # Calculate percentages for component costs
    if total_cost > 0:
        for cost_item in component_costs:
            cost_item['percentage'] = (cost_item['cost'] / total_cost * 100)

    # Sort component costs by percentage (descending)
    component_costs.sort(key=lambda x: x['percentage'], reverse=True)

    # Calculate selling price and profit
    selling_price = final_product.price if final_product else 0
    profit = selling_price - total_cost
    profit_margin = (profit / selling_price * 100) if selling_price > 0 else 0

    # Prepare data for the PDF template
    bom_data = {
        'id': bom.id,
        'final_product_id': bom.final_product_id,
        'final_product_name': final_product.name if final_product else 'Unknown Product',
        'final_product_category_name': final_product_category.name if final_product_category else 'Uncategorized',
        'final_product_category_type': getattr(final_product_category, 'category_type', 'Unknown') if final_product_category else 'Unknown',
        'description': bom.description,
        'created_at': bom.created_at.strftime('%Y-%m-%d'),
        'updated_at': bom.updated_at.strftime('%Y-%m-%d'),
        'details': details,
        'total_cost': total_cost,
        'selling_price': selling_price,
        'profit': profit,
        'profit_margin': profit_margin,
        'component_costs': component_costs
    }

    # Render the PDF template
    html_content = render_template('bom_pdf_template.html', bom=bom_data)

    # Generate the PDF
    try:
        pdf_path = generate_pdf(html_content)

        # Send the PDF file
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=f'BOM-{bom.id}-{final_product.name if final_product else "report"}.pdf',
            mimetype='application/pdf'
        )
    except Exception as e:
        return jsonify({'message': f'Error generating PDF: {str(e)}'}), 500

@bom_bp.route('/api/bom/<int:bom_id>/simple-pdf', methods=['GET'])
@login_required
def generate_simple_bom_pdf(bom_id):
    """Generate a simplified PDF report for a BOM (without cost summary)"""
    bom = BOM.query.get_or_404(bom_id)
    final_product = Item.query.get(bom.final_product_id)
    final_product_category = Category.query.get(final_product.category_id) if final_product and final_product.category_id else None

    # Get all details for this BOM
    details = []

    for detail in bom.details:
        component = Item.query.get(detail.component_item_id)
        component_category = Category.query.get(component.category_id) if component and component.category_id else None

        details.append({
            'id': detail.id,
            'component_item_id': detail.component_item_id,
            'component_name': component.name if component else 'Unknown Component',
            'component_category_name': component_category.name if component_category else 'Uncategorized',
            'component_category_type': getattr(component_category, 'category_type', 'Unknown') if component_category else 'Unknown',
            'quantity_required': detail.quantity_required,
            'unit_of_measure': detail.unit_of_measure
        })

    # Prepare data for the PDF template
    bom_data = {
        'id': bom.id,
        'final_product_id': bom.final_product_id,
        'final_product_name': final_product.name if final_product else 'Unknown Product',
        'final_product_category_name': final_product_category.name if final_product_category else 'Uncategorized',
        'final_product_category_type': getattr(final_product_category, 'category_type', 'Unknown') if final_product_category else 'Unknown',
        'description': bom.description,
        'created_at': bom.created_at.strftime('%Y-%m-%d'),
        'updated_at': bom.updated_at.strftime('%Y-%m-%d'),
        'details': details
    }

    # Render the PDF template
    html_content = render_template('bom_simple_pdf_template.html', bom=bom_data)

    # Generate the PDF
    try:
        pdf_path = generate_pdf(html_content)

        # Send the PDF file
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=f'BOM-Simple-{bom.id}-{final_product.name if final_product else "report"}.pdf',
            mimetype='application/pdf'
        )
    except Exception as e:
        return jsonify({'message': f'Error generating PDF: {str(e)}'}), 500


@bom_bp.route('/api/bom/stats', methods=['GET'])
@login_required
def get_bom_stats():
    """Get BOM statistics for the dashboard"""
    try:
        # Get all BOMs
        boms = BOM.query.all()

        # Count BOMs for final products
        final_products_count = 0
        intermediate_products_count = 0

        for bom in boms:
            product = Item.query.get(bom.final_product_id)
            if product and product.category:
                if product.category.category_type == 'FinalProduct':
                    final_products_count += 1
                else:
                    intermediate_products_count += 1

        return jsonify({
            'finalProducts': final_products_count,
            'intermediateProducts': intermediate_products_count
        })

    except Exception as e:
        current_app.logger.error(f"Error fetching BOM stats: {str(e)}")
        return jsonify({'message': f'Error fetching BOM stats: {str(e)}'}), 500

@bom_bp.route('/api/bom/products-with-cost', methods=['GET'])
@login_required
def get_products_with_cost():
    """Get products with their BOM cost breakdown"""
    try:
        # Get all BOMs
        boms = BOM.query.all()
        result = []

        for bom in boms:
            product = Item.query.get(bom.final_product_id)
            if not product:
                continue

            # Get product category information
            category = Category.query.get(product.category_id) if product.category_id else None
            category_name = category.name if category else 'غير مصنف'
            category_type = category.category_type if category and hasattr(category, 'category_type') else None

            # Skip if not a final or intermediate product
            if category_type not in ['FinalProduct', 'IntermediateProduct']:
                continue

            # Calculate total cost
            total_cost = 0
            component_costs = []

            # Get BOM details
            bom_details = BOMDetail.query.filter_by(bom_id=bom.id).all()

            for detail in bom_details:
                component = Item.query.get(detail.component_item_id)
                if not component:
                    continue

                # Get component category
                component_category = Category.query.get(component.category_id) if component and component.category_id else None
                component_category_name = component_category.name if component_category else 'غير مصنف'
                component_category_type = component_category.category_type if component_category else None

                # Calculate component cost
                component_cost = component.cost * detail.quantity_required
                total_cost += component_cost

                component_costs.append({
                    'component_id': component.id,
                    'component_name': component.name,
                    'component_category': component_category_name,
                    'component_category_type': component_category_type,
                    'quantity': detail.quantity_required,
                    'unit_cost': component.cost,
                    'cost': component_cost,
                    'percentage': 0  # Will calculate after total is known
                })

            # Calculate percentages
            if total_cost > 0:
                for cost in component_costs:
                    cost['percentage'] = (cost['cost'] / total_cost) * 100

            # Sort components by cost (highest first)
            component_costs.sort(key=lambda x: x['cost'], reverse=True)

            # Calculate profit margin
            selling_price = product.price or 0
            profit = selling_price - total_cost
            profit_margin = ((selling_price - total_cost) / selling_price) * 100 if selling_price > 0 else 0

            result.append({
                'id': product.id,
                'name': product.name,
                'sku': product.sku,
                'category_id': product.category_id,
                'category_name': category_name,
                'category_type': category_type,
                'bom_id': bom.id,
                'total_cost': total_cost,
                'selling_price': selling_price,
                'profit': profit,
                'profit_margin': profit_margin,
                'component_costs': component_costs
            })

        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f"Error fetching products with cost: {str(e)}")
        return jsonify({'message': f'Error fetching products with cost: {str(e)}'}), 500

# Add this to an appropriate routes file (e.g., item_routes.py or bom_routes.py)

@bom_bp.route('/api/items/<int:item_id>/update-price', methods=['POST'])
@login_required
def update_item_price(item_id):
    """Update an item's selling price"""
    try:
        data = request.get_json()

        if 'price' not in data:
            return jsonify({'message': 'Missing required field: price'}), 400

        price = float(data['price'])
        if price < 0:
            return jsonify({'message': 'Price cannot be negative'}), 400

        item = Item.query.get_or_404(item_id)
        item.price = price

        # Update the timestamp
        item.updated_at = datetime.utcnow()

        db.session.commit()

        return jsonify({
            'id': item.id,
            'name': item.name,
            'price': item.price,
            'message': 'Price updated successfully'
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating item price: {str(e)}")
        return jsonify({'message': f'Error updating item price: {str(e)}'}), 500
