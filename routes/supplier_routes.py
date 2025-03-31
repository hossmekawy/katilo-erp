from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from models import db, Supplier, SupplierItem, Item, Category, Inventory, InventoryTransaction, Warehouse, PurchaseOrder, PurchaseOrderDetail
from datetime import datetime

supplier_bp = Blueprint('supplier_bp', __name__)

# ================= TEMPLATE ROUTES =================

@supplier_bp.route('/suppliers-management')
@login_required
def suppliers_page():
    return render_template('suppliers.html')

@supplier_bp.route('/supplier-items-management')
@login_required
def supplier_items_page():
    return render_template('supplier_items.html')

# ================= API ROUTES =================

# Supplier Routes
@supplier_bp.route('/api/suppliers', methods=['GET'])
@login_required
def get_suppliers():
    suppliers = Supplier.query.all()
    return jsonify([{
        'id': s.id,
        'supplier_name': s.supplier_name,
        'contact_info': s.contact_info,
        'payment_terms': s.payment_terms,
        'rating': s.rating,
        'email': s.email,
        'phone': s.phone,
        'address': s.address,
        'tax_id': s.tax_id,
        'website': s.website,
        'contact_person': s.contact_person
    } for s in suppliers])

@supplier_bp.route('/api/suppliers/<int:id>', methods=['GET'])
@login_required
def get_supplier(id):
    supplier = Supplier.query.get_or_404(id)
    return jsonify({
        'id': supplier.id,
        'supplier_name': supplier.supplier_name,
        'contact_info': supplier.contact_info,
        'payment_terms': supplier.payment_terms,
        'rating': supplier.rating,
        'email': supplier.email,
        'phone': supplier.phone,
        'address': supplier.address,
        'tax_id': supplier.tax_id,
        'website': supplier.website,
        'contact_person': supplier.contact_person
    })

@supplier_bp.route('/api/suppliers', methods=['POST'])
@login_required
def create_supplier():
    data = request.get_json()
    
    # Validate required fields
    if not data.get('supplier_name'):
        return jsonify({'message': 'اسم المورد مطلوب'}), 400
    
    supplier = Supplier(
        supplier_name=data['supplier_name'],
        contact_info=data.get('contact_info'),
        payment_terms=data.get('payment_terms'),
        rating=data.get('rating'),
        email=data.get('email'),
        phone=data.get('phone'),
        address=data.get('address'),
        tax_id=data.get('tax_id'),
        website=data.get('website'),
        contact_person=data.get('contact_person')
    )
    
    db.session.add(supplier)
    db.session.commit()
    
    return jsonify({
        'id': supplier.id,
        'supplier_name': supplier.supplier_name,
        'contact_info': supplier.contact_info,
        'payment_terms': supplier.payment_terms,
        'rating': supplier.rating,
        'email': supplier.email,
        'phone': supplier.phone,
        'address': supplier.address,
        'tax_id': supplier.tax_id,
        'website': supplier.website,
        'contact_person': supplier.contact_person
    }), 201

@supplier_bp.route('/api/suppliers/<int:id>', methods=['PUT'])
@login_required
def update_supplier(id):
    supplier = Supplier.query.get_or_404(id)
    data = request.get_json()
    
    if 'supplier_name' in data:
        supplier.supplier_name = data['supplier_name']
    if 'contact_info' in data:
        supplier.contact_info = data['contact_info']
    if 'payment_terms' in data:
        supplier.payment_terms = data['payment_terms']
    if 'rating' in data:
        supplier.rating = data['rating']
    if 'email' in data:
        supplier.email = data['email']
    if 'phone' in data:
        supplier.phone = data['phone']
    if 'address' in data:
        supplier.address = data['address']
    if 'tax_id' in data:
        supplier.tax_id = data['tax_id']
    if 'website' in data:
        supplier.website = data['website']
    if 'contact_person' in data:
        supplier.contact_person = data['contact_person']
    
    db.session.commit()
    
    return jsonify({
        'id': supplier.id,
        'supplier_name': supplier.supplier_name,
        'contact_info': supplier.contact_info,
        'payment_terms': supplier.payment_terms,
        'rating': supplier.rating,
        'email': supplier.email,
        'phone': supplier.phone,
        'address': supplier.address,
        'tax_id': supplier.tax_id,
        'website': supplier.website,
        'contact_person': supplier.contact_person
    })

