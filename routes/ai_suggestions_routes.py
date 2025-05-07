from flask import Blueprint, request, jsonify, render_template, current_app, send_file
from flask_login import login_required, current_user
from models import db, AISuggestion, Item, Category
from utils.ai_suggestions import analyze_item_data, start_suggestion_thread
import threading
import pandas as pd
import io
from datetime import datetime

# Create a Blueprint for AI suggestions routes
ai_suggestions_bp = Blueprint('ai_suggestions', __name__)

# Global variable to store the suggestion thread
suggestion_thread = None

@ai_suggestions_bp.route('/api/ai-suggestions', methods=['GET'])
@login_required
def get_ai_suggestions():
    """Get AI suggestions with optional filtering and pagination"""
    try:
        # Get query parameters
        status = request.args.get('status', 'Pending')
        suggestion_type = request.args.get('type')
        item_id = request.args.get('item_id')

        # Pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)

        # Build query
        query = AISuggestion.query

        if status:
            query = query.filter(AISuggestion.status == status)

        if suggestion_type:
            query = query.filter(AISuggestion.suggestion_type == suggestion_type)

        if item_id:
            query = query.filter(AISuggestion.item_id == item_id)

        # Order by created_at descending
        query = query.order_by(AISuggestion.created_at.desc())

        # Apply pagination
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        suggestions = pagination.items

        # Format response
        result = []
        for suggestion in suggestions:
            item_data = None
            if suggestion.item:
                item_data = {
                    'id': suggestion.item.id,
                    'name': suggestion.item.name,
                    'sku': suggestion.item.sku,
                    'category_name': suggestion.item.category.name if suggestion.item.category else None,
                    'reorder_level': suggestion.item.reorder_level
                }

            result.append({
                'id': suggestion.id,
                'item': item_data,
                'suggestion_type': suggestion.suggestion_type,
                'suggestion_text': suggestion.suggestion_text,
                'suggested_value': suggestion.suggested_value,
                'status': suggestion.status,
                'created_at': suggestion.created_at.isoformat() if suggestion.created_at else None
            })

        # Return paginated response
        return jsonify({
            'items': result,
            'pagination': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'pages': pagination.pages,
                'has_next': pagination.has_next,
                'has_prev': pagination.has_prev,
                'next_num': pagination.next_num if pagination.has_next else None,
                'prev_num': pagination.prev_num if pagination.has_prev else None
            }
        })

    except Exception as e:
        current_app.logger.error(f"Error getting AI suggestions: {e}")
        return jsonify({'error': str(e)}), 500

@ai_suggestions_bp.route('/api/ai-suggestions/<int:suggestion_id>', methods=['PUT'])
@login_required
def update_suggestion_status(suggestion_id):
    """Update the status of an AI suggestion"""
    try:
        data = request.get_json()

        if not data or 'status' not in data:
            return jsonify({'error': 'Status is required'}), 400

        status = data['status']
        if status not in ['Applied', 'Dismissed']:
            return jsonify({'error': 'Invalid status. Must be Applied or Dismissed'}), 400

        suggestion = AISuggestion.query.get_or_404(suggestion_id)
        suggestion.status = status

        # If applying the suggestion, update the item
        if status == 'Applied' and suggestion.item_id and suggestion.suggested_value:
            item = Item.query.get(suggestion.item_id)
            if item:
                if suggestion.suggestion_type == 'NameImprovement':
                    item.name = suggestion.suggested_value
                elif suggestion.suggestion_type == 'ReorderLevelAdjustment':
                    try:
                        item.reorder_level = int(suggestion.suggested_value)
                    except ValueError:
                        pass
                elif suggestion.suggestion_type == 'CategoryMismatch' and suggestion.suggested_value:
                    try:
                        category = Category.query.filter_by(name=suggestion.suggested_value).first()
                        if category:
                            item.category_id = category.id
                    except Exception:
                        pass

        db.session.commit()
        return jsonify({'success': True, 'status': status})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating suggestion status: {e}")
        return jsonify({'error': str(e)}), 500

@ai_suggestions_bp.route('/api/ai-suggestions/analyze', methods=['POST'])
@login_required
def trigger_analysis():
    """Manually trigger AI analysis for items"""
    try:
        data = request.get_json()
        item_id = data.get('item_id')
        category_id = data.get('category_id')

        # Get the current Flask app
        app = current_app._get_current_object()

        # Start analysis in a separate thread to avoid blocking the request
        thread = threading.Thread(
            target=analyze_item_data,
            kwargs={'item_id': item_id, 'category_id': category_id, 'app': app}
        )
        thread.daemon = True
        thread.start()

        return jsonify({'success': True, 'message': 'Analysis started'})

    except Exception as e:
        current_app.logger.error(f"Error triggering analysis: {e}")
        return jsonify({'error': str(e)}), 500

