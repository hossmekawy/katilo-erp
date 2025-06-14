# Katilo ERP System - Comprehensive Documentation
## Graduation Project Documentation

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Key Features](#key-features)
4. [Technical Implementation](#technical-implementation)
5. [AI Integration](#ai-integration)
6. [PDF Generation System](#pdf-generation-system)
7. [Data Flow](#data-flow)
8. [User Interface](#user-interface)
9. [Installation and Deployment](#installation-and-deployment)
10. [Future Enhancements](#future-enhancements)

---

## 1. System Overview

### 1.1 Introduction

The Katilo ERP (Enterprise Resource Planning) System is a comprehensive business management solution designed to streamline operations across multiple departments including inventory management, production, quality control, sales, purchasing, and distribution. Built with modern web technologies, the system provides real-time data processing, intelligent automation, and advanced reporting capabilities.

### 1.2 Purpose and Objectives

**Primary Objectives:**
- Centralize business operations in a unified platform
- Automate routine tasks and reduce manual errors
- Provide real-time visibility into business processes
- Enable data-driven decision making through advanced analytics
- Integrate AI capabilities for intelligent suggestions and automation
- Support scalable growth and multi-location operations

**Target Users:**
- Manufacturing companies
- Distribution centers
- Retail businesses
- Small to medium enterprises (SMEs)
- Multi-location businesses

### 1.3 Core Functionality

The system encompasses the following core areas:

**Inventory Management:**
- Real-time stock tracking across multiple warehouses
- Automated reorder level monitoring
- Batch and lot tracking
- Warehouse layout management with sections and slots
- Item weight and volume management

**Production Management:**
- Bill of Materials (BOM) management
- Production order planning and execution
- Quality control and testing
- Packaging operations
- Production efficiency tracking

**Sales and Customer Management:**
- Customer relationship management
- Sales order processing
- Invoice generation and payment tracking
- Sales representative management
- Return and refund processing

**Purchasing and Supplier Management:**
- Supplier relationship management
- Purchase order automation
- Supplier performance tracking
- Payment management and ledger tracking

**Financial Management:**
- Cash account management
- Transaction tracking
- Financial reporting
- Multi-currency support

**Distribution and Logistics:**
- Vehicle management
- Route optimization
- Shipment tracking
- Delivery confirmation

---

## 2. Architecture

### 2.1 System Architecture Overview

The Katilo ERP system follows a modern web application architecture with the following components:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend       │    │   Database      │
│   (HTML/JS/CSS) │◄──►│   (Flask/Python)│◄──►│   (PostgreSQL)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   AI Services   │
                       │   (Gemini API)  │
                       └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   PDF Engine    │
                       │   (wkhtmltopdf) │
                       └─────────────────┘
```

### 2.2 Technology Stack

**Backend Framework:**
- **Flask**: Python web framework for rapid development
- **SQLAlchemy**: Object-Relational Mapping (ORM) for database operations
- **Flask-Login**: User session management
- **Flask-Migrate**: Database migration management

**Database:**
- **PostgreSQL**: Primary relational database
- **Advanced features**: JSONB support, full-text search, indexing

**Frontend Technologies:**
- **HTML5/CSS3**: Modern web standards
- **JavaScript (ES6+)**: Client-side functionality
- **Bootstrap**: Responsive UI framework
- **Vue.js**: Progressive JavaScript framework for dynamic components

**AI Integration:**
- **Google Gemini API**: Advanced language model for intelligent features
- **Custom AI modules**: Inventory analysis and suggestions

**PDF Generation:**
- **wkhtmltopdf**: High-quality PDF generation from HTML
- **Custom templates**: Branded report templates

**Development Tools:**
- **Waitress**: Production WSGI server
- **Python Virtual Environment**: Dependency isolation
- **Git**: Version control system

### 2.3 Database Schema

The system uses a comprehensive relational database schema with the following key entities:

**Core Entities:**
- Categories, Items, Warehouses
- Inventory, InventoryTransactions
- Users, Roles, Permissions

**Manufacturing:**
- BOM (Bill of Materials), BOMDetails
- ProductionOrders, ProductionLines
- QualityChecks, QCParameters

**Sales & Purchasing:**
- Customers, SalesOrders, SalesOrderDetails
- Suppliers, PurchaseOrders, PurchaseOrderDetails
- Invoices, Payments

**Advanced Features:**
- AISuggestions, DemandForecasts
- EmployeeShifts, ProductionEfficiency
- SupportTickets, DocumentManagement

---

## 3. Key Features

### 3.1 Inventory Management Module

**Real-time Stock Tracking:**
- Multi-warehouse inventory management
- Automatic stock level updates
- Low stock alerts and notifications
- Inventory transaction history

**Warehouse Layout Management:**
- Visual warehouse mapping
- Section and slot-based organization
- Optimized picking routes
- Space utilization analytics

**Advanced Inventory Features:**
- Batch and lot tracking
- Expiration date management
- Item weight and volume tracking
- Barcode and QR code support

### 3.2 Production Management Module

**Bill of Materials (BOM):**
- Multi-level BOM support
- Component requirement calculation
- Cost analysis and optimization
- Version control and change tracking

**Production Planning:**
- Production order scheduling
- Resource allocation
- Capacity planning
- Production line management

**Quality Control:**
- Quality inspection workflows
- Test parameter management
- Pass/fail criteria
- Quality reports and certificates

### 3.3 Sales Management Module

**Customer Relationship Management:**
- Customer profile management
- Sales history tracking
- Credit limit management
- Customer interaction logs

**Order Processing:**
- Sales order creation and management
- Automated inventory allocation
- Order fulfillment tracking
- Invoice generation

**Sales Analytics:**
- Sales performance dashboards
- Revenue analysis
- Customer segmentation
- Sales forecasting

### 3.4 AI-Powered Features

**Intelligent Inventory Management:**
- Automated reorder level suggestions
- Demand forecasting
- Inventory optimization recommendations
- Anomaly detection

**Smart Chatbot Assistant:**
- Natural language query processing
- Real-time data access
- Multi-language support (Arabic/English)
- Image recognition capabilities

**Predictive Analytics:**
- Sales trend analysis
- Production efficiency optimization
- Quality prediction models
- Supplier performance analysis

---

## 4. Technical Implementation

### 4.1 Backend Implementation

The backend is built using Flask, a lightweight Python web framework that provides flexibility and scalability:

**Application Structure:**
```
app.py                 # Main application entry point
models.py             # Database models and relationships
routes/               # Modular route handlers
├── inventory_routes.py
├── production_routes.py
├── sales_routes.py
├── ai_suggestions_routes.py
└── chatbot_routes.py
utils/                # Utility modules
├── pdf_generator.py
├── ai_suggestions.py
└── database_seeder.py
```

**Key Implementation Features:**
- Modular blueprint architecture for scalability
- Comprehensive error handling and logging
- Database connection pooling
- Session management and security
- API rate limiting and caching

### 4.2 Database Design

The database follows normalized design principles with optimized indexing:

**Performance Optimizations:**
- Strategic indexing on frequently queried columns
- Database connection pooling
- Query optimization and caching
- Batch processing for large operations

**Data Integrity:**
- Foreign key constraints
- Check constraints for data validation
- Transaction management
- Audit trails for critical operations

### 4.3 Security Implementation

**Authentication and Authorization:**
- Role-based access control (RBAC)
- Session-based authentication
- Password hashing using Werkzeug
- Permission-based feature access

**Data Security:**
- SQL injection prevention through ORM
- XSS protection
- CSRF token validation
- Secure session management

---

## 5. AI Integration

### 5.1 Google Gemini Integration

The system integrates Google's Gemini AI model for advanced intelligent features:

**Chatbot Implementation:**
```python
# Gemini AI Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")
```

**Key AI Features:**
- Natural language processing for user queries
- Context-aware responses based on system data
- Image recognition and analysis
- Multi-language support (Arabic and English)

### 5.2 AI-Powered Inventory Suggestions

**Intelligent Analysis:**
- Automated inventory anomaly detection
- Reorder level optimization
- Category mismatch identification
- Name improvement suggestions

**Implementation Process:**
1. Data collection from inventory tables
2. AI analysis using Gemini model
3. Suggestion generation and storage
4. User notification and approval workflow

### 5.3 Predictive Analytics

**Demand Forecasting:**
- Historical sales data analysis
- Seasonal trend identification
- Market demand prediction
- Inventory planning optimization

**Production Optimization:**
- Efficiency analysis
- Resource allocation suggestions
- Quality prediction models
- Maintenance scheduling

---

## 6. PDF Generation System

### 6.1 wkhtmltopdf Integration

The system uses wkhtmltopdf for high-quality PDF generation:

**Configuration:**
```python
wkhtmltopdf_path = 'pdftool/wkhtmltopdf/bin/wkhtmltopdf.exe'
options = {
    'page-size': 'A4',
    'margin-top': '10mm',
    'margin-right': '10mm',
    'margin-bottom': '10mm',
    'margin-left': '10mm',
    'encoding': 'UTF-8',
    'enable-local-file-access': None
}
```

### 6.2 Report Templates

**Available Report Types:**
- Inventory reports
- Production reports
- Quality control certificates
- Sales invoices
- Purchase orders
- Financial statements

**Template Features:**
- Responsive design for multiple page sizes
- Company branding integration
- Multi-language support
- Dynamic data binding
- Professional formatting

### 6.3 PDF Generation Workflow

1. **Template Selection**: Choose appropriate template
2. **Data Preparation**: Gather and format data
3. **HTML Rendering**: Generate HTML from template
4. **PDF Conversion**: Convert HTML to PDF using wkhtmltopdf
5. **Delivery**: Serve PDF to user or save to storage

---

## 7. Data Flow

### 7.1 Inventory Data Flow

```mermaid
graph TD
    A[Item Creation] --> B[Inventory Entry]
    B --> C[Transaction Recording]
    C --> D[Stock Level Update]
    D --> E[Reorder Alert Check]
    E --> F[AI Analysis]
    F --> G[Suggestion Generation]
```

### 7.2 Production Data Flow

```mermaid
graph TD
    A[Production Order] --> B[BOM Validation]
    B --> C[Material Allocation]
    C --> D[Production Execution]
    D --> E[Quality Control]
    E --> F[Packaging]
    F --> G[Inventory Update]
```

### 7.3 Sales Data Flow

```mermaid
graph TD
    A[Customer Order] --> B[Inventory Check]
    B --> C[Order Confirmation]
    C --> D[Picking List]
    D --> E[Shipment]
    E --> F[Invoice Generation]
    F --> G[Payment Processing]
```

---

## 8. User Interface

### 8.1 Dashboard Design

The main dashboard provides a comprehensive overview of business operations:

**Key Metrics Display:**
- Real-time inventory levels
- Production status
- Sales performance
- Financial summaries
- AI-generated insights

**Interactive Elements:**
- Dynamic charts and graphs
- Quick action buttons
- Search and filter capabilities
- Responsive design for mobile devices

### 8.2 Module-Specific Interfaces

**Inventory Management Interface:**
- Grid-based item listing
- Advanced search and filtering
- Bulk operations support
- Visual warehouse layout

**Production Interface:**
- Kanban-style production boards
- Real-time status updates
- Quality control workflows
- Resource allocation views

**Sales Interface:**
- Customer management panels
- Order processing workflows
- Payment tracking systems
- Sales analytics dashboards

### 8.3 AI Chat Interface

**Features:**
- Natural language input
- Context-aware responses
- Image upload and analysis
- Chat history management
- Multi-session support

---

## 9. Installation and Deployment

### 9.1 System Requirements

**Hardware Requirements:**
- Minimum 4GB RAM (8GB recommended)
- 50GB available disk space
- Multi-core processor (2.4GHz or higher)
- Network connectivity for AI features

**Software Requirements:**
- Python 3.8 or higher
- PostgreSQL 12 or higher
- wkhtmltopdf
- Modern web browser

### 9.2 Installation Steps

**1. Environment Setup:**
```bash
# Clone the repository
git clone <repository-url>
cd katilo-system-postgresql

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

**2. Database Configuration:**
```bash
# Create PostgreSQL database
createdb katilo_erp

# Set environment variables
export DATABASE_URL="postgresql://username:password@localhost/katilo_erp"
export GEMINI_API_KEY="your-gemini-api-key"

# Initialize database
flask db upgrade
```

**3. Application Startup:**
```bash
# Development mode
python app.py

# Production mode
python wsgi.py
```

### 9.3 Deployment Options

**Local Deployment:**
- Single-server installation
- SQLite or PostgreSQL database
- Suitable for small businesses

**Cloud Deployment:**
- AWS, Azure, or Google Cloud
- Managed database services
- Auto-scaling capabilities
- Load balancing support

**Docker Deployment:**
- Containerized application
- Easy scaling and management
- Consistent environments
- Orchestration with Kubernetes

---

## 10. Future Enhancements

### 10.1 Planned AI Improvements

**Advanced Machine Learning:**
- Custom ML models for demand forecasting
- Computer vision for quality control
- Natural language processing for document analysis
- Automated decision-making systems

**Enhanced Chatbot Capabilities:**
- Voice interaction support
- Advanced context understanding
- Integration with external systems
- Personalized recommendations

### 10.2 System Scalability

**Performance Optimizations:**
- Database sharding
- Caching layer implementation
- Microservices architecture
- API rate limiting

**Feature Expansions:**
- Mobile application development
- IoT device integration
- Blockchain for supply chain tracking
- Advanced analytics and reporting

### 10.3 Integration Capabilities

**Third-Party Integrations:**
- E-commerce platforms
- Accounting software
- Shipping providers
- Payment gateways
- CRM systems

**API Development:**
- RESTful API endpoints
- GraphQL implementation
- Webhook support
- Real-time data streaming

---

## Conclusion

The Katilo ERP system represents a modern approach to enterprise resource planning, combining traditional ERP functionality with cutting-edge AI capabilities. The system's modular architecture, comprehensive feature set, and intelligent automation make it an ideal solution for businesses looking to optimize their operations and gain competitive advantages through data-driven insights.

The integration of AI technologies, particularly the Google Gemini model, sets this system apart from traditional ERP solutions by providing intelligent suggestions, predictive analytics, and natural language interfaces that enhance user productivity and decision-making capabilities.

With its robust technical foundation, scalable architecture, and focus on user experience, the Katilo ERP system is well-positioned to support business growth and adapt to evolving market requirements.

---

*This documentation serves as a comprehensive guide for understanding, implementing, and extending the Katilo ERP system as part of a graduation project.*
