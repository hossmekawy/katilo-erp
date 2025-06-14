from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, current_app, send_file
from flask_login import login_required, current_user
from datetime import datetime
from sqlalchemy import or_, and_
from models import (
    Category, CustomerInteraction, InventoryTransaction, User, db, SalesOrder, SalesOrderDetail, Customer, Item, Inventory,
    SalesRepresentative, SalesInvoice, SalesPayment, SalesActivityLog, SalesReturn, SalesReturnItem,
    DiscountPromotion, CashAccount, CashTransaction, SystemSettings
)
from datetime import datetime, timedelta
import random
import string
from sqlalchemy import func
import json
import uuid
import pandas as pd
import io
import os
import tempfile
from werkzeug.utils import secure_filename

sales_bp = Blueprint('sales', __name__, url_prefix='/sales')

# Helper function to log sales activities
from flask_login import current_user
from datetime import datetime
from models import db, SalesActivityLog

# Helper function to log sales activities
def log_activity(order_id=None, invoice_id=None, activity_type="", description=""):
    """
    Log a sales activity in the database

    Args:
        order_id: The ID of the sales order (optional)
        invoice_id: The ID of the invoice (optional)
        activity_type: Type of activity (e.g., "Created", "Updated", "Deleted", "Payment", etc.)
        description: Detailed description of the activity
    """
    try:
        activity_log = SalesActivityLog(
            sales_order_id=order_id,
            invoice_id=invoice_id,
            activity_type=activity_type,
            description=description,
            performed_by=current_user.id,
            timestamp=datetime.utcnow()
        )

        db.session.add(activity_log)
        db.session.commit()
        return True
    except Exception as e:
        print(f"Error logging activity: {str(e)}")
        # Don't roll back the main transaction if logging fails
        db.session.rollback()
        return False


# Helper function to check product availability
 # Helper function to check product availability
def check_product_availability(item_id, quantity, warehouse_id=None):
    # First check if the item is a FinalProduct or IntermediateProduct
    item = Item.query.get(item_id)
    if not item or (item.category and item.category.category_type.lower() not in ['finalproduct', 'intermediateproduct']):
        return False, 0, "هذا المنتج ليس منتج نهائي أو وسيط"

    if warehouse_id:
        # Check specific warehouse
        inventory = Inventory.query.filter_by(item_id=item_id, warehouse_id=warehouse_id).first()
        if inventory and inventory.quantity >= quantity:
            return True, inventory.quantity, "متاح في المخزن"
        return False, inventory.quantity if inventory else 0, "غير متاح بالكمية المطلوبة"
    else:
        # Check all warehouses
        total_quantity = db.session.query(func.sum(Inventory.quantity)).filter(
            Inventory.item_id == item_id
        ).scalar() or 0

        if total_quantity >= quantity:
            return True, total_quantity, "متاح في المخزن"
        return False, total_quantity, "غير متاح بالكمية المطلوبة"

# Helper function to generate invoice number
def generate_invoice_number():
    prefix = "INV"
    date_part = datetime.now().strftime("%Y%m%d")
    random_part = ''.join(random.choices(string.digits, k=4))
    return f"{prefix}-{date_part}-{random_part}"

# Dashboard
@sales_bp.route('/')
@login_required
def sales_dashboard():
    # Get recent sales orders
    recent_orders = SalesOrder.query.order_by(SalesOrder.order_date.desc()).limit(10).all()

    # Get sales statistics
    total_orders = SalesOrder.query.count()
    pending_orders = SalesOrder.query.filter_by(status='Pending').count()
    delivered_orders = SalesOrder.query.filter_by(status='Delivered').count()

    # Calculate total sales amount
    total_sales = db.session.query(func.sum(SalesOrder.total_amount)).scalar() or 0

    # Get top customers
    top_customers = db.session.query(
        Customer, func.sum(SalesOrder.total_amount).label('total_spent')
    ).join(SalesOrder).group_by(Customer.id).order_by(func.sum(SalesOrder.total_amount).desc()).limit(5).all()

    # Get top products
    top_products = db.session.query(
        Item, func.sum(SalesOrderDetail.quantity_ordered).label('total_sold')
    ).join(SalesOrderDetail).group_by(Item.id).order_by(func.sum(SalesOrderDetail.quantity_ordered).desc()).limit(5).all()

    return render_template(
        'sales/dashboard.html',
        recent_orders=recent_orders,
        total_orders=total_orders,
        pending_orders=pending_orders,
        delivered_orders=delivered_orders,
        total_sales=total_sales,
        top_customers=top_customers,
        top_products=top_products
    )

# Sales Order Management
@sales_bp.route('/orders')
@login_required
def list_orders():
    orders = SalesOrder.query.order_by(SalesOrder.order_date.desc()).all()
    return render_template('sales/orders/list.html', orders=orders)

@sales_bp.route('/orders/new', methods=['GET'])
@login_required
def new_order_form():
    customers = Customer.query.all()
    items = Item.query.all()
    representatives = SalesRepresentative.query.filter_by(is_active=True).all()
    cash_accounts = CashAccount.query.filter_by(is_active=True).all()
    return render_template(
        'sales/orders/new.html',
        customers=customers,
        items=items,
        representatives=representatives,
        cash_accounts=cash_accounts
    )

@sales_bp.route('/orders', methods=['POST'])
@login_required
def create_order():
    data = request.json

    # Get payment information
    payment_method = data.get('payment_method', 'cash')
    cash_account_id = data.get('cash_account_id')

    # FIXED: Do not automatically set payment status to 'Paid' for sales orders
    # Payment status should only be updated when actual payments are received through invoices
    payment_status = 'Unpaid'

    # Create sales order
    order = SalesOrder(
        customer_id=data['customer_id'],
        order_date=datetime.now(),
        status='Pending',
        total_amount=data['total_amount'],
        payment_method=payment_method,
        cash_account_id=cash_account_id,
        payment_status=payment_status,
        payment_reference=data.get('payment_reference', '')
    )

    # Add representative if assigned
    if data.get('representative_id'):
        order.sales_rep_id = data['representative_id']

    db.session.add(order)
    db.session.flush()  # Get the order ID without committing

    # Create order details
    for item in data['items']:
        # Check availability
        is_available, available_quantity, message = check_product_availability(item['item_id'], item['quantity'])
        if not is_available:
            db.session.rollback()
            return jsonify({
                'success': False,
                'message': f"Insufficient stock for item ID {item['item_id']}"
            }), 400

        detail = SalesOrderDetail(
            sales_order_id=order.id,
            item_id=item['item_id'],
            quantity_ordered=item['quantity'],
            unit_price=item['unit_price']
        )
        db.session.add(detail)

    # FIXED: Remove automatic cash booking for sales orders
    # Cash should only be booked when invoices are paid, not when orders are created
    # This prevents double-counting of revenue

    db.session.commit()

    # Log the activity
    log_activity(
        order_id=order.id,
        activity_type="Created",
        description=f"Sales order created for customer {order.customer_id} with total amount {order.total_amount}"
    )

    return jsonify({
        'success': True,
        'order_id': order.id,
        'message': 'Sales order created successfully'
    })

