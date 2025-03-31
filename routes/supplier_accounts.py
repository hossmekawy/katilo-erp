from flask import Blueprint, request, jsonify, render_template, send_file
from flask_login import login_required, current_user
from models import db, Supplier, PurchaseOrder, PurchaseOrderDetail, SupplierPayment, SupplierLedgerEntry
from datetime import datetime, timedelta
import pandas as pd
import pdfkit
import tempfile
import os
from io import BytesIO

supplier_accounts_bp = Blueprint('supplier_accounts_bp', __name__)

# ================= TEMPLATE ROUTES =================

@supplier_accounts_bp.route('/supplier-accounts')
@login_required
def supplier_accounts_page():
    return render_template('supplier_accounts.html')

@supplier_accounts_bp.route('/supplier-accounts/<int:id>')
@login_required
def supplier_account_details_page(id):
    supplier = Supplier.query.get_or_404(id)
    return render_template('supplier_account_details.html', supplier_id=id)

# ================= API ROUTES =================

@supplier_accounts_bp.route('/api/supplier-accounts', methods=['GET'])
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
        
        result.append({
            'id': supplier.id,
            'name': supplier.supplier_name,
            'contact': supplier.contact_info,
            'email': supplier.email,
            'phone': supplier.phone,
            'total_ordered': total_ordered,
            'total_paid': total_paid,
            'balance': balance,
            'purchase_orders_count': len(purchase_orders)
        })
    
    return jsonify(result)

@supplier_accounts_bp.route('/api/supplier-accounts/<int:supplier_id>', methods=['GET'])
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

