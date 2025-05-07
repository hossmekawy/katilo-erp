import os
import tempfile
import subprocess
from io import BytesIO
from datetime import datetime
from flask import current_app, render_template, send_file

class InvoicePDFGenerator:
    """
    Utility class for generating PDF invoices using wkhtmltopdf with different size options.
    Supports A4, A5, and POS (receipt) formats with appropriate styling.
    """

    def __init__(self, invoice, user=None):
        """
        Initialize the PDF generator with an invoice object.

        Args:
            invoice: The SalesInvoice object containing all invoice data
            user: The current user (optional)
        """
        self.invoice = invoice
        self.user = user
        self.wkhtmltopdf_path = os.path.abspath(os.path.join(current_app.root_path, 'pdftool', 'wkhtmltopdf', 'bin', 'wkhtmltopdf.exe'))

        # Check if wkhtmltopdf exists
        if not os.path.exists(self.wkhtmltopdf_path):
            current_app.logger.error(f"wkhtmltopdf not found at: {self.wkhtmltopdf_path}")
            # Try to find wkhtmltopdf in the system path
            import shutil
            wkhtmltopdf_in_path = shutil.which('wkhtmltopdf')
            if wkhtmltopdf_in_path:
                self.wkhtmltopdf_path = wkhtmltopdf_in_path
                current_app.logger.info(f"Using wkhtmltopdf from system path: {self.wkhtmltopdf_path}")
            else:
                current_app.logger.error("wkhtmltopdf not found in system path")
        else:
            current_app.logger.info(f"wkhtmltopdf found at: {self.wkhtmltopdf_path}")
        self.logo_path = os.path.abspath(os.path.join(current_app.root_path, 'static', 'uploads', 'images', 'katilo.png'))

    def generate_pdf(self, size='a4', download=True, auto_print=False, style=None):
        """
        Generate a PDF invoice with the specified size and style.

        Args:
            size: Paper size ('a4', 'a5', or 'pos')
            download: Whether to force download the PDF
            auto_print: Whether to set up the PDF for auto-printing
            style: Optional style variant ('card' for modern card-based design)

        Returns:
            A Flask response object with the PDF file
        """
        # Check if wkhtmltopdf is available
        if not os.path.exists(self.wkhtmltopdf_path):
            current_app.logger.error(f"wkhtmltopdf not found at: {self.wkhtmltopdf_path}")
            # Fallback to HTML view
            return render_template('sales/invoices/view.html', invoice=self.invoice)

        try:
            # Create temporary files for HTML and PDF
            fd, html_path = tempfile.mkstemp(suffix='.html')
            os.close(fd)

            fd, pdf_file_path = tempfile.mkstemp(suffix='.pdf')
            os.close(fd)

            # Prepare template data
            template_data = self._prepare_template_data()

            # Choose the appropriate template based on size and style
            if size.lower() == 'a5':
                if style == 'card':
                    template_file = 'sales/invoices/a5_card_pdf.html'
                else:
                    template_file = 'sales/invoices/a5_pdf.html'
            elif size.lower() == 'pos':
                template_file = 'sales/invoices/pos_pdf.html'
            else:  # Default to A4
                template_file = 'sales/invoices/a4_pdf.html'

            # Render the HTML template
            html_content = render_template(template_file, **template_data)

            # Write HTML content to temporary file
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

            # Set up wkhtmltopdf command with appropriate options for the selected size
            cmd = self._get_wkhtmltopdf_command(size, html_path, pdf_file_path, auto_print)

            # Execute command
            try:
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                _, stderr = process.communicate()

                if process.returncode != 0:
                    error_msg = stderr.decode() if stderr else "Unknown error"
                    current_app.logger.error(f"Error generating PDF: {error_msg}")
                    current_app.logger.error(f"Command was: {' '.join(cmd)}")
                    raise Exception(f"PDF generation failed: {error_msg}")
            except Exception as e:
                current_app.logger.error(f"Exception running wkhtmltopdf: {str(e)}")
                current_app.logger.error(f"Command was: {' '.join(cmd)}")
                raise Exception(f"PDF generation failed: {str(e)}")

            # Read the PDF file
            with open(pdf_file_path, 'rb') as f:
                pdf_content = f.read()

            # Clean up temporary files
            os.unlink(html_path)
            os.unlink(pdf_file_path)

            # Create response
            response = BytesIO(pdf_content)
            response.seek(0)

            # Determine if we should force download or display inline
            download_name = f'invoice_{self.invoice.invoice_number}.pdf'

            return send_file(
                response,
                mimetype='application/pdf',
                as_attachment=download,
                download_name=download_name
            )

        except Exception as e:
            current_app.logger.error(f"PDF generation error: {str(e)}")
            # Clean up temporary files if they exist
            if 'html_path' in locals() and os.path.exists(html_path):
                os.unlink(html_path)
            if 'pdf_file_path' in locals() and os.path.exists(pdf_file_path):
                os.unlink(pdf_file_path)
            raise

    def _prepare_template_data(self):
        """
        Prepare data for the invoice template.

        Returns:
            A dictionary with all data needed for the template
        """
        # Calculate total paid amount
        total_paid = sum(payment.amount for payment in self.invoice.payments) if self.invoice.payments else 0

        # Calculate remaining balance
        remaining_balance = self.invoice.total_amount - total_paid

        # Get company information from system settings
        from models import SystemSettings
        settings = SystemSettings.get_settings()

        company_info = {
            'name': settings.company_name,
            'address': settings.company_address,
            'city': settings.company_city,
            'email': settings.company_email,
            'phone': settings.company_phone,
            'website': settings.company_website,
            'tax_id': settings.company_tax_id,
        }

        # Get username if user is available
        user_name = self.user.username if self.user else 'Admin'

        # Calculate payment days
        payment_days = (self.invoice.due_date - self.invoice.invoice_date).days if self.invoice.due_date and self.invoice.invoice_date else 30

        # Get payment terms text from settings
        payment_terms = settings.payment_terms_text.replace('{days}', str(payment_days))

        return {
            'invoice': self.invoice,
            'company_info': company_info,
            'logo_path': self.logo_path,
            'total_paid': total_paid,
            'remaining_balance': remaining_balance,
            'payment_days': payment_days,
            'payment_terms': payment_terms,
            'current_user': self.user,
            'user_name': user_name,
            'generated_at': datetime.now()
        }

    def _get_wkhtmltopdf_command(self, size, html_path, pdf_file_path, auto_print=False):
        """
        Get the wkhtmltopdf command with appropriate options for the selected size.

        Args:
            size: Paper size ('a4', 'a5', or 'pos')
            html_path: Path to the HTML file
            pdf_file_path: Path to save the PDF file
            auto_print: Whether to set up the PDF for auto-printing

        Returns:
            A list with the command and its arguments
        """
        cmd = [
            self.wkhtmltopdf_path,
            '--enable-local-file-access',
            '--encoding', 'utf-8',
        ]

        # Add size-specific options
        if size.lower() == 'a4':
            cmd.extend([
                '--page-size', 'A4',
                '--margin-top', '10mm',
                '--margin-bottom', '10mm',
                '--margin-left', '10mm',
                '--margin-right', '10mm',
            ])
        elif size.lower() == 'a5':
            cmd.extend([
                '--page-size', 'A5',
                '--margin-top', '5mm',
                '--margin-bottom', '5mm',
                '--margin-left', '5mm',
                '--margin-right', '5mm',
            ])
        elif size.lower() == 'pos':
            # POS receipt is typically 80mm wide
            cmd.extend([
                '--page-width', '80mm',
                # Height will be determined by content
                '--page-height', '297mm',  # Default height, will adjust based on content
                '--margin-top', '2mm',
                '--margin-bottom', '2mm',
                '--margin-left', '2mm',
                '--margin-right', '2mm',
                # For POS, we use grayscale
                '--grayscale',
            ])

        # Add auto-print option if requested
        if auto_print:
            cmd.append('--javascript-delay')
            cmd.append('1000')
            cmd.append('--run-script')
            cmd.append('window.print();')

        # Add input and output files
        cmd.extend([html_path, pdf_file_path])

        # Log the command for debugging
        current_app.logger.debug(f"wkhtmltopdf command: {' '.join(cmd)}")

        return cmd
