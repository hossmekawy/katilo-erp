# Katilo ERP Alerts System

## Overview

The Katilo ERP Alerts System is a comprehensive notification system that tracks important events across the ERP system, including money transfers, inventory movements, and low stock alerts. The system stores alerts in JSON format and provides both web interface and REST API access.

## Features

### 1. Alert Types
- **Money Transfers**: Notifications for cash transfers between accounts
- **Inventory Movements**: Alerts for product movements between warehouses
- **Low Stock**: Warnings when inventory levels fall below minimum thresholds
- **General**: Custom alerts for system events

### 2. Web Interface
- **Alerts Page**: `/alerts` - Main dashboard with tab-based navigation
- **Real-time Updates**: Auto-refresh every 30 seconds
- **Statistics Dashboard**: Overview of alert counts and types
- **Mark as Read/Delete**: Individual alert management
- **Bulk Actions**: Mark all alerts as read

### 3. REST API
- **External API**: Add alerts from external systems
- **Internal API**: Full CRUD operations for authenticated users
- **Statistics**: Get alert counts and analytics
- **Filtering**: Filter alerts by type and status

### 4. UI Integration
- **Notification Bell**: Header notification with unread count badge
- **Sidebar Menu**: Direct access to alerts page
- **Responsive Design**: Works on desktop and mobile devices

## Installation & Setup

### 1. Files Added/Modified

**New Files:**
- `routes/alerts_routes.py` - Main alerts blueprint
- `templates/alerts.html` - Alerts page template
- `utils/alerts_manager.py` - Alert management utility
- `data/alerts.json` - JSON storage file
- `test_alerts.py` - Test script

**Modified Files:**
- `app.py` - Added blueprint registration and context processors
- `templates/base.html` - Added notification button and JavaScript
- `models.py` - Added alerts menu item to sidebar
- `routes/cash_management_routes.py` - Added money transfer alerts

### 2. Dependencies
No additional Python packages required. Uses existing Flask infrastructure.

### 3. Database Changes
No database changes required. Alerts are stored in JSON format.

## Usage

### Web Interface

1. **Access Alerts Page**
   ```
   Navigate to: http://localhost:5005/alerts
   ```

2. **View Notifications**
   - Click the bell icon in the header
   - Badge shows unread count
   - Click to navigate to alerts page

3. **Tab Navigation**
   - **All Alerts**: View all notifications
   - **Money Transfers**: Filter by transfer alerts
   - **Inventory Movements**: Filter by movement alerts
   - **Low Stock**: Filter by stock alerts

### REST API

#### 1. Add Alert (External API)
```bash
POST /alerts/api/alerts
Content-Type: application/json

{
  "title": "Alert message in Arabic",
  "type": "money_transfer|inventory_movement|low_stock|general",
  "metadata": {
    "key": "value"
  }
}
```

**Example:**
```bash
curl -X POST http://localhost:5005/alerts/api/alerts \
  -H "Content-Type: application/json" \
  -d '{
    "title": "تحويل نقدي من الخزينة إلى البنك بمبلغ 5000",
    "type": "money_transfer",
    "metadata": {
      "from_account": "الخزينة الرئيسية",
      "to_account": "البنك",
      "amount": 5000
    }
  }'
```

#### 2. Get Alerts (Requires Authentication)
```bash
GET /alerts/api/alerts?type=money_transfer&limit=10
```

#### 3. Mark Alert as Read
```bash
PUT /alerts/api/alerts/{alert_id}/read
```

#### 4. Delete Alert
```bash
DELETE /alerts/api/alerts/{alert_id}
```

#### 5. Get Statistics
```bash
GET /alerts/api/alerts/stats
```

#### 6. Get Unread Count
```bash
GET /alerts/api/alerts/unread-count
```

### Programmatic Usage