@ai_suggestions_bp.route('/api/ai-suggestions/edit-item', methods=['POST'])
@login_required
def edit_item_from_suggestion():
    """Edit an item directly based on suggestion type"""
    try:
        data = request.get_json()

        if not data or 'item_id' not in data or 'edit_type' not in data:
            return jsonify({'error': 'Missing required fields'}), 400

        item_id = data.get('item_id')
        edit_type = data.get('edit_type')
        new_value = data.get('new_value')
        suggestion_id = data.get('suggestion_id')

        if not new_value:
            return jsonify({'error': 'New value is required'}), 400

        # Get the item
        item = Item.query.get_or_404(item_id)

        # Apply the edit based on type
        if edit_type == 'NameImprovement':
            item.name = new_value
        elif edit_type == 'ReorderLevelAdjustment':
            try:
                item.reorder_level = int(new_value)
            except ValueError:
                return jsonify({'error': 'Reorder level must be a number'}), 400
        elif edit_type == 'CategoryMismatch':
            try:
                category = Category.query.filter_by(name=new_value).first()
                if not category:
                    return jsonify({'error': 'Category not found'}), 404
                item.category_id = category.id
            except Exception as e:
                return jsonify({'error': f'Error updating category: {str(e)}'}), 400
        else:
            return jsonify({'error': 'Invalid edit type'}), 400

        # If a suggestion ID was provided, mark it as applied
        if suggestion_id:
            suggestion = AISuggestion.query.get(suggestion_id)
            if suggestion:
                suggestion.status = 'Applied'

        db.session.commit()
        return jsonify({'success': True, 'message': 'Item updated successfully'})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error editing item: {e}")
        return jsonify({'error': str(e)}), 500

@ai_suggestions_bp.route('/api/ai-suggestions/export', methods=['GET'])
@login_required
def export_ai_suggestions():
    """Export AI suggestions to Excel file"""
    try:
        # Get query parameters
        status = request.args.get('status', 'Pending')
        suggestion_type = request.args.get('type')

        # Build query
        query = AISuggestion.query

        if status:
            query = query.filter(AISuggestion.status == status)

        if suggestion_type:
            query = query.filter(AISuggestion.suggestion_type == suggestion_type)

        # Get suggestions with related data
        suggestions = query.order_by(AISuggestion.created_at.desc()).all()

        # Prepare data for Excel
        data = []
        for suggestion in suggestions:
            item_name = "غير معروف"
            item_sku = ""
            category_name = ""
            reorder_level = ""

            if suggestion.item:
                item_name = suggestion.item.name
                item_sku = suggestion.item.sku
                category_name = suggestion.item.category.name if suggestion.item.category else ""
                reorder_level = suggestion.item.reorder_level

            suggestion_type_name = {
                'NameImprovement': 'تحسين الاسم',
                'CategoryMismatch': 'تصنيف غير مناسب',
                'ReorderLevelAdjustment': 'تعديل مستوى إعادة الطلب',
                'InventoryAnomaly': 'شذوذ في المخزون'
            }.get(suggestion.suggestion_type, suggestion.suggestion_type)

            status_name = {
                'Pending': 'معلق',
                'Applied': 'مطبق',
                'Dismissed': 'مرفوض'
            }.get(suggestion.status, suggestion.status)

            data.append({
                'رقم الاقتراح': suggestion.id,
                'اسم العنصر': item_name,
                'الرمز التعريفي': item_sku,
                'الفئة': category_name,
                'مستوى إعادة الطلب': reorder_level,
                'نوع الاقتراح': suggestion_type_name,
                'الاقتراح': suggestion.suggestion_text,
                'القيمة المقترحة': suggestion.suggested_value or '',
                'الحالة': status_name,
                'تاريخ الإنشاء': suggestion.created_at.strftime('%Y-%m-%d %H:%M:%S') if suggestion.created_at else ''
            })

        # Create DataFrame
        df = pd.DataFrame(data)

        # Create Excel file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='اقتراحات الذكاء الاصطناعي', index=False)

            # Get the xlsxwriter workbook and worksheet objects
            workbook = writer.book
            worksheet = writer.sheets['اقتراحات الذكاء الاصطناعي']

            # Add some formatting
            header_format = workbook.add_format({
                'bold': True,
                'text_wrap': True,
                'valign': 'top',
                'fg_color': '#D9D9D9',
                'border': 1
            })

            # Write the column headers with the defined format
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)

            # Set column widths
            worksheet.set_column('A:A', 10)  # رقم الاقتراح
            worksheet.set_column('B:B', 30)  # اسم العنصر
            worksheet.set_column('C:C', 15)  # الرمز التعريفي
            worksheet.set_column('D:D', 20)  # الفئة
            worksheet.set_column('E:E', 15)  # مستوى إعادة الطلب
            worksheet.set_column('F:F', 20)  # نوع الاقتراح
            worksheet.set_column('G:G', 50)  # الاقتراح
            worksheet.set_column('H:H', 20)  # القيمة المقترحة
            worksheet.set_column('I:I', 15)  # الحالة
            worksheet.set_column('J:J', 20)  # تاريخ الإنشاء

        # Set the file pointer to the beginning
        output.seek(0)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"ai_suggestions_{timestamp}.xlsx"

        # Return the Excel file
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        current_app.logger.error(f"Error exporting AI suggestions: {e}")
        return jsonify({'error': str(e)}), 500

@ai_suggestions_bp.route('/ai-suggestions-dashboard')
@login_required
def ai_suggestions_dashboard():
    """Render the AI suggestions dashboard page"""
    return render_template('ai_suggestions_dashboard.html')

# Blueprint registration hook - no longer starts the background thread automatically
@ai_suggestions_bp.record_once
def on_load(state):
    # We no longer start the background thread automatically
    # The analysis will only run when manually triggered via the "تحليل جديد" button
    app = state.app
    app.logger.info("AI suggestions module initialized - analysis will only run when manually triggered")
