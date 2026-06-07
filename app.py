"""
app.py — Main Flask application for the Apartment Management System
NextGen Design and Developers Ltd. & Luxury Construction
"""

import os
import uuid
from functools import wraps

from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, jsonify, abort)
import json
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

import database as db
from telegram_backup import send_backup_to_telegram

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "fallback-secret-key")

UPLOAD_FOLDER   = os.path.join(app.root_path, "static", "uploads")
ALLOWED_IMAGES  = {"png", "jpg", "jpeg", "gif", "webp"}
ALLOWED_DOCS    = {"pdf", "png", "jpg", "jpeg", "doc", "docx"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Credentials loaded from .env
CREDENTIALS = {
    "nextgen": os.getenv("NEXTGEN_PASSWORD", "NextGen@2024"),
    "luxury":  os.getenv("LUXURY_PASSWORD",  "Luxury@2024"),
}

COMPANY_DISPLAY = {
    "nextgen": "NextGen Design & Developers Ltd",
    "luxury":  "Luxury Construction",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def allowed_image(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGES


def allowed_doc(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_DOCS


def save_upload(file, subfolder=""):
    """Save an uploaded file with a unique name; return relative path for DB."""
    if not file or file.filename == "":
        return None
    directory = os.path.join(app.config["UPLOAD_FOLDER"], subfolder)
    os.makedirs(directory, exist_ok=True)
    ext      = secure_filename(file.filename).rsplit(".", 1)[-1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(directory, filename))
    return f"uploads/{subfolder}/{filename}" if subfolder else f"uploads/{filename}"


# ---------------------------------------------------------------------------
# Auth decorators
# ---------------------------------------------------------------------------

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "role" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def operator_required(f):
    """Allow only nextgen / luxury operators."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("role") not in ("nextgen", "luxury"):
            flash("Operator access required.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Context processor — inject role helpers into all templates
# ---------------------------------------------------------------------------

@app.context_processor
def inject_globals():
    return {
        "COMPANY_DISPLAY": COMPANY_DISPLAY,
        "current_role":    session.get("role"),
        "current_company": session.get("role"),
    }


# ---------------------------------------------------------------------------
# Routes — Auth
# ---------------------------------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if "role" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        role     = request.form.get("role", "").strip().lower()
        password = request.form.get("password", "").strip()

        if role in CREDENTIALS and CREDENTIALS[role] == password:
            session["role"]    = role
            session.permanent  = True
            flash(f"Welcome, {COMPANY_DISPLAY.get(role, role)}!", "success")
            db.log_audit("LOGIN", role, f"{COMPANY_DISPLAY.get(role, role)} logged in.")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials. Please try again.", "danger")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    role = session.get("role", "unknown")
    db.log_audit("LOGOUT", role, f"{COMPANY_DISPLAY.get(role, role)} logged out.")
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Routes — Dashboard
# ---------------------------------------------------------------------------

@app.route("/")
@login_required
def dashboard():
    apartments = db.get_all_apartments()
    return render_template("dashboard.html", apartments=apartments)


@app.route("/api/apartments")
@login_required
def api_apartments():
    """JSON endpoint for real-time polling."""
    return jsonify(db.get_all_apartments())


# ---------------------------------------------------------------------------
# Routes — Booking
# ---------------------------------------------------------------------------

@app.route("/book/<apt_id>", methods=["POST"])
@login_required
@operator_required
def book(apt_id):
    role = session["role"]

    apartment = db.get_apartment(apt_id)
    if not apartment:
        flash("Apartment not found.", "danger")
        return redirect(url_for("dashboard"))

    if apartment["status"] == "Booked":
        flash(f"Apartment {apt_id} is already booked.", "danger")
        return redirect(url_for("dashboard"))

    name          = request.form.get("name", "").strip()
    address       = request.form.get("address", "").strip()
    phone         = request.form.get("phone", "").strip()
    total_price   = float(request.form.get("total_price") or 0)
    booking_money = float(request.form.get("booking_money") or 0)
    due_amount    = float(request.form.get("due_amount") or 0)

    if not all([name, address, phone]):
        flash("All customer fields are required.", "danger")
        return redirect(url_for("dashboard"))

    # Handle file uploads
    profile_pic   = None
    document_path = None

    pic_file = request.files.get("profile_pic")
    if pic_file and pic_file.filename:
        if not allowed_image(pic_file.filename):
            flash("Profile picture must be an image file (PNG, JPG, GIF, WEBP).", "danger")
            return redirect(url_for("dashboard"))
        profile_pic = save_upload(pic_file, "profiles")

    doc_paths = []
    doc_files = request.files.getlist("document")
    for df in doc_files:
        if df and df.filename:
            if not allowed_doc(df.filename):
                flash("One of the documents is invalid. Must be PDF, image, DOC or DOCX.", "danger")
                return redirect(url_for("dashboard"))
            doc_paths.append(save_upload(df, "documents"))

    document_path = json.dumps(doc_paths) if doc_paths else None

    db.book_apartment(apt_id, role, name, address, phone, profile_pic, document_path, total_price, booking_money, due_amount)
    db.log_audit("BOOK", role,
                 f"Apartment {apt_id} booked by {COMPANY_DISPLAY[role]} for customer '{name}'.")

    send_backup_to_telegram(action=f"BOOK {apt_id}", performed_by=COMPANY_DISPLAY[role])
    flash(f"Apartment {apt_id} successfully booked for {name}!", "success")
    return redirect(url_for("dashboard"))


# ---------------------------------------------------------------------------
# Routes — Edit Booking
# ---------------------------------------------------------------------------

@app.route("/edit/<apt_id>", methods=["POST"])
@login_required
@operator_required
def edit(apt_id):
    role      = session["role"]
    apartment = db.get_apartment(apt_id)

    if not apartment:
        flash("Apartment not found.", "danger")
        return redirect(url_for("dashboard"))

    if apartment["status"] != "Booked":
        flash("This apartment is not currently booked.", "warning")
        return redirect(url_for("dashboard"))

    # RBAC: only the booking company can edit
    if apartment["booked_by"] != role:
        flash("You are not authorized to edit this booking.", "danger")
        return redirect(url_for("dashboard"))

    name          = request.form.get("name", "").strip()
    address       = request.form.get("address", "").strip()
    phone         = request.form.get("phone", "").strip()
    total_price   = float(request.form.get("total_price") or 0)
    booking_money = float(request.form.get("booking_money") or 0)
    due_amount    = float(request.form.get("due_amount") or 0)

    if not all([name, address, phone]):
        flash("All customer fields are required.", "danger")
        return redirect(url_for("dashboard"))

    profile_pic   = None
    document_path = None

    pic_file = request.files.get("profile_pic")
    if pic_file and pic_file.filename:
        if not allowed_image(pic_file.filename):
            flash("Profile picture must be an image file.", "danger")
            return redirect(url_for("dashboard"))
        profile_pic = save_upload(pic_file, "profiles")

    doc_paths = []
    doc_files = request.files.getlist("document")
    for df in doc_files:
        if df and df.filename:
            if not allowed_doc(df.filename):
                flash("One of the documents is invalid. Must be PDF, image, DOC or DOCX.", "danger")
                return redirect(url_for("dashboard"))
            doc_paths.append(save_upload(df, "documents"))
            
    document_path = None
    if doc_paths:
        existing_docs_str = apartment.get("document_path")
        if existing_docs_str:
            try:
                existing_docs = json.loads(existing_docs_str)
                if not isinstance(existing_docs, list):
                    existing_docs = [existing_docs_str]
            except:
                existing_docs = [existing_docs_str]
        else:
            existing_docs = []
            
        existing_docs.extend(doc_paths)
        document_path = json.dumps(existing_docs)

    db.edit_customer(apt_id, name, address, phone, profile_pic, document_path, total_price, booking_money, due_amount)
    db.log_audit("EDIT", role,
                 f"Customer details updated for Apartment {apt_id} by {COMPANY_DISPLAY.get(role, role)}.")

    send_backup_to_telegram(action=f"EDIT {apt_id}", performed_by=COMPANY_DISPLAY.get(role, role))
    flash(f"Booking details for Apartment {apt_id} updated successfully.", "success")
    return redirect(url_for("dashboard"))


# ---------------------------------------------------------------------------
# Routes — Cancel Booking
# ---------------------------------------------------------------------------

@app.route("/cancel/<apt_id>", methods=["POST"])
@login_required
@operator_required
def cancel(apt_id):
    role      = session["role"]
    apartment = db.get_apartment(apt_id)

    if not apartment:
        flash("Apartment not found.", "danger")
        return redirect(url_for("dashboard"))

    if apartment["status"] != "Booked":
        flash("This apartment is not currently booked.", "warning")
        return redirect(url_for("dashboard"))

    # RBAC: only the booking company can cancel
    if apartment["booked_by"] != role:
        flash("You are not authorized to cancel this booking.", "danger")
        return redirect(url_for("dashboard"))

    customer_name = apartment.get("name", "Unknown")
    db.cancel_booking(apt_id)
    db.log_audit("CANCEL", role,
                 f"Booking cancelled for Apartment {apt_id} (was '{customer_name}') by {COMPANY_DISPLAY.get(role, role)}.")

    send_backup_to_telegram(action=f"CANCEL {apt_id}", performed_by=COMPANY_DISPLAY.get(role, role))
    flash(f"Booking for Apartment {apt_id} has been cancelled.", "success")
    return redirect(url_for("dashboard"))


# ---------------------------------------------------------------------------
# Routes — Profile (JSON for modal)
# ---------------------------------------------------------------------------

@app.route("/profile/<apt_id>")
@login_required
def profile(apt_id):
    apartment = db.get_apartment(apt_id)
    if not apartment or apartment["status"] != "Booked":
        return jsonify({"error": "No active booking found."}), 404
    doc_str = apartment.get("document_path")
    doc_list = []
    if doc_str:
        try:
            doc_list = json.loads(doc_str)
            if not isinstance(doc_list, list):
                doc_list = [doc_str]
        except:
            doc_list = [doc_str]

    return jsonify({
        "apt_id":       apt_id,
        "name":         apartment.get("name"),
        "phone":        apartment.get("phone"),
        "address":      apartment.get("address"),
        "profile_pic":  apartment.get("profile_pic"),
        "document":     doc_list,
        "booked_by":    apartment.get("booked_by"),
        "booked_at":    apartment.get("booked_at"),
        "total_price":  apartment.get("total_price", 0),
        "booking_money": apartment.get("booking_money", 0),
        "due_amount":   apartment.get("due_amount", 0),
        "company_display": COMPANY_DISPLAY.get(apartment.get("booked_by"), ""),
    })


@app.route("/report/<apt_id>")
@login_required
def individual_report(apt_id):
    apartment = db.get_apartment(apt_id)
    if not apartment or apartment["status"] != "Booked":
        flash("No active booking found for this apartment.", "danger")
        return redirect(url_for("dashboard"))
    
    from datetime import datetime
    generated_at = datetime.now().strftime("%d %B %Y, %I:%M %p")
    return render_template("individual_report.html", apartment=apartment, generated_at=generated_at, COMPANY_DISPLAY=COMPANY_DISPLAY)


# ---------------------------------------------------------------------------
# Routes — Reports
# ---------------------------------------------------------------------------

@app.route("/report")
@login_required
def report():
    """Printable HTML apartment status report."""
    from datetime import datetime
    apartments = db.get_all_apartments()
    generated_at = datetime.now().strftime("%d %B %Y, %I:%M %p")
    return render_template("report.html", apartments=apartments, generated_at=generated_at)


@app.route("/report/csv")
@login_required
def report_csv():
    """Download apartment status report as CSV."""
    import csv, io
    from datetime import datetime
    apartments = db.get_all_apartments()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Apartment", "Status", "Booked By (Company)", "Tenant Name",
                     "Phone", "Address", "Booked On"])
    for apt in apartments:
        writer.writerow([
            apt["id"],
            apt["status"],
            COMPANY_DISPLAY.get(apt["booked_by"], "") if apt["booked_by"] else "",
            apt.get("name")    or "",
            apt.get("phone")   or "",
            apt.get("address") or "",
            apt.get("booked_at") or "",
        ])

    from flask import Response
    filename = f"apartment_report_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )



@app.route("/audit")
@login_required
@operator_required
def audit_log():
    logs = db.get_audit_logs(limit=300)
    return render_template("audit_log.html", logs=logs)


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(413)
def too_large(e):
    flash("File is too large. Maximum allowed size is 16 MB.", "danger")
    return redirect(url_for("dashboard"))


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    db.init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
