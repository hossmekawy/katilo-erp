<p align="center">
  <img src="https://ik.imagekit.io/tijarahub/optimized/Frontend-Ayehia/Vendors/Egypt/Katilo/Logo.png" alt="Katilo ERP Logo" width="120" />
</p>

<h1 align="center" style="font-size: 3rem; color: #4CAF50;">✨ Katilo ERP ✨</h1>

<p align="center">
  <em>A Modern & Scalable Inventory and Warehouse Management Platform in arabic عربي</em>
</p>

<p align="center">
  <a href="https://github.com/hossmekawy/katilo-erp/stargazers"><img src="https://img.shields.io/github/stars/hossmekawy/katilo-erp.svg?style=for-the-badge" alt="Stars"></a>
  <a href="https://github.com/hossmekawy/katilo-erp/network/members"><img src="https://img.shields.io/github/forks/hossmekawy/katilo-erp.svg?style=for-the-badge" alt="Forks"></a>
  <a href="https://github.com/hossmekawy/katilo-erp/issues"><img src="https://img.shields.io/github/issues/hossmekawy/katilo-erp.svg?style=for-the-badge" alt="Issues"></a>
  <a href="https://github.com/hossmekawy/katilo-erp/blob/main/LICENSE"><img src="https://img.shields.io/github/license/hossmekawy/katilo-erp.svg?style=for-the-badge" alt="License"></a>
</p>

---

## 🌐 Overview

**Katilo ERP** is an open-source ERP platform designed with **Flask** to handle all your business's inventory, warehouse, and operations management. Clean, lightweight, and modular.

### 🎯 Key Features

- 📦 **Inventory Management** — Track stock, quantities, and alerts.
- 🏢 **Warehouse Mapping** — Slot/section organization.
- 👤 **User Roles & Permissions** — Admin and employee access control.
- 🎟️ **Support Tickets** — With file uploads and responses.
- 📊 **Dynamic Dashboard** — Real-time metrics and analytics.
- 🛠️ **Upcoming** — Forecasting, production planning, and much more!

---

## ⚙️ Installation & Setup

### 📋 Requirements
- Python 3.8+
- Git
- Virtual Environment tool (optional but recommended)

### 🚧 Steps

```bash
# 1. Clone the repo
git clone https://github.com/hossmekawy/katilo-erp.git
cd katilo-erp

# 2. Set up the virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install requirements
pip install -r requirements.txt

# 4. (Optional) Set a secure SECRET_KEY in app.py
app.config['SECRET_KEY'] = 'your-secret-key'

# 5. Initialize DB
python
>>> from app import app, db
>>> with app.app_context():
>>>     db.create_all()
```

### ▶️ Run the App
```bash
python app.py
```

Navigate to:
```
http://localhost:5000
```

- 🔐 `/login` – User login
- ➕ `/api/admin/users` – Admin-only user registration

---

## 📁 Project Layout

```bash
katilo-erp/
├── app.py              # Main Flask app
├── models.py           # DB models
├── support_routes.py   # Ticket endpoints
├── static/
│   └── uploads/support # File uploads
├── templates/          # HTML views
├── requirements.txt    # Dependencies
└── katilo.db           # SQLite DB (auto-created)
```

---

## 💡 How to Use

- 🧑‍💼 **Admin** can manage users, view dashboards, and handle tickets.
- 🧾 **Inventory** tools available at `/inventory-management`
- 🆘 **Support** form is at `/contact-support`
- 📈 **Stats** and visual metrics at `/dashboard`

---

## 🤝 Contributing

We welcome pull requests! Here's how:

1. Fork the project
2. Create a feature branch: `git checkout -b feature/xyz`
3. Commit your work: `git commit -m "feat: add xyz feature"`
4. Push it: `git push origin feature/xyz`
5. Open a PR

📘 Read our [Contributing Guide](CONTRIBUTING.md) for details.

---

## 📄 License

Licensed under the **MIT License**. See the [LICENSE](LICENSE) file.

---

## 👨‍💻 Author

Made with 💚 by [Hossam Mekawy](https://github.com/hossmekawy)

<p align="center">
  <img src="https://img.shields.io/badge/Thanks%20for%20visiting-Katilo%20ERP-brightgreen?style=for-the-badge"/>
</p>