@sales_bp.route('/orders/<int:order_id>')
@login_required
def view_order(order_id):
    order = SalesOrder.query.get_or_404(order_id)

    # Helper function to get item details
    def get_item(item_id):
        try:
            # Try to get the item directly
            return Item.query.get(item_id)
        except Exception as e:
            # If there's an error (like missing columns), use a more basic query
            try:
                # Use a more specific query that doesn't include the Weight and Volume columns
                return db.session.query(
                    Item.id, Item.name, Item.category_id, Item.sku,
                    Item.description, Item.unit_of_measure, Item.cost,
                    Item.price, Item.reorder_level
                ).filter(Item.id == item_id).first()
            except Exception as inner_e:
                print(f"Error getting item: {str(inner_e)}")
                return None

    return render_template(
        'sales/orders/view.html',
        order=order,
        get_item=get_item
    )


@sales_bp.route('/orders/<int:order_id>/edit', methods=['GET'])
@login_required
def edit_order_form(order_id):
    order = SalesOrder.query.get_or_404(order_id)
    customers = Customer.query.all()
    items = Item.query.all()
    representatives = SalesRepresentative.query.filter_by(is_active=True).all()
    return render_template(
        'sales/orders/edit.html',
        order=order,
        customers=customers,
        items=items,
        representatives=representatives
    )

@sales_bp.route('/orders/<int:order_id>', methods=['PUT'])
@login_required
def update_order(order_id):
    order = SalesOrder.query.get_or_404(order_id)
    data = request.json

    # Update order fields
    if 'customer_id' in data:
        order.customer_id = data['customer_id']
    if 'status' in data:
        order.status = data['status']
    if 'total_amount' in data:
        order.total_amount = data['total_amount']
    if 'representative_id' in data:
        order.sales_rep_id = data['representative_id']

    # Update order details if provided
    if 'items' in data:
        # Remove existing details
        for detail in order.details:
            db.session.delete(detail)

        # Add new details
        for item in data['items']:
            # Check availability
            is_available, available_quantity, message = check_product_availability(item['item_id'], item['quantity'])
            if not is_available:
                db.session.rollback()
                return jsonify({
                    'success': False,
                    'message': f"Insufficient stock for item ID {item['item_id']}"
                }), 400

            detail = SalesOrderDetail(
                sales_order_id=order.id,
                item_id=item['item_id'],
                quantity_ordered=item['quantity'],
                unit_price=item['unit_price']
            )
            db.session.add(detail)

    db.session.commit()

    # Log the activity
    log_activity(
        order_id=order.id,
        activity_type="Updated",
        description=f"Sales order updated with new total amount {order.total_amount}"
    )

    return jsonify({
        'success': True,
        'message': 'Sales order updated successfully'
    })

@sales_bp.route('/orders/<int:order_id>', methods=['DELETE'])
@login_required
def delete_order(order_id):
    order = SalesOrder.query.get_or_404(order_id)

    # Log before deletion
    log_activity(
        activity_type="Deleted",
        description=f"Sales order {order_id} for customer {order.customer_id} was deleted"
    )

    # Delete order details first
    for detail in order.details:
        db.session.delete(detail)

    # Delete the order
    db.session.delete(order)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Sales order deleted successfully'
    })

# Check Product Availability
# Add this new route to create customers via modal

# Add this route to search for customers

# Add this route to search for sales representatives

# Add this route to search for products with category filter

# Update the check_product_availability function to return more detailed information
# Helper function to check product availability
# Helper function to check product availability
def check_product_availability(item_id, quantity, warehouse_id=None):
    # Convert quantity to integer or float
    try:
        quantity = int(quantity)
    except (ValueError, TypeError):
        try:
            quantity = float(quantity)
        except (ValueError, TypeError):
            return False, 0, "Invalid quantity format"

    if warehouse_id:
        # Check specific warehouse
        inventory = Inventory.query.filter_by(item_id=item_id, warehouse_id=warehouse_id).first()
        if inventory and inventory.quantity >= quantity:
            return True, inventory.quantity, "Available in specified warehouse"
        return False, inventory.quantity if inventory else 0, "Insufficient quantity in specified warehouse"
    else:
        # Check all warehouses
        total_quantity = db.session.query(func.sum(Inventory.quantity)).filter(
            Inventory.item_id == item_id
        ).scalar() or 0

        # Now both are numeric types and can be compared
        if total_quantity >= quantity:
            return True, total_quantity, "Available across all warehouses"
        return False, total_quantity, "Insufficient quantity across all warehouses"

# Update the check-availability endpoint to use the enhanced function
@sales_bp.route('/check-availability', methods=['POST'])
@login_required
def check_availability():
    data = request.json
    item_id = data.get('item_id')
    quantity = data.get('quantity', 1)
    warehouse_id = data.get('warehouse_id')

    is_available, available_quantity, message = check_product_availability(item_id, quantity, warehouse_id)

    return jsonify({
        'is_available': is_available,
        'available_quantity': available_quantity,
        'requested_quantity': quantity,
        'message': message
    })


# Apply Discount
@sales_bp.route('/apply-discount', methods=['POST'])
@login_required
def apply_discount():
    data = request.json
    customer_id = data.get('customer_id')
    total_amount = data.get('total_amount', 0)
    items = data.get('items', [])

    # Check for customer-specific discounts
    # Check for customer-specific discounts
    customer_discount = DiscountPromotion.query.filter(
        DiscountPromotion.customer_id == customer_id,
        DiscountPromotion.start_date <= datetime.now(),
        DiscountPromotion.end_date >= datetime.now()
    ).order_by(DiscountPromotion.discount_percentage.desc()).first()

    # Check for general discounts
    general_discount = DiscountPromotion.query.filter(
        DiscountPromotion.customer_id == None,
        DiscountPromotion.start_date <= datetime.now(),
        DiscountPromotion.end_date >= datetime.now()
    ).order_by(DiscountPromotion.discount_percentage.desc()).first()

    # Use the higher discount
    discount = customer_discount if customer_discount and (not general_discount or
                                                         customer_discount.discount_percentage > general_discount.discount_percentage) else general_discount

    discount_percentage = discount.discount_percentage if discount else 0
    discount_amount = total_amount * (discount_percentage / 100)
    final_amount = total_amount - discount_amount

    return jsonify({
        'original_amount': total_amount,
        'discount_percentage': discount_percentage,
        'discount_amount': discount_amount,
        'final_amount': final_amount,
        'discount_applied': discount is not None
    })

