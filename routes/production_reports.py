from flask import Blueprint, render_template, request, jsonify, send_file, current_app
from flask_login import login_required, current_user
from models import (
    Category, db, Item, Batch, BOM, BOMDetail, ProductionRun, ProductionRunDetail, 
    ProductionProcess, ProductionOrder, QCTest, QCTestResult, 
    ProductPackaging, PackagingMaterial, AgingRecord, ProductionStep,
    ProductionStepRecord, ProductionParameter
)
from sqlalchemy import func, desc, and_, or_
import pandas as pd
import os
import tempfile
import subprocess
from datetime import datetime, timedelta
import json
from werkzeug.utils import secure_filename
import uuid

production_reports = Blueprint('production_reports', __name__)

@production_reports.route('/api/reports/production/<report_type>')
@login_required
def generate_production_report(report_type):
    """Generate production reports based on the specified type and format."""
    report_format = request.args.get('format', 'pdf').lower()
    
    # Common parameters
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    item_id = request.args.get('item_id')
    batch_id = request.args.get('batch_id')
    production_order_id = request.args.get('production_order_id')
    production_run_id = request.args.get('production_run_id')
    
    # Convert date strings to datetime objects if provided
    if date_from:
        date_from = datetime.strptime(date_from, '%Y-%m-%d')
    if date_to:
        date_to = datetime.strptime(date_to, '%Y-%m-%d')
        # Include the entire day
        date_to = date_to + timedelta(days=1) - timedelta(seconds=1)
    
    # Generate the appropriate report based on type
    if report_type == 'activity_log':
        return generate_activity_log_report(report_format, date_from, date_to, item_id, batch_id)
    elif report_type == 'production_orders':
        return generate_production_orders_report(report_format, date_from, date_to, item_id)
    elif report_type == 'batches':
        return generate_batches_report(report_format, date_from, date_to, item_id)
    elif report_type == 'quality_control':
        return generate_qc_report(report_format, date_from, date_to, batch_id)
    elif report_type == 'packaging':
        return generate_packaging_report(report_format, date_from, date_to, batch_id)
    elif report_type == 'material_usage':
        return generate_material_usage_report(report_format, date_from, date_to, production_order_id)
    elif report_type == 'bom_details':
        return generate_bom_details_report(report_format, item_id)
    elif report_type == 'production_timeline':
        return generate_production_timeline_report(report_format, batch_id)
    elif report_type == 'production_efficiency':
        return generate_production_efficiency_report(report_format, date_from, date_to)
    elif report_type == 'aging_records':
        return generate_aging_records_report(report_format, date_from, date_to, batch_id)
    else:
        return jsonify({'error': 'Invalid report type'}), 400

def generate_activity_log_report(report_format, date_from, date_to, item_id=None, batch_id=None):
    """Generate a report of all production activities."""
    query = db.session.query(
        ProductionProcess.id,
        ProductionProcess.process_type,
        ProductionProcess.start_time,
        ProductionProcess.end_time,
        ProductionProcess.temperature,
        ProductionProcess.humidity,
        ProductionProcess.ph_level,
        ProductionProcess.notes,
        Batch.lot_number,
        Item.name.label('item_name'),
        Item.sku
    ).join(
        Batch, ProductionProcess.batch_id == Batch.id
    ).join(
        Item, Batch.item_id == Item.id
    )
    
    # Apply filters
    if date_from:
        query = query.filter(ProductionProcess.start_time >= date_from)
    if date_to:
        query = query.filter(ProductionProcess.start_time <= date_to)
    if item_id:
        query = query.filter(Item.id == item_id)
    if batch_id:
        query = query.filter(Batch.id == batch_id)
    
    # Order by start_time descending
    query = query.order_by(desc(ProductionProcess.start_time))
    
    activities = query.all()
    
    # Prepare data for the report
    data = []
    for activity in activities:
        duration = None
        if activity.start_time and activity.end_time:
            duration = (activity.end_time - activity.start_time).total_seconds() / 3600  # in hours
        
        data.append({
            'id': activity.id,
            'process_type': activity.process_type,
            'start_time': activity.start_time.strftime('%Y-%m-%d %H:%M') if activity.start_time else '',
            'end_time': activity.end_time.strftime('%Y-%m-%d %H:%M') if activity.end_time else '',
            'duration_hours': f"{duration:.2f}" if duration else '',
            'temperature': f"{activity.temperature:.1f}°C" if activity.temperature else '',
            'humidity': f"{activity.humidity:.1f}%" if activity.humidity else '',
            'ph_level': f"{activity.ph_level:.2f}" if activity.ph_level else '',
            'lot_number': activity.lot_number,
            'item_name': activity.item_name,
            'sku': activity.sku,
            'notes': activity.notes or ''
        })
    
    # Generate the report
    title = "تقرير سجل أنشطة الإنتاج"
    return render_and_convert_report(
        'production/reports/activity_log.html', 
        report_format, 
        title, 
        {'activities': data, 'date_from': date_from, 'date_to': date_to}
    )

