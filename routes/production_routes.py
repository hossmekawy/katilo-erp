from flask import Blueprint, request, jsonify, render_template, send_file
from flask_login import login_required, current_user
from models import (
    AgingRecord, Inventory, ProductionProcess, User, WarehouseSection, WarehouseSlot, WorkerProductivity, db, Item, Category, Warehouse, BOM, BOMDetail, 
    Batch, BatchSlot, ProductionRun, ProductionRunDetail,
    InventoryTransaction
)
from datetime import datetime, timedelta
import json
import io
import csv

# Create blueprint
production_bp = Blueprint('production_bp', __name__)

@production_bp.route('/production-management')
@login_required
def production_page():
    return render_template('production_management.html')

@production_bp.route('/production-scheduling')
@login_required
def production_scheduling_page():
    return render_template('production_scheduling.html')

@production_bp.route('/cheese-recipes')
@login_required
def cheese_recipes_page():
    return render_template('cheese_recipes.html')

@production_bp.route('/batch-tracking')
@login_required
def batch_tracking_page():
    return render_template('batch_tracking.html')

@production_bp.route('/production-reports')
@login_required
def production_reports_page():
    return render_template('production_reports.html')

@production_bp.route('/aging-monitoring')
@login_required
def aging_monitoring_page():
    return render_template('aging_monitoring.html')

@production_bp.route('/worker-productivity')
@login_required
def worker_productivity_page():
    return render_template('worker_productivity.html')

@production_bp.route('/production-processes')
@login_required
def production_processes_page():
    return render_template('production_processes.html')

# API Endpoints for Production Runs
@production_bp.route('/api/production-runs', methods=['GET'])
@login_required
def get_production_runs():
    production_runs = ProductionRun.query.all()
    return jsonify([{
        'id': run.id,
        'planned_start_date': run.planned_start_date.isoformat() if run.planned_start_date else None,
        'planned_end_date': run.planned_end_date.isoformat() if run.planned_end_date else None,
        'status': run.status,
        'responsible_user_id': run.responsible_user_id,
        'responsible_user': run.responsible_user.username if run.responsible_user else None
    } for run in production_runs])

@production_bp.route('/api/production-runs', methods=['POST'])
@login_required
def create_production_run():
    data = request.get_json()
    
    # Convert string dates to datetime objects
    planned_start = datetime.fromisoformat(data['planned_start_date']) if data.get('planned_start_date') else None
    planned_end = datetime.fromisoformat(data['planned_end_date']) if data.get('planned_end_date') else None
    
    production_run = ProductionRun(
        planned_start_date=planned_start,
        planned_end_date=planned_end,
        status=data.get('status', 'Planned'),
        responsible_user_id=data.get('responsible_user_id', current_user.id)
    )
    
    db.session.add(production_run)
    db.session.commit()
    
    # Add production run details if provided
    if 'details' in data and isinstance(data['details'], list):
        for detail in data['details']:
            run_detail = ProductionRunDetail(
                production_run_id=production_run.id,
                item_id=detail['item_id'],
                quantity_planned=detail['quantity_planned'],
                bom_id=detail.get('bom_id')
            )
            db.session.add(run_detail)
        
        db.session.commit()
    
    return jsonify({
        'id': production_run.id,
        'status': production_run.status,
        'message': 'تم إنشاء دورة الإنتاج بنجاح'
    }), 201

@production_bp.route('/api/production-runs/<int:id>', methods=['PUT'])
@login_required
def update_production_run(id):
    production_run = ProductionRun.query.get_or_404(id)
    data = request.get_json()
    
    if 'planned_start_date' in data and data['planned_start_date']:
        production_run.planned_start_date = datetime.fromisoformat(data['planned_start_date'])
    
    if 'planned_end_date' in data and data['planned_end_date']:
        production_run.planned_end_date = datetime.fromisoformat(data['planned_end_date'])
    
    if 'status' in data:
        production_run.status = data['status']
    
    if 'responsible_user_id' in data:
        production_run.responsible_user_id = data['responsible_user_id']
    
    db.session.commit()
    
    return jsonify({
        'id': production_run.id,
        'status': production_run.status,
        'message': 'تم تحديث دورة الإنتاج بنجاح'
    })

@production_bp.route('/api/production-runs/<int:id>/details', methods=['GET'])
@login_required
def get_production_run_details(id):
    details = ProductionRunDetail.query.filter_by(production_run_id=id).all()
    
    result = []
    for detail in details:
        item = Item.query.get(detail.item_id)
        bom = BOM.query.get(detail.bom_id) if detail.bom_id else None
        
        result.append({
            'id': detail.id,
            'production_run_id': detail.production_run_id,
            'item_id': detail.item_id,
            'item_name': item.name if item else None,
            'quantity_planned': detail.quantity_planned,
            'bom_id': detail.bom_id,
            'bom_name': f"وصفة {bom.final_product.name}" if bom and bom.final_product else None
        })
    
    return jsonify(result)

# Batch Management Endpoints
@production_bp.route('/api/batches', methods=['GET'])
@login_required
def get_batches():
    with_aging = request.args.get('with_aging', 'false').lower() == 'true'
    
    query = Batch.query
    
    # If with_aging is true, filter batches that have aging records
    if with_aging:
        # This assumes you have a relationship between Batch and AgingRecord
        query = query.join(AgingRecord, Batch.id == AgingRecord.batch_id).distinct()
    
    batches = query.all()
    
    result = []
    for batch in batches:
        item = Item.query.get(batch.item_id)
        
        result.append({
            'id': batch.id,
            'item_id': batch.item_id,
            'item_name': item.name if item else None,
            'lot_number': batch.lot_number,
            'production_date': batch.production_date.isoformat() if batch.production_date else None,
            'expiry_date': batch.expiry_date.isoformat() if batch.expiry_date else None,
            'quantity': batch.quantity
        })
    
    return jsonify(result)

@production_bp.route('/api/batches', methods=['POST'])
@login_required
def create_batch():
    data = request.get_json()
    
    # Validate required fields
    if not data.get('item_id') or not data.get('lot_number'):
        return jsonify({'message': 'رقم المنتج ورقم الدفعة مطلوبان'}), 400
    
    # Check if lot number already exists
    existing_batch = Batch.query.filter_by(lot_number=data['lot_number']).first()
    if existing_batch:
        return jsonify({'message': 'رقم الدفعة موجود بالفعل'}), 400
    
    # Convert string dates to datetime objects
    production_date = datetime.fromisoformat(data['production_date']) if data.get('production_date') else datetime.now()
    expiry_date = datetime.fromisoformat(data['expiry_date']) if data.get('expiry_date') else None
    
    batch = Batch(
        item_id=data['item_id'],
        lot_number=data['lot_number'],
        production_date=production_date,
        expiry_date=expiry_date,
        quantity=data.get('quantity', 0)
    )
    
    db.session.add(batch)
    
    # Create inventory transaction if quantity > 0
    if batch.quantity > 0 and data.get('warehouse_id'):
        transaction = InventoryTransaction(
            item_id=batch.item_id,
            warehouse_id=data['warehouse_id'],
            transaction_type='IN',
            quantity=batch.quantity,
            reference=f"Batch {batch.lot_number}"
        )
        db.session.add(transaction)
    
    db.session.commit()
    
    return jsonify({
        'id': batch.id,
        'lot_number': batch.lot_number,
        'message': 'تم إنشاء الدفعة بنجاح'
    }), 201

