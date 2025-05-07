import os
import uuid
import subprocess
import tempfile
from datetime import datetime
from flask import current_app
import pandas as pd
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import arabic_reshaper
from bidi.algorithm import get_display
import xlsxwriter

# Register Arabic font
def register_fonts():
    font_path = os.path.join(current_app.root_path, 'static', 'fonts')
    pdfmetrics.registerFont(TTFont('Arabic', os.path.join(font_path, 'NotoSansArabic-Regular.ttf')))
    pdfmetrics.registerFont(TTFont('ArabicBold', os.path.join(font_path, 'NotoSansArabic-Bold.ttf')))

# Helper function for Arabic text
def arabic_text(text):
    if not text:
        return ""
    reshaped_text = arabic_reshaper.reshape(str(text))
    return get_display(reshaped_text)

# Generate PDF from HTML using wkhtmltopdf
def generate_pdf(html_content):
    """
    Generate a PDF from HTML content using wkhtmltopdf

    Args:
        html_content (str): HTML content to convert to PDF

    Returns:
        bytes: PDF file content as bytes
    """
    # Create a temporary file for the HTML content
    with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as html_file:
        html_file.write(html_content.encode('utf-8'))
        html_file_path = html_file.name

    # Create a temporary file for the PDF output
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as pdf_file:
        pdf_file_path = pdf_file.name

    try:
        # Path to wkhtmltopdf executable
        wkhtmltopdf_path = os.path.join(current_app.root_path, 'pdftool', 'wkhtmltopdf', 'bin', 'wkhtmltopdf.exe')

        # Build the command
        cmd = [
            wkhtmltopdf_path,
            '--encoding', 'utf-8',
            '--enable-local-file-access',
            '--margin-top', '10mm',
            '--margin-right', '10mm',
            '--margin-bottom', '10mm',
            '--margin-left', '10mm',
            '--page-size', 'A4',
            html_file_path,
            pdf_file_path
        ]

        # Execute the command
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()

        if process.returncode != 0:
            current_app.logger.error(f"wkhtmltopdf error: {stderr.decode('utf-8')}")
            raise Exception(f"PDF generation failed: {stderr.decode('utf-8')}")

        # Read the generated PDF
        with open(pdf_file_path, 'rb') as f:
            pdf_content = f.read()

        return pdf_content

    finally:
        # Clean up temporary files
        try:
            os.unlink(html_file_path)
            os.unlink(pdf_file_path)
        except Exception as e:
            current_app.logger.error(f"Error cleaning up temporary files: {str(e)}")