def generate_production_orders_report(report_format, date_from, date_to, item_id=None):
    """Generate a report of production orders."""
    query = db.session.query(
        ProductionOrder.id,
        ProductionOrder.quantity,
        ProductionOrder.status,
        ProductionOrder.scheduled_start,
        ProductionOrder.scheduled_end,
        ProductionOrder.actual_start,
        ProductionOrder.actual_end,
        Item.name.label('product_name'),
        Item.sku,
        func.count(Batch.id).label('batch_count')
    ).join(
        Item, ProductionOrder.product_id == Item.id
    ).outerjoin(
        Batch, ProductionOrder.id == Batch.production_order_id
    ).group_by(
        ProductionOrder.id
    )
    
    # Apply filters
    if date_from:
        query = query.filter(or_(
            ProductionOrder.scheduled_start >= date_from,
            ProductionOrder.actual_start >= date_from
        ))
    if date_to:
        query = query.filter(or_(
            ProductionOrder.scheduled_start <= date_to,
            ProductionOrder.actual_start <= date_to
        ))
    if item_id:
        query = query.filter(Item.id == item_id)
    
    # Order by scheduled_start descending
    query = query.order_by(desc(ProductionOrder.scheduled_start))
    
    orders = query.all()
    
    # Prepare data for the report
    data = []
    for order in orders:
        # Calculate efficiency (actual vs scheduled time)
        efficiency = None
        if order.scheduled_start and order.scheduled_end and order.actual_start and order.actual_end:
            scheduled_duration = (order.scheduled_end - order.scheduled_start).total_seconds()
            actual_duration = (order.actual_end - order.actual_start).total_seconds()
            if scheduled_duration > 0:
                efficiency = (scheduled_duration / actual_duration) * 100
        
        data.append({
            'id': order.id,
            'product_name': order.product_name,
            'sku': order.sku,
            'quantity': order.quantity,
            'status': order.status,
            'scheduled_start': order.scheduled_start.strftime('%Y-%m-%d %H:%M') if order.scheduled_start else '',
            'scheduled_end': order.scheduled_end.strftime('%Y-%m-%d %H:%M') if order.scheduled_end else '',
            'actual_start': order.actual_start.strftime('%Y-%m-%d %H:%M') if order.actual_start else '',
            'actual_end': order.actual_end.strftime('%Y-%m-%d %H:%M') if order.actual_end else '',
            'efficiency': f"{efficiency:.1f}%" if efficiency else '',
            'batch_count': order.batch_count
        })
    
    # Generate the report
    title = "تقرير أوامر الإنتاج"
    return render_and_convert_report(
        'production/reports/production_orders.html', 
        report_format, 
        title, 
        {'orders': data, 'date_from': date_from, 'date_to': date_to}
    )

