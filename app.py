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
import io
import base64
from io import TextIOWrapper

# Database imports
import sqlite3
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename


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
    conn.execute("""
    CREATE TABLE IF NOT EXISTS attendance_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        upload_file_id INTEGER NOT NULL,   -- references user_files.id
        student_no TEXT,
        student_name TEXT,
        present INTEGER NOT NULL,          -- 1 = present, 0 = absent
        created_at TEXT NOT NULL,
        FOREIGN KEY (upload_file_id) REFERENCES user_files(id)
    )
""")

    conn.commit()
    conn.close()

init_db()

def crop_cell_to_data_uri(page, bbox, resolution=150, inset=2):
    x0, top, x1, bottom = bbox

    # Inset slightly to avoid grid lines
    x0 += inset; top += inset; x1 -= inset; bottom -= inset

    cropped = page.crop((x0, top, x1, bottom))
    img = cropped.to_image(resolution=resolution).original  # PIL Image

    present = signature_present_from_pil(img)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    return f"data:image/png;base64,{b64}", present

def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to access Attendance History.")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    return wrapped

def extract_rows_with_signature_images(pdf_path):
    def get_bbox(cell):
        # Case 1: object with .bbox
        if hasattr(cell, "bbox"):
            return cell.bbox

        # Case 2: tuple/list already (x0, top, x1, bottom)
        if isinstance(cell, (tuple, list)) and len(cell) == 4:
            return tuple(cell)

        # Case 3: dict-like cell
        if isinstance(cell, dict):
            # common keys in pdfplumber outputs
            if all(k in cell for k in ("x0", "top", "x1", "bottom")):
                return (cell["x0"], cell["top"], cell["x1"], cell["bottom"])
            # sometimes y0/y1 instead of top/bottom
            if all(k in cell for k in ("x0", "y0", "x1", "y1")):
                return (cell["x0"], cell["y0"], cell["x1"], cell["y1"])

        return None

    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]

        tables = page.find_tables()
        if not tables:
            return None

        t = tables[0]
        text_rows = t.extract()   # list of text rows
        row_objs = t.rows         # geometry rows

        out_rows = []

        for r in range(1, len(text_rows)):  # skip header
            row_text = text_rows[r]
            if not row_text or len(row_text) < 2:
                continue

            row_obj = row_objs[r]
            cells = row_obj.cells if hasattr(row_obj, "cells") else row_obj

            sig_cell = cells[-1]
            bbox = get_bbox(sig_cell)

            if bbox is None:
                # If this happens, we can print/debug what type it is
                return "Could not read signature cell bbox", 500

            # Some PDFs may return None for empty cells, so guard with "or ''"
            student_no = (row_text[0] or "").strip()
            student_name = (row_text[1] or "").strip()

            has_student_data = bool(student_no or student_name)

            sig_img, present_raw = crop_cell_to_data_uri(page, bbox)

            out_rows.append({
                "student_no": student_no,
                "student_name": student_name,
                "sig_img": sig_img,
                # Only show Yes/No if there is a student on that row
                "present": present_raw if has_student_data else None
            })
            

        return out_rows

