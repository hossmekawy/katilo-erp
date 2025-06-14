# Katilo ERP System - Installation and Deployment Guide

## Table of Contents
1. [System Requirements](#system-requirements)
2. [Pre-Installation Setup](#pre-installation-setup)
3. [Installation Process](#installation-process)
4. [Configuration](#configuration)
5. [Database Setup](#database-setup)
6. [AI Services Configuration](#ai-services-configuration)
7. [Production Deployment](#production-deployment)
8. [Troubleshooting](#troubleshooting)

---

## 1. System Requirements

### 1.1 Hardware Requirements

**Minimum Requirements:**
- **CPU**: 2-core processor (2.4 GHz or higher)
- **RAM**: 4GB (8GB recommended)
- **Storage**: 50GB available disk space
- **Network**: Stable internet connection for AI features

**Recommended Requirements:**
- **CPU**: 4-core processor (3.0 GHz or higher)
- **RAM**: 16GB or more
- **Storage**: 100GB SSD storage
- **Network**: High-speed internet (100 Mbps+)

**Production Environment:**
- **CPU**: 8-core processor or higher
- **RAM**: 32GB or more
- **Storage**: 500GB SSD with backup storage
- **Network**: Redundant internet connections
- **Load Balancer**: For high availability

### 1.2 Software Requirements

**Operating System:**
- Windows 10/11 (64-bit)
- Windows Server 2019/2022
- Ubuntu 20.04 LTS or higher
- CentOS 8 or higher
- macOS 10.15 or higher

**Required Software:**
- Python 3.8 or higher
- PostgreSQL 12 or higher
- Git (for version control)
- Web browser (Chrome, Firefox, Safari, Edge)

**Optional Software:**
- Redis (for caching)
- Nginx (for reverse proxy)
- Docker (for containerization)

### 1.3 Network Requirements

**Ports:**
- **5000**: Flask development server
- **8000**: Production server (Waitress)
- **5432**: PostgreSQL database
- **6379**: Redis cache (if used)
- **80/443**: HTTP/HTTPS (production)

**External Services:**
- Google Gemini API access
- SMTP server for email notifications
- SSL certificate for HTTPS

---

## 2. Pre-Installation Setup

### 2.1 Python Environment

**Install Python:**
```bash
# Windows (using Chocolatey)
choco install python

# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-pip python3-venv

# CentOS/RHEL
sudo yum install python3 python3-pip

# macOS (using Homebrew)
brew install python
```

**Verify Installation:**
```bash
python --version
pip --version
```

### 2.2 PostgreSQL Installation

**Windows:**
1. Download PostgreSQL installer from postgresql.org
2. Run installer and follow setup wizard
3. Set password for postgres user
4. Note the port number (default: 5432)

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

**CentOS/RHEL:**
```bash
sudo yum install postgresql-server postgresql-contrib
sudo postgresql-setup initdb
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

**macOS:**
```bash
brew install postgresql
brew services start postgresql
```

### 2.3 Git Installation

**Windows:**
- Download Git from git-scm.com
- Run installer with default settings

**Linux:**
```bash
# Ubuntu/Debian
sudo apt install git

# CentOS/RHEL
sudo yum install git
```

**macOS:**
```bash
brew install git
```

---

## 3. Installation Process

### 3.1 Download Source Code

**Clone Repository:**
```bash
git clone <repository-url>
cd katilo-system-postgresql
```

**Alternative: Download ZIP:**
1. Download ZIP file from repository
2. Extract to desired directory
3. Navigate to extracted folder

### 3.2 Virtual Environment Setup

**Create Virtual Environment:**
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

**Verify Activation:**
```bash
which python  # Should show venv path
```

### 3.3 Install Dependencies

**Install Python Packages:**
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Common Dependencies:**
```txt
Flask==2.3.3
Flask-SQLAlchemy==3.0.5
Flask-Login==0.6.3
Flask-Migrate==4.0.5
psycopg2-binary==2.9.7
google-generativeai==0.3.2
wkhtmltopdf==0.2
pandas==2.0.3
python-dotenv==1.0.0
waitress==2.1.2
```

### 3.4 wkhtmltopdf Installation

**Windows:**
1. Download wkhtmltopdf from wkhtmltopdf.org
2. Install to `pdftool/wkhtmltopdf/bin/` directory
3. Verify installation path in code

**Ubuntu/Debian:**
```bash
sudo apt install wkhtmltopdf
```

**CentOS/RHEL:**
```bash
sudo yum install wkhtmltopdf
```

**macOS:**
```bash
brew install wkhtmltopdf
```

---

## 4. Configuration

### 4.1 Environment Variables

**Create .env File:**
```bash
# Database Configuration
DATABASE_URL=postgresql://username:password@localhost:5432/katilo_erp
FLASK_ENV=development
FLASK_DEBUG=True

# AI Configuration
GEMINI_API_KEY=your_gemini_api_key_here

# Security
SECRET_KEY=your_secret_key_here
SECURITY_PASSWORD_SALT=your_password_salt_here

# Email Configuration (Optional)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_app_password

# File Upload
MAX_CONTENT_LENGTH=16777216  # 16MB
UPLOAD_FOLDER=uploads
```

**Environment Variables Explanation:**
- `DATABASE_URL`: PostgreSQL connection string
- `GEMINI_API_KEY`: Google Gemini API key for AI features
- `SECRET_KEY`: Flask application secret key
- `FLASK_ENV`: Environment mode (development/production)

### 4.2 Application Configuration

**config.py Settings:**
```python
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    UPLOAD_FOLDER = 'uploads'
    
    # AI Configuration
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    
    # Email Configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
```

---

## 5. Database Setup

### 5.1 Create Database

**PostgreSQL Setup:**
```sql
-- Connect to PostgreSQL as superuser
sudo -u postgres psql

-- Create database
CREATE DATABASE katilo_erp;

-- Create user
CREATE USER katilo_user WITH PASSWORD 'secure_password';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE katilo_erp TO katilo_user;

-- Exit PostgreSQL
\q
```

### 5.2 Database Migration

**Initialize Migration:**
```bash
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

**Verify Database:**
```bash
# Connect to database
psql -h localhost -U katilo_user -d katilo_erp

# List tables
\dt

# Exit
\q
```

### 5.3 Seed Initial Data

**Run Database Seeder:**
```bash
python utils/database_seeder.py
```

**Manual Data Entry:**
1. Start the application
2. Access admin interface
3. Create initial users and roles
4. Add basic categories and items
5. Configure system settings

---

## 6. AI Services Configuration

### 6.1 Google Gemini API Setup

**Obtain API Key:**
1. Visit Google AI Studio (ai.google.dev)
2. Create new project or select existing
3. Enable Gemini API
4. Generate API key
5. Add key to .env file

**Test AI Connection:**
```python
import google.generativeai as genai
import os

genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-2.0-flash')

# Test connection
response = model.generate_content("Hello, test connection")
print(response.text)
```

### 6.2 AI Features Configuration

**Enable AI Features:**
```python
# In app.py or config.py
AI_ENABLED = True
AI_MODEL = "gemini-2.0-flash"
AI_RATE_LIMIT = 60  # requests per minute
AI_TIMEOUT = 30  # seconds
```

**Configure AI Suggestions:**
```python
# AI suggestion settings
AI_SUGGESTION_BATCH_SIZE = 10
AI_SUGGESTION_INTERVAL = 3600  # 1 hour
AI_SUGGESTION_ENABLED = True
```

---

## 7. Production Deployment

### 7.1 Production Configuration

**Update Environment:**
```bash
# .env for production
FLASK_ENV=production
FLASK_DEBUG=False
DATABASE_URL=postgresql://user:pass@prod-db:5432/katilo_erp
SECRET_KEY=production_secret_key_here
```

**Security Settings:**
```python
# Production security
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
PERMANENT_SESSION_LIFETIME = 1800  # 30 minutes
WTF_CSRF_ENABLED = True
```

### 7.2 WSGI Server Setup

**Using Waitress (Recommended):**
```python
# wsgi.py
from waitress import serve
from app import app
import os

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    serve(app, host='0.0.0.0', port=port, threads=6)
```

**Start Production Server:**
```bash
python wsgi.py
```

### 7.3 Reverse Proxy (Nginx)

**Nginx Configuration:**
```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location /static {
        alias /path/to/katilo/static;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

### 7.4 SSL Certificate

**Using Let's Encrypt:**
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

**Manual SSL Setup:**
```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /path/to/certificate.crt;
    ssl_certificate_key /path/to/private.key;
    
    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
}
```

---

## 8. Troubleshooting

### 8.1 Common Issues

**Database Connection Error:**
```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Verify connection
psql -h localhost -U katilo_user -d katilo_erp

# Check firewall
sudo ufw status
```

**Python Import Errors:**
```bash
# Verify virtual environment
which python
pip list

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

**AI API Errors:**
```bash
# Test API key
curl -H "Authorization: Bearer $GEMINI_API_KEY" \
     https://generativelanguage.googleapis.com/v1/models

# Check rate limits
# Verify API quotas in Google Cloud Console
```

### 8.2 Performance Issues

**Database Optimization:**
```sql
-- Create indexes
CREATE INDEX idx_inventory_item_warehouse ON inventory(item_id, warehouse_id);
CREATE INDEX idx_transactions_date ON inventory_transactions(transaction_date);

-- Analyze tables
ANALYZE;

-- Check slow queries
SELECT query, mean_time, calls FROM pg_stat_statements ORDER BY mean_time DESC;
```

**Application Optimization:**
```python
# Enable caching
from flask_caching import Cache
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

# Database connection pooling
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_size': 10,
    'pool_recycle': 120,
    'pool_pre_ping': True
}
```

### 8.3 Monitoring and Logging

**Application Logging:**
```python
import logging
from logging.handlers import RotatingFileHandler

if not app.debug:
    file_handler = RotatingFileHandler('logs/katilo.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
```

**System Monitoring:**
```bash
# Monitor system resources
htop
iostat -x 1
free -h

# Monitor application
tail -f logs/katilo.log
journalctl -u katilo-erp -f
```

### 8.4 Backup and Recovery

**Database Backup:**
```bash
# Create backup
pg_dump -h localhost -U katilo_user katilo_erp > backup_$(date +%Y%m%d).sql

# Automated backup script
#!/bin/bash
BACKUP_DIR="/backups"
DATE=$(date +%Y%m%d_%H%M%S)
pg_dump -h localhost -U katilo_user katilo_erp | gzip > $BACKUP_DIR/katilo_backup_$DATE.sql.gz
```

**Application Backup:**
```bash
# Backup application files
tar -czf katilo_app_backup_$(date +%Y%m%d).tar.gz \
    --exclude='venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    /path/to/katilo-system-postgresql
```

**Recovery Process:**
```bash
# Restore database
gunzip -c backup_file.sql.gz | psql -h localhost -U katilo_user katilo_erp

# Restore application
tar -xzf katilo_app_backup.tar.gz -C /path/to/restore/
```

---

## Support and Maintenance

### 8.5 Regular Maintenance

**Daily Tasks:**
- Monitor system performance
- Check error logs
- Verify backup completion
- Review AI usage metrics

**Weekly Tasks:**
- Database maintenance (VACUUM, ANALYZE)
- Security updates
- Performance review
- User activity audit

**Monthly Tasks:**
- Full system backup
- Security assessment
- Capacity planning
- Feature usage analysis

### 8.6 Getting Support

**Documentation:**
- System documentation
- API reference
- User manuals
- Video tutorials

**Community Support:**
- GitHub issues
- Community forums
- Stack Overflow
- Discord/Slack channels

**Professional Support:**
- Technical support team
- Consulting services
- Custom development
- Training programs

---

This installation guide provides comprehensive instructions for setting up the Katilo ERP system in various environments. For additional support or custom deployment requirements, please contact the development team.