def generate_batches_report(report_format, date_from, date_to, item_id=None):
    """Generate a report of production batches."""
    query = db.session.query(
        Batch.id,
        Batch.lot_number,
        Batch.production_date,
        Batch.expiry_date,
        Batch.quantity,
        Batch.status,
        Item.name.label('item_name'),
        Item.sku,
        ProductionOrder.id.label('production_order_id')
    ).join(
        Item, Batch.item_id == Item.id
    ).outerjoin(
        ProductionOrder, Batch.production_order_id == ProductionOrder.id
    )
    
    # Apply filters
    if date_from:
        query = query.filter(Batch.production_date >= date_from)
    if date_to:
        query = query.filter(Batch.production_date <= date_to)
    if item_id:
        query = query.filter(Item.id == item_id)
    
    # Order by production_date descending
    query = query.order_by(desc(Batch.production_date))
    
    batches = query.all()
    
    # Prepare data for the report
    data = []
    for batch in batches:
        # Get QC status
        qc_status = db.session.query(QCTest.status).filter(
            QCTest.batch_id == batch.id
        ).order_by(desc(QCTest.created_at)).first()
        
        data.append({
            'id': batch.id,
            'lot_number': batch.lot_number,
            'production_date': batch.production_date.strftime('%Y-%m-%d') if batch.production_date else '',
            'expiry_date': batch.expiry_date.strftime('%Y-%m-%d') if batch.expiry_date else '',
            'quantity': batch.quantity,
            'status': batch.status,
            'item_name': batch.item_name,
            'sku': batch.sku,
            'production_order_id': batch.production_order_id,
            'qc_status': qc_status[0] if qc_status else 'لم يتم الفحص'
        })
    
    # Generate the report
    title = "تقرير دفعات الإنتاج"
    return render_and_convert_report(
        'production/reports/batches.html', 
        report_format, 
        title, 
        {'batches': data, 'date_from': date_from, 'date_to': date_to}
    )

def generate_qc_report(report_format, date_from, date_to, batch_id=None):
    """Generate a quality control report."""
    query = db.session.query(
        QCTest.id,
        QCTest.test_type,
        QCTest.status,
        QCTest.created_at,
        QCTest.completed_at,
        QCTest.notes,
        Batch.lot_number,
        Item.name.label('item_name'),
        Item.sku
    ).join(
        Batch, QCTest.batch_id == Batch.id
    ).join(
        Item, Batch.item_id == Item.id
    )
    
    # Apply filters
    if date_from:
        query = query.filter(QCTest.created_at >= date_from)
    if date_to:
        query = query.filter(QCTest.created_at <= date_to)
    if batch_id:
        query = query.filter(Batch.id == batch_id)
    
    # Order by created_at descending
    query = query.order_by(desc(QCTest.created_at))
    
    tests = query.all()
    
    # Prepare data for the report
    data = []
    for test in tests:
        # Get test results
        results = db.session.query(QCTestResult).filter(
            QCTestResult.test_id == test.id
        ).all()
        
        test_results = []
        for result in results:
            test_results.append({
                'parameter_name': result.parameter_name,
                'expected_value': result.expected_value,
                'actual_value': result.actual_value,
                'passed': result.is_passed
            })
        
        data.append({
            'id': test.id,
            'test_type': test.test_type,
            'status': test.status,
            'created_at': test.created_at.strftime('%Y-%m-%d %H:%M') if test.created_at else '',
            'completed_at': test.completed_at.strftime('%Y-%m-%d %H:%M') if test.completed_at else '',
            'lot_number': test.lot_number,
            'item_name': test.item_name,
            'sku': test.sku,
            'notes': test.notes or '',
            'results': test_results
        })
    
    # Generate the report
    title = "تقرير مراقبة الجودة"
    return render_and_convert_report(
        'production/reports/quality_control.html', 
        report_format, 
        title, 
        {'tests': data, 'date_from': date_from, 'date_to': date_to}
    )

