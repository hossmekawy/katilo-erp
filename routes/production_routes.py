from flask import Blueprint, request, jsonify, render_template, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from sqlalchemy import desc
from datetime import datetime
import json
import os
from flask import send_file
from utils.pdf_generator import PDFGenerator
from models import (
    Category, db, Item, Batch, ProductionOrder, ProductionLine, ProductionStep,
    ProductionStepRecord, ProductionParameter, QCTest, QCTestResult,
    PackagingOrder, PackagingLine, PackagingMaterialUsage, ProductLabel,
    Inventory, InventoryTransaction, Warehouse, BOM, BOMDetail
)

production_bp = Blueprint('production', __name__, url_prefix='/production')

# Production Order Management
@production_bp.route('/orders', methods=['GET'])
@login_required
def production_orders():
    orders = ProductionOrder.query.order_by(desc(ProductionOrder.created_at)).all()
    production_lines = ProductionLine.query.filter_by(is_active=True).all()
    return render_template('production/orders.html', orders=orders, production_lines=production_lines)

@production_bp.route('/orders/create', methods=['GET', 'POST'])
@login_required
def create_production_order():
    if request.method == 'POST':
        try:
            data = request.form
            product_id = int(data.get('product_id'))
            quantity = int(data.get('quantity'))
            production_line_id = int(data.get('production_line_id')) if data.get('production_line_id') else None
            warehouse_id = int(data.get('warehouse_id'))
            scheduled_start = datetime.strptime(data.get('scheduled_start'), '%Y-%m-%dT%H:%M')
            scheduled_end = datetime.strptime(data.get('scheduled_end'), '%Y-%m-%dT%H:%M')

            # Check if BOM exists for the product
            bom = BOM.query.filter_by(final_product_id=product_id).first()
            if not bom:
                flash('لا توجد قائمة مواد لهذا المنتج. يرجى إنشاء قائمة المواد أولاً.', 'danger')
                return redirect(url_for('production.create_production_order', product_id=product_id))

            # Check material availability
            bom_details = BOMDetail.query.filter_by(bom_id=bom.id).all()
            for detail in bom_details:
                inventory = Inventory.query.filter_by(
                    item_id=detail.component_item_id,
                    warehouse_id=warehouse_id
                ).first()

                required_qty = detail.quantity_required * quantity
                if not inventory or inventory.quantity < required_qty:
                    flash(f'Insufficient stock for component {detail.component_item.name}', 'danger')
                    return redirect(url_for('production.create_production_order'))

            # Create production order
            new_order = ProductionOrder(
                product_id=product_id,
                quantity=quantity,
                production_line_id=production_line_id,
                scheduled_start=scheduled_start,
                scheduled_end=scheduled_end,
                status='Planned',
                created_by=current_user.id
            )
            db.session.add(new_order)
            db.session.commit()

            # Create batch
            new_batch = Batch(
                item_id=product_id,
                lot_number=f"LOT-{datetime.now().strftime('%Y%m%d')}-{new_order.id}",
                production_date=datetime.now(),
                quantity=quantity,
                production_order_id=new_order.id,
                status='Created'
            )
            db.session.add(new_batch)
            db.session.commit()

            # Reserve materials
            for detail in bom_details:
                required_qty = detail.quantity_required * quantity
                inventory = Inventory.query.filter_by(
                    item_id=detail.component_item_id,
                    warehouse_id=warehouse_id
                ).first()

                # Create transaction to reserve materials
                transaction = InventoryTransaction(
                    item_id=detail.component_item_id,
                    warehouse_id=warehouse_id,
                    transaction_type='OUT',
                    quantity=required_qty,
                    reference=f"Reserved for Production Order #{new_order.id}"
                )
                db.session.add(transaction)

                # Update inventory
                inventory.quantity -= required_qty

            db.session.commit()
            flash('Production order created successfully!', 'success')
            return redirect(url_for('production.production_orders'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error creating production order: {str(e)}', 'danger')
            return redirect(url_for('production.create_production_order'))

    # GET request - show form
    products = Item.query.join(Category).filter(Category.category_type == 'FinalProduct').all()
    production_lines = ProductionLine.query.filter_by(is_active=True).all()
    warehouses = Warehouse.query.all()
    return render_template('production/create_order.html',
                          products=products,
                          production_lines=production_lines,
                          warehouses=warehouses)

@production_bp.route('/orders/<int:order_id>', methods=['GET'])
@login_required
def view_production_order(order_id):
    order = ProductionOrder.query.get_or_404(order_id)
    batches = Batch.query.filter_by(production_order_id=order_id).all()
    production_lines = ProductionLine.query.filter_by(is_active=True).all()

    # Get BOM data for the product
    bom_data = {}
    bom = BOM.query.filter_by(final_product_id=order.product_id).first()

    if bom:
        bom_details = BOMDetail.query.filter_by(bom_id=bom.id).all()
        components = []

        for detail in bom_details:
            component = Item.query.get(detail.component_item_id)
            components.append({
                'id': component.id,
                'name': component.name,
                'quantity_required': detail.quantity_required,
                'unit_of_measure': detail.unit_of_measure or component.unit_of_measure
            })

        bom_data = {
            'bom': bom,
            'components': components
        }

    return render_template('production/view_order.html',
                          order=order,
                          batches=batches,
                          production_lines=production_lines,
                          bom_data=bom_data)
# Production Line Management
# Production Line Management
@production_bp.route('/lines', methods=['GET'])
@login_required
def production_lines():
    lines = ProductionLine.query.all()

    # Get current production orders for each line
    for line in lines:
        current_order = ProductionOrder.query.filter_by(
            production_line_id=line.id,
            status='InProgress'
        ).first()

        line.current_order_id = current_order.id if current_order else None

    return render_template('production/lines.html', lines=lines)

@production_bp.route('/lines/assign', methods=['POST'])
@login_required
def assign_line_to_production():
    try:
        data = request.form
        order_id = int(data.get('order_id'))
        line_id = int(data.get('line_id'))

        order = ProductionOrder.query.get_or_404(order_id)
        order.production_line_id = line_id
        db.session.commit()

        flash('Production order assigned to line successfully!', 'success')
    except Exception as e:
        flash(f'Error assigning production line: {str(e)}', 'danger')

    return redirect(url_for('production.production_orders'))

@production_bp.route('/lines/create', methods=['POST'])
@login_required
def create_production_line():
    try:
        current_app.logger.info("Received request to create production line")
        data = request.form
        current_app.logger.info(f"Form data: {data}")
        name = data.get('name')
        description = data.get('description', '')
        capacity = data.get('capacity')
        capacity_unit = data.get('capacity_unit', 'وحدة')
        capacity_period = data.get('capacity_period', 'يوم')
        location = data.get('location', '')
        is_active = 'is_active' in data

        # Validate required fields
        if not name:
            current_app.logger.error("Name is required")
            flash('اسم خط الإنتاج مطلوب', 'danger')
            return redirect(url_for('production.production_lines'))

        # Convert capacity to float if provided
        capacity_per_hour = None
        if capacity:
            try:
                capacity_per_hour = float(capacity)
            except ValueError:
                current_app.logger.error(f"Invalid capacity value: {capacity}")
                flash('قيمة السعة الإنتاجية يجب أن تكون رقمية', 'danger')
                return redirect(url_for('production.production_lines'))

        # Create new production line
        current_app.logger.info("Creating new production line")
        new_line = ProductionLine(
            name=name,
            description=description,
            capacity_per_hour=capacity_per_hour,
            is_active=is_active,
            location=location,
            capacity_unit=capacity_unit,
            capacity_period=capacity_period
        )

        db.session.add(new_line)
        db.session.commit()
        current_app.logger.info(f"Production line created successfully with ID: {new_line.id}")

        flash('تم إضافة خط الإنتاج بنجاح!', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating production line: {str(e)}")
        flash(f'حدث خطأ أثناء إضافة خط الإنتاج: {str(e)}', 'danger')

    return redirect(url_for('production.production_lines'))

@production_bp.route('/lines/update', methods=['POST'])
@login_required
def update_production_line():
    try:
        data = request.form
        line_id = int(data.get('line_id'))
        name = data.get('name')
        description = data.get('description', '')
        capacity = data.get('capacity')
        capacity_unit = data.get('capacity_unit', 'وحدة')
        capacity_period = data.get('capacity_period', 'يوم')
        location = data.get('location', '')
        is_active = 'is_active' in data

        # Validate required fields
        if not name:
            flash('اسم خط الإنتاج مطلوب', 'danger')
            return redirect(url_for('production.production_lines'))

        # Convert capacity to float if provided
        capacity_per_hour = None
        if capacity:
            try:
                capacity_per_hour = float(capacity)
            except ValueError:
                flash('قيمة السعة الإنتاجية يجب أن تكون رقمية', 'danger')
                return redirect(url_for('production.production_lines'))

        # Update production line
        line = ProductionLine.query.get_or_404(line_id)
        line.name = name
        line.description = description
        line.capacity_per_hour = capacity_per_hour
        line.capacity_unit = capacity_unit
        line.capacity_period = capacity_period
        line.location = location
        line.is_active = is_active

        db.session.commit()

        flash('تم تحديث خط الإنتاج بنجاح!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'حدث خطأ أثناء تحديث خط الإنتاج: {str(e)}', 'danger')

    return redirect(url_for('production.production_lines'))

@production_bp.route('/lines/delete', methods=['POST'])
@login_required
def delete_production_line():
    try:
        line_id = int(request.form.get('line_id'))
        line = ProductionLine.query.get_or_404(line_id)

        # Check if line is currently in use
        active_orders = ProductionOrder.query.filter_by(
            production_line_id=line_id,
            status='InProgress'
        ).first()

        if active_orders:
            flash('لا يمكن حذف خط الإنتاج لأنه قيد الاستخدام حالياً', 'danger')
            return redirect(url_for('production.production_lines'))

        # Check if line has any completed orders (optional - can be removed if you want to allow deletion)
        has_orders = ProductionOrder.query.filter_by(production_line_id=line_id).first()
        if has_orders:
            # Instead of deleting, mark as inactive
            line.is_active = False
            db.session.commit()
            flash('تم تعطيل خط الإنتاج بنجاح. لم يتم حذفه لأنه مرتبط بأوامر إنتاج سابقة.', 'warning')
        else:
            # Delete the line if it has no orders
            db.session.delete(line)
            db.session.commit()
            flash('تم حذف خط الإنتاج بنجاح!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'حدث خطأ أثناء حذف خط الإنتاج: {str(e)}', 'danger')

    return redirect(url_for('production.production_lines'))


# Batch Production Steps
@production_bp.route('/batches/<int:batch_id>/steps', methods=['GET'])
@login_required
def batch_steps(batch_id):
    batch = Batch.query.get_or_404(batch_id)
    steps = ProductionStep.query.filter_by(is_active=True).order_by(ProductionStep.sequence_number).all()
    step_records = ProductionStepRecord.query.filter_by(batch_id=batch_id).all()

    completed_steps = [record.step_id for record in step_records if record.end_time]

    return render_template('production/batch_steps.html',
                          batch=batch,
                          steps=steps,
                          step_records=step_records,
                          completed_steps=completed_steps)

@production_bp.route('/orders/assign-line', methods=['POST'])
@login_required
def assign_production_line():
    try:
        data = request.form
        order_id = int(data.get('order_id'))
        line_id = int(data.get('line_id'))

        order = ProductionOrder.query.get_or_404(order_id)
        order.production_line_id = line_id
        db.session.commit()

        flash('تم تعيين خط الإنتاج بنجاح!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'حدث خطأ أثناء تعيين خط الإنتاج: {str(e)}', 'danger')

    return redirect(url_for('production.view_production_order', order_id=order_id))

@production_bp.route('/orders/start-production', methods=['POST'])
@login_required
def start_production():
    try:
        order_id = int(request.form.get('order_id'))
        order = ProductionOrder.query.get_or_404(order_id)

        # Check if production line is assigned
        if not order.production_line_id:
            flash('يجب تعيين خط إنتاج قبل بدء الإنتاج!', 'danger')
            return redirect(url_for('production.view_production_order', order_id=order_id))

        # Check if BOM exists for the product
        bom = BOM.query.filter_by(final_product_id=order.product_id).first()
        if not bom:
            flash('لا توجد قائمة مواد لهذا المنتج. يرجى إنشاء قائمة المواد أولاً.', 'danger')
            return redirect(url_for('production.view_production_order', order_id=order_id))

        # Update order status and set actual start time
        order.status = 'InProgress'
        order.actual_start = datetime.now()

        # Update batches status
        batches = Batch.query.filter_by(production_order_id=order_id).all()
        for batch in batches:
            if batch.status == 'Created':
                batch.status = 'InProduction'

        db.session.commit()
        flash('تم بدء الإنتاج بنجاح!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'حدث خطأ أثناء بدء الإنتاج: {str(e)}', 'danger')

    return redirect(url_for('production.view_production_order', order_id=order_id))

@production_bp.route('/orders/cancel', methods=['POST'])
@login_required
def cancel_production_order():
    try:
        order_id = int(request.form.get('order_id'))
        cancel_reason = request.form.get('cancel_reason', '')

        order = ProductionOrder.query.get_or_404(order_id)

        # Check if order can be cancelled
        if order.status in ['Completed', 'Cancelled']:
            flash('لا يمكن إلغاء أمر إنتاج مكتمل أو ملغي بالفعل!', 'danger')
            return redirect(url_for('production.view_production_order', order_id=order_id))

        # Update order status
        order.status = 'Cancelled'
        order.notes = cancel_reason

        # Update batches status
        batches = Batch.query.filter_by(production_order_id=order_id).all()
        for batch in batches:
            if batch.status not in ['QCPassed', 'Packaged', 'Stored']:
                batch.status = 'Cancelled'

        # Return reserved materials to inventory
        if order.status == 'Planned':
            # Get BOM for the product
            bom = BOM.query.filter_by(final_product_id=order.product_id).first()
            if bom:
                bom_details = BOMDetail.query.filter_by(bom_id=bom.id).all()

                for detail in bom_details:
                    required_qty = detail.quantity_required * order.quantity

                    # Find inventory record
                    inventory = Inventory.query.filter_by(
                        item_id=detail.component_item_id
                    ).first()

                    if inventory:
                        # Create transaction to return materials
                        transaction = InventoryTransaction(
                            item_id=detail.component_item_id,
                            warehouse_id=inventory.warehouse_id,
                            transaction_type='IN',
                            quantity=required_qty,
                            reference=f"Returned from cancelled Production Order #{order_id}"
                        )
                        db.session.add(transaction)

                        # Update inventory
                        inventory.quantity += required_qty

        db.session.commit()
        flash('تم إلغاء أمر الإنتاج بنجاح!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'حدث خطأ أثناء إلغاء أمر الإنتاج: {str(e)}', 'danger')

    return redirect(url_for('production.view_production_order', order_id=order_id))

@production_bp.route('/batches/<int:batch_id>/steps/record', methods=['POST'])
@login_required
def record_step(batch_id):
    try:
        data = request.form
        step_id = int(data.get('step_id'))
        notes = data.get('notes', '')
        parameters = {}

        # Extract parameters from form
        for key, value in data.items():
            if key.startswith('param_'):
                param_name = key.replace('param_', '')
                parameters[param_name] = value

        # Check if step already recorded
        existing_record = ProductionStepRecord.query.filter_by(
            batch_id=batch_id,
            step_id=step_id
        ).first()

        if existing_record:
            # Update existing record
            existing_record.end_time = datetime.now()
            existing_record.notes = notes
            existing_record.parameters = parameters
        else:
            # Create new record
            new_record = ProductionStepRecord(
                batch_id=batch_id,
                step_id=step_id,
                start_time=datetime.now(),
                operator_id=current_user.id,
                notes=notes,
                parameters=parameters
            )
            db.session.add(new_record)

        # Update batch status
        batch = Batch.query.get(batch_id)
        batch.status = 'InProduction'

        db.session.commit()
        flash('Production step recorded successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error recording production step: {str(e)}', 'danger')

    return redirect(url_for('production.batch_steps', batch_id=batch_id))

# Production Parameters Monitoring
@production_bp.route('/batches/<int:batch_id>/parameters', methods=['GET', 'POST'])
@login_required
def monitor_parameters(batch_id):
    batch = Batch.query.get_or_404(batch_id)

    if request.method == 'POST':
        try:
            data = request.form
            parameter_name = data.get('parameter_name')
            parameter_value = data.get('parameter_value')

            new_parameter = ProductionParameter(
                batch_id=batch_id,
                parameter_name=parameter_name,
                parameter_value=parameter_value,
                recorded_by=current_user.id
            )
            db.session.add(new_parameter)
            db.session.commit()

            flash('Parameter recorded successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error recording parameter: {str(e)}', 'danger')

    parameters = ProductionParameter.query.filter_by(batch_id=batch_id).order_by(
        ProductionParameter.recorded_at.desc()).all()

    return render_template('production/parameters.html', batch=batch, parameters=parameters)

# Complete Production Batch
@production_bp.route('/batches/<int:batch_id>/complete', methods=['POST'])
@login_required
def complete_batch(batch_id):
    try:
        batch = Batch.query.get_or_404(batch_id)

        # Check if all steps are completed
        steps = ProductionStep.query.filter_by(is_active=True).all()
        step_records = ProductionStepRecord.query.filter_by(batch_id=batch_id).all()

        completed_step_ids = [record.step_id for record in step_records if record.end_time]
        all_step_ids = [step.id for step in steps]

        if not all(step_id in completed_step_ids for step_id in all_step_ids):
            flash('Cannot complete batch: Not all production steps are completed.', 'danger')
            return redirect(url_for('production.batch_steps', batch_id=batch_id))

        # Update batch status
        batch.status = 'QCPending'

        # Update production order status if all batches are completed
        order = ProductionOrder.query.get(batch.production_order_id)
        all_batches = Batch.query.filter_by(production_order_id=order.id).all()

        if all(b.status in ['QCPending', 'QCPassed', 'Packaged', 'Stored'] for b in all_batches):
            order.status = 'Completed'
            order.actual_end = datetime.now()

        db.session.commit()
        flash('Production batch completed successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error completing batch: {str(e)}', 'danger')

    return redirect(url_for('production.view_production_order', order_id=batch.production_order_id))

# Quality Control
@production_bp.route('/qc/tests', methods=['GET'])
@login_required
def qc_tests():
    tests = QCTest.query.order_by(QCTest.created_at.desc()).all()
    return render_template('production/qc_tests.html', tests=tests)

@production_bp.route('/qc/create_test', methods=['GET', 'POST'])
@login_required
def create_qc_test():
    if request.method == 'POST':
        try:
            data = request.form
            batch_id = int(data.get('batch_id'))
            test_type = data.get('test_type')
            notes = data.get('notes', '')

            # Create new QC test
            new_test = QCTest(
                batch_id=batch_id,
                test_type=test_type,
                status='Pending',
                inspector_id=current_user.id,
                notes=notes
            )
            db.session.add(new_test)

            # Process test parameters if provided
            param_count = 1
            parameters = {}
            while f'param_name_{param_count}' in data:
                param_name = data.get(f'param_name_{param_count}')
                expected_value = data.get(f'expected_value_{param_count}')

                if param_name and expected_value:
                    parameters[param_name] = {
                        'expected': expected_value,
                        'id': param_count
                    }

                param_count += 1

            # Store parameters as JSON if any were provided
            if parameters:
                new_test.parameters = parameters

            # Update batch status to indicate it's under QC testing
            batch = Batch.query.get_or_404(batch_id)
            if batch.status == 'QCPending':
                batch.status = 'QCInProgress'

            db.session.commit()

            flash('تم إنشاء فحص الجودة بنجاح!', 'success')
            return redirect(url_for('production.record_test_results', test_id=new_test.id))
        except Exception as e:
            db.session.rollback()
            flash(f'حدث خطأ أثناء إنشاء فحص الجودة: {str(e)}', 'danger')
            return redirect(url_for('production.create_qc_test'))

    # GET request - show form
    batches = Batch.query.filter_by(status='QCPending').all()
    return render_template('production/create_qc_test.html', batches=batches)

@production_bp.route('/qc/tests/<int:test_id>/results', methods=['GET', 'POST'])
@login_required
def record_test_results(test_id):
    test = QCTest.query.get_or_404(test_id)

    if request.method == 'POST':
        try:
            data = request.form
            test_status = data.get('test_status')
            result_notes = data.get('result_notes', '')

            # Update test status
            test.status = test_status
            test.completed_at = datetime.now()
            if result_notes:
                test.notes = result_notes if not test.notes else test.notes + "\n\n" + result_notes

            # Process parameters and results
            results = []

            # Check if test has parameters attribute
            has_parameters = hasattr(test, 'parameters') and test.parameters is not None

            # Handle existing parameters from test.parameters
            if has_parameters:
                for param_name, param_data in test.parameters.items():
                    param_id = param_data['id']
                    expected_value = param_data['expected']
                    actual_value = data.get(f'param_{param_id}')
                    is_passed = f'passed_{param_id}' in data

                    result = QCTestResult(
                        test_id=test_id,
                        parameter_name=param_name,
                        expected_value=expected_value,
                        actual_value=actual_value,
                        is_passed=is_passed
                    )
                    db.session.add(result)
                    results.append(result)
            else:
                # Handle dynamically added parameters
                param_count = 1
                parameters = {}

                while f'param_name_{param_count}' in data:
                    param_name = data.get(f'param_name_{param_count}')
                    expected_value = data.get(f'expected_{param_count}')
                    actual_value = data.get(f'param_{param_count}')
                    is_passed = f'passed_{param_count}' in data

                    if param_name and expected_value and actual_value:
                        # Store parameter in test record
                        parameters[param_name] = {
                            'expected': expected_value,
                            'id': param_count
                        }

                        # Create result record
                        result = QCTestResult(
                            test_id=test_id,
                            parameter_name=param_name,
                            expected_value=expected_value,
                            actual_value=actual_value,
                            is_passed=is_passed
                        )
                        db.session.add(result)
                        results.append(result)

                    param_count += 1

                # Save parameters to test record if the attribute exists
                if parameters and hasattr(test, 'parameters'):
                    test.parameters = parameters

            # Update batch status based on test result
            batch = test.batch
            if test_status == 'Passed':
                batch.status = 'QCPassed'
            elif test_status == 'Failed':
                batch.status = 'QCFailed'

            db.session.commit()

            flash('تم تسجيل نتائج الفحص بنجاح!', 'success')
            return redirect(url_for('production.qc_tests'))
        except Exception as e:
            db.session.rollback()
            flash(f'حدث خطأ أثناء تسجيل نتائج الفحص: {str(e)}', 'danger')
            current_app.logger.error(f"Error recording test results: {str(e)}")
            current_app.logger.error(f"Form data: {request.form}")

    # GET request - show form
    return render_template('production/record_test_results.html', test=test)


@production_bp.route('/qc/tests/<int:test_id>/approve', methods=['POST'])
@login_required
def approve_test(test_id):
    try:
        test = QCTest.query.get_or_404(test_id)
        batch = test.batch

        # Update batch status
        batch.status = 'QCPassed'
        test.status = 'Passed'
        test.completed_at = datetime.now()

        db.session.commit()
        flash('تم قبول دفعة الإنتاج بنجاح!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'حدث خطأ أثناء قبول الدفعة: {str(e)}', 'danger')

    return redirect(url_for('production.qc_tests'))


@production_bp.route('/qc/tests/<int:test_id>/reject', methods=['POST'])
@login_required
def reject_test(test_id):
    try:
        data = request.form
        reason = data.get('reason', 'لم يتم تحديد سبب')

        test = QCTest.query.get_or_404(test_id)
        batch = test.batch

        # Update batch status
        batch.status = 'QCFailed'
        test.status = 'Failed'
        test.completed_at = datetime.now()
        test.notes = reason

        # Return reserved materials to inventory if rejected
        order = ProductionOrder.query.get(batch.production_order_id)
        bom = BOM.query.filter_by(final_product_id=order.product_id).first()

        if bom:
            bom_details = BOMDetail.query.filter_by(bom_id=bom.id).all()
            for detail in bom_details:
                # Find the warehouse where materials were taken from
                transaction = InventoryTransaction.query.filter_by(
                    item_id=detail.component_item_id,
                    reference=f"Reserved for Production Order #{order.id}"
                ).first()

                if transaction:
                    warehouse_id = transaction.warehouse_id
                    required_qty = detail.quantity_required * batch.quantity

                    # Create transaction to return materials
                    return_transaction = InventoryTransaction(
                        item_id=detail.component_item_id,
                        warehouse_id=warehouse_id,
                        transaction_type='IN',
                        quantity=required_qty,
                        reference=f"Returned from rejected batch #{batch.id}"
                    )
                    db.session.add(return_transaction)

                    # Update inventory
                    inventory = Inventory.query.filter_by(
                        item_id=detail.component_item_id,
                        warehouse_id=warehouse_id
                    ).first()

                    if inventory:
                        inventory.quantity += required_qty

        db.session.commit()
        flash('تم رفض دفعة الإنتاج بنجاح!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'حدث خطأ أثناء رفض الدفعة: {str(e)}', 'danger')

    return redirect(url_for('production.qc_tests'))

@production_bp.route('/qc/report/<int:batch_id>', methods=['GET'])
@login_required
def generate_qc_report(batch_id):
    """Generate a quality control report for a specific batch"""
    try:
        batch = Batch.query.get_or_404(batch_id)
        tests = QCTest.query.filter_by(batch_id=batch_id).all()

        # Get test results for each test
        for test in tests:
            test.results = QCTestResult.query.filter_by(test_id=test.id).all()

        # Current date and time for the report
        now = datetime.now()

        return render_template(
            'production/qc_report.html',
            batch=batch,
            tests=tests,
            now=now
        )
    except Exception as e:
        flash(f'حدث خطأ أثناء إنشاء تقرير الفحص: {str(e)}', 'danger')
        return redirect(url_for('production.qc_tests'))

# Packaging Management
@production_bp.route('/packaging/orders', methods=['GET'])
@login_required
def packaging_orders():
    """View all packaging orders"""

    orders = PackagingOrder.query.order_by(PackagingOrder.created_at.desc()).all()
    warehouses = Warehouse.query.all()


    return render_template(
        'production/packaging_orders.html',
        orders=orders,
        warehouses=warehouses
    )


@production_bp.route('/packaging/create', methods=['GET', 'POST'])
@login_required
def create_packaging_order():
    """Create a new packaging order"""
    if request.method == 'POST':
        try:
            # Log the form data for debugging
            current_app.logger.info("Received form data for packaging order creation:")
            current_app.logger.info(request.form)

            data = request.form
            batch_id = int(data.get('batch_id'))
            packaging_type = data.get('packaging_type')
            quantity = int(data.get('quantity'))
            packaging_line_id = int(data.get('packaging_line_id')) if data.get('packaging_line_id') else None
            notes = data.get('notes', '')

            # Validate batch exists and is in QCPassed status
            batch = Batch.query.get_or_404(batch_id)
            current_app.logger.info(f"Found batch: {batch.id}, status: {batch.status}")

            if batch.status != 'QCPassed':
                flash('لا يمكن إنشاء أمر تعبئة لدفعة لم تجتز فحص الجودة', 'danger')
                return redirect(url_for('production.create_packaging_order'))

            # Create packaging order with all required fields
            current_app.logger.info("Creating new packaging order")
            new_order = PackagingOrder(
                batch_id=batch_id,
                packaging_type=packaging_type,
                quantity=quantity,
                packaging_line_id=packaging_line_id,
                status='Pending',
                created_by=current_user.id,
                scheduled_date=datetime.now()  # Add default scheduled date
            )

            # Store notes in a separate table or update the model to include notes

            current_app.logger.info(f"New order created with batch_id={batch_id}, packaging_type={packaging_type}, quantity={quantity}")
            db.session.add(new_order)

            # Update batch status
            batch.status = 'Packaging'

            # Commit to get the new order ID
            db.session.commit()
            current_app.logger.info(f"Packaging order saved successfully with ID: {new_order.id}")

            # Now find all packaging materials and add them automatically
            try:
                # Find all items with category type 'Packaging' or name containing 'تعبئة'
                packaging_materials = Item.query.join(
                    Category,
                    Item.category_id == Category.id
                ).filter(
                    db.or_(
                        Category.category_type == 'Packaging',
                        Category.name.like('%تعبئة%'),
                        Category.name.like('%packaging%')
                    )
                ).all()

                # Log all categories to debug
                all_categories = Category.query.all()
                current_app.logger.info(f"All categories: {[(c.id, c.name, getattr(c, 'category_type', 'Unknown')) for c in all_categories]}")

                # Log all items with their categories
                all_items = Item.query.all()
                current_app.logger.info(f"All items: {[(i.id, i.name, i.category_id) for i in all_items]}")

                current_app.logger.info(f"Found {len(packaging_materials)} packaging materials")
                if packaging_materials:
                    for material in packaging_materials:
                        current_app.logger.info(f"Packaging material found: {material.id} - {material.name} (Category: {material.category_id})")

                if packaging_materials:
                    # Default quantity for each material (can be adjusted based on business logic)
                    default_quantity = quantity  # Using the same quantity as the packaging order

                    # Find a warehouse with available inventory
                    for material in packaging_materials:
                        # Find inventory for this material
                        inventory_records = Inventory.query.filter_by(item_id=material.id).order_by(Inventory.quantity.desc()).all()

                        if not inventory_records:
                            current_app.logger.warning(f"No inventory found for packaging material: {material.name}")
                            continue

                        # Find a warehouse with enough inventory
                        warehouse_id = None
                        for inventory in inventory_records:
                            if inventory.quantity >= default_quantity:
                                warehouse_id = inventory.warehouse_id
                                break

                        if not warehouse_id:
                            current_app.logger.warning(f"Not enough inventory for packaging material: {material.name}")
                            continue

                        # Record material usage
                        try:
                            # Try to create with created_at field
                            usage = PackagingMaterialUsage(
                                packaging_order_id=new_order.id,
                                material_id=material.id,
                                quantity_used=default_quantity,
                                created_at=datetime.utcnow()
                            )
                        except Exception as e:
                            # Fallback if created_at field doesn't exist
                            usage = PackagingMaterialUsage(
                                packaging_order_id=new_order.id,
                                material_id=material.id,
                                quantity_used=default_quantity
                            )
                        db.session.add(usage)

                        # Update inventory
                        inventory = Inventory.query.filter_by(item_id=material.id, warehouse_id=warehouse_id).first()
                        inventory.quantity -= default_quantity

                        # Create transaction
                        transaction = InventoryTransaction(
                            item_id=material.id,
                            warehouse_id=warehouse_id,
                            transaction_type='OUT',
                            quantity=default_quantity,
                            reference=f"Used for Packaging Order #{new_order.id}"
                        )
                        db.session.add(transaction)

                    # Update order status to InProgress since materials are already assigned
                    new_order.status = 'InProgress'
                    db.session.commit()
                    current_app.logger.info(f"Automatically added packaging materials to order #{new_order.id}")

                    flash('تم إنشاء أمر التعبئة وإضافة مواد التغليف تلقائياً!', 'success')
                else:
                    flash('تم إنشاء أمر التعبئة بنجاح! لم يتم العثور على مواد تغليف لإضافتها تلقائياً.', 'success')
            except Exception as e:
                current_app.logger.error(f"Error adding packaging materials: {str(e)}")
                current_app.logger.exception("Exception details:")
                flash(f'تم إنشاء أمر التعبئة ولكن حدث خطأ أثناء إضافة مواد التغليف: {str(e)}', 'warning')

            return redirect(url_for('production.packaging_orders'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating packaging order: {str(e)}")
            current_app.logger.exception("Exception details:")
            flash(f'حدث خطأ أثناء إنشاء أمر التعبئة: {str(e)}', 'danger')
            return redirect(url_for('production.create_packaging_order'))

    # GET request - show form
    batches = Batch.query.filter_by(status='QCPassed').all()
    packaging_lines = PackagingLine.query.filter_by(is_active=True).all()

    # Check if batch_id is provided in query params (from QC report)
    batch_id = request.args.get('batch_id', type=int)
    selected_batch = None
    if batch_id:
        selected_batch = Batch.query.get(batch_id)

    return render_template(
        'production/create_packaging_order.html',
        batches=batches,
        packaging_lines=packaging_lines,
        selected_batch=selected_batch
    )


@production_bp.route('/packaging/check-materials', methods=['GET'])
@login_required
def check_packaging_materials():
    """Debug endpoint to check packaging materials"""
    # Find all items with category type 'Packaging' or name containing 'تعبئة'
    packaging_materials = Item.query.join(
        Category,
        Item.category_id == Category.id
    ).filter(
        db.or_(
            Category.category_type == 'Packaging',
            Category.name.like('%تعبئة%'),
            Category.name.like('%packaging%')
        )
    ).all()

    # Get all categories
    all_categories = Category.query.all()
    categories_info = [
        {
            'id': c.id,
            'name': c.name,
            'type': c.category_type if hasattr(c, 'category_type') else 'Unknown'
        }
        for c in all_categories
    ]

    # Get all items
    all_items = Item.query.all()
    items_info = [
        {
            'id': i.id,
            'name': i.name,
            'category_id': i.category_id,
            'category_name': Category.query.get(i.category_id).name if Category.query.get(i.category_id) else 'Unknown'
        }
        for i in all_items
    ]

    # Get packaging materials
    packaging_info = [
        {
            'id': p.id,
            'name': p.name,
            'category_id': p.category_id,
            'category_name': Category.query.get(p.category_id).name if Category.query.get(p.category_id) else 'Unknown'
        }
        for p in packaging_materials
    ]

    return render_template(
        'production/debug_packaging_materials.html',
        packaging_materials=packaging_info,
        all_categories=categories_info,
        all_items=items_info
    )

@production_bp.route('/packaging/orders/<int:order_id>/materials', methods=['GET', 'POST'])
@login_required
def record_packaging_materials(order_id):
    """Record materials used for packaging"""
    order = PackagingOrder.query.get_or_404(order_id)

    if request.method == 'POST':
        try:
            data = request.form
            material_ids = request.form.getlist('material_id')
            quantities = request.form.getlist('quantity')

            # Validate order status
            if order.status != 'Pending':
                flash('لا يمكن تسجيل مواد التعبئة لأمر ليس في حالة الانتظار', 'danger')
                return redirect(url_for('production.record_packaging_materials', order_id=order_id))

            # Record packaging materials
            for i in range(len(material_ids)):
                if not material_ids[i] or not quantities[i]:
                    continue

                material_id = int(material_ids[i])
                quantity = float(quantities[i])

                # Check if material exists in inventory
                inventory_items = Inventory.query.filter_by(item_id=material_id).all()
                if not inventory_items:
                    flash(f'المادة غير متوفرة في المخزون', 'danger')
                    return redirect(url_for('production.record_packaging_materials', order_id=order_id))

                # Find warehouse with sufficient quantity
                warehouse_id = None
                for inv in inventory_items:
                    if inv.quantity >= quantity:
                        warehouse_id = inv.warehouse_id
                        break

                if not warehouse_id:
                    material = Item.query.get(material_id)
                    flash(f'كمية غير كافية من {material.name} في المخزون', 'danger')
                    return redirect(url_for('production.record_packaging_materials', order_id=order_id))

                # Record material usage
                try:
                    # Try to create with created_at field
                    usage = PackagingMaterialUsage(
                        packaging_order_id=order_id,
                        material_id=material_id,
                        quantity_used=quantity,
                        created_at=datetime.utcnow()
                    )
                except Exception as e:
                    # Fallback if created_at field doesn't exist
                    usage = PackagingMaterialUsage(
                        packaging_order_id=order_id,
                        material_id=material_id,
                        quantity_used=quantity
                    )
                db.session.add(usage)

                # Update inventory
                inventory = Inventory.query.filter_by(item_id=material_id, warehouse_id=warehouse_id).first()
                inventory.quantity -= quantity

                # Create transaction
                transaction = InventoryTransaction(
                    item_id=material_id,
                    warehouse_id=warehouse_id,
                    transaction_type='OUT',
                    quantity=quantity,
                    reference=f"Used for Packaging Order #{order_id}"
                )
                db.session.add(transaction)

            # Update order status
            order.status = 'InProgress'

            db.session.commit()
            flash('تم تسجيل مواد التعبئة بنجاح!', 'success')
            return redirect(url_for('production.view_packaging_order', order_id=order_id))
        except Exception as e:
            db.session.rollback()
            flash(f'حدث خطأ أثناء تسجيل مواد التعبئة: {str(e)}', 'danger')

    # GET request - show form
    # Use category_type or name to find packaging materials
    packaging_materials = Item.query.join(
        Category,
        Item.category_id == Category.id
    ).filter(
        db.or_(
            Category.category_type == 'Packaging',
            Category.name.like('%تعبئة%'),
            Category.name.like('%packaging%')
        )
    ).all()

    # Log the number of packaging materials found
    current_app.logger.info(f"Found {len(packaging_materials)} packaging materials for manual selection")

    existing_materials = PackagingMaterialUsage.query.filter_by(packaging_order_id=order_id).all()

    return render_template(
        'production/record_packaging_materials.html',
        order=order,
        packaging_materials=packaging_materials,
        existing_materials=existing_materials
    )


@production_bp.route('/packaging/orders/<int:order_id>/complete', methods=['POST'])
@login_required
def complete_packaging(order_id):
    """Complete a packaging order and add products to inventory"""
    try:
        order = PackagingOrder.query.get_or_404(order_id)
        batch = order.batch

        # Validate order status
        if order.status != 'InProgress':
            flash('لا يمكن إكمال أمر تعبئة ليس في حالة التنفيذ', 'danger')
            return redirect(url_for('production.packaging_orders'))

        # Get form data
        warehouse_id = int(request.form.get('warehouse_id'))
        completion_notes = request.form.get('completion_notes', '')

        # Update order status
        order.status = 'Completed'
        order.completed_date = datetime.now()
        # Notes are not supported in the PackagingOrder model
        # if completion_notes:
        #     order.notes = completion_notes if not order.notes else order.notes + "\n\n" + completion_notes

        # Update batch status
        batch.status = 'Packaged'

        # Add finished product to inventory
        product = Item.query.get(batch.item_id)

        # Check if inventory record exists
        inventory = Inventory.query.filter_by(
            item_id=batch.item_id,
            warehouse_id=warehouse_id
        ).first()

        if inventory:
            inventory.quantity += batch.quantity
        else:
            # Create new inventory record
            inventory = Inventory(
                item_id=batch.item_id,
                warehouse_id=warehouse_id,
                quantity=batch.quantity
            )
            db.session.add(inventory)

        # Create transaction
        transaction = InventoryTransaction(
            item_id=batch.item_id,
            warehouse_id=warehouse_id,
            transaction_type='IN',
            quantity=batch.quantity,
            reference=f"Added from Packaging Order #{order_id}"
        )
        db.session.add(transaction)

        db.session.commit()
        flash('تم إكمال أمر التعبئة بنجاح وإضافة المنتج للمخزون!', 'success')
        return redirect(url_for('production.view_packaging_order', order_id=order_id))
    except Exception as e:
        db.session.rollback()
        flash(f'حدث خطأ أثناء إكمال أمر التعبئة: {str(e)}', 'danger')
        return redirect(url_for('production.view_packaging_order', order_id=order_id))

@production_bp.route('/packaging/orders/<int:order_id>/cancel', methods=['POST'])
@login_required
def cancel_packaging_order(order_id):
    """Cancel a packaging order"""
    try:
        order = PackagingOrder.query.get_or_404(order_id)

        # Validate order status
        if order.status not in ['Pending', 'InProgress']:
            flash('لا يمكن إلغاء أمر تعبئة مكتمل', 'danger')
            return redirect(url_for('production.packaging_orders'))

        cancel_reason = request.form.get('cancel_reason', '')

        # If materials were already used, return them to inventory
        if order.status == 'InProgress':
            material_usages = PackagingMaterialUsage.query.filter_by(packaging_order_id=order_id).all()

            for usage in material_usages:
                # Find the last transaction for this material
                transaction = InventoryTransaction.query.filter_by(
                    item_id=usage.material_id,
                    reference=f"Used for Packaging Order #{order_id}"
                ).order_by(InventoryTransaction.created_at.desc()).first()

                if transaction:
                    warehouse_id = transaction.warehouse_id

                    # Create transaction to return materials
                    return_transaction = InventoryTransaction(
                        item_id=usage.material_id,
                        warehouse_id=warehouse_id,
                        transaction_type='IN',
                        quantity=usage.quantity_used,
                        reference=f"Returned from cancelled Packaging Order #{order_id}"
                    )
                    db.session.add(return_transaction)

                    # Update inventory
                    inventory = Inventory.query.filter_by(
                        item_id=usage.material_id,
                        warehouse_id=warehouse_id
                    ).first()

                    if inventory:
                        inventory.quantity += usage.quantity_used

        # Update order status
        order.status = 'Cancelled'
        # Notes are not supported in the PackagingOrder model
        # if cancel_reason:
        #     order.notes = cancel_reason if not order.notes else order.notes + "\n\n" + "سبب الإلغاء: " + cancel_reason

        # Update batch status back to QCPassed
        batch = order.batch
        batch.status = 'QCPassed'

        db.session.commit()
        flash('تم إلغاء أمر التعبئة بنجاح!', 'success')
        return redirect(url_for('production.view_packaging_order', order_id=order_id))
    except Exception as e:
        db.session.rollback()
        flash(f'حدث خطأ أثناء إلغاء أمر التعبئة: {str(e)}', 'danger')
        return redirect(url_for('production.view_packaging_order', order_id=order_id))

@production_bp.route('/packaging/orders/<int:order_id>/view', methods=['GET'])
@login_required
def view_packaging_order(order_id):
    """View details of a packaging order"""
    try:
        order = PackagingOrder.query.get_or_404(order_id)
        material_usages = PackagingMaterialUsage.query.filter_by(packaging_order_id=order_id).all()

        # Get transactions related to this order
        material_transactions = InventoryTransaction.query.filter(
            InventoryTransaction.reference.like(f"%Packaging Order #{order_id}%")
        ).order_by(InventoryTransaction.created_at).all()

        # Get warehouses for the complete packaging modal
        warehouses = Warehouse.query.all()

        return render_template(
            'production/view_packaging_order.html',
            order=order,
            material_usages=material_usages,
            transactions=material_transactions,
            warehouses=warehouses
        )
    except Exception as e:
        flash(f'حدث خطأ أثناء عرض تفاصيل أمر التعبئة: {str(e)}', 'danger')
        return redirect(url_for('production.packaging_orders'))

@production_bp.route('/labels/generate/<int:batch_id>', methods=['GET', 'POST'])
@login_required
def generate_product_label(batch_id):
    batch = Batch.query.get_or_404(batch_id)

    if request.method == 'POST':
        try:
            data = request.form
            quantity = int(data.get('quantity'))

            # Generate label
            item = Item.query.get(batch.item_id)

            # Create a valid barcode value (alphanumeric only)
            barcode_value = f"{item.sku}-{batch.lot_number}-{datetime.now().strftime('%Y%m%d')}"
            # Remove any non-alphanumeric characters that might cause barcode generation to fail
            barcode_value = ''.join(c for c in barcode_value if c.isalnum() or c in '-_')

            label_data = {
                'product_name': item.name,
                'batch_number': batch.lot_number,
                'sku': item.sku,
                'production_date': batch.production_date.strftime('%Y-%m-%d'),
                'expiry_date': batch.expiry_date.strftime('%Y-%m-%d') if batch.expiry_date else 'N/A',
                'barcode': barcode_value
            }

            new_label = ProductLabel(
                batch_id=batch_id,
                label_template='standard',
                quantity=quantity,
                generated_by=current_user.id,
                label_data=label_data
            )
            db.session.add(new_label)
            db.session.commit()

            flash('Product label generated successfully!', 'success')
            return redirect(url_for('production.view_label', label_id=new_label.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error generating label: {str(e)}', 'danger')

    # GET request - show form
    return render_template('production/generate_label.html', batch=batch)

@production_bp.route('/labels/<int:label_id>', methods=['GET'])
@login_required
def view_label(label_id):
    label = ProductLabel.query.get_or_404(label_id)
    return render_template('production/view_label.html', label=label)

@production_bp.route('/labels/download/<int:label_id>', methods=['POST'])
@login_required
def download_label(label_id):
    """Download a label using wkhtmltoimage"""
    import subprocess
    import tempfile
    import os
    from flask import send_file, after_this_request

    label = ProductLabel.query.get_or_404(label_id)

    # Get form data
    format = request.form.get('format', 'pdf')
    quality = request.form.get('quality', 'high')
    filename = request.form.get('filename', f'label_{label.batch.lot_number}')

    # Create a temporary HTML file with the label content
    with tempfile.NamedTemporaryFile(suffix='.html', delete=False, mode='w', encoding='utf-8') as html_file:
        html_path = html_file.name

        # Write HTML content
        html_content = f"""
        <!DOCTYPE html>
        <html dir="rtl">
        <head>
            <meta charset="UTF-8">
            <title>Label {label.id}</title>
            <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css">
            <script src="https://cdn.jsdelivr.net/npm/jsbarcode@3.11.5/dist/JsBarcode.all.min.js"></script>
            <style>
                body {{
                    margin: 0;
                    padding: 20px;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    background-color: white;
                }}
                .label-container {{
                    border: 1px solid #e5e7eb;
                    border-radius: 0.5rem;
                    padding: 1.5rem;
                    background-color: white;
                    max-width: 400px;
                    box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
                }}
                .text-center {{ text-align: center; }}
                .mb-4 {{ margin-bottom: 1rem; }}
                .grid {{ display: grid; }}
                .grid-cols-2 {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
                .gap-3 {{ gap: 0.75rem; }}
                .text-sm {{ font-size: 0.875rem; }}
                .text-gray-600 {{ color: #4b5563; }}
                .font-medium {{ font-weight: 500; }}
                .text-xl {{ font-size: 1.25rem; }}
                .font-bold {{ font-weight: 700; }}
                .bg-blue-100 {{ background-color: #dbeafe; }}
                .p-2 {{ padding: 0.5rem; }}
                .rounded-lg {{ border-radius: 0.5rem; }}
                .text-blue-600 {{ color: #2563eb; }}
                .text-2xl {{ font-size: 1.5rem; }}
                .mt-2 {{ margin-top: 0.5rem; }}
                .bg-gray-50 {{ background-color: #f9fafb; }}
                .p-3 {{ padding: 0.75rem; }}
                .border {{ border-width: 1px; }}
                .border-gray-200 {{ border-color: #e5e7eb; }}
                .text-xs {{ font-size: 0.75rem; }}
            </style>
        </head>
        <body>
            <div class="label-container">
                <!-- Company Logo -->
                <div class="text-center mb-4">
                    <div class="inline-block bg-blue-100 p-2 rounded-lg">
                        <i class="fas fa-cheese text-blue-600 text-2xl"></i>
                    </div>
                    <h3 class="font-bold text-lg mt-2">منتجات قاتيلو</h3>
                </div>

                <!-- Product Name -->
                <div class="text-center mb-4">
                    <h2 class="text-xl font-bold">{label.label_data.get('product_name', '')}</h2>
                </div>

                <!-- Product Details -->
                <div class="grid grid-cols-2 gap-3 mb-4">
                    <div>
                        <p class="text-sm text-gray-600">رقم الدفعة:</p>
                        <p class="font-medium">{label.label_data.get('batch_number', '')}</p>
                    </div>
                    <div>
                        <p class="text-sm text-gray-600">الرمز:</p>
                        <p class="font-medium">{label.label_data.get('sku', '')}</p>
                    </div>
                    <div>
                        <p class="text-sm text-gray-600">تاريخ الإنتاج:</p>
                        <p class="font-medium">{label.label_data.get('production_date', '')}</p>
                    </div>
                    <div>
                        <p class="text-sm text-gray-600">تاريخ الانتهاء:</p>
                        <p class="font-medium">{label.label_data.get('expiry_date', '')}</p>
                    </div>
                </div>

                <!-- Barcode -->
                <div class="text-center p-3 bg-gray-50 rounded-lg border border-gray-200">
                    <svg id="barcode"></svg>
                    <p class="text-xs text-gray-600">{label.label_data.get('barcode', '')}</p>
                </div>
            </div>

            <script>
                document.addEventListener('DOMContentLoaded', function() {{
                    JsBarcode("#barcode", "{label.label_data.get('barcode', '')}", {{
                        format: "CODE128",
                        lineColor: "#000",
                        width: 2,
                        height: 50,
                        displayValue: false,
                        margin: 5
                    }});
                }});
            </script>
        </body>
        </html>
        """
        html_file.write(html_content)

    # Create a temporary output file
    output_ext = 'pdf' if format == 'pdf' else format
    with tempfile.NamedTemporaryFile(suffix=f'.{output_ext}', delete=False) as output_file:
        output_path = output_file.name

    try:
        # Path to wkhtmltoimage
        wkhtmltoimage_path = 'pdftool/wkhtmltopdf/bin/wkhtmltoimage.exe'

        # Set quality parameter
        quality_param = '100' if quality == 'high' else '75' if quality == 'medium' else '50'

        # Command arguments
        if format == 'pdf':
            # Use wkhtmltopdf for PDF
            wkhtmltopdf_path = 'pdftool/wkhtmltopdf/bin/wkhtmltopdf.exe'
            cmd = [
                wkhtmltopdf_path,
                '--enable-local-file-access',
                '--javascript-delay', '1000',  # Wait for JS to execute
                '--no-stop-slow-scripts',
                '--page-size', 'A6',
                '--margin-top', '5',
                '--margin-right', '5',
                '--margin-bottom', '5',
                '--margin-left', '5',
                html_path,
                output_path
            ]
        else:
            # Use wkhtmltoimage for images
            cmd = [
                wkhtmltoimage_path,
                '--enable-local-file-access',
                '--javascript-delay', '1000',  # Wait for JS to execute
                '--no-stop-slow-scripts',
                '--quality', quality_param,
                '--width', '400',
                '--format', format,
                html_path,
                output_path
            ]

        # Execute command
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()

        if process.returncode != 0:
            current_app.logger.error(f"Error generating label image: {stderr.decode()}")
            flash(f'Error generating label image: {stderr.decode()}', 'danger')
            return redirect(url_for('production.view_label', label_id=label_id))

        # Send the file to the user
        mimetype = 'application/pdf' if format == 'pdf' else f'image/{format}'

        @after_this_request
        def cleanup(response):
            try:
                os.remove(html_path)
                os.remove(output_path)
            except Exception as e:
                current_app.logger.error(f"Error cleaning up temporary files: {str(e)}")
            return response

        return send_file(
            output_path,
            mimetype=mimetype,
            as_attachment=True,
            download_name=f"{filename}.{output_ext}"
        )

    except Exception as e:
        current_app.logger.error(f"Error in download_label: {str(e)}")
        flash(f'Error downloading label: {str(e)}', 'danger')
        return redirect(url_for('production.view_label', label_id=label_id))

@production_bp.route('/labels/history/<int:batch_id>', methods=['GET'])
@login_required
def label_history(batch_id):
    """View history of labels generated for a batch"""
    batch = Batch.query.get_or_404(batch_id)
    labels = ProductLabel.query.filter_by(batch_id=batch_id).order_by(ProductLabel.generated_at.desc()).all()
    return render_template('production/label_history.html', batch=batch, labels=labels)

# Production Logs
@production_bp.route('/logs', methods=['GET'])
@login_required
def production_logs():
    # Create a table of all production-related activities
    logs = []

    # Production orders
    orders = ProductionOrder.query.order_by(desc(ProductionOrder.created_at)).all()
    for order in orders:
        logs.append({
            'timestamp': order.created_at,
            'action': 'Production Order Created',
            'details': f"Order #{order.id} for {order.product.name}, Qty: {order.quantity}",
            'user': order.creator.username if order.creator else 'System',
            'status': order.status
        })

    # Production steps
    step_records = ProductionStepRecord.query.order_by(desc(ProductionStepRecord.start_time)).all()
    for record in step_records:
        logs.append({
            'timestamp': record.start_time,
            'action': 'Production Step Started',
            'details': f"Batch #{record.batch_id}, Step: {record.step.name if record.step else 'Unknown'}",
            'user': record.operator.username if record.operator else 'System',
            'status': 'Completed' if record.end_time else 'In Progress'
        })
        if record.end_time:
            logs.append({
                'timestamp': record.end_time,
                'action': 'Production Step Completed',
                'details': f"Batch #{record.batch_id}, Step: {record.step.name if record.step else 'Unknown'}",
                'user': record.operator.username if record.operator else 'System',
                'status': 'Completed'
            })

    # QC tests
    tests = QCTest.query.order_by(desc(QCTest.created_at)).all()
    for test in tests:
        logs.append({
            'timestamp': test.created_at,
            'action': 'QC Test Created',
            'details': f"Batch #{test.batch_id}, Type: {test.test_type}",
            'user': test.inspector.username if test.inspector else 'System',
            'status': test.status
        })
        if test.completed_at:
            logs.append({
                'timestamp': test.completed_at,
                'action': 'QC Test Completed',
                'details': f"Batch #{test.batch_id}, Result: {test.status}",
                'user': test.inspector.username if test.inspector else 'System',
                'status': test.status
            })

    # Packaging orders
    packaging_orders = PackagingOrder.query.order_by(desc(PackagingOrder.created_at)).all()
    for order in packaging_orders:
        logs.append({
            'timestamp': order.created_at,
            'action': 'Packaging Order Created',
            'details': f"Order #{order.id} for Batch #{order.batch_id}",
            'user': order.creator.username if order.creator else 'System',
            'status': order.status
        })
        if order.completed_date:
            logs.append({
                'timestamp': order.completed_date,
                'action': 'Packaging Completed',
                'details': f"Order #{order.id} for Batch #{order.batch_id}",
                'user': order.creator.username if order.creator else 'System',
                'status': 'Completed'
            })

    # Product labels
    labels = ProductLabel.query.order_by(desc(ProductLabel.generated_at)).all()
    for label in labels:
        logs.append({
            'timestamp': label.generated_at,
            'action': 'Product Label Generated',
            'details': f"Batch #{label.batch_id}, Qty: {label.quantity}",
            'user': label.generator.username if label.generator else 'System',
            'status': 'Generated'
        })

    # Sort logs by timestamp (newest first)
    logs.sort(key=lambda x: x['timestamp'], reverse=True)

    # Extract unique users for the filter dropdown
    users_list = []
    for log in logs:
        if log['user'] and log['user'] not in users_list:
            users_list.append(log['user'])

    # Get current date/time for report generation
    now = datetime.now()

    return render_template('production/logs.html', logs=logs, users_list=users_list, now=now)

# Production Timeline
@production_bp.route('/timeline/<int:batch_id>', methods=['GET'])
@login_required
def production_timeline(batch_id):
    batch = Batch.query.get_or_404(batch_id)
    timeline_events = []

    # Creation event
    timeline_events.append({
        'timestamp': batch.production_date,
        'event': 'Batch Created',
        'details': f"Lot Number: {batch.lot_number}, Quantity: {batch.quantity}",
        'status': 'Created'
    })

    # Production steps
    step_records = ProductionStepRecord.query.filter_by(batch_id=batch_id).order_by(ProductionStepRecord.start_time).all()
    for record in step_records:
        timeline_events.append({
            'timestamp': record.start_time,
            'event': f"Step Started: {record.step.name if record.step else 'Unknown'}",
            'details': record.notes,
            'status': 'InProduction'
        })
        if record.end_time:
            timeline_events.append({
                'timestamp': record.end_time,
                'event': f"Step Completed: {record.step.name if record.step else 'Unknown'}",
                'details': record.notes,
                'status': 'InProduction'
            })

    # QC tests
    tests = QCTest.query.filter_by(batch_id=batch_id).order_by(QCTest.created_at).all()
    for test in tests:
        timeline_events.append({
            'timestamp': test.created_at,
            'event': f"QC Test Started: {test.test_type}",
            'details': f"Inspector: {test.inspector.username if test.inspector else 'Unknown'}",
            'status': 'QCPending'
        })
        if test.completed_at:
            timeline_events.append({
                'timestamp': test.completed_at,
                'event': f"QC Test Completed: {test.test_type}",
                'details': f"Result: {test.status}",
                'status': test.status
            })

    # Packaging
    packaging_orders = PackagingOrder.query.filter_by(batch_id=batch_id).order_by(PackagingOrder.created_at).all()
    for order in packaging_orders:
        timeline_events.append({
            'timestamp': order.created_at,
            'event': 'Packaging Started',
            'details': f"Type: {order.packaging_type}, Quantity: {order.quantity}",
            'status': 'Packaging'
        })
        if order.completed_date:
            timeline_events.append({
                'timestamp': order.completed_date,
                'event': 'Packaging Completed',
                'details': f"Added to inventory",
                'status': 'Packaged'
            })

    # Sort timeline events by timestamp
    timeline_events.sort(key=lambda x: x['timestamp'])

    return render_template('production/timeline.html', batch=batch, timeline_events=timeline_events)

# Production Steps Management
@production_bp.route('/steps', methods=['GET'])
@login_required
def manage_production_steps():
    steps = ProductionStep.query.order_by(ProductionStep.sequence_number).all()
    return render_template('production/manage_steps.html', steps=steps)

@production_bp.route('/steps/create', methods=['GET', 'POST'])
@login_required
def create_production_step():
    if request.method == 'POST':
        try:
            data = request.form
            name = data.get('name')
            description = data.get('description')
            standard_duration = int(data.get('standard_duration'))
            sequence_number = int(data.get('sequence_number'))

            # Create new step
            new_step = ProductionStep(
                name=name,
                description=description,
                standard_duration=standard_duration,
                sequence_number=sequence_number,
                is_active=True
            )
            db.session.add(new_step)
            db.session.commit()

            flash('Production step created successfully!', 'success')
            return redirect(url_for('production.manage_production_steps'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating production step: {str(e)}', 'danger')

    # GET request - show form
    return render_template('production/create_step.html')

@production_bp.route('/steps/<int:step_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_production_step(step_id):
    step = ProductionStep.query.get_or_404(step_id)

    if request.method == 'POST':
        try:
            data = request.form
            step.name = data.get('name')
            step.description = data.get('description')
            step.standard_duration = int(data.get('standard_duration'))
            step.sequence_number = int(data.get('sequence_number'))
            step.is_active = data.get('is_active') == 'on'

            db.session.commit()
            flash('Production step updated successfully!', 'success')
            return redirect(url_for('production.manage_production_steps'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating production step: {str(e)}', 'danger')

    # GET request - show form
    return render_template('production/edit_step.html', step=step)

@production_bp.route('/steps/<int:step_id>/delete', methods=['POST'])
@login_required
def delete_production_step(step_id):
    try:
        step = ProductionStep.query.get_or_404(step_id)

        # Check if step is used in any records
        records = ProductionStepRecord.query.filter_by(step_id=step_id).first()
        if records:
            # Don't delete, just mark as inactive
            step.is_active = False
            db.session.commit()
            flash('Production step marked as inactive (cannot be deleted because it is used in records).', 'warning')
        else:
            # Safe to delete
            db.session.delete(step)
            db.session.commit()
            flash('Production step deleted successfully!', 'success')

        return redirect(url_for('production.manage_production_steps'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting production step: {str(e)}', 'danger')
        return redirect(url_for('production.manage_production_steps'))

# Production Dashboard
@production_bp.route('/dashboard', methods=['GET'])
@login_required
def production_dashboard():
    # Get production statistics
    total_orders = ProductionOrder.query.count()
    active_orders = ProductionOrder.query.filter_by(status='InProgress').count()
    planned_orders = ProductionOrder.query.filter_by(status='Planned').count()
    completed_orders = ProductionOrder.query.filter_by(status='Completed').count()

    # Get recent production orders
    recent_orders = ProductionOrder.query.order_by(desc(ProductionOrder.created_at)).limit(5).all()

    # Get active production lines
    active_lines = ProductionLine.query.filter_by(is_active=True).all()

    # Get production line utilization
    line_utilization = []
    for line in active_lines:
        active_order = ProductionOrder.query.filter_by(
            production_line_id=line.id,
            status='InProgress'
        ).first()

        line_utilization.append({
            'line': line,
            'active_order': active_order,
            'status': 'active' if active_order else 'idle'
        })

    # Get QC statistics
    pending_qc = Batch.query.filter_by(status='QCPending').count()
    passed_qc = Batch.query.filter_by(status='QCPassed').count()
    failed_qc = Batch.query.filter_by(status='QCFailed').count()

    return render_template('production/dashboard.html',
                          total_orders=total_orders,
                          active_orders=active_orders,
                          planned_orders=planned_orders,
                          completed_orders=completed_orders,
                          recent_orders=recent_orders,
                          active_lines=active_lines,
                          line_utilization=line_utilization,
                          pending_qc=pending_qc,
                          passed_qc=passed_qc,
                          failed_qc=failed_qc)


# API Endpoints for AJAX requests
@production_bp.route('/api/batches/<int:batch_id>/status', methods=['GET'])
@login_required
def get_batch_status(batch_id):
    batch = Batch.query.get_or_404(batch_id)
    return jsonify({
        'status': batch.status,
        'lot_number': batch.lot_number,
        'quantity': batch.quantity
    })

@production_bp.route('/api/orders/<int:order_id>/status', methods=['GET'])
@login_required
def get_order_status(order_id):
    order = ProductionOrder.query.get_or_404(order_id)
    return jsonify({
        'status': order.status,
        'product': order.product.name,
        'quantity': order.quantity,
        'scheduled_start': order.scheduled_start.isoformat() if order.scheduled_start else None,
        'scheduled_end': order.scheduled_end.isoformat() if order.scheduled_end else None,
        'actual_start': order.actual_start.isoformat() if order.actual_start else None,
        'actual_end': order.actual_end.isoformat() if order.actual_end else None
    })

@production_bp.route('/api/lines/<int:line_id>/current_orders', methods=['GET'])
@login_required
def get_line_orders(line_id):
    orders = ProductionOrder.query.filter_by(
        production_line_id=line_id,
        status='InProgress'
    ).all()

    return jsonify({
        'orders': [{
            'id': order.id,
            'product': order.product.name,
            'quantity': order.quantity,
            'status': order.status
        } for order in orders]
    })



@production_bp.route('/orders/start', methods=['POST'])
@login_required
def start_production_order():
    try:
        data = request.form
        order_id = int(data.get('order_id'))

        order = ProductionOrder.query.get_or_404(order_id)

        # Check if production line is assigned
        if not order.production_line_id:
            flash('لا يمكن بدء الإنتاج: لم يتم تعيين خط إنتاج.', 'danger')
            return redirect(url_for('production.production_orders'))

        # Check if BOM exists for the product
        bom = BOM.query.filter_by(final_product_id=order.product_id).first()
        if not bom:
            flash('لا يمكن بدء الإنتاج: لا توجد قائمة مواد (BOM) لهذا المنتج. يرجى إنشاء قائمة مواد أولاً.', 'danger')
            return redirect(url_for('production.view_order', order_id=order_id))

        # Check if BOM has components
        bom_details = BOMDetail.query.filter_by(bom_id=bom.id).all()
        if not bom_details:
            flash('لا يمكن بدء الإنتاج: قائمة المواد لهذا المنتج لا تحتوي على مكونات. يرجى إضافة مكونات إلى قائمة المواد أولاً.', 'danger')
            return redirect(url_for('production.view_order', order_id=order_id))

        # Update order status
        order.status = 'InProgress'
        order.actual_start = datetime.now()

        # Update batch status if any
        batches = Batch.query.filter_by(production_order_id=order_id).all()
        for batch in batches:
            if batch.status == 'Created':
                batch.status = 'InProduction'

        db.session.commit()
        flash('تم بدء الإنتاج بنجاح!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'خطأ في بدء الإنتاج: {str(e)}', 'danger')

    return redirect(url_for('production.production_orders'))

@production_bp.route('/orders/cancel', methods=['POST'])
@login_required
def cancel_production():
    try:
        data = request.form
        order_id = int(data.get('order_id'))
        cancel_reason = data.get('cancel_reason', '')

        order = ProductionOrder.query.get_or_404(order_id)

        # Can only cancel orders in 'Planned' status
        if order.status != 'Planned':
            flash('Only planned orders can be cancelled.', 'danger')
            return redirect(url_for('production.production_orders'))

        # Update order status
        order.status = 'Cancelled'

        # Return reserved materials to inventory
        bom = BOM.query.filter_by(final_product_id=order.product_id).first()
        if bom:
            bom_details = BOMDetail.query.filter_by(bom_id=bom.id).all()
            for detail in bom_details:
                # Find the warehouse where materials were taken from
                transaction = InventoryTransaction.query.filter_by(
                    item_id=detail.component_item_id,
                    reference=f"Reserved for Production Order #{order.id}"
                ).first()

                if transaction:
                    warehouse_id = transaction.warehouse_id
                    required_qty = detail.quantity_required * order.quantity

                    # Create transaction to return materials
                    return_transaction = InventoryTransaction(
                        item_id=detail.component_item_id,
                        warehouse_id=warehouse_id,
                        transaction_type='IN',
                        quantity=required_qty,
                        reference=f"Returned from cancelled order #{order.id}"
                    )
                    db.session.add(return_transaction)

                    # Update inventory
                    inventory = Inventory.query.filter_by(
                        item_id=detail.component_item_id,
                        warehouse_id=warehouse_id
                    ).first()

                    if inventory:
                        inventory.quantity += required_qty

        # Update batches
        batches = Batch.query.filter_by(production_order_id=order_id).all()
        for batch in batches:
            batch.status = 'Cancelled'

        # Save cancellation reason
        order.notes = cancel_reason

        db.session.commit()
        flash('Production order cancelled successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error cancelling production order: {str(e)}', 'danger')

    return redirect(url_for('production.production_orders'))


@production_bp.route('/api/bom/check/<int:product_id>', methods=['GET'])
@login_required
def check_bom(product_id):
    """API endpoint to check if a BOM exists for a product"""
    try:
        # Check if BOM exists for the product
        bom = BOM.query.filter_by(final_product_id=product_id).first()

        if bom:
            # If BOM exists, also check if it has details
            details = BOMDetail.query.filter_by(bom_id=bom.id).all()
            has_details = len(details) > 0

            return jsonify({
                'exists': True,
                'has_details': has_details,
                'bom_id': bom.id
            })
        else:
            # Get product information for quick BOM creation
            product = Item.query.get(product_id)
            if not product:
                return jsonify({
                    'exists': False,
                    'error': 'Product not found'
                }), 404

            # Get product category
            category = Category.query.get(product.category_id) if product.category_id else None
            category_type = category.category_type if category and hasattr(category, 'category_type') else None

            return jsonify({
                'exists': False,
                'product': {
                    'id': product.id,
                    'name': product.name,
                    'sku': product.sku,
                    'category_id': product.category_id,
                    'category_name': category.name if category else 'Uncategorized',
                    'category_type': category_type
                }
            })
    except Exception as e:
        current_app.logger.error(f"Error checking BOM: {str(e)}")
        return jsonify({
            'exists': False,
            'error': str(e)
        }), 500

@production_bp.route('/api/bom/components-by-type', methods=['GET'])
@login_required
def get_components_by_type():
    """API endpoint to get components grouped by category type"""
    try:
        # Get all items that can be used as components
        items = Item.query.join(Category).all()

        # Group items by category type
        components_by_type = {}

        for item in items:
            category_type = item.category.category_type if item.category and hasattr(item.category, 'category_type') else 'Other'

            if category_type not in components_by_type:
                components_by_type[category_type] = []

            components_by_type[category_type].append({
                'id': item.id,
                'name': item.name,
                'sku': item.sku,
                'unit_of_measure': item.unit_of_measure
            })

        # Convert to list format for response
        result = []
        for category_type, items in components_by_type.items():
            result.append({
                'category_type': category_type,
                'items': items
            })

        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error getting components by type: {str(e)}")
        return jsonify({
            'error': str(e)
        }), 500

@production_bp.route('/api/products/<int:product_id>', methods=['GET'])
@login_required
def get_product_details(product_id):
    """API endpoint to get product details"""
    try:
        product = Item.query.get_or_404(product_id)
        category = Category.query.get(product.category_id) if product.category_id else None

        return jsonify({
            'id': product.id,
            'name': product.name,
            'sku': product.sku,
            'category_id': product.category_id,
            'category_name': category.name if category else 'Uncategorized',
            'category_type': category.category_type if category and hasattr(category, 'category_type') else None,
            'unit_of_measure': product.unit_of_measure
        })
    except Exception as e:
        current_app.logger.error(f"Error getting product details: {str(e)}")
        return jsonify({
            'error': str(e)
        }), 500

@production_bp.route('/api/bom', methods=['POST'])
@login_required
def create_bom():
    """API endpoint to create a new BOM"""
    try:
        data = request.json
        final_product_id = data.get('final_product_id')
        description = data.get('description', '')

        if not final_product_id:
            return jsonify({
                'success': False,
                'message': 'Final product ID is required'
            }), 400

        # Check if BOM already exists
        existing_bom = BOM.query.filter_by(final_product_id=final_product_id).first()
        if existing_bom:
            return jsonify({
                'success': False,
                'message': 'BOM already exists for this product',
                'id': existing_bom.id
            }), 400

        # Create new BOM
        new_bom = BOM(
            final_product_id=final_product_id,
            description=description,
            created_by=current_user.id
        )
        db.session.add(new_bom)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'BOM created successfully',
            'id': new_bom.id
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating BOM: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error creating BOM: {str(e)}'
        }), 500

@production_bp.route('/api/bom/<int:bom_id>/details', methods=['POST'])
@login_required
def add_bom_detail(bom_id):
    """API endpoint to add a detail to a BOM"""
    try:
        bom = BOM.query.get_or_404(bom_id)
        data = request.json

        component_item_id = data.get('component_item_id')
        quantity_required = data.get('quantity_required')
        unit_of_measure = data.get('unit_of_measure')

        if not component_item_id or not quantity_required:
            return jsonify({
                'success': False,
                'message': 'Component item ID and quantity are required'
            }), 400

        # Create new BOM detail
        new_detail = BOMDetail(
            bom_id=bom_id,
            component_item_id=component_item_id,
            quantity_required=quantity_required,
            unit_of_measure=unit_of_measure
        )
        db.session.add(new_detail)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'BOM detail added successfully',
            'id': new_detail.id
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error adding BOM detail: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error adding BOM detail: {str(e)}'
        }), 500

@production_bp.route('/api/materials/check', methods=['GET'])
@login_required
def check_materials():
    """API endpoint to check if materials are available for production"""
    try:
        product_id = request.args.get('product_id', type=int)
        warehouse_id = request.args.get('warehouse_id', type=int)
        quantity = request.args.get('quantity', type=int, default=1)

        if not product_id or not warehouse_id:
            return jsonify({
                'available': False,
                'error': 'Missing required parameters'
            }), 400

        # Check if BOM exists for the product
        bom = BOM.query.filter_by(final_product_id=product_id).first()
        if not bom:
            return jsonify({
                'available': False,
                'error': 'No BOM found for this product'
            }), 404

        # Get BOM details
        bom_details = BOMDetail.query.filter_by(bom_id=bom.id).all()
        if not bom_details:
            return jsonify({
                'available': False,
                'error': 'BOM has no components'
            }), 404

        # Check material availability
        materials = []
        all_available = True

        for detail in bom_details:
            required_qty = detail.quantity_required * quantity

            # Get inventory for this component
            inventory = Inventory.query.filter_by(
                item_id=detail.component_item_id,
                warehouse_id=warehouse_id
            ).first()

            available_qty = inventory.quantity if inventory else 0

            # Get component item details
            component = Item.query.get(detail.component_item_id)

            materials.append({
                'id': component.id,
                'name': component.name,
                'required_qty': required_qty,
                'available_qty': available_qty,
                'unit': detail.unit_of_measure or component.unit_of_measure or 'وحدة',
                'is_available': available_qty >= required_qty
            })

            if available_qty < required_qty:
                all_available = False

        return jsonify({
            'available': all_available,
            'materials': materials
        })

    except Exception as e:
        current_app.logger.error(f"Error checking materials: {str(e)}")
        return jsonify({
            'available': False,
            'error': str(e)
        }), 500
# Production Steps Management API
@production_bp.route('/api/steps', methods=['GET'])
@login_required
def api_list_production_steps():
    """API endpoint to get all production steps"""
    try:
        steps = ProductionStep.query.order_by(ProductionStep.sequence_number).all()

        steps_data = [{
            'id': step.id,
            'name': step.name,
            'description': step.description,
            'standard_duration': step.standard_duration,
            'sequence_number': step.sequence_number,
            'is_active': step.is_active
        } for step in steps]

        return jsonify({
            'success': True,
            'steps': steps_data
        })
    except Exception as e:
        current_app.logger.error(f"Error listing production steps: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@production_bp.route('/api/steps/create', methods=['POST'])
@login_required
def api_create_step():
    """API endpoint to create a new production step"""
    try:
        data = request.form
        name = data.get('name')
        description = data.get('description', '')
        standard_duration = int(data.get('standard_duration')) if data.get('standard_duration') else None
        sequence_number = int(data.get('sequence_number'))
        is_active = 'is_active' in data

        # Validate required fields
        if not name:
            return jsonify({
                'success': False,
                'message': 'اسم المرحلة مطلوب'
            }), 400

        # Create new step
        new_step = ProductionStep(
            name=name,
            description=description,
            standard_duration=standard_duration,
            sequence_number=sequence_number,
            is_active=is_active
        )

        db.session.add(new_step)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'تم إضافة المرحلة بنجاح',
            'step_id': new_step.id
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating production step: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'حدث خطأ أثناء إضافة المرحلة: {str(e)}'
        }), 500

@production_bp.route('/api/steps/update/<int:step_id>', methods=['POST'])
@login_required
def api_update_step(step_id):
    """API endpoint to update an existing production step"""
    try:
        step = ProductionStep.query.get_or_404(step_id)

        data = request.form
        name = data.get('name')
        description = data.get('description', '')
        standard_duration = int(data.get('standard_duration')) if data.get('standard_duration') else None
        sequence_number = int(data.get('sequence_number'))
        is_active = 'is_active' in data

        # Validate required fields
        if not name:
            return jsonify({
                'success': False,
                'message': 'اسم المرحلة مطلوب'
            }), 400

        # Update step
        step.name = name
        step.description = description
        step.standard_duration = standard_duration
        step.sequence_number = sequence_number
        step.is_active = is_active

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'تم تحديث المرحلة بنجاح'
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating production step: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'حدث خطأ أثناء تحديث المرحلة: {str(e)}'
        }), 500

@production_bp.route('/api/steps/delete/<int:step_id>', methods=['POST'])
@login_required
def api_delete_step(step_id):
    """API endpoint to delete a production step"""
    try:
        step = ProductionStep.query.get_or_404(step_id)

        # Check if step is used in any records
        records = ProductionStepRecord.query.filter_by(step_id=step_id).first()
        if records:
            # Don't delete, just mark as inactive
            step.is_active = False
            db.session.commit()
            return jsonify({
                'success': True,
                'message': 'تم تعطيل المرحلة (لا يمكن حذفها لأنها مستخدمة في سجلات الإنتاج)'
            })
        else:
            # Safe to delete
            db.session.delete(step)
            db.session.commit()
            return jsonify({
                'success': True,
                'message': 'تم حذف المرحلة بنجاح'
            })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting production step: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'حدث خطأ أثناء حذف المرحلة: {str(e)}'
        }), 500

# Route for saving a production step (create or update)
@production_bp.route('/api/steps/save', methods=['POST'])
@login_required
def api_save_production_step():
    """Route to save a production step (create or update)"""
    try:
        data = request.form
        step_id = data.get('step_id')

        if step_id:
            # Update existing step
            return api_update_step(int(step_id))
        else:
            # Create new step
            return api_create_step()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error saving production step: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'حدث خطأ أثناء حفظ المرحلة: {str(e)}'
        }), 500

# Add these imports at the top of the file
import os
from flask import send_file
from utils.pdf_generator import PDFGenerator

# Add this new route for generating PDF reports
@production_bp.route('/qc/report/<int:batch_id>/pdf', methods=['GET'])
@login_required
def generate_qc_report_pdf(batch_id):
    """Generate a PDF quality control report for a specific batch"""
    try:
        batch = Batch.query.get_or_404(batch_id)
        tests = QCTest.query.filter_by(batch_id=batch_id).all()

        # Get test results for each test
        for test in tests:
            test.results = QCTestResult.query.filter_by(test_id=test.id).all()

        # Current date and time for the report
        now = datetime.now()

        # Context for the PDF template
        context = {
            'batch': batch,
            'tests': tests,
            'now': now,
            'report_title': f'تقرير فحص الجودة للدفعة {batch.lot_number}'
        }

        # Generate the PDF
        pdf_filename = f"qc_report_{batch.lot_number}_{now.strftime('%Y%m%d_%H%M%S')}.pdf"

        current_app.logger.info(f"Generating PDF report for batch {batch_id}")

        try:
            pdf_path = PDFGenerator.generate_report_pdf(
                template_path='pdf/qc_report_pdf.html',
                context=context,
                filename=pdf_filename
            )

            # Send the file to the client
            return send_file(
                pdf_path,
                as_attachment=True,
                download_name=pdf_filename,
                mimetype='application/pdf'
            )
        except Exception as pdf_error:
            current_app.logger.error(f"PDF generation error: {str(pdf_error)}")
            flash(f'حدث خطأ أثناء إنشاء ملف PDF: {str(pdf_error)}', 'danger')

            # Check if wkhtmltopdf is installed
            import subprocess
            try:
                wkhtmltopdf_path = PDFGenerator.get_wkhtmltopdf_path()
                subprocess.run([wkhtmltopdf_path, '--version'],
                              stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE,
                              check=True)
            except Exception as e:
                flash('تأكد من تثبيت wkhtmltopdf بشكل صحيح. استخدم الأمر: python scripts/setup_pdf_generator.py', 'warning')
                current_app.logger.error(f"wkhtmltopdf check failed: {str(e)}")

            return redirect(url_for('production.generate_qc_report', batch_id=batch_id))

    except Exception as e:
        flash(f'حدث خطأ أثناء إنشاء تقرير الفحص: {str(e)}', 'danger')
        current_app.logger.error(f"Error generating QC report: {str(e)}")
        return redirect(url_for('production.qc_tests'))

# Add this new route for generating Certificate of Analysis PDF
@production_bp.route('/qc/certificate/<int:batch_id>/pdf', methods=['GET'])
@login_required
def generate_coa_pdf(batch_id):
    """Generate a PDF Certificate of Analysis for a specific batch"""
    try:
        batch = Batch.query.get_or_404(batch_id)

        # Check if batch has passed QC
        if batch.status != 'QCPassed':
            flash('لا يمكن إصدار شهادة تحليل لدفعة لم تجتز فحص الجودة', 'warning')
            return redirect(url_for('production.generate_qc_report', batch_id=batch_id))

        tests = QCTest.query.filter_by(batch_id=batch_id).all()

        # Get test results for each test
        for test in tests:
            test.results = QCTestResult.query.filter_by(test_id=test.id).all()

        # Current date and time for the report
        now = datetime.now()

        # Context for the PDF template
        context = {
            'batch': batch,
            'tests': tests,
            'report_generated_at': now,
            'certificate_only': True,  # This flag will ensure only the certificate part is rendered
            'report_title': f'شهادة تحليل للدفعة {batch.lot_number}'
        }

        # Generate the PDF
        pdf_filename = f"certificate_of_analysis_{batch.lot_number}_{now.strftime('%Y%m%d_%H%M%S')}.pdf"

        try:
            pdf_path = PDFGenerator.generate_report_pdf(
                template_path='pdf/qc_report_pdf.html',
                context=context,
                filename=pdf_filename,
                options={
                    'page-size': 'A4',
                    'margin-top': '20mm',
                    'margin-right': '20mm',
                    'margin-bottom': '20mm',
                    'margin-left': '20mm'
                }
            )

            # Send the file to the client
            return send_file(
                pdf_path,
                as_attachment=True,
                download_name=pdf_filename,
                mimetype='application/pdf'
            )
        except Exception as pdf_error:
            current_app.logger.error(f"PDF generation error: {str(pdf_error)}")
            flash(f'حدث خطأ أثناء إنشاء شهادة التحليل PDF: {str(pdf_error)}', 'danger')

            # Check if wkhtmltopdf is installed
            import subprocess
            try:
                wkhtmltopdf_path = PDFGenerator.get_wkhtmltopdf_path()
                subprocess.run([wkhtmltopdf_path, '--version'],
                              stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE,
                              check=True)
            except Exception as e:
                flash('تأكد من تثبيت wkhtmltopdf بشكل صحيح. استخدم الأمر: python scripts/setup_pdf_generator.py', 'warning')
                current_app.logger.error(f"wkhtmltopdf check failed: {str(e)}")

            return redirect(url_for('production.generate_qc_report', batch_id=batch_id))

    except Exception as e:
        flash(f'حدث خطأ أثناء إنشاء شهادة التحليل PDF: {str(e)}', 'danger')
        current_app.logger.error(f"Error generating PDF Certificate of Analysis: {str(e)}")
        return redirect(url_for('production.generate_qc_report', batch_id=batch_id))


