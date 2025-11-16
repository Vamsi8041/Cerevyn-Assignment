import os
import math
from datetime import datetime, date

from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, jsonify, session, g
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

# Base directory for DB and file storage
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "temp-secret-key")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASE_DIR, "geofence_attendance.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# ---------------------------------------------------------
#                     DATABASE MODELS
# ---------------------------------------------------------

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255))
    role = db.Column(db.String(30), default="employee")  # admin or employee
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    attendances = db.relationship("Attendance", backref="user", lazy=True)
    location_logs = db.relationship("LocationPing", backref="user", lazy=True)

    # Password utilities
    def set_password(self, pwd):
        self.password_hash = generate_password_hash(pwd)

    def verify_password(self, pwd):
        return check_password_hash(self.password_hash, pwd)


class GeoFence(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), default="Default Zone")
    center_lat = db.Column(db.Float, nullable=False)
    center_lng = db.Column(db.Float, nullable=False)
    radius_m = db.Column(db.Float, nullable=False, default=150.0)
    active = db.Column(db.Boolean, default=True)


class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    date = db.Column(db.Date, default=date.today)
    check_in_time = db.Column(db.DateTime)
    check_out_time = db.Column(db.DateTime)

    check_in_lat = db.Column(db.Float)
    check_in_lng = db.Column(db.Float)
    check_out_lat = db.Column(db.Float)
    check_out_lng = db.Column(db.Float)

    check_in_photo = db.Column(db.String(255))
    check_out_photo = db.Column(db.String(255))

    status = db.Column(db.String(30))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class LocationPing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    inside_geofence = db.Column(db.Boolean, default=False)


# ---------------------------------------------------------
#                  UTILITY FUNCTIONS
# ---------------------------------------------------------