def generate_packaging_report(report_format, date_from, date_to, batch_id=None):
    """Generate a packaging report."""
    query = db.session.query(
        ProductPackaging.id,
        ProductPackaging.packaging_date,
        ProductPackaging.status,
        ProductPackaging.notes,
        Batch.lot_number,
        Batch.id.label('batch_id'),
        Item.name.label('item_name'),
        Item.sku
    ).join(
        Batch, ProductPackaging.batch_id == Batch.id
    ).join(
        Item, Batch.item_id == Item.id
    )
    
    # Apply filters
    if date_from:
        query = query.filter(ProductPackaging.packaging_date >= date_from)
    if date_to:
        query = query.filter(ProductPackaging.packaging_date <= date_to)
    if batch_id:
        query = query.filter(Batch.id == batch_id)
    
    # Order by packaging_date descending
    query = query.order_by(desc(ProductPackaging.packaging_date))
    
    packaging_records = query.all()
    
    # Prepare data for the report
    data = []
    for record in packaging_records:
        # Get packaging materials
        materials = db.session.query(
            PackagingMaterial.quantity_used,
            Item.name.label('material_name'),
            Item.sku.label('material_sku')
        ).join(
            Item, PackagingMaterial.item_id == Item.id
        ).filter(
            PackagingMaterial.packaging_id == record.id
        ).all()
        
        packaging_materials = []
        for material in materials:
            packaging_materials.append({
                'material_name': material.material_name,
                'material_sku': material.material_sku,
                'quantity_used': material.quantity_used
            })
        
        data.append({
            'id': record.id,
            'packaging_date': record.packaging_date.strftime('%Y-%m-%d %H:%M') if record.packaging_date else '',
            'status': record.status,
            'lot_number': record.lot_number,
            'batch_id': record.batch_id,
            'item_name': record.item_name,
            'sku': record.sku,
            'notes': record.notes or '',
            'materials': packaging_materials
        })
    
    # Generate the report
    title = "تقرير التعبئة والتغليف"
    return render_and_convert_report(
        'production/reports/packaging.html', 
        report_format, 
        title, 
        {'packaging_records': data, 'date_from': date_from, 'date_to': date_to}
    )

def generate_material_usage_report(report_format, date_from, date_to, production_order_id=None):
    """Generate a material usage report."""
    # First, get all production orders in the date range
    order_query = db.session.query(
        ProductionOrder.id,
        ProductionOrder.quantity,
        ProductionOrder.status,
        ProductionOrder.scheduled_start,
        ProductionOrder.actual_start,
        Item.name.label('product_name'),
        Item.sku.label('product_sku')
    ).join(
        Item, ProductionOrder.product_id == Item.id
    )
    
    # Apply filters to orders
    if date_from:
        order_query = order_query.filter(or_(
            ProductionOrder.scheduled_start >= date_from,
            ProductionOrder.actual_start >= date_from
        ))
    if date_to:
        order_query = order_query.filter(or_(
            ProductionOrder.scheduled_start <= date_to,
            ProductionOrder.actual_start <= date_to
        ))
    if production_order_id:
        order_query = order_query.filter(ProductionOrder.id == production_order_id)
    
    orders = order_query.all()
    
    # Prepare data for the report
    data = []
    for order in orders:
        # Get the BOM for this product
        bom = db.session.query(BOM).filter(BOM.final_product_id == Item.id).first()
        
        if bom:
            # Get BOM details (materials used)
            materials = db.session.query(
                BOMDetail.quantity_required,
                BOMDetail.unit_of_measure,
                Item.name.label('material_name'),
                Item.sku.label('material_sku'),
                Item.cost.label('material_cost')
            ).join(
                Item, BOMDetail.component_item_id == Item.id
            ).filter(
                BOMDetail.bom_id == bom.id
            ).all()
            
            order_materials = []
            total_material_cost = 0
            
            for material in materials:
                # Calculate total quantity and cost for this material in this order
                total_qty = material.quantity_required * order.quantity
                total_cost = total_qty * material.material_cost
                total_material_cost += total_cost
                
                order_materials.append({
                    'material_name': material.material_name,
                    'material_sku': material.material_sku,
                    'quantity_per_unit': material.quantity_required,
                    'unit_of_measure': material.unit_of_measure,
                    'total_quantity': total_qty,
                    'unit_cost': material.material_cost,
                    'total_cost': total_cost
                })
            
            data.append({
                'order_id': order.id,
                'product_name': order.product_name,
                'product_sku': order.product_sku,
                'order_quantity': order.quantity,
                'status': order.status,
                'scheduled_start': order.scheduled_start.strftime('%Y-%m-%d') if order.scheduled_start else '',
                'actual_start': order.actual_start.strftime('%Y-%m-%d') if order.actual_start else '',
                'materials': order_materials,
                'total_material_cost': total_material_cost
            })
    
    # Generate the report
    title = "تقرير استخدام المواد"
    return render_and_convert_report(
        'production/reports/material_usage.html', 
        report_format, 
        title, 
        {'orders': data, 'date_from': date_from, 'date_to': date_to}
    )

