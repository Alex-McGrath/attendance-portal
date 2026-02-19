from flask import Flask, render_template, request, send_file, redirect, url_for, session, flash
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import os
import csv
import pdfplumber
from io import TextIOWrapper

# Database imports
import sqlite3
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash


# --- Flask Setup ---
app = Flask(__name__)

#more database preconditions
app.secret_key = "dev-secret-change-this-later"
DB_PATH = "app.db"


# Ensure folders exist
os.makedirs("generated_templates", exist_ok=True)
os.makedirs("uploads", exist_ok=True)


# database helper functions - AI Assisted -
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS user_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        type TEXT NOT NULL,            -- 'upload' or 'template'
        label TEXT NOT NULL,           -- e.g. CS262
        filename TEXT NOT NULL,        -- saved file name
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
""")

    conn.commit()
    conn.close()

init_db()

# --- ROUTES ---

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm") or ""

        if not username or not password:
            flash("Username and password are required.")
            return render_template("register.html")

        if len(username) < 3:
            flash("Username must be at least 3 characters.")
            return render_template("register.html")

        if len(password) < 6:
            flash("Password must be at least 6 characters.")
            return render_template("register.html")

        if password != confirm:
            flash("Passwords do not match.")
            return render_template("register.html")

        password_hash = generate_password_hash(password)

        try:
            conn = get_db_connection()
            cur = conn.execute(
                "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                (username, password_hash, datetime.now().isoformat())
            )
            conn.commit()

            user_id = cur.lastrowid
            conn.close()

            # Auto log-in after register
            session["user_id"] = user_id
            session["username"] = username

            return redirect(url_for("home"))

        except sqlite3.IntegrityError:
            flash("That username is already taken.")
            return render_template("register.html")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()
        conn.close()

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Invalid username or password.")
            return render_template("login.html")

        session["user_id"] = user["id"]
        session["username"] = user["username"]

        return redirect(url_for("home"))

    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("home"))




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
        session_name = (request.form.get("session_name") or "").strip()

        if not session_name:
            return "Session name is required", 400

        file = request.files.get('file')

        if not file or file.filename == "":
            return "No file selected", 400
        
        # Save uploaded file
        # Clean session name for filename use
        safe_name = session_name.replace(" ", "_")

        # Keep original file extension
        _, ext = os.path.splitext(file.filename)

        timestamp = datetime.now().strftime('%Y-%m-%d')

        new_filename = f"{timestamp}_{safe_name}{ext}"
        save_path = os.path.join("uploads", new_filename)

        file.save(save_path)
        if session.get("user_id"):
            conn = get_db_connection()
            conn.execute(
                "INSERT INTO user_files (user_id, type, label, filename, created_at) VALUES (?, ?, ?, ?, ?)",
                (session["user_id"], "upload", session_name, new_filename, datetime.now().isoformat())
            )
            conn.commit()
            conn.close()


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
        return render_template(
            "upload_results.html",
            rows=extracted_rows,
            filename=new_filename,  
            session_name=session_name
        )


    # GET request -> show upload page
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

@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    conn = get_db_connection()
    uploads = conn.execute(
        """
        SELECT id, label, filename, created_at
        FROM user_files
        WHERE user_id = ? AND type = 'upload'
        ORDER BY created_at DESC
        """,
        (session["user_id"],)
    ).fetchall()

    templates = conn.execute(
        """
        SELECT id, label, filename, created_at
        FROM user_files
        WHERE user_id = ? AND type = 'template'
        ORDER BY created_at DESC
        """,
        (session["user_id"],)
    ).fetchall()

    conn.close()

    return render_template("profile.html", uploads=uploads, templates=templates)

@app.route("/files/<file_type>/<path:filename>")
def download_saved_file(file_type, filename):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    if file_type == "upload":
        folder = "uploads"
    elif file_type == "template":
        folder = "generated_templates"
    else:
        return "Invalid file type", 400

    file_path = os.path.join(folder, filename)

    if not os.path.exists(file_path):
        return "File not found", 404

    return send_file(file_path, as_attachment=True)

@app.route("/view/upload/<path:filename>")
def view_uploaded_file(filename):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    file_path = os.path.join("uploads", filename)

    if not os.path.exists(file_path):
        return "File not found", 404

    extracted_rows = []

    with pdfplumber.open(file_path) as pdf:
        page = pdf.pages[0]
        table = page.extract_table()

        if table:
            extracted_rows = table
        else:
            return "No table detected in PDF", 400

    return render_template(
        "upload_results.html",
        rows=extracted_rows,
        filename=filename,
        session_name="Saved Session"
    )


# --- Run the Flask App ---
if __name__ == '__main__':
    app.run(debug=True)
