import sqlite3
import os
import re
from datetime import datetime
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, g
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(APP_DIR, "lostfound.db")
UPLOAD_FOLDER = os.path.join(APP_DIR, "static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

app = Flask(__name__)
app.config["SECRET_KEY"] = "noun-lostfound-dev-secret-key-change-in-production"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

ITEM_CATEGORIES = [
    "Electronics", "Documents (ID Card, Certificate, etc.)", "Bags",
    "Books/Study Materials", "Clothing/Accessories", "Keys", "Wallet/Purse",
    "Jewelry", "Other"
]


# ---------- Database helpers ----------

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def init_db():
    with app.app_context():
        db = get_db()
        with open(os.path.join(APP_DIR, "schema.sql")) as f:
            db.executescript(f.read())
        # create a default admin account: admin@noun.edu.ng / admin123
        db.execute(
            "INSERT INTO users (full_name, email, phone, password, role) VALUES (?, ?, ?, ?, ?)",
            ("System Administrator", "admin@noun.edu.ng", "08000000000",
             generate_password_hash("admin123"), "admin")
        )
        db.commit()
        print("Database initialized with default admin account:")
        print("  Email: admin@noun.edu.ng")
        print("  Password: admin123")


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ---------- Auth helpers ----------

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("role") != "admin":
            flash("Admin access required.", "danger")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated


# ---------- Keyword matching engine ----------

STOPWORDS = {
    "a", "an", "the", "is", "was", "it", "my", "our", "with", "of", "in",
    "on", "at", "to", "and", "for", "has", "have", "had", "this", "that"
}


def tokenize(text):
    words = re.findall(r"[a-zA-Z0-9]+", (text or "").lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 1}


def compute_match_score(lost, found):
    """
    Simple weighted keyword-matching engine:
    - Category match: 40%
    - Location keyword overlap: 20%
    - Description keyword overlap: 40%
    """
    score = 0.0

    if lost["category"] == found["category"]:
        score += 0.4

    loc_lost = tokenize(lost["location_lost"])
    loc_found = tokenize(found["location_found"])
    if loc_lost and loc_found:
        overlap = len(loc_lost & loc_found) / max(len(loc_lost | loc_found), 1)
        score += 0.2 * overlap

    desc_lost = tokenize(lost["item_name"] + " " + lost["description"])
    desc_found = tokenize(found["item_name"] + " " + found["description"])
    if desc_lost and desc_found:
        overlap = len(desc_lost & desc_found) / max(len(desc_lost | desc_found), 1)
        score += 0.4 * overlap

    return round(score, 2)


def run_matching_engine():
    """Scan all unresolved lost/found items and (re)compute matches above threshold."""
    db = get_db()
    lost_items = db.execute(
        "SELECT * FROM lost_items WHERE status = 'unresolved'"
    ).fetchall()
    found_items = db.execute(
        "SELECT * FROM found_items WHERE status = 'unresolved'"
    ).fetchall()

    THRESHOLD = 0.5
    new_matches = 0

    for lost in lost_items:
        for found in found_items:
            score = compute_match_score(lost, found)
            if score >= THRESHOLD:
                existing = db.execute(
                    "SELECT * FROM matches WHERE lost_id = ? AND found_id = ?",
                    (lost["lost_id"], found["found_id"])
                ).fetchone()
                if not existing:
                    db.execute(
                        "INSERT INTO matches (lost_id, found_id, match_score, status) "
                        "VALUES (?, ?, ?, 'pending')",
                        (lost["lost_id"], found["found_id"], score)
                    )
                    new_matches += 1
    db.commit()
    return new_matches


# ---------- Routes: public ----------

@app.route("/")
def index():
    db = get_db()
    recent_lost = db.execute(
        "SELECT * FROM lost_items ORDER BY date_reported DESC LIMIT 4"
    ).fetchall()
    recent_found = db.execute(
        "SELECT * FROM found_items ORDER BY date_reported DESC LIMIT 4"
    ).fetchall()
    stats = {
        "lost_count": db.execute("SELECT COUNT(*) c FROM lost_items").fetchone()["c"],
        "found_count": db.execute("SELECT COUNT(*) c FROM found_items").fetchone()["c"],
        "matched_count": db.execute(
            "SELECT COUNT(*) c FROM matches WHERE status = 'confirmed'"
        ).fetchone()["c"],
    }
    return render_template("index.html", recent_lost=recent_lost,
                            recent_found=recent_found, stats=stats)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form["full_name"].strip()
        email = request.form["email"].strip().lower()
        phone = request.form["phone"].strip()
        password = request.form["password"]
        confirm = request.form["confirm_password"]

        if not full_name or not email or not phone or not password:
            flash("Please fill in all fields.", "danger")
            return redirect(url_for("register"))
        if password != confirm:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("register"))

        db = get_db()
        existing = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            flash("An account with that email already exists.", "danger")
            return redirect(url_for("register"))

        db.execute(
            "INSERT INTO users (full_name, email, phone, password, role) VALUES (?, ?, ?, ?, 'user')",
            (full_name, email, phone, generate_password_hash(password))
        )
        db.commit()
        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["user_id"]
            session["full_name"] = user["full_name"]
            session["role"] = user["role"]
            flash(f"Welcome back, {user['full_name']}!", "success")
            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("index"))
        else:
            flash("Invalid email or password.", "danger")
            return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


