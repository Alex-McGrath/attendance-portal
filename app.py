from flask import Flask, render_template, request, send_file
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from datetime import datetime
import os
import csv
import pdfplumber
from io import TextIOWrapper

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

    # Add 30empty rows
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


@app.route('/upload', methods=['GET', 'POST'])
def upload_sheet():
    if request.method == 'POST':
        file = request.files.get('file')

        if not file or file.filename == "":
            return "No file selected", 400
        
        # Save uploaded file
        save_path = os.path.join("uploads", file.filename)
        file.save(save_path)

        # --- Extract table using pdfplumber ---
        extracted_rows = []

        with pdfplumber.open(save_path) as pdf:
            page = pdf.pages[0]  # first page only for now
            table = page.extract_table()

            if table:
                # Remove header row from PDF if needed
                # or keep it if you'd like
                extracted_rows = table
            else:
                return "No table detected in PDF", 400

        # Pass the extracted rows to a results page
        return render_template("upload_results.html", rows=extracted_rows, filename=file.filename)

    # GET request → show upload page
    return render_template('upload.html')



@app.route('/create-template', methods=['GET', 'POST'])
def create_template():
    if request.method == 'POST':
        class_name = request.form.get('class_name')
        date = request.form.get('date') or datetime.now().strftime('%d/%m/%Y')

        # Headings logic
        headings_input = request.form.get('headings', '').strip()
        if headings_input:
            headings = [h.strip() for h in headings_input.split(',') if h.strip()]
        else:
            headings = ["Student Number", "Student Name (Block Caps)", "Signature"]

        # Row number logic
        row_number = request.form.get('row_number')
        try:
            row_number = int(row_number)
        except (TypeError, ValueError):
            row_number = 30  # Default

        # --- NEW: CSV Upload Handling ---
        csv_file = request.files.get('csv_file')
        csv_rows = []

        if csv_file and csv_file.filename.endswith('.csv'):
            csv_stream = TextIOWrapper(csv_file, encoding='utf-8')
            reader = csv.reader(csv_stream)

            for row in reader:
                # Skip empty rows
                if not row or len(row) < 2:
                    continue

                # Skip header row automatically
                if "student" in row[0].lower():
                    continue

                student_id = row[0].strip()
                student_name = row[1].strip()
                csv_rows.append([student_id, student_name])

        # --- Build Table Data ---
        data = [headings]

        # Insert CSV rows first
        for student_id, student_name in csv_rows:
            row_data = []
            for h in headings:
                h_lower = h.lower()
                if "student" in h_lower and "number" in h_lower:
                    row_data.append(student_id)
                elif "name" in h_lower:
                    row_data.append(student_name)
                else:
                    row_data.append("")  # e.g., Signature column
            data.append(row_data)

        # Fill remaining rows after CSV rows
        remaining = row_number - len(csv_rows)
        for _ in range(max(0, remaining)):
            data.append(["" for _ in headings])

        # PDF Output Path
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

        # Table creation
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

    return render_template('create_template.html')


# --- Run the Flask App ---
if __name__ == '__main__':
    app.run(debug=True)