# Generate Invoice
@sales_bp.route('/orders/<int:order_id>/generate-invoice', methods=['POST'])
@login_required
def generate_invoice(order_id):
    try:
        order = SalesOrder.query.get_or_404(order_id)

        # Check if invoice already exists
        existing_invoice = SalesInvoice.query.filter_by(sales_order_id=order_id).first()
        if existing_invoice:
            return jsonify({
                'success': False,
                'message': 'Invoice already exists for this order',
                'invoice_id': existing_invoice.id
            }), 400

        # Safely get JSON data, defaulting to an empty dict if parsing fails
        try:
            data = request.get_json(silent=True) or {}
        except:
            data = {}

        # Calculate amounts
        subtotal = float(order.total_amount) if order.total_amount else 0
        tax_rate = float(data.get('tax_rate', 0))
        tax_amount = subtotal * (tax_rate / 100)

        # Apply discount if provided
        discount_amount = float(data.get('discount_amount', 0))

        # Calculate total
        total_amount = subtotal + tax_amount - discount_amount

        # Create invoice
        invoice = SalesInvoice(
            sales_order_id=order_id,
            invoice_number=generate_invoice_number(),
            invoice_date=datetime.now(),
            due_date=datetime.now() + timedelta(days=int(data.get('payment_terms', 30))),
            subtotal=subtotal,
            tax_amount=tax_amount,
            discount_amount=discount_amount,
            total_amount=total_amount,
            notes=data.get('notes', ''),
            status='Unpaid',
            created_by=current_user.id
        )

        db.session.add(invoice)
        db.session.commit()

        # Create activity log entry
        activity_log = SalesActivityLog(
            sales_order_id=order_id,
            invoice_id=invoice.id,
            activity_type="Invoice Generated",
            description=f"Invoice {invoice.invoice_number} generated for order {order_id} with total amount {total_amount}",
            performed_by=current_user.id,
            timestamp=datetime.now()
        )
        db.session.add(activity_log)
        db.session.commit()

        return jsonify({
            'success': True,
            'invoice_id': invoice.id,
            'invoice_number': invoice.invoice_number,
            'total_amount': float(total_amount),
            'message': 'Invoice generated successfully'
        })
    except Exception as e:
        db.session.rollback()
        import traceback
        error_details = traceback.format_exc()
        print(f"Error generating invoice: {str(e)}\n{error_details}")
        return jsonify({
            'success': False,
            'message': f'Error generating invoice: {str(e)}'
        }), 500

@sales_bp.route('/invoices')
@login_required
def list_invoices():
    # Check if format parameter is provided for printing all invoices
    format_param = request.args.get('format', '')
    if format_param.lower() == 'pdf':
        # Get the invoice ID from the request
        invoice_id = request.args.get('id')
        if invoice_id:
            try:
                # Redirect to the print route for the specific invoice
                return redirect(url_for('sales.print_invoice', invoice_id=invoice_id, format='pdf'))
            except:
                pass

    invoices = SalesInvoice.query.order_by(SalesInvoice.invoice_date.desc()).all()
    return render_template('sales/invoices/list.html', invoices=invoices)

@sales_bp.route('/invoices/<int:invoice_id>')
@login_required
def view_invoice(invoice_id):
    invoice = SalesInvoice.query.get_or_404(invoice_id)
    cash_accounts = CashAccount.query.filter_by(is_active=True).all()

    # Get company information and payment terms from system settings
    settings = SystemSettings.get_settings()

    # Calculate payment days
    payment_days = (invoice.due_date - invoice.invoice_date).days if invoice.due_date and invoice.invoice_date else 30

    # Format payment terms with the actual days
    payment_terms = settings.payment_terms_text.replace('{days}', str(payment_days))

    return render_template(
        'sales/invoices/view.html',
        invoice=invoice,
        cash_accounts=cash_accounts,
        settings=settings,
        payment_terms=payment_terms
    )

# Process Payment
@sales_bp.route('/invoices/<int:invoice_id>/process-payment', methods=['POST'])
@login_required
def process_payment(invoice_id):
    invoice = SalesInvoice.query.get_or_404(invoice_id)
    data = request.json

    # Validate payment amount
    amount = float(data.get('amount', 0))
    if amount <= 0:
        return jsonify({
            'success': False,
            'message': 'Payment amount must be greater than zero'
        }), 400

    # Calculate total payments made so far
    total_paid = sum(payment.amount for payment in invoice.payments)

    # Ensure payment doesn't exceed remaining balance
    remaining_balance = invoice.total_amount - total_paid
    if amount > remaining_balance:
        return jsonify({
            'success': False,
            'message': f'Payment amount exceeds remaining balance of {remaining_balance}'
        }), 400

    # Get payment method and cash account
    payment_method = data.get('payment_method', 'Cash')
    cash_account_id = data.get('cash_account_id')

    # Create payment record
    payment = SalesPayment(
        invoice_id=invoice_id,
        payment_date=datetime.now(),
        amount=amount,
        payment_method=payment_method,
        cash_account_id=cash_account_id,
        reference_number=data.get('reference_number', ''),
        notes=data.get('notes', ''),
        recorded_by=current_user.id
    )

    db.session.add(payment)

    # Update invoice status
    new_total_paid = total_paid + amount
    if new_total_paid >= invoice.total_amount:
        invoice.status = 'Paid'
    elif new_total_paid > 0:
        invoice.status = 'Partially Paid'

    # Update order payment status
    order = invoice.sales_order
    if order:
        order.payment_status = invoice.status

        # If payment method is cash and cash account is provided, record the transaction
        if payment_method.lower() == 'cash' and cash_account_id:
            # Get the cash account
            cash_account = CashAccount.query.get(cash_account_id)
            if cash_account:
                # Update the cash account balance
                cash_account.current_balance += amount

                # Create a cash transaction record
                transaction = CashTransaction(
                    account_id=cash_account_id,
                    transaction_type='deposit',
                    amount=amount,
                    reference_type='sales_payment',
                    reference_id=payment.id,
                    description=f"Payment for invoice #{invoice.invoice_number}",
                    transaction_date=datetime.now(),
                    created_by=current_user.id
                )
                db.session.add(transaction)

    db.session.commit()

    # Log the activity
    log_activity(
        invoice_id=invoice_id,
        activity_type="Payment Processed",
        description=f"Payment of {amount} processed for invoice {invoice.invoice_number} via {payment_method}"
    )

    return jsonify({
        'success': True,
        'payment_id': payment.id,
        'invoice_status': invoice.status,
        'amount_paid': amount,
        'total_paid': new_total_paid,
        'remaining_balance': invoice.total_amount - new_total_paid,
        'message': 'Payment processed successfully'
    })

# Sales Returns and Refunds Management
@sales_bp.route('/returns')
@login_required
def list_returns():
    returns = SalesReturn.query.order_by(SalesReturn.return_date.desc()).all()
    return render_template('sales/returns/list.html', returns=returns)

@sales_bp.route('/returns/new', methods=['GET'])
@login_required
def new_return_form():
    try:
        # Get all delivered or shipped orders
        orders = SalesOrder.query.filter(SalesOrder.status.in_(['Delivered', 'Shipped'])).order_by(SalesOrder.order_date.desc()).all()

        # Filter out orders that have all items fully returned
        orders_with_returnable_items = []
        for order in orders:
            # Get all order details
            order_details = SalesOrderDetail.query.filter_by(sales_order_id=order.id).all()

            # For each order detail, check how many have been returned
            has_returnable_items = False
            for detail in order_details:
                # Get total quantity ordered for this item
                quantity_ordered = detail.quantity_ordered

                # Get total quantity already returned for this item in this order
                returned_quantity = db.session.query(func.sum(SalesReturnItem.quantity)).join(
                    SalesReturn, SalesReturn.id == SalesReturnItem.return_id
                ).filter(
                    SalesReturn.sales_order_id == order.id,
                    SalesReturnItem.item_id == detail.item_id,
                    SalesReturn.return_status.in_(['Approved', 'Completed'])
                ).scalar() or 0

                # If there are still items that can be returned
                if quantity_ordered > returned_quantity:
                    has_returnable_items = True
                    break

            if has_returnable_items:
                orders_with_returnable_items.append(order)

        print(f"Found {len(orders_with_returnable_items)} orders with returnable items out of {len(orders)} total orders")
    except Exception as e:
        # If there's an error, fall back to a simpler query
        print(f"Error in new_return_form: {e}")
        orders_with_returnable_items = SalesOrder.query.filter(SalesOrder.status.in_(['Delivered', 'Shipped'])).all()

    cash_accounts = CashAccount.query.filter_by(is_active=True).all()
    return render_template('sales/returns/new.html', orders=orders_with_returnable_items, cash_accounts=cash_accounts)

