import os
from flask import Blueprint, current_app, render_template, request, jsonify, redirect, send_file, url_for, flash
from flask_login import login_required, current_user
import pandas as pd
from models import User, db, CashAccount, CashTransaction, CashTransferVoucher, CashReconciliation, Supplier, SupplierLedgerEntry, SupplierPayment
from datetime import datetime, timedelta
import uuid

from utils.pdf_generator import PDFGenerator
from utils.alerts_manager import add_money_transfer_alert

cash_bp = Blueprint('cash', __name__, url_prefix='/cash')

# Helper function to check permissions
def check_permission(permission):
    if not current_user.has_permission(permission):
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return False
    return True

# Dashboard
@cash_bp.route('/dashboard')
@login_required
def dashboard():
    if not check_permission('view_cash_management'):
        return redirect(url_for('dashboard'))

    accounts = CashAccount.query.filter_by(is_active=True).all()
    total_cash = sum(account.current_balance for account in accounts)
    recent_transactions = CashTransaction.query.order_by(CashTransaction.transaction_date.desc()).limit(10).all()

    return render_template('cash/dashboard.html',
                          accounts=accounts,
                          total_cash=total_cash,
                          recent_transactions=recent_transactions)

# Cash Accounts Management
@cash_bp.route('/accounts')
@login_required
def accounts():
    if not check_permission('view_cash_accounts'):
        return redirect(url_for('dashboard'))

    accounts = CashAccount.query.all()
    return render_template('cash/accounts.html', accounts=accounts)

@cash_bp.route('/accounts/add', methods=['GET', 'POST'])
@login_required
def add_account():
    if not check_permission('add_cash_account'):
        return redirect(url_for('cash.accounts'))

    if request.method == 'POST':
        name = request.form.get('name')
        account_type = request.form.get('account_type')
        currency = request.form.get('currency')
        initial_balance = float(request.form.get('initial_balance', 0))

        account = CashAccount(
            name=name,
            account_type=account_type,
            currency=currency,
            initial_balance=initial_balance,
            current_balance=initial_balance,
            created_by=current_user.id
        )

        db.session.add(account)
        db.session.commit()

        # Create initial transaction if balance > 0
        if initial_balance > 0:
            transaction = CashTransaction(
                account_id=account.id,
                transaction_type='deposit',
                amount=initial_balance,
                reference_type='initial_balance',
                description='رصيد افتتاحي',
                created_by=current_user.id
            )
            db.session.add(transaction)
            db.session.commit()

        flash('تم إنشاء الحساب بنجاح', 'success')
        return redirect(url_for('cash.accounts'))

    return render_template('cash/add_account.html')

@cash_bp.route('/accounts/edit/<int:account_id>', methods=['GET', 'POST'])
@login_required
def edit_account(account_id):
    if not check_permission('edit_cash_account'):
        return redirect(url_for('cash.accounts'))

    account = CashAccount.query.get_or_404(account_id)

    if request.method == 'POST':
        account.name = request.form.get('name')
        account.account_type = request.form.get('account_type')
        account.currency = request.form.get('currency')
        account.is_active = 'is_active' in request.form

        db.session.commit()
        flash('تم تحديث الحساب بنجاح', 'success')
        return redirect(url_for('cash.accounts'))

    return render_template('cash/edit_account.html', account=account)

# Transactions
@cash_bp.route('/transactions')
@login_required
def transactions():
    if not check_permission('view_cash_transactions'):
        return redirect(url_for('dashboard'))

    transactions = CashTransaction.query.order_by(CashTransaction.transaction_date.desc()).all()
    accounts = CashAccount.query.filter_by(is_active=True).all()

    return render_template('cash/transactions.html',
                          transactions=transactions,
                          accounts=accounts)

