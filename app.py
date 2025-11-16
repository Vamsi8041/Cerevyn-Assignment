import os
import math
from datetime import datetime, date

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify, g
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASE_DIR, "geofence_attendance.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# ---------------------- Models ---------------------- #

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="employee")  # admin / employee
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    attendances = db.relationship("Attendance", backref="user", lazy=True)
    pings = db.relationship("LocationPing", backref="user", lazy=True)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class GeoFence(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), default="Primary Office")
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
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    inside_geofence = db.Column(db.Boolean, default=False)


# ---------------------- Helpers ---------------------- #

def create_default_geofence():
    """Create a default geofence if none exist."""
    gf = GeoFence.query.first()
    if gf is None:
        # Default: center somewhere in Hyderabad (you can change this)
        gf = GeoFence(
            name="Hyderabad HQ",
            center_lat=17.385044,
            center_lng=78.486671,
            radius_m=200.0,
            active=True,
        )
        db.session.add(gf)
        db.session.commit()


def haversine(lat1, lon1, lat2, lon2):
    """Return distance in meters between two lat/lng points."""
    R = 6371000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def get_active_geofence():
    return GeoFence.query.filter_by(active=True).first()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        user = User.query.get(session["user_id"])
        if not user or user.role != "admin":
            flash("Admin access required.", "danger")
            return redirect(url_for("employee_dashboard"))
        return view(*args, **kwargs)

    return wrapped


@app.before_request
def load_user():
    g.user = None
    if "user_id" in session:
        g.user = User.query.get(session["user_id"])


# ---------------------- Auth Routes ---------------------- #