@supplier_bp.route('/api/suppliers/<int:id>', methods=['DELETE'])
@login_required
def delete_supplier(id):
    supplier = Supplier.query.get_or_404(id)
    
    # Check if supplier has any items
    supplier_items = SupplierItem.query.filter_by(supplier_id=id).first()
    if supplier_items:
        return jsonify({'message': 'لا يمكن حذف المورد لأنه مرتبط بعناصر'}), 400
    
    db.session.delete(supplier)
    db.session.commit()
    
    return '', 204

# Supplier Item Routes
@supplier_bp.route('/api/supplier-items', methods=['GET'])
@login_required
def get_supplier_items():
    supplier_items = SupplierItem.query.all()
    result = []
    
    for si in supplier_items:
        item = Item.query.get(si.item_id)
        supplier = Supplier.query.get(si.supplier_id)
        
        result.append({
            'id': si.id,
            'supplier_id': si.supplier_id,
            'supplier_name': supplier.supplier_name if supplier else None,
            'item_id': si.item_id,
            'item_name': item.name if item else None,
            'supplier_sku': si.supplier_sku,
            'cost': si.cost
        })
    
    return jsonify(result)

@supplier_bp.route('/api/supplier-items/<int:id>', methods=['GET'])
@login_required
def get_supplier_item(id):
    supplier_item = SupplierItem.query.get_or_404(id)
    item = Item.query.get(supplier_item.item_id)
    supplier = Supplier.query.get(supplier_item.supplier_id)
    
    return jsonify({
        'id': supplier_item.id,
        'supplier_id': supplier_item.supplier_id,
        'supplier_name': supplier.supplier_name if supplier else None,
        'item_id': supplier_item.item_id,
        'item_name': item.name if item else None,
        'supplier_sku': supplier_item.supplier_sku,
        'cost': supplier_item.cost
    })

@supplier_bp.route('/api/supplier-items', methods=['POST'])
@login_required
def create_supplier_item():
    data = request.get_json()
    
    # Validate required fields
    if not data.get('supplier_id') or not data.get('item_id') or 'cost' not in data:
        return jsonify({'message': 'المورد والعنصر والتكلفة مطلوبة'}), 400
    
    # Check if supplier exists
    supplier = Supplier.query.get(data['supplier_id'])
    if not supplier:
        return jsonify({'message': 'المورد غير موجود'}), 400
    
    # Check if item exists
    item = Item.query.get(data['item_id'])
    if not item:
        return jsonify({'message': 'العنصر غير موجود'}), 400
    
    # Check if this supplier-item combination already exists
    existing = SupplierItem.query.filter_by(
        supplier_id=data['supplier_id'],
        item_id=data['item_id']
    ).first()
    
    if existing:
        return jsonify({'message': 'هذا العنصر مرتبط بالفعل بهذا المورد'}), 400
    
    supplier_item = SupplierItem(
        supplier_id=data['supplier_id'],
        item_id=data['item_id'],
        supplier_sku=data.get('supplier_sku'),
        cost=data['cost']
    )
    
    db.session.add(supplier_item)
    db.session.commit()
    
    return jsonify({
        'id': supplier_item.id,
        'supplier_id': supplier_item.supplier_id,
        'supplier_name': supplier.supplier_name,
        'item_id': supplier_item.item_id,
        'item_name': item.name,
        'supplier_sku': supplier_item.supplier_sku,
        'cost': supplier_item.cost
    }), 201