def signature_present_from_pil(img, dark_threshold=200, min_dark_ratio=0.01):
    """
    Returns True if the image likely contains ink (signature), else False.
    dark_threshold: pixel values below this are considered 'ink' (0=black, 255=white)
    min_dark_ratio: fraction of dark pixels needed to count as present
    """
    # Convert to grayscale for a stable threshold test
    g = img.convert("L")

    # Optional: speed + smoothing (helps with noise)
    g = g.resize((max(1, g.width // 2), max(1, g.height // 2)))

    pixels = list(g.getdata())
    dark = sum(1 for p in pixels if p < dark_threshold)
    ratio = dark / max(1, len(pixels))

    return ratio >= min_dark_ratio

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

        safe_name = session_name.replace(" ", "_")
        _, ext = os.path.splitext(file.filename)

        timestamp = datetime.now().strftime('%Y-%m-%d')
        new_filename = f"{timestamp}_{safe_name}{ext}"
        save_path = os.path.join("uploads", new_filename)

        file.save(save_path)

        # Save metadata if logged in
        if session.get("user_id"):
            conn = get_db_connection()
            conn.execute(
                "INSERT INTO user_files (user_id, type, label, filename, created_at) VALUES (?, ?, ?, ?, ?)",
                (session["user_id"], "upload", session_name, new_filename, datetime.now().isoformat())
            )
            conn.commit()
            conn.close()

        # Extract table + signature images
        rows = extract_rows_with_signature_images(save_path)
        # Save attendance records if logged in
        if session.get("user_id") and rows:
            conn = get_db_connection()

            # Find the upload id you just inserted (better: keep lastrowid when inserting user_files)
            upload_row = conn.execute(
                "SELECT id FROM user_files WHERE user_id = ? AND type = 'upload' AND filename = ?",
                (session["user_id"], new_filename)
            ).fetchone()

            if upload_row:
                upload_id = upload_row["id"]

                for r in rows:
                    # skip blank rows
                    if not r["student_no"] and not r["student_name"]:
                        continue

                    # present might be None for blank rows, so force 0/1 for real students
                    present_val = 1 if r["present"] else 0

                    conn.execute("""
                        INSERT INTO attendance_records
                        (upload_file_id, student_no, student_name, present, created_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        upload_id,
                        r["student_no"],
                        r["student_name"],
                        present_val,
                        datetime.now().isoformat()
                    ))

                conn.commit()

            conn.close()
        if rows is None:
            return "No table detected in PDF", 400

        return render_template(
            "upload_results.html",
            rows=rows,
            filename=new_filename,
            session_name=session_name
        )

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

@app.route("/history")
@login_required
def history():
    conn = get_db_connection()

    sessions = conn.execute(
        """
        SELECT id, label, created_at
        FROM user_files
        WHERE user_id = ? AND type = 'upload'
        ORDER BY created_at DESC
        """,
        (session["user_id"],)
    ).fetchall()

    conn.close()

    return render_template("history.html", sessions=sessions)

@app.route("/history/<int:upload_id>")
@login_required
def view_history(upload_id):
    conn = get_db_connection()

    records = conn.execute(
        """
        SELECT student_no, student_name, present
        FROM attendance_records
        WHERE upload_file_id = ?
        """,
        (upload_id,)
    ).fetchall()

    conn.close()

    if not records:
        return "No attendance data found.", 404

    present_students = [r for r in records if r["present"] == 1]
    absent_students = [r for r in records if r["present"] == 0]

    return render_template(
        "history_detail.html",
        present_students=present_students,
        absent_students=absent_students,
        total=len(records),
        present_count=len(present_students)
    )

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

    rows = extract_rows_with_signature_images(file_path)
    if rows is None:
        return "No table detected in PDF", 400

    return render_template(
        "upload_results.html",
        rows=rows,
        filename=filename,
        session_name="Saved Session"
    )

@app.route("/delete/<int:file_id>", methods=["POST"])
def delete_file(file_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    conn = get_db_connection()

    # Only allow deleting files that belong to the logged-in user
    file_row = conn.execute(
        "SELECT id, user_id, type, filename FROM user_files WHERE id = ?",
        (file_id,)
    ).fetchone()

    if file_row is None:
        conn.close()
        return "File not found", 404

    if file_row["user_id"] != session["user_id"]:
        conn.close()
        return "Unauthorized", 403

    # Work out folder based on type
    if file_row["type"] == "upload":
        folder = "uploads"
    elif file_row["type"] == "template":
        folder = "generated_templates"
    else:
        conn.close()
        return "Invalid file type", 400

    file_path = os.path.join(folder, file_row["filename"])

    # Delete DB row first (so UI updates even if file already missing)
    conn.execute("DELETE FROM user_files WHERE id = ?", (file_id,))
    conn.commit()
    conn.close()

    # Then try delete the file from disk (ignore if already gone)
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        # Optional: log it
        print("Error deleting file:", e)

    flash("File deleted.")
    return redirect(url_for("profile"))

# --- Run the Flask App ---
if __name__ == '__main__':
    app.run(debug=True)