def generate_bom_details_report(report_format, item_id):
    """Generate a BOM details report for a specific product."""
    if not item_id:
        return jsonify({'error': 'Item ID is required'}), 400
    
    # Get the product details
    product = db.session.query(Item).filter(Item.id == item_id).first()
    if not product:
        return jsonify({'error': 'Product not found'}), 404
    
    # Get the BOM for this product
    bom = db.session.query(BOM).filter(BOM.final_product_id == item_id).first()
    if not bom:
        return jsonify({'error': 'BOM not found for this product'}), 404
    
    # Get BOM details (materials used)
    materials = db.session.query(
        BOMDetail.id,
        BOMDetail.quantity_required,
        BOMDetail.unit_of_measure,
        Item.id.label('material_id'),
        Item.name.label('material_name'),
        Item.sku.label('material_sku'),
        Item.cost.label('material_cost'),
        Category.name.label('category_name')
    ).join(
        Item, BOMDetail.component_item_id == Item.id
    ).join(
        Category, Item.category_id == Category.id
    ).filter(
        BOMDetail.bom_id == bom.id
    ).all()
    
    # Prepare data for the report
    bom_materials = []
    total_cost = 0
    
    for material in materials:
        material_cost = material.quantity_required * material.material_cost
        total_cost += material_cost
        
        bom_materials.append({
            'id': material.id,
            'material_id': material.material_id,
            'material_name': material.material_name,
            'material_sku': material.material_sku,
            'category': material.category_name,
            'quantity_required': material.quantity_required,
            'unit_of_measure': material.unit_of_measure,
            'unit_cost': material.material_cost,
            'total_cost': material_cost
        })
    
    # Generate the report
    title = f"تقرير قائمة المكونات - {product.name}"
    return render_and_convert_report(
        'production/reports/bom_details.html', 
        report_format, 
        title, 
        {
            'product': product,
            'bom': bom,
            'materials': bom_materials,
            'total_cost': total_cost
        }
    )

