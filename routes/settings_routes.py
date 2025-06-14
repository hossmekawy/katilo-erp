from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app, send_file
from flask_login import login_required, current_user
import os
import sys
import json
import datetime
import sqlite3
import tempfile
import shutil
from werkzeug.utils import secure_filename
from io import BytesIO
import subprocess

# Add the parent directory to sys.path to allow importing from the root directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import from the models_helper module
from models_helper import db, SystemSettings, User, Role, Permission, RolePermission

# Create the blueprint
settings_bp = Blueprint('settings', __name__, url_prefix='/settings')

# ================= TEMPLATE ROUTES =================

@settings_bp.route('/')
@login_required
def settings_index():
    """Main settings page"""
    if not current_user.role or current_user.role.name != 'admin':
        flash('You do not have permission to access settings', 'error')
        return redirect('/dashboard')

    return render_template('settings/index.html')

@settings_bp.route('/system')
@login_required
def system_settings():
    """System settings page"""
    if not current_user.role or current_user.role.name != 'admin':
        flash('You do not have permission to access settings', 'error')
        return redirect('/dashboard')

    settings = SystemSettings.get_settings()
    return render_template('settings/system.html', settings=settings)

@settings_bp.route('/company')
@login_required
def company_settings():
    """Company settings page"""
    if not current_user.role or current_user.role.name != 'admin':
        flash('You do not have permission to access settings', 'error')
        return redirect('/dashboard')

    settings = SystemSettings.get_settings()
    return render_template('settings/company.html', settings=settings)

@settings_bp.route('/themes')
@login_required
def themes_settings():
    """Theme settings page"""
    if not current_user.role or current_user.role.name != 'admin':
        flash('You do not have permission to access settings', 'error')
        return redirect('/dashboard')

    settings = SystemSettings.get_settings()
    return render_template('settings/themes.html', settings=settings)

@settings_bp.route('/api-keys')
@login_required
def api_keys_settings():
    """API keys settings page"""
    if not current_user.role or current_user.role.name != 'admin':
        flash('You do not have permission to access settings', 'error')
        return redirect('/dashboard')

    # Get current API keys from app config
    gemini_api_key = current_app.config.get('GEMINI_API_KEY', '')
    google_maps_api_key = current_app.config.get('GOOGLE_MAPS_API_KEY', '')

    # Mask the API keys for display
    masked_gemini_key = mask_api_key(gemini_api_key)
    masked_maps_key = mask_api_key(google_maps_api_key)

    return render_template('settings/api_keys.html',
                          gemini_api_key=masked_gemini_key,
                          google_maps_api_key=masked_maps_key)

@settings_bp.route('/database')
@login_required
def database_settings():
    """Database import/export settings page"""
    if not current_user.role or current_user.role.name != 'admin':
        flash('You do not have permission to access settings', 'error')
        return redirect('/dashboard')

    return render_template('settings/database.html')

@settings_bp.route('/permissions')
@login_required
def permissions_settings():
    """Permissions settings page"""
    if not current_user.role or current_user.role.name != 'admin':
        flash('You do not have permission to access settings', 'error')
        return redirect('/dashboard')

    permissions = Permission.query.all()
    return render_template('settings/permissions.html', permissions=permissions)

# ================= API ROUTES =================