class PDFGenerator:
    def __init__(self):
        register_fonts()
        self.styles = getSampleStyleSheet()
        # Add Arabic style
        self.styles.add(ParagraphStyle(
            name='Arabic',
            fontName='Arabic',
            alignment=1,  # Center alignment
            fontSize=12,
            leading=14,
            rightIndent=10,
            leftIndent=10
        ))
        self.styles.add(ParagraphStyle(
            name='ArabicTitle',
            fontName='ArabicBold',
            alignment=1,  # Center alignment
            fontSize=16,
            leading=20,
            spaceAfter=12
        ))
        self.styles.add(ParagraphStyle(
            name='ArabicHeader',
            fontName='ArabicBold',
            alignment=1,  # Center alignment
            fontSize=14,
            leading=16,
            spaceAfter=10
        ))

    def generate_account_statement(self, account, transactions, date_from, date_to, format='pdf'):
        """Generate account statement report"""
        title = f"كشف حساب - {account.name}" if account else "كشف حساب - جميع الحسابات"
        subtitle = f"الفترة من {date_from.strftime('%Y-%m-%d')} إلى {date_to.strftime('%Y-%m-%d')}"

        # Prepare data
        data = [['التاريخ', 'الحساب', 'النوع', 'المبلغ', 'الرصيد', 'الوصف']]

        balance = 0
        for transaction in transactions:
            account_name = transaction.account.name if transaction.account else ""

            # Calculate running balance
            if transaction.transaction_type == 'deposit':
                balance += transaction.amount
                amount_str = f"+{transaction.amount:,.2f}"
            else:
                balance -= transaction.amount
                amount_str = f"-{transaction.amount:,.2f}"

            data.append([
                transaction.transaction_date.strftime('%Y-%m-%d %H:%M'),
                account_name,
                'إيداع' if transaction.transaction_type == 'deposit' else 'سحب',
                amount_str,
                f"{balance:,.2f}",
                transaction.description or ""
            ])

        if format == 'pdf':
            return self._generate_pdf_report(title, subtitle, data)
        elif format == 'excel':
            return self._generate_excel_report(title, subtitle, data)
        else:
            return None

    def generate_cash_flow(self, accounts, transactions, date_from, date_to, format='pdf'):
        """Generate cash flow report"""
        title = "تقرير التدفق النقدي"
        subtitle = f"الفترة من {date_from.strftime('%Y-%m-%d')} إلى {date_to.strftime('%Y-%m-%d')}"

        # Prepare summary data
        total_deposits = sum(t.amount for t in transactions if t.transaction_type == 'deposit')
        total_withdrawals = sum(t.amount for t in transactions if t.transaction_type == 'withdrawal')
        net_flow = total_deposits - total_withdrawals

        summary_data = [
            ['إجمالي الإيداعات', 'إجمالي المسحوبات', 'صافي التدفق'],
            [f"{total_deposits:,.2f}", f"{total_withdrawals:,.2f}", f"{net_flow:,.2f}"]
        ]

        # Prepare account balances
        account_data = [['الحساب', 'الرصيد الافتتاحي', 'الإيداعات', 'المسحوبات', 'الرصيد الختامي']]

        for account in accounts:
            account_deposits = sum(t.amount for t in transactions
                                if t.account_id == account.id and t.transaction_type == 'deposit')
            account_withdrawals = sum(t.amount for t in transactions
                                   if t.account_id == account.id and t.transaction_type == 'withdrawal')

            # Calculate opening balance (current balance - net flow for this period)
            opening_balance = account.current_balance - (account_deposits - account_withdrawals)
            closing_balance = opening_balance + account_deposits - account_withdrawals

            account_data.append([
                account.name,
                f"{opening_balance:,.2f}",
                f"{account_deposits:,.2f}",
                f"{account_withdrawals:,.2f}",
                f"{closing_balance:,.2f}"
            ])

        if format == 'pdf':
            return self._generate_pdf_cash_flow(title, subtitle, summary_data, account_data)
        elif format == 'excel':
            return self._generate_excel_cash_flow(title, subtitle, summary_data, account_data)
        else:
            return None

    def generate_supplier_payments(self, supplier, payments, date_from, date_to, format='pdf'):
        """Generate supplier payments report"""
        title = f"تقرير دفعات المورد - {supplier.supplier_name}" if supplier else "تقرير دفعات الموردين"
        subtitle = f"الفترة من {date_from.strftime('%Y-%m-%d')} إلى {date_to.strftime('%Y-%m-%d')}"

        # Prepare data
        data = [['التاريخ', 'المورد', 'المبلغ', 'الحساب', 'رقم السند', 'ملاحظات']]

        for payment in payments:
            supplier_name = payment.supplier.supplier_name if payment.supplier else ""
            account_name = payment.from_account.name if payment.from_account else ""

            data.append([
                payment.transfer_date.strftime('%Y-%m-%d'),
                supplier_name,
                f"{payment.amount:,.2f}",
                account_name,
                payment.voucher_number,
                payment.notes or ""
            ])

        # Add total row
        total_amount = sum(payment.amount for payment in payments)
        data.append(['الإجمالي', '', f"{total_amount:,.2f}", '', '', ''])

        if format == 'pdf':
            return self._generate_pdf_report(title, subtitle, data)
        elif format == 'excel':
            return self._generate_excel_report(title, subtitle, data)
        else:
            return None

    def generate_transactions_summary(self, transactions, date_from, date_to, format='pdf'):
        """Generate transactions summary report"""
        title = "ملخص المعاملات"
        subtitle = f"الفترة من {date_from.strftime('%Y-%m-%d')} إلى {date_to.strftime('%Y-%m-%d')}"

        # Prepare data
        data = [['التاريخ', 'الحساب', 'النوع', 'المبلغ', 'الوصف']]

        for transaction in transactions:
            account_name = transaction.account.name if transaction.account else ""

            data.append([
                transaction.transaction_date.strftime('%Y-%m-%d %H:%M'),
                account_name,
                'إيداع' if transaction.transaction_type == 'deposit' else 'سحب',
                f"{transaction.amount:,.2f}",
                transaction.description or ""
            ])

        # Add summary
        total_deposits = sum(t.amount for t in transactions if t.transaction_type == 'deposit')
        total_withdrawals = sum(t.amount for t in transactions if t.transaction_type == 'withdrawal')

        summary_data = [
            ['إجمالي الإيداعات', 'إجمالي المسحوبات', 'صافي الحركة'],
            [f"{total_deposits:,.2f}", f"{total_withdrawals:,.2f}", f"{total_deposits - total_withdrawals:,.2f}"]
        ]

        if format == 'pdf':
            return self._generate_pdf_with_summary(title, subtitle, data, summary_data)
        elif format == 'excel':
            return self._generate_excel_with_summary(title, subtitle, data, summary_data)
        else:
            return None

    def generate_reconciliation_report(self, reconciliations, date_from, date_to, format='pdf'):
        """Generate reconciliation report"""
        title = "تقرير جرد الخزينة"
        subtitle = f"الفترة من {date_from.strftime('%Y-%m-%d')} إلى {date_to.strftime('%Y-%m-%d')}"

        # Prepare data
        data = [['التاريخ', 'الحساب', 'الرصيد الدفتري', 'الرصيد الفعلي', 'الفرق', 'الحالة', 'ملاحظات']]

        for recon in reconciliations:
            account_name = recon.account.name if recon.account else ""
            difference = recon.actual_balance - recon.system_balance

            data.append([
                recon.reconciliation_date.strftime('%Y-%m-%d'),
                account_name,
                f"{recon.system_balance:,.2f}",
                f"{recon.actual_balance:,.2f}",
                f"{difference:,.2f}",
                recon.status,
                recon.notes or ""
            ])

        if format == 'pdf':
            return self._generate_pdf_report(title, subtitle, data)
        elif format == 'excel':
            return self._generate_excel_report(title, subtitle, data)
        else:
            return None

    def _generate_pdf_report(self, title, subtitle, data):
        """Generate a generic PDF report"""
        # Create a temporary file in the configured temp folder
        temp_folder = current_app.config['TEMP_FOLDER']
        os.makedirs(temp_folder, exist_ok=True)

        # Generate a unique filename
        filename = f"report_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}.pdf"
        path = os.path.join(temp_folder, filename)

        # Make sure the file doesn't exist (just in case)
        if os.path.exists(path):
            os.remove(path)

        # Create the PDF document
        doc = SimpleDocTemplate(
            path,
            pagesize=landscape(A4),
            rightMargin=30,
            leftMargin=30,
            topMargin=30,
            bottomMargin=30
        )

        # Build the story
        story = []

        # Add logo if available
        logo_path = os.path.join(current_app.root_path, 'static', 'uploads', 'images', 'katilo.png')
        if os.path.exists(logo_path):
            img = Image(logo_path, width=100, height=100)
            img.hAlign = 'CENTER'
            story.append(img)
            story.append(Spacer(1, 10))

        # Add title and subtitle
        story.append(Paragraph(arabic_text(title), self.styles['ArabicTitle']))
        story.append(Paragraph(arabic_text(subtitle), self.styles['ArabicHeader']))
        story.append(Spacer(1, 10))

        # Process data for Arabic text
        processed_data = []
        for row in data:
            processed_row = [arabic_text(cell) for cell in row]
            processed_data.append(processed_row)

        # Create table
        table = Table(processed_data, repeatRows=1)

        # Add table style
        table_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'ArabicBold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Arabic'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ])

        # Add alternating row colors
        for i in range(1, len(processed_data)):
            if i % 2 == 0:
                table_style.add('BACKGROUND', (0, i), (-1, i), colors.lightgrey)

        table.setStyle(table_style)
        story.append(table)

        # Add footer with date and page number
        def add_page_number(canvas, doc):
            canvas.saveState()
            canvas.setFont('Arabic', 9)

            # Add date
            date_text = arabic_text(f"تاريخ الطباعة: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            canvas.drawString(doc.leftMargin, doc.bottomMargin - 20, date_text)

            # Add page number - use ReportLab's page number mechanism
            # canvas.getPageNumber() is the current page number
            page_num = canvas.getPageNumber()
            text = f"صفحة {page_num}"
            page_text = arabic_text(text)
            canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, doc.bottomMargin - 20, page_text)

            canvas.restoreState()

        # Build the PDF with page number support

        # Create a custom canvas maker that supports page numbering
        def page_number_canvas(canvas, doc):
            canvas.saveState()
            add_page_number(canvas, doc)
            canvas.restoreState()

        # Build the document with page number support
        doc.build(story, onFirstPage=page_number_canvas, onLaterPages=page_number_canvas)

        return path

    def _generate_pdf_cash_flow(self, title, subtitle, summary_data, account_data):
        """Generate a PDF cash flow report with multiple tables"""
        # Create a temporary file in the configured temp folder
        temp_folder = current_app.config['TEMP_FOLDER']
        os.makedirs(temp_folder, exist_ok=True)

        # Generate a unique filename
        filename = f"report_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}.pdf"
        path = os.path.join(temp_folder, filename)

        # Make sure the file doesn't exist (just in case)
        if os.path.exists(path):
            os.remove(path)

        # Create the PDF document
        doc = SimpleDocTemplate(
            path,
            pagesize=landscape(A4),
            rightMargin=30,
            leftMargin=30,
            topMargin=30,
            bottomMargin=30
        )

        # Build the story
        story = []

        # Add logo if available
        logo_path = os.path.join(current_app.root_path, 'static', 'uploads', 'images', 'katilo.png')
        if os.path.exists(logo_path):
            img = Image(logo_path, width=100, height=100)
            img.hAlign = 'CENTER'
            story.append(img)
            story.append(Spacer(1, 10))

        # Add title and subtitle
        story.append(Paragraph(arabic_text(title), self.styles['ArabicTitle']))
        story.append(Paragraph(arabic_text(subtitle), self.styles['ArabicHeader']))
        story.append(Spacer(1, 20))

        # Process summary data for Arabic text
        processed_summary = []
        for row in summary_data:
            processed_row = [arabic_text(cell) for cell in row]
            processed_summary.append(processed_row)

        # Create summary table
        summary_table = Table(processed_summary, repeatRows=1)

        # Add summary table style
        summary_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'ArabicBold'),
            ('FONTNAME', (0, 1), (-1, -1), 'ArabicBold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('FONTSIZE', (0, 1), (-1, 1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, 1), colors.lightblue),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ])

        summary_table.setStyle(summary_style)
        story.append(summary_table)
        story.append(Spacer(1, 20))

        # Add account balances title
        story.append(Paragraph(arabic_text("أرصدة الحسابات"), self.styles['ArabicHeader']))
        story.append(Spacer(1, 10))

        # Process account data for Arabic text
        processed_account_data = []
        for row in account_data:
            processed_row = [arabic_text(cell) for cell in row]
            processed_account_data.append(processed_row)

        # Create account table
        account_table = Table(processed_account_data, repeatRows=1)

        # Add account table style
        account_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'ArabicBold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Arabic'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ])

        # Add alternating row colors
        for i in range(1, len(processed_account_data)):
            if i % 2 == 0:
                account_style.add('BACKGROUND', (0, i), (-1, i), colors.lightgrey)

        account_table.setStyle(account_style)
        story.append(account_table)

        # Add footer with date and page number
        def add_page_number(canvas, doc):
            canvas.saveState()
            canvas.setFont('Arabic', 9)

            # Add date
            date_text = arabic_text(f"تاريخ الطباعة: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            canvas.drawString(doc.leftMargin, doc.bottomMargin - 20, date_text)

            # Add page number - use ReportLab's page number mechanism
            # canvas.getPageNumber() is the current page number
            page_num = canvas.getPageNumber()
            text = f"صفحة {page_num}"
            page_text = arabic_text(text)
            canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, doc.bottomMargin - 20, page_text)

            canvas.restoreState()

        # Build the PDF with page number support
        # Create a custom canvas maker that supports page numbering
        def page_number_canvas(canvas, doc):
            canvas.saveState()
            add_page_number(canvas, doc)
            canvas.restoreState()

        # Build the document with page number support
        doc.build(story, onFirstPage=page_number_canvas, onLaterPages=page_number_canvas)

        return path

    def _generate_pdf_with_summary(self, title, subtitle, data, summary_data):
        """Generate a PDF report with a summary section"""
        # Create a temporary file in the configured temp folder
        temp_folder = current_app.config['TEMP_FOLDER']
        os.makedirs(temp_folder, exist_ok=True)

        # Generate a unique filename
        filename = f"report_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}.pdf"
        path = os.path.join(temp_folder, filename)

        # Make sure the file doesn't exist (just in case)
        if os.path.exists(path):
            os.remove(path)

        # Create the PDF document
        doc = SimpleDocTemplate(
            path,
            pagesize=landscape(A4),
            rightMargin=30,
            leftMargin=30,
            topMargin=30,
            bottomMargin=30
        )

        # Build the story
        story = []

        # Add logo if available
        logo_path = os.path.join(current_app.root_path, 'static', 'uploads', 'images', 'katilo.png')
        if os.path.exists(logo_path):
            img = Image(logo_path, width=100, height=100)
            img.hAlign = 'CENTER'
            story.append(img)
            story.append(Spacer(1, 10))

        # Add title and subtitle
        story.append(Paragraph(arabic_text(title), self.styles['ArabicTitle']))
        story.append(Paragraph(arabic_text(subtitle), self.styles['ArabicHeader']))
        story.append(Spacer(1, 10))

        # Process data for Arabic text
        processed_data = []
        for row in data:
            processed_row = [arabic_text(cell) for cell in row]
            processed_data.append(processed_row)

        # Create table
        table = Table(processed_data, repeatRows=1)

        # Add table style
        table_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'ArabicBold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Arabic'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ])

        # Add alternating row colors
        for i in range(1, len(processed_data)):
            if i % 2 == 0:
                table_style.add('BACKGROUND', (0, i), (-1, i), colors.lightgrey)

        table.setStyle(table_style)
        story.append(table)
        story.append(Spacer(1, 20))

        # Add summary title
        story.append(Paragraph(arabic_text("ملخص"), self.styles['ArabicHeader']))
        story.append(Spacer(1, 10))

        # Process summary data for Arabic text
        processed_summary = []
        for row in summary_data:
            processed_row = [arabic_text(cell) for cell in row]
            processed_summary.append(processed_row)

        # Create summary table
        summary_table = Table(processed_summary, repeatRows=1)

        # Add summary table style
        summary_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'ArabicBold'),
            ('FONTNAME', (0, 1), (-1, -1), 'ArabicBold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, 1), colors.lightblue),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ])

        summary_table.setStyle(summary_style)
        story.append(summary_table)

        # Add footer with date and page number
        def add_page_number(canvas, doc):
            canvas.saveState()
            canvas.setFont('Arabic', 9)

            # Add date
            date_text = arabic_text(f"تاريخ الطباعة: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            canvas.drawString(doc.leftMargin, doc.bottomMargin - 20, date_text)

            # Add page number - use ReportLab's page number mechanism
            # canvas.getPageNumber() is the current page number
            page_num = canvas.getPageNumber()
            text = f"صفحة {page_num}"
            page_text = arabic_text(text)
            canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, doc.bottomMargin - 20, page_text)

            canvas.restoreState()

        # Build the PDF with page number support
        # Create a custom canvas maker that supports page numbering
        def page_number_canvas(canvas, doc):
            canvas.saveState()
            add_page_number(canvas, doc)
            canvas.restoreState()

        # Build the document with page number support
        doc.build(story, onFirstPage=page_number_canvas, onLaterPages=page_number_canvas)

        return path

    def _generate_excel_report(self, title, subtitle, data):
        """Generate a generic Excel report"""
        # Create a temporary file in the configured temp folder
        temp_folder = current_app.config['TEMP_FOLDER']
        os.makedirs(temp_folder, exist_ok=True)

        # Generate a unique filename
        filename = f"report_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}.xlsx"
        path = os.path.join(temp_folder, filename)

        # Make sure the file doesn't exist (just in case)
        if os.path.exists(path):
            os.remove(path)

        # Create Excel workbook
        workbook = xlsxwriter.Workbook(path)
        worksheet = workbook.add_worksheet()

        # Add formats
        title_format = workbook.add_format({
            'bold': True,
            'font_size': 16,
            'align': 'center',
            'valign': 'vcenter'
        })

        subtitle_format = workbook.add_format({

            'font_size': 14,
            'align': 'center',
            'valign': 'vcenter'
        })

        header_format = workbook.add_format({
            'bold': True,
            'font_size': 12,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#4F81BD',
            'font_color': 'white',
            'border': 1
        })

        cell_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })

        alt_row_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#E6E6E6',
            'border': 1
        })

        # Set RTL mode for Arabic
        worksheet.right_to_left()

        # Add title and subtitle
        worksheet.merge_range('A1:F1', title, title_format)
        worksheet.merge_range('A2:F2', subtitle, subtitle_format)

        # Add data
        for row_idx, row in enumerate(data):
            for col_idx, cell in enumerate(row):
                if row_idx == 0:  # Header row
                    worksheet.write(row_idx + 3, col_idx, cell, header_format)
                else:
                    format_to_use = alt_row_format if row_idx % 2 == 0 else cell_format
                    worksheet.write(row_idx + 3, col_idx, cell, format_to_use)

        # Auto-fit columns
        for col_idx in range(len(data[0])):
            max_width = max(len(str(data[row_idx][col_idx])) for row_idx in range(len(data)))
            worksheet.set_column(col_idx, col_idx, max_width + 2)

        # Add logo if available
        logo_path = os.path.join(current_app.root_path, 'static', 'uploads', 'images', 'katilo.png')
        if os.path.exists(logo_path):
            worksheet.insert_image('D1', logo_path, {'x_offset': 10, 'y_offset': 10, 'x_scale': 0.5, 'y_scale': 0.5})

        # Add footer
        footer_row = len(data) + 5
        worksheet.merge_range(f'A{footer_row}:F{footer_row}',
                             f"تاريخ الطباعة: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                             subtitle_format)

        workbook.close()
        return path

    def _generate_excel_cash_flow(self, title, subtitle, summary_data, account_data):
        """Generate an Excel cash flow report with multiple tables"""
        # Create a temporary file in the configured temp folder
        temp_folder = current_app.config['TEMP_FOLDER']
        os.makedirs(temp_folder, exist_ok=True)

        # Generate a unique filename
        filename = f"report_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}.xlsx"
        path = os.path.join(temp_folder, filename)

        # Make sure the file doesn't exist (just in case)
        if os.path.exists(path):
            os.remove(path)

        # Create Excel workbook
        workbook = xlsxwriter.Workbook(path)
        worksheet = workbook.add_worksheet()

        # Add formats
        title_format = workbook.add_format({
            'bold': True,
            'font_size': 16,
            'align': 'center',
            'valign': 'vcenter'
        })

        subtitle_format = workbook.add_format({
            'font_size': 14,
            'align': 'center',
            'valign': 'vcenter'
        })

        section_title_format = workbook.add_format({
            'bold': True,
            'font_size': 14,
            'align': 'center',
            'valign': 'vcenter'
        })

        header_format = workbook.add_format({
            'bold': True,
            'font_size': 12,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#4F81BD',
            'font_color': 'white',
            'border': 1
        })

        summary_format = workbook.add_format({
            'bold': True,
            'font_size': 12,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#A5A5A5',
            'border': 1
        })

        cell_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })

        alt_row_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#E6E6E6',
            'border': 1
        })

        # Set RTL mode for Arabic
        worksheet.right_to_left()

        # Add title and subtitle
        worksheet.merge_range('A1:E1', title, title_format)
        worksheet.merge_range('A2:E2', subtitle, subtitle_format)

        # Add summary data
        worksheet.merge_range('A4:E4', 'ملخص التدفق النقدي', section_title_format)

        for row_idx, row in enumerate(summary_data):
            for col_idx, cell in enumerate(row):
                if row_idx == 0:  # Header row
                    worksheet.write(row_idx + 5, col_idx, cell, header_format)
                else:
                    worksheet.write(row_idx + 5, col_idx, cell, summary_format)

        # Add account data
        worksheet.merge_range('A8:E8', 'أرصدة الحسابات', section_title_format)

        for row_idx, row in enumerate(account_data):
            for col_idx, cell in enumerate(row):
                if row_idx == 0:  # Header row
                    worksheet.write(row_idx + 9, col_idx, cell, header_format)
                else:
                    format_to_use = alt_row_format if row_idx % 2 == 0 else cell_format
                    worksheet.write(row_idx + 9, col_idx, cell, format_to_use)

        # Auto-fit columns
        for col_idx in range(max(len(summary_data[0]), len(account_data[0]))):
            max_width = 0
            if col_idx < len(summary_data[0]):
                max_width = max(max_width, max(len(str(summary_data[row_idx][col_idx])) for row_idx in range(len(summary_data))))
            if col_idx < len(account_data[0]):
                max_width = max(max_width, max(len(str(account_data[row_idx][col_idx])) for row_idx in range(len(account_data))))
            worksheet.set_column(col_idx, col_idx, max_width + 2)

        # Add logo if available
        logo_path = os.path.join(current_app.root_path, 'static', 'uploads', 'images', 'katilo.png')
        if os.path.exists(logo_path):
            worksheet.insert_image('D1', logo_path, {'x_offset': 10, 'y_offset': 10, 'x_scale': 0.5, 'y_scale': 0.5})

        # Add footer
        footer_row = len(account_data) + 11
        worksheet.merge_range(f'A{footer_row}:E{footer_row}',
                             f"تاريخ الطباعة: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                             subtitle_format)

        workbook.close()
        return path

    def _generate_excel_with_summary(self, title, subtitle, data, summary_data):
        """Generate an Excel report with a summary section"""
        # Create a temporary file in the configured temp folder
        temp_folder = current_app.config['TEMP_FOLDER']
        os.makedirs(temp_folder, exist_ok=True)

        # Generate a unique filename
        filename = f"report_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}.xlsx"
        path = os.path.join(temp_folder, filename)

        # Make sure the file doesn't exist (just in case)
        if os.path.exists(path):
            os.remove(path)

        # Create Excel workbook
        workbook = xlsxwriter.Workbook(path)
        worksheet = workbook.add_worksheet()

        # Add formats
        title_format = workbook.add_format({
            'bold': True,
            'font_size': 16,
            'align': 'center',
            'valign': 'vcenter'
        })

        subtitle_format = workbook.add_format({
            'font_size': 14,
            'align': 'center',
            'valign': 'vcenter'
        })

        section_title_format = workbook.add_format({
            'bold': True,
            'font_size': 14,
            'align': 'center',
            'valign': 'vcenter'
        })

        header_format = workbook.add_format({
            'bold': True,
            'font_size': 12,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#4F81BD',
            'font_color': 'white',
            'border': 1
        })

        summary_header_format = workbook.add_format({
            'bold': True,
            'font_size': 12,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#4F81BD',
            'font_color': 'white',
            'border': 1
        })

        summary_format = workbook.add_format({
            'bold': True,
            'font_size': 12,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#A5A5A5',
            'border': 1
        })

        cell_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })

        alt_row_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#E6E6E6',
            'border': 1
        })

        # Set RTL mode for Arabic
        worksheet.right_to_left()

        # Add title and subtitle
        worksheet.merge_range('A1:E1', title, title_format)
        worksheet.merge_range('A2:E2', subtitle, subtitle_format)

        # Add data
        for row_idx, row in enumerate(data):
            for col_idx, cell in enumerate(row):
                if row_idx == 0:  # Header row
                    worksheet.write(row_idx + 3, col_idx, cell, header_format)
                else:
                    format_to_use = alt_row_format if row_idx % 2 == 0 else cell_format
                    worksheet.write(row_idx + 3, col_idx, cell, format_to_use)

        # Add summary section
        summary_start_row = len(data) + 5
        worksheet.merge_range(f'A{summary_start_row}:E{summary_start_row}', 'ملخص', section_title_format)

        for row_idx, row in enumerate(summary_data):
            for col_idx, cell in enumerate(row):
                if row_idx == 0:  # Header row
                    worksheet.write(summary_start_row + row_idx + 1, col_idx, cell, summary_header_format)
                else:
                    worksheet.write(summary_start_row + row_idx + 1, col_idx, cell, summary_format)

        # Auto-fit columns
        for col_idx in range(max(len(data[0]), len(summary_data[0]))):
            max_width = 0
            if col_idx < len(data[0]):
                max_width = max(max_width, max(len(str(data[row_idx][col_idx])) for row_idx in range(len(data))))
            if col_idx < len(summary_data[0]):
                max_width = max(max_width, max(len(str(summary_data[row_idx][col_idx])) for row_idx in range(len(summary_data))))
            worksheet.set_column(col_idx, col_idx, max_width + 2)

        # Add logo if available
        logo_path = os.path.join(current_app.root_path, 'static', 'uploads', 'images', 'katilo.png')
        if os.path.exists(logo_path):
            worksheet.insert_image('D1', logo_path, {'x_offset': 10, 'y_offset': 10, 'x_scale': 0.5, 'y_scale': 0.5})

        # Add footer
        footer_row = summary_start_row + len(summary_data) + 3
        worksheet.merge_range(f'A{footer_row}:E{footer_row}',
                             f"تاريخ الطباعة: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                             subtitle_format)

        workbook.close()
        return path