@supplier_bp.route('/api/supplier-items/<int:id>', methods=['PUT'])
@login_required
def update_supplier_item(id):
    supplier_item = SupplierItem.query.get_or_404(id)
    data = request.get_json()
    
    if 'supplier_sku' in data:
        supplier_item.supplier_sku = data['supplier_sku']
    if 'cost' in data:
        supplier_item.cost = data['cost']
    
    db.session.commit()
    
    item = Item.query.get(supplier_item.item_id)
    supplier = Supplier.query.get(supplier_item.supplier_id)
    
    return jsonify({
        'id': supplier_item.id,
        'supplier_id': supplier_item.supplier_id,
        'supplier_name': supplier.supplier_name if supplier else None,
        'item_id': supplier_item.item_id,
        'item_name': item.name if item else None,
        'supplier_sku': supplier_item.supplier_sku,
        'cost': supplier_item.cost
    })

@supplier_bp.route('/api/supplier-items/<int:id>', methods=['DELETE'])
@login_required
def delete_supplier_item(id):
    supplier_item = SupplierItem.query.get_or_404(id)
    db.session.delete(supplier_item)
    db.session.commit()
    
    return '', 204

# Additional utility endpoints
@supplier_bp.route('/api/suppliers/<int:supplier_id>/items', methods=['GET'])
@login_required
def get_supplier_items_by_supplier(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    supplier_items = SupplierItem.query.filter_by(supplier_id=supplier_id).all()
    
    result = []
    for si in supplier_items:
        item = Item.query.get(si.item_id)
        result.append({
            'id': si.id,
            'item_id': si.item_id,
            'item_name': item.name if item else None,
            'sku': item.sku if item else None,
            'supplier_sku': si.supplier_sku,
            'cost': si.cost,
            'reorder_level': item.reorder_level if item else None
        })
    
    return jsonify(result)

@supplier_bp.route('/api/items/<int:item_id>/suppliers', methods=['GET'])
@login_required
def get_item_suppliers(item_id):
    item = Item.query.get_or_404(item_id)
    supplier_items = SupplierItem.query.filter_by(item_id=item_id).all()
    
    result = []
    for si in supplier_items:
        supplier = Supplier.query.get(si.supplier_id)
        result.append({
            'id': si.id,
            'supplier_id': si.supplier_id,
            'supplier_name': supplier.supplier_name if supplier else None,
            'supplier_sku': si.supplier_sku,
            'cost': si.cost
        })
    
    return jsonify(result)

# Get best supplier for an item (lowest cost)
@supplier_bp.route('/api/items/<int:item_id>/best-supplier', methods=['GET'])
@login_required
def get_best_supplier_for_item(item_id):
    item = Item.query.get_or_404(item_id)
    
    best_supplier_item = SupplierItem.query.filter_by(item_id=item_id).order_by(SupplierItem.cost).first()
    
    if not best_supplier_item:
        return jsonify({'message': 'لا يوجد موردين لهذا العنصر'}), 404
    
    supplier = Supplier.query.get(best_supplier_item.supplier_id)
    
    return jsonify({
        'supplier_item_id': best_supplier_item.id,
        'supplier_id': best_supplier_item.supplier_id,
        'supplier_name': supplier.supplier_name if supplier else None,
        'supplier_sku': best_supplier_item.supplier_sku,
        'cost': best_supplier_item.cost
    })

@supplier_bp.route('/api/suppliers/<int:supplier_id>/inventory', methods=['GET'])
@login_required
def get_supplier_inventory(supplier_id):
    """Get inventory for all items supplied by a specific supplier"""
    supplier = Supplier.query.get_or_404(supplier_id)
    
    # Get all items from this supplier
    supplier_items = SupplierItem.query.filter_by(supplier_id=supplier_id).all()
    item_ids = [si.item_id for si in supplier_items]
    
    # Get inventory for these items
    inventory_items = Inventory.query.filter(Inventory.item_id.in_(item_ids)).all()
    
    result = []
    for inv in inventory_items:
        item = Item.query.get(inv.item_id)
        warehouse = Warehouse.query.get(inv.warehouse_id)
        supplier_item = SupplierItem.query.filter_by(supplier_id=supplier_id, item_id=inv.item_id).first()
        
        result.append({
            'inventory_id': inv.id,
            'item_id': inv.item_id,
            'item_name': item.name if item else None,
            'warehouse_id': inv.warehouse_id,
            'warehouse_name': warehouse.name if warehouse else None,
            'quantity': inv.quantity,
            'supplier_sku': supplier_item.supplier_sku if supplier_item else None,
            'supplier_cost': supplier_item.cost if supplier_item else None,
            'last_updated': inv.last_updated.isoformat()
        })
    
    return jsonify(result)

@supplier_bp.route('/api/suppliers/<int:supplier_id>/restock', methods=['POST'])
@login_required
def restock_from_supplier(supplier_id):
    """Create a transaction to restock inventory from a specific supplier"""
    supplier = Supplier.query.get_or_404(supplier_id)
    data = request.get_json()
    
    # Validate required fields
    if not data.get('item_id') or not data.get('warehouse_id') or 'quantity' not in data:
        return jsonify({'message': 'العنصر والمستودع والكمية مطلوبة'}), 400
    
    item_id = data['item_id']
    warehouse_id = data['warehouse_id']
    quantity = data['quantity']
    
    # Verify this supplier supplies this item
    supplier_item = SupplierItem.query.filter_by(supplier_id=supplier_id, item_id=item_id).first()
    if not supplier_item:
        return jsonify({'message': 'هذا المورد لا يوفر هذا العنصر'}), 400
    
    # Get current inventory record
    inventory = Inventory.query.filter_by(
        item_id=item_id,
        warehouse_id=warehouse_id
    ).first()
    
    # Create new inventory record if it doesn't exist
    if not inventory:
        inventory = Inventory(
            item_id=item_id,
            warehouse_id=warehouse_id,
            quantity=quantity
        )
        db.session.add(inventory)
    else:
        # Update existing inventory
        inventory.quantity += quantity
    
    # Create transaction record
    reference = f"Restock from supplier: {supplier.supplier_name}"
    transaction = InventoryTransaction(
        item_id=item_id,
        warehouse_id=warehouse_id,
        transaction_type='IN',
        quantity=quantity,
        reference=reference
    )
    db.session.add(transaction)
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Database error: {str(e)}'}), 500
    
    return jsonify({
        'inventory_id': inventory.id,
        'quantity': inventory.quantity,
        'transaction_id': transaction.id
    })

# Purchase Order Routes related to suppliers
@supplier_bp.route('/api/suppliers/<int:supplier_id>/purchase-orders', methods=['GET'])
@login_required
def get_supplier_purchase_orders(supplier_id):
    """Get all purchase orders for a specific supplier"""
    supplier = Supplier.query.get_or_404(supplier_id)
    
    purchase_orders = PurchaseOrder.query.filter_by(supplier_id=supplier_id).all()
    
    result = []
    for po in purchase_orders:
        # Get total items and total amount
        po_details = PurchaseOrderDetail.query.filter_by(po_id=po.id).all()
        total_items = len(po_details)
        
        result.append({
            'id': po.id,
            'order_date': po.order_date.isoformat() if po.order_date else None,
            'status': po.status,
            'total_amount': po.total_amount,
            'total_items': total_items
        })
    
    return jsonify(result)

# In supplier_routes.py, modify the create_purchase_order function:

@supplier_bp.route('/api/purchase-orders', methods=['POST'])
@login_required
def create_purchase_order():
    """Create a new purchase order"""
    data = request.get_json()
    
    # Validate required fields
    if not data.get('supplier_id') or not data.get('items') or len(data['items']) == 0:
        return jsonify({'message': 'المورد والعناصر مطلوبة'}), 400
    
    supplier_id = data['supplier_id']
    
    # Verify supplier exists
    supplier = Supplier.query.get(supplier_id)
    if not supplier:
        return jsonify({'message': 'المورد غير موجود'}), 400
    
    # Calculate total amount
    total_amount = 0
    for item in data['items']:
        if 'quantity_ordered' not in item or 'unit_price' not in item:
            return jsonify({'message': 'الكمية والسعر مطلوبان لكل عنصر'}), 400
        
        # Convert values to float before multiplication
        quantity = float(item['quantity_ordered'])
        price = float(item['unit_price'])
        total_amount += quantity * price
    
    # Create purchase order
    purchase_order = PurchaseOrder(
        supplier_id=supplier_id,
        order_date=datetime.utcnow(),
        status='Pending',
        total_amount=total_amount
    )
    
    db.session.add(purchase_order)
    db.session.flush()  # Get ID without committing
    
    # Create purchase order details
    for item in data['items']:
        po_detail = PurchaseOrderDetail(
            po_id=purchase_order.id,
            item_id=item['item_id'],
            quantity_ordered=int(item['quantity_ordered']),  # Convert to int
            unit_price=float(item['unit_price']),  # Convert to float
            quantity_received=0
        )
        db.session.add(po_detail)
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Database error: {str(e)}'}), 500
    
    return jsonify({
        'id': purchase_order.id,
        'supplier_id': purchase_order.supplier_id,
        'order_date': purchase_order.order_date.isoformat(),
        'status': purchase_order.status,
        'total_amount': purchase_order.total_amount
    }), 201

@supplier_bp.route('/api/items/<int:item_id>/low-stock-suppliers', methods=['GET'])
@login_required
def get_low_stock_suppliers(item_id):
    """Get suppliers for a low stock item, sorted by rating and cost"""
    item = Item.query.get_or_404(item_id)
    
    # Get all suppliers for this item
    supplier_items = SupplierItem.query.filter_by(item_id=item_id).all()
    
    result = []
    for si in supplier_items:
        supplier = Supplier.query.get(si.supplier_id)
        if supplier:
            result.append({
                'supplier_item_id': si.id,
                'supplier_id': si.supplier_id,
                'supplier_name': supplier.supplier_name,
                'contact_info': supplier.contact_info,
                'payment_terms': supplier.payment_terms,
                'supplier_sku': si.supplier_sku,
                'cost': si.cost,
                'rating': supplier.rating or 0
            })
    
    # Sort by rating (highest first) and then by cost (lowest first)
    result.sort(key=lambda x: (-x['rating'], x['cost']))
    
    return jsonify(result)

@supplier_bp.route('/api/suppliers/search', methods=['GET'])
@login_required
def search_suppliers():
    """Search suppliers by name or contact info"""
    query = request.args.get('q', '')
    
    if not query or len(query) < 2:
        return jsonify([])
    
    # Search for suppliers matching the query
    suppliers = Supplier.query.filter(
        (Supplier.supplier_name.ilike(f'%{query}%')) | 
        (Supplier.contact_info.ilike(f'%{query}%'))
    ).all()
    
    result = [{
        'id': s.id,
        'supplier_name': s.supplier_name,
        'contact_info': s.contact_info,
        'payment_terms': s.payment_terms,
        'rating': s.rating
    } for s in suppliers]
    
    return jsonify(result)

@supplier_bp.route('/api/suppliers/stats', methods=['GET'])
@login_required
def get_supplier_stats():
    """Get statistics about suppliers"""
    # Total number of suppliers
    total_suppliers = Supplier.query.count()
    
    # Average supplier rating
    avg_rating_result = db.session.query(db.func.avg(Supplier.rating)).filter(Supplier.rating != None).first()
    avg_rating = float(avg_rating_result[0]) if avg_rating_result[0] else 0
    
    # Number of items with suppliers
    items_with_suppliers = db.session.query(db.func.count(db.distinct(SupplierItem.item_id))).scalar()
    
    # Total number of items
    total_items = Item.query.count()
    
    # Items without suppliers
    items_without_suppliers = total_items - items_with_suppliers
    
    # Top rated suppliers (limit to 5)
    top_suppliers = Supplier.query.filter(Supplier.rating != None).order_by(Supplier.rating.desc()).limit(5).all()
    top_suppliers_data = [{
        'id': s.id,
        'supplier_name': s.supplier_name,
        'rating': s.rating
    } for s in top_suppliers]
    
    return jsonify({
        'total_suppliers': total_suppliers,
        'avg_rating': avg_rating,
        'items_with_suppliers': items_with_suppliers,
        'items_without_suppliers': items_without_suppliers,
        'top_suppliers': top_suppliers_data
    })