@app.route("/")
def index():
    if g.user:
        if g.user.role == "admin":
            return redirect(url_for("admin_dashboard"))
        else:
            return redirect(url_for("employee_dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    # For demo: anyone can register. First user becomes admin.
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        if not name or not email or not password:
            flash("All fields are required.", "danger")
            return redirect(url_for("register"))

        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "warning")
            return redirect(url_for("register"))

        user_count = User.query.count()
        role = "admin" if user_count == 0 else "employee"

        user = User(name=name, email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash(f"Account created successfully! You are registered as {role}.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash("Invalid email or password.", "danger")
            return redirect(url_for("login"))

        session["user_id"] = user.id
        flash("Logged in successfully.", "success")
        if user.role == "admin":
            return redirect(url_for("admin_dashboard"))
        else:
            return redirect(url_for("employee_dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("login"))


# ---------------------- Employee Views ---------------------- #

@app.route("/employee")
@login_required
def employee_dashboard():
    gf = get_active_geofence()
    today = date.today()
    attendance_today = Attendance.query.filter_by(user_id=g.user.id, date=today).first()
    recent_attendance = (
        Attendance.query.filter_by(user_id=g.user.id)
        .order_by(Attendance.date.desc())
        .limit(10)
        .all()
    )
    return render_template(
        "employee_dashboard.html",
        geofence=gf,
        attendance_today=attendance_today,
        recent_attendance=recent_attendance,
        today=today,
    )


@app.route("/api/mark_attendance", methods=["POST"])
@login_required
def mark_attendance():
    data = request.get_json() or {}
    lat = data.get("lat")
    lng = data.get("lng")
    action = data.get("action")

    if lat is None or lng is None or action not in {"check_in", "check_out"}:
        return jsonify({"success": False, "message": "Invalid data."}), 400

    gf = get_active_geofence()
    if not gf:
        return jsonify({"success": False, "message": "Geofence not configured."}), 500

    # Convert to float
    try:
        lat = float(lat)
        lng = float(lng)
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Invalid coordinates."}), 400

    distance_m = haversine(lat, lng, gf.center_lat, gf.center_lng)
    inside = distance_m <= gf.radius_m

    if not inside:
        return jsonify(
            {
                "success": False,
                "message": f"You are outside the allowed area (~{int(distance_m)} m away).",
                "distance_m": distance_m,
                "inside": False,
            }
        )

    # Inside geofence: mark attendance
    today = date.today()
    attendance = Attendance.query.filter_by(user_id=g.user.id, date=today).first()
    now = datetime.utcnow()

    if action == "check_in":
        if attendance and attendance.check_in_time:
            return jsonify(
                {
                    "success": False,
                    "message": "You have already checked in for today.",
                    "inside": True,
                }
            )
        if not attendance:
            attendance = Attendance(user_id=g.user.id, date=today)
            db.session.add(attendance)

        attendance.check_in_time = now
        attendance.check_in_lat = lat
        attendance.check_in_lng = lng
        attendance.status = "Present"
        db.session.commit()
        return jsonify(
            {
                "success": True,
                "message": "Check-in successful.",
                "inside": True,
                "timestamp": now.isoformat(),
            }
        )

    if action == "check_out":
        if not attendance or not attendance.check_in_time:
            return jsonify(
                {
                    "success": False,
                    "message": "You haven't checked in yet.",
                    "inside": True,
                }
            )
        if attendance.check_out_time:
            return jsonify(
                {
                    "success": False,
                    "message": "You already checked out for today.",
                    "inside": True,
                }
            )

        attendance.check_out_time = now
        attendance.check_out_lat = lat
        attendance.check_out_lng = lng
        db.session.commit()
        return jsonify(
            {
                "success": True,
                "message": "Check-out successful.",
                "inside": True,
                "timestamp": now.isoformat(),
            }
        )


@app.route("/api/ping_location", methods=["POST"])
@login_required
def ping_location():
    data = request.get_json() or {}
    lat = data.get("lat")
    lng = data.get("lng")

    if lat is None or lng is None:
        return jsonify({"success": False, "message": "Invalid coordinates."}), 400

    gf = get_active_geofence()
    if not gf:
        return jsonify({"success": False, "message": "Geofence not configured."}), 500

    try:
        lat = float(lat)
        lng = float(lng)
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Invalid coordinates."}), 400

    distance_m = haversine(lat, lng, gf.center_lat, gf.center_lng)
    inside = distance_m <= gf.radius_m

    ping = LocationPing(
        user_id=g.user.id, lat=lat, lng=lng, inside_geofence=inside
    )
    db.session.add(ping)
    db.session.commit()

    return jsonify(
        {
            "success": True,
            "inside": inside,
            "distance_m": distance_m,
            "timestamp": ping.timestamp.isoformat(),
        }
    )


@app.route("/api/geofence")
@login_required
def geofence_info():
    gf = get_active_geofence()
    if not gf:
        return jsonify({"has_geofence": False})
    return jsonify(
        {
            "has_geofence": True,
            "name": gf.name,
            "center_lat": gf.center_lat,
            "center_lng": gf.center_lng,
            "radius_m": gf.radius_m,
        }
    )


# ---------------------- Admin Views ---------------------- #

@app.route("/admin")
@admin_required
def admin_dashboard():
    gf = get_active_geofence()
    users = User.query.order_by(User.created_at.desc()).all()
    latest_attendance = (
        Attendance.query.order_by(Attendance.date.desc(), Attendance.created_at.desc())
        .limit(20)
        .all()
    )
    return render_template(
        "admin_dashboard.html",
        geofence=gf,
        users=users,
        latest_attendance=latest_attendance,
    )


@app.route("/api/mark_attendance_photo", methods=["POST"])
@login_required
def mark_attendance_photo():
    data = request.form

    lat = data.get("lat")
    lng = data.get("lng")
    action = data.get("action")

    if "photo" not in request.files:
        return jsonify({"success": False, "message": "No photo captured."}), 400

    photo = request.files["photo"]

    gf = get_active_geofence()
    if not gf:
        return jsonify({"success": False, "message": "Geofence not configured."}), 500

    try:
        lat = float(lat)
        lng = float(lng)
    except:
        return jsonify({"success": False, "message": "Invalid coordinates."}), 400

    # Distance check
    distance_m = haversine(lat, lng, gf.center_lat, gf.center_lng)
    inside = distance_m <= gf.radius_m

    if not inside:
        return jsonify({
            "success": False,
            "message": f"You are outside allowed area (~{int(distance_m)} m).",
            "inside": False
        })

    # ATTENDANCE LOGIC
    today = date.today()
    attendance = Attendance.query.filter_by(user_id=g.user.id, date=today).first()
    now = datetime.utcnow()

    # Create / ensure folder
    photos_path = os.path.join(BASE_DIR, "photos")
    os.makedirs(photos_path, exist_ok=True)

    # Save photo
    filename = f"{g.user.id}_{action}_{now.strftime('%Y%m%d%H%M%S')}.jpg"
    save_path = os.path.join(photos_path, filename)
    photo.save(save_path)

    # Check-in
    if action == "check_in":
        if attendance and attendance.check_in_time:
            return jsonify({"success": False, "message": "Already checked in."})

        if not attendance:
            attendance = Attendance(user_id=g.user.id, date=today)
            db.session.add(attendance)

        attendance.check_in_time = now
        attendance.check_in_lat = lat
        attendance.check_in_lng = lng
        attendance.status = "Present"
        attendance.check_in_photo = filename  # NEW FIELD
        db.session.commit()

        return jsonify({"success": True, "message": "Check-in + Photo captured!"})

    # Check-out
    if action == "check_out":
        if not attendance or not attendance.check_in_time:
            return jsonify({"success": False, "message": "Not checked in yet."})

        if attendance.check_out_time:
            return jsonify({"success": False, "message": "Already checked out."})

        attendance.check_out_time = now
        attendance.check_out_lat = lat
        attendance.check_out_lng = lng
        attendance.check_out_photo = filename  # NEW FIELD
        db.session.commit()

        return jsonify({"success": True, "message": "Check-out + Photo captured!"})

    return jsonify({"success": False, "message": "Invalid action."})



@app.route("/admin/geofence", methods=["GET", "POST"])
@admin_required
def admin_geofence():
    gf = get_active_geofence()
    if request.method == "POST":
        name = request.form.get("name", "").strip() or "Office"
        lat = request.form.get("center_lat")
        lng = request.form.get("center_lng")
        radius = request.form.get("radius_m")

        try:
            lat = float(lat)
            lng = float(lng)
            radius = float(radius)
        except (TypeError, ValueError):
            flash("Invalid geofence values.", "danger")
            return redirect(url_for("admin_geofence"))

        if gf is None:
            gf = GeoFence(
                name=name,
                center_lat=lat,
                center_lng=lng,
                radius_m=radius,
                active=True,
            )
            db.session.add(gf)
        else:
            gf.name = name
            gf.center_lat = lat
            gf.center_lng = lng
            gf.radius_m = radius
            gf.active = True

        db.session.commit()
        flash("Geofence updated.", "success")
        return redirect(url_for("admin_geofence"))

    return render_template("admin_geofence.html", geofence=gf)


@app.route("/admin/user/<int:user_id>/movement")
@admin_required
def user_movement(user_id):
    user = User.query.get_or_404(user_id)
    date_str = request.args.get("date")
    if date_str:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            target_date = date.today()
    else:
        target_date = date.today()

    start_dt = datetime.combine(target_date, datetime.min.time())
    end_dt = datetime.combine(target_date, datetime.max.time())

    pings = (
        LocationPing.query.filter(
            LocationPing.user_id == user.id,
            LocationPing.timestamp >= start_dt,
            LocationPing.timestamp <= end_dt,
        )
        .order_by(LocationPing.timestamp.asc())
        .all()
    )
    gf = get_active_geofence()
    return render_template(
        "user_movement.html",
        user=user,
        pings=pings,
        geofence=gf,
        target_date=target_date,
    )


# ---------------------- CLI / Setup ---------------------- #

@app.cli.command("init-db")
def init_db_command():
    """Initialize the database and create a default geofence."""
    db.create_all()
    create_default_geofence()
    print("Database initialized and default geofence created.")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        create_default_geofence()
    app.run(host="0.0.0.0", port=5000, debug=True)