@sales_bp.route('/returns', methods=['POST'])
@login_required
def create_return():
    data = request.json

    # Validate required fields
    if not data.get('sales_order_id'):
        return jsonify({
            'success': False,
            'message': 'Sales order ID is required'
        }), 400

    if not data.get('items') or len(data.get('items', [])) == 0:
        return jsonify({
            'success': False,
            'message': 'At least one item must be returned'
        }), 400

    # Get the sales order
    order = SalesOrder.query.get_or_404(data['sales_order_id'])

    # Calculate total refund amount
    total_refund = sum(float(item.get('refund_amount', 0)) for item in data['items'])

    # Create the return record
    sales_return = SalesReturn(
        sales_order_id=order.id,
        invoice_id=data.get('invoice_id'),
        return_date=datetime.now(),
        return_reason=data.get('return_reason', 'Other'),
        return_status='Pending',
        total_refund_amount=total_refund,
        cash_account_id=data.get('cash_account_id'),
        refund_method=data.get('refund_method', 'cash'),
        refund_reference=data.get('refund_reference', ''),
        notes=data.get('notes', ''),
        created_by=current_user.id
    )

    db.session.add(sales_return)
    db.session.flush()  # Get the return ID without committing

    # Add return items
    for item_data in data['items']:
        return_item = SalesReturnItem(
            return_id=sales_return.id,
            item_id=item_data['item_id'],
            quantity=item_data['quantity'],
            unit_price=item_data['unit_price'],
            refund_amount=item_data['refund_amount'],
            return_reason=item_data.get('return_reason', 'Other'),
            condition=item_data.get('condition', 'Good'),
            restocked=item_data.get('restocked', True)
        )
        db.session.add(return_item)

    db.session.commit()

    # Log the activity
    log_activity(
        order_id=order.id,
        activity_type="Return Created",
        description=f"Return created for order #{order.id} with total refund amount {total_refund}"
    )

    return jsonify({
        'success': True,
        'return_id': sales_return.id,
        'message': 'Return created successfully'
    })

@sales_bp.route('/returns/<int:return_id>')
@login_required
def view_return(return_id):
    sales_return = SalesReturn.query.get_or_404(return_id)
    return render_template('sales/returns/view.html', return_=sales_return)

@sales_bp.route('/returns/<int:return_id>/approve', methods=['POST'])
@login_required
def approve_return(return_id):
    sales_return = SalesReturn.query.get_or_404(return_id)

    # Check if already approved
    if sales_return.return_status == 'Approved':
        return jsonify({
            'success': False,
            'message': 'Return has already been approved'
        }), 400

    # Update return status
    sales_return.return_status = 'Approved'
    sales_return.approved_by = current_user.id
    sales_return.approved_at = datetime.now()

    # Process refund if cash account is provided
    if sales_return.refund_method == 'cash' and sales_return.cash_account_id:
        cash_account = CashAccount.query.get(sales_return.cash_account_id)
        if cash_account:
            # Update cash account balance
            cash_account.current_balance -= sales_return.total_refund_amount

            # Create cash transaction
            transaction = CashTransaction(
                account_id=sales_return.cash_account_id,
                transaction_type='withdrawal',
                amount=sales_return.total_refund_amount,
                reference_type='sales_return',
                reference_id=sales_return.id,
                description=f"Refund for return #{sales_return.id}",
                transaction_date=datetime.now(),
                created_by=current_user.id
            )
            db.session.add(transaction)

    # Restock items if needed
    for item in sales_return.items:
        if item.restocked:
            # Find the inventory record for this item
            inventory = Inventory.query.filter_by(item_id=item.item_id).first()
            if inventory:
                # Update inventory
                inventory.quantity += item.quantity

                # Create inventory transaction
                transaction = InventoryTransaction(
                    item_id=item.item_id,
                    warehouse_id=inventory.warehouse_id,
                    transaction_type='IN',
                    quantity=item.quantity,
                    transaction_date=datetime.now(),
                    reference=f'Return #{sales_return.id}'
                )
                db.session.add(transaction)

    db.session.commit()

    # Log the activity
    log_activity(
        order_id=sales_return.sales_order_id,
        activity_type="Return Approved",
        description=f"Return #{sales_return.id} approved with total refund amount {sales_return.total_refund_amount}"
    )

    return jsonify({
        'success': True,
        'message': 'Return approved successfully'
    })