@cash_bp.route('/transactions/add', methods=['GET', 'POST'])
@login_required
def add_transaction():
    if not check_permission('add_cash_transaction'):
        return redirect(url_for('cash.transactions'))

    accounts = CashAccount.query.filter_by(is_active=True).all()

    if request.method == 'POST':
        account_id = request.form.get('account_id')
        transaction_type = request.form.get('transaction_type')
        amount = float(request.form.get('amount', 0))
        description = request.form.get('description')
        transaction_date = datetime.strptime(request.form.get('transaction_date'), '%Y-%m-%d')

        account = CashAccount.query.get(account_id)

        # Update account balance
        if transaction_type == 'deposit':
            account.current_balance += amount
        elif transaction_type == 'withdrawal':
            if account.current_balance < amount:
                flash('رصيد الحساب غير كافي', 'error')
                return redirect(url_for('cash.add_transaction'))
            account.current_balance -= amount

        transaction = CashTransaction(
            account_id=account_id,
            transaction_type=transaction_type,
            amount=amount,
            description=description,
            transaction_date=transaction_date,
            created_by=current_user.id
        )

        db.session.add(transaction)
        db.session.commit()

        flash('تم تسجيل المعاملة بنجاح', 'success')
        return redirect(url_for('cash.transactions'))

    return render_template('cash/add_transaction.html', accounts=accounts)

# Transfer Vouchers
@cash_bp.route('/transfers')
@login_required
def transfers():
    if not check_permission('view_cash_transfers'):
        return redirect(url_for('dashboard'))

    vouchers = CashTransferVoucher.query.order_by(CashTransferVoucher.transfer_date.desc()).all()
    return render_template('cash/transfers.html', vouchers=vouchers)

@cash_bp.route('/transfers/add', methods=['GET', 'POST'])
@login_required
def add_transfer():
    if not check_permission('add_cash_transfer'):
        return redirect(url_for('cash.transfers'))

    accounts = CashAccount.query.filter_by(is_active=True).all()
    suppliers = Supplier.query.all()

    if request.method == 'POST':
        from_account_id = request.form.get('from_account_id')
        transfer_type = request.form.get('transfer_type')  # account or supplier
        to_account_id = request.form.get('to_account_id') if transfer_type == 'account' else None
        supplier_id = request.form.get('supplier_id') if transfer_type == 'supplier' else None
        amount = float(request.form.get('amount', 0))
        notes = request.form.get('notes')

        # Generate voucher number
        voucher_number = f"TRF-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        # Check if from_account has sufficient balance
        from_account = CashAccount.query.get(from_account_id)
        if from_account.current_balance < amount:
            flash('رصيد الحساب غير كافي للتحويل', 'error')
            return redirect(url_for('cash.add_transfer'))

        # Create transfer voucher
        voucher = CashTransferVoucher(
            voucher_number=voucher_number,
            from_account_id=from_account_id,
            to_account_id=to_account_id,
            supplier_id=supplier_id,
            amount=amount,
            notes=notes,
            status='completed',
            created_by=current_user.id
        )

        db.session.add(voucher)

        # Update account balances
        from_account.current_balance -= amount

        # Create transaction for from_account
        from_transaction = CashTransaction(
            account_id=from_account_id,
            transaction_type='withdrawal',
            amount=amount,
            reference_type='transfer_voucher',
            reference_id=voucher.id,
            description=f"تحويل نقدي - {voucher_number}",
            created_by=current_user.id
        )

        db.session.add(from_transaction)

        # If transferring to another account
        if to_account_id:
            to_account = CashAccount.query.get(to_account_id)
            to_account.current_balance += amount

            # Create transaction for to_account
            to_transaction = CashTransaction(
                account_id=to_account_id,
                transaction_type='deposit',
                amount=amount,
                reference_type='transfer_voucher',
                reference_id=voucher.id,
                description=f"تحويل نقدي مستلم - {voucher_number}",
                created_by=current_user.id
            )

            db.session.add(to_transaction)

        # If transferring to a supplier
        elif supplier_id:
            supplier = Supplier.query.get(supplier_id)

            # Create supplier ledger entry
            ledger_entry = SupplierLedgerEntry(
                supplier_id=supplier_id,
                description=f"دفعة نقدية - {voucher_number}",
                reference_type='cash_transfer',
                reference_id=voucher.id,
                credit=amount  # Credit increases what we've paid to supplier
            )

            db.session.add(ledger_entry)

        db.session.commit()

        # Add alert for money transfer
        try:
            from_account_name = from_account.name
            to_account_name = to_account.name if to_account else (supplier.name if supplier else "مورد")
            add_money_transfer_alert(from_account_name, to_account_name, amount, voucher_number)
        except Exception as e:
            # Don't fail the transaction if alert creation fails
            print(f"Failed to create alert: {e}")

        flash('تم إنشاء سند التحويل بنجاح', 'success')
        return redirect(url_for('cash.transfers'))

    return render_template('cash/add_transfer.html', accounts=accounts, suppliers=suppliers)

