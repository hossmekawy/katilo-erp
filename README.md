# Katilo ERP System

![Katilo ERP](static/img/logo.png)

## 🌟 Overview

Katilo ERP is a comprehensive Enterprise Resource Planning system designed specifically for inventory management, production planning, and supplier relationship management. Built with Flask and modern web technologies, it provides a robust solution for businesses looking to streamline their operations.

## ✨ Features

### 📦 Inventory Management
- Complete item tracking with SKU, categories, and pricing
- Multi-warehouse inventory management
- Real-time inventory transaction logging
- Low stock alerts and reorder level management

### 🏭 Production Management
- Bill of Materials (BOM) creation and management
- Production run planning and execution
- Worker productivity tracking
- Quality control processes

### 🤝 Supplier Management
- Supplier database with contact information
- Purchase order creation and tracking
- Supplier payment management
- Supplier ledger and account balances

### 🧠 AI-Powered Assistant
- Integrated chatbot using Google's Gemini AI
- Natural language queries about inventory, production, and suppliers
- Image recognition capabilities for visual item identification
- Contextual responses based on your actual business data

### 👥 User Management
- Role-based access control
- Customizable permissions
- User profile management
- Secure authentication

## 🚀 Installation

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)
- Git (optional, for cloning the repository)
- Google Gemini API key (for AI assistant functionality)

### Step 1: Clone the Repository
```bash
git clone https://github.com/hossmekawy/katilo-erp.git
cd katilo-erp
```

### Step 2: Set Up Virtual Environment
```bash
python -m venv venv
```

#### Activate the virtual environment:
- **Windows**:
```bash
venv\Scripts\activate
```
- **macOS/Linux**:
```bash
source venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables
Create a `.env` file in the root directory with the following content:
```
SECRET_KEY=your_secret_key_here
GEMINI_API_KEY=your_gemini_api_key_here
```

### Step 5: Initialize the Database
```bash
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

### Step 6: Run the Application
```bash
python app.py
```

The application will be available at `http://localhost:5000` or `http://your-local-ip:5000`

## 🔧 Usage

### First-time Setup
1. Log in with the default admin credentials:
   - Username: `hussien`
   - Password: `Sahs223344```
2. Navigate to the admin panel to create additional users and roles
3. Set up your categories, warehouses, and initial inventory

### Daily Operations
- **Inventory Management**: Add/edit items, record transactions
- **Production Planning**: Create BOMs, schedule production runs
- **Supplier Management**: Manage suppliers, create purchase orders
- **AI Assistant**: Ask questions about your inventory and operations

## 🧩 System Architecture

Katilo ERP follows a modular architecture with the following components:

- **Flask Backend**: Handles HTTP requests, database operations, and business logic
- **SQLite Database**: Stores all application data (can be upgraded to PostgreSQL/MySQL)
- **Jinja2 Templates**: Renders the frontend views
- **AlpineJS**: Provides reactive frontend functionality
- **Tailwind CSS**: Styles the user interface
- **Google Gemini AI**: Powers the intelligent chatbot assistant

## 📊 Database Schema

The system uses a comprehensive database schema with the following main entities:
- Items, Categories, Warehouses
- Inventory, Transactions
- BOMs, Production Runs
- Suppliers, Purchase Orders
- Users, Roles, Permissions

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 📞 Support

For support, please open an issue on the GitHub repository or contact the maintainers directly.

---

Built with ❤️ by Hussien Mekawy
```