# ---------- Routes: report lost / found ----------

@app.route("/report/lost", methods=["GET", "POST"])
@login_required
def report_lost():
    if request.method == "POST":
        item_name = request.form["item_name"].strip()
        category = request.form["category"]
        description = request.form["description"].strip()
        location_lost = request.form["location_lost"].strip()
        date_lost = request.form["date_lost"]

        image_path = None
        file = request.files.get("image")
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(
                f"lost_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
            )
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            image_path = filename

        db = get_db()
        db.execute(
            "INSERT INTO lost_items (user_id, item_name, category, description, "
            "location_lost, date_lost, image_path) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (session["user_id"], item_name, category, description,
             location_lost, date_lost, image_path)
        )
        db.commit()
        run_matching_engine()
        flash("Lost item reported successfully. We'll notify you of any matches.", "success")
        return redirect(url_for("browse"))

    return render_template("report_lost.html", categories=ITEM_CATEGORIES)


@app.route("/report/found", methods=["GET", "POST"])
@login_required
def report_found():
    if request.method == "POST":
        item_name = request.form["item_name"].strip()
        category = request.form["category"]
        description = request.form["description"].strip()
        location_found = request.form["location_found"].strip()
        date_found = request.form["date_found"]

        image_path = None
        file = request.files.get("image")
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(
                f"found_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
            )
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            image_path = filename

        db = get_db()
        db.execute(
            "INSERT INTO found_items (user_id, item_name, category, description, "
            "location_found, date_found, image_path) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (session["user_id"], item_name, category, description,
             location_found, date_found, image_path)
        )
        db.commit()
        run_matching_engine()
        flash("Found item reported successfully. Thank you for helping reunite it!", "success")
        return redirect(url_for("browse"))

    return render_template("report_found.html", categories=ITEM_CATEGORIES)


# ---------- Routes: browse / search ----------

@app.route("/browse")
def browse():
    db = get_db()
    item_type = request.args.get("type", "all")
    category = request.args.get("category", "")
    keyword = request.args.get("q", "")

    lost_items, found_items = [], []

    if item_type in ("all", "lost"):
        query = "SELECT * FROM lost_items WHERE status != 'closed'"
        params = []
        if category:
            query += " AND category = ?"
            params.append(category)
        if keyword:
            query += " AND (item_name LIKE ? OR description LIKE ? OR location_lost LIKE ?)"
            params += [f"%{keyword}%"] * 3
        query += " ORDER BY date_reported DESC"
        lost_items = db.execute(query, params).fetchall()

    if item_type in ("all", "found"):
        query = "SELECT * FROM found_items WHERE status != 'closed'"
        params = []
        if category:
            query += " AND category = ?"
            params.append(category)
        if keyword:
            query += " AND (item_name LIKE ? OR description LIKE ? OR location_found LIKE ?)"
            params += [f"%{keyword}%"] * 3
        query += " ORDER BY date_reported DESC"
        found_items = db.execute(query, params).fetchall()

    return render_template(
        "browse.html", lost_items=lost_items, found_items=found_items,
        categories=ITEM_CATEGORIES, selected_type=item_type,
        selected_category=category, keyword=keyword
    )


