from flask import Flask, render_template, request, send_file
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from datetime import datetime
import os

# --- Flask Setup ---
app = Flask(__name__)

# Ensure folders exist
os.makedirs("generated_templates", exist_ok=True)
os.makedirs("uploads", exist_ok=True)


# --- ROUTES ---

@app.route('/')
def home():
    return render_template('index.html')


@app.route('/download-template')
def download_template():
    file_path = "generated_templates/attendance_template.pdf"

    # Create PDF document
    pdf = SimpleDocTemplate(file_path, pagesize=A4)
    elements = []

    # Styles
    styles = getSampleStyleSheet()
    title_style = styles['Title']
    normal_style = styles['Normal']

    # Title and details
    title = Paragraph("Attendance Sheet", title_style)
    class_info = Paragraph(
        f"<b>Module Code:</b> ____________________ &nbsp;&nbsp;&nbsp;&nbsp; "
        f"<b>Date:</b> {datetime.now().strftime('%d/%m/%Y')}",
        normal_style
    )

    elements.append(title)
    elements.append(Spacer(1, 12))
    elements.append(class_info)
    elements.append(Spacer(1, 24))

    # Table data
    headers = ["Student Number", "Student Name (Block Caps)", "Signature"]
    data = [headers]

    # Add 20 empty rows
    for _ in range(30):
        data.append(["", "", ""])

    # Create table
    table = Table(data, colWidths=[150, 200, 150])

    # Table style
    style = TableStyle([
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ])

    table.setStyle(style)

    elements.append(table)

    # Build PDF
    pdf.build(elements)

    return send_file(file_path, as_attachment=True)


@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files.get('file')
    if file:
        filename = file.filename
        upload_path = os.path.join("uploads", filename)
        file.save(upload_path)
        return f"File '{filename}' uploaded successfully!"
    return "No file uploaded.", 400

@app.route('/create-template', methods=['GET', 'POST'])
def create_template():
    if request.method == 'POST':
        class_name = request.form.get('class_name')
        date = request.form.get('date') or datetime.now().strftime('%d/%m/%Y')
        headings = request.form.get('headings').split(',')
        headings_input = request.form.get('headings', '').strip()
        if headings_input:
            headings = [h.strip() for h in headings_input.split(',') if h.strip()]
        else:
            headings = ["Student Number", "Student Name (Block Caps)", "Signature"]
        row_number = request.form.get('row_number')

        try:
            row_number = int(row_number)
        except (TypeError, ValueError):
            row_number = 30 #default amount if left blank


        # Clean up headings (remove spaces)
        headings = [h.strip() for h in headings]

        # Create file path
        file_path = f"generated_templates/{class_name}_attendance_custom.pdf"

        # Create PDF
        pdf = SimpleDocTemplate(file_path, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()

        title = Paragraph("Attendance Sheet", styles['Title'])
        info = Paragraph(
            f"<b>Class:</b> {class_name} &nbsp;&nbsp;&nbsp;&nbsp; <b>Date:</b> {date}",
            styles['Normal']
        )

        elements.extend([title, Spacer(1, 12), info, Spacer(1, 24)])

        # Build table test
        data = [headings]
        for _ in range(row_number):
            data.append(["" for _ in headings])

        table = Table(data, colWidths=[A4[0] / len(headings) - 10] * len(headings))

        style = TableStyle([
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ])

        table.setStyle(style)
        elements.append(table)
        pdf.build(elements)

        return send_file(file_path, as_attachment=True)

    # If GET request — show form
    return render_template('create_template.html')

# --- Run the Flask App ---
if __name__ == '__main__':
    app.run(debug=True)
