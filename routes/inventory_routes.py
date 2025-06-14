from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, current_app, session
from flask_login import login_required
from models import db, Item, Inventory, Category
from sqlalchemy import func
import pandas as pd
import os
import uuid
from werkzeug.utils import secure_filename

inventory_bp = Blueprint('inventory', __name__, url_prefix='/inventory')

@inventory_bp.route('/item-weights')
@login_required
def item_weights():
    """Show the item weights and volumes management page"""
    return render_template('inventory/item_weights.html')

@inventory_bp.route('/api/items/<int:item_id>/update-weight-volume', methods=['POST'])
@login_required
def update_item_weight_volume(item_id):
    """Update an item's weight and volume in the item_weights table"""
    data = request.json

    try:
        # Check if the item exists
        item = Item.query.get_or_404(item_id)

        # Get the weight and volume from the request
        weight = data.get('weight', 0)
        volume = data.get('volume', 0)

        # Check if there's already a record for this item in the item_weights table
        from sqlalchemy import text
        result = db.session.execute(
            text("SELECT id FROM item_weights WHERE item_id = :item_id"),
            {"item_id": item_id}
        ).fetchone()

        if result:
            # Update the existing record
            db.session.execute(
                text("UPDATE item_weights SET weight = :weight, volume = :volume WHERE item_id = :item_id"),
                {"weight": weight, "volume": volume, "item_id": item_id}
            )
        else:
            # Insert a new record
            db.session.execute(
                text("INSERT INTO item_weights (item_id, weight, volume) VALUES (:item_id, :weight, :volume)"),
                {"item_id": item_id, "weight": weight, "volume": volume}
            )

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Item weight and volume updated successfully'
        })
    except Exception as e:
        db.session.rollback()
        print(f"Error updating item weight and volume: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error updating item: {str(e)}'
        }), 500

@inventory_bp.route('/api/items', methods=['GET'])
@login_required
def get_items():
    """Get all items with their weights and volumes from the item_weights table"""
    # Get all items
    items = Item.query.all()

    # Get all item weights in a single query
    item_weights_data = {}
    try:
        from sqlalchemy import text
        results = db.session.execute(
            text("SELECT item_id, weight, volume FROM item_weights")
        ).fetchall()

        for row in results:
            item_weights_data[row[0]] = {'weight': row[1], 'volume': row[2]}
    except Exception as e:
        print(f"Error fetching item weights: {str(e)}")

    # Build the response
    response = []
    for item in items:
        weight_data = item_weights_data.get(item.id, {'weight': 0, 'volume': 0})
        response.append({
            'id': item.id,
            'name': item.name,
            'sku': item.sku,
            'category_id': item.category_id,
            'weight': weight_data['weight'],
            'volume': weight_data['volume']
        })

    return jsonify(response)

@inventory_bp.route('/api/categories', methods=['GET'])
@login_required
def get_categories():
    """Get all categories"""
    categories = Category.query.all()

    return jsonify([{
        'id': category.id,
        'name': category.name,
        'category_type': category.category_type
    } for category in categories])

@inventory_bp.route('/api/items/<int:item_id>', methods=['GET'])
@login_required
def get_item_details(item_id):
    """Get details for a specific item"""
    item = Item.query.get_or_404(item_id)

    return jsonify({
        'id': item.id,
        'name': item.name,
        'sku': item.sku,
        'description': item.description,
        'unit_of_measure': item.unit_of_measure,
        'cost': item.cost,
        'selling_price': item.price,  # Using price as selling_price
        'reorder_level': item.reorder_level
    })

@inventory_bp.route('/api/items/<int:item_id>/availability', methods=['GET'])
@login_required
def check_item_availability(item_id):
    """Check if an item is available in the requested quantity"""
    quantity = request.args.get('quantity', type=int, default=1)

    # Get total quantity across all warehouses
    total_quantity = db.session.query(func.sum(Inventory.quantity)).filter(
        Inventory.item_id == item_id
    ).scalar() or 0

    is_available = total_quantity >= quantity

    return jsonify({
        'is_available': is_available,
        'available_quantity': total_quantity,
        'requested_quantity': quantity
    })

@inventory_bp.route('/import-excel', methods=['GET'])
@login_required
def import_excel_form():
    """Show the Excel import form"""
    # Get all categories for the dropdown
    categories = Category.query.all()
    return render_template('inventory/import_excel.html', categories=categories)

