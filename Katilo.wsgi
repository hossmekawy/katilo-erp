# Procfile
web: gunicorn app:app

# requirements.txt (أضف هذه المكتبات إلى ملف المتطلبات الحالي إذا لم تكن موجودة)
Flask>=2.0.0
gunicorn>=20.1.0
Werkzeug>=2.0.0

# runtime.txt (اختياري - يحدد إصدار Python)
python-3.9.13