@production_bp.route('/api/batches/<int:id>', methods=['PUT'])
@login_required
def update_batch(id):
    batch = Batch.query.get_or_404(id)
    data = request.get_json()
    
    # Handle lot number change (check for uniqueness)
    if 'lot_number' in data and data['lot_number'] != batch.lot_number:
        existing_batch = Batch.query.filter_by(lot_number=data['lot_number']).first()
        if existing_batch and existing_batch.id != id:
            return jsonify({'message': 'رقم الدفعة موجود بالفعل'}), 400
        batch.lot_number = data['lot_number']
    
    # Update other fields
    if 'production_date' in data and data['production_date']:
        batch.production_date = datetime.fromisoformat(data['production_date'])
    
    if 'expiry_date' in data and data['expiry_date']:
        batch.expiry_date = datetime.fromisoformat(data['expiry_date'])
    
    # Handle quantity changes
    if 'quantity' in data and data['quantity'] != batch.quantity:
        old_quantity = batch.quantity
        new_quantity = data['quantity']
        quantity_diff = new_quantity - old_quantity
        
        # Create inventory transaction for the difference if warehouse_id provided
        if quantity_diff != 0 and data.get('warehouse_id'):
            transaction_type = 'IN' if quantity_diff > 0 else 'OUT'
            
            transaction = InventoryTransaction(
                item_id=batch.item_id,
                warehouse_id=data['warehouse_id'],
                transaction_type=transaction_type,
                quantity=abs(quantity_diff),
                reference=f"Batch {batch.lot_number} update"
            )
            db.session.add(transaction)
        
        batch.quantity = new_quantity
    
    db.session.commit()
    
    return jsonify({
        'id': batch.id,
        'lot_number': batch.lot_number,
        'message': 'تم تحديث الدفعة بنجاح'
    })

@production_bp.route('/api/batches/<int:id>/slots', methods=['GET'])
@login_required
def get_batch_slots(id):
    batch_slots = BatchSlot.query.filter_by(batch_id=id).all()
    
    result = []
    for slot in batch_slots:
        warehouse_slot = WarehouseSlot.query.get(slot.slot_id)
        
        # Get section and warehouse if warehouse_slot exists
        section = None
        warehouse = None
        if warehouse_slot:
            # Assuming section_id is a field in WarehouseSlot
            if hasattr(warehouse_slot, 'section_id'):
                section = WarehouseSection.query.get(warehouse_slot.section_id)
                
                if section and hasattr(section, 'warehouse_id'):
                    warehouse = Warehouse.query.get(section.warehouse_id)
        
        result.append({
            'id': slot.id,
            'batch_id': slot.batch_id,
            'slot_id': slot.slot_id,
            'quantity_in_slot': slot.quantity_in_slot,
            'warehouse_name': warehouse.name if warehouse else None,
            'section_name': section.section_name if section else None,
            'position': f"Row {warehouse_slot.row_number}, Col {warehouse_slot.column_number}" if warehouse_slot else None
        })
    
    return jsonify(result)

@production_bp.route('/api/batch-slots', methods=['POST'])
@login_required
def create_batch_slot():
    data = request.get_json()
    
    # Validate required fields
    if not data.get('batch_id') or 'quantity_in_slot' not in data:
        return jsonify({'message': 'رقم الدفعة والكمية مطلوبة'}), 400
    
    # Check if batch exists
    batch = Batch.query.get(data['batch_id'])
    if not batch:
        return jsonify({'message': 'الدفعة غير موجودة'}), 404
    
    # Handle slot creation if needed
    if data.get('create_new_slot') and data.get('section_id'):
        # Create a new slot in the specified section
        section = WarehouseSection.query.get(data['section_id'])
        if not section:
            return jsonify({'message': 'قسم المستودع غير موجود'}), 404
        
        # Find the next available position in the section
        existing_slots = WarehouseSlot.query.filter_by(section_id=section.id).all()
        
        # Determine next row/column
        max_row = 1
        max_col = 1
        
        if existing_slots:
            max_row = max(slot.row_number for slot in existing_slots)
            max_col = max(slot.column_number for slot in existing_slots if slot.row_number == max_row)
            
            # If the current row is full (based on section column_count), start a new row
            if max_col >= section.column_count:
                max_row += 1
                max_col = 1
            else:
                max_col += 1
        
        # Create the new slot
        new_slot = WarehouseSlot(
            section_id=section.id,
            row_number=max_row,
            column_number=max_col,
            item_id=batch.item_id,
            quantity=data['quantity_in_slot']
        )
        
        db.session.add(new_slot)
        db.session.commit()
        
        # Use the newly created slot
        data['slot_id'] = new_slot.id
            # If we still don't have a slot_id, return an error
    if not data.get('slot_id'):
        return jsonify({'message': 'موقع المستودع مطلوب'}), 400
    
    # Check if slot exists
    slot = WarehouseSlot.query.get(data['slot_id'])
    if not slot:
        return jsonify({'message': 'موقع المستودع غير موجود'}), 404
    
    # Check if batch-slot combination already exists
    existing = BatchSlot.query.filter_by(
        batch_id=data['batch_id'],
        slot_id=data['slot_id']
    ).first()
    
    if existing:
        return jsonify({'message': 'هذه الدفعة موجودة بالفعل في هذا الموقع'}), 400
    
    # Create new batch slot
    batch_slot = BatchSlot(
        batch_id=data['batch_id'],
        slot_id=data['slot_id'],
        quantity_in_slot=data['quantity_in_slot']
    )
    
    # Update the slot's item_id and quantity if not already set
    if not slot.item_id:
        slot.item_id = batch.item_id
    elif slot.item_id != batch.item_id:
        return jsonify({'message': 'هذا الموقع يحتوي على منتج مختلف'}), 400
    
    slot.quantity += data['quantity_in_slot']
    
    db.session.add(batch_slot)
    db.session.commit()
    
    return jsonify({
        'id': batch_slot.id,
        'message': 'تم تخزين الدفعة في الموقع بنجاح'
    }), 201