@cash_bp.route('/transfers/view/<int:voucher_id>')
@login_required
def view_transfer(voucher_id):
    if not check_permission('view_cash_transfers'):
        return redirect(url_for('cash.transfers'))

    voucher = CashTransferVoucher.query.get_or_404(voucher_id)
    return render_template('cash/view_transfer.html', voucher=voucher)

# Cash Reconciliation
@cash_bp.route('/reconciliations')
@login_required
def reconciliations():
    if not check_permission('view_cash_reconciliations'):
        return redirect(url_for('dashboard'))

    reconciliations = CashReconciliation.query.order_by(CashReconciliation.reconciliation_date.desc()).all()
    return render_template('cash/reconciliations.html', reconciliations=reconciliations)

@cash_bp.route('/reconciliations/add', methods=['GET', 'POST'])
@login_required
def add_reconciliation():
    if not check_permission('add_cash_reconciliation'):
        return redirect(url_for('cash.reconciliations'))

    accounts = CashAccount.query.filter_by(is_active=True).all()

    if request.method == 'POST':
        account_id = request.form.get('account_id')
        actual_balance = float(request.form.get('actual_balance', 0))
        notes = request.form.get('notes')

        account = CashAccount.query.get(account_id)
        system_balance = account.current_balance
        difference = actual_balance - system_balance

        reconciliation = CashReconciliation(
            account_id=account_id,
            system_balance=system_balance,
            counted_balance=actual_balance,
            difference=difference,
            notes=notes,
            status='pending',
            performed_by=current_user.id
        )

        db.session.add(reconciliation)
        db.session.commit()

        flash('تم تسجيل الجرد بنجاح وبانتظار الاعتماد', 'success')
        return redirect(url_for('cash.reconciliations'))

    return render_template('cash/add_reconciliation.html', accounts=accounts)

@cash_bp.route('/reconciliations/approve/<int:reconciliation_id>', methods=['POST'])
@login_required
def approve_reconciliation(reconciliation_id):
    if not check_permission('approve_cash_reconciliation'):
        flash('ليس لديك صلاحية لاعتماد الجرد', 'error')
        return redirect(url_for('cash.reconciliations'))

    reconciliation = CashReconciliation.query.get_or_404(reconciliation_id)

    if reconciliation.status != 'pending':
        flash('لا يمكن اعتماد جرد تم اعتماده أو رفضه من قبل', 'error')
        return redirect(url_for('cash.reconciliations'))

    # Update reconciliation status
    reconciliation.status = 'approved'
    reconciliation.approved_by = current_user.id
    reconciliation.approved_at = datetime.utcnow()

    # If there's a difference, create an adjustment transaction
    if reconciliation.difference != 0:
        transaction_type = 'deposit' if reconciliation.difference > 0 else 'withdrawal'
        amount = abs(reconciliation.difference)

        transaction = CashTransaction(
            account_id=reconciliation.account_id,
            transaction_type=transaction_type,
            amount=amount,
            description=f'تسوية جرد #{reconciliation.id}',
            reference_type='reconciliation',
            reference_id=reconciliation.id,
            created_by=current_user.id
        )

        db.session.add(transaction)

        # Update account balance
        account = reconciliation.account
        if transaction_type == 'deposit':
            account.current_balance += amount
        else:
            account.current_balance -= amount

    db.session.commit()

    flash('تم اعتماد الجرد بنجاح', 'success')
    return redirect(url_for('cash.reconciliations'))

