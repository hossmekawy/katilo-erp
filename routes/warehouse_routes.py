from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required
# Add this to the imports at the top
from models import db, Warehouse, Inventory, WarehouseSection, WarehouseSlot, InventoryTransaction, Item, Category

# Create blueprint
warehouse_bp = Blueprint('warehouse_bp', __name__)

@warehouse_bp.route('/warehouses-management')
@login_required
def warehouses_page():
    return render_template('warehouses.html')

@warehouse_bp.route('/warehouse-layout')
@login_required
def warehouse_layout_page():
    return render_template('warehouse_layout.html')

@warehouse_bp.route('/api/warehouses', methods=['GET'])
@login_required
def get_warehouses():
    warehouses = Warehouse.query.all()
    return jsonify([{
        'id': w.id,
        'name': w.name,
        'location': w.location,
        'capacity': w.capacity,
        'contact_info': w.contact_info,
        'item_location': w.item_location
    } for w in warehouses])

@warehouse_bp.route('/api/warehouses', methods=['POST'])
@login_required
def create_warehouse():
    data = request.get_json()
    
    # Validate required fields
    if not data.get('name'):
        return jsonify({'message': 'اسم المستودع مطلوب'}), 400
    
    warehouse = Warehouse(
        name=data['name'],
        location=data.get('location'),
        capacity=data.get('capacity'),
        contact_info=data.get('contact_info'),
        item_location=data.get('item_location')
    )
    
    db.session.add(warehouse)
    
    try:
        db.session.commit()
        return jsonify({
            'id': warehouse.id,
            'name': warehouse.name,
            'location': warehouse.location,
            'capacity': warehouse.capacity,
            'contact_info': warehouse.contact_info,
            'item_location': warehouse.item_location
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'حدث خطأ أثناء إنشاء المستودع: {str(e)}'}), 500

@warehouse_bp.route('/api/warehouses/<int:id>', methods=['PUT'])
@login_required
def update_warehouse(id):
    warehouse = Warehouse.query.get_or_404(id)
    data = request.get_json()
    
    # Update fields
    if 'name' in data and data['name']:
        warehouse.name = data['name']
    if 'location' in data:
        warehouse.location = data['location']
    if 'capacity' in data:
        warehouse.capacity = data['capacity']
    if 'contact_info' in data:
        warehouse.contact_info = data['contact_info']
    if 'item_location' in data:
        warehouse.item_location = data['item_location']
    
    try:
        db.session.commit()
        return jsonify({
            'id': warehouse.id,
            'name': warehouse.name,
            'location': warehouse.location,
            'capacity': warehouse.capacity,
            'contact_info': warehouse.contact_info,
            'item_location': warehouse.item_location
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'حدث خطأ أثناء تحديث المستودع: {str(e)}'}), 500

@warehouse_bp.route('/api/warehouses/<int:id>', methods=['DELETE'])
@login_required
def delete_warehouse(id):
    warehouse = Warehouse.query.get_or_404(id)
    
    # Check if warehouse has inventory items
    inventory_count = Inventory.query.filter_by(warehouse_id=id).count()
    if inventory_count > 0:
        return jsonify({
            'message': f'لا يمكن حذف المستودع لأنه يحتوي على {inventory_count} عنصر في المخزون. قم بنقل العناصر أولاً.'
        }), 400
    
    # Check if warehouse has sections
    sections_count = WarehouseSection.query.filter_by(warehouse_id=id).count()
    if sections_count > 0:
        return jsonify({
            'message': f'لا يمكن حذف المستودع لأنه يحتوي على {sections_count} قسم. قم بحذف الأقسام أولاً.'
        }), 400
    
    # Check if warehouse has transactions
    transactions_count = InventoryTransaction.query.filter_by(warehouse_id=id).count()
    if transactions_count > 0:
        return jsonify({
            'message': f'لا يمكن حذف المستودع لأنه مرتبط بـ {transactions_count} معاملة. قم بحذف المعاملات أولاً أو استخدم مستودع آخر.'
        }), 400
    
    try:
        db.session.delete(warehouse)
        db.session.commit()
        return '', 204
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'حدث خطأ أثناء حذف المستودع: {str(e)}'}), 500

@warehouse_bp.route('/api/warehouses/<int:id>/inventory', methods=['GET'])
@login_required
def get_warehouse_inventory(id):
    # Check if warehouse exists
    warehouse = Warehouse.query.get_or_404(id)
    
    # Get all inventory items for this warehouse
    inventory_items = db.session.query(
        Inventory, Item, Category
    ).join(
        Item, Inventory.item_id == Item.id
    ).join(
        Category, Item.category_id == Category.id
    ).filter(
        Inventory.warehouse_id == id
    ).all()
    
    result = []
    for inv, item, category in inventory_items:
        result.append({
            'id': inv.id,
            'item_id': item.id,
            'name': item.name,
            'sku': item.sku,
            'category_id': category.id,
            'category_name': category.name,
            'quantity': inv.quantity,
            'unit_of_measure': item.unit_of_measure,
            'reorder_level': item.reorder_level,
            'cost': item.cost,
            'price': item.price,
            'last_updated': inv.last_updated.isoformat() if inv.last_updated else None
        })
    
    return jsonify(result)