@production_bp.route('/api/production-processes', methods=['GET'])
@login_required
def get_production_processes():
    # Check if batch_id filter is provided
    batch_id = request.args.get('batch_id')
    
    # Apply filter if batch_id is provided
    if batch_id:
        processes = ProductionProcess.query.filter_by(batch_id=batch_id).all()
    else:
        processes = ProductionProcess.query.all()
    
    result = []
    for process in processes:
        batch = Batch.query.get(process.batch_id)
        item = Item.query.get(batch.item_id) if batch else None
        operator = User.query.get(process.operator_id)
        
        result.append({
            'id': process.id,
            'batch_id': process.batch_id,
            'item_id': batch.item_id if batch else None,
            'item_name': item.name if item else None,
            'process_type': process.process_type,
            'start_time': process.start_time.isoformat() if process.start_time else None,
            'end_time': process.end_time.isoformat() if process.end_time else None,
            'temperature': process.temperature,
            'humidity': process.humidity,
            'ph_level': process.ph_level,
            'notes': process.notes,
            'operator_id': process.operator_id,
            'operator_name': operator.username if operator else None,
            # Remove the timestamp field or replace with created_at if available
            'created_at': process.created_at.isoformat() if hasattr(process, 'created_at') and process.created_at else None
        })
    
    return jsonify(result)

@production_bp.route('/api/production-processes', methods=['POST'])
@login_required
def create_production_process():
    data = request.get_json()
    
    # Validate required fields
    if not data.get('batch_id') or not data.get('process_type') or not data.get('start_time'):
        return jsonify({'message': 'جميع الحقول المطلوبة يجب ملؤها'}), 400
    
    # Check if batch exists
    batch = Batch.query.get(data['batch_id'])
    if not batch:
        return jsonify({'message': 'الدفعة غير موجودة'}), 404
    
    # Convert string dates to datetime objects
    start_time = datetime.fromisoformat(data['start_time']) if data.get('start_time') else None
    end_time = datetime.fromisoformat(data['end_time']) if data.get('end_time') else None
    
    process = ProductionProcess(
        batch_id=data['batch_id'],
        process_type=data['process_type'],
        start_time=start_time,
        end_time=end_time,
        temperature=data.get('temperature'),
        humidity=data.get('humidity'),
        ph_level=data.get('ph_level'),
        notes=data.get('notes'),
        operator_id=data.get('operator_id', current_user.id)
    )
    
    db.session.add(process)
    db.session.commit()
    
    return jsonify({
        'id': process.id,
        'batch_id': process.batch_id,
        'process_type': process.process_type,
        'message': 'تم تسجيل مرحلة الإنتاج بنجاح'
    }), 201

@production_bp.route('/api/production-processes/<int:id>', methods=['PUT'])
@login_required
def update_production_process(id):
    process = ProductionProcess.query.get_or_404(id)
    data = request.get_json()
    
    # Update fields if provided
    if 'batch_id' in data:
        # Check if batch exists
        batch = Batch.query.get(data['batch_id'])
        if not batch:
            return jsonify({'message': 'الدفعة غير موجودة'}), 404
        process.batch_id = data['batch_id']
    
    if 'process_type' in data:
        process.process_type = data['process_type']
    
    if 'start_time' in data and data['start_time']:
        process.start_time = datetime.fromisoformat(data['start_time'])
    
    if 'end_time' in data:
        process.end_time = datetime.fromisoformat(data['end_time']) if data['end_time'] else None
    
    if 'temperature' in data:
        process.temperature = data['temperature']
    
    if 'humidity' in data:
        process.humidity = data['humidity']
    
    if 'ph_level' in data:
        process.ph_level = data['ph_level']
    
    if 'notes' in data:
        process.notes = data['notes']
    
    if 'operator_id' in data:
        process.operator_id = data['operator_id']
    
    db.session.commit()
    
    return jsonify({
        'id': process.id,
        'message': 'تم تحديث مرحلة الإنتاج بنجاح'
    })

@production_bp.route('/api/production-processes/<int:id>', methods=['DELETE'])
@login_required
def delete_production_process(id):
    process = ProductionProcess.query.get_or_404(id)
    db.session.delete(process)
    db.session.commit()
    
    return jsonify({
        'message': 'تم حذف مرحلة الإنتاج بنجاح'
    })

@production_bp.route('/api/aging-records', methods=['GET'])
@login_required
def get_aging_records():
    records = AgingRecord.query.all()
    
    result = []
    for record in records:
        batch = Batch.query.get(record.batch_id)
        item = Item.query.get(batch.item_id) if batch else None
        inspector = User.query.get(record.inspector_id)
        
        result.append({
            'id': record.id,
            'batch_id': record.batch_id,
            'item_id': batch.item_id if batch else None,
            'item_name': item.name if item else None,
            'aging_room': record.aging_room,
            'temperature': record.temperature,
            'humidity': record.humidity,
            'appearance': record.appearance,
            'texture': record.texture,
            'aroma': record.aroma,
            'notes': record.notes,
            'inspector_id': record.inspector_id,
            'inspector_name': inspector.username if inspector else None,
            'timestamp': record.timestamp.isoformat() if record.timestamp else None
        })
    
    return jsonify(result)

@production_bp.route('/api/aging-records', methods=['POST'])
@login_required
def create_aging_record():
    data = request.get_json()
    
    # Validate required fields
    if not data.get('batch_id') or not data.get('aging_room') or 'temperature' not in data or 'humidity' not in data:
        return jsonify({'message': 'جميع الحقول المطلوبة يجب ملؤها'}), 400
    
    # Check if batch exists
    batch = Batch.query.get(data['batch_id'])
    if not batch:
        return jsonify({'message': 'الدفعة غير موجودة'}), 404
    
    record = AgingRecord(
        batch_id=data['batch_id'],
        aging_room=data['aging_room'],
        temperature=data['temperature'],
        humidity=data['humidity'],
        appearance=data.get('appearance'),
        texture=data.get('texture'),
        aroma=data.get('aroma'),
        notes=data.get('notes'),
        inspector_id=data.get('inspector_id', current_user.id)
    )
    
    db.session.add(record)
    db.session.commit()
    
    return jsonify({
        'id': record.id,
        'batch_id': record.batch_id,
        'message': 'تم تسجيل مراقبة التعتيق بنجاح'
    }), 201

@production_bp.route('/api/aging-records/<int:id>', methods=['PUT'])
@login_required
def update_aging_record(id):
    record = AgingRecord.query.get_or_404(id)
    data = request.get_json()
    
    # Update fields if provided
    if 'batch_id' in data:
        # Check if batch exists
        batch = Batch.query.get(data['batch_id'])
        if not batch:
            return jsonify({'message': 'الدفعة غير موجودة'}), 404
        record.batch_id = data['batch_id']
    
    if 'aging_room' in data:
        record.aging_room = data['aging_room']
    
    if 'temperature' in data:
        record.temperature = data['temperature']
    
    if 'humidity' in data:
        record.humidity = data['humidity']
    
    if 'appearance' in data:
        record.appearance = data['appearance']
    
    if 'texture' in data:
        record.texture = data['texture']
    
    if 'aroma' in data:
        record.aroma = data['aroma']
    
    if 'notes' in data:
        record.notes = data['notes']
    
    if 'inspector_id' in data:
        record.inspector_id = data['inspector_id']
    
    db.session.commit()
    
    return jsonify({
        'id': record.id,
        'message': 'تم تحديث سجل مراقبة التعتيق بنجاح'
    })