@settings_bp.route('/api/system-settings', methods=['GET', 'POST'])
@login_required
def api_system_settings():
    """API endpoint for system settings"""
    if not current_user.role or current_user.role.name != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    settings = SystemSettings.get_settings()

    if request.method == 'GET':
        return jsonify(settings.to_dict())

    elif request.method == 'POST':
        try:
            data = request.json

            # Update basic settings
            settings.system_title = data.get('system_title', settings.system_title)

            # Update theme settings
            settings.theme_mode = data.get('theme_mode', settings.theme_mode)
            settings.theme_color = data.get('theme_color', settings.theme_color)
            settings.background_color = data.get('background_color', settings.background_color)
            settings.sidebar_color = data.get('sidebar_color', settings.sidebar_color)

            # Update UI settings
            settings.font_family = data.get('font_family', settings.font_family)
            settings.font_size = data.get('font_size', settings.font_size)
            settings.border_radius = data.get('border_radius', settings.border_radius)
            settings.animation_speed = data.get('animation_speed', settings.animation_speed)

            # Update layout settings
            settings.layout_density = data.get('layout_density', settings.layout_density)
            settings.sidebar_collapsed = data.get('sidebar_collapsed', settings.sidebar_collapsed)
            settings.rtl_enabled = data.get('rtl_enabled', settings.rtl_enabled)

            # Update custom colors
            if 'custom_colors' in data and isinstance(data['custom_colors'], dict):
                settings.custom_colors = data['custom_colors']

            # Update image settings if provided
            if 'logo_image' in data:
                settings.logo_image = data['logo_image']
            if 'login_bg_image' in data:
                settings.login_bg_image = data['login_bg_image']
            if 'favicon_image' in data:
                settings.favicon_image = data['favicon_image']

            db.session.commit()

            return jsonify({'success': True, 'message': 'Settings updated successfully'})

        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

@settings_bp.route('/api/company-settings', methods=['GET', 'POST'])
@login_required
def api_company_settings():
    """API endpoint for company settings"""
    if not current_user.role or current_user.role.name != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    settings = SystemSettings.get_settings()

    if request.method == 'GET':
        company_settings = {
            'company_name': settings.company_name,
            'company_address': settings.company_address,
            'company_city': settings.company_city,
            'company_email': settings.company_email,
            'company_phone': settings.company_phone,
            'company_website': settings.company_website,
            'company_tax_id': settings.company_tax_id,
            'payment_terms_days': settings.payment_terms_days,
            'payment_terms_text': settings.payment_terms_text
        }
        return jsonify(company_settings)

    elif request.method == 'POST':
        try:
            data = request.json

            # Update company information
            settings.company_name = data.get('company_name', settings.company_name)
            settings.company_address = data.get('company_address', settings.company_address)
            settings.company_city = data.get('company_city', settings.company_city)
            settings.company_email = data.get('company_email', settings.company_email)
            settings.company_phone = data.get('company_phone', settings.company_phone)
            settings.company_website = data.get('company_website', settings.company_website)
            settings.company_tax_id = data.get('company_tax_id', settings.company_tax_id)

            # Update invoice settings
            settings.payment_terms_days = data.get('payment_terms_days', settings.payment_terms_days)
            settings.payment_terms_text = data.get('payment_terms_text', settings.payment_terms_text)

            db.session.commit()

            return jsonify({'success': True, 'message': 'Company settings updated successfully'})

        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

@settings_bp.route('/api/update-api-keys', methods=['POST'])
@login_required
def api_update_api_keys():
    """API endpoint to update API keys"""
    if not current_user.role or current_user.role.name != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        data = request.json

        # Get the .env file path
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')

        # Read existing .env file
        env_vars = {}
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                for line in f:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        env_vars[key] = value

        # Update API keys
        if 'gemini_api_key' in data and data['gemini_api_key']:
            env_vars['GEMINI_API_KEY'] = data['gemini_api_key']
            current_app.config['GEMINI_API_KEY'] = data['gemini_api_key']

        if 'google_maps_api_key' in data and data['google_maps_api_key']:
            env_vars['GOOGLE_MAPS_API_KEY'] = data['google_maps_api_key']
            current_app.config['GOOGLE_MAPS_API_KEY'] = data['google_maps_api_key']

        # Write back to .env file
        with open(env_path, 'w') as f:
            for key, value in env_vars.items():
                f.write(f"{key}={value}\n")

        return jsonify({'success': True, 'message': 'API keys updated successfully'})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@settings_bp.route('/api/export-database', methods=['GET'])
