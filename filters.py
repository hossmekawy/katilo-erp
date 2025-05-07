from datetime import datetime, timedelta

def init_filters(app):
    @app.template_filter('currency')
    def currency_filter(value):
        """Format a value as currency"""
        if value is None:
            return "N/A"
        return f"${value:,.2f}"
    
    @app.template_filter('date')
    def date_filter(value, format='%Y-%m-%d'):
        """Format a date"""
        if value is None:
            return ""
        if isinstance(value, str):
            try:
                value = datetime.strptime(value, '%Y-%m-%d')
            except ValueError:
                return value
        return value.strftime(format)
    
    @app.template_filter('status_color')
    def status_color_filter(status):
        """Return Bootstrap color class based on status"""
        status_colors = {
            'Pending': 'warning',
            'Shipped': 'primary',
            'Delivered': 'success',
            'Cancelled': 'danger',
            'Approved': 'success',
            'Received': 'info',
            'In Progress': 'primary',
            'Completed': 'success'
        }
        return status_colors.get(status, 'secondary')
    
    @app.template_filter('invoice_status_color')
    def invoice_status_color_filter(status):
        status_colors = {
            'Paid': 'success',
            'Unpaid': 'danger',
            'Partially Paid': 'warning',
            'Overdue': 'danger',
            'Cancelled': 'secondary',
            'Refunded': 'info'
        }
        return status_colors.get(status, 'primary')
    
    @app.template_filter('format_date')
    def format_date(value):
        if value is None:
            return "--"
        if isinstance(value, str):
            try:
                value = datetime.strptime(value, '%Y-%m-%d')
            except ValueError:
                return value
        return value.strftime('%d/%m/%Y')
    
    @app.template_filter('format_datetime')
    def format_datetime(value):
        if value is None:
            return "--"
        if isinstance(value, str):
            try:
                value = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                return value
        return value.strftime('%d/%m/%Y %H:%M')
    
    @app.template_filter('format_currency')
    def format_currency(value):
        if value is None:
            return "--"
        return f"{float(value):,.2f} ج.م"

    @app.template_filter('time_ago')
    def time_ago_filter(value):
        if not value:
            return '--'
        
        if isinstance(value, str):
            try:
                value = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                return value
        
        now = datetime.now()
        diff = now - value
        
        seconds = diff.total_seconds()
        
        if seconds < 60:
            return "الآن"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            return f"{minutes} {'دقيقة' if minutes == 1 else 'دقائق'}"
        elif seconds < 86400:
            hours = int(seconds // 3600)
            return f"{hours} {'ساعة' if hours == 1 else 'ساعات'}"
        elif seconds < 2592000:
            days = int(seconds // 86400)
            return f"{days} {'يوم' if days == 1 else 'أيام'}"
        elif seconds < 31536000:
            months = int(seconds // 2592000)
            return f"{months} {'شهر' if months == 1 else 'أشهر'}"
        else:
            years = int(seconds // 31536000)
            return f"{years} {'سنة' if years == 1 else 'سنوات'}"
        
    @app.template_filter('datetime')
    def datetime_filter(value, format='%Y-%m-%d %H:%M:%S'):
        if value is None:
            return ""
        if isinstance(value, str):
            try:
                value = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                try:
                    value = datetime.strptime(value, '%Y-%m-%d')
                except ValueError:
                    return value
        return value.strftime(format)
    
    # Add these filters to your app.py or where you initialize your Flask app

    @app.template_filter('date')
    def date_filter(value, format='%Y-%m-%d'):
        if value is None:
            return ""
        if isinstance(value, str):
            try:
                value = datetime.strptime(value, '%Y-%m-%d')
            except ValueError:
                return value
        return value.strftime(format)

    @app.template_filter('datetime')
    def datetime_filter(value, format='%Y-%m-%d %H:%M'):
        if value is None:
            return ""
        if isinstance(value, str):
            try:
                value = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                return value
        return value.strftime(format)

    @app.template_filter('currency')
    def currency_filter(value):
        if value is None:
            return "0.00 ج.م"
        return f"{float(value):.2f} ج.م"

    @app.template_filter('status_color')
    def status_color_filter(status):
        status_colors = {
            'Pending': 'warning',
            'Processing': 'info',
            'Shipped': 'primary',
            'Delivered': 'success',
            'Cancelled': 'danger'
        }
        return status_colors.get(status, 'secondary')

    @app.template_filter('invoice_status_color')
    def invoice_status_color_filter(status):
        status_colors = {
            'Paid': 'success',
            'Unpaid': 'danger',
            'Partially Paid': 'warning',
            'Overdue': 'danger',
            'Cancelled': 'secondary',
            'Refunded': 'info'
        }
        return status_colors.get(status, 'primary')

    @app.template_filter('now')
    def template_now(value=None, format='%Y-%m-%d'):
        """Return current date/time formatted according to the specified format.
        The value parameter is ignored but required by Jinja2's filter mechanism."""
        return datetime.now().strftime(format)

    @app.template_filter('month_start')
    def month_start_filter(value=None):
        """Return the first day of the current month."""
        today = datetime.now()
        first_day = today.replace(day=1)
        return first_day.strftime('%Y-%m-%d')

    @app.template_filter('month_end')
    def month_end_filter(value=None):
        """Return the last day of the current month."""
        today = datetime.now()
        # Get the first day of next month, then subtract one day
        if today.month == 12:
            next_month = today.replace(year=today.year + 1, month=1, day=1)
        else:
            next_month = today.replace(month=today.month + 1, day=1)
        
        last_day = next_month - timedelta(days=1)
        return last_day.strftime('%Y-%m-%d')