@cash_bp.route('/reconciliations/reject/<int:reconciliation_id>', methods=['POST'])
@login_required
def reject_reconciliation(reconciliation_id):
    if not check_permission('approve_cash_reconciliation'):
        flash('ليس لديك صلاحية لرفض الجرد', 'error')
        return redirect(url_for('cash.reconciliations'))

    reconciliation = CashReconciliation.query.get_or_404(reconciliation_id)

    if reconciliation.status != 'pending':
        flash('لا يمكن رفض جرد تم اعتماده أو رفضه من قبل', 'error')
        return redirect(url_for('cash.reconciliations'))

    # Update reconciliation status
    reconciliation.status = 'rejected'
    reconciliation.approved_by = current_user.id
    reconciliation.approved_at = datetime.utcnow()

    db.session.commit()

    flash('تم رفض الجرد بنجاح', 'success')
    return redirect(url_for('cash.reconciliations'))

@cash_bp.route('/api/reconciliation/<int:reconciliation_id>')
@login_required
def get_reconciliation(reconciliation_id):
    if not check_permission('view_cash_reconciliations'):
        return jsonify({'error': 'Unauthorized'}), 403

    reconciliation = CashReconciliation.query.get_or_404(reconciliation_id)

    performer = User.query.get(reconciliation.performed_by)
    approver = User.query.get(reconciliation.approved_by) if reconciliation.approved_by else None

    return jsonify({
        'id': reconciliation.id,
        'account_id': reconciliation.account_id,
        'account_name': reconciliation.account.name,
        'system_balance': reconciliation.system_balance,
        'counted_balance': reconciliation.counted_balance,
        'difference': reconciliation.difference,
        'notes': reconciliation.notes,
        'status': reconciliation.status,
        'reconciliation_date': reconciliation.reconciliation_date.isoformat(),
        'performed_by': performer.username if performer else 'Unknown',
        'approved_by': approver.username if approver else None,
        'currency': reconciliation.account.currency
    })
# API Endpoints for AJAX requests
@cash_bp.route('/api/account/<int:account_id>')
@login_required
def get_account(account_id):
    account = CashAccount.query.get_or_404(account_id)
    return jsonify({
        'id': account.id,
        'name': account.name,
        'current_balance': account.current_balance,
        'currency': account.currency
    })

@cash_bp.route('/api/transactions/<int:account_id>')
@login_required
def get_account_transactions(account_id):
    transactions = CashTransaction.query.filter_by(account_id=account_id).order_by(CashTransaction.transaction_date.desc()).all()

    result = []
    for transaction in transactions:
        creator = transaction.creator.username if transaction.creator else 'N/A'
        reference_info = ""

        # Add reference information if available
        if transaction.reference_type and transaction.reference_id:
            if transaction.reference_type == 'transfer_voucher':
                voucher = CashTransferVoucher.query.get(transaction.reference_id)
                if voucher:
                    reference_info = f"رقم السند: {voucher.voucher_number}"
            elif transaction.reference_type == 'supplier_payment':
                reference_info = f"دفعة مورد #{transaction.reference_id}"
            elif transaction.reference_type == 'reconciliation':
                reference_info = f"تسوية جرد #{transaction.reference_id}"
            elif transaction.reference_type == 'sales_order':
                from models import SalesOrder
                order = SalesOrder.query.get(transaction.reference_id)
                if order:
                    reference_info = f"طلب مبيعات #{order.id}"
            elif transaction.reference_type == 'sales_payment':
                from models import SalesPayment
                payment = SalesPayment.query.get(transaction.reference_id)
                if payment and payment.invoice:
                    reference_info = f"دفعة فاتورة #{payment.invoice.invoice_number}"
            elif transaction.reference_type == 'sales_return':
                from models import SalesReturn
                sales_return = SalesReturn.query.get(transaction.reference_id)
                if sales_return:
                    reference_info = f"مرتجع مبيعات #{sales_return.id}"

        result.append({
            'id': transaction.id,
            'type': transaction.transaction_type,
            'amount': transaction.amount,
            'description': transaction.description or '',
            'reference_info': reference_info,
            'date': transaction.transaction_date.strftime('%Y-%m-%d %H:%M'),
            'created_by': creator
        })

    return jsonify(result)