@login_required
def api_export_database():
    """API endpoint to export database"""
    if not current_user.role or current_user.role.name != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        # For PostgreSQL, we can't directly export the database file
        # Instead, we'll return a message explaining this
        return jsonify({
            'error': 'Direct database export is not supported for PostgreSQL databases. Please contact your system administrator for database backup procedures.'
        }), 400

    except Exception as e:
        return jsonify({'error': str(e), 'details': 'Error exporting database'}), 500

@settings_bp.route('/api/import-database', methods=['POST'])
@login_required
def api_import_database():
    """API endpoint to import database"""
    if not current_user.role or current_user.role.name != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        if 'database_file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400

        file = request.files['database_file']

        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        # For PostgreSQL, we can't directly import a database file
        # Instead, we'll return a message explaining this
        return jsonify({
            'error': 'Direct database import is not supported for PostgreSQL databases. Please use the database erase function to reset the database or contact your system administrator for database restoration.'
        }), 400

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@settings_bp.route('/api/erase-database', methods=['POST'])
@login_required
def api_erase_database():
    """API endpoint to erase database"""
    if not current_user.role or current_user.role.name != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        data = request.json
        password = data.get('password', '')

        # Verify the user's password
        if not current_user.check_password(password):
            return jsonify({'error': 'Invalid password'}), 401

        # Store current user information for recreation
        current_username = current_user.username
        current_email = current_user.email

        # Close all database connections
        db.session.close()
        db.engine.dispose()

        try:
            # Connect to PostgreSQL and drop all tables
            # We'll use SQLAlchemy's metadata to drop all tables
            db.drop_all()

            # Recreate all tables
            db.create_all()
        except Exception as e:
            # Log the error but continue with the process
            print(f"Error during database reset: {str(e)}")
            # We'll still try to create the admin user even if there were errors

        # Create default admin user if it doesn't exist
        admin_role = Role.query.filter_by(name='admin').first()
        if not admin_role:
            admin_role = Role(name='admin')
            db.session.add(admin_role)
            db.session.commit()

        # Create admin user with the same credentials
        admin_user = User(
            username=current_username,
            email=current_email,
            role_id=admin_role.id
        )
        admin_user.set_password(password)  # Use the password provided by the user for verification
        db.session.add(admin_user)

        # Create default system settings
        settings = SystemSettings.get_settings()
        if not settings:
            settings = SystemSettings()
            db.session.add(settings)

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Database erased successfully. The system has been reset to its initial state with your admin account preserved. Note: Some initial data may have duplicate keys and might need manual correction.'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e), 'details': 'Error erasing database'}), 500

# ================= HELPER FUNCTIONS =================

def get_database_path():
    """Get the path to the SQLite database file"""
    # Try multiple possible locations
    possible_db_paths = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'katilo.db'),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'instance', 'katilo.db'),
        'katilo.db',
        'instance/katilo.db'
    ]

    # Check each path
    for path in possible_db_paths:
        if os.path.exists(path):
            return path

    # If we can't find the database, try to get it from Flask's configuration
    if hasattr(current_app, 'config') and 'SQLALCHEMY_DATABASE_URI' in current_app.config:
        uri = current_app.config['SQLALCHEMY_DATABASE_URI']
        if uri.startswith('sqlite:///'):
            db_path = uri.replace('sqlite:///', '')
            if not os.path.isabs(db_path):
                db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), db_path)
            if os.path.exists(db_path):
                return db_path

    # Return None if no database file is found
    return None

def mask_api_key(api_key):
    """Mask API key for display"""
    if not api_key:
        return ''

    if len(api_key) <= 8:
        return '*' * len(api_key)

    return api_key[:4] + '*' * (len(api_key) - 8) + api_key[-4:]

