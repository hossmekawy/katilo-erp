from flask import Blueprint, request, jsonify, render_template, abort, current_app
from flask_login import current_user, login_required
from models import db, BOM, BOMDetail, Item, Inventory, InventoryTransaction, Warehouse, Category

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
    for detail in bom.details:
        component = Item.query.get(detail.component_item_id)
        component_category = Category.query.get(component.category_id) if component and component.category_id else None
        
        # Calculate component cost
        component_cost = component.cost * detail.quantity_required if component else 0
        total_cost += component_cost
        
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
    
    # Calculate selling price and profit
    selling_price = final_product.price if final_product else 0
    profit = selling_price - total_cost
    profit_margin = (profit / selling_price * 100) if selling_price > 0 else 0
    
    # Count how many times this BOM has been produced
    # We'll count the number of "IN" transactions for the final product with reference "Production from BOM"
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
        'production_count': production_count
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
        
        if category_name not in categorized_items:
            categorized_items[category_name] = []
            
        categorized_items[category_name].append({
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
            'items': items
        }
        for category, items in categorized_items.items()
    ]
    
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
    
    # Get category information for response
    final_product_category = Category.query.get(final_product.category_id) if final_product.category_id else None
   
    return jsonify({
        'id': bom.id,
        'final_product_id': bom.final_product_id,
        'final_product_name': final_product.name,
        'final_product_category_id': final_product.category_id,
        'final_product_category_name': final_product_category.name if final_product_category else 'Uncategorized',
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
       
        # Check if another BOM already uses this product
        existing_bom = BOM.query.filter_by(final_product_id=data['final_product_id']).first()
        if existing_bom and existing_bom.id != id:
            return jsonify({'message': 'A BOM already exists for this product'}), 400
       
        bom.final_product_id = data['final_product_id']
   
    db.session.commit()
    
    # Get updated product and category information
    final_product = Item.query.get(bom.final_product_id)
    final_product_category = Category.query.get(final_product.category_id) if final_product and final_product.category_id else None
   
    return jsonify({
        'id': bom.id,
        'final_product_id': bom.final_product_id,
        'final_product_name': final_product.name if final_product else 'Unknown Product',
        'final_product_category_id': final_product.category_id if final_product else None,
        'final_product_category_name': final_product_category.name if final_product_category else 'Uncategorized',
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
    
    # Get category information for response
    component_category = Category.query.get(component.category_id) if component.category_id else None
   
    return jsonify({
        'id': detail.id,
        'bom_id': detail.bom_id,
        'component_item_id': detail.component_item_id,
        'component_name': component.name,
        'component_category_id': component.category_id,
        'component_category_name': component_category.name if component_category else 'Uncategorized',
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
       
        # Check if component already exists in this BOM
        existing_detail = BOMDetail.query.filter_by(
            bom_id=detail.bom_id,
            component_item_id=data['component_item_id']
        ).first()
       
        if existing_detail and existing_detail.id != detail_id:
            return jsonify({'message': 'This component is already part of the BOM'}), 400
       
        detail.component_item_id = data['component_item_id']
   
    db.session.commit()
   
    component = Item.query.get(detail.component_item_id)
    component_category = Category.query.get(component.category_id) if component and component.category_id else None
   
    return jsonify({
        'id': detail.id,
        'bom_id': detail.bom_id,
        'component_item_id': detail.component_item_id,
        'component_name': component.name if component else 'Unknown Component',
        'component_category_id': component.category_id if component else None,
        'component_category_name': component_category.name if component_category else 'Uncategorized',
        'quantity_required': detail.quantity_required,
        'unit_of_measure': detail.unit_of_measure
    })

@bom_bp.route('/api/bom/details/<int:detail_id>', methods=['DELETE'])
@login_required
def delete_bom_detail(detail_id):
    detail = BOMDetail.query.get_or_404(detail_id)
    db.session.delete(detail)
    db.session.commit()
   
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
    for detail in bom.details:
        component = Item.query.get(detail.component_item_id)
        if not component:
            return jsonify({'message': f'Component with ID {detail.component_item_id} not found'}), 404
       
        # Calculate required quantity
        required_qty = detail.quantity_required * quantity
       
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
                    'category': component_category.name if component_category else 'Uncategorized'
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
                'quantity_produced': quantity
            }
        })
       
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Error during production: {str(e)}'}), 500

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
    
    # Group components by category for cost analysis
    category_costs = {}
   
    for detail in bom.details:
        component = Item.query.get(detail.component_item_id)
        if not component:
            return jsonify({'message': f'Component with ID {detail.component_item_id} not found'}), 404
        
        component_category = Category.query.get(component.category_id) if component and component.category_id else None
        category_name = component_category.name if component_category else 'Uncategorized'
       
        component_cost = component.cost * detail.quantity_required
        total_cost += component_cost
        
        # Add to category costs
        if category_name not in category_costs:
            category_costs[category_name] = 0
        category_costs[category_name] += component_cost
       
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
    
    # Format category costs for response
    category_cost_breakdown = [
        {'category': category, 'cost': cost, 'percentage': (cost / total_cost * 100) if total_cost > 0 else 0}
        for category, cost in category_costs.items()
    ]
   
    return jsonify({
        'final_product': {
            'id': final_product.id,
            'name': final_product.name,
            'category': final_product_category.name if final_product_category else 'Uncategorized',
            'selling_price': selling_price
        },
        'components': component_costs,
        'category_breakdown': category_cost_breakdown,
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
    category_dict = {category.id: category.name for category in categories}
    
    # Group items by category
    categorized_items = {}
    for item in items:
        category_name = category_dict.get(item.category_id, 'Uncategorized')
        
        if category_name not in categorized_items:
            categorized_items[category_name] = []
            
        categorized_items[category_name].append({
            'id': item.id,
            'name': item.name,
            'sku': item.sku,
            'unit_of_measure': item.unit_of_measure,
            'cost': item.cost
        })
    
    # Convert to list format for the frontend
    result = []
    for category_name, items in categorized_items.items():
        result.append({
            'category_name': category_name,
            'items': sorted(items, key=lambda x: x['name'])
        })
    
    # Sort categories alphabetically
    result.sort(key=lambda x: x['category_name'])
    
    return jsonify(result)

# Add a route for the BOM management page
@bom_bp.route('/bom-management')
@login_required
def bom_management_page():
    return render_template('bom_management.html')

