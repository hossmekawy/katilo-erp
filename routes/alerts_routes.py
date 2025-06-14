from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from utils.alerts_manager import alerts_manager
import json

# Create blueprint
alerts_bp = Blueprint('alerts', __name__, url_prefix='/alerts')

@alerts_bp.route('/')
@login_required
def alerts_page():
    """Main alerts page"""
    return render_template('alerts.html')

@alerts_bp.route('/api/alerts', methods=['GET'])
@login_required
def get_alerts():
    """API endpoint to get all alerts"""
    try:
        # Get query parameters
        limit = request.args.get('limit', type=int)
        alert_type = request.args.get('type')
        
        # Get alerts
        alerts = alerts_manager.get_all_alerts(limit=limit, alert_type=alert_type)
        
        return jsonify({
            'success': True,
            'alerts': alerts,
            'total_count': len(alerts),
            'unread_count': alerts_manager.get_unread_count(alert_type)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@alerts_bp.route('/api/alerts', methods=['POST'])
def add_alert():
    """External API endpoint to add new alerts (accessible without login)"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        title = data.get('title')
        if not title:
            return jsonify({
                'success': False,
                'error': 'Title is required'
            }), 400
        
        alert_type = data.get('type', 'general')
        metadata = data.get('metadata', {})
        
        # Add the alert
        alert_id = alerts_manager.add_alert(title, alert_type, metadata)
        
        return jsonify({
            'success': True,
            'alert_id': alert_id,
            'message': 'Alert added successfully'
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@alerts_bp.route('/api/alerts/<alert_id>', methods=['GET'])
@login_required
def get_alert(alert_id):
    """Get a specific alert by ID"""
    try:
        alert = alerts_manager.get_alert_by_id(alert_id)
        
        if not alert:
            return jsonify({
                'success': False,
                'error': 'Alert not found'
            }), 404
        
        return jsonify({
            'success': True,
            'alert': alert
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@alerts_bp.route('/api/alerts/<alert_id>/read', methods=['PUT'])
@login_required
def mark_alert_read(alert_id):
    """Mark an alert as read"""
    try:
        success = alerts_manager.mark_alert_as_read(alert_id)
        
        if not success:
            return jsonify({
                'success': False,
                'error': 'Alert not found'
            }), 404
        
        return jsonify({
            'success': True,
            'message': 'Alert marked as read'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@alerts_bp.route('/api/alerts/<alert_id>', methods=['DELETE'])
@login_required
def delete_alert(alert_id):
    """Delete an alert"""
    try:
        success = alerts_manager.delete_alert(alert_id)
        
        if not success:
            return jsonify({
                'success': False,
                'error': 'Alert not found'
            }), 404
        
        return jsonify({
            'success': True,
            'message': 'Alert deleted successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@alerts_bp.route('/api/alerts/unread-count', methods=['GET'])
@login_required
def get_unread_count():
    """Get count of unread alerts"""
    try:
        alert_type = request.args.get('type')
        count = alerts_manager.get_unread_count(alert_type)
        
        return jsonify({
            'success': True,
            'unread_count': count
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@alerts_bp.route('/api/alerts/mark-all-read', methods=['PUT'])
@login_required
def mark_all_read():
    """Mark all alerts as read"""
    try:
        alert_type = request.args.get('type')
        marked_count = alerts_manager.mark_all_as_read(alert_type)
        
        return jsonify({
            'success': True,
            'marked_count': marked_count,
            'message': f'Marked {marked_count} alerts as read'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@alerts_bp.route('/api/alerts/cleanup', methods=['DELETE'])
@login_required
def cleanup_old_alerts():
    """Clean up old alerts (admin only)"""
    try:
        # Check if user is admin
        if not current_user.role or current_user.role.name != 'admin':
            return jsonify({
                'success': False,
                'error': 'Unauthorized - Admin access required'
            }), 403
        
        days_old = request.args.get('days', default=30, type=int)
        removed_count = alerts_manager.cleanup_old_alerts(days_old)
        
        return jsonify({
            'success': True,
            'removed_count': removed_count,
            'message': f'Removed {removed_count} old alerts'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@alerts_bp.route('/api/alerts/stats', methods=['GET'])
@login_required
def get_alert_stats():
    """Get alert statistics"""
    try:
        all_alerts = alerts_manager.get_all_alerts()
        
        # Calculate statistics
        total_count = len(all_alerts)
        unread_count = sum(1 for alert in all_alerts if not alert.get('read', False))
        
        # Count by type
        type_counts = {}
        for alert in all_alerts:
            alert_type = alert.get('type', 'general')
            type_counts[alert_type] = type_counts.get(alert_type, 0) + 1
        
        # Recent alerts (last 24 hours)
        from datetime import datetime, timedelta
        yesterday = datetime.now() - timedelta(days=1)
        recent_count = 0
        
        for alert in all_alerts:
            try:
                alert_time = datetime.fromisoformat(alert.get('time', ''))
                if alert_time > yesterday:
                    recent_count += 1
            except (ValueError, TypeError):
                pass
        
        return jsonify({
            'success': True,
            'stats': {
                'total_count': total_count,
                'unread_count': unread_count,
                'read_count': total_count - unread_count,
                'recent_count': recent_count,
                'type_counts': type_counts
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
