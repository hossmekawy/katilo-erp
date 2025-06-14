import json
import os
import uuid
from datetime import datetime
from typing import List, Dict, Optional

class AlertsManager:
    """Manager class for handling alerts stored in JSON file"""
    
    def __init__(self, alerts_file_path: str = "data/alerts.json"):
        self.alerts_file_path = alerts_file_path
        self._ensure_data_directory()
        self._ensure_alerts_file()
    
    def _ensure_data_directory(self):
        """Ensure the data directory exists"""
        data_dir = os.path.dirname(self.alerts_file_path)
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
    
    def _ensure_alerts_file(self):
        """Ensure the alerts JSON file exists with proper structure"""
        if not os.path.exists(self.alerts_file_path):
            initial_data = {"alerts": []}
            with open(self.alerts_file_path, 'w', encoding='utf-8') as f:
                json.dump(initial_data, f, ensure_ascii=False, indent=2)
    
    def _load_alerts(self) -> Dict:
        """Load alerts from JSON file"""
        try:
            with open(self.alerts_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # If file doesn't exist or is corrupted, return empty structure
            return {"alerts": []}
    
    def _save_alerts(self, data: Dict):
        """Save alerts to JSON file"""
        with open(self.alerts_file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def add_alert(self, title: str, alert_type: str = "general", metadata: Optional[Dict] = None) -> str:
        """
        Add a new alert
        
        Args:
            title: Alert title/message
            alert_type: Type of alert (money_transfer, inventory_movement, low_stock, general)
            metadata: Additional metadata for the alert
            
        Returns:
            str: The auto-generated alert ID
        """
        data = self._load_alerts()
        
        alert_id = str(uuid.uuid4())
        new_alert = {
            "autoid": alert_id,
            "title": title,
            "time": datetime.now().isoformat(),
            "type": alert_type,
            "read": False,
            "metadata": metadata or {}
        }
        
        data["alerts"].append(new_alert)
        self._save_alerts(data)
        
        return alert_id
    
    def get_all_alerts(self, limit: Optional[int] = None, alert_type: Optional[str] = None) -> List[Dict]:
        """
        Get all alerts, optionally filtered by type and limited
        
        Args:
            limit: Maximum number of alerts to return
            alert_type: Filter by alert type
            
        Returns:
            List of alert dictionaries
        """
        data = self._load_alerts()
        alerts = data.get("alerts", [])
        
        # Filter by type if specified
        if alert_type:
            alerts = [alert for alert in alerts if alert.get("type") == alert_type]
        
        # Sort by time (newest first)
        alerts.sort(key=lambda x: x.get("time", ""), reverse=True)
        
        # Apply limit if specified
        if limit:
            alerts = alerts[:limit]
        
        return alerts
    
    def get_alert_by_id(self, alert_id: str) -> Optional[Dict]:
        """Get a specific alert by ID"""
        data = self._load_alerts()
        alerts = data.get("alerts", [])
        
        for alert in alerts:
            if alert.get("autoid") == alert_id:
                return alert
        
        return None
    
    def mark_alert_as_read(self, alert_id: str) -> bool:
        """
        Mark an alert as read
        
        Returns:
            bool: True if alert was found and marked, False otherwise
        """
        data = self._load_alerts()
        alerts = data.get("alerts", [])
        
        for alert in alerts:
            if alert.get("autoid") == alert_id:
                alert["read"] = True
                self._save_alerts(data)
                return True
        
        return False
    
    def delete_alert(self, alert_id: str) -> bool:
        """
        Delete an alert
        
        Returns:
            bool: True if alert was found and deleted, False otherwise
        """
        data = self._load_alerts()
        alerts = data.get("alerts", [])
        
        original_count = len(alerts)
        data["alerts"] = [alert for alert in alerts if alert.get("autoid") != alert_id]
        
        if len(data["alerts"]) < original_count:
            self._save_alerts(data)
            return True
        
        return False
    
    def get_unread_count(self, alert_type: Optional[str] = None) -> int:
        """
        Get count of unread alerts
        
        Args:
            alert_type: Filter by alert type
            
        Returns:
            int: Number of unread alerts
        """
        data = self._load_alerts()
        alerts = data.get("alerts", [])
        
        # Filter by type if specified
        if alert_type:
            alerts = [alert for alert in alerts if alert.get("type") == alert_type]
        
        # Count unread alerts
        unread_count = sum(1 for alert in alerts if not alert.get("read", False))
        
        return unread_count
    
    def mark_all_as_read(self, alert_type: Optional[str] = None) -> int:
        """
        Mark all alerts as read, optionally filtered by type
        
        Args:
            alert_type: Filter by alert type
            
        Returns:
            int: Number of alerts marked as read
        """
        data = self._load_alerts()
        alerts = data.get("alerts", [])
        
        marked_count = 0
        for alert in alerts:
            # Check if we should mark this alert
            should_mark = True
            if alert_type and alert.get("type") != alert_type:
                should_mark = False
            
            if should_mark and not alert.get("read", False):
                alert["read"] = True
                marked_count += 1
        
        if marked_count > 0:
            self._save_alerts(data)
        
        return marked_count
    
    def cleanup_old_alerts(self, days_old: int = 30) -> int:
        """
        Remove alerts older than specified days
        
        Args:
            days_old: Number of days after which to remove alerts
            
        Returns:
            int: Number of alerts removed
        """
        from datetime import timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days_old)
        data = self._load_alerts()
        alerts = data.get("alerts", [])
        
        original_count = len(alerts)
        
        # Keep alerts that are newer than cutoff date
        data["alerts"] = []
        for alert in alerts:
            try:
                alert_time = datetime.fromisoformat(alert.get("time", ""))
                if alert_time > cutoff_date:
                    data["alerts"].append(alert)
            except (ValueError, TypeError):
                # Keep alerts with invalid timestamps
                data["alerts"].append(alert)
        
        removed_count = original_count - len(data["alerts"])
        
        if removed_count > 0:
            self._save_alerts(data)
        
        return removed_count

# Global instance
alerts_manager = AlertsManager()

# Helper functions for common alert types
def add_money_transfer_alert(from_account: str, to_account: str, amount: float, voucher_number: str = None):
    """Add alert for money transfer between accounts"""
    title = f"تحويل نقدي من {from_account} إلى {to_account} بمبلغ {amount:,.2f}"
    metadata = {
        "from_account": from_account,
        "to_account": to_account,
        "amount": amount,
        "voucher_number": voucher_number
    }
    return alerts_manager.add_alert(title, "money_transfer", metadata)

def add_inventory_movement_alert(item_name: str, from_warehouse: str, to_warehouse: str, quantity: int):
    """Add alert for inventory movement between warehouses"""
    title = f"نقل مخزون: {item_name} من {from_warehouse} إلى {to_warehouse} بكمية {quantity}"
    metadata = {
        "item_name": item_name,
        "from_warehouse": from_warehouse,
        "to_warehouse": to_warehouse,
        "quantity": quantity
    }
    return alerts_manager.add_alert(title, "inventory_movement", metadata)

def add_low_stock_alert(item_name: str, current_quantity: int, minimum_allowed: int, warehouse_name: str):
    """Add alert for low stock levels"""
    title = f"مخزون منخفض: {item_name} في {warehouse_name} (الكمية الحالية: {current_quantity}, المسموح: {minimum_allowed})"
    metadata = {
        "item_name": item_name,
        "current_quantity": current_quantity,
        "minimum_allowed": minimum_allowed,
        "warehouse_name": warehouse_name
    }
    return alerts_manager.add_alert(title, "low_stock", metadata)
