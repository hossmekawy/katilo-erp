from flask import Blueprint, request, jsonify, current_app, render_template, send_file
from flask_login import current_user, login_required
from models import db, User
from werkzeug.utils import secure_filename
import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import io
import qrcode
from io import BytesIO

profile_bp = Blueprint('profile', __name__)

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@profile_bp.route('/api/auth/profile')
@login_required
def get_profile():
    # Format dates for JSON response
    birthdate = None
    if current_user.birthdate:
        birthdate = current_user.birthdate.isoformat()
        
    hire_date = None
    if current_user.hire_date:
        hire_date = current_user.hire_date.isoformat()
    
    return jsonify({
        'id': current_user.id,
        'username': current_user.username,
        'email': current_user.email,
        'role': current_user.role.name if current_user.role else 'user',
        'phone': current_user.phone,
        'department': current_user.department,
        'position': current_user.position,
        'identification_number': current_user.identification_number,
        'gender': current_user.gender,
        'nationality': current_user.nationality,
        'birthdate': birthdate,
        'hire_date': hire_date,
        'address': current_user.address,
        'profile_image': current_user.profile_image,
        'emergency_contact': current_user.emergency_contact
    })

@profile_bp.route('/api/auth/profile', methods=['PUT'])
@login_required
def update_profile():
    data = request.get_json()
    
    # Update user fields
    if 'phone' in data:
        current_user.phone = data['phone']
    if 'department' in data:
        current_user.department = data['department']
    if 'position' in data:
        current_user.position = data['position']
    if 'identification_number' in data:
        current_user.identification_number = data['identification_number']
    if 'gender' in data:
        current_user.gender = data['gender']
    if 'nationality' in data:
        current_user.nationality = data['nationality']
    if 'address' in data:
        current_user.address = data['address']
    
    # Handle date fields
    if 'birthdate' in data and data['birthdate']:
        try:
            current_user.birthdate = datetime.strptime(data['birthdate'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'message': 'صيغة تاريخ الميلاد غير صحيحة'}), 400
    
    if 'hire_date' in data and data['hire_date']:
        try:
            current_user.hire_date = datetime.strptime(data['hire_date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'message': 'صيغة تاريخ التوظيف غير صحيحة'}), 400
    
    # Handle emergency contact
    if 'emergency_contact' in data:
        current_user.emergency_contact = {
            'name': data['emergency_contact'].get('name', ''),
            'phone': data['emergency_contact'].get('phone', ''),
            'relation': data['emergency_contact'].get('relation', '')
        }
    
    # Handle password change if provided
    if 'password' in data and data['password']:
        current_user.set_password(data['password'])
    
    db.session.commit()
    
    # Format dates for JSON response
    birthdate = None
    if current_user.birthdate:
        birthdate = current_user.birthdate.isoformat()
        
    hire_date = None
    if current_user.hire_date:
        hire_date = current_user.hire_date.isoformat()
    
    return jsonify({
        'id': current_user.id,
        'username': current_user.username,
        'email': current_user.email,
        'role': current_user.role.name if current_user.role else 'user',
        'phone': current_user.phone,
        'department': current_user.department,
        'position': current_user.position,
        'identification_number': current_user.identification_number,
        'gender': current_user.gender,
        'nationality': current_user.nationality,
        'birthdate': birthdate,
        'hire_date': hire_date,
        'address': current_user.address,
        'profile_image': current_user.profile_image,
        'emergency_contact': current_user.emergency_contact
    })

@profile_bp.route('/api/auth/profile/image', methods=['POST'])
@login_required
def upload_profile_image():
    if 'profile_image' not in request.files:
        return jsonify({'message': 'لم يتم تحديد ملف'}), 400
    
    file = request.files['profile_image']
    
    if file.filename == '':
        return jsonify({'message': 'لم يتم اختيار ملف'}), 400
    
    if file and allowed_file(file.filename):
        # Create a unique filename
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{timestamp}_{current_user.id}_{filename}"
        
        # Get upload folder from app config
        upload_folder = current_app.config.get('PROFILE_UPLOAD_FOLDER', 'static/uploads/profiles')
        
        # Ensure directory exists
        os.makedirs(upload_folder, exist_ok=True)
        
        # Save the file
        file_path = os.path.join(upload_folder, unique_filename)
        file.save(file_path)
        
        # Update user's profile image
        relative_path = f"/static/uploads/profiles/{unique_filename}"
        current_user.profile_image = relative_path
        db.session.commit()
        
        return jsonify({'profile_image': relative_path})
    
    return jsonify({'message': 'نوع الملف غير مدعوم'}), 400

@profile_bp.route('/api/auth/business-card')
@login_required
def generate_business_card():
    try:
        # Create a business card image (1000x600 pixels)
        card_width = 1000
        card_height = 600
        card = Image.new('RGB', (card_width, card_height), color=(255, 255, 255))
        draw = ImageDraw.Draw(card)
        
        # Find an Arabic font
        arabic_fonts = [
            "static/fonts/NotoSansArabic-Regular.ttf",
            "static/fonts/NotoKufiArabic-Regular.ttf",
            "static/fonts/Tajawal-Medium.ttf",
            "static/fonts/Amiri-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/Arial Unicode.ttf",
            "C:\\Windows\\Fonts\\arial.ttf",
        ]
        
        # Try to find a suitable font
        name_font = None
        title_font = None
        details_font = None
        
        for font_path in arabic_fonts:
            try:
                if os.path.exists(font_path):
                    name_font = ImageFont.truetype(font_path, 48)
                    title_font = ImageFont.truetype(font_path, 32)
                    details_font = ImageFont.truetype(font_path, 24)
                    break
            except Exception:
                continue
        
        # If no suitable font found, use default
        if name_font is None:
            name_font = ImageFont.load_default()
            title_font = ImageFont.load_default()
            details_font = ImageFont.load_default()
        
        # Create a modern gradient background
        # Use a more elegant gradient from dark blue to light blue
        for y in range(card_height):
            r = int(20 + (y / card_height) * 50)
            g = int(40 + (y / card_height) * 80)
            b = int(90 + (y / card_height) * 100)
            for x in range(card_width):
                draw.point((x, y), fill=(r, g, b))
        
        # Add decorative elements
        # Add a curved design element on the right side
        for i in range(300):
            x = int(card_width * 0.8 + i * 0.5)
            y = int((card_height / 2) - 150 + i)
            if 0 <= x < card_width and 0 <= y < card_height:
                draw.point((x, y), fill=(255, 255, 255, 50))
        
        # Add a subtle pattern to the left side
        for i in range(0, card_width // 2, 20):
            for j in range(0, card_height, 20):
                draw.rectangle([(i, j), (i+2, j+2)], fill=(255, 255, 255, 30))
        
        # Add company logo if available
        try:
            logo_path = os.path.join(current_app.root_path, 'static/img/logo.png')
            if os.path.exists(logo_path):
                logo = Image.open(logo_path)
                logo = logo.resize((150, 150))
                card.paste(logo, (50, 50), logo if 'A' in logo.getbands() else None)
        except Exception as e:
            print(f"Error loading logo: {e}")
        
        # Add profile image if available
        if current_user.profile_image:
            try:
                profile_img_path = os.path.join(current_app.root_path, current_user.profile_image.lstrip('/'))
                if os.path.exists(profile_img_path):
                    profile_img = Image.open(profile_img_path)
                    profile_img = profile_img.resize((150, 150))
                    
                    # Create circular mask for profile image
                    mask = Image.new('L', (150, 150), 0)
                    mask_draw = ImageDraw.Draw(mask)
                    mask_draw.ellipse((0, 0, 150, 150), fill=255)
                    
                    # Apply circular mask
                    output = Image.new('RGBA', (150, 150), (0, 0, 0, 0))
                    output.paste(profile_img, (0, 0), mask)
                    
                    # Paste the circular profile image
                    card.paste(output, (card_width - 200, 50), output)
            except Exception as e:
                print(f"Error processing profile image: {e}")
        
        # Add user information with right-to-left support for Arabic
        # Name - right aligned for Arabic
        name = current_user.username or "الاسم"
        try:
            name_width = name_font.getlength(name)
        except AttributeError:
            # For older Pillow versions
            name_width = draw.textlength(name, font=name_font)
        
        draw.text((card_width - 50 - name_width, 220), name, fill=(255, 255, 255), font=name_font)
        
        # Position and Department - right aligned for Arabic
        position_text = current_user.position or "المنصب"
        department_text = current_user.department or ""
        if department_text:
            position_text += f" - {department_text}"
        
        try:
            position_width = title_font.getlength(position_text)
        except AttributeError:
            position_width = draw.textlength(position_text, font=title_font)
        
        draw.text((card_width - 50 - position_width, 280), position_text, fill=(255, 255, 255), font=title_font)
        
        # Contact information - right aligned for Arabic
        y_position = 350
        if current_user.email:
            email_text = f" email: {current_user.email}"
            try:
                email_width = details_font.getlength(email_text)
            except AttributeError:
                email_width = draw.textlength(email_text, font=details_font)
            
            draw.text((card_width - 50 - email_width, y_position), email_text, fill=(255, 255, 255), font=details_font)
            y_position += 40
        
        if current_user.phone:
            phone_text = f"phone: {current_user.phone}"
            try:
                phone_width = details_font.getlength(phone_text)
            except AttributeError:
                phone_width = draw.textlength(phone_text, font=details_font)
            
            draw.text((card_width - 50 - phone_width, y_position), phone_text, fill=(255, 255, 255), font=details_font)
            y_position += 40
        
        if current_user.address:
            address_text = f"address: {current_user.address}"
            try:
                address_width = details_font.getlength(address_text)
            except AttributeError:
                address_width = draw.textlength(address_text, font=details_font)
            
            draw.text((card_width - 50 - address_width, y_position), address_text, fill=(255, 255, 255), font=details_font)
        
        # Generate QR code with contact information
        qr_data = f"BEGIN:VCARD\nVERSION:3.0\nN:{current_user.username}\nTEL:{current_user.phone or ''}\nEMAIL:{current_user.email}\nTITLE:{current_user.position or ''}\nORG:{current_user.department or ''}\nEND:VCARD"
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=5,
            border=4,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        qr_img = qr_img.resize((150, 150))
        
        # Paste QR code
        card.paste(qr_img, (50, card_height - 200))
        
        # Add decorative elements
        draw.line([(30, 210), (card_width - 30, 210)], fill=(255, 255, 255), width=2)
        
                # Add a label for the QR code in Arabic
        qr_label = " "
        try:
            qr_label_width = details_font.getlength(qr_label)
        except AttributeError:
            qr_label_width = draw.textlength(qr_label, font=details_font)
        
        draw.text((50 + (150 - qr_label_width) // 2, card_height - 220), qr_label, fill=(255, 255, 255), font=details_font)
        
        # Add company name or system name at the bottom
        company_name = "katilo"
        try:
            company_name_width = details_font.getlength(company_name)
        except AttributeError:
            company_name_width = draw.textlength(company_name, font=details_font)
        
        draw.text((card_width // 2 - company_name_width // 2, card_height - 50), company_name, fill=(255, 255, 255), font=details_font)
        
        # Save to BytesIO
        img_io = BytesIO()
        card.save(img_io, 'PNG')
        img_io.seek(0)
        
        # Return the image
        return send_file(img_io, mimetype='image/png', 
                         download_name=f'business_card_{current_user.username}.png',
                         as_attachment=True)
    
    except Exception as e:
        print(f"Error generating business card: {e}")
        return jsonify({'message': 'حدث خطأ أثناء إنشاء بطاقة العمل'}), 500

@profile_bp.route('/user-profile')
@login_required
def profile_page():
    return render_template('profile.html')