# Reports
@cash_bp.route('/reports')
@login_required
def reports():
    if not check_permission('view_cash_reports'):
        return redirect(url_for('dashboard'))

    # Get all accounts for the dropdown
    accounts = CashAccount.query.filter_by(is_active=True).all()

    # Get all suppliers for the dropdown
    suppliers = Supplier.query.all()

    # Get recent reports (you'll need to create a CashReport model)
    recent_reports = []  # This will be populated from the database if you implement report tracking

    return render_template('cash/reports.html',
                          accounts=accounts,
                          suppliers=suppliers,
                          recent_reports=recent_reports)


@cash_bp.route('/generate-report', methods=['POST'])
@login_required
def generate_report():
    if not check_permission('generate_cash_reports'):
        return jsonify({'success': False, 'message': 'ليس لديك صلاحية لإنشاء التقارير'})

    # Get form data
    report_type = request.form.get('report_type')
    date_from = datetime.strptime(request.form.get('date_from'), '%Y-%m-%d')
    date_to = datetime.strptime(request.form.get('date_to'), '%Y-%m-%d')
    # Add one day to date_to to include the entire day
    date_to = date_to + timedelta(days=1)

    account_id = request.form.get('account_id')
    supplier_id = request.form.get('supplier_id')
    transaction_type = request.form.get('transaction_type')
    report_format = request.form.get('report_format')
    is_preview = request.form.get('preview') == 'true'

    # Initialize report generator
    report_generator = PDFGenerator()

    # Generate report based on type
    if report_type == 'account_statement':
        # Get account if specified
        account = None
        if account_id:
            account = CashAccount.query.get(account_id)

        # Build query for transactions
        query = CashTransaction.query.filter(
            CashTransaction.transaction_date.between(date_from, date_to)
        )

        if account_id:
            query = query.filter(CashTransaction.account_id == account_id)

        if transaction_type:
            query = query.filter(CashTransaction.transaction_type == transaction_type)

        transactions = query.order_by(CashTransaction.transaction_date).all()

        # Generate report
        report_path = report_generator.generate_account_statement(
            account, transactions, date_from, date_to, report_format
        )

        report_name = f"كشف_حساب_{date_from.strftime('%Y%m%d')}_الى_{date_to.strftime('%Y%m%d')}"

    elif report_type == 'cash_flow':
        # Get account if specified
        accounts = CashAccount.query.filter_by(is_active=True).all()
        if account_id:
            accounts = [account for account in accounts if str(account.id) == account_id]

        # Get transactions for the period
        query = CashTransaction.query.filter(
            CashTransaction.transaction_date.between(date_from, date_to)
        )

        if account_id:
            query = query.filter(CashTransaction.account_id == account_id)

        transactions = query.all()

        # Generate report
        report_path = report_generator.generate_cash_flow(
            accounts, transactions, date_from, date_to, report_format
        )

        report_name = f"التدفق_النقدي_{date_from.strftime('%Y%m%d')}_الى_{date_to.strftime('%Y%m%d')}"

    elif report_type == 'supplier_payments':
        # Get supplier if specified
        supplier = None
        if supplier_id:
            supplier = Supplier.query.get(supplier_id)

        # Build query for payments
        query = CashTransferVoucher.query.filter(
            CashTransferVoucher.transfer_date.between(date_from, date_to),
            CashTransferVoucher.supplier_id.isnot(None)  # Only get supplier payments
        )

        if supplier_id:
            query = query.filter(CashTransferVoucher.supplier_id == supplier_id)

        if account_id:
            query = query.filter(CashTransferVoucher.from_account_id == account_id)

        payments = query.order_by(CashTransferVoucher.transfer_date).all()

        # Generate report
        report_path = report_generator.generate_supplier_payments(
            supplier, payments, date_from, date_to, report_format
        )

        report_name = f"دفعات_الموردين_{date_from.strftime('%Y%m%d')}_الى_{date_to.strftime('%Y%m%d')}"

    elif report_type == 'transactions_summary':
        # Build query for transactions
        query = CashTransaction.query.filter(
            CashTransaction.transaction_date.between(date_from, date_to)
        )

        if account_id:
            query = query.filter(CashTransaction.account_id == account_id)

        if transaction_type:
            query = query.filter(CashTransaction.transaction_type == transaction_type)

        transactions = query.order_by(CashTransaction.transaction_date).all()

        # Generate report
        report_path = report_generator.generate_transactions_summary(
            transactions, date_from, date_to, report_format
        )

        report_name = f"ملخص_المعاملات_{date_from.strftime('%Y%m%d')}_الى_{date_to.strftime('%Y%m%d')}"

    elif report_type == 'reconciliation':
        # Build query for reconciliations
        query = CashReconciliation.query.filter(
            CashReconciliation.reconciliation_date.between(date_from, date_to)
        )

        if account_id:
            query = query.filter(CashReconciliation.account_id == account_id)

        reconciliations = query.order_by(CashReconciliation.reconciliation_date).all()

        # Generate report
        report_path = report_generator.generate_reconciliation_report(
            reconciliations, date_from, date_to, report_format
        )

        report_name = f"جرد_الخزينة_{date_from.strftime('%Y%m%d')}_الى_{date_to.strftime('%Y%m%d')}"

    else:
        return jsonify({'success': False, 'message': 'نوع التقرير غير صالح'})

    # If this is a preview request, return the URL
    if is_preview:
        preview_url = url_for('cash.view_report', path=os.path.basename(report_path))
        return jsonify({'success': True, 'preview_url': preview_url})

    # If HTML format is requested, redirect to the report view
    if report_format == 'html':
        return redirect(url_for('cash.view_report', path=os.path.basename(report_path)))

    # For PDF and Excel, send the file as attachment
    try:
        return send_file(
            report_path,
            as_attachment=True,
            download_name=f"{report_name}.{report_format}",
            mimetype='application/pdf' if report_format == 'pdf' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        return jsonify({'success': False, 'message': f'حدث خطأ أثناء إنشاء التقرير: {str(e)}'})

@cash_bp.route('/view-report')
@login_required
def view_report():
    if not check_permission('view_cash_reports'):
        return redirect(url_for('dashboard'))

    # Get the report path from the query parameter
    report_path = request.args.get('path')
    if not report_path:
        flash('مسار التقرير غير صالح', 'error')
        return redirect(url_for('cash.reports'))

    # Construct the full path
    full_path = os.path.join(current_app.config['TEMP_FOLDER'], report_path)

    # Check if the file exists
    if not os.path.exists(full_path):
        flash('التقرير غير موجود', 'error')
        return redirect(url_for('cash.reports'))

    # Determine the file type
    if full_path.endswith('.pdf'):
        return send_file(full_path, mimetype='application/pdf')
    elif full_path.endswith('.xlsx'):
        # For Excel files, we'll convert to HTML for viewing
        try:
            df = pd.read_excel(full_path)
            html_table = df.to_html(classes='table table-striped table-bordered', index=False)
            return render_template('cash/report_view.html', report_html=html_table)
        except Exception as e:
            flash(f'حدث خطأ أثناء عرض التقرير: {str(e)}', 'error')
            return redirect(url_for('cash.reports'))
    else:
        flash('نوع الملف غير مدعوم للعرض', 'error')
        return redirect(url_for('cash.reports'))

@cash_bp.route('/print-report')
@login_required
def print_report():
    if not check_permission('print_cash_reports'):
        return jsonify({'success': False, 'message': 'ليس لديك صلاحية لطباعة التقارير'})

    # Get the report path from the query parameter
    report_path = request.args.get('path')
    if not report_path:
        return jsonify({'success': False, 'message': 'مسار التقرير غير صالح'})

    # Construct the full path
    full_path = os.path.join(current_app.config['TEMP_FOLDER'], report_path)

    # Check if the file exists
    if not os.path.exists(full_path):
        return jsonify({'success': False, 'message': 'التقرير غير موجود'})

    # Return a URL that will open the file for printing
    print_url = url_for('cash.view_report', path=os.path.basename(full_path))
    return jsonify({'success': True, 'print_url': print_url})

@cash_bp.route('/download-report/<int:report_id>')
@login_required
def download_report(report_id):
    if not check_permission('download_cash_reports'):
        flash('ليس لديك صلاحية لتنزيل التقارير', 'error')
        return redirect(url_for('cash.reports'))

    # This would be implemented if you have a CashReport model to track reports
    # For now, we'll just redirect to the reports page
    flash('هذه الميزة غير متاحة حاليًا', 'info')
    return redirect(url_for('cash.reports'))

@cash_bp.route('/reports/account-statement', methods=['GET', 'POST'])
@login_required
def account_statement_report():
    if not check_permission('view_cash_reports'):
        return redirect(url_for('cash.reports'))

    accounts = CashAccount.query.filter_by(is_active=True).all()
    transactions = []

    if request.method == 'POST':
        account_id = request.form.get('account_id')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')

        query = CashTransaction.query.filter_by(account_id=account_id)

        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(CashTransaction.transaction_date >= start_date)

        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d')
            query = query.filter(CashTransaction.transaction_date <= end_date)

        transactions = query.order_by(CashTransaction.transaction_date).all()

    return render_template('cash/account_statement.html',
                          accounts=accounts,
                          transactions=transactions)

@cash_bp.route('/reports/cash-flow', methods=['GET', 'POST'])
@login_required
def cash_flow_report():
    if not check_permission('view_cash_reports'):
        return redirect(url_for('cash.reports'))

    accounts = CashAccount.query.filter_by(is_active=True).all()
    results = []

    if request.method == 'POST':
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')

        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
        else:
            start_date = datetime(datetime.now().year, datetime.now().month, 1)

        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d')
        else:
            end_date = datetime.now()

        for account in accounts:
            deposits = db.session.query(db.func.sum(CashTransaction.amount)).filter(
                CashTransaction.account_id == account.id,
                CashTransaction.transaction_type == 'deposit',
                CashTransaction.transaction_date.between(start_date, end_date)
            ).scalar() or 0

            withdrawals = db.session.query(db.func.sum(CashTransaction.amount)).filter(
                CashTransaction.account_id == account.id,
                CashTransaction.transaction_type == 'withdrawal',
                CashTransaction.transaction_date.between(start_date, end_date)
            ).scalar() or 0

            results.append({
                'account': account,
                'deposits': deposits,
                'withdrawals': withdrawals,
                'net': deposits - withdrawals
            })

    return render_template('cash/cash_flow.html',
                          accounts=accounts,
                          results=results)

# Supplier payments
@cash_bp.route('/supplier-payments')
@login_required
def supplier_payments():
    if not check_permission('view_supplier_payments'):
        return redirect(url_for('dashboard'))

    # Get all transfers to suppliers
    vouchers = CashTransferVoucher.query.filter(CashTransferVoucher.supplier_id.isnot(None)).order_by(CashTransferVoucher.transfer_date.desc()).all()
    return render_template('cash/supplier_payments.html', vouchers=vouchers)

@cash_bp.route('/supplier-payments/add', methods=['GET', 'POST'])
@login_required
def add_supplier_payment():
    if not check_permission('add_supplier_payment'):
        return redirect(url_for('cash.supplier_payments'))

    accounts = CashAccount.query.filter_by(is_active=True).all()
    suppliers = Supplier.query.all()

    if request.method == 'POST':
        from_account_id = request.form.get('account_id')
        supplier_id = request.form.get('supplier_id')
        amount = float(request.form.get('amount', 0))
        payment_date = datetime.strptime(request.form.get('payment_date'), '%Y-%m-%d')
        payment_method = request.form.get('payment_method')
        reference = request.form.get('reference')
        notes = request.form.get('notes')

        # Generate voucher number
        voucher_number = f"SPV-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        # Check if from_account has sufficient balance
        from_account = CashAccount.query.get(from_account_id)
        if from_account.current_balance < amount:
            flash('رصيد الحساب غير كافي للدفع', 'error')
            return redirect(url_for('cash.add_supplier_payment'))

        # Create transfer voucher
        voucher = CashTransferVoucher(
            voucher_number=voucher_number,
            from_account_id=from_account_id,
            to_account_id=None,
            supplier_id=supplier_id,
            amount=amount,
            transfer_date=payment_date,
            notes=notes,
            status='completed',
            created_by=current_user.id
        )

        db.session.add(voucher)

        # Update account balance
        from_account.current_balance -= amount

        # Create transaction for from_account
        from_transaction = CashTransaction(
            account_id=from_account_id,
            transaction_type='withdrawal',
            amount=amount,
            transaction_date=payment_date,
            reference_type='supplier_payment',
            reference_id=voucher.id,
            description=f"دفعة للمورد - {voucher_number}",
            created_by=current_user.id
        )

        db.session.add(from_transaction)

        # Create supplier payment record
        supplier = Supplier.query.get(supplier_id)
        supplier_payment = SupplierPayment(
            supplier_id=supplier_id,
            amount=amount,
            payment_date=payment_date,
            payment_method=payment_method,
            reference=reference or voucher_number,
            notes=notes,
            created_by=current_user.id
        )

        db.session.add(supplier_payment)
        db.session.flush()  # Get the payment ID

        # Create supplier ledger entry
        ledger_entry = SupplierLedgerEntry(
            supplier_id=supplier_id,
            entry_date=payment_date,
            description=f"دفعة نقدية - {voucher_number}",
            reference_type='payment',
            reference_id=supplier_payment.id,  # Reference the payment record
            debit=0,
            credit=amount
        )

        db.session.add(ledger_entry)

        # Also create a cash transfer ledger entry for tracking
        cash_transfer_ledger = SupplierLedgerEntry(
            supplier_id=supplier_id,
            entry_date=payment_date,
            description=f"تحويل نقدي - {voucher_number}",
            reference_type='cash_transfer',
            reference_id=voucher.id,  # Reference the voucher
            debit=0,
            credit=0  # This is just for tracking the cash transfer
        )

        db.session.add(cash_transfer_ledger)
        db.session.commit()

        flash(f'تم تسجيل دفعة بمبلغ {amount} للمورد {supplier.supplier_name} بنجاح', 'success')
        return redirect(url_for('cash.supplier_payments'))

    return render_template('cash/add_supplier_payment.html', accounts=accounts, suppliers=suppliers)

# API endpoint for cash accounts (accessible globally)
@cash_bp.route('/api/cash-accounts')
@login_required
def api_cash_accounts():
    """API endpoint to get all active cash accounts"""
    if not check_permission('view_cash_management'):
        return jsonify({'error': 'Permission denied'}), 403

    accounts = CashAccount.query.filter_by(is_active=True).all()

    accounts_data = []
    for account in accounts:
        accounts_data.append({
            'id': account.id,
            'name': account.name,
            'account_type': account.account_type,
            'currency': account.currency,
            'current_balance': account.current_balance,
            'is_active': account.is_active
        })

    return jsonify(accounts_data)

@cash_bp.route('/supplier-payments/view/<int:voucher_id>')
@login_required
def view_supplier_payment(voucher_id):
    if not check_permission('view_supplier_payments'):
        return redirect(url_for('dashboard'))

    voucher = CashTransferVoucher.query.get_or_404(voucher_id)

    if not voucher.supplier_id:
        flash('هذا ليس سند دفع لمورد', 'error')
        return redirect(url_for('cash.supplier_payments'))

    return render_template('cash/view_supplier_payment.html', voucher=voucher)

