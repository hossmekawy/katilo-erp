from io import BytesIO
from flask import Blueprint, request, jsonify, render_template, send_file
from flask_login import login_required, current_user
import pdfkit
from models import db, QualityInspection, QualityInspectionCriteria, PurchaseOrderDetail, PurchaseOrder, Item
from datetime import datetime

quality_bp = Blueprint('quality_bp', __name__)

# ================= TEMPLATE ROUTES =================

@quality_bp.route('/quality-inspections')
@login_required
def quality_inspections_page():
    return render_template('quality_inspections.html')

@quality_bp.route('/quality-inspections/<int:id>')
@login_required
def quality_inspection_details_page(id):
    inspection = QualityInspection.query.get_or_404(id)
    return render_template('quality_inspection_details.html', inspection_id=id)

# ================= API ROUTES =================

@quality_bp.route('/api/purchase-orders/<int:po_id>/quality-inspection', methods=['POST'])
@login_required
def create_quality_inspection(po_id):
    """Create quality inspection for items in a purchase order"""
    purchase_order = PurchaseOrder.query.get_or_404(po_id)
    data = request.get_json()
    
    # Validate required fields
    if not data.get('inspections') or len(data['inspections']) == 0:
        return jsonify({'message': 'بيانات الفحص مطلوبة'}), 400
    
    created_inspections = []
    
    for inspection_data in data['inspections']:
        detail_id = inspection_data.get('purchase_order_detail_id')
        if not detail_id:
            continue
            
        # Verify the detail belongs to this purchase order
        po_detail = PurchaseOrderDetail.query.get(detail_id)
        if not po_detail or po_detail.po_id != po_id:
            return jsonify({'message': 'تفاصيل طلب الشراء غير صحيحة'}), 400
        
        # Create inspection record
        inspection = QualityInspection(
            purchase_order_detail_id=detail_id,
            inspector_id=current_user.id,
            status=inspection_data.get('status', 'Pending'),
            notes=inspection_data.get('notes', '')
        )
        
        db.session.add(inspection)
        db.session.flush()  # Get ID without committing
        
        # Add inspection criteria
        for criterion in inspection_data.get('criteria', []):
            inspection_criterion = QualityInspectionCriteria(
                inspection_id=inspection.id,
                criterion_name=criterion.get('name', ''),
                expected_value=criterion.get('expected_value', ''),
                actual_value=criterion.get('actual_value', ''),
                passed=criterion.get('passed', False),
                importance=criterion.get('importance', 'Major')
            )
            db.session.add(inspection_criterion)
        
        created_inspections.append({
            'id': inspection.id,
            'purchase_order_detail_id': inspection.purchase_order_detail_id,
            'status': inspection.status
        })
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Database error: {str(e)}'}), 500
    
    return jsonify({
        'message': f'تم إنشاء {len(created_inspections)} فحص جودة بنجاح',
        'created_inspections': created_inspections
    }), 201

@quality_bp.route('/api/quality-inspections', methods=['GET'])
@login_required
def get_quality_inspections():
    """Get all quality inspections"""
    inspections = QualityInspection.query.all()
    
    result = []
    for inspection in inspections:
        po_detail = inspection.purchase_order_detail
        item = Item.query.get(po_detail.item_id) if po_detail else None
        purchase_order = PurchaseOrder.query.get(po_detail.po_id) if po_detail else None
        
        result.append({
            'id': inspection.id,
            'purchase_order_id': purchase_order.id if purchase_order else None,
            'item_id': po_detail.item_id if po_detail else None,
            'item_name': item.name if item else 'Unknown',
            'inspection_date': inspection.inspection_date.isoformat(),
            'inspector_name': inspection.inspector.username if inspection.inspector else 'Unknown',
            'status': inspection.status,
            'criteria_count': len(inspection.criteria),
            'passed_criteria_count': sum(1 for c in inspection.criteria if c.passed)
        })
    
    return jsonify(result)

@quality_bp.route('/api/quality-inspections/<int:id>', methods=['GET'])
@login_required
def get_quality_inspection(id):
    """Get a specific quality inspection with its criteria"""
    inspection = QualityInspection.query.get_or_404(id)
    po_detail = inspection.purchase_order_detail
    item = Item.query.get(po_detail.item_id) if po_detail else None
    purchase_order = PurchaseOrder.query.get(po_detail.po_id) if po_detail else None
    
    criteria_list = []
    for criterion in inspection.criteria:
        criteria_list.append({
            'id': criterion.id,
            'name': criterion.criterion_name,
            'expected_value': criterion.expected_value,
            'actual_value': criterion.actual_value,
            'passed': criterion.passed,
            'importance': criterion.importance
        })
    
    return jsonify({
        'id': inspection.id,
        'purchase_order_id': purchase_order.id if purchase_order else None,
        'purchase_order_detail_id': inspection.purchase_order_detail_id,
        'item_id': po_detail.item_id if po_detail else None,
        'item_name': item.name if item else 'Unknown',
        'inspection_date': inspection.inspection_date.isoformat(),
        'inspector_id': inspection.inspector_id,
        'inspector_name': inspection.inspector.username if inspection.inspector else 'Unknown',
        'status': inspection.status,
        'notes': inspection.notes,
        'criteria': criteria_list
    })

