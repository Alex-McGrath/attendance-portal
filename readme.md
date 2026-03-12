# Attendance Portal

A Flask-based attendance processing platform that combines traditional handwritten attendance sheets with automated digital verification and storage.

The system allows educators to make structured attendance templates, collect handwritten signatures in class, and then upload the completed sheet for automated extraction and verification. Signature similarity techniques are used to compare uploaded signatures with stored reference signatures, enabling automated attendance validation.

This project demonstrates how manual attendance workflows can be enhanced through structured document processing, computer vision techniques, and database-backed digital record keeping.

Example files can be found in the sampleCSVs directories.
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

### 0. Recommended Python  Version

**3.12** as thats what was used while in development

---

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


## Using the System

After launching the application:

- Create a new account using the Register page.

- Log in with your newly created account.

- Generate a structured attendance template.

- Print the generated template and collect signatures during a class session.

- Upload the completed attendance sheet through the Upload Sheet page.

The system will extract student information, isolate signature regions, and perform signature verification.


### Example Data for Testing

The repository includes several example files that can be used to demonstrate the system workflow.

**Example CSV File**
A sample CSV file containing student numbers and names is provided. This file can be uploaded when generating a new attendance template to automatically populate the student list.

**Example Reference Signatures**
Sample reference signatures are included and can be used during the signature enrolment process. These allow the system to perform signature verification during testing.

**Example Populated Attendance Sheet**
A sample completed attendance sheet is included to demonstrate the upload and processing pipeline. This file can be uploaded through the *Upload Sheet* page to test table extraction and signature verification.

These files are provided purely for demonstration purposes to allow the system to be tested without creating new data.

## Runtime Files and Database

When the system runs, several runtime files and directories may be created automatically.

These include:

- `app.db`
- `uploads/`
- `generated_templates/`
- `sig_uploads/`
- `known_sigs/`

These files store:

- user accounts
- uploaded attendance sheets
- generated templates
- enrolled signature images
- processed attendance records

These files are **not included in version control** and will be generated automatically when the application runs.

---

### Resetting the System

If you wish to reset the system to a clean state, delete the `app.db` database file and restart the application. A new database will be created automatically.

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

This system was developed as part of final year computer science project exploring hybrid attendance recording systems that combines manual signature collection with automated digital processing and verification.