def ensure_default_geofence():
    """Create an initial geofence if DB is empty."""
    if not GeoFence.query.first():
        gf = GeoFence(
            name="Hyderabad HQ",
            center_lat=17.385044,
            center_lng=78.486671,
            radius_m=200
        )
        db.session.add(gf)
        db.session.commit()


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate the distance between two points (in meters)."""
    R = 6371000  # Earth radius (meters)
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ = math.radians(lat2 - lat1)
    dλ = math.radians(lon2 - lon1)

    a = math.sin(dφ/2)**2 + math.cos(φ1)*math.cos(φ2)*math.sin(dλ/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R * c


def get_active_fence():
    return GeoFence.query.filter_by(active=True).first()


# ---------------------- LOGIN DECORATORS ---------------------- #

def login_required(fn):
    @wraps(fn)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return decorated


def admin_required(fn):
    @wraps(fn)
    def decorated(*args, **kwargs):
        uid = session.get("user_id")
        user = User.query.get(uid)
        if not uid or not user or user.role != "admin":
            flash("Admin access only.", "danger")
            return redirect(url_for("employee_dashboard"))
        return fn(*args, **kwargs)
    return decorated


@app.before_request
def inject_user():
    """Load current user into `g` for templates."""
    g.user = User.query.get(session.get("user_id")) if "user_id" in session else None


# ---------------------------------------------------------
#                     AUTHENTICATION
# ---------------------------------------------------------

@app.route("/")
def home():
    if g.user:
        return redirect(url_for("admin_dashboard" if g.user.role == "admin" else "employee_dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not all([name, email, password]):
            flash("Every field is mandatory.", "danger")
            return redirect(url_for("register"))

        if User.query.filter_by(email=email).first():
            flash("Email already exists.", "danger")
            return redirect(url_for("register"))

        # First user becomes admin automatically
        role = "admin" if User.query.count() == 0 else "employee"

        user = User(name=name, email=email, role=role)
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        flash(f"Account created! Assigned role: {role}", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").lower()
        pwd = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()

        if not user or not user.verify_password(pwd):
            flash("Incorrect login details.", "danger")
            return redirect(url_for("login"))

        session["user_id"] = user.id
        return redirect(url_for("admin_dashboard" if user.role == "admin" else "employee_dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("login"))


# ---------------------------------------------------------
#                   EMPLOYEE INTERFACE
# ---------------------------------------------------------

@app.route("/employee")
@login_required
def employee_dashboard():
    gf = get_active_fence()
    today = date.today()

    todays_record = Attendance.query.filter_by(
        user_id=g.user.id, date=today
    ).first()

    recent = Attendance.query.filter_by(
        user_id=g.user.id
    ).order_by(Attendance.date.desc()).limit(10).all()

    return render_template(
        "employee_dashboard.html",
        geofence=gf,
        attendance_today=todays_record,
        recent_attendance=recent,
        today=today,
    )


@app.route("/api/mark_attendance", methods=["POST"])
@login_required
def mark_attendance():
    data = request.get_json() or {}
    lat = data.get("lat")
    lng = data.get("lng")
    action = data.get("action")

    if None in (lat, lng) or action not in {"check_in", "check_out"}:
        return jsonify({"success": False, "message": "Invalid data"}), 400

    try:
        lat = float(lat)
        lng = float(lng)
    except:
        return jsonify({"success": False, "message": "Invalid coordinates"}), 400

    gf = get_active_fence()
    if not gf:
        return jsonify({"success": False, "message": "No geofence configured"}), 500

    # Distance evaluation
    distance = haversine_distance(lat, lng, gf.center_lat, gf.center_lng)
    inside = distance <= gf.radius_m

    if not inside:
        return jsonify({
            "success": False,
            "inside": False,
            "distance_m": distance,
            "message": f"You are outside the zone (~{int(distance)} m)."
        })

    # Attendance Logic
    today = date.today()
    record = Attendance.query.filter_by(user_id=g.user.id, date=today).first()
    now = datetime.utcnow()

    if action == "check_in":
        if record and record.check_in_time:
            return jsonify({"success": False, "message": "Already checked in"})

        if not record:
            record = Attendance(user_id=g.user.id, date=today)
            db.session.add(record)

        record.check_in_time = now
        record.check_in_lat = lat
        record.check_in_lng = lng
        record.status = "Present"
        db.session.commit()

        return jsonify({"success": True, "message": "Check-in recorded", "timestamp": now.isoformat()})

    if action == "check_out":
        if not record or not record.check_in_time:
            return jsonify({"success": False, "message": "No check-in found"})

        if record.check_out_time:
            return jsonify({"success": False, "message": "Already checked out"})

        record.check_out_time = now
        record.check_out_lat = lat
        record.check_out_lng = lng
        db.session.commit()

        return jsonify({"success": True, "message": "Check-out recorded", "timestamp": now.isoformat()})


@app.route("/api/ping_location", methods=["POST"])
@login_required
def ping_location():
    data = request.get_json() or {}
    lat = data.get("lat")
    lng = data.get("lng")

    if lat is None or lng is None:
        return jsonify({"success": False, "message": "Invalid coordinates"}), 400

    try:
        lat = float(lat)
        lng = float(lng)
    except:
        return jsonify({"success": False, "message": "Invalid coordinates"}), 400

    gf = get_active_fence()
    if not gf:
        return jsonify({"success": False, "message": "No geofence"}), 500

    distance = haversine_distance(lat, lng, gf.center_lat, gf.center_lng)
    inside = distance <= gf.radius_m

    log = LocationPing(user_id=g.user.id, lat=lat, lng=lng, inside_geofence=inside)
    db.session.add(log)
    db.session.commit()

    return jsonify({
        "success": True,
        "inside": inside,
        "distance_m": distance,
        "timestamp": log.timestamp.isoformat()
    })


@app.route("/api/geofence")
@login_required
def geofence_info():
    gf = get_active_fence()
    if not gf:
        return jsonify({"has_geofence": False})
    return jsonify({
        "has_geofence": True,
        "name": gf.name,
        "center_lat": gf.center_lat,
        "center_lng": gf.center_lng,
        "radius_m": gf.radius_m,
    })


# ---------------------------------------------------------
#                       ADMIN AREA
# ---------------------------------------------------------

@app.route("/admin")
@admin_required
def admin_dashboard():
    gf = get_active_fence()
    users = User.query.order_by(User.created_at.desc()).all()
    logs = Attendance.query.order_by(
        Attendance.date.desc(), Attendance.created_at.desc()
    ).limit(20).all()

    return render_template(
        "admin_dashboard.html", geofence=gf, users=users, latest_attendance=logs
    )


@app.route("/api/mark_attendance_photo", methods=["POST"])
@login_required
def mark_attendance_photo():
    form = request.form
    lat = form.get("lat")
    lng = form.get("lng")
    action = form.get("action")

    if "photo" not in request.files:
        return jsonify({"success": False, "message": "Photo missing"}), 400

    try:
        lat, lng = float(lat), float(lng)
    except:
        return jsonify({"success": False, "message": "Invalid coordinates"}), 400

    gf = get_active_fence()
    if not gf:
        return jsonify({"success": False, "message": "Geofence missing"}), 500

    distance = haversine_distance(lat, lng, gf.center_lat, gf.center_lng)
    inside = distance <= gf.radius_m

    if not inside:
        return jsonify({"success": False, "message": "Outside geofence"}), 400

    today = date.today()
    record = Attendance.query.filter_by(user_id=g.user.id, date=today).first()
    now = datetime.utcnow()

    photos_dir = os.path.join(BASE_DIR, "photos")
    os.makedirs(photos_dir, exist_ok=True)

    photo = request.files["photo"]
    filename = f"{g.user.id}_{action}_{now.strftime('%Y%m%d%H%M%S')}.jpg"
    save_path = os.path.join(photos_dir, filename)
    photo.save(save_path)

    if action == "check_in":
        if record and record.check_in_time:
            return jsonify({"success": False, "message": "Already checked in"})

        if not record:
            record = Attendance(user_id=g.user.id, date=today)
            db.session.add(record)

        record.check_in_time = now
        record.check_in_lat = lat
        record.check_in_lng = lng
        record.check_in_photo = filename
        record.status = "Present"
        db.session.commit()

        return jsonify({"success": True, "message": "Check-in with photo saved"})

    if action == "check_out":
        if not record or not record.check_in_time:
            return jsonify({"success": False, "message": "Not checked in yet"})

        if record.check_out_time:
            return jsonify({"success": False, "message": "Already checked out"})

        record.check_out_time = now
        record.check_out_lat = lat
        record.check_out_lng = lng
        record.check_out_photo = filename
        db.session.commit()

        return jsonify({"success": True, "message": "Check-out with photo saved"})

    return jsonify({"success": False, "message": "Invalid action"})


@app.route("/admin/geofence", methods=["GET", "POST"])
@admin_required
def admin_geofence():
    gf = get_active_fence()

    if request.method == "POST":
        name = request.form.get("name", "").strip() or "Office Zone"
        lat = request.form.get("center_lat")
        lng = request.form.get("center_lng")
        radius = request.form.get("radius_m")

        try:
            lat = float(lat)
            lng = float(lng)
            radius = float(radius)
        except:
            flash("Incorrect geofence values.", "danger")
            return redirect(url_for("admin_geofence"))

        if gf:
            gf.name = name
            gf.center_lat = lat
            gf.center_lng = lng
            gf.radius_m = radius
        else:
            gf = GeoFence(name=name, center_lat=lat, center_lng=lng, radius_m=radius)
            db.session.add(gf)

        db.session.commit()
        flash("Geofence saved successfully.", "success")
        return redirect(url_for("admin_geofence"))

    return render_template("admin_geofence.html", geofence=gf)


@app.route("/admin/user/<int:user_id>/movement")
@admin_required
def user_movement(user_id):
    user = User.query.get_or_404(user_id)

    date_str = request.args.get("date")
    try:
        chosen_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else date.today()
    except:
        chosen_date = date.today()

    start = datetime.combine(chosen_date, datetime.min.time())
    end = datetime.combine(chosen_date, datetime.max.time())

    pings = LocationPing.query.filter(
        LocationPing.user_id == user.id,
        LocationPing.timestamp >= start,
        LocationPing.timestamp <= end
    ).order_by(LocationPing.timestamp).all()

    return render_template(
        "user_movement.html",
        user=user,
        pings=pings,
        geofence=get_active_fence(),
        target_date=chosen_date,
    )


# ---------------------------------------------------------
#                    CLI / INITIALIZATION
# ---------------------------------------------------------

@app.cli.command("init-db")
def init_db():
    db.create_all()
    ensure_default_geofence()
    print("Database created. Default Geofence Ready.")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        ensure_default_geofence()

    app.run(host="0.0.0.0", port=5000, debug=True)