def generate_production_timeline_report(report_format, batch_id):
    """Generate a production timeline report for a specific batch."""
    if not batch_id:
        return jsonify({'error': 'Batch ID is required'}), 400
    
    # Get the batch details
    batch = db.session.query(
        Batch.id,
        Batch.lot_number,
        Batch.production_date,
        Batch.expiry_date,
        Batch.quantity,
        Batch.status,
        Item.name.label('item_name'),
        Item.sku
    ).join(
        Item, Batch.item_id == Item.id
    ).filter(
        Batch.id == batch_id
    ).first()
    
    if not batch:
        return jsonify({'error': 'Batch not found'}), 404
    
    # Get all production processes for this batch
    processes = db.session.query(
        ProductionProcess.id,
        ProductionProcess.process_type,
        ProductionProcess.start_time,
        ProductionProcess.end_time,
        ProductionProcess.temperature,
        ProductionProcess.humidity,
        ProductionProcess.ph_level,
        ProductionProcess.notes
    ).filter(
        ProductionProcess.batch_id == batch_id
    ).order_by(
        ProductionProcess.start_time
    ).all()
    
    # Get all production step records for this batch
    steps = db.session.query(
        ProductionStepRecord.id,
        ProductionStepRecord.start_time,
        ProductionStepRecord.end_time,
        ProductionStepRecord.notes,
        ProductionStep.name.label('step_name'),
        ProductionStep.description.label('step_description')
    ).join(
        ProductionStep, ProductionStepRecord.step_id == ProductionStep.id
    ).filter(
        ProductionStepRecord.batch_id == batch_id
    ).order_by(
        ProductionStepRecord.start_time
    ).all()
    
    # Get quality control tests for this batch
    qc_tests = db.session.query(
        QCTest.id,
        QCTest.test_type,
        QCTest.status,
        QCTest.created_at,
        QCTest.completed_at,
        QCTest.notes
    ).filter(
        QCTest.batch_id == batch_id
    ).order_by(
        QCTest.created_at
    ).all()
    
    # Get packaging records for this batch
    packaging = db.session.query(
        ProductPackaging.id,
        ProductPackaging.packaging_date,
        ProductPackaging.status,
        ProductPackaging.notes
    ).filter(
        ProductPackaging.batch_id == batch_id
    ).order_by(
        ProductPackaging.packaging_date
    ).all()
    
    # Combine all events into a timeline
    timeline = []
    
    for process in processes:
        timeline.append({
            'type': 'process',
            'id': process.id,
            'name': process.process_type,
            'start_time': process.start_time,
            'end_time': process.end_time,
            'details': {
                'temperature': process.temperature,
                'humidity': process.humidity,
                'ph_level': process.ph_level,
                'notes': process.notes
            }
        })
    
    for step in steps:
        timeline.append({
            'type': 'step',
            'id': step.id,
            'name': step.step_name,
            'start_time': step.start_time,
            'end_time': step.end_time,
            'details': {
                'description': step.step_description,
                'notes': step.notes
            }
        })
    
    for test in qc_tests:
        timeline.append({
            'type': 'qc_test',
            'id': test.id,
            'name': f"اختبار الجودة: {test.test_type}",
            'start_time': test.created_at,
            'end_time': test.completed_at,
            'details': {
                'status': test.status,
                'notes': test.notes
            }
        })
    
    for pkg in packaging:
        timeline.append({
            'type': 'packaging',
            'id': pkg.id,
            'name': "التعبئة والتغليف",
            'start_time': pkg.packaging_date,
            'end_time': pkg.packaging_date,  # Same as start for packaging
            'details': {
                'status': pkg.status,
                'notes': pkg.notes
            }
        })
    
    # Sort timeline by start_time
    timeline.sort(key=lambda x: x['start_time'] if x['start_time'] else datetime.min)
    
    # Generate the report
    title = f"تقرير الجدول الزمني للإنتاج - دفعة {batch.lot_number}"
    return render_and_convert_report(
        'production/reports/production_timeline.html', 
        report_format, 
        title, 
        {
            'batch': batch,
            'timeline': timeline
        }
    )