@inventory_bp.route('/upload-excel', methods=['POST'])
@login_required
def upload_excel():
    """Upload Excel file and show column mapping page or sheet selection if multiple sheets"""
    if 'excel_file' not in request.files:
        flash('No file part', 'error')
        return redirect(url_for('inventory.import_excel_form'))

    file = request.files['excel_file']
    default_category_id = request.form.get('default_category')

    if not default_category_id:
        flash('يجب اختيار التصنيف الافتراضي للعناصر', 'error')
        return redirect(url_for('inventory.import_excel_form'))

    if file.filename == '':
        flash('No selected file', 'error')
        return redirect(url_for('inventory.import_excel_form'))

    if file and file.filename.endswith(('.xlsx', '.xls')):
        # Create a unique filename
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4()}_{filename}"

        # Ensure the upload directory exists
        upload_dir = os.path.join(current_app.config['TEMP_FOLDER'], 'excel_imports')
        os.makedirs(upload_dir, exist_ok=True)

        # Save the file
        file_path = os.path.join(upload_dir, unique_filename)
        file.save(file_path)

        # Read the Excel file and check for multiple sheets
        try:
            # Get the sheet names from the Excel file
            excel_file = pd.ExcelFile(file_path)
            sheet_names = excel_file.sheet_names

            # Get the default category for display
            default_category = Category.query.get(default_category_id)

            # If there's more than one sheet, show the sheet selection page
            if len(sheet_names) > 1:
                return render_template('inventory/select_sheet.html',
                                      sheet_names=sheet_names,
                                      file_path=file_path,
                                      default_category_id=default_category_id,
                                      default_category=default_category)
            else:
                # If there's only one sheet, proceed with that sheet
                sheet_name = sheet_names[0]
                df = pd.read_excel(file_path, sheet_name=sheet_name)

                # Get column names for the mapping page
                excel_columns = df.columns.tolist()

                # Get a preview of the data (first 5 rows)
                excel_preview = df.head(5).to_dict('records')

                # Render the column mapping page
                return render_template('inventory/map_columns.html',
                                      excel_columns=excel_columns,
                                      excel_preview=excel_preview,
                                      file_path=file_path,
                                      sheet_name=sheet_name,
                                      default_category_id=default_category_id,
                                      default_category=default_category)

        except Exception as e:
            flash(f'Error reading Excel file: {str(e)}', 'error')
            return redirect(url_for('inventory.import_excel_form'))
    else:
        flash('File must be an Excel file (.xlsx or .xls)', 'error')
        return redirect(url_for('inventory.import_excel_form'))

@inventory_bp.route('/process-sheet-selection', methods=['POST'])
@login_required
def process_sheet_selection():
    """Process sheet selection and show column mapping page"""
    # Get form data
    file_path = request.form.get('file_path')
    default_category_id = request.form.get('default_category_id')
    selected_sheet = request.form.get('selected_sheet')

    # Validate required fields
    if not file_path or not default_category_id or not selected_sheet:
        flash('Missing required fields', 'error')
        return redirect(url_for('inventory.import_excel_form'))

    try:
        # Read the selected sheet from the Excel file
        df = pd.read_excel(file_path, sheet_name=selected_sheet)

        # Get column names for the mapping page
        excel_columns = df.columns.tolist()

        # Get a preview of the data (first 5 rows)
        excel_preview = df.head(5).to_dict('records')

        # Get the default category for display
        default_category = Category.query.get(default_category_id)

        # Render the column mapping page
        return render_template('inventory/map_columns.html',
                              excel_columns=excel_columns,
                              excel_preview=excel_preview,
                              file_path=file_path,
                              sheet_name=selected_sheet,
                              default_category_id=default_category_id,
                              default_category=default_category)
    except Exception as e:
        flash(f'Error reading Excel sheet: {str(e)}', 'error')
        return redirect(url_for('inventory.import_excel_form'))

