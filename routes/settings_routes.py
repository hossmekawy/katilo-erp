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
        # Get database path
        db_path = get_database_path()

        if not db_path:
            return jsonify({
                'error': 'Database file not found. Please check your configuration.'
            }), 404

        # Create a copy of the database
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"katilo_backup_{timestamp}.db"

        # Create a temporary file
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, backup_filename)

        # Copy the database to the temporary file
        shutil.copy2(db_path, temp_path)

        # Send the file
        return send_file(
            temp_path,
            as_attachment=True,
            download_name=backup_filename,
            mimetype='application/octet-stream'
        )

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

        if not file.filename.endswith('.db'):
            return jsonify({'error': 'File must be a SQLite database (.db)'}), 400

        # Save the uploaded file to a temporary location
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, secure_filename(file.filename))
        file.save(temp_path)

        # Verify it's a valid SQLite database
        try:
            conn = sqlite3.connect(temp_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            conn.close()

            # Check if it has the expected tables
            table_names = [table[0] for table in tables]
            required_tables = ['users', 'roles', 'permissions', 'system_settings']

            for table in required_tables:
                if table not in table_names:
                    return jsonify({'error': f'Invalid database: missing {table} table'}), 400

        except sqlite3.Error:
            return jsonify({'error': 'Invalid SQLite database file'}), 400

        # Get database path
        db_path = get_database_path()

        if not db_path:
            return jsonify({
                'error': 'Database file not found. Please check your configuration.'
            }), 404

        # Create a backup of the current database
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = f"{db_path}.backup_{timestamp}"
        shutil.copy2(db_path, backup_path)

        # Replace the current database with the uploaded one
        shutil.copy2(temp_path, db_path)

        # Clean up
        os.remove(temp_path)

        return jsonify({
            'success': True,
            'message': 'Database imported successfully. Please restart the application for changes to take effect.',
            'backup_path': backup_path
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