def generate_production_efficiency_report(report_format, date_from, date_to):
    """Generate a production efficiency report."""
    # Get all production orders in the date range
    query = db.session.query(
        ProductionOrder.id,
        ProductionOrder.quantity,
        ProductionOrder.scheduled_start,
        ProductionOrder.scheduled_end,
        ProductionOrder.actual_start,
        ProductionOrder.actual_end,
        Item.name.label('product_name'),
        Item.sku
    ).join(
        Item, ProductionOrder.product_id == Item.id
    ).filter(
        ProductionOrder.status == 'Completed'
    )
    
    # Apply date filters
    if date_from:
        query = query.filter(ProductionOrder.actual_end >= date_from)
    if date_to:
        query = query.filter(ProductionOrder.actual_end <= date_to)
    
    orders = query.all()
    
    # Prepare data for the report
    data = []
    total_scheduled_hours = 0
    total_actual_hours = 0
    
    for order in orders:
        if order.scheduled_start and order.scheduled_end and order.actual_start and order.actual_end:
            scheduled_duration = (order.scheduled_end - order.scheduled_start).total_seconds() / 3600  # in hours
            actual_duration = (order.actual_end - order.actual_start).total_seconds() / 3600  # in hours
            
            efficiency = (scheduled_duration / actual_duration) * 100 if actual_duration > 0 else 0
            
            total_scheduled_hours += scheduled_duration
            total_actual_hours += actual_duration
            
            data.append({
                'id': order.id,
                'product_name': order.product_name,
                'sku': order.sku,
                'quantity': order.quantity,
                'scheduled_start': order.scheduled_start.strftime('%Y-%m-%d %H:%M'),
                'scheduled_end': order.scheduled_end.strftime('%Y-%m-%d %H:%M'),
                'scheduled_duration': f"{scheduled_duration:.2f}",
                'actual_start': order.actual_start.strftime('%Y-%m-%d %H:%M'),
                'actual_end': order.actual_end.strftime('%Y-%m-%d %H:%M'),
                'actual_duration': f"{actual_duration:.2f}",
                'efficiency': f"{efficiency:.1f}%",
                'units_per_hour': f"{order.quantity / actual_duration:.2f}" if actual_duration > 0 else '0'
            })
    
    # Calculate overall efficiency
    overall_efficiency = (total_scheduled_hours / total_actual_hours) * 100 if total_actual_hours > 0 else 0
    
    # Generate the report
    title = "تقرير كفاءة الإنتاج"
    return render_and_convert_report(
        'production/reports/production_efficiency.html', 
        report_format, 
        title, 
        {
            'orders': data, 
            'date_from': date_from, 
            'date_to': date_to,
            'total_scheduled_hours': f"{total_scheduled_hours:.2f}",
            'total_actual_hours': f"{total_actual_hours:.2f}",
            'overall_efficiency': f"{overall_efficiency:.1f}%"
        }
    )

def generate_aging_records_report(report_format, date_from, date_to, batch_id=None):
    """Generate a report of cheese aging records."""
    query = db.session.query(
        AgingRecord.id,
        AgingRecord.aging_room,
        AgingRecord.temperature,
        AgingRecord.humidity,
        AgingRecord.appearance,
        AgingRecord.texture,
        AgingRecord.aroma,
        AgingRecord.notes,
        AgingRecord.timestamp,
        Batch.lot_number,
        Item.name.label('item_name'),
        Item.sku
    ).join(
        Batch, AgingRecord.batch_id == Batch.id
    ).join(
        Item, Batch.item_id == Item.id
    )
    
    # Apply filters
    if date_from:
        query = query.filter(AgingRecord.timestamp >= date_from)
    if date_to:
        query = query.filter(AgingRecord.timestamp <= date_to)
    if batch_id:
        query = query.filter(Batch.id == batch_id)
    
    # Order by timestamp descending
    query = query.order_by(desc(AgingRecord.timestamp))
    
    records = query.all()
    
    # Prepare data for the report
    data = []
    for record in records:
        data.append({
            'id': record.id,
            'aging_room': record.aging_room,
            'temperature': f"{record.temperature:.1f}°C",
            'humidity': f"{record.humidity:.1f}%",
            'appearance': record.appearance,
            'texture': record.texture,
            'aroma': record.aroma,
            'notes': record.notes,
            'timestamp': record.timestamp.strftime('%Y-%m-%d %H:%M'),
            'lot_number': record.lot_number,
            'item_name': record.item_name,
            'sku': record.sku
        })
    
    # Generate the report
    title = "تقرير سجلات التعتيق"
    return render_and_convert_report(
        'production/reports/aging_records.html', 
        report_format, 
        title, 
        {'records': data, 'date_from': date_from, 'date_to': date_to}
    )

