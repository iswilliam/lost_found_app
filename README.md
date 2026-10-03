# NOUN Lost and Found Item Reporting System

A web-based Lost and Found Item Reporting System for the NOUN Opi Community
Study Centre, built with Flask and SQLite, featuring an automated
keyword-matching engine between lost and found reports.

## Setup Instructions

1. Install Python 3.10+ from https://python.org
2. Open this folder in a terminal / VS Code
3. (Optional but recommended) Create a virtual environment:
   python -m venv venv
   venv\Scripts\activate      (Windows)
   source venv/bin/activate   (Mac/Linux)
4. Install dependencies:
   pip install -r requirements.txt
5. Run the app:
   python app.py
6. Open your browser to: http://127.0.0.1:5000

On first run, the database (lostfound.db) is created automatically with a
default admin account:
   Email: admin@noun.edu.ng
   Password: admin123

## Project Structure

- app.py            -> Main Flask application (routes, logic, matching engine)
- schema.sql         -> Database table definitions
- templates/         -> HTML pages (Jinja2 templates)
- static/css/        -> Stylesheet
- static/uploads/    -> Uploaded item photos
- lostfound.db       -> SQLite database (auto-created on first run)

## Features

- User registration & login (passwords hashed with Werkzeug)
- Report lost items / report found items (with optional photo upload)
- Browse & search all items by keyword or category
- Automated keyword-matching engine (category + location + description
  overlap) that suggests possible matches automatically
- Admin dashboard to confirm or reject suggested matches
- Admin item management (close resolved reports)

## Default Admin Login

Email: admin@noun.edu.ng
Password: admin123

(Change this in a real deployment by editing the init_db() function in app.py
before first run, or by updating the password directly in the database.)
