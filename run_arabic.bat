@echo off
echo مرحبًا! جاري إعداد وتشغيل Katilo ERP...
echo.

echo 1. إنشاء بيئة افتراضية...
python -m venv venv
if %ERRORLEVEL% NEQ 0 (
    echo خطأ: فشل إنشاء البيئة الافتراضية. تأكد من تثبيت Python.
    pause
    exit /b %ERRORLEVEL%
)
echo تم إنشاء البيئة الافتراضية بنجاح!
echo.

echo 2. تفعيل البيئة الافتراضية...
call venv\Scripts\activate
if %ERRORLEVEL% NEQ 0 (
    echo خطأ: فشل تفعيل البيئة الافتراضية.
    pause
    exit /b %ERRORLEVEL%
)
echo تم تفعيل البيئة الافتراضية!
echo.

echo 3. تثبيت المتطلبات من requirements.txt...
pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo خطأ: فشل تثبيت المتطلبات. تأكد من وجود ملف requirements.txt واتصال الإنترنت.
    pause
    exit /b %ERRORLEVEL%
)
echo تم تثبيت المتطلبات بنجاح!
echo.

echo 4. تشغيل التطبيق...
python app.py
if %ERRORLEVEL% NEQ 0 (
    echo خطأ: فشل تشغيل app.py. تأكد من وجود الملف وأنه صحيح.
    pause
    exit /b %ERRORLEVEL%
)

echo التطبيق يعمل الآن! افتح المتصفح على http://localhost:5000
pause
