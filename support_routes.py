from flask import Blueprint, request, jsonify, render_template, abort, current_app
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename
from models import db, SupportTicket, TicketResponse, Document
import os
from datetime import datetime
from flask import Blueprint, request, jsonify, render_template, abort, current_app, session, url_for, redirect, flash
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename
from models import db, SupportTicket, TicketResponse, Document
import os
from datetime import datetime

# Create a Blueprint for support routes
support_bp = Blueprint('support', __name__)

# Helper function for file uploads
def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx', 'txt'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Contact Support Routes


@support_bp.route('/contact-support')
def contact_support():
    if not current_user.is_authenticated:
        # Store the intended destination in the session
        session['next'] = request.url
        # Flash a message to inform the user
        flash('يرجى تسجيل الدخول أولاً لإرسال تذكرة دعم', 'warning')
        # Redirect to login page
        return redirect(url_for('login_page'))
    return render_template('contact_support.html')

@support_bp.route('/api/support-tickets', methods=['POST'])
@login_required
def create_support_ticket():
    data = request.form
    
    # Create new support ticket
    ticket = SupportTicket(
        user_id=current_user.id,
        subject=data['subject'],
        message=data['message'],
        ticket_type=data.get('ticket_type', 'general'),
        priority=data.get('priority', 'medium')
    )
    
    db.session.add(ticket)
    db.session.commit()
    
    # Handle file attachment if present
    if 'attachment' in request.files:
        file = request.files['attachment']
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
            upload_folder = current_app.config['UPLOAD_FOLDER']
            file_path = os.path.join(upload_folder, filename)
            file.save(file_path)
            
            # Create a document record for the attachment
            document = Document(
                title=f"Attachment for Ticket #{ticket.id}",
                file_path=f"/static/uploads/support/{filename}",
                category="Other",
                uploaded_by=current_user.id
            )
            db.session.add(document)
            db.session.commit()
    
    return jsonify({
        'id': ticket.id,
        'subject': ticket.subject,
        'status': ticket.status,
        'created_at': ticket.created_at.isoformat()
    }), 201

@support_bp.route('/my-tickets')
@login_required
def my_tickets():
    return render_template('my_tickets.html')

@support_bp.route('/api/my-tickets', methods=['GET'])
@login_required
def get_my_tickets():
    tickets = SupportTicket.query.filter_by(user_id=current_user.id).order_by(SupportTicket.created_at.desc()).all()
    return jsonify([{
        'id': t.id,
        'subject': t.subject,
        'message': t.message,
        'ticket_type': t.ticket_type,
        'status': t.status,
        'priority': t.priority,
        'created_at': t.created_at.isoformat(),
        'updated_at': t.updated_at.isoformat(),
        'responses_count': len(t.responses)
    } for t in tickets])

@support_bp.route('/ticket/<int:id>')
@login_required
def view_ticket(id):
    ticket = SupportTicket.query.get_or_404(id)
    
    # Ensure user can only view their own tickets (unless admin)
    if ticket.user_id != current_user.id and (not current_user.role or current_user.role.name != 'admin'):
        abort(403)
        
    return render_template('ticket_detail.html', ticket_id=id)

@support_bp.route('/api/tickets/<int:id>', methods=['GET'])
@login_required
def get_ticket(id):
    ticket = SupportTicket.query.get_or_404(id)
    
    # Ensure user can only access their own tickets (unless admin)
    if ticket.user_id != current_user.id and (not current_user.role or current_user.role.name != 'admin'):
        return jsonify({'message': 'Unauthorized'}), 403
    
    responses = [{
        'id': r.id,
        'message': r.message,
        'is_staff_response': r.is_staff_response,
        'created_at': r.created_at.isoformat(),
        'user': {
            'id': r.user.id,
            'username': r.user.username,
            'profile_image': r.user.profile_image
        } if r.user else None
    } for r in ticket.responses]
    
    return jsonify({
        'id': ticket.id,
        'subject': ticket.subject,
        'message': ticket.message,
        'ticket_type': ticket.ticket_type,
        'status': ticket.status,
        'priority': ticket.priority,
        'created_at': ticket.created_at.isoformat(),
        'updated_at': ticket.updated_at.isoformat(),
        'user': {
            'id': ticket.user.id,
            'username': ticket.user.username,
            'profile_image': ticket.user.profile_image
        } if ticket.user else None,
        'responses': responses
    })

@support_bp.route('/api/tickets/<int:id>/respond', methods=['POST'])
@login_required
def respond_to_ticket(id):
    ticket = SupportTicket.query.get_or_404(id)
    
    # Ensure user can only respond to their own tickets (unless admin)
    if ticket.user_id != current_user.id and (not current_user.role or current_user.role.name != 'admin'):
        return jsonify({'message': 'Unauthorized'}), 403
    
    data = request.get_json()
    
    # Create new response
    response = TicketResponse(
        ticket_id=ticket.id,
        user_id=current_user.id,
        message=data['message'],
        is_staff_response=current_user.role and current_user.role.name == 'admin'
    )
    
    # Update ticket status if admin is responding
    if current_user.role and current_user.role.name == 'admin':
        if data.get('update_status'):
            ticket.status = data.get('status', ticket.status)
    
    # Update the ticket's updated_at timestamp
    ticket.updated_at = datetime.utcnow()
    
    db.session.add(response)
    db.session.commit()
    
    return jsonify({
        'id': response.id,
        'message': response.message,
        'is_staff_response': response.is_staff_response,
        'created_at': response.created_at.isoformat(),
        'user': {
            'id': current_user.id,
            'username': current_user.username,
            'profile_image': current_user.profile_image
        }
    }), 201

# Admin Support Management
@support_bp.route('/admin/support-tickets')
@login_required
def admin_support_tickets():
    if not current_user.role or current_user.role.name != 'admin':
        abort(403)
    return render_template('admin_support_tickets.html')

@support_bp.route('/api/admin/support-tickets', methods=['GET'])
@login_required
def get_all_tickets():
    if not current_user.role or current_user.role.name != 'admin':
        return jsonify({'message': 'Unauthorized'}), 403
    
    status_filter = request.args.get('status')
    
    query = SupportTicket.query
    
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    tickets = query.order_by(SupportTicket.created_at.desc()).all()
    
    return jsonify([{
        'id': t.id,
        'subject': t.subject,
        'ticket_type': t.ticket_type,
        'status': t.status,
        'priority': t.priority,
        'created_at': t.created_at.isoformat(),
        'updated_at': t.updated_at.isoformat(),
        'user': {
            'id': t.user.id,
            'username': t.user.username
        } if t.user else None,
        'responses_count': len(t.responses)
    } for t in tickets])

@support_bp.route('/api/admin/support-tickets/<int:id>', methods=['PUT'])
@login_required
def update_ticket_status(id):
    if not current_user.role or current_user.role.name != 'admin':
        return jsonify({'message': 'Unauthorized'}), 403
    
    ticket = SupportTicket.query.get_or_404(id)
    data = request.get_json()
    
    if 'status' in data:
        ticket.status = data['status']
    
    if 'priority' in data:
        ticket.priority = data['priority']
    
    ticket.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        'id': ticket.id,
        'status': ticket.status,
        'priority': ticket.priority,
        'updated_at': ticket.updated_at.isoformat()
    })
