# Katilo ERP System - API Documentation

## Table of Contents
1. [API Overview](#api-overview)
2. [Authentication](#authentication)
3. [Inventory API](#inventory-api)
4. [Production API](#production-api)
5. [Sales API](#sales-api)
6. [AI Services API](#ai-services-api)
7. [Reports API](#reports-api)
8. [Error Handling](#error-handling)

---

## 1. API Overview

### 1.1 Base Information

**Base URL:** `https://your-domain.com/api`
**API Version:** v1
**Content Type:** `application/json`
**Authentication:** Session-based with CSRF protection

### 1.2 HTTP Methods

- `GET`: Retrieve data
- `POST`: Create new resources
- `PUT`: Update existing resources
- `DELETE`: Remove resources
- `PATCH`: Partial updates

### 1.3 Response Format

**Success Response:**
```json
{
    "success": true,
    "data": {
        // Response data
    },
    "message": "Operation completed successfully",
    "timestamp": "2024-01-15T10:30:00Z"
}
```

**Error Response:**
```json
{
    "success": false,
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Invalid input data",
        "details": {
            "field": "item_name",
            "issue": "Field is required"
        }
    },
    "timestamp": "2024-01-15T10:30:00Z"
}
```

---

## 2. Authentication

### 2.1 Session Authentication

**Login Endpoint:**
```http
POST /auth/login
Content-Type: application/json

{
    "username": "user@example.com",
    "password": "secure_password"
}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "user_id": 123,
        "username": "user@example.com",
        "role": "manager",
        "permissions": ["view_inventory", "create_orders"],
        "session_token": "abc123xyz"
    }
}
```

**Logout Endpoint:**
```http
POST /auth/logout
```

### 2.2 CSRF Protection

**CSRF Token Header:**
```http
X-CSRFToken: csrf_token_value
```

**Get CSRF Token:**
```http
GET /auth/csrf-token
```

---

## 3. Inventory API

### 3.1 Items Management

**Get All Items:**
```http
GET /inventory/items
```

**Query Parameters:**
- `page`: Page number (default: 1)
- `per_page`: Items per page (default: 20)
- `category_id`: Filter by category
- `search`: Search term
- `sort_by`: Sort field (name, sku, cost)
- `sort_order`: asc or desc

**Response:**
```json
{
    "success": true,
    "data": {
        "items": [
            {
                "id": 1,
                "name": "Product A",
                "sku": "PROD-001",
                "category_id": 1,
                "category_name": "Electronics",
                "cost": 100.00,
                "price": 150.00,
                "reorder_level": 10,
                "current_stock": 25,
                "created_at": "2024-01-01T00:00:00Z"
            }
        ],
        "pagination": {
            "page": 1,
            "per_page": 20,
            "total": 100,
            "pages": 5
        }
    }
}
```

**Get Single Item:**
```http
GET /inventory/items/{item_id}
```

**Create Item:**
```http
POST /inventory/items
Content-Type: application/json

{
    "name": "New Product",
    "sku": "PROD-002",
    "category_id": 1,
    "description": "Product description",
    "unit_of_measure": "pcs",
    "cost": 80.00,
    "price": 120.00,
    "reorder_level": 15
}
```

**Update Item:**
```http
PUT /inventory/items/{item_id}
Content-Type: application/json

{
    "name": "Updated Product Name",
    "cost": 85.00,
    "price": 125.00
}
```

**Delete Item:**
```http
DELETE /inventory/items/{item_id}
```

### 3.2 Inventory Levels

**Get Inventory by Warehouse:**
```http
GET /inventory/levels
```

**Query Parameters:**
- `warehouse_id`: Filter by warehouse
- `item_id`: Filter by item
- `low_stock`: Show only low stock items (true/false)

**Update Inventory:**
```http
POST /inventory/transactions
Content-Type: application/json

{
    "item_id": 1,
    "warehouse_id": 1,
    "transaction_type": "IN",
    "quantity": 50,
    "reference": "PO-001"
}
```

### 3.3 Categories

**Get Categories:**
```http
GET /inventory/categories
```

**Create Category:**
```http
POST /inventory/categories
Content-Type: application/json

{
    "name": "New Category",
    "description": "Category description",
    "category_type": "RawMaterial"
}
```

---

## 4. Production API

### 4.1 Bill of Materials (BOM)

**Get BOMs:**
```http
GET /production/bom
```

**Create BOM:**
```http
POST /production/bom
Content-Type: application/json

{
    "final_product_id": 1,
    "description": "BOM for Product A",
    "components": [
        {
            "component_item_id": 2,
            "quantity_required": 2.5,
            "unit_of_measure": "kg"
        },
        {
            "component_item_id": 3,
            "quantity_required": 1,
            "unit_of_measure": "pcs"
        }
    ]
}
```

### 4.2 Production Orders

**Get Production Orders:**
```http
GET /production/orders
```

**Query Parameters:**
- `status`: Filter by status (Planned, In Progress, Completed)
- `production_line_id`: Filter by production line
- `date_from`: Start date filter
- `date_to`: End date filter

**Create Production Order:**
```http
POST /production/orders
Content-Type: application/json

{
    "item_id": 1,
    "quantity": 100,
    "production_line_id": 1,
    "scheduled_start": "2024-01-20T08:00:00Z",
    "scheduled_end": "2024-01-20T16:00:00Z",
    "priority": "High"
}
```

**Update Production Order Status:**
```http
PATCH /production/orders/{order_id}/status
Content-Type: application/json

{
    "status": "In Progress",
    "notes": "Production started"
}
```

### 4.3 Quality Control

**Get Quality Checks:**
```http
GET /production/quality-checks
```

**Create Quality Check:**
```http
POST /production/quality-checks
Content-Type: application/json

{
    "production_order_id": 1,
    "batch_id": 1,
    "inspector_id": 5,
    "test_parameters": [
        {
            "parameter_name": "Weight",
            "expected_value": 100,
            "actual_value": 98,
            "tolerance": 5,
            "unit": "grams"
        }
    ]
}
```

---

## 5. Sales API

### 5.1 Customers

**Get Customers:**
```http
GET /sales/customers
```

**Create Customer:**
```http
POST /sales/customers
Content-Type: application/json

{
    "customer_name": "ABC Company",
    "contact_info": "contact@abc.com",
    "billing_address": "123 Main St, City",
    "shipping_address": "456 Oak Ave, City",
    "credit_limit": 10000.00,
    "payment_terms": "Net 30"
}
```

### 5.2 Sales Orders

**Get Sales Orders:**
```http
GET /sales/orders
```

**Create Sales Order:**
```http
POST /sales/orders
Content-Type: application/json

{
    "customer_id": 1,
    "order_date": "2024-01-15T00:00:00Z",
    "items": [
        {
            "item_id": 1,
            "quantity": 10,
            "unit_price": 150.00
        },
        {
            "item_id": 2,
            "quantity": 5,
            "unit_price": 200.00
        }
    ],
    "payment_method": "credit_card",
    "shipping_address": "789 Pine St, City"
}
```

**Update Order Status:**
```http
PATCH /sales/orders/{order_id}/status
Content-Type: application/json

{
    "status": "Shipped",
    "tracking_number": "TRK123456789"
}
```

### 5.3 Invoices

**Generate Invoice:**
```http
POST /sales/orders/{order_id}/invoice
Content-Type: application/json

{
    "invoice_date": "2024-01-15T00:00:00Z",
    "due_date": "2024-02-14T00:00:00Z",
    "payment_terms": "Net 30"
}
```

**Get Invoice PDF:**
```http
GET /sales/invoices/{invoice_id}/pdf
```

---

## 6. AI Services API

### 6.1 Chatbot

**Send Message to Chatbot:**
```http
POST /api/chatbot/ask
Content-Type: application/json

{
    "query": "What's the current stock level of Product A?",
    "chat_id": "chat_123",
    "image_data": "base64_encoded_image_data"
}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "response": "Product A currently has 25 units in stock across all warehouses.",
        "chat_id": "chat_123",
        "context_used": ["inventory_data", "warehouse_data"]
    }
}
```

**Get Chat Sessions:**
```http
GET /api/chatbot/sessions
```

**Create New Chat Session:**
```http
POST /api/chatbot/sessions
Content-Type: application/json

{
    "title": "Inventory Discussion"
}
```

### 6.2 AI Suggestions

**Get AI Suggestions:**
```http
GET /api/ai-suggestions
```

**Query Parameters:**
- `status`: Filter by status (Pending, Approved, Rejected)
- `suggestion_type`: Filter by type
- `item_id`: Filter by item

**Trigger AI Analysis:**
```http
POST /api/ai-suggestions/analyze
Content-Type: application/json

{
    "item_id": 1,
    "category_id": null
}
```

**Update Suggestion Status:**
```http
PATCH /api/ai-suggestions/{suggestion_id}
Content-Type: application/json

{
    "status": "Approved",
    "notes": "Good suggestion, implementing change"
}
```

### 6.3 Predictive Analytics

**Get Demand Forecast:**
```http
GET /api/analytics/demand-forecast
```

**Query Parameters:**
- `item_id`: Item to forecast
- `period`: Forecast period (days, weeks, months)
- `horizon`: Forecast horizon (30, 60, 90 days)

**Response:**
```json
{
    "success": true,
    "data": {
        "item_id": 1,
        "forecast_period": "30_days",
        "predictions": [
            {
                "date": "2024-01-16",
                "predicted_demand": 15,
                "confidence": 0.85
            }
        ],
        "accuracy_metrics": {
            "mape": 12.5,
            "rmse": 3.2
        }
    }
}
```

---

## 7. Reports API

### 7.1 Standard Reports

**Get Available Reports:**
```http
GET /api/reports/types
```

**Generate Report:**
```http
POST /api/reports/generate
Content-Type: application/json

{
    "report_type": "inventory_levels",
    "parameters": {
        "warehouse_id": 1,
        "date_from": "2024-01-01",
        "date_to": "2024-01-31",
        "format": "PDF"
    }
}
```

**Get Report Status:**
```http
GET /api/reports/{report_id}/status
```

**Download Report:**
```http
GET /api/reports/{report_id}/download
```

### 7.2 Custom Reports

**Create Custom Report:**
```http
POST /api/reports/custom
Content-Type: application/json

{
    "name": "Custom Inventory Report",
    "data_sources": ["items", "inventory", "categories"],
    "fields": ["item_name", "category_name", "quantity", "value"],
    "filters": {
        "category_id": 1,
        "warehouse_id": [1, 2]
    },
    "grouping": ["category_name"],
    "sorting": [{"field": "item_name", "order": "asc"}]
}
```

---

## 8. Error Handling

### 8.1 HTTP Status Codes

- `200 OK`: Successful request
- `201 Created`: Resource created successfully
- `400 Bad Request`: Invalid request data
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `422 Unprocessable Entity`: Validation errors
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

### 8.2 Error Response Format

**Validation Error:**
```json
{
    "success": false,
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Validation failed",
        "details": {
            "item_name": ["This field is required"],
            "cost": ["Must be a positive number"]
        }
    }
}
```

**Authentication Error:**
```json
{
    "success": false,
    "error": {
        "code": "AUTHENTICATION_REQUIRED",
        "message": "Please log in to access this resource"
    }
}
```

**Rate Limit Error:**
```json
{
    "success": false,
    "error": {
        "code": "RATE_LIMIT_EXCEEDED",
        "message": "Too many requests. Please try again later.",
        "retry_after": 60
    }
}
```

### 8.3 Error Codes

**Common Error Codes:**
- `VALIDATION_ERROR`: Input validation failed
- `AUTHENTICATION_REQUIRED`: User not authenticated
- `PERMISSION_DENIED`: Insufficient permissions
- `RESOURCE_NOT_FOUND`: Requested resource doesn't exist
- `DUPLICATE_RESOURCE`: Resource already exists
- `BUSINESS_RULE_VIOLATION`: Business logic constraint violated
- `EXTERNAL_SERVICE_ERROR`: Third-party service error
- `RATE_LIMIT_EXCEEDED`: API rate limit exceeded

### 8.4 Best Practices

**Error Handling Guidelines:**
1. Always check the `success` field in responses
2. Handle different HTTP status codes appropriately
3. Display user-friendly error messages
4. Log detailed error information for debugging
5. Implement retry logic for transient errors
6. Respect rate limits and implement backoff strategies

**Example Error Handling (JavaScript):**
```javascript
async function apiRequest(url, options) {
    try {
        const response = await fetch(url, options);
        const data = await response.json();
        
        if (!data.success) {
            throw new Error(data.error.message);
        }
        
        return data.data;
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}
```

---

## Rate Limiting

### 8.5 Rate Limits

**Default Limits:**
- General API: 1000 requests per hour
- AI Services: 60 requests per minute
- Report Generation: 10 requests per hour
- File Uploads: 100 requests per hour

**Rate Limit Headers:**
```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1642248000
```

---

This API documentation provides comprehensive information for integrating with the Katilo ERP system. For additional endpoints or custom integrations, please refer to the system's OpenAPI specification or contact the development team.