@settings_bp.route('/api/backup-database', methods=['POST'])
@login_required
def api_backup_database():
    """API endpoint to backup PostgreSQL database"""
    if not current_user.role or current_user.role.name != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        # Get database connection info from app config
        db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
        if not db_uri or not db_uri.startswith('postgresql://'):
            return jsonify({'error': 'Not a PostgreSQL database'}), 400

        # Parse connection string
        # Format: postgresql://username:password@host:port/dbname
        db_parts = db_uri.replace('postgresql://', '').split('/')
        db_name = db_parts[-1]
        connection_parts = db_parts[0].split('@')
        
        auth_parts = connection_parts[0].split(':')
        username = auth_parts[0]
        password = auth_parts[1] if len(auth_parts) > 1 else ''
        
        host_parts = connection_parts[1].split(':')
        host = host_parts[0]
        port = host_parts[1] if len(host_parts) > 1 else '5432'

        # Create a timestamp for the filename
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"katiloerp_backup_{timestamp}.sql"
        
        # Create a temporary file to store the backup
        temp_dir = tempfile.mkdtemp()
        backup_path = os.path.join(temp_dir, filename)
        
        # Set environment variable for password if needed
        env = os.environ.copy()
        if password:
            env['PGPASSWORD'] = password
        
        # Execute pg_dump command
        cmd = [
            'pg_dump',
            '-h', host,
            '-p', port,
            '-U', username,
            '-F', 'c',  # Custom format for pg_restore
            '-b',  # Include large objects
            '-v',  # Verbose
            '-f', backup_path,
            db_name
        ]
        
        process = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        if process.returncode != 0:
            return jsonify({'error': f'Backup failed: {process.stderr}'}), 500
        
        # Send the file to the client
        return send_file(
            backup_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/octet-stream'
        )
        
    except Exception as e:
        return jsonify({'error': str(e), 'details': 'Error creating database backup'}), 500
    finally:
        # Clean up temporary directory
        if 'temp_dir' in locals():
            shutil.rmtree(temp_dir, ignore_errors=True)