@production_bp.route('/api/aging-records/<int:id>', methods=['DELETE'])
@login_required
def delete_aging_record(id):
    record = AgingRecord.query.get_or_404(id)
    db.session.delete(record)
    db.session.commit()
    
    return jsonify({
        'message': 'تم حذف سجل مراقبة التعتيق بنجاح'
    })

@production_bp.route('/api/worker-productivity', methods=['GET'])
@login_required
def get_worker_productivity():
    records = WorkerProductivity.query.all()
    
    result = []
    for record in records:
        user = User.query.get(record.user_id)
        
        result.append({
            'id': record.id,
            'user_id': record.user_id,
            'user_name': user.username if user else None,
            'production_run_id': record.production_run_id,
            'items_produced': record.items_produced,
            'errors_made': record.errors_made,
            'hours_worked': record.hours_worked,
            'efficiency_score': record.efficiency_score,
            'notes': record.notes,
            'recorded_by': record.recorded_by,
            'timestamp': record.timestamp.isoformat() if record.timestamp else None
        })
    
    return jsonify(result)

@production_bp.route('/api/worker-productivity', methods=['POST'])
@login_required
def create_worker_productivity():
    data = request.get_json()
    
    # Validate required fields
    if not data.get('user_id') or not data.get('production_run_id') or 'hours_worked' not in data:
        return jsonify({'message': 'جميع الحقول المطلوبة يجب ملؤها'}), 400
    
    # Convert string values to appropriate numeric types
    items_produced = float(data.get('items_produced', 0)) if data.get('items_produced') else 0
    hours_worked = float(data.get('hours_worked', 0)) if data.get('hours_worked') else 0
    errors_made = float(data.get('errors_made', 0)) if data.get('errors_made') else 0
    
    # Calculate efficiency score if possible
    efficiency_score = None
    if items_produced > 0 and hours_worked > 0:
        efficiency_score = items_produced / hours_worked
    
    record = WorkerProductivity(
        user_id=data['user_id'],
        production_run_id=data['production_run_id'],
        items_produced=items_produced,
        errors_made=errors_made,
        hours_worked=hours_worked,
        efficiency_score=efficiency_score,
        notes=data.get('notes'),
        recorded_by=current_user.id
    )
    
    db.session.add(record)
    db.session.commit()
    
    return jsonify({
        'id': record.id,
        'user_id': record.user_id,
        'production_run_id': record.production_run_id,
        'message': 'تم تسجيل إنتاجية العامل بنجاح'
    }), 201

@production_bp.route('/api/worker-productivity/<int:id>', methods=['PUT'])
@login_required
def update_worker_productivity(id):
    record = WorkerProductivity.query.get_or_404(id)
    data = request.get_json()
    
    # Update fields if provided
    if 'user_id' in data:
        record.user_id = data['user_id']
    
    if 'production_run_id' in data:
        record.production_run_id = data['production_run_id']
    
    if 'items_produced' in data:
        record.items_produced = data['items_produced']
    
    if 'errors_made' in data:
        record.errors_made = data['errors_made']
    
    if 'hours_worked' in data:
        record.hours_worked = data['hours_worked']
    
    if 'notes' in data:
        record.notes = data['notes']
    
    # Recalculate efficiency score
    if record.items_produced > 0 and record.hours_worked > 0:
        record.efficiency_score = record.items_produced / record.hours_worked
    else:
        record.efficiency_score = None
    
    db.session.commit()
    
    return jsonify({
        'id': record.id,
        'message': 'تم تحديث سجل إنتاجية العامل بنجاح'
    })

@production_bp.route('/api/worker-productivity/<int:id>', methods=['DELETE'])
@login_required
def delete_worker_productivity(id):
    record = WorkerProductivity.query.get_or_404(id)
    db.session.delete(record)
    db.session.commit()
    
    return jsonify({
        'message': 'تم حذف سجل إنتاجية العامل بنجاح'
    })

# BOM-related endpoints for cheese recipes
@production_bp.route('/api/cheese-recipes', methods=['GET'])
@login_required
def get_cheese_recipes():
    # Get all BOMs that are for cheese products
    # We could filter by category if we had a cheese category
    boms = BOM.query.all()
    
    result = []
    for bom in boms:
        final_product = Item.query.get(bom.final_product_id)
        
        if final_product:
            result.append({
                'id': bom.id,
                'final_product_id': bom.final_product_id,
                'product_name': final_product.name,
                'description': bom.description,
                'created_at': bom.created_at.isoformat() if bom.created_at else None,
                'updated_at': bom.updated_at.isoformat() if bom.updated_at else None
            })
    
    return jsonify(result)

@production_bp.route('/api/cheese-recipes/<int:id>/details', methods=['GET'])
@login_required
def get_cheese_recipe_details(id):
    # Get BOM details for a specific cheese recipe
    bom = BOM.query.get_or_404(id)
    details = BOMDetail.query.filter_by(bom_id=id).all()
    
    result = []
    for detail in details:
        component = Item.query.get(detail.component_item_id)
        
        if component:
            result.append({
                'id': detail.id,
                'component_item_id': detail.component_item_id,
                'component_name': component.name,
                'quantity_required': detail.quantity_required,
                'unit_of_measure': detail.unit_of_measure or component.unit_of_measure
            })
    
    return jsonify(result)