# Warehouse Section Routes
@warehouse_bp.route('/api/warehouse-sections', methods=['GET'])
@login_required
def get_warehouse_sections():
    sections = WarehouseSection.query.all()
    return jsonify([{
        'id': s.id,
        'warehouse_id': s.warehouse_id,
        'section_name': s.section_name,
        'row_count': s.row_count,
        'column_count': s.column_count
    } for s in sections])

@warehouse_bp.route('/api/warehouse-sections', methods=['POST'])
@login_required
def create_warehouse_section():
    data = request.get_json()
    section = WarehouseSection(
        warehouse_id=data['warehouse_id'],
        section_name=data['section_name'],
        row_count=data.get('row_count', 10),
        column_count=data.get('column_count', 10)
    )
    db.session.add(section)
    db.session.commit()
    return jsonify({
        'id': section.id,
        'section_name': section.section_name,
        'warehouse_id': section.warehouse_id
    }), 201

@warehouse_bp.route('/api/warehouse-sections/<int:id>', methods=['PUT'])
@login_required
def update_warehouse_section(id):
    section = WarehouseSection.query.get_or_404(id)
    data = request.get_json()
    for key, value in data.items():
        if hasattr(section, key):
            setattr(section, key, value)
    db.session.commit()
    return jsonify({
        'id': section.id,
        'section_name': section.section_name,
        'row_count': section.row_count,
        'column_count': section.column_count
    })

@warehouse_bp.route('/api/warehouse-sections/<int:id>', methods=['DELETE'])
@login_required
def delete_warehouse_section(id):
    section = WarehouseSection.query.get_or_404(id)
    db.session.delete(section)
    db.session.commit()
    return '', 204

@warehouse_bp.route('/api/warehouse-sections/<int:id>/slots', methods=['GET'])
@login_required
def get_section_slots(id):
    slots = WarehouseSlot.query.filter_by(section_id=id).all()
    return jsonify([{
        'id': s.id,
        'row_number': s.row_number,
        'column_number': s.column_number,
        'item_id': s.item_id,
        'quantity': s.quantity
    } for s in slots])

@warehouse_bp.route('/api/warehouses/<int:id>/sections', methods=['GET'])
@login_required
def get_warehouse_layout(id):
    sections = WarehouseSection.query.filter_by(warehouse_id=id).all()
    return jsonify([{
        'id': s.id,
        'section_name': s.section_name,
        'row_count': s.row_count,
        'column_count': s.column_count,
        'slots': [{
            'id': slot.id,
            'row_number': slot.row_number,
            'column_number': slot.column_number,
            'item_id': slot.item_id,
            'quantity': slot.quantity
        } for slot in s.slots]
    } for s in sections])

# Add these routes to warehouse_routes.py

@warehouse_bp.route('/api/warehouse-slots', methods=['GET'])
@login_required
def get_warehouse_slots():
    slots = WarehouseSlot.query.all()
    return jsonify([{
        'id': s.id,
        'section_id': s.section_id,
        'row_number': s.row_number,
        'column_number': s.column_number,
        'item_id': s.item_id,
        'quantity': s.quantity
    } for s in slots])

@warehouse_bp.route('/api/warehouse-slots', methods=['POST'])
@login_required
def create_warehouse_slot():
    data = request.get_json()
    slot = WarehouseSlot(
        section_id=data['section_id'],
        row_number=data['row_number'],
        column_number=data['column_number'],
        item_id=data.get('item_id'),
        quantity=data.get('quantity', 0)
    )
    db.session.add(slot)
    db.session.commit()
    return jsonify({
        'id': slot.id,
        'section_id': slot.section_id,
        'row_number': slot.row_number,
        'column_number': slot.column_number
    }), 201

@warehouse_bp.route('/api/warehouse-slots/<int:id>', methods=['PUT'])
@login_required
def update_warehouse_slot(id):
    slot = WarehouseSlot.query.get_or_404(id)
    data = request.get_json()
    for key, value in data.items():
        if hasattr(slot, key):
            setattr(slot, key, value)
    db.session.commit()
    return jsonify({
        'id': slot.id,
        'section_id': slot.section_id,
        'item_id': slot.item_id,
        'quantity': slot.quantity
    })

@warehouse_bp.route('/api/warehouse-slots/<int:id>', methods=['DELETE'])
@login_required
def delete_warehouse_slot(id):
    slot = WarehouseSlot.query.get_or_404(id)
    db.session.delete(slot)
    db.session.commit()
    return '', 204