@inventory_bp.route('/process-mapping', methods=['POST'])
@login_required
def process_mapping():
    """Process column mapping and show preview page"""
    # Get form data
    file_path = request.form.get('file_path')
    default_category_id = request.form.get('default_category_id')
    sheet_name = request.form.get('sheet_name')  # Get the sheet name if provided

    # Get column mapping from form
    column_mapping = {
        'name': request.form.get('name_column'),
        'description': request.form.get('description_column'),
        'unit_of_measure': request.form.get('unit_column'),
        'cost': request.form.get('cost_column'),
        'price': request.form.get('price_column'),
        'sku': request.form.get('sku_column')
    }

    # Validate required fields
    if not file_path or not default_category_id or not column_mapping['name']:
        flash('Missing required fields', 'error')
        return redirect(url_for('inventory.import_excel_form'))

    try:
        # Read the Excel file with the specified sheet if provided
        if sheet_name:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
        else:
            df = pd.read_excel(file_path)

        # Map columns according to user input
        mapped_items = []
        for _, row in df.iterrows():
            item = {}

            # Process each field with its mapped column name
            for field, column in column_mapping.items():
                if column and column in df.columns:
                    # Get the value from the mapped column
                    value = row[column]

                    # Handle NaN values
                    if pd.isna(value):
                        if field in ['cost', 'price']:
                            value = 0
                        elif field in ['description', 'unit_of_measure', 'sku']:
                            value = ''
                        else:
                            value = None

                    item[field] = value
                else:
                    # Set default values for missing columns
                    if field == 'name':
                        # Name is required, so we'll skip items without a name later
                        item[field] = None
                    elif field in ['cost', 'price']:
                        item[field] = 0
                    elif field == 'sku':
                        item[field] = f"SKU-{uuid.uuid4().hex[:8]}"
                    elif field == 'unit_of_measure':
                        item[field] = 'وحدة'
                    else:
                        item[field] = ''

            # Only add items that have a name
            if item.get('name'):
                mapped_items.append(item)

        # Store the file path and mapped items in session for later processing
        session_data = {
            'file_path': file_path,
            'items': mapped_items,
            'default_category_id': default_category_id,
            'column_mapping': column_mapping
        }

        # Get the default category name for display
        default_category = Category.query.get(default_category_id)

        # Get all categories for the dropdown
        categories = Category.query.all()

        # Return the preview page with mapped items
        return render_template('inventory/preview_excel.html',
                              items=mapped_items,
                              session_data=session_data,
                              default_category=default_category,
                              categories=categories)

    except Exception as e:
        flash(f'Error processing Excel file: {str(e)}', 'error')
        return redirect(url_for('inventory.import_excel_form'))

@inventory_bp.route('/process-excel', methods=['POST'])
@login_required
def process_excel():
    """Process the Excel data and insert into database"""
    data = request.json
    items = data.get('items', [])
    default_category_id = data.get('default_category_id')

    # Counters for summary
    added_items = 0
    added_categories = 0
    skipped_items = 0

    for item in items:
        action = item.get('action')

        if action == 'item':
            # Add as item
            try:
                # Use the item's category_id if provided, otherwise use the default
                category_id = item.get('category_id') or default_category_id

                # Make sure we have a category_id
                if not category_id:
                    print(f"Error: No category ID for item {item.get('name')}")
                    skipped_items += 1
                    continue

                # Get the category to update its type if needed
                category = Category.query.get(int(category_id))
                if category:
                    # Update the category type based on the selected product type
                    product_type = item.get('category_type', 'RawMaterial')
                    if category.category_type != product_type:
                        category.category_type = product_type
                        print(f"Updated category {category.name} type to {product_type}")

                # Create a new item
                new_item = Item(
                    name=item.get('name'),
                    category_id=int(category_id),
                    sku=item.get('sku', f"SKU-{uuid.uuid4().hex[:8]}"),
                    description=item.get('description', ''),
                    unit_of_measure=item.get('unit_of_measure', 'وحدة'),
                    cost=float(item.get('cost', 0)),
                    price=float(item.get('price', 0)),
                    reorder_level=int(item.get('reorder_level', 0))
                )
                db.session.add(new_item)
                added_items += 1
            except Exception as e:
                # Log the error but continue with other items
                print(f"Error adding item {item.get('name')}: {str(e)}")

        elif action == 'category':
            # Add as category - this means creating a new category in the system
            try:
                # Use the selected product type or default to RawMaterial
                product_type = item.get('category_type', 'RawMaterial')

                new_category = Category(
                    name=item.get('name'),
                    description=item.get('description', ''),
                    category_type=product_type
                )
                db.session.add(new_category)
                added_categories += 1
            except Exception as e:
                # Log the error but continue with other items
                print(f"Error adding category {item.get('name')}: {str(e)}")

        else:
            # Skip this item
            skipped_items += 1

    try:
        db.session.commit()
        return jsonify({
            'success': True,
            'message': f'Successfully processed Excel file. Added {added_items} items, {added_categories} categories, and skipped {skipped_items} items.',
            'added_items': added_items,
            'added_categories': added_categories,
            'skipped_items': skipped_items
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error processing Excel file: {str(e)}'
        }), 500