@settings_bp.route('/api/restore-database', methods=['POST'])
@login_required
def api_restore_database():
    """API endpoint to restore PostgreSQL database"""
    if not current_user.role or current_user.role.name != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        if 'backup_file' not in request.files:
            return jsonify({'error': 'No backup file provided'}), 400

        file = request.files['backup_file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
            
        # Verify password
        password = request.form.get('password', '')
        if not current_user.check_password(password):
            return jsonify({'error': 'Invalid password'}), 401

        # Get database connection info from app config
        db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
        if not db_uri or not db_uri.startswith('postgresql://'):
            return jsonify({'error': 'Not a PostgreSQL database'}), 400

        # Parse connection string
        db_parts = db_uri.replace('postgresql://', '').split('/')
        db_name = db_parts[-1]
        connection_parts = db_parts[0].split('@')
        
        auth_parts = connection_parts[0].split(':')
        username = auth_parts[0]
        password_db = auth_parts[1] if len(auth_parts) > 1 else ''
        
        host_parts = connection_parts[1].split(':')
        host = host_parts[0]
        port = host_parts[1] if len(host_parts) > 1 else '5432'

        # Create a temporary directory to store the uploaded file
        temp_dir = tempfile.mkdtemp()
        backup_path = os.path.join(temp_dir, secure_filename(file.filename))
        file.save(backup_path)
        
        # Close all database connections
        db.session.close()
        db.engine.dispose()
        
        # Set environment variable for password if needed
        env = os.environ.copy()
        if password_db:
            env['PGPASSWORD'] = password_db
            
        # First, drop the database and recreate it
        # Connect to postgres database to drop and recreate the target database
        drop_cmd = [
            'psql',
            '-h', host,
            '-p', port,
            '-U', username,
            '-d', 'postgres',
            '-c', f"DROP DATABASE IF EXISTS {db_name};"
        ]
        
        create_cmd = [
            'psql',
            '-h', host,
            '-p', port,
            '-U', username,
            '-d', 'postgres',
            '-c', f"CREATE DATABASE {db_name};"
        ]
        
        # Execute drop and create commands
        subprocess.run(drop_cmd, env=env, capture_output=True, text=True)
        subprocess.run(create_cmd, env=env, capture_output=True, text=True)
        
        # Now restore the database using pg_restore
        restore_cmd = [
            'pg_restore',
            '-h', host,
            '-p', port,
            '-U', username,
            '-d', db_name,
            '-v',  # Verbose
            backup_path
        ]
        
        process = subprocess.run(restore_cmd, env=env, capture_output=True, text=True)
        
        if process.returncode != 0 and "errors were encountered" in process.stderr:
            # Some errors during restore are expected (like role already exists)
            # We'll return success with a warning
            return jsonify({
                'success': True,
                'warning': 'Database restored with some warnings. This is normal if roles or permissions already exist.',
                'details': process.stderr
            })
        elif process.returncode != 0:
            return jsonify({'error': f'Restore failed: {process.stderr}'}), 500
            
        return jsonify({
            'success': True,
            'message': 'Database restored successfully'
        })
        
    except Exception as e:
        return jsonify({'error': str(e), 'details': 'Error restoring database'}), 500
    finally:
        # Clean up temporary directory
        if 'temp_dir' in locals():
            shutil.rmtree(temp_dir, ignore_errors=True)

# Add these imports at the top of the file
from models_helper import SidebarItem

# Add these routes to your settings_routes.py file
@settings_bp.route('/sidebar')
@login_required
def sidebar_settings():
    """Sidebar settings page"""
    if not current_user.role or current_user.role.name != 'admin':
        flash('You do not have permission to access settings', 'error')
        return redirect('/dashboard')
        
    # Get a list of Font Awesome icons for the dropdown
    icons = [
        'fa-tachometer-alt', 'fa-boxes', 'fa-box-open', 'fa-th', 'fa-warehouse',
        'fa-clipboard-check', 'fa-file-alt', 'fa-cubes', 'fa-tags', 'fa-cube',
        'fa-weight-hanging', 'fa-industry', 'fa-tasks', 'fa-calendar-alt',
        'fa-clipboard-list', 'fa-project-diagram', 'fa-cheese', 'fa-barcode',
        'fa-cogs', 'fa-temperature-high', 'fa-user-clock', 'fa-check-circle',
        'fa-box', 'fa-chart-bar', 'fa-shopping-cart', 'fa-file-invoice',
        'fa-file-invoice-dollar', 'fa-users', 'fa-user-tie', 'fa-route',
        'fa-map-marker-alt', 'fa-chart-line', 'fa-undo', 'fa-history',
        'fa-truck', 'fa-address-book', 'fa-shopping-cart', 'fa-dolly-flatbed',
        'fa-exchange-alt', 'fa-user-shield', 'fa-user-tag', 'fa-ticket-alt',
        'fa-robot', 'fa-cogs', 'fa-sliders-h', 'fa-palette', 'fa-key',
        'fa-database', 'fa-user-lock', 'fa-lightbulb', 'fa-money-bill-wave',
        'fa-wallet', 'fa-exchange-alt', 'fa-random', 'fa-balance-scale',
        'fa-truck-loading', 'fa-shipping-fast', 'fa-map-marked-alt', 'fa-circle'
    ]
    
    return render_template('settings/sidebar.html', icons=icons)

@settings_bp.route('/api/sidebar-items', methods=['GET'])
@login_required
def api_get_sidebar_items():
    """API endpoint to get all sidebar items"""
    if not current_user.role or current_user.role.name != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
        
    try:
        items = SidebarItem.query.all()
        return jsonify([item.to_dict() for item in items])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@settings_bp.route('/api/sidebar-items', methods=['POST'])
@login_required
def api_add_sidebar_item():
    """API endpoint to add a new sidebar item"""
    if not current_user.role or current_user.role.name != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
        
    try:
        data = request.json
        
        # Create new sidebar item
        item = SidebarItem(
            title=data.get('title'),
            icon=data.get('icon'),
            url=data.get('url', ''),
            order=data.get('order', 0),
            parent_id=data.get('parent_id'),
            is_dropdown=data.get('is_dropdown', False),
            admin_only=data.get('admin_only', False),
            is_active=data.get('is_active', True)
        )
        
        db.session.add(item)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'تمت إضافة عنصر القائمة بنجاح',
            'item': item.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@settings_bp.route('/api/sidebar-items/<int:item_id>', methods=['PUT'])
@login_required
def api_update_sidebar_item(item_id):
    """API endpoint to update a sidebar item"""
    if not current_user.role or current_user.role.name != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
        
    try:
        item = SidebarItem.query.get(item_id)
        if not item:
            return jsonify({'error': 'Item not found'}), 404
            
        data = request.json
        
        # Update item fields
        item.title = data.get('title', item.title)
        item.icon = data.get('icon', item.icon)
        item.url = data.get('url', item.url)
        item.order = data.get('order', item.order)
        item.parent_id = data.get('parent_id')
        item.is_dropdown = data.get('is_dropdown', item.is_dropdown)
        item.admin_only = data.get('admin_only', item.admin_only)
        item.is_active = data.get('is_active', item.is_active)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'تم تحديث عنصر القائمة بنجاح',
            'item': item.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@settings_bp.route('/api/sidebar-items/<int:item_id>', methods=['DELETE'])
@login_required
def api_delete_sidebar_item(item_id):
    """API endpoint to delete a sidebar item"""
    if not current_user.role or current_user.role.name != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
        
    try:
        item = SidebarItem.query.get(item_id)
        if not item:
            return jsonify({'error': 'Item not found'}), 404
            
        # Check if this is a parent item with children
        children = SidebarItem.query.filter_by(parent_id=item_id).all()
        if children:
            # Either delete children or update them
            for child in children:
                db.session.delete(child)
        
        db.session.delete(item)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'تم حذف عنصر القائمة بنجاح'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@settings_bp.route('/api/sidebar-items/reorder', methods=['POST'])
@login_required
def api_reorder_sidebar_items():
    """API endpoint to reorder sidebar items"""
    if not current_user.role or current_user.role.name != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
        
    try:
        data = request.json
        items = data.get('items', [])
        
        for item_data in items:
            item = SidebarItem.query.get(item_data.get('id'))
            if item:
                item.order = item_data.get('order')
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'تم إعادة ترتيب عناصر القائمة بنجاح'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

from models_helper import SidebarItem

# Add this new route to the settings_routes.py file
@settings_bp.route('/api/sidebar-items/reset', methods=['POST'])
@login_required
def api_reset_sidebar_items():
    """API endpoint to reset sidebar items to default"""
    if not current_user.role or current_user.role.name != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        # Delete all existing sidebar items
        SidebarItem.query.delete()
        db.session.commit()
        
        # Create default menu items
        SidebarItem.get_default_menu()
        
        return jsonify({
            'success': True,
            'message': 'تم إعادة تعيين القائمة الجانبية بنجاح'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@settings_bp.route('/api/sidebar-items/<int:item_id>/move', methods=['POST'])
@login_required
def api_move_sidebar_item(item_id):
    """API endpoint to move a sidebar item up or down in order"""
    if not current_user.role or current_user.role.name != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        item = SidebarItem.query.get(item_id)
        if not item:
            return jsonify({'error': 'العنصر غير موجود'}), 404
        
        data = request.json
        direction = data.get('direction', 'up')
        
        # Get the appropriate sibling items
        if item.parent_id:
            siblings = SidebarItem.query.filter_by(parent_id=item.parent_id).order_by(SidebarItem.order).all()
        else:
            siblings = SidebarItem.query.filter_by(parent_id=None).order_by(SidebarItem.order).all()
        
        # Find the current item's index
        current_index = next((i for i, sibling in enumerate(siblings) if sibling.id == item_id), None)
        if current_index is None:
            return jsonify({'error': 'خطأ في ترتيب العناصر'}), 500
        
        # Calculate the target index
        if direction == 'up' and current_index > 0:
            target_index = current_index - 1
        elif direction == 'down' and current_index < len(siblings) - 1:
            target_index = current_index + 1
        else:
            return jsonify({'error': 'لا يمكن نقل العنصر في هذا الاتجاه'}), 400
        
        # Swap orders with the target item
        target_item = siblings[target_index]
        temp_order = item.order
        item.order = target_item.order
        target_item.order = temp_order
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'تم نقل العنصر بنجاح'
        })
    except Exception as e:
        db.session.rollback()
        # Log the error for debugging
        print(f"Error in move_sidebar_item: {str(e)}")
        return jsonify({'error': str(e)}), 500

@settings_bp.route('/api/settings/suggested-routes')
@login_required
def get_suggested_routes():
    """API endpoint to get suggested routes for the sidebar"""
    if not current_user.role or current_user.role.name != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        # Get all registered routes from the application
        all_routes = []
        for rule in current_app.url_map.iter_rules():
            # Skip static, debug, and API routes
            if (str(rule).startswith('/static/') or 
                str(rule).startswith('/_debug_toolbar/') or 
                str(rule).startswith('/api/') or
                str(rule).startswith('/_') or
                'login' in str(rule) or
                'logout' in str(rule) or
                'register' in str(rule)):
                continue

            # Get route name from endpoint
            endpoint = rule.endpoint
            route_name = endpoint.split('.')[-1]  # Get the last part after the dot
            route_name = route_name.replace('_', ' ').title()

            # Get the blueprint name if exists
            blueprint = None
            if '.' in endpoint:
                blueprint = endpoint.split('.')[0].replace('_', ' ').title()

            route_info = {
                'path': str(rule),
                'name': route_name,
                'blueprint': blueprint,
                'methods': list(rule.methods - {'HEAD', 'OPTIONS'}),
                'is_page': 'GET' in rule.methods and not str(rule).startswith('/api/')
            }
            all_routes.append(route_info)

        # Get all sidebar items
        sidebar_items = SidebarItem.query.all()
        sidebar_urls = {item.url for item in sidebar_items if item.url}

        # Find unused routes (routes that exist but are not in the sidebar)
        unused_routes = [
            route for route in all_routes
            if route['path'] not in sidebar_urls and
            route['is_page'] and  # Only include page routes
            not any(route['path'].startswith(prefix) for prefix in ['/static/', '/api/', '/_', '/login', '/logout', '/register'])
        ]

        # Group unused routes by blueprint
        grouped_unused_routes = {}
        for route in unused_routes:
            blueprint = route['blueprint'] or 'Other'
            if blueprint not in grouped_unused_routes:
                grouped_unused_routes[blueprint] = []
            grouped_unused_routes[blueprint].append(route)

        # Find missing routes (routes that are in the sidebar but don't exist)
        missing_routes = []
        for url in sidebar_urls:
            if not any(route['path'] == url for route in all_routes):
                # Try to find a similar route
                similar_routes = [
                    route for route in all_routes
                    if url.split('/')[-1] in route['path'] or
                    route['path'].split('/')[-1] in url
                ]
                
                if similar_routes:
                    # Use the most similar route's information
                    most_similar = similar_routes[0]
                    missing_routes.append({
                        'path': url,
                        'name': most_similar['name'],
                        'blueprint': most_similar['blueprint'],
                        'methods': most_similar['methods'],
                        'suggested_path': most_similar['path']
                    })
                else:
                    missing_routes.append({
                        'path': url,
                        'name': 'Missing Route',
                        'blueprint': 'Unknown',
                        'methods': [],
                        'suggested_path': None
                    })

        return jsonify({
            'unused_routes': grouped_unused_routes,
            'missing_routes': missing_routes
        })

    except Exception as e:
        print(f"Error in get_suggested_routes: {str(e)}")  # Add logging
        return jsonify({'error': str(e)}), 500