#### Add Alerts from Code
```python
from utils.alerts_manager import add_money_transfer_alert, add_inventory_movement_alert, add_low_stock_alert

# Money transfer alert
add_money_transfer_alert("الخزينة الرئيسية", "البنك", 10000.0, "TV-001")

# Inventory movement alert
add_inventory_movement_alert("أرز بسمتي", "المستودع الرئيسي", "مستودع الفرع", 50)

# Low stock alert
add_low_stock_alert("زيت الزيتون", 5, 10, "المستودع الرئيسي")
```

#### Direct Alert Manager Usage
```python
from utils.alerts_manager import alerts_manager

# Add custom alert
alert_id = alerts_manager.add_alert(
    title="Custom alert message",
    alert_type="general",
    metadata={"custom_field": "value"}
)

# Get all alerts
alerts = alerts_manager.get_all_alerts(limit=10)

# Get unread count
unread_count = alerts_manager.get_unread_count()
```

## Alert Triggers

### Automatic Triggers

1. **Money Transfers**
   - Triggered in: `routes/cash_management_routes.py`
   - When: Cash transfer vouchers are created
   - Data: From/to accounts, amount, voucher number

2. **Inventory Movements**
   - Triggered in: `app.py` (inventory transaction function)
   - When: Items are transferred between warehouses
   - Data: Item name, warehouses, quantity

3. **Low Stock Alerts**
   - Triggered in: `app.py` (inventory transaction function)
   - When: Inventory quantity falls to/below reorder level
   - Data: Item name, current quantity, minimum allowed, warehouse

### Manual Triggers

Use the external API or programmatic functions to create custom alerts.

## Testing

### Run Test Script
```bash
python test_alerts.py
```

This script will:
- Add sample alerts of each type
- Test API endpoints
- Display results and statistics

### Manual Testing

1. **Create Money Transfer**
   - Go to Cash Management → Transfers
   - Create a new transfer
   - Check alerts page for notification

2. **Create Inventory Movement**
   - Perform inventory transactions
   - Check for movement and low stock alerts

3. **External API Test**
   - Use curl or Postman to send POST requests
   - Verify alerts appear in the web interface

## Configuration

### Alert Storage Location
Default: `data/alerts.json`

To change location, modify `AlertsManager` initialization:
```python
alerts_manager = AlertsManager("custom/path/alerts.json")
```

### Auto-refresh Interval
Default: 30 seconds

To change, modify JavaScript in `templates/alerts.html`:
```javascript
// Change 30000 to desired milliseconds
setInterval(() => {
    this.loadAlerts();
    this.loadStats();
}, 30000);
```

### Alert Cleanup
Automatically remove alerts older than 30 days:
```python
removed_count = alerts_manager.cleanup_old_alerts(days_old=30)
```

## Troubleshooting

### Common Issues

1. **Alerts not appearing**
   - Check if `data/alerts.json` exists and is writable
   - Verify Flask app has proper permissions
   - Check browser console for JavaScript errors

2. **External API not working**
   - Ensure Flask app is running on correct port
   - Check firewall settings
   - Verify JSON format in requests

3. **Notification badge not updating**
   - Check browser console for errors
   - Verify authentication status
   - Clear browser cache

### Debug Mode

Enable debug logging in `utils/alerts_manager.py`:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Security Considerations

1. **External API**: No authentication required for adding alerts
2. **Internal API**: Requires user authentication
3. **Admin Functions**: Cleanup requires admin role
4. **File Permissions**: Ensure proper access to `data/alerts.json`

## Future Enhancements

1. **Email Notifications**: Send alerts via email
2. **Push Notifications**: Browser push notifications
3. **Alert Rules**: Configurable alert conditions
4. **Alert Templates**: Predefined alert formats
5. **Integration**: Connect with external monitoring systems

## Support

For issues or questions about the alerts system:
1. Check this documentation
2. Run the test script to verify functionality
3. Check application logs for errors
4. Review the code in `utils/alerts_manager.py` and `routes/alerts_routes.py`