@production_bp.route('/api/boms', methods=['POST'])
@login_required
def create_bom():
    data = request.get_json()
    
    # Validate required fields
    if not data.get('final_product_id'):
        return jsonify({'message': 'المنتج النهائي مطلوب'}), 400
    
    # Check if final product exists
    final_product = Item.query.get(data['final_product_id'])
    if not final_product:
        return jsonify({'message': 'المنتج النهائي غير موجود'}), 404
    
    # Create BOM
    bom = BOM(
        final_product_id=data['final_product_id'],
        description=data.get('description'),
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    db.session.add(bom)
    db.session.commit()
    
    # Add BOM details if provided
    if 'components' in data and isinstance(data['components'], list):
        for component in data['components']:
            if not component.get('component_item_id') or 'quantity_required' not in component:
                continue  # Skip invalid components
                
            # Check if component item exists
            component_item = Item.query.get(component['component_item_id'])
            if not component_item:
                continue  # Skip non-existent components
                
            detail = BOMDetail(
                bom_id=bom.id,
                component_item_id=component['component_item_id'],
                quantity_required=component['quantity_required'],
                unit_of_measure=component.get('unit_of_measure')
            )
            
            db.session.add(detail)
        
        db.session.commit()
    
    return jsonify({
        'id': bom.id,
        'final_product_id': bom.final_product_id,
        'message': 'تم إنشاء وصفة الجبن بنجاح'
    }), 201

@production_bp.route('/api/boms/<int:id>', methods=['PUT'])
@login_required
def update_bom(id):
    bom = BOM.query.get_or_404(id)
    data = request.get_json()
    
    # Update BOM fields if provided
    if 'final_product_id' in data:
        # Check if final product exists
        final_product = Item.query.get(data['final_product_id'])
        if not final_product:
            return jsonify({'message': 'المنتج النهائي غير موجود'}), 404
        bom.final_product_id = data['final_product_id']
    
    if 'description' in data:
        bom.description = data['description']
    
    bom.updated_at = datetime.now()
    
    # Update BOM details if provided
    if 'components' in data and isinstance(data['components'], list):
        # Delete existing details
        BOMDetail.query.filter_by(bom_id=bom.id).delete()
        
        # Add new details
        for component in data['components']:
            if not component.get('component_item_id') or 'quantity_required' not in component:
                continue  # Skip invalid components
                
            # Check if component item exists
            component_item = Item.query.get(component['component_item_id'])
            if not component_item:
                continue  # Skip non-existent components
                
            detail = BOMDetail(
                bom_id=bom.id,
                component_item_id=component['component_item_id'],
                quantity_required=component['quantity_required'],
                unit_of_measure=component.get('unit_of_measure')
            )
            
            db.session.add(detail)
    
    db.session.commit()
    
    return jsonify({
        'id': bom.id,
        'message': 'تم تحديث وصفة الجبن بنجاح'
    })

@production_bp.route('/api/boms/<int:id>', methods=['DELETE'])
@login_required
def delete_bom(id):
    bom = BOM.query.get_or_404(id)
    
    # Delete BOM details first
    BOMDetail.query.filter_by(bom_id=bom.id).delete()
    
    # Delete BOM
    db.session.delete(bom)
    db.session.commit()
    
    return jsonify({
        'message': 'تم حذف وصفة الجبن بنجاح'
    })

# Production material consumption tracking
@production_bp.route('/api/material-consumption', methods=['POST'])
@login_required
def record_material_consumption():
    data = request.get_json()
    
    # Validate required fields
    if not data.get('production_run_id') or not data.get('item_id') or 'quantity_used' not in data:
        return jsonify({'message': 'جميع الحقول مطلوبة'}), 400
    
    # Check if production run exists
    production_run = ProductionRun.query.get(data['production_run_id'])
    if not production_run:
        return jsonify({'message': 'دورة الإنتاج غير موجودة'}), 404
    
    # Check if item exists
    item = Item.query.get(data['item_id'])
    if not item:
        return jsonify({'message': 'المنتج غير موجود'}), 404
    
    # Create inventory transaction for material consumption
    if data.get('warehouse_id'):
        transaction = InventoryTransaction(
            item_id=data['item_id'],
            warehouse_id=data['warehouse_id'],
            transaction_type='OUT',
            quantity=data['quantity_used'],
            reference=f"Production Run #{data['production_run_id']}"
        )
        db.session.add(transaction)
    
    # We could also create a specific MaterialConsumption model
    # For now, just commit the transaction
    db.session.commit()
    
    return jsonify({
        'production_run_id': data['production_run_id'],
        'item_id': data['item_id'],
        'quantity_used': data['quantity_used'],
        'message': 'تم تسجيل استهلاك المواد بنجاح'
    }), 201

# Start production run and consume materials based on BOM
@production_bp.route('/api/production-runs/<int:id>/start', methods=['POST'])
@login_required
def start_production_run(id):
    production_run = ProductionRun.query.get_or_404(id)
    
    # Check if production run is already in progress or completed
    if production_run.status != 'Planned':
        return jsonify({'message': 'لا يمكن بدء دورة إنتاج غير مخططة'}), 400
    
    data = request.get_json()
    warehouse_id = data.get('warehouse_id')
    
    if not warehouse_id:
        return jsonify({'message': 'معرف المستودع مطلوب'}), 400
    
    # Update production run status
    production_run.status = 'In Progress'
    
    # Get all production run details
    details = ProductionRunDetail.query.filter_by(production_run_id=id).all()
    
    consumed_materials = []
    errors = []
    
    for detail in details:
        # If this detail has a BOM, consume materials according to the BOM
        if detail.bom_id:
            bom = BOM.query.get(detail.bom_id)
            if bom:
                bom_details = BOMDetail.query.filter_by(bom_id=bom.id).all()
                
                for bom_detail in bom_details:
                    # Calculate quantity needed based on production quantity
                    quantity_needed = bom_detail.quantity_required * detail.quantity_planned
                    
                    # Check inventory
                    inventory = Inventory.query.filter_by(
                        item_id=bom_detail.component_item_id,
                        warehouse_id=warehouse_id
                    ).first()
                    
                    if not inventory or inventory.quantity < quantity_needed:
                        errors.append({
                            'item_id': bom_detail.component_item_id,
                            'item_name': Item.query.get(bom_detail.component_item_id).name if Item.query.get(bom_detail.component_item_id) else 'Unknown',
                            'quantity_needed': quantity_needed,
                            'quantity_available': inventory.quantity if inventory else 0
                        })
                        continue
                    
                    # Create transaction to consume material
                    transaction = InventoryTransaction(
                        item_id=bom_detail.component_item_id,
                        warehouse_id=warehouse_id,
                        transaction_type='OUT',
                        quantity=quantity_needed,
                        reference=f"Production Run #{id}"
                    )
                    db.session.add(transaction)
                    
                    # Update inventory
                    inventory.quantity -= quantity_needed
                    
                    consumed_materials.append({
                        'item_id': bom_detail.component_item_id,
                        'item_name': Item.query.get(bom_detail.component_item_id).name if Item.query.get(bom_detail.component_item_id) else 'Unknown',
                        'quantity_consumed': quantity_needed
                    })
    
    # If there are errors, rollback and return error
    if errors:
        db.session.rollback()
        return jsonify({
            'message': 'لا يمكن بدء الإنتاج بسبب نقص في المواد',
            'errors': errors
        }), 400
    
    # Commit changes
    db.session.commit()
    
    return jsonify({
        'id': production_run.id,
        'status': production_run.status,
        'consumed_materials': consumed_materials,
        'message': 'تم بدء دورة الإنتاج بنجاح واستهلاك المواد'
    })

# Complete production run and add produced items to inventory
@production_bp.route('/api/production-runs/<int:id>/complete', methods=['POST'])
@login_required
def complete_production_run(id):
    production_run = ProductionRun.query.get_or_404(id)
    
    # Check if production run is in progress
    if production_run.status != 'In Progress':
        return jsonify({'message': 'يمكن إكمال دورات الإنتاج قيد التنفيذ فقط'}), 400
    
    data = request.get_json()
    warehouse_id = data.get('warehouse_id')
    
    if not warehouse_id:
        return jsonify({'message': 'معرف المستودع مطلوب'}), 400
    
    # Update production run status
    production_run.status = 'Completed'
    
    # Get all production run details
    details = ProductionRunDetail.query.filter_by(production_run_id=id).all()
    
    produced_items = []
    
    for detail in details:
        # Create batch for produced item if requested
        if data.get('create_batches', True):
            # Generate lot number (you might want a more sophisticated system)
            lot_number = f"PR{id}-{detail.item_id}-{datetime.now().strftime('%Y%m%d%H%M')}"
            
            # Create batch
            batch = Batch(
                item_id=detail.item_id,
                lot_number=lot_number,
                production_date=datetime.now(),
                # Set expiry date based on item shelf life if available
                expiry_date=None,  # You would calculate this based on the item
                quantity=detail.quantity_planned
            )
            db.session.add(batch)
        
        # Add produced items to inventory
        inventory = Inventory.query.filter_by(
            item_id=detail.item_id,
            warehouse_id=warehouse_id
        ).first()
        
        if inventory:
            inventory.quantity += detail.quantity_planned
        else:
            inventory = Inventory(
                item_id=detail.item_id,
                warehouse_id=warehouse_id,
                quantity=detail.quantity_planned
            )
            db.session.add(inventory)
        
        # Create transaction for produced items
        transaction = InventoryTransaction(
            item_id=detail.item_id,
            warehouse_id=warehouse_id,
            transaction_type='IN',
            quantity=detail.quantity_planned,
            reference=f"Production Run #{id} Completion"
        )
        db.session.add(transaction)
        
        produced_items.append({
            'item_id': detail.item_id,
            'item_name': Item.query.get(detail.item_id).name if Item.query.get(detail.item_id) else 'Unknown',
            'quantity_produced': detail.quantity_planned
        })
    
    # Commit changes
    db.session.commit()
    
    return jsonify({
        'id': production_run.id,
        'status': production_run.status,
        'produced_items': produced_items,
        'message': 'تم إكمال دورة الإنتاج بنجاح وإضافة المنتجات إلى المخزون'
    })

# Add these new API endpoints to support the dashboard
@production_bp.route('/api/production-summary/today', methods=['GET'])
@login_required
def get_today_production_summary():
    """Get summary of today's production"""
    today = datetime.now().date()
    
    # Get all production runs completed today
    completed_runs = ProductionRun.query.filter(
        ProductionRun.status == 'Completed',
        db.func.date(ProductionRun.planned_end_date) == today
    ).all()
    
    # Calculate total quantity produced
    total_quantity = 0
    for run in completed_runs:
        details = ProductionRunDetail.query.filter_by(production_run_id=run.id).all()
        for detail in details:
            total_quantity += detail.quantity_planned
    
    return jsonify({
        'date': today.isoformat(),
        'completed_runs': len(completed_runs),
        'total_quantity': total_quantity
    })

@production_bp.route('/api/production-weekly-summary', methods=['GET'])
@login_required
def get_weekly_production_summary():
    """Get summary of production for the current week"""
    # Get the start and end of the current week
    today = datetime.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    
    # Initialize daily totals
    daily_totals = {(start_of_week + timedelta(days=i)).isoformat(): 0 for i in range(7)}
    
    # Get all production runs completed this week
    completed_runs = ProductionRun.query.filter(
        ProductionRun.status == 'Completed',
        db.func.date(ProductionRun.planned_end_date) >= start_of_week,
        db.func.date(ProductionRun.planned_end_date) <= end_of_week
    ).all()
    
    # Calculate daily production
    for run in completed_runs:
        if run.planned_end_date:
            day = run.planned_end_date.date().isoformat()
            if day in daily_totals:
                details = ProductionRunDetail.query.filter_by(production_run_id=run.id).all()
                for detail in details:
                    daily_totals[day] += detail.quantity_planned
    
    # Format for chart.js
    result = {
        'labels': list(daily_totals.keys()),
        'data': list(daily_totals.values())
    }
    
    return jsonify(result)

@production_bp.route('/api/cheese-types-distribution', methods=['GET'])
@login_required
def get_cheese_types_distribution():
    """Get distribution of cheese types produced"""
    # Get all production run details
    production_details = ProductionRunDetail.query.join(
        ProductionRun, ProductionRunDetail.production_run_id == ProductionRun.id
    ).filter(
        ProductionRun.status == 'Completed'
    ).all()
    
    # Group by item and sum quantities
    item_quantities = {}
    for detail in production_details:
        item = Item.query.get(detail.item_id)
        if item:
            if item.name not in item_quantities:
                item_quantities[item.name] = 0
            item_quantities[item.name] += detail.quantity_planned
    
    # Sort by quantity (descending) and take top 5
    sorted_items = sorted(item_quantities.items(), key=lambda x: x[1], reverse=True)[:5]
    
    # Format for chart.js
    result = {
        'labels': [item[0] for item in sorted_items],
        'data': [item[1] for item in sorted_items]
    }
    
    return jsonify(result)

# Report API endpoints
@production_bp.route('/api/reports/production', methods=['GET'])
@login_required
def get_production_report():
    """Generate production report data"""
    # Parse date range
    date_range = request.args.get('date_range', '')
    item_id = request.args.get('item_id')
    
    start_date, end_date = parse_date_range(date_range)
    
    # Query production runs within date range
    query = ProductionRun.query.filter(
        ProductionRun.planned_start_date >= start_date,
        ProductionRun.planned_start_date <= end_date
    )
    
    if item_id:
        # Join with production run details to filter by item
        query = query.join(
            ProductionRunDetail, 
            ProductionRunDetail.production_run_id == ProductionRun.id
        ).filter(ProductionRunDetail.item_id == item_id)
    
    production_runs = query.all()
    
    # Calculate summary data
    total_production = 0
    completed_runs = 0
    
    # Prepare chart data (group by date)
    chart_data = {}
    table_data = []
    
    for run in production_runs:
        # Get run details
        details = ProductionRunDetail.query.filter_by(production_run_id=run.id).all()
        
        # Skip if no details or filtered by item and no matching items
        if not details or (item_id and not any(d.item_id == int(item_id) for d in details)):
            continue
        
        # Format date for chart grouping
        date_key = run.planned_start_date.strftime('%Y-%m-%d') if run.planned_start_date else 'Unknown'
        
        if date_key not in chart_data:
            chart_data[date_key] = 0
        
        # Calculate total quantity for this run
        run_quantity = 0
        for detail in details:
            # If filtering by item, only count matching items
            if not item_id or detail.item_id == int(item_id):
                run_quantity += detail.quantity_planned
                
                # Add to table data
                item = Item.query.get(detail.item_id)
                table_data.append({
                    'date': date_key,
                    'run_id': run.id,
                    'item_name': item.name if item else 'Unknown',
                    'quantity': detail.quantity_planned,
                    'status': run.status,
                    'responsible_user': run.responsible_user.username if run.responsible_user else 'Unknown'
                })
        
        # Add to chart data
        chart_data[date_key] += run_quantity
        
        # Add to summary
        total_production += run_quantity
        if run.status == 'Completed':
            completed_runs += 1
    
    # Sort chart data by date
    sorted_dates = sorted(chart_data.keys())
    
    # Format response
    response = {
        'summary': {
            'total_production': total_production,
            'completed_runs': completed_runs,
            'avg_efficiency': None  # Not applicable for production report
        },
        'chart': {
            'labels': sorted_dates,
            'data': [chart_data[date] for date in sorted_dates]
        },
        'table': sorted(table_data, key=lambda x: x['date'], reverse=True)
    }
    
    return jsonify(response)

@production_bp.route('/api/reports/efficiency', methods=['GET'])
@login_required
def get_efficiency_report():
    """Generate efficiency report data"""
    # Parse date range
    date_range = request.args.get('date_range', '')
    item_id = request.args.get('item_id')
    
    start_date, end_date = parse_date_range(date_range)
    
    # Query completed production runs within date range
    query = ProductionRun.query.filter(
        ProductionRun.status == 'Completed',
        ProductionRun.planned_start_date >= start_date,
        ProductionRun.planned_start_date <= end_date
    )
    
    if item_id:
        # Join with production run details to filter by item
        query = query.join(
            ProductionRunDetail, 
            ProductionRunDetail.production_run_id == ProductionRun.id
        ).filter(ProductionRunDetail.item_id == item_id)
    
    production_runs = query.all()
    
    # Prepare chart and table data
    chart_data = {}
    table_data = []
    total_efficiency = 0
    run_count = 0
    
    for run in production_runs:
        # Get run details
        details = ProductionRunDetail.query.filter_by(production_run_id=run.id).all()
        
        # Skip if no details or filtered by item and no matching items
        if not details or (item_id and not any(d.item_id == int(item_id) for d in details)):
            continue
        
        # Format date for chart grouping
        date_key = run.planned_start_date.strftime('%Y-%m-%d') if run.planned_start_date else 'Unknown'
        
        # Calculate efficiency for this run
        # This is a simplified example - you might have a more complex efficiency calculation
        planned_quantity = sum(d.quantity_planned for d in details if not item_id or d.item_id == int(item_id))
        actual_quantity = planned_quantity  # In a real system, you'd have actual production data
        
        # Simulate some variance for demonstration
        import random
        efficiency_factor = random.uniform(0.85, 1.05)
        actual_quantity = int(planned_quantity * efficiency_factor)
        
        efficiency = int((actual_quantity / planned_quantity * 100) if planned_quantity > 0 else 0)
        
        # Add to chart data (average efficiency per day)
        if date_key not in chart_data:
            chart_data[date_key] = {'total': 0, 'count': 0}
        
        chart_data[date_key]['total'] += efficiency
        chart_data[date_key]['count'] += 1
        
        # Add to table data
        table_data.append({
            'date': date_key,
            'run_id': run.id,
            'planned_quantity': planned_quantity,
            'actual_quantity': actual_quantity,
            'efficiency': efficiency,
            'notes': 'تم الإنتاج بنجاح' if efficiency >= 95 else 'كفاءة منخفضة'
        })
        
        # Add to summary
        total_efficiency += efficiency
        run_count += 1
    
    # Calculate average efficiency
    avg_efficiency = int(total_efficiency / run_count) if run_count > 0 else 0
    
    # Calculate daily average efficiency for chart
    sorted_dates = sorted(chart_data.keys())
    daily_avg_efficiency = [
        int(chart_data[date]['total'] / chart_data[date]['count']) 
        for date in sorted_dates
    ]
    
    # Format response
    response = {
        'summary': {
            'total_production': sum(item['actual_quantity'] for item in table_data),
            'completed_runs': run_count,
            'avg_efficiency': avg_efficiency
        },
        'chart': {
            'labels': sorted_dates,
            'data': daily_avg_efficiency
        },
        'table': sorted(table_data, key=lambda x: x['date'], reverse=True)
    }
    
    return jsonify(response)

@production_bp.route('/api/reports/aging', methods=['GET'])
@login_required
def get_aging_report():
    """Generate aging monitoring report data"""
    # Parse date range
    date_range = request.args.get('date_range', '')
    item_id = request.args.get('item_id')
    
    start_date, end_date = parse_date_range(date_range)
    
    # Query aging records within date range
    query = AgingRecord.query.filter(
        AgingRecord.timestamp >= start_date,
        AgingRecord.timestamp <= end_date
    )
    
    if item_id:
        # Join with batch to filter by item
        query = query.join(
            Batch, 
            Batch.id == AgingRecord.batch_id
        ).filter(Batch.item_id == item_id)
    
    aging_records = query.all()
    
    # Prepare chart and table data
    chart_data = {}
    table_data = []
    
    for record in aging_records:
        # Get batch and item info
        batch = Batch.query.get(record.batch_id)
        item = Item.query.get(batch.item_id) if batch else None
        
        # Skip if filtered by item and no match
        if item_id and (not item or item.id != int(item_id)):
            continue
        
        # Format date for chart grouping
        date_key = record.timestamp.strftime('%Y-%m-%d') if record.timestamp else 'Unknown'
        
        # Count batches per day for chart
        if date_key not in chart_data:
            chart_data[date_key] = 0
        chart_data[date_key] += 1
        
        # Add to table data
        table_data.append({
            'date': date_key,
            'batch_id': record.batch_id,
            'item_name': item.name if item else 'Unknown',
            'aging_room': record.aging_room,
            'temperature': record.temperature,
            'humidity': record.humidity,
            'notes': record.notes or ''
        })
    
    # Sort chart data by date
    sorted_dates = sorted(chart_data.keys())
    
    # Format response
    response = {
        'summary': {
            'total_production': None,  # Not applicable for aging report
            'completed_runs': None,    # Not applicable for aging report
            'avg_efficiency': None     # Not applicable for aging report
        },
        'chart': {
            'labels': sorted_dates,
            'data': [chart_data[date] for date in sorted_dates]
        },
        'table': sorted(table_data, key=lambda x: x['date'], reverse=True)
    }
    
    return jsonify(response)

@production_bp.route('/api/reports/productivity', methods=['GET'])
@login_required
def get_productivity_report():
    """Generate worker productivity report data"""
    # Parse date range
    date_range = request.args.get('date_range', '')
    
    start_date, end_date = parse_date_range(date_range)
    
    # Query worker productivity records within date range
    productivity_records = WorkerProductivity.query.filter(
        WorkerProductivity.timestamp >= start_date,
        WorkerProductivity.timestamp <= end_date
    ).all()
    
    # Prepare chart and table data
    chart_data = {}  # Group by date
    worker_data = {}  # Group by worker
    table_data = []
    
    for record in productivity_records:
        # Get worker info
        worker = User.query.get(record.user_id)
        
        # Format date for chart grouping
        date_key = record.timestamp.strftime('%Y-%m-%d') if record.timestamp else 'Unknown'
        
        # Track productivity by date (average efficiency score per day)
        if date_key not in chart_data:
            chart_data[date_key] = {'total': 0, 'count': 0}
        
        if record.efficiency_score:
            chart_data[date_key]['total'] += record.efficiency_score
            chart_data[date_key]['count'] += 1
        
        # Track productivity by worker
        worker_name = worker.username if worker else f"Worker #{record.user_id}"
        if worker_name not in worker_data:
            worker_data[worker_name] = {
                'total_items': 0,
                'total_hours': 0,
                'records': 0
            }
        
        worker_data[worker_name]['total_items'] += record.items_produced
        worker_data[worker_name]['total_hours'] += record.hours_worked
        worker_data[worker_name]['records'] += 1
        
        # Add to table data
        table_data.append({
            'date': date_key,
            'worker_name': worker_name,
            'items_produced': record.items_produced,
            'hours_worked': record.hours_worked,
            'efficiency_score': f"{record.efficiency_score:.2f}" if record.efficiency_score else 'N/A',
            'notes': record.notes or ''
        })
    
    # Calculate daily average productivity for chart
    sorted_dates = sorted(chart_data.keys())
    daily_avg_productivity = [
        chart_data[date]['total'] / chart_data[date]['count'] if chart_data[date]['count'] > 0 else 0
        for date in sorted_dates
    ]
    
    # Calculate overall average productivity
    total_items = sum(data['total_items'] for data in worker_data.values())
    total_hours = sum(data['total_hours'] for data in worker_data.values())
    avg_productivity = total_items / total_hours if total_hours > 0 else 0
    
    # Format response
    response = {
        'summary': {
            'total_production': total_items,
            'completed_runs': None,  # Not applicable for productivity report
            'avg_efficiency': f"{avg_productivity:.2f}"
        },
        'chart': {
            'labels': sorted_dates,
            'data': daily_avg_productivity
        },
        'table': sorted(table_data, key=lambda x: x['date'], reverse=True)
    }
    
    return jsonify(response)
@production_bp.route('/api/reports/export', methods=['GET'])
@login_required
def export_report():
    """Export report data as CSV"""
    report_type = request.args.get('report_type', 'production')
    date_range = request.args.get('date_range', '')
    item_id = request.args.get('item_id')
    
    # Get report data based on type
    if report_type == 'production':
        data = get_production_report().json
    elif report_type == 'efficiency':
        data = get_efficiency_report().json
    elif report_type == 'aging':
        data = get_aging_report().json
    elif report_type == 'productivity':
        data = get_productivity_report().json
    else:
        return jsonify({'error': 'Invalid report type'}), 400
    
    # Create CSV file in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write headers based on report type
    if report_type == 'production':
        writer.writerow(['التاريخ', 'رقم الدورة', 'المنتج', 'الكمية', 'الحالة', 'المسؤول'])
    elif report_type == 'efficiency':
        writer.writerow(['التاريخ', 'رقم الدورة', 'الكمية المخططة', 'الكمية الفعلية', 'الكفاءة', 'ملاحظات'])
    elif report_type == 'aging':
        writer.writerow(['التاريخ', 'رقم الدفعة', 'المنتج', 'غرفة التعتيق', 'درجة الحرارة', 'الرطوبة', 'ملاحظات'])
    elif report_type == 'productivity':
        writer.writerow(['التاريخ', 'اسم العامل', 'الكمية المنتجة', 'ساعات العمل', 'معدل الكفاءة', 'ملاحظات'])
    
    # Write data rows
    for row in data['table']:
        if report_type == 'production':
            writer.writerow([
                row['date'], row['run_id'], row['item_name'], 
                row['quantity'], row['status'], row['responsible_user']
            ])
        elif report_type == 'efficiency':
            writer.writerow([
                row['date'], row['run_id'], row['planned_quantity'], 
                row['actual_quantity'], row['efficiency'], row['notes']
            ])
        elif report_type == 'aging':
            writer.writerow([
                row['date'], row['batch_id'], row['item_name'], 
                row['aging_room'], row['temperature'], row['humidity'], row['notes']
            ])
        elif report_type == 'productivity':
            writer.writerow([
                row['date'], row['worker_name'], row['items_produced'], 
                row['hours_worked'], row['efficiency_score'], row['notes']
            ])
    
    # Prepare response
    output.seek(0)
    
    # Create a filename for the download
    filename = f'{report_type}_report_{datetime.now().strftime("%Y%m%d")}.csv'
    
    # Use the updated parameter names for send_file
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=filename  # Changed from attachment_filename to download_name
    )