def render_and_convert_report(template_path, report_format, title, data):
    """Render the report template and convert to the requested format."""
    # Add common data for all reports
    data['title'] = title
    data['generated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    data['generated_by'] = current_user.username if current_user else 'System'
    
    # Render the HTML template
    html_content = render_template(template_path, **data)
    
    # For HTML format, return directly
    if report_format == 'html':
        return html_content
    
    # For other formats, convert the HTML
    if report_format == 'pdf':
        return convert_to_pdf(html_content, title)
    elif report_format in ['excel', 'csv']:
        return convert_to_spreadsheet(data, report_format, title)
    else:
        return jsonify({'error': 'Unsupported format'}), 400

def convert_to_pdf(html_content, title):
    """Convert HTML content to PDF using wkhtmltopdf."""
    # Create a temporary file for the HTML content
    with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as html_file:
        html_file.write(html_content.encode('utf-8'))
        html_file_path = html_file.name
    
    # Create a temporary file for the PDF output
    pdf_file_path = tempfile.mktemp(suffix='.pdf')
    
    try:
        # Use wkhtmltopdf to convert HTML to PDF
        # Add options for RTL support and proper Arabic rendering
        cmd = [
            'wkhtmltopdf',
            '--encoding', 'utf-8',
            '--page-size', 'A4',
            '--margin-top', '10mm',
            '--margin-right', '10mm',
            '--margin-bottom', '10mm',
            '--margin-left', '10mm',
            '--header-spacing', '5',
            '--footer-spacing', '5',
            '--header-center', title,
            '--footer-center', '[page]/[topage]',
            html_file_path,
            pdf_file_path
        ]
        
        subprocess.run(cmd, check=True)
        
        # Return the PDF file
        return send_file(
            pdf_file_path,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"{secure_filename(title)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        )
    
    finally:
        # Clean up temporary files
        try:
            os.unlink(html_file_path)
            # The PDF file will be removed automatically after sending
        except:
            pass

def convert_to_spreadsheet(data, format_type, title):
    """Convert data to Excel or CSV format."""
    # Create a pandas DataFrame from the data
    # This depends on the structure of the data, which varies by report type
    # We'll need to handle each report type differently
    
    # For simplicity, let's assume data contains a key that matches the report type
    # and contains a list of dictionaries for the main data
    df = None
    
    # Find the main data list in the data dictionary
    for key, value in data.items():
        if isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
            df = pd.DataFrame(value)
            break
    
    if df is None:
        return jsonify({'error': 'Could not convert data to spreadsheet format'}), 400
    
    # Create a temporary file for the output
    if format_type == 'excel':
        output_file = tempfile.mktemp(suffix='.xlsx')
        df.to_excel(output_file, index=False, sheet_name=title[:31])  # Excel sheet names limited to 31 chars
        mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        extension = 'xlsx'
    else:  # CSV
        output_file = tempfile.mktemp(suffix='.csv')
        df.to_csv(output_file, index=False, encoding='utf-8-sig')  # Use UTF-8 with BOM for Excel compatibility
        mimetype = 'text/csv'
        extension = 'csv'
    
    # Return the file
    return send_file(
        output_file,
        mimetype=mimetype,
        as_attachment=True,
        download_name=f"{secure_filename(title)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{extension}"
    )

@production_reports.route('/production/reports')
@login_required
def production_reports_page():
    """Render the production reports page."""
    return render_template('production/reports.html')

@production_reports.route('/api/production/report_data')
@login_required
def get_report_data():
    """Get data needed for the production reports page."""
    # Get all items
    items = db.session.query(Item.id, Item.name, Item.sku, Category.name.label('category_name')).join(
        Category, Item.category_id == Category.id
    ).all()
    
    items_data = [{'id': item.id, 'name': item.name, 'sku': item.sku, 'category': item.category_name} for item in items]
    
    # Get all batches
    batches = db.session.query(Batch.id, Batch.lot_number, Item.name.label('item_name')).join(
        Item, Batch.item_id == Item.id
    ).order_by(desc(Batch.production_date)).limit(100).all()
    
    batches_data = [{'id': batch.id, 'lot_number': batch.lot_number, 'item_name': batch.item_name} for batch in batches]
    
    # Get all production orders
    orders = db.session.query(ProductionOrder.id, Item.name.label('product_name')).join(
        Item, ProductionOrder.product_id == Item.id
    ).order_by(desc(ProductionOrder.created_at)).limit(100).all()
    
    orders_data = [{'id': order.id, 'name': f"أمر إنتاج #{order.id} - {order.product_name}"} for order in orders]
    
    return jsonify({
        'items': items_data,
        'batches': batches_data,
        'production_orders': orders_data
    })