@supplier_accounts_bp.route('/api/supplier-accounts/<int:supplier_id>/statement', methods=['GET'])
@login_required
def get_supplier_statement(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    
    # Get date range from query parameters
    from_date = request.args.get('from')
    to_date = request.args.get('to')
    
    # Default to last 30 days if not provided
    if not from_date:
        from_date = (datetime.utcnow() - timedelta(days=30)).isoformat()
    if not to_date:
        to_date = datetime.utcnow().isoformat()
    
    # Convert to datetime objects
    from_date = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
    to_date = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
    to_date = to_date.replace(hour=23, minute=59, second=59)  # Include the entire day
    
    # Get ledger entries for this supplier within the date range
    ledger_entries = SupplierLedgerEntry.query.filter(
        SupplierLedgerEntry.supplier_id == supplier.id,
        SupplierLedgerEntry.entry_date >= from_date,
        SupplierLedgerEntry.entry_date <= to_date
    ).order_by(SupplierLedgerEntry.entry_date).all()
    
    # Calculate opening balance (sum of all entries before from_date)
    opening_balance = db.session.query(
        db.func.sum(SupplierLedgerEntry.debit) - db.func.sum(SupplierLedgerEntry.credit)
    ).filter(
        SupplierLedgerEntry.supplier_id == supplier.id,
        SupplierLedgerEntry.entry_date < from_date
    ).scalar() or 0
    
    # Format ledger entries for response
    entries = []
    running_balance = opening_balance
    
    # Add opening balance entry
    entries.append({
        'date': from_date.isoformat(),
        'description': 'رصيد افتتاحي',
        'reference': '',
        'debit': None,
        'credit': None,
        'balance': running_balance
    })
    
    for entry in ledger_entries:
        if entry.debit > 0:
            running_balance += entry.debit
        if entry.credit > 0:
            running_balance -= entry.credit
        
        # Get reference details
        reference = ''
        if entry.reference_type == 'purchase_order':
            reference = f'طلب شراء #{entry.reference_id}'
        elif entry.reference_type == 'payment':
            payment = SupplierPayment.query.get(entry.reference_id)
            if payment and payment.reference:
                reference = payment.reference
            else:
                reference = f'دفعة #{entry.reference_id}'
        
        entries.append({
            'date': entry.entry_date.isoformat(),
            'description': entry.description,
            'reference': reference,
            'debit': entry.debit if entry.debit > 0 else None,
            'credit': entry.credit if entry.credit > 0 else None,
            'balance': running_balance
        })
    
    return jsonify(entries)

@supplier_accounts_bp.route('/api/supplier-accounts/<int:supplier_id>/payments', methods=['POST'])
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

@supplier_accounts_bp.route('/api/supplier-accounts/<int:supplier_id>/pdf', methods=['GET'])
@login_required
def generate_supplier_account_pdf(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    
    # Get supplier account details
    account_details = get_supplier_account_details(supplier_id).get_json()
    
    # Get statement for the last 90 days
    from_date = (datetime.utcnow() - timedelta(days=90)).isoformat()
    to_date = datetime.utcnow().isoformat()
    statement = get_supplier_statement(supplier_id).get_json()
    
    # Render the PDF template
    html = render_template(
        'supplier_account_pdf.html',
        supplier=account_details['supplier'],
        financial_summary=account_details['financial_summary'],
        purchase_orders=account_details['purchase_orders'],
        payments=account_details['payments'],
        statement_items=statement,
        generated_date=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    )
    
    # Generate PDF
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
    
    pdf = pdfkit.from_string(html, False, options=options)
    
    # Create response
    response = BytesIO(pdf)
    
    # Return the PDF as a downloadable file
    return send_file(
        response,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'supplier_account_{supplier.supplier_name}_{datetime.utcnow().strftime("%Y%m%d")}.pdf'
    )

@supplier_accounts_bp.route('/api/supplier-accounts/<int:supplier_id>/excel', methods=['GET'])
@login_required
def generate_supplier_account_excel(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    
    # Get supplier account details
    account_details = get_supplier_account_details(supplier_id).get_json()
    
    # Get statement for the last 90 days
    from_date = (datetime.utcnow() - timedelta(days=90)).isoformat()
    to_date = datetime.utcnow().isoformat()
    statement = get_supplier_statement(supplier_id).get_json()
    
    # Create Excel file with multiple sheets
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # Create summary sheet
        summary_data = {
            'المعلومات': ['اسم المورد', 'معلومات الاتصال', 'البريد الإلكتروني', 'الهاتف', 'العنوان', 'إجمالي المشتريات', 'إجمالي المدفوعات', 'الرصيد المستحق'],
            'القيمة': [
                account_details['supplier']['name'],
                account_details['supplier']['contact'] or '',
                account_details['supplier']['email'] or '',
                account_details['supplier']['phone'] or '',
                account_details['supplier']['address'] or '',
                account_details['financial_summary']['total_ordered'],
                account_details['financial_summary']['total_paid'],
                account_details['financial_summary']['balance']
            ]
        }
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='ملخص الحساب', index=False)
        
        # Create purchase orders sheet
        if account_details['purchase_orders']:
            po_data = []
            for po in account_details['purchase_orders']:
                status_map = {
                    'Pending': 'قيد الانتظار',
                    'Approved': 'تمت الموافقة',
                    'Received': 'تم الاستلام',
                    'Cancelled': 'ملغي'
                }
                
                po_data.append({
                    'رقم الطلب': po['id'],
                    'تاريخ الطلب': po['order_date'].split('T')[0] if po['order_date'] else '',
                    'الحالة': status_map.get(po['status'], po['status']),
                    'عدد العناصر': po['items_count'],
                    'المبلغ الإجمالي': po['total_amount']
                })
            
            po_df = pd.DataFrame(po_data)
            po_df.to_excel(writer, sheet_name='طلبات الشراء', index=False)
        
        # Create payments sheet
        if account_details['payments']:
            payment_data = []
            for payment in account_details['payments']:
                payment_data.append({
                    'رقم الدفعة': payment['id'],
                    'تاريخ الدفع': payment['date'].split('T')[0] if payment['date'] else '',
                    'المبلغ': payment['amount'],
                    'المرجع': payment['reference'] or '',
                    'طريقة الدفع': payment['method'] or '',
                    'ملاحظات': payment['notes'] or ''  # Include the notes field
                })
            
            payment_df = pd.DataFrame(payment_data)
            # Make sure to include all 6 column names
            payment_df.columns = ['رقم الدفعة', 'تاريخ الدفع', 'المبلغ', 'المرجع', 'طريقة الدفع', 'ملاحظات']
            payment_df.to_excel(writer, sheet_name='المدفوعات', index=False)
        
        # Create statement sheet
        if statement:
            statement_data = []
            for entry in statement:
                statement_data.append({
                    'التاريخ': entry['date'].split('T')[0] if entry['date'] else '',
                    'البيان': entry['description'],
                    'المرجع': entry['reference'],
                    'مدين': entry['debit'] if entry['debit'] is not None else '',
                    'دائن': entry['credit'] if entry['credit'] is not None else '',
                    'الرصيد': entry['balance']
                })
            
            statement_df = pd.DataFrame(statement_data)
            statement_df.to_excel(writer, sheet_name='كشف الحساب', index=False)
        
        # Format the Excel file
        workbook = writer.book
        
        # Add formats
        header_format = workbook.add_format({
            'bold': True,
            'text_wrap': True,
            'valign': 'top',
            'align': 'right',
            'bg_color': '#D9EAD3',
            'border': 1
        })
        
        cell_format = workbook.add_format({
            'align': 'right',
            'border': 1
        })
        
        money_format = workbook.add_format({
            'num_format': '#,##0.00 [$ج.م]',
            'align': 'right',
            'border': 1
        })
        
        # Apply formats to each sheet
        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]
            worksheet.set_column('A:Z', 18)  # Set column width
            worksheet.right_to_left()  # Set RTL direction
            
            # Format headers
            for col_num, value in enumerate(worksheet.table.columns):
                worksheet.write(0, col_num, value, header_format)
            
            # Format cells based on sheet
            if sheet_name in ['طلبات الشراء', 'المدفوعات']:
                # Apply money format to amount columns
                amount_col = 4 if sheet_name == 'طلبات الشراء' else 2
                for row in range(1, worksheet.dim_rowmax + 1):
                    worksheet.write_number(row, amount_col, worksheet.table[row][amount_col], money_format)
            
            elif sheet_name == 'كشف الحساب':
                # Apply money format to debit, credit, and balance columns
                for row in range(1, worksheet.dim_rowmax + 1):
                    for col in [3, 4, 5]:  # Debit, Credit, Balance columns
                        if worksheet.table[row][col]:
                            worksheet.write_number(row, col, worksheet.table[row][col], money_format)
            
            elif sheet_name == 'ملخص الحساب':
                # Apply money format to financial values
                for row in range(6, 9):  # Rows with financial data
                    worksheet.write_number(row, 1, worksheet.table[row][1], money_format)
    
    # Reset the file pointer to the beginning
    output.seek(0)
    
    # Return the Excel file as a downloadable file
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'supplier_account_{supplier.supplier_name}_{datetime.utcnow().strftime("%Y%m%d")}.xlsx'
    )