@sales_bp.route('/api/orders/<int:order_id>/items')
@login_required
def get_order_items(order_id):
    try:
        print(f"Fetching items for order ID: {order_id}")
        order = SalesOrder.query.get_or_404(order_id)
        print(f"Order found: {order}")

        # Directly query the database for order details
        details = SalesOrderDetail.query.filter_by(sales_order_id=order_id).all()
        print(f"Order details count from direct query: {len(details)}")

        items = []
        if not details:
            print(f"No details found for order {order_id}")
            return jsonify([])

        # Check if there's an invoice with discount for this order
        invoice = SalesInvoice.query.filter_by(sales_order_id=order_id).first()
        discount_amount = 0
        discount_percentage = 0

        if invoice and invoice.discount_amount > 0:
            discount_amount = float(invoice.discount_amount)
            # Calculate discount percentage based on subtotal
            if invoice.subtotal > 0:
                discount_percentage = (discount_amount / float(invoice.subtotal)) * 100
            print(f"Found invoice with discount: {discount_amount} ({discount_percentage:.2f}%)")

        # Calculate total order value for proportional discount distribution
        total_order_value = sum(detail.unit_price * detail.quantity_ordered for detail in details)

        for detail in details:
            print(f"Processing detail: {detail}")

            # Get total quantity ordered for this item
            quantity_ordered = detail.quantity_ordered

            # Get total quantity already returned for this item in this order
            returned_quantity = db.session.query(func.sum(SalesReturnItem.quantity)).join(
                SalesReturn, SalesReturn.id == SalesReturnItem.return_id
            ).filter(
                SalesReturn.sales_order_id == order_id,
                SalesReturnItem.item_id == detail.item_id,
                SalesReturn.return_status.in_(['Approved', 'Completed', 'Pending'])
            ).scalar() or 0

            # Calculate remaining quantity that can be returned
            remaining_quantity = quantity_ordered - returned_quantity

            # Skip items that have been fully returned
            if remaining_quantity <= 0:
                print(f"Item {detail.item_id} has been fully returned ({returned_quantity}/{quantity_ordered})")
                continue

            # Calculate item's total price
            item_total_price = float(detail.unit_price * quantity_ordered)

            # Calculate item's discount (proportional to its value in the order)
            item_discount = 0
            if total_order_value > 0 and discount_amount > 0:
                item_discount = (item_total_price / total_order_value) * discount_amount

            # Calculate discounted unit price
            discounted_unit_price = detail.unit_price
            if quantity_ordered > 0:
                discounted_unit_price = (item_total_price - item_discount) / quantity_ordered

            item = Item.query.get(detail.item_id)
            if item:
                print(f"Item found: {item.name}, Remaining: {remaining_quantity}/{quantity_ordered}")
                items.append({
                    'id': detail.id,
                    'item_id': detail.item_id,
                    'name': item.name,
                    'quantity_ordered': quantity_ordered,
                    'quantity_returned': returned_quantity,
                    'remaining_quantity': remaining_quantity,
                    'unit_price': float(detail.unit_price),
                    'total_price': item_total_price,
                    'has_discount': discount_amount > 0,
                    'discount_percentage': discount_percentage,
                    'item_discount': item_discount,
                    'discounted_unit_price': discounted_unit_price,
                    'discounted_total_price': item_total_price - item_discount
                })
            else:
                print(f"Item not found for item_id: {detail.item_id}")
                # Add a placeholder item
                items.append({
                    'id': detail.id,
                    'item_id': detail.item_id,
                    'name': 'عنصر غير معروف',
                    'quantity_ordered': quantity_ordered,
                    'quantity_returned': returned_quantity,
                    'remaining_quantity': remaining_quantity,
                    'unit_price': float(detail.unit_price),
                    'total_price': item_total_price,
                    'has_discount': discount_amount > 0,
                    'discount_percentage': discount_percentage,
                    'item_discount': item_discount,
                    'discounted_unit_price': discounted_unit_price,
                    'discounted_total_price': item_total_price - item_discount
                })

        print(f"Returning {len(items)} items with remaining quantities")

        # If no items are available for return, return an empty array
        if not items:
            print("No items available for return")
            return jsonify([])

        return jsonify(items)
    except Exception as e:
        print(f"Error in get_order_items: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify([]), 500

# Sales Representatives Management

# Sales Activity Logs
@sales_bp.route('/activity-logs')
@login_required
def view_activity_logs():
    logs = SalesActivityLog.query.order_by(SalesActivityLog.timestamp.desc()).all()
    return render_template('sales/activity_logs.html', logs=logs)

# Customer Management within Sales
@sales_bp.route('/customers')
@login_required
def list_customers():
    customers = Customer.query.all()
    return render_template('sales/customers/list.html', customers=customers)

@sales_bp.route('/customers/new', methods=['GET'])
@login_required
def new_customer_form():
    return render_template('sales/customers/new.html')

@sales_bp.route('/customers', methods=['POST'])
@login_required
def create_customer():
    data = request.json

    customer = Customer(
        customer_name=data['customer_name'],
        contact_info=data.get('contact_info', ''),
        billing_address=data.get('billing_address', ''),
        shipping_address=data.get('shipping_address', '')
    )

    db.session.add(customer)
    db.session.commit()

    # Log the activity
    log_activity(
        activity_type="Customer Created",
        description=f"Customer {customer.customer_name} created"
    )

    return jsonify({
        'success': True,
        'customer_id': customer.id,
        'message': 'Customer created successfully'
    })

@sales_bp.route('/customers/<int:customer_id>', methods=['PUT'])
@login_required
def update_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    data = request.json

    # Update fields
    if 'customer_name' in data:
        customer.customer_name = data['customer_name']
    if 'contact_info' in data:
        customer.contact_info = data['contact_info']
    if 'billing_address' in data:
        customer.billing_address = data['billing_address']
    if 'shipping_address' in data:
        customer.shipping_address = data['shipping_address']

    db.session.commit()

    # Log the activity
    log_activity(
        activity_type="Customer Updated",
        description=f"Customer {customer.customer_name} updated"
    )

    return jsonify({
        'success': True,
        'message': 'Customer updated successfully'
    })

# API endpoints for AJAX requests
@sales_bp.route('/api/customers')
@login_required
def api_get_customers():
    customers = Customer.query.all()
    return jsonify([{
        'id': c.id,
        'name': c.customer_name,
        'customer_name': c.customer_name,  # Keep for backward compatibility
        'contact_info': c.contact_info,
        'billing_address': c.billing_address,
        'shipping_address': c.shipping_address
    } for c in customers])


@sales_bp.route('/api/items')
@login_required
def api_get_items():
    items = Item.query.all()
    return jsonify([{
        'id': i.id,
        'name': i.name,
        'sku': i.sku,
        'price': i.price,
        'category_id': i.category_id,
        'unit_of_measure': i.unit_of_measure
    } for i in items])

@sales_bp.route('/api/representatives')
@login_required
def api_get_representatives():
    reps = SalesRepresentative.query.filter_by(is_active=True).all()
    return jsonify([{
        'id': r.id,
        'user_id': r.user_id,
        'name': r.user.username,
        'territory': r.territory
    } for r in reps])

# Add this new API endpoint to routes/sales_routes.py
@sales_bp.route('/api/representatives/<int:rep_id>')
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


@sales_bp.route('/api/orders')
@login_required
def api_get_orders():
    customer_id = request.args.get('customer_id', type=int)

    query = SalesOrder.query

    if customer_id:
        query = query.filter_by(customer_id=customer_id)

    orders = query.order_by(SalesOrder.order_date.desc()).all()

    return jsonify([{
        'id': order.id,
        'customer_id': order.customer_id,
        'order_date': order.order_date.isoformat() if order.order_date else None,
        'status': order.status,
        'total_amount': float(order.total_amount) if order.total_amount else 0,
        'representative_id': order.sales_rep_id
    } for order in orders])

@sales_bp.route('/api/orders/<int:order_id>/edit-items')
@login_required
def get_order_items_for_edit(order_id):
    """Get order items specifically formatted for editing an order"""
    try:
        order = SalesOrder.query.get_or_404(order_id)
        details = SalesOrderDetail.query.filter_by(sales_order_id=order_id).all()

        if not details:
            return jsonify([])

        items = []
        for detail in details:
            item = Item.query.get(detail.item_id)
            if item:
                items.append({
                    'item_id': detail.item_id,
                    'item_name': item.name,
                    'quantity': detail.quantity_ordered,
                    'unit_price': float(detail.unit_price)
                })
            else:
                items.append({
                    'item_id': detail.item_id,
                    'item_name': 'عنصر غير معروف',
                    'quantity': detail.quantity_ordered,
                    'unit_price': float(detail.unit_price)
                })

        return jsonify(items)
    except Exception as e:
        print(f"Error in get_order_items_for_edit: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify([]), 500
@sales_bp.route('/customers/<int:customer_id>')
@login_required
def view_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)

    # Get purchase history data for chart
    purchase_history = db.session.query(
        SalesOrder.order_date,
        SalesOrder.total_amount
    ).filter(
        SalesOrder.customer_id == customer_id
    ).order_by(SalesOrder.order_date).all()

    purchase_history_dates = [order.order_date.strftime('%Y-%m-%d') for order in purchase_history]
    purchase_history_amounts = [float(order.total_amount) for order in purchase_history]

    # Get top products data for chart
    top_products = db.session.query(
        Item.name,
        func.sum(SalesOrderDetail.quantity_ordered).label('total_quantity')
    ).join(
        SalesOrderDetail, SalesOrderDetail.item_id == Item.id
    ).join(
        SalesOrder, SalesOrder.id == SalesOrderDetail.sales_order_id
    ).filter(
        SalesOrder.customer_id == customer_id
    ).group_by(
        Item.id
    ).order_by(
        func.sum(SalesOrderDetail.quantity_ordered).desc()
    ).limit(5).all()

    top_products_names = [product.name for product in top_products]
    top_products_quantities = [int(product.total_quantity) for product in top_products]

    # Calculate customer metrics
    total_spent = db.session.query(func.sum(SalesOrder.total_amount)).filter(
        SalesOrder.customer_id == customer_id
    ).scalar() or 0

    avg_order_value = db.session.query(func.avg(SalesOrder.total_amount)).filter(
        SalesOrder.customer_id == customer_id
    ).scalar() or 0

    last_order = SalesOrder.query.filter_by(customer_id=customer_id).order_by(
        SalesOrder.order_date.desc()
    ).first()

    last_order_date = last_order.order_date if last_order else None

    # Add calculated metrics to customer object
    customer.total_spent = total_spent
    customer.avg_order_value = avg_order_value
    customer.last_order_date = last_order_date

    return render_template(
        'sales/customers/view.html',
        customer=customer,
        purchase_history_dates=purchase_history_dates,
        purchase_history_amounts=purchase_history_amounts,
        top_products_names=top_products_names,
        top_products_quantities=top_products_quantities
    )
@sales_bp.route('/customers/<int:customer_id>/edit', methods=['GET'])
@login_required
def edit_customer_form(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    return render_template('sales/customers/edit.html', customer=customer)

@sales_bp.route('/customers/interactions', methods=['POST'])
@login_required
def create_customer_interaction():
    data = request.json

    # Validate required fields
    if not data.get('customer_id') or not data.get('notes'):
        return jsonify({
            'success': False,
            'message': 'Customer ID and notes are required'
        }), 400

    # Process follow_up_date if provided
    follow_up_date = None
    if data.get('follow_up_date'):
        try:
            # Convert string date to Python date object
            follow_up_date = datetime.strptime(data['follow_up_date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({
                'success': False,
                'message': 'Invalid date format for follow_up_date. Use YYYY-MM-DD format.'
            }), 400

    # Create new interaction
    interaction = CustomerInteraction(
        customer_id=data['customer_id'],
        interaction_type=data.get('interaction_type', 'Other'),
        notes=data['notes'],
        follow_up_date=follow_up_date,
        created_by=current_user.id
    )

    db.session.add(interaction)
    db.session.commit()

    # Log the activity
    log_activity(
        activity_type="Customer Interaction",
        description=f"New {interaction.interaction_type} interaction recorded for customer {interaction.customer_id}"
    )

    return jsonify({
        'success': True,
        'interaction_id': interaction.id,
        'message': 'Interaction recorded successfully'
    })
@sales_bp.route('/invoices/<int:invoice_id>/remaining-balance')
@login_required
def get_invoice_remaining_balance(invoice_id):
    invoice = SalesInvoice.query.get_or_404(invoice_id)

    # Calculate total payments made so far
    total_paid = sum(payment.amount for payment in invoice.payments)

    # Calculate remaining balance
    remaining_balance = invoice.total_amount - total_paid

    return jsonify({
        'invoice_id': invoice.id,
        'total_amount': invoice.total_amount,
        'total_paid': total_paid,
        'remaining_balance': remaining_balance
    })

@sales_bp.route('/api/invoices')
@login_required
def api_get_invoices():
    invoices = SalesInvoice.query.order_by(SalesInvoice.invoice_date.desc()).all()
    return jsonify([{
        'id': i.id,
        'invoice_number': i.invoice_number,
        'sales_order_id': i.sales_order_id,
        'customer_name': i.sales_order.customer.customer_name,
        'invoice_date': i.invoice_date.strftime('%Y-%m-%d'),
        'due_date': i.due_date.strftime('%Y-%m-%d'),
        'total_amount': i.total_amount,
        'status': i.status
    } for i in invoices])

@sales_bp.route('/invoices/<int:invoice_id>/print')
@login_required
def print_invoice(invoice_id):
    from utils.invoice_pdf_generator import InvoicePDFGenerator
    from flask import request
    from models import CashAccount

    invoice = SalesInvoice.query.get_or_404(invoice_id)
    cash_accounts = CashAccount.query.filter_by(is_active=True).all()

    # Check if print parameter is provided (for auto-printing)
    print_param = request.args.get('print', 'false')
    auto_print = print_param.lower() == 'true'

    # Check if download parameter is provided
    download_param = request.args.get('download', 'false')
    force_download = download_param.lower() == 'true'

    # Check if size parameter is provided
    size_param = request.args.get('size', 'a4')

    # Check if style parameter is provided
    style_param = request.args.get('style')

    try:
        # Create PDF generator instance
        pdf_generator = InvoicePDFGenerator(invoice, current_user)

        # Generate PDF with specified options
        return pdf_generator.generate_pdf(
            size=size_param,
            download=force_download,
            auto_print=auto_print,
            style=style_param
        )
    except Exception as e:
        current_app.logger.error(f"PDF generation error: {str(e)}")

        # Fallback to HTML template if PDF generation fails
        return render_template('sales/invoices/view.html', invoice=invoice, cash_accounts=cash_accounts)

@sales_bp.route('/customers/create-modal', methods=['POST'])
@login_required
def create_customer_modal():
    data = request.json

    # Validate required fields
    if not data.get('customer_name'):
        return jsonify({
            'success': False,
            'message': 'اسم العميل مطلوب'
        }), 400

    customer = Customer(
        customer_name=data['customer_name'],
        contact_info=data.get('contact_info', ''),
        billing_address=data.get('billing_address', ''),
        shipping_address=data.get('shipping_address', '')
    )

    db.session.add(customer)
    db.session.commit()

    # Log the activity
    log_activity(
        activity_type="Customer Created",
        description=f"Customer {customer.customer_name} created from sales order form"
    )

    return jsonify({
        'success': True,
        'customer_id': customer.id,
        'customer_name': customer.customer_name,
        'message': 'تم إنشاء العميل بنجاح'
    })

# Add this route to search for customers
@sales_bp.route('/api/customers/search')
@login_required
def search_customers():
    query = request.args.get('q', '')

    if not query:
        customers = Customer.query.limit(10).all()
    else:
        customers = Customer.query.filter(
            Customer.customer_name.ilike(f'%{query}%')
        ).limit(10).all()

    return jsonify([{
        'id': c.id,
        'name': c.customer_name,
        'customer_name': c.customer_name,  # Keep for backward compatibility
        'contact_info': c.contact_info
    } for c in customers])

@sales_bp.route('/customers/export')
@login_required
def export_customers():
    """Export customers to Excel file"""
    # Get all customers
    customers = Customer.query.all()

    # Create a DataFrame from the customers data
    data = []
    for customer in customers:
        data.append({
            'ID': customer.id,
            'Customer Name': customer.customer_name,
            'Contact Info': customer.contact_info,
            'Billing Address': customer.billing_address,
            'Shipping Address': customer.shipping_address
        })

    df = pd.DataFrame(data)

    # Create a BytesIO object to store the Excel file
    output = io.BytesIO()

    # Use pandas to write the DataFrame to Excel
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Customers', index=False)

        # Get the xlsxwriter workbook and worksheet objects
        workbook = writer.book
        worksheet = writer.sheets['Customers']

        # Add some formatting
        header_format = workbook.add_format({
            'bold': True,
            'text_wrap': True,
            'valign': 'top',
            'fg_color': '#D7E4BC',
            'border': 1
        })

        # Write the column headers with the defined format
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)

        # Set column widths
        worksheet.set_column('A:A', 10)  # ID
        worksheet.set_column('B:B', 30)  # Customer Name
        worksheet.set_column('C:C', 30)  # Contact Info
        worksheet.set_column('D:D', 40)  # Billing Address
        worksheet.set_column('E:E', 40)  # Shipping Address

    # Set the file pointer to the beginning
    output.seek(0)

    # Generate filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"customers_export_{timestamp}.xlsx"

    # Return the Excel file
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )

@sales_bp.route('/customers/import', methods=['GET'])
@login_required
def import_customers_form():
    """Show the form for importing customers from Excel/CSV"""
    return render_template('sales/customers/import.html')

@sales_bp.route('/customers/upload', methods=['POST'])
@login_required
def upload_customers_file():
    """Upload Excel/CSV file and show column mapping page"""
    if 'customers_file' not in request.files:
        flash('No file part', 'error')
        return redirect(url_for('sales.import_customers_form'))

    file = request.files['customers_file']

    if file.filename == '':
        flash('No selected file', 'error')
        return redirect(url_for('sales.import_customers_form'))

    if file and (file.filename.endswith(('.xlsx', '.xls', '.csv'))):
        # Create a unique filename
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4()}_{filename}"

        # Ensure the upload directory exists
        upload_dir = os.path.join(current_app.config['TEMP_FOLDER'], 'customer_imports')
        os.makedirs(upload_dir, exist_ok=True)

        # Save the file
        file_path = os.path.join(upload_dir, unique_filename)
        file.save(file_path)

        # Read the file and get preview data
        try:
            # Determine file type and read accordingly
            if file.filename.endswith('.csv'):
                df = pd.read_csv(file_path)
                sheet_names = None
            else:
                # Get the sheet names from the Excel file
                excel_file = pd.ExcelFile(file_path)
                sheet_names = excel_file.sheet_names

                # If there are multiple sheets, let the user select one
                if len(sheet_names) > 1:
                    return render_template('sales/customers/select_sheet.html',
                                          file_path=file_path,
                                          sheet_names=sheet_names)

                # Otherwise, read the first sheet
                df = pd.read_excel(file_path, sheet_name=0)

            # Get column names and preview data
            excel_columns = df.columns.tolist()
            excel_preview = df.head(5).to_dict('records')

            # Render the column mapping page
            return render_template('sales/customers/map_columns.html',
                                  excel_columns=excel_columns,
                                  excel_preview=excel_preview,
                                  file_path=file_path,
                                  sheet_name=sheet_names[0] if sheet_names else None)

        except Exception as e:
            flash(f'Error reading file: {str(e)}', 'error')
            return redirect(url_for('sales.import_customers_form'))
    else:
        flash('File must be an Excel file (.xlsx, .xls) or CSV file (.csv)', 'error')
        return redirect(url_for('sales.import_customers_form'))

