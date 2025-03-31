import base64
from io import BytesIO
import os
from flask import Blueprint, current_app, request, jsonify, render_template, send_file
from flask_login import login_required, current_user
import pdfkit
from models import (
    db, Supplier, SupplierItem, Item, Inventory, 
    InventoryTransaction, Warehouse, PurchaseOrder, PurchaseOrderDetail,SupplierLedgerEntry,SupplierPayment,
)
from datetime import datetime

purchase_order_bp = Blueprint('purchase_order_bp', __name__)

# ================= TEMPLATE ROUTES =================

@purchase_order_bp.route('/purchase-orders')
@login_required
def purchase_orders_page():
    return render_template('purchase_orders.html')

@purchase_order_bp.route('/purchase-orders/<int:id>')
@login_required
def purchase_order_details_page(id):
    purchase_order = PurchaseOrder.query.get_or_404(id)
    return render_template('purchase_order_details.html', order_id=id)

@purchase_order_bp.route('/supplier-accounts')
@login_required
def supplier_accounts_page():
    return render_template('supplier_accounts.html')

@purchase_order_bp.route('/supplier-accounts/<int:supplier_id>')
@login_required
def supplier_account_details_page(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    return render_template('supplier_account_details.html', supplier_id=supplier_id)


# ================= API ROUTES =================

@purchase_order_bp.route('/api/purchase-orders', methods=['GET'])
@login_required
def get_purchase_orders():
    """Get all purchase orders"""
    purchase_orders = PurchaseOrder.query.all()
    
    result = []
    for po in purchase_orders:
        supplier = Supplier.query.get(po.supplier_id)
        po_details = PurchaseOrderDetail.query.filter_by(po_id=po.id).all()
        
        result.append({
            'id': po.id,
            'supplier_id': po.supplier_id,
            'supplier_name': supplier.supplier_name if supplier else 'Unknown',
            'order_date': po.order_date.isoformat() if po.order_date else None,
            'status': po.status,
            'total_amount': po.total_amount,
            'items_count': len(po_details)
        })
    
    return jsonify(result)

@purchase_order_bp.route('/api/purchase-orders/<int:id>', methods=['GET'])
@login_required
def get_purchase_order(id):
    """Get a specific purchase order with its details"""
    purchase_order = PurchaseOrder.query.get_or_404(id)
    supplier = Supplier.query.get(purchase_order.supplier_id)
    po_details = PurchaseOrderDetail.query.filter_by(po_id=id).all()
    
    details = []
    for detail in po_details:
        item = Item.query.get(detail.item_id)
        details.append({
            'id': detail.id,
            'item_id': detail.item_id,
            'item_name': item.name if item else 'Unknown',
            'sku': item.sku if item else None,
            'quantity_ordered': detail.quantity_ordered,
            'quantity_received': detail.quantity_received,
            'unit_price': detail.unit_price,
            'subtotal': detail.quantity_ordered * detail.unit_price
        })
    
    return jsonify({
        'id': purchase_order.id,
        'supplier_id': purchase_order.supplier_id,
        'supplier_name': supplier.supplier_name if supplier else 'Unknown',
        'order_date': purchase_order.order_date.isoformat() if purchase_order.order_date else None,
        'status': purchase_order.status,
        'total_amount': purchase_order.total_amount,
        'details': details
    })

# Update the create_purchase_order function to add a ledger entry
@purchase_order_bp.route('/api/purchase-orders', methods=['POST'])
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
    
    # Create ledger entry for this purchase order
    ledger_entry = SupplierLedgerEntry(
        supplier_id=supplier_id,
        entry_date=purchase_order.order_date,
        description="طلب شراء",
        reference_type='purchase_order',
        reference_id=purchase_order.id,
        debit=total_amount  # Debit increases when we order from supplier
    )
    db.session.add(ledger_entry)
    
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


@purchase_order_bp.route('/api/purchase-orders/<int:id>', methods=['PUT'])
@login_required
def update_purchase_order(id):
    """Update a purchase order's status"""
    purchase_order = PurchaseOrder.query.get_or_404(id)
    data = request.get_json()
    
    if 'status' in data:
        purchase_order.status = data['status']
    
    db.session.commit()
    
    return jsonify({
        'id': purchase_order.id,
        'status': purchase_order.status
    })


@purchase_order_bp.route('/api/purchase-orders/<int:id>/cancel', methods=['POST'])
@login_required
def cancel_purchase_order(id):
    """Cancel a purchase order"""
    purchase_order = PurchaseOrder.query.get_or_404(id)
    
    if purchase_order.status == 'Received':
        return jsonify({'message': 'لا يمكن إلغاء طلب تم استلامه بالفعل'}), 400
    
    purchase_order.status = 'Cancelled'
    db.session.commit()
    
    return jsonify({
        'id': purchase_order.id,
        'status': purchase_order.status,
        'message': 'تم إلغاء الطلب بنجاح'
    })

@purchase_order_bp.route('/api/suppliers/<int:supplier_id>/purchase-orders', methods=['GET'])
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

@purchase_order_bp.route('/api/purchase-orders/stats', methods=['GET'])
@login_required
def get_purchase_order_stats():
    """Get statistics about purchase orders"""
    # Total number of purchase orders
    total_pos = PurchaseOrder.query.count()
    
    # Count by status
    pending_count = PurchaseOrder.query.filter_by(status='Pending').count()
    approved_count = PurchaseOrder.query.filter_by(status='Approved').count()
    received_count = PurchaseOrder.query.filter_by(status='Received').count()
    cancelled_count = PurchaseOrder.query.filter_by(status='Cancelled').count()
    
    # Total amount of all purchase orders
    total_amount_result = db.session.query(db.func.sum(PurchaseOrder.total_amount)).first()
    total_amount = float(total_amount_result[0]) if total_amount_result[0] else 0
    
    # Recent purchase orders (limit to 5)
    recent_pos = PurchaseOrder.query.order_by(PurchaseOrder.order_date.desc()).limit(5).all()
    recent_pos_data = []
    
    for po in recent_pos:
        supplier = Supplier.query.get(po.supplier_id)
        recent_pos_data.append({
            'id': po.id,
            'supplier_name': supplier.supplier_name if supplier else 'Unknown',
            'order_date': po.order_date.isoformat() if po.order_date else None,
            'status': po.status,
            'total_amount': po.total_amount
        })
    
    return jsonify({
        'total_purchase_orders': total_pos,
        'status_counts': {
            'pending': pending_count,
            'approved': approved_count,
            'received': received_count,
            'cancelled': cancelled_count
        },
        'total_amount': total_amount,
        'recent_purchase_orders': recent_pos_data
    })

@purchase_order_bp.route('/api/purchase-orders/search', methods=['GET'])
@login_required
def search_purchase_orders():
    """Search purchase orders by supplier name or status"""
    query = request.args.get('q', '')
    status = request.args.get('status', '')
    
    # Base query
    purchase_orders_query = PurchaseOrder.query
    
    # Apply status filter if provided
    if status:
        purchase_orders_query = purchase_orders_query.filter_by(status=status)
    
    # Apply search filter if provided
    if query and len(query) >= 2:
        # Join with suppliers to search by supplier name
        supplier_ids = db.session.query(Supplier.id).filter(
            Supplier.supplier_name.ilike(f'%{query}%')
        ).all()
        supplier_ids = [s[0] for s in supplier_ids]
        
        if supplier_ids:
            purchase_orders_query = purchase_orders_query.filter(
                PurchaseOrder.supplier_id.in_(supplier_ids)
            )
        else:
            # No matching suppliers, return empty result
            return jsonify([])
    
    # Execute query and format results
    purchase_orders = purchase_orders_query.all()
    result = []
    
    for po in purchase_orders:
        supplier = Supplier.query.get(po.supplier_id)
        po_details = PurchaseOrderDetail.query.filter_by(po_id=po.id).all()
        
        result.append({
            'id': po.id,
            'supplier_id': po.supplier_id,
            'supplier_name': supplier.supplier_name if supplier else 'Unknown',
            'order_date': po.order_date.isoformat() if po.order_date else None,
            'status': po.status,
            'total_amount': po.total_amount,
            'items_count': len(po_details)
        })
    
    return jsonify(result)

@purchase_order_bp.route('/api/items/<int:item_id>/purchase-history', methods=['GET'])
@login_required
def get_item_purchase_history(item_id):
    """Get purchase history for a specific item"""
    item = Item.query.get_or_404(item_id)
    
    # Get all purchase order details for this item
    po_details = PurchaseOrderDetail.query.filter_by(item_id=item_id).all()
    
    result = []
    for detail in po_details:
        po = PurchaseOrder.query.get(detail.po_id)
        if po:
            supplier = Supplier.query.get(po.supplier_id)
            result.append({
                'purchase_order_id': po.id,
                'supplier_id': po.supplier_id,
                'supplier_name': supplier.supplier_name if supplier else 'Unknown',
                'order_date': po.order_date.isoformat() if po.order_date else None,
                'status': po.status,
                'quantity_ordered': detail.quantity_ordered,
                'quantity_received': detail.quantity_received,
                'unit_price': detail.unit_price,
                'subtotal': detail.quantity_ordered * detail.unit_price
            })
    
    # Sort by order date (newest first)
    result.sort(key=lambda x: x['order_date'] if x['order_date'] else '', reverse=True)
    
    return jsonify(result)

@purchase_order_bp.route('/api/purchase-orders/<int:id>/details/<int:detail_id>', methods=['PUT'])
@login_required
def update_purchase_order_detail(id, detail_id):
    """Update a specific detail in a purchase order"""
    purchase_order = PurchaseOrder.query.get_or_404(id)
    po_detail = PurchaseOrderDetail.query.get_or_404(detail_id)
    
    # Verify the detail belongs to this purchase order
    if po_detail.po_id != id:
        return jsonify({'message': 'تفاصيل الطلب غير موجودة في هذا الطلب'}), 400
    
    # Only allow updates if the order is still pending
    if purchase_order.status != 'Pending':
        return jsonify({'message': 'لا يمكن تعديل طلب تم الموافقة عليه أو استلامه أو إلغاؤه'}), 400
    
    data = request.get_json()
    
    if 'quantity_ordered' in data:
        po_detail.quantity_ordered = int(data['quantity_ordered'])
    
    if 'unit_price' in data:
        po_detail.unit_price = float(data['unit_price'])
    
    # Recalculate total amount for the purchase order
    po_details = PurchaseOrderDetail.query.filter_by(po_id=id).all()
    total_amount = sum(detail.quantity_ordered * detail.unit_price for detail in po_details)
    purchase_order.total_amount = total_amount
    
    db.session.commit()
    
    return jsonify({
        'id': po_detail.id,
        'quantity_ordered': po_detail.quantity_ordered,
        'unit_price': po_detail.unit_price,
        'subtotal': po_detail.quantity_ordered * po_detail.unit_price,
        'purchase_order_total': purchase_order.total_amount
    })

@purchase_order_bp.route('/api/purchase-orders/<int:id>/items', methods=['POST'])
@login_required
def add_purchase_order_items(id):
    """Add a new item to an existing purchase order (alias for add_purchase_order_detail)"""
    return add_purchase_order_detail(id)

@purchase_order_bp.route('/api/purchase-orders/<int:id>/details', methods=['POST'])
@login_required
def add_purchase_order_detail(id):
    """Add a new item to an existing purchase order"""
    purchase_order = PurchaseOrder.query.get_or_404(id)
    
    # Only allow updates if the order is still pending
    if purchase_order.status != 'Pending':
        return jsonify({'message': 'لا يمكن تعديل طلب تم الموافقة عليه أو استلامه أو إلغاؤه'}), 400
    
    data = request.get_json()
    
    # Validate required fields
    if not data.get('item_id') or 'quantity_ordered' not in data or 'unit_price' not in data:
        return jsonify({'message': 'العنصر والكمية والسعر مطلوبة'}), 400
    
    # Check if item already exists in this purchase order
    existing_detail = PurchaseOrderDetail.query.filter_by(
        po_id=id, 
        item_id=data['item_id']
    ).first()
    
    if existing_detail:
        return jsonify({'message': 'هذا العنصر موجود بالفعل في الطلب'}), 400
    
    # Create new purchase order detail
    po_detail = PurchaseOrderDetail(
        po_id=id,
        item_id=data['item_id'],
        quantity_ordered=int(data['quantity_ordered']),
        unit_price=float(data['unit_price']),
        quantity_received=0
    )
    
    db.session.add(po_detail)
    
    # Recalculate total amount for the purchase order
    purchase_order.total_amount += int(data['quantity_ordered']) * float(data['unit_price'])
    
    db.session.commit()
    
    # Get item details for response
    item = Item.query.get(data['item_id'])
    
    return jsonify({
        'id': po_detail.id,
        'item_id': po_detail.item_id,
        'item_name': item.name if item else 'Unknown',
        'sku': item.sku if item else None,
        'quantity_ordered': po_detail.quantity_ordered,
        'quantity_received': po_detail.quantity_received,
        'unit_price': po_detail.unit_price,
        'subtotal': po_detail.quantity_ordered * po_detail.unit_price,
        'purchase_order_total': purchase_order.total_amount
    }), 201

@purchase_order_bp.route('/api/purchase-orders/<int:id>/details/<int:detail_id>', methods=['DELETE'])
@login_required
def delete_purchase_order_detail(id, detail_id):
    """Remove an item from a purchase order"""
    purchase_order = PurchaseOrder.query.get_or_404(id)
    po_detail = PurchaseOrderDetail.query.get_or_404(detail_id)
    
    # Verify the detail belongs to this purchase order
    if po_detail.po_id != id:
        return jsonify({'message': 'تفاصيل الطلب غير موجودة في هذا الطلب'}), 400
    
    # Only allow updates if the order is still pending
    if purchase_order.status != 'Pending':
        return jsonify({'message': 'لا يمكن تعديل طلب تم الموافقة عليه أو استلامه أو إلغاؤه'}), 400
    
    # Subtract this detail's amount from the purchase order total
    purchase_order.total_amount -= po_detail.quantity_ordered * po_detail.unit_price
    
    # Delete the detail
    db.session.delete(po_detail)
    
    # Check if this was the last item in the purchase order
    remaining_details = PurchaseOrderDetail.query.filter_by(po_id=id).count()
    
    if remaining_details == 0:
        # If no items left, delete the entire purchase order
        db.session.delete(purchase_order)
        db.session.commit()
        return jsonify({'message': 'تم حذف طلب الشراء بالكامل لأنه لم يعد يحتوي على عناصر'}), 200
    else:
        db.session.commit()
        return jsonify({'message': 'تم حذف العنصر من طلب الشراء', 'purchase_order_total': purchase_order.total_amount}), 200

@purchase_order_bp.route('/api/purchase-orders/bulk-create', methods=['POST'])
@login_required
def create_bulk_purchase_orders():
    """Create purchase orders for multiple suppliers at once (for low stock items)"""
    data = request.get_json()
    
    # Validate required fields
    if not data.get('orders') or len(data['orders']) == 0:
        return jsonify({'message': 'لا توجد طلبات للإنشاء'}), 400
    
    created_orders = []
    
    for order_data in data['orders']:
        if not order_data.get('supplier_id') or not order_data.get('items') or len(order_data['items']) == 0:
            continue
        
        supplier_id = order_data['supplier_id']
        
        # Verify supplier exists
        supplier = Supplier.query.get(supplier_id)
        if not supplier:
            continue
        
        # Calculate total amount
        total_amount = 0
        for item in order_data['items']:
            if 'quantity_ordered' not in item or 'unit_price' not in item:
                continue
            
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
        for item in order_data['items']:
            if 'item_id' not in item or 'quantity_ordered' not in item or 'unit_price' not in item:
                continue
                
            po_detail = PurchaseOrderDetail(
                po_id=purchase_order.id,
                item_id=item['item_id'],
                quantity_ordered=int(item['quantity_ordered']),
                unit_price=float(item['unit_price']),
                quantity_received=0
            )
            db.session.add(po_detail)
        
        created_orders.append({
            'id': purchase_order.id,
            'supplier_id': purchase_order.supplier_id,
            'supplier_name': supplier.supplier_name,
            'total_amount': purchase_order.total_amount
        })
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Database error: {str(e)}'}), 500
    
    return jsonify({
        'message': f'تم إنشاء {len(created_orders)} طلب شراء بنجاح',
        'created_orders': created_orders
    }), 201


@purchase_order_bp.route('/api/purchase-orders/<int:id>/receive', methods=['POST'])
@login_required
def receive_purchase_order(id):
    """Mark items in a purchase order as received and update inventory"""
    # Get the purchase order
    purchase_order = PurchaseOrder.query.get_or_404(id)
    
    # Check if the purchase order is in a valid state for receiving
    if purchase_order.status not in ['Pending', 'Approved']:
        return jsonify({'message': 'لا يمكن استلام طلب شراء بحالة ' + purchase_order.status}), 400
    
    data = request.get_json()
    warehouse_id = data.get('warehouse_id')
    items_to_receive = data.get('items', [])
    
    # Validate required fields
    if not warehouse_id:
        return jsonify({'message': 'يجب تحديد المستودع'}), 400
    
    if not items_to_receive:
        return jsonify({'message': 'يجب تحديد العناصر المستلمة'}), 400
    
    # Check if warehouse exists
    warehouse = Warehouse.query.get(warehouse_id)
    if not warehouse:
        return jsonify({'message': 'المستودع غير موجود'}), 400
    
    try:
        # Process each received item
        for item_data in items_to_receive:
            detail_id = item_data.get('detail_id')
            quantity_received = item_data.get('quantity_received', 0)
            
            if not detail_id or quantity_received <= 0:
                continue
            
            # Get the purchase order detail
            po_detail = PurchaseOrderDetail.query.get(detail_id)
            if not po_detail or po_detail.po_id != id:
                return jsonify({'message': 'تفاصيل طلب الشراء غير صحيحة'}), 400
            
            # Check if quantity is valid
            remaining_quantity = po_detail.quantity_ordered - po_detail.quantity_received
            if quantity_received > remaining_quantity:
                return jsonify({
                    'message': f'الكمية المستلمة للعنصر {po_detail.item_id} تتجاوز الكمية المتبقية'
                }), 400
            
            # Update received quantity
            po_detail.quantity_received += quantity_received
            
            # Update inventory
            inventory = Inventory.query.filter_by(
                item_id=po_detail.item_id,
                warehouse_id=warehouse_id
            ).first()
            
            if inventory:
                inventory.quantity += quantity_received
            else:
                inventory = Inventory(
                    item_id=po_detail.item_id,
                    warehouse_id=warehouse_id,
                    quantity=quantity_received
                )
                db.session.add(inventory)
            
            # Create inventory transaction record
            transaction = InventoryTransaction(
                item_id=po_detail.item_id,
                warehouse_id=warehouse_id,
                transaction_type='IN',
                quantity=quantity_received,
                reference=f'PO#{purchase_order.id}'
            )
            db.session.add(transaction)
        
        # Check if all items are fully received
        all_received = all(
            detail.quantity_ordered == detail.quantity_received
            for detail in purchase_order.details
        )
        
        # Update purchase order status if all items are received
        if all_received:
            purchase_order.status = 'Received'
        
        db.session.commit()
        
        return jsonify({
            'message': 'تم استلام العناصر بنجاح',
            'status': purchase_order.status
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'حدث خطأ أثناء استلام العناصر: {str(e)}'}), 500
    
    
    # API endpoint to get all suppliers with financial summary
    
@purchase_order_bp.route('/api/supplier-accounts/<int:supplier_id>/payments', methods=['POST'])
@login_required
def add_supplier_payment(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    data = request.get_json()
    
    # Validate required fields
    if not data.get('amount') or float(data.get('amount', 0)) <= 0:
        return jsonify({'message': 'المبلغ مطلوب ويجب أن يكون أكبر من صفر'}), 400
    
    if not data.get('date'):
        return jsonify({'message': 'تاريخ الدفع مطلوب'}), 400
    
    if not data.get('method'):
        return jsonify({'message': 'طريقة الدفع مطلوبة'}), 400
    
    try:
        # Create payment record
        payment = SupplierPayment(
            supplier_id=supplier_id,
            amount=float(data['amount']),
            payment_date=datetime.fromisoformat(data['date'].replace('Z', '+00:00')),
            payment_method=data['method'],
            reference=data.get('reference', ''),
            notes=data.get('notes', ''),
            created_by=current_user.id
        )
        db.session.add(payment)
        
        # Create ledger entry for this payment
        ledger_entry = SupplierLedgerEntry(
            supplier_id=supplier_id,
            entry_date=payment.payment_date,
            description=f"دفعة {data.get('method')}",
            reference_type='payment',
            reference_id=payment.id,
            credit=float(data['amount'])  # Credit increases when we pay the supplier
        )
        db.session.add(ledger_entry)
        
        db.session.commit()
        
        return jsonify({
            'id': payment.id,
            'amount': payment.amount,
            'date': payment.payment_date.isoformat(),
            'method': payment.payment_method,
            'reference': payment.reference,
            'message': 'تمت إضافة الدفعة بنجاح'
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'حدث خطأ أثناء إضافة الدفعة: {str(e)}'}), 500
    
    
@purchase_order_bp.route('/api/supplier-accounts', methods=['GET'])
@login_required
def get_supplier_accounts():
    suppliers = Supplier.query.all()
    result = []
    
    for supplier in suppliers:
        # Get all purchase orders for this supplier
        purchase_orders = PurchaseOrder.query.filter_by(supplier_id=supplier.id).all()
        
        # Calculate total ordered amount (excluding cancelled orders)
        total_ordered = sum(po.total_amount for po in purchase_orders if po.status != 'Cancelled')
        
        # Calculate total paid amount from the payments table
        total_paid = db.session.query(db.func.sum(SupplierPayment.amount)).filter_by(supplier_id=supplier.id).scalar() or 0
        
        # Calculate balance
        balance = total_ordered - total_paid
        
        # Count purchase orders by status
        pending_count = PurchaseOrder.query.filter_by(supplier_id=supplier.id, status='Pending').count()
        approved_count = PurchaseOrder.query.filter_by(supplier_id=supplier.id, status='Approved').count()
        received_count = PurchaseOrder.query.filter_by(supplier_id=supplier.id, status='Received').count()
        cancelled_count = PurchaseOrder.query.filter_by(supplier_id=supplier.id, status='Cancelled').count()
        
        result.append({
            'id': supplier.id,
            'name': supplier.supplier_name,
            'contact': supplier.contact_info,
            'email': supplier.email,
            'phone': supplier.phone,
            'total_ordered': total_ordered,
            'total_paid': total_paid,
            'balance': balance,
            'purchase_orders_count': len(purchase_orders),
            'status_counts': {
                'pending': pending_count,
                'approved': approved_count,
                'received': received_count,
                'cancelled': cancelled_count
            }
        })
    
    return jsonify(result)

# API endpoint to get detailed financial information for a specific supplier
@purchase_order_bp.route('/api/supplier-accounts/<int:supplier_id>', methods=['GET'])
@login_required
def get_supplier_account_details(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    
    # Get all purchase orders for this supplier
    purchase_orders = PurchaseOrder.query.filter_by(supplier_id=supplier.id).all()
    
    po_details = []
    for po in purchase_orders:
        po_details.append({
            'id': po.id,
            'order_date': po.order_date.isoformat() if po.order_date else None,
            'status': po.status,
            'total_amount': po.total_amount,
            'items_count': PurchaseOrderDetail.query.filter_by(po_id=po.id).count()
        })
    
    # Get payment history from the database
    payments_query = SupplierPayment.query.filter_by(supplier_id=supplier.id).order_by(SupplierPayment.payment_date.desc())
    payments = []
    
    for payment in payments_query:
        payments.append({
            'id': payment.id,
            'date': payment.payment_date.isoformat() if payment.payment_date else None,
            'amount': payment.amount,
            'reference': payment.reference,
            'method': payment.payment_method,
            'notes': payment.notes
        })
    
    # Calculate totals
    total_ordered = sum(po.total_amount for po in purchase_orders if po.status != 'Cancelled')
    total_paid = sum(payment.amount for payment in SupplierPayment.query.filter_by(supplier_id=supplier.id).all())
    balance = total_ordered - total_paid
    
    return jsonify({
        'supplier': {
            'id': supplier.id,
            'name': supplier.supplier_name,
            'contact': supplier.contact_info,
            'address': supplier.address,
            'email': supplier.email,
            'phone': supplier.phone,
            'tax_id': supplier.tax_id,
            'website': supplier.website,
            'contact_person': supplier.contact_person,
            'payment_terms': supplier.payment_terms
        },
        'financial_summary': {
            'total_ordered': total_ordered,
            'total_paid': total_paid,
            'balance': balance
        },
        'purchase_orders': po_details,
        'payments': payments
    })
# API endpoint to generate and download supplier account statement as PDF
@purchase_order_bp.route('/api/supplier-accounts/<int:supplier_id>/pdf', methods=['GET'])
@login_required
def download_supplier_account_pdf(supplier_id):
    try:
        # Get supplier details
        supplier = Supplier.query.get_or_404(supplier_id)
        
        # Get purchase orders
        purchase_orders = PurchaseOrder.query.filter_by(supplier_id=supplier_id).all()
        
        # Get payments
        payments = SupplierPayment.query.filter_by(supplier_id=supplier_id).all()
        
        # Calculate totals
        total_ordered = sum(po.total_amount for po in purchase_orders if po.status != 'Cancelled')
        total_paid = sum(payment.amount for payment in payments)
        balance = total_ordered - total_paid
        
        # Prepare data for template
        po_data = []
        for po in purchase_orders:
            po_data.append({
                'id': po.id,
                'order_date': po.order_date.strftime('%Y-%m-%d') if po.order_date else '',
                'status': po.status,
                'total_amount': po.total_amount
            })
        
        payment_data = []
        for payment in payments:
            payment_data.append({
                'id': payment.id,
                'date': payment.payment_date.strftime('%Y-%m-%d') if payment.payment_date else '',
                'amount': payment.amount,
                'method': payment.payment_method,
                'reference': payment.reference
            })
        
        # Get logo as base64
        import os
        import base64
        from flask import current_app
        
        # Get the correct base directory path
        base_dir = current_app.root_path
        image_path = os.path.join(base_dir, 'static', 'uploads', 'images', 'katilo.png')
        
        if os.path.exists(image_path):
            with open(image_path, 'rb') as img_file:
                img_data = base64.b64encode(img_file.read()).decode('utf-8')
            
            # Pass the data URI to the template
            logo_src = f"data:image/png;base64,{img_data}"
        else:
            logo_src = ""
            current_app.logger.warning(f"Logo image not found at path: {image_path}")
        
        # Render HTML template with current user information
        html_content = render_template(
            'supplier_account_pdf.html',
            supplier=supplier,
            purchase_orders=po_data,
            payments=payment_data,
            total_ordered=total_ordered,
            total_paid=total_paid,
            balance=balance,
            logo_src=logo_src,
            current_user=current_user,  # Pass the current user from Flask-Login
            generated_date=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
        
        # Configure PDF options
        options = {
            'page-size': 'A4',
            'margin-top': '1cm',
            'margin-right': '1cm',
            'margin-bottom': '1cm',
            'margin-left': '1cm',
            'encoding': 'UTF-8',
            'no-outline': None,
            'enable-local-file-access': None
        }
        
        try:
            # Specify the path to wkhtmltopdf executable
            config = pdfkit.configuration(wkhtmltopdf='pdftool/wkhtmltopdf/bin/wkhtmltopdf.exe')
            
            # Generate PDF
            pdf = pdfkit.from_string(html_content, False, options=options, configuration=config)
            
            # Create response
            response = BytesIO(pdf)
            
            # Return the PDF as a downloadable file
            return send_file(
                response,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=f'supplier_account_{supplier.supplier_name}_{datetime.now().strftime("%Y%m%d")}.pdf'
            )
        except Exception as e:
            # Log the error for debugging
            current_app.logger.error(f"PDF generation error: {str(e)}")
            return jsonify({"error": f"Failed to generate PDF: {str(e)}"}), 500
            
    except Exception as e:
        # Log the error for debugging
        current_app.logger.error(f"Error in download_supplier_account_pdf: {str(e)}")
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500


# API endpoint to generate and download supplier account statement as Excel
@purchase_order_bp.route('/api/supplier-accounts/<int:supplier_id>/excel', methods=['GET'])
@login_required
def download_supplier_account_excel(supplier_id):
    from flask import send_file
    import pandas as pd
    from io import BytesIO
    from datetime import datetime
   
    supplier = Supplier.query.get_or_404(supplier_id)
   
    # Get supplier account details
    account_details = get_supplier_account_details(supplier_id).json
   
    # Create Excel file with multiple sheets
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # Summary sheet
        summary_data = {
            'المورد': [account_details['supplier']['name']],
            'إجمالي المشتريات': [account_details['financial_summary']['total_ordered']],
            'إجمالي المدفوعات': [account_details['financial_summary']['total_paid']],
            'الرصيد المتبقي': [account_details['financial_summary']['balance']]
        }
        pd.DataFrame(summary_data).to_excel(writer, sheet_name='ملخص الحساب', index=False)
       
        # Purchase orders sheet
        if account_details['purchase_orders']:
            # First, check the structure of the first purchase order to determine columns
            first_po = account_details['purchase_orders'][0]
            po_columns = list(first_po.keys())
            
            # Create a list of dictionaries for the DataFrame
            po_list = []
            for po in account_details['purchase_orders']:
                po_dict = {}
                for key in po_columns:
                    po_dict[key] = po[key]
                po_list.append(po_dict)
            
            po_data = pd.DataFrame(po_list)
            
            # Map the column names to Arabic
            column_mapping = {
                'id': 'رقم الطلب',
                'order_date': 'تاريخ الطلب',
                'status': 'الحالة',
                'total_amount': 'المبلغ الإجمالي',
                'items_count': 'عدد العناصر'
            }
            
            # Rename columns that exist in the DataFrame
            rename_dict = {col: column_mapping.get(col, col) for col in po_data.columns if col in column_mapping}
            po_data = po_data.rename(columns=rename_dict)
            
            po_data.to_excel(writer, sheet_name='طلبات الشراء', index=False)
       
        # Payments sheet
        if account_details['payments']:
            # First, check the structure of the first payment to determine columns
            first_payment = account_details['payments'][0]
            payment_columns = list(first_payment.keys())
            
            # Create a list of dictionaries for the DataFrame
            payment_list = []
            for payment in account_details['payments']:
                payment_dict = {}
                for key in payment_columns:
                    payment_dict[key] = payment[key]
                payment_list.append(payment_dict)
            
            payment_data = pd.DataFrame(payment_list)
            
            # Map the column names to Arabic
            payment_column_mapping = {
                'id': 'رقم الدفعة',
                'date': 'تاريخ الدفع',
                'amount': 'المبلغ',
                'reference': 'المرجع',
                'method': 'طريقة الدفع',
                'notes': 'ملاحظات'
            }
            
            # Rename columns that exist in the DataFrame
            payment_rename_dict = {col: payment_column_mapping.get(col, col) for col in payment_data.columns if col in payment_column_mapping}
            payment_data = payment_data.rename(columns=payment_rename_dict)
            
            payment_data.to_excel(writer, sheet_name='المدفوعات', index=False)
       
        # Format the Excel file
        workbook = writer.book
       
        # Add formats
        header_format = workbook.add_format({
            'bold': True,
            'text_wrap': True,
            'valign': 'top',
            'fg_color': '#D7E4BC',
            'border': 1
        })
       
        # Apply formatting to all sheets
        for sheet in writer.sheets.values():
            sheet.set_column('A:Z', 18)
            sheet.right_to_left()
   
    output.seek(0)
   
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'supplier_account_{supplier.supplier_name}_{datetime.now().strftime("%Y%m%d")}.xlsx'
    )

