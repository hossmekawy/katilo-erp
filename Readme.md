

# 🌟 **KATILO ERP** – Enterprise Resource Planning System

## 🧾 Overview  
**KATILO ERP** is a powerful, all-in-one Enterprise Resource Planning solution built to simplify and automate your business operations — from inventory control and warehouse logistics to supplier management and procurement.  
Designed with modern technologies and an Arabic-friendly interface, KATILO adapts to businesses of all sizes.

---

## 🚀 Key Features  
✅ **Inventory Management** – Track stock levels, movements, and history  
✅ **Warehouse Layout** – Visualize and manage storage sections and slots  
✅ **Supplier Management** – Organize supplier profiles and monitor transactions  
✅ **Purchase Orders** – Create, monitor, and manage purchase requests  
✅ **Bill of Materials (BOM)** – Define recipes and material requirements for products  
✅ **User Roles & Permissions** – Role-based access with customizable privileges  
✅ **Support Tickets** – Built-in help desk for internal support  
✅ **User Profiles** – Edit personal info and manage credentials  
✅ **Mobile-Friendly Interface** – Fully responsive design for all screen sizes  

---

## ⚙️ Tech Stack  
- **Backend**: Python 3.10+, Flask  
- **Database**: SQLite with SQLAlchemy ORM  
- **Frontend**: HTML5, CSS3, JavaScript, Alpine.js  
- **Styling**: Tailwind CSS  
- **Icons**: Font Awesome  
- **PDF Reports**: pdfkit  
- **Data Tools**: pandas, numpy  

---

## 🛠️ Installation Guide

### 🔗 Prerequisites  
- Python 3.10+  
- Git  
- pip  

### 📥 Step-by-Step Setup  
1. **Clone the repo**  
```bash
git clone https://github.com/hossmekawy/katilo-erp.git  
cd katilo-erp
```

2. **Create & activate virtual environment**  
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

3. **Install dependencies**  
```bash
pip install -r requirements.txt
```

4. **Run the application**  
```bash
python app.py
```

5. **Access KATILO ERP**  
Open your browser and go to: [http://localhost:5000](http://localhost:5000)

---

### 💡 Quick Setup for Windows  
Just run:
```bash
setup.bat
```

---

## 👤 User Guide

### 🔑 First Login  
- **Username:** `hussien`  
- **Password:** `Sahs223344`

### 🧭 Navigation  
- Left sidebar: Access all modules  
- Top-right corner: Manage your profile  
- Dashboard: View real-time alerts and key data  

---

## 📦 Core Modules

| Module              | Description                                  |
|---------------------|----------------------------------------------|
| **Dashboard**        | System insights & metrics overview           |
| **Inventory**        | Add, edit, and track inventory items         |
| **Warehouse Layout** | Define & manage physical storage layout      |
| **Categories**       | Organize items by types                      |
| **Items**            | Detailed item information & stock tracking  |
| **BOM**              | Define material requirements per product     |
| **Suppliers**        | Manage supplier profiles & transactions      |
| **Purchase Orders**  | Handle procurement & order tracking          |
| **Transactions**     | Full history of inventory movements          |
| **Admin Panel**      | User/role management (Admin access only)     |

---

## 🧱 Project Structure
```
katilo-erp/
├── app.py               # Main app entry point
├── models.py            # DB models
├── routes/              # Feature-specific routes
│   ├── bom_routes.py
│   ├── profile_routes.py
│   └── ...
├── static/              # CSS, JS, images, uploads
├── templates/           # HTML templates
├── requirements.txt     # Dependencies
└── setup.bat            # Quick setup for Windows
```

---

## 🤝 Contributing

1. Fork the repo  
2. Create a feature branch  
```bash
git checkout -b feature/your-feature-name
```
3. Commit your changes  
```bash
git commit -m "Add new feature"
```
4. Push to GitHub  
```bash
git push origin feature/your-feature-name
```
5. Open a Pull Request

---

## 📄 License  
This project is licensed under the **MIT License**. See the `LICENSE` file for details.

---

## 🙌 Acknowledgements  
Built with ❤️ by the **7AMLA Team**  
Big thanks to all contributors and testers!

---

## 📬 Contact  
📍 GitHub: [hossmekawy](https://github.com/hossmekawy)