@quality_bp.route('/api/quality-inspections/<int:id>', methods=['PUT'])
@login_required
def update_quality_inspection(id):
    """Update a quality inspection"""
    inspection = QualityInspection.query.get_or_404(id)
    data = request.get_json()
    
    if 'status' in data:
        inspection.status = data['status']
    if 'notes' in data:
        inspection.notes = data['notes']
    
    # Update criteria if provided
    if 'criteria' in data:
        for criterion_data in data['criteria']:
            criterion_id = criterion_data.get('id')
            
            # Convert string boolean to Python boolean
            if 'passed' in criterion_data:
                if isinstance(criterion_data['passed'], str):
                    criterion_data['passed'] = criterion_data['passed'].lower() == 'true'
            
            if criterion_id:
                # Update existing criterion
                criterion = QualityInspectionCriteria.query.get(criterion_id)
                if criterion and criterion.inspection_id == id:
                    if 'name' in criterion_data:
                        criterion.criterion_name = criterion_data['name']
                    if 'expected_value' in criterion_data:
                        criterion.expected_value = criterion_data['expected_value']
                    if 'actual_value' in criterion_data:
                        criterion.actual_value = criterion_data['actual_value']
                    if 'passed' in criterion_data:
                        criterion.passed = criterion_data['passed']
            else:
                # Add new criterion
                new_criterion = QualityInspectionCriteria(
                    inspection_id=id,
                    criterion_name=criterion_data.get('name', ''),
                    expected_value=criterion_data.get('expected_value', ''),
                    actual_value=criterion_data.get('actual_value', ''),
                    passed=criterion_data.get('passed', False),
                    importance=criterion_data.get('importance', 'Major')
                )
                db.session.add(new_criterion)
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Database error: {str(e)}'}), 500
    
    return jsonify({
        'id': inspection.id,
        'status': inspection.status,
        'message': 'تم تحديث فحص الجودة بنجاح'
    })

# Add this to the quality_control.py file

@quality_bp.route('/api/quality-inspections/<int:id>/pdf', methods=['GET'])
@login_required
def download_quality_inspection_pdf(id):
    """Generate and download quality inspection report as PDF"""
    try:
        # Get inspection details
        inspection = QualityInspection.query.get_or_404(id)
        po_detail = inspection.purchase_order_detail
        item = Item.query.get(po_detail.item_id) if po_detail else None
        purchase_order = PurchaseOrder.query.get(po_detail.po_id) if po_detail else None
        
        # Prepare inspection data for template
        inspection_data = {
            'id': inspection.id,
            'purchase_order_id': purchase_order.id if purchase_order else None,
            'item_id': po_detail.item_id if po_detail else None,
            'item_name': item.name if item else 'Unknown',
            'inspection_date': inspection.inspection_date,
            'inspector_id': inspection.inspector_id,
            'inspector_name': inspection.inspector.username if inspection.inspector else 'Unknown',
            'status': inspection.status,
            'notes': inspection.notes,
            'criteria': []
        }
        
        # Add criteria data
        for criterion in inspection.criteria:
            inspection_data['criteria'].append({
                'id': criterion.id,
                'name': criterion.criterion_name,
                'expected_value': criterion.expected_value,
                'actual_value': criterion.actual_value,
                'passed': criterion.passed,
                'importance': criterion.importance
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
        
        # Render HTML template
        html_content = render_template(
            'quality_inspection_pdf.html',
            inspection=inspection_data,
            logo_src=logo_src,
            current_user=current_user,
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
                download_name=f'quality_inspection_{inspection.id}_{datetime.now().strftime("%Y%m%d")}.pdf'
            )
        except Exception as e:
            # Log the error for debugging
            current_app.logger.error(f"PDF generation error: {str(e)}")
            return jsonify({"error": f"Failed to generate PDF: {str(e)}"}), 500
            
    except Exception as e:
        # Log the error for debugging
        current_app.logger.error(f"Error in download_quality_inspection_pdf: {str(e)}")
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500