@sales_bp.route('/customers/process-sheet-selection', methods=['POST'])
@login_required
def process_sheet_selection():
    """Process sheet selection and show column mapping page"""
    # Get form data
    file_path = request.form.get('file_path')
    selected_sheet = request.form.get('selected_sheet')

    # Validate required fields
    if not file_path or not selected_sheet:
        flash('Missing required fields', 'error')
        return redirect(url_for('sales.import_customers_form'))

    try:
        # Read the Excel file with the selected sheet
        df = pd.read_excel(file_path, sheet_name=selected_sheet)

        # Get column names and preview data
        excel_columns = df.columns.tolist()
        excel_preview = df.head(5).to_dict('records')

        # Render the column mapping page
        return render_template('sales/customers/map_columns.html',
                              excel_columns=excel_columns,
                              excel_preview=excel_preview,
                              file_path=file_path,
                              sheet_name=selected_sheet)
    except Exception as e:
        flash(f'Error reading Excel sheet: {str(e)}', 'error')
        return redirect(url_for('sales.import_customers_form'))

@sales_bp.route('/customers/map-columns', methods=['POST'])
@login_required
def map_customer_columns():
    """Process column mapping and preview data before import"""
    # Get form data
    file_path = request.form.get('file_path')
    sheet_name = request.form.get('sheet_name')

    # Get column mappings
    column_mapping = {
        'customer_name': request.form.get('customer_name'),
        'contact_info': request.form.get('contact_info'),
        'billing_address': request.form.get('billing_address'),
        'shipping_address': request.form.get('shipping_address')
    }

    # Validate required fields
    if not file_path or not column_mapping['customer_name']:
        flash('Customer name mapping is required', 'error')
        return redirect(url_for('sales.import_customers_form'))

    try:
        # Read the file with the specified sheet if provided
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
        elif sheet_name:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
        else:
            df = pd.read_excel(file_path)

        # Map columns according to user input
        mapped_customers = []
        for _, row in df.iterrows():
            customer = {}

            # Map each field if a column was selected
            for field, column in column_mapping.items():
                if column and column in df.columns:
                    customer[field] = str(row[column]) if not pd.isna(row[column]) else ''
                else:
                    customer[field] = ''

            # Only add customers that have a name
            if customer.get('customer_name'):
                mapped_customers.append(customer)

        # Store the file path and mapped customers in session for later processing
        session_data = {
            'file_path': file_path,
            'customers': mapped_customers,
            'column_mapping': column_mapping
        }

        # Return the preview page with mapped customers
        return render_template('sales/customers/preview_import.html',
                              customers=mapped_customers,
                              session_data=session_data)

    except Exception as e:
        flash(f'Error processing file: {str(e)}', 'error')
        return redirect(url_for('sales.import_customers_form'))