@app.route("/item/lost/<int:lost_id>")
def view_lost_item(lost_id):
    db = get_db()
    item = db.execute("SELECT * FROM lost_items WHERE lost_id = ?", (lost_id,)).fetchone()
    if item is None:
        flash("Item not found.", "danger")
        return redirect(url_for("browse"))
    matches = db.execute(
        "SELECT f.*, m.match_score, m.status AS match_status, m.match_id "
        "FROM matches m JOIN found_items f ON m.found_id = f.found_id "
        "WHERE m.lost_id = ? ORDER BY m.match_score DESC", (lost_id,)
    ).fetchall()
    return render_template("item_detail.html", item=item, item_kind="lost", matches=matches)


@app.route("/item/found/<int:found_id>")
def view_found_item(found_id):
    db = get_db()
    item = db.execute("SELECT * FROM found_items WHERE found_id = ?", (found_id,)).fetchone()
    if item is None:
        flash("Item not found.", "danger")
        return redirect(url_for("browse"))
    matches = db.execute(
        "SELECT l.*, m.match_score, m.status AS match_status, m.match_id "
        "FROM matches m JOIN lost_items l ON m.lost_id = l.lost_id "
        "WHERE m.found_id = ? ORDER BY m.match_score DESC", (found_id,)
    ).fetchall()
    return render_template("item_detail.html", item=item, item_kind="found", matches=matches)


# ---------- Routes: admin ----------

@app.route("/admin")
@admin_required
def admin_dashboard():
    db = get_db()
    stats = {
        "total_users": db.execute("SELECT COUNT(*) c FROM users").fetchone()["c"],
        "total_lost": db.execute("SELECT COUNT(*) c FROM lost_items").fetchone()["c"],
        "total_found": db.execute("SELECT COUNT(*) c FROM found_items").fetchone()["c"],
        "pending_matches": db.execute(
            "SELECT COUNT(*) c FROM matches WHERE status = 'pending'"
        ).fetchone()["c"],
        "confirmed_matches": db.execute(
            "SELECT COUNT(*) c FROM matches WHERE status = 'confirmed'"
        ).fetchone()["c"],
    }
    pending_matches = db.execute(
        "SELECT m.*, l.item_name AS lost_name, f.item_name AS found_name "
        "FROM matches m "
        "JOIN lost_items l ON m.lost_id = l.lost_id "
        "JOIN found_items f ON m.found_id = f.found_id "
        "WHERE m.status = 'pending' ORDER BY m.match_score DESC"
    ).fetchall()
    return render_template("admin_dashboard.html", stats=stats, pending_matches=pending_matches)


@app.route("/admin/match/<int:match_id>/<action>")
@admin_required
def admin_update_match(match_id, action):
    db = get_db()
    match = db.execute("SELECT * FROM matches WHERE match_id = ?", (match_id,)).fetchone()
    if match is None:
        flash("Match not found.", "danger")
        return redirect(url_for("admin_dashboard"))

    if action == "confirm":
        db.execute("UPDATE matches SET status = 'confirmed' WHERE match_id = ?", (match_id,))
        db.execute("UPDATE lost_items SET status = 'matched' WHERE lost_id = ?", (match["lost_id"],))
        db.execute("UPDATE found_items SET status = 'matched' WHERE found_id = ?", (match["found_id"],))
        flash("Match confirmed. Both items marked as matched.", "success")
    elif action == "reject":
        db.execute("UPDATE matches SET status = 'rejected' WHERE match_id = ?", (match_id,))
        flash("Match rejected.", "info")

    db.commit()
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/items")
@admin_required
def admin_items():
    db = get_db()
    lost_items = db.execute("SELECT * FROM lost_items ORDER BY date_reported DESC").fetchall()
    found_items = db.execute("SELECT * FROM found_items ORDER BY date_reported DESC").fetchall()
    return render_template("admin_items.html", lost_items=lost_items, found_items=found_items)


@app.route("/admin/item/<kind>/<int:item_id>/close")
@admin_required
def admin_close_item(kind, item_id):
    db = get_db()
    if kind == "lost":
        db.execute("UPDATE lost_items SET status = 'closed' WHERE lost_id = ?", (item_id,))
    elif kind == "found":
        db.execute("UPDATE found_items SET status = 'closed' WHERE found_id = ?", (item_id,))
    db.commit()
    flash("Item closed.", "info")
    return redirect(url_for("admin_items"))


def database_needs_init():
    if not os.path.exists(DATABASE):
        return True
    try:
        conn = sqlite3.connect(DATABASE)
        result = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='lost_items'"
        ).fetchone()
        conn.close()
        return result is None
    except sqlite3.Error:
        return True


if database_needs_init():
    init_db()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
