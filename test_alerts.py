#!/usr/bin/env python3
"""
Test script for the Katilo ERP Alerts System
This script tests the alerts functionality by creating sample alerts
"""

import requests
import json
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:5005"
ALERTS_API_URL = f"{BASE_URL}/alerts/api/alerts"

def test_external_api():
    """Test the external API for adding alerts"""
    print("Testing External Alerts API...")
    
    # Test data for different alert types
    test_alerts = [
        {
            "title": "تحويل نقدي من الخزينة الرئيسية إلى البنك بمبلغ 10,000.00",
            "type": "money_transfer",
            "metadata": {
                "from_account": "الخزينة الرئيسية",
                "to_account": "البنك",
                "amount": 10000.00,
                "voucher_number": "TV-001"
            }
        },
        {
            "title": "نقل مخزون: أرز بسمتي من المستودع الرئيسي إلى مستودع الفرع بكمية 50",
            "type": "inventory_movement",
            "metadata": {
                "item_name": "أرز بسمتي",
                "from_warehouse": "المستودع الرئيسي",
                "to_warehouse": "مستودع الفرع",
                "quantity": 50
            }
        },
        {
            "title": "مخزون منخفض: زيت الزيتون في المستودع الرئيسي (الكمية الحالية: 5, المسموح: 10)",
            "type": "low_stock",
            "metadata": {
                "item_name": "زيت الزيتون",
                "current_quantity": 5,
                "minimum_allowed": 10,
                "warehouse_name": "المستودع الرئيسي"
            }
        },
        {
            "title": "تنبيه عام: تم تحديث النظام بنجاح",
            "type": "general",
            "metadata": {
                "update_version": "1.2.3",
                "update_time": datetime.now().isoformat()
            }
        }
    ]
    
    # Add test alerts
    for i, alert_data in enumerate(test_alerts, 1):
        try:
            print(f"\n{i}. Adding alert: {alert_data['type']}")
            response = requests.post(ALERTS_API_URL, json=alert_data, timeout=10)
            
            if response.status_code == 201:
                result = response.json()
                print(f"   ✓ Success: Alert ID {result.get('alert_id')}")
            else:
                print(f"   ✗ Failed: {response.status_code} - {response.text}")
                
        except requests.exceptions.RequestException as e:
            print(f"   ✗ Connection Error: {e}")
    
    print("\n" + "="*50)

def test_alerts_retrieval():
    """Test retrieving alerts"""
    print("Testing Alerts Retrieval...")
    
    try:
        # Note: This requires authentication, so it might fail if not logged in
        response = requests.get(ALERTS_API_URL, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                alerts = result.get('alerts', [])
                print(f"✓ Retrieved {len(alerts)} alerts")
                
                # Show first few alerts
                for i, alert in enumerate(alerts[:3], 1):
                    print(f"   {i}. {alert.get('title', 'No title')[:50]}...")
                    print(f"      Type: {alert.get('type', 'unknown')}")
                    print(f"      Read: {'Yes' if alert.get('read') else 'No'}")
                    print(f"      Time: {alert.get('time', 'unknown')}")
                    print()
            else:
                print(f"✗ API Error: {result.get('error', 'Unknown error')}")
        else:
            print(f"✗ HTTP Error: {response.status_code}")
            if response.status_code == 401:
                print("   (This is expected if not authenticated)")
                
    except requests.exceptions.RequestException as e:
        print(f"✗ Connection Error: {e}")

def test_alerts_stats():
    """Test alerts statistics endpoint"""
    print("\nTesting Alerts Statistics...")
    
    try:
        stats_url = f"{BASE_URL}/alerts/api/alerts/stats"
        response = requests.get(stats_url, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                stats = result.get('stats', {})
                print("✓ Statistics retrieved:")
                print(f"   Total alerts: {stats.get('total_count', 0)}")
                print(f"   Unread alerts: {stats.get('unread_count', 0)}")
                print(f"   Recent alerts (24h): {stats.get('recent_count', 0)}")
                
                type_counts = stats.get('type_counts', {})
                if type_counts:
                    print("   Alerts by type:")
                    for alert_type, count in type_counts.items():
                        print(f"     - {alert_type}: {count}")
            else:
                print(f"✗ API Error: {result.get('error', 'Unknown error')}")
        else:
            print(f"✗ HTTP Error: {response.status_code}")
            if response.status_code == 401:
                print("   (This is expected if not authenticated)")
                
    except requests.exceptions.RequestException as e:
        print(f"✗ Connection Error: {e}")

def test_unread_count():
    """Test unread alerts count endpoint"""
    print("\nTesting Unread Count...")
    
    try:
        unread_url = f"{BASE_URL}/alerts/api/alerts/unread-count"
        response = requests.get(unread_url, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                count = result.get('unread_count', 0)
                print(f"✓ Unread alerts count: {count}")
            else:
                print(f"✗ API Error: {result.get('error', 'Unknown error')}")
        else:
            print(f"✗ HTTP Error: {response.status_code}")
            if response.status_code == 401:
                print("   (This is expected if not authenticated)")
                
    except requests.exceptions.RequestException as e:
        print(f"✗ Connection Error: {e}")

def main():
    """Main test function"""
    print("Katilo ERP Alerts System Test")
    print("="*50)
    
    # Test external API (should work without authentication)
    test_external_api()
    
    # Test other endpoints (require authentication)
    test_alerts_retrieval()
    test_alerts_stats()
    test_unread_count()
    
    print("\n" + "="*50)
    print("Test completed!")
    print("\nTo view the alerts in the web interface:")
    print(f"1. Open your browser and go to {BASE_URL}")
    print("2. Log in to the system")
    print("3. Click on the alerts bell icon in the header")
    print("4. Or navigate directly to /alerts")

if __name__ == "__main__":
    main()