@sales_bp.route('/customers/process-import', methods=['POST'])
@login_required
def process_customers_import():
    """Process the import data and insert into database"""
    try:
        data = request.json
        customers = data.get('customers', [])

        # Counters for summary
        added_customers = 0
        skipped_customers = 0
        updated_customers = 0

        for customer_data in customers:
            action = customer_data.get('action', 'add')

            if action == 'skip':
                skipped_customers += 1
                continue

            # Check if customer with same name already exists
            existing_customer = Customer.query.filter_by(customer_name=customer_data['customer_name']).first()

            if existing_customer and action == 'update':
                # Update existing customer
                if 'contact_info' in customer_data:
                    existing_customer.contact_info = customer_data['contact_info']
                if 'billing_address' in customer_data:
                    existing_customer.billing_address = customer_data['billing_address']
                if 'shipping_address' in customer_data:
                    existing_customer.shipping_address = customer_data['shipping_address']

                updated_customers += 1

            elif not existing_customer and action == 'add':
                # Create new customer
                new_customer = Customer(
                    customer_name=customer_data['customer_name'],
                    contact_info=customer_data.get('contact_info', ''),
                    billing_address=customer_data.get('billing_address', ''),
                    shipping_address=customer_data.get('shipping_address', '')
                )
                db.session.add(new_customer)
                added_customers += 1
            else:
                # Skip if customer exists but action is add, or if customer doesn't exist but action is update
                skipped_customers += 1

        db.session.commit()

        # Log the activity
        log_activity(
            activity_type="Customers Imported",
            description=f"Imported customers: {added_customers} added, {updated_customers} updated, {skipped_customers} skipped"
        )

        return jsonify({
            'success': True,
            'message': f'Successfully processed import. Added {added_customers} customers, updated {updated_customers} customers, and skipped {skipped_customers} customers.',
            'added_customers': added_customers,
            'updated_customers': updated_customers,
            'skipped_customers': skipped_customers
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error processing customer import: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error processing import: {str(e)}'
        }), 500

# Add this route to search for sales representatives
@sales_bp.route('/api/representatives/search')
@login_required
def search_representatives():
    query = request.args.get('q', '')

    if not query:
        reps = SalesRepresentative.query.filter_by(is_active=True).limit(10).all()
    else:
        reps = SalesRepresentative.query.join(User).filter(
            SalesRepresentative.is_active == True,
            User.username.ilike(f'%{query}%')
        ).limit(10).all()

    return jsonify([{
        'id': r.id,
        'name': r.user.username,
        'territory': r.territory
    } for r in reps])

# Add this route to search for products with category filter
@sales_bp.route('/api/items/search')
@login_required
def search_items():
    query = request.args.get('q', '')

    if not query or len(query) < 2:
        return jsonify([])

    # Search for items by name or SKU and filter by category type
    items = Item.query.join(Category).filter(
        and_(
            or_(
                Item.name.ilike(f'%{query}%'),
                Item.sku.ilike(f'%{query}%')
            ),
            Category.category_type.in_(['FinalProduct', 'IntermediateProduct'])
        )
    ).limit(10).all()

    return jsonify([{
        'id': item.id,
        'name': item.name,
        'sku': item.sku,
        'price': float(item.price) if item.price else 0,
        'category_id': item.category_id,
        'category_type': item.category.category_type if item.category else None
    } for item in items])

@sales_bp.route('/orders/<int:order_id>/status', methods=['PUT'])
@login_required
def update_order_status(order_id):
    order = SalesOrder.query.get_or_404(order_id)
    data = request.json

    if 'status' not in data:
        return jsonify({
            'success': False,
            'message': 'Status is required'
        }), 400

    try:
        # Store old status for logging
        old_status = order.status
        new_status = data['status']

        # Check if we're moving to a status that requires inventory deduction
        # This could be "Processing", "Shipped", or another status in your workflow
        should_deduct_inventory = (old_status == 'Pending' and
                                  new_status in ['Processing', 'Shipped'])

        # Update the order status
        order.status = new_status

        # If we should deduct inventory
        if should_deduct_inventory:
            # Get all order details
            order_details = SalesOrderDetail.query.filter_by(sales_order_id=order.id).all()

            for detail in order_details:
                # Find inventory records for this item
                inventory_records = Inventory.query.filter_by(item_id=detail.item_id).all()

                # Calculate how much we need to deduct
                quantity_to_deduct = detail.quantity_ordered

                if not inventory_records:
                    # No inventory found for this item
                    db.session.rollback()
                    return jsonify({
                        'success': False,
                        'message': f'No inventory found for item ID {detail.item_id}'
                    }), 400

                # Try to deduct from available inventory
                for inventory in inventory_records:
                    if quantity_to_deduct <= 0:
                        break

                    if inventory.quantity > 0:
                        # Determine how much we can take from this inventory record
                        deduction = min(inventory.quantity, quantity_to_deduct)

                        # Update inventory
                        inventory.quantity -= deduction

                        # Create transaction record
                        transaction = InventoryTransaction(
                            item_id=detail.item_id,
                            warehouse_id=inventory.warehouse_id,
                            transaction_type='OUT',
                            quantity=deduction,
                            transaction_date=datetime.utcnow(),
                            reference=f'Sales Order #{order.id}'
                        )
                        db.session.add(transaction)

                        # Update remaining quantity to deduct
                        quantity_to_deduct -= deduction

                # If we couldn't deduct all required quantity
                if quantity_to_deduct > 0:
                    db.session.rollback()
                    return jsonify({
                        'success': False,
                        'message': f'Insufficient inventory for item ID {detail.item_id}'
                    }), 400

                # Update the shipped quantity in the order detail
                detail.quantity_shipped = detail.quantity_ordered

        # Create activity log entry
        notes = data.get('notes', '')
        status_description = f"Order status updated from {old_status} to {new_status}"
        if notes:
            status_description += f". Notes: {notes}"

        if should_deduct_inventory:
            status_description += ". Inventory has been deducted."

        # Update the order's updated_at timestamp if you have this field
        if hasattr(order, 'updated_at'):
            order.updated_at = datetime.now()

        # Create activity log entry
        activity_log = SalesActivityLog(
            sales_order_id=order.id,
            activity_type="Status Updated",
            description=status_description,
            performed_by=current_user.id,
            timestamp=datetime.now()
        )
        db.session.add(activity_log)

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'تم تحديث حالة الطلب بنجاح'
        })
    except Exception as e:
        db.session.rollback()
        import traceback
        error_details = traceback.format_exc()
        print(f"Error updating order status: {str(e)}\n{error_details}")
        return jsonify({
            'success': False,
            'message': f'Error updating order status: {str(e)}'
        }), 500


@sales_bp.route('/orders/<int:order_id>/cancel', methods=['PUT'])
@login_required
def cancel_order(order_id):
    order = SalesOrder.query.get_or_404(order_id)

    if order.status == 'Cancelled':
        return jsonify({
            'success': False,
            'message': 'Order is already cancelled'
        }), 400

    data = request.json or {}

    try:
        # Update the status
        old_status = order.status
        order.status = 'Cancelled'

        # Get cancellation reason
        cancel_reason = data.get('notes', 'No reason provided')

        # Update the order's updated_at timestamp if you have this field
        if hasattr(order, 'updated_at'):
            order.updated_at = datetime.now()

        # Create activity log entry
        activity_log = SalesActivityLog(
            sales_order_id=order.id,
            activity_type="Order Cancelled",
            description=f"Order cancelled. Previous status: {old_status}. Reason: {cancel_reason}",
            performed_by=current_user.id,
            timestamp=datetime.now()
        )
        db.session.add(activity_log)

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'تم إلغاء الطلب بنجاح'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error cancelling order: {str(e)}'
        }), 500