def parse_date_range(date_range_str):
    """Parse date range string into start and end dates"""
    try:
        if date_range_str and ' to ' in date_range_str:
            start_str, end_str = date_range_str.split(' to ')
            start_date = datetime.strptime(start_str.strip(), '%Y-%m-%d')
            end_date = datetime.strptime(end_str.strip(), '%Y-%m-%d')
            # Make end_date inclusive by setting it to end of day
            end_date = end_date.replace(hour=23, minute=59, second=59)
        else:
            # Default to last 30 days
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
    except Exception as e:
        # Log the error for debugging
        print(f"Error parsing date range: {e}")
        # Default to last 30 days on error
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
    
    return start_date, end_date

@production_bp.route('/api/batch-slots/<int:id>', methods=['DELETE'])
@login_required
def delete_batch_slot(id):
    batch_slot = BatchSlot.query.get_or_404(id)
    
    # Get the slot to update its quantity
    slot = WarehouseSlot.query.get(batch_slot.slot_id)
    
    if slot:
        # Decrease the slot's quantity by the quantity in the batch slot
        slot.quantity -= batch_slot.quantity_in_slot
        
        # If the slot is now empty, clear its item_id
        if slot.quantity <= 0:
            slot.quantity = 0
            slot.item_id = None
    
    # Delete the batch slot
    db.session.delete(batch_slot)
    db.session.commit()
    
    return jsonify({
        'message': 'تم إزالة الدفعة من الموقع بنجاح'
    })


