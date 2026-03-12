# Attendance Portal

A Flask-based attendance processing platform that combines traditional handwritten attendance sheets with automated digital verification and storage.

The system allows educators to make structured attendance templates, collect handwritten signatures in class, and then upload the completed sheet for automated extraction and verification. Signature similarity techniques are used to compare uploaded signatures with stored reference signatures, enabling automated attendance validation.

This project demonstrates how manual attendance workflows can be enhanced through structured document processing, computer vision techniques, and database-backed digital record keeping.

---

## Features

- Generate structured attendance sheet templates
- Import class lists using CSV
- Download printable PDF attendance sheets
- Upload completed attendance sheets
- Automatically extract student data from uploaded PDFs
- Detect and isolate signature regions
- Compare signatures against stored reference signatures
- Calculate similarity scores using perceptual hashing
- Store attendance records in a database
- View attendance history and previously uploaded sessions

---

## Technologies Used

- Python
- Flask
- OpenCV
- NumPy
- PDFPlumber
- ReportLab
- Pillow
- SQLite
- Bootstrap

---

## Setup Instructions

### 0. Recommended to use python 3.12 as thats what was used while creating

### 1. Clone the Repository

```bash
git clone https://github.com/Alex-McGrath/attendance-portal.git
cd attendance-portal
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
```

### 3. Activate the Virtual Environment

**Windows**

```bash
venv\Scripts\activate
```

**Mac / Linux**

```bash
source venv/bin/activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Run the Application

```bash
python app.py
```

or

```bash
py app.py
```

### 6. Open the Web Interface

Navigate to:

```
http://127.0.0.1:5000
```

The application will now be running locally and accessible through your browser.

---

## Project Structure

```
attendance-portal/
│
├── app.py
├── requirements.txt
├── app.db
│
├── templates/
│
├── uploads/
├── generated_templates/
├── known_sigs/
├── sig_uploads/
│
└── sampleCSVs/
```

---

## Academic Context

This system was developed as part of a final year computer science project exploring hybrid attendance recording systems that combines manual signature collection with automated digital processing and verification.
