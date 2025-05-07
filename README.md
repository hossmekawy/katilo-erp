# Katilo ERP System

![Katilo Logo](static/uploads/images/katilo.png)

[![Version](https://img.shields.io/badge/version-10.0.1-blue.svg)](https://github.com/hossmekawy/katilo-erp/tree/v10.0.1)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> Comprehensive inventory management and ERP solution since 1910

## 🌟 Overview

Katilo ERP is an integrated solution for inventory management, warehousing, production, and sales operations. Built with modern web technologies, it provides a robust Arabic-first interface designed for businesses of all sizes.

## ✨ Features

- **Inventory Management**: Track stock levels, movements, and valuations
- **Warehouse Operations**: Manage multiple locations and transfers
- **Production Management**: BOM (Bill of Materials) and manufacturing processes
- **Sales & Distribution**: Order processing and vehicle management
- **PDF Report Generation**: Create professional reports with custom branding
- **Multi-user Access**: Role-based permissions system
- **Arabic Interface**: Full RTL support with Arabic fonts and localization

## 🚀 Installation

### Prerequisites

- Python 3.8 or higher
- wkhtmltopdf (for PDF generation)

### Windows Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/hossmekawy/katilo-erp.git -b v10.0.1
   cd katilo-erp
   ```

2. Run the setup script:
   ```bash
   setup.bat
   ```

3. Start the application:
   ```bash
   run.bat
   ```

### Linux/macOS Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/hossmekawy/katilo-erp.git -b v10.0.1
   cd katilo-erp
   ```

2. Create and activate virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Install wkhtmltopdf:
   ```bash
   # Ubuntu/Debian
   sudo apt-get install wkhtmltopdf
   
   # macOS
   brew install wkhtmltopdf
   ```

5. Start the application:
   ```bash
   python wsgi.py
   ```

## 📊 Usage

After starting the application, navigate to:
- Local: http://localhost:8080
- Network: http://{your-ip}:8080

Default login credentials:
- Username: admin
- Password: admin

## 📄 PDF Generation

Katilo ERP includes a powerful PDF generation system for reports and documents:

```python
from utils.pdf_generator import PDFGenerator

# Generate a report with Katilo branding
pdf_path = PDFGenerator.generate_report_pdf(
    template_path='my_report_template.html',
    context={'report_data': data},
    filename='my_report.pdf'
)
```

See [PDF_GENERATION.md](PDF_GENERATION.md) for detailed documentation.

## 🔧 Configuration

Configuration options can be modified in the application settings or by editing the configuration files directly.

## 🌐 Deployment

For production deployment, the system uses Waitress WSGI server with automatic port selection and multi-threading based on available CPU cores.

## 📱 Contact

- Email: hussienmekawy38@gmail.com
- Phone: +201099641402

## 📜 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

<p align="center">© Katilo ERP - Since 1910</p>
