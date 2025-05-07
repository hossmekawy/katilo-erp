# PDF Generation in Katilo ERP

This document explains how to use the PDF generation functionality in the Katilo ERP system.

## Prerequisites

The PDF generation system uses `wkhtmltopdf` to convert HTML templates to PDF files. You need to have this tool installed on your system.

### Installing wkhtmltopdf

You can run the setup script to install wkhtmltopdf automatically:

```bash
python scripts/setup_pdf_generator.py
```

Or you can install it manually:

- **Ubuntu/Debian**: `sudo apt-get install wkhtmltopdf`
- **RHEL/CentOS/Fedora**: `sudo yum install wkhtmltopdf`
- **macOS**: `brew install wkhtmltopdf`
- **Windows**: Download the installer from [wkhtmltopdf.org](https://wkhtmltopdf.org/downloads.html)

## Using the PDF Generator

The `PDFGenerator` class provides methods for generating PDF files from HTML templates.

### Basic Usage

```python
from utils.pdf_generator import PDFGenerator

# Generate a PDF from a template
pdf_path = PDFGenerator.generate_pdf(
    template_path='my_template.html',
    context={'variable1': 'value1', 'variable2': 'value2'},
    output_path='/path/to/output.pdf',
    options={'page-size': 'A4', 'margin-top': '10mm'}
)

# Generate a report with Katilo branding
pdf_path = PDFGenerator.generate_report_pdf(
    template_path='my_report_template.html',
    context={'report_data': data},
    filename='my_report.pdf'
)
```

### Creating PDF Templates

PDF templates are regular HTML templates with CSS styling. You can use all the features of HTML and CSS that are supported by wkhtmltopdf.

For consistent branding, use the standard header and footer templates:

- `templates/pdf/header.html`
- `templates/pdf/footer.html`

### Adding PDF Generation to a Route

To add PDF generation to a route, use the following pattern:

```python
@app.route('/my-report/<int:id>/pdf')
def generate_my_report_pdf(id):
    # Get data for the report
    data = get_my_report_data(id)
    
    # Generate the PDF
    pdf_path = PDFGenerator.generate_report_pdf(
        template_path='pdf/my_report_pdf.html',
        context={'data': data, 'report_title': 'My Report'},
        filename=f'my_report_{id}.pdf'
    )
    
    # Send the file to the client
    return send_file(
        pdf_path,
        as_attachment=True,
        download_name=f'my_report_{id}.pdf',
        mimetype='application/pdf'
    )
```

## Troubleshooting

If you encounter issues with PDF generation:

1. Check that wkhtmltopdf is installed and accessible in your PATH
2. Verify that your HTML template is valid and renders correctly
3. Check the application logs for error messages
4. Try running wkhtmltopdf manually to see if there are any errors:
   ```
   wkhtmltopdf input.html output.pdf
   ```

For more information, see the [wkhtmltopdf documentation](https://wkhtmltopdf.org/docs.html).
