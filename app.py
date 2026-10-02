import json
import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, flash, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from services.ai_service import VoiceTranscriptionError, analyze_incident, transcribe_audio
from services.geocoding_service import geocode_location, reverse_geocode
from services.resource_service import ResourceLookupError, get_nearby_resources, resource_types_for_incident
from services.routing_service import get_route_info

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

# Render/Linux-safe SQLite paths
DATABASE_DIR = BASE_DIR / "database"
DATABASE_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_PATH = DATABASE_DIR / "civicshield.db"
INCIDENT_PHOTO_DIR = BASE_DIR / "static" / "incident_photos"
INCIDENT_PHOTO_DIR.mkdir(parents=True, exist_ok=True)
MAX_INCIDENT_PHOTO_SIZE = 8 * 1024 * 1024
MAX_VOICE_AUDIO_SIZE = 4 * 1024 * 1024
VOICE_LANGUAGES = {
    "en-US": "English",
    "te-IN": "Telugu",
    "hi-IN": "Hindi",
    "ta-IN": "Tamil",
    "kn-IN": "Kannada",
}
INCIDENT_PHOTO_SIGNATURES = {
    "jpg": lambda data: data.startswith(b"\xff\xd8\xff"),
    "png": lambda data: data.startswith(b"\x89PNG\r\n\x1a\n"),
    "webp": lambda data: data.startswith(b"RIFF") and data[8:12] == b"WEBP",
}

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "civicshield-secret")
app.config["MAX_CONTENT_LENGTH"] = MAX_INCIDENT_PHOTO_SIZE + 1024 * 1024


def get_db():
    # Make sure the database directory exists before SQLite opens the file.
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS incidents (
            id TEXT PRIMARY KEY,
            user_id INTEGER,
            emergency_type TEXT NOT NULL,
            description TEXT NOT NULL,
            latitude REAL,
            longitude REAL,
            address TEXT,
            state TEXT,
            city TEXT,
            severity TEXT,
            source TEXT,
            language TEXT,
            photo_path TEXT,
            ai_analysis TEXT,
            status TEXT DEFAULT 'ACTIVE',
            created_at TEXT,
            updated_at TEXT,
            resolved_at TEXT
        );

        CREATE TABLE IF NOT EXISTS incident_updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id TEXT,
            previous_risk TEXT,
            updated_risk TEXT,
            reason_for_update TEXT,
            updated_support_requirements TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS incident_timeline (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id TEXT,
            event TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id TEXT,
            resource_json TEXT,
            created_at TEXT
        );
        """
    )
    incident_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(incidents)").fetchall()
    }
    if "photo_path" not in incident_columns:
        conn.execute("ALTER TABLE incidents ADD COLUMN photo_path TEXT")
    conn.commit()
    conn.close()


def now_iso():
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")


def incident_id_for_year():
    today = datetime.utcnow()
    prefix = f"CS-{today.year}-"
    conn = get_db()
    row = conn.execute(
        "SELECT COUNT(*) as count FROM incidents WHERE id LIKE ?",
        (prefix + "%",),
    ).fetchone()
    conn.close()
    count = int(row["count"]) + 1
    return f"{prefix}{count:04d}"


def safe_json(value, default=None):
    if value in (None, "", "null"):
        return default if default is not None else {}
    try:
        return json.loads(value)
    except Exception:
        try:
            return json.loads(str(value))
        except Exception:
            return default if default is not None else {}


def add_timeline_event(incident_id, event_text):
    conn = get_db()
    conn.execute(
        "INSERT INTO incident_timeline (incident_id, event, created_at) VALUES (?, ?, ?)",
        (incident_id, event_text, now_iso()),
    )
    conn.commit()
    conn.close()


def get_incident(incident_id):
    conn = get_db()
    incident = conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
    conn.close()
    if incident is None:
        return None
    incident = dict(incident)
    incident["ai_analysis"] = safe_json(incident.get("ai_analysis"), {})
    return incident


def normalize_emergency_type(value):
    mapping = {
        "fire": "FIRE",
        "road accident": "ROAD_ACCIDENT",
        "road_accident": "ROAD_ACCIDENT",
        "accident": "ROAD_ACCIDENT",
        "flood": "FLOOD",
        "other emergency": "OTHER_EMERGENCY",
        "other_emergency": "OTHER_EMERGENCY",
        "general": "OTHER_EMERGENCY",
    }
    if not value:
        return "OTHER_EMERGENCY"
    return mapping.get((value or "").strip().lower(), str(value).upper())


def analyze_and_store(incident, extra_text=None):
    emergency_type = normalize_emergency_type(incident.get("emergency_type"))
    description = incident.get("description") or ""
    if extra_text:
        description = f"{description} {extra_text}".strip()
    analysis = analyze_incident(
        emergency_type=emergency_type,
        description=description,
        location=incident.get("address") or "Unknown location",
        severity=incident.get("severity") or "Moderate",
        city=incident.get("city") or "",
        state=incident.get("state") or "",
        flood_details=description if emergency_type == "FLOOD" else "",
    )
    severity_value = analysis.get("risk_level") if emergency_type == "FLOOD" else incident.get("severity") or "Moderate"
    conn = get_db()
    conn.execute(
        "UPDATE incidents SET ai_analysis = ?, severity = ?, updated_at = ? WHERE id = ?",
        (json.dumps(analysis), severity_value, now_iso(), incident["id"]),
    )
    conn.commit()
    conn.close()
    return analysis


@app.before_request
def ensure_database_exists():
    init_db()


@app.errorhandler(413)
def request_entity_too_large(_error):
    if request.path == "/api/transcribe":
        return jsonify({"ok": False, "message": "The recording is too large. Please record a shorter voice report."}), 413
    flash("The upload is too large. Emergency photos must be 8 MB or smaller.")
    return redirect(url_for("report_page"))


@app.route("/")
def home():
    return render_template("home.html", current_page="home")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["full_name"]
            return redirect(url_for("user_dashboard"))
        flash("Invalid email or password.")
    return render_template("login.html", current_page="login")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if not full_name or not email or not password:
            flash("Please complete all signup fields.")
            return render_template("signup.html", current_page="signup")
        if password != confirm:
            flash("Passwords do not match.")
            return render_template("signup.html", current_page="signup")

        conn = get_db()
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            conn.close()
            flash("An account with that email already exists.")
            return render_template("signup.html", current_page="signup")

        conn.execute(
            "INSERT INTO users (full_name, email, password_hash) VALUES (?, ?, ?)",
            (full_name, email, generate_password_hash(password)),
        )
        conn.commit()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()
        session["user_id"] = user["id"]
        session["user_name"] = user["full_name"]
        return redirect(url_for("user_dashboard"))
    return render_template("signup.html", current_page="signup")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/user-dashboard")
def user_dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))
    user_id = session["user_id"]
    conn = get_db()
    total_reports = conn.execute("SELECT COUNT(*) as count FROM incidents WHERE user_id = ?", (user_id,)).fetchone()["count"]
    active_incidents = conn.execute("SELECT COUNT(*) as count FROM incidents WHERE user_id = ? AND status != 'RESOLVED'", (user_id,)).fetchone()["count"]
    resolved_incidents = conn.execute("SELECT COUNT(*) as count FROM incidents WHERE user_id = ? AND status = 'RESOLVED'", (user_id,)).fetchone()["count"]
    incidents = conn.execute(
        "SELECT * FROM incidents WHERE user_id = ? ORDER BY created_at DESC LIMIT 10",
        (user_id,),
    ).fetchall()
    conn.close()
    incident_rows = [dict(item) for item in incidents]
    return render_template(
        "user_dashboard.html",
        current_page="dashboard",
        user_name=session.get("user_name", "User"),
        total_reports=total_reports,
        active_incidents=active_incidents,
        resolved_incidents=resolved_incidents,
        incidents=incident_rows,
    )


@app.route("/report")
def report_page():
    return render_template("report.html", current_page="report")


def save_incident_photo(upload):
    if upload is None or not upload.filename:
        return None

    image_data = upload.stream.read(MAX_INCIDENT_PHOTO_SIZE + 1)
    if len(image_data) > MAX_INCIDENT_PHOTO_SIZE:
        raise ValueError("The photo must be 8 MB or smaller.")

    extension = next(
        (
            extension
            for extension, matches_signature in INCIDENT_PHOTO_SIGNATURES.items()
            if matches_signature(image_data)
        ),
        None,
    )
    if extension is None:
        raise ValueError("Choose a valid JPEG, PNG, or WebP photo.")

    INCIDENT_PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.{extension}"
    (INCIDENT_PHOTO_DIR / filename).write_bytes(image_data)
    return filename


@app.route("/create-incident", methods=["POST"])
def create_incident():
    emergency_type = normalize_emergency_type(request.form.get("emergency_type", "OTHER_EMERGENCY"))
    description = (request.form.get("description") or "").strip()
    if not description:
        flash("Please describe the emergency.")
        return redirect(url_for("report_page"))
    try:
        photo_path = save_incident_photo(request.files.get("incident_photo"))
    except ValueError as error:
        flash(str(error))
        return redirect(url_for("report_page"))

    latitude = request.form.get("latitude")
    longitude = request.form.get("longitude")
    address = request.form.get("address") or "Location not provided"
    city = request.form.get("city") or "Unknown"
    state = request.form.get("state") or "Unknown"
    source = request.form.get("source") or "CITIZEN_REPORT"
    language = request.form.get("language") or "en"
    severity = request.form.get("severity") or "Moderate"

    incident_id = incident_id_for_year()
    if emergency_type == "FLOOD":
        severity = "Moderate"

    incident_record = {
        "id": incident_id,
        "emergency_type": emergency_type,
        "description": description,
        "address": address,
        "city": city,
        "state": state,
        "severity": severity,
        "source": source,
        "language": language,
        "status": "ACTIVE",
        "user_id": session.get("user_id"),
        "latitude": float(latitude) if latitude not in (None, "") else 0.0,
        "longitude": float(longitude) if longitude not in (None, "") else 0.0,
    }

    now = now_iso()
    conn = get_db()
    conn.execute(
        "INSERT INTO incidents (id, user_id, emergency_type, description, latitude, longitude, address, state, city, severity, source, language, photo_path, ai_analysis, status, created_at, updated_at, resolved_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            incident_id,
            incident_record["user_id"],
            emergency_type,
            description,
            incident_record["latitude"],
            incident_record["longitude"],
            address,
            state,
            city,
            severity,
            source,
            language,
            photo_path,
            json.dumps({"risk_level": severity, "situation_summary": "AI analysis pending."}),
            "ACTIVE",
            now,
            now,
            None,
        ),
    )
    conn.commit()
    conn.close()

    add_timeline_event(incident_id, "Emergency reported")
    add_timeline_event(incident_id, "Location confirmed")
    analysis = analyze_and_store({**incident_record, "id": incident_id})
    if analysis:
        add_timeline_event(incident_id, "AI analysis completed")
    return redirect(url_for("dashboard", incident_id=incident_id))


@app.route("/incident-photo/<filename>")
def incident_photo(filename):
    return send_from_directory(INCIDENT_PHOTO_DIR, filename)


@app.route("/dashboard/<incident_id>")
def dashboard(incident_id):
    incident = get_incident(incident_id)
    if incident is None:
        return redirect(url_for("home"))
    conn = get_db()
    timeline = conn.execute(
        "SELECT event, created_at FROM incident_timeline WHERE incident_id = ? ORDER BY created_at ASC",
        (incident_id,),
    ).fetchall()
    resource_rows = conn.execute(
        "SELECT resource_json FROM resources WHERE incident_id = ? ORDER BY created_at DESC LIMIT 1",
        (incident_id,),
    ).fetchone()
    conn.close()
    incident["timeline"] = [dict(row) for row in timeline]
    incident["resource_cache"] = safe_json(resource_rows[0] if resource_rows else None, []) if resource_rows else []
    return render_template("dashboard.html", incident=incident, current_page="dashboard")


@app.route("/incidents")
def incidents():
    conn = get_db()
    rows = conn.execute("SELECT * FROM incidents ORDER BY created_at DESC").fetchall()
    conn.close()
    return render_template("incidents.html", incidents=[dict(r) for r in rows], current_page="incidents")


@app.route("/incident/<incident_id>/update", methods=["POST"])
def incident_update(incident_id):
    incident = get_incident(incident_id)
    if incident is None:
        return jsonify({"ok": False, "message": "Incident not found"}), 404
    update_text = (request.form.get("update_details") or "").strip()
    previous_risk = incident.get("severity") or "Moderate"
    if not update_text:
        return jsonify({"ok": False, "message": "Please add an update."}), 400
    analysis = analyze_incident(
        emergency_type=incident.get("emergency_type"),
        description=f"{incident.get('description')} Update: {update_text}",
        location=incident.get("address") or "Unknown",
        severity=previous_risk,
        city=incident.get("city"),
        state=incident.get("state"),
        flood_details=update_text if incident.get("emergency_type") == "FLOOD" else "",
    )
    new_risk = analysis.get("risk_level") or previous_risk
    conn = get_db()
    conn.execute(
        "INSERT INTO incident_updates (incident_id, previous_risk, updated_risk, reason_for_update, updated_support_requirements, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (
            incident_id,
            previous_risk,
            new_risk,
            update_text,
            "; ".join(analysis.get("likely_support_needed") or []),
            now_iso(),
        ),
    )
    conn.execute(
        "UPDATE incidents SET ai_analysis = ?, severity = ?, status = 'VERIFIED', updated_at = ? WHERE id = ?",
        (json.dumps(analysis), new_risk, now_iso(), incident_id),
    )
    conn.commit()
    conn.close()
    add_timeline_event(incident_id, "Situation updated")
    add_timeline_event(incident_id, "Human verification")
    return redirect(url_for("dashboard", incident_id=incident_id))


@app.route("/incident/<incident_id>/resolve", methods=["POST"])
def incident_resolve(incident_id):
    conn = get_db()
    conn.execute(
        "UPDATE incidents SET status = 'RESOLVED', resolved_at = ?, updated_at = ? WHERE id = ?",
        (now_iso(), now_iso(), incident_id),
    )
    conn.commit()
    conn.close()
    add_timeline_event(incident_id, "Incident resolved")
    return redirect(url_for("dashboard", incident_id=incident_id))


@app.route("/simulate-iot")
def simulate_iot():
    signal_file = BASE_DIR / "data" / "iot_signals.json"
    with open(signal_file, "r", encoding="utf-8") as handle:
        signals = json.load(handle)
    signal_type = request.args.get("type") or "fire"
    signal = signals.get(signal_type, signals["fire"])
    incident_id = incident_id_for_year()
    description = signal.get("description", "Simulated emergency signal")
    latitude = signal.get("latitude") or 0.0
    longitude = signal.get("longitude") or 0.0
    source = "SIMULATED_IOT"
    severity = signal.get("severity") or "Moderate"
    city = signal.get("city") or "Unknown"
    state = signal.get("state") or "Unknown"
    address = f"{signal.get('landmark') or 'Demo area'}, {city}, {state}"
    now = now_iso()
    conn = get_db()
    conn.execute(
        "INSERT INTO incidents (id, emergency_type, description, latitude, longitude, address, state, city, severity, source, language, ai_analysis, status, created_at, updated_at, resolved_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            incident_id,
            signal.get("type", "OTHER_EMERGENCY"),
            description,
            latitude,
            longitude,
            address,
            state,
            city,
            severity,
            source,
            "en",
            json.dumps({"risk_level": severity, "situation_summary": "Demo simulation prepared."}),
            "ACTIVE",
            now,
            now,
            None,
        ),
    )
    conn.commit()
    conn.close()
    add_timeline_event(incident_id, "Emergency reported")
    add_timeline_event(incident_id, "Location confirmed")
    analysis = analyze_and_store({
        "id": incident_id,
        "emergency_type": signal.get("type", "OTHER_EMERGENCY"),
        "description": description,
        "address": address,
        "city": city,
        "state": state,
        "severity": severity,
        "source": source,
        "latitude": latitude,
        "longitude": longitude,
    })
    if analysis:
        add_timeline_event(incident_id, "AI analysis completed")
    return redirect(url_for("dashboard", incident_id=incident_id))


@app.route("/api/geocode")
def api_geocode():
    query = request.args.get("q") or request.args.get("query")
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    if lat is not None and lon is not None:
        result = reverse_geocode(lat, lon)
    else:
        result = geocode_location(query or "", limit=5)
    if not result.get("ok"):
        return jsonify({"ok": False, "message": result.get("error", "Unable to locate this place. Please try another location.")}), 400
    return jsonify({"ok": True, **result})


@app.route("/api/resources")
def api_resources():
    incident_id = request.args.get("incident_id")
    if incident_id:
        incident = get_incident(incident_id)
        if incident is None:
            return jsonify({"ok": False, "message": "Incident not found"}), 404
        lat = incident.get("latitude")
        lon = incident.get("longitude")
        emergency = incident.get("emergency_type")
        if lat is None or lon is None or (lat == 0 and lon == 0):
            return jsonify({
                "ok": False,
                "message": "No incident location was saved. Select a place or use your current location to find nearby resources.",
            }), 400
    else:
        lat = request.args.get("lat", type=float)
        lon = request.args.get("lon", type=float)
        emergency = request.args.get("emergency_type") or "OTHER_EMERGENCY"
    if lat is None or lon is None:
        return jsonify({"ok": False, "message": "Nearby resource data temporarily unavailable."}), 400
    lookup_error = None
    try:
        resources = get_nearby_resources(lat, lon, emergency)
    except ResourceLookupError as exc:
        resources = []
        lookup_error = exc

    stale_resources = False
    resource_message = ""
    allowed_types = resource_types_for_incident(emergency)
    resources = [
        item for item in resources
        if isinstance(item, dict) and item.get("type") in allowed_types
    ]
    if incident_id:
        required_types = allowed_types
        live_types = {
            item.get("type")
            for item in resources
            if isinstance(item, dict)
        }
        missing_types = required_types - live_types

    if incident_id and (lookup_error or missing_types):
        conn = get_db()
        cached_row = conn.execute(
            "SELECT resource_json FROM resources WHERE incident_id = ? ORDER BY created_at DESC LIMIT 1",
            (incident_id,),
        ).fetchone()
        conn.close()
        cached_resources = safe_json(cached_row["resource_json"], []) if cached_row else []
        if isinstance(cached_resources, list):
            cached_resources = [
                item for item in cached_resources
                if isinstance(item, dict) and item.get("type") in allowed_types
            ]
        if isinstance(cached_resources, list) and cached_resources:
            if lookup_error or not resources:
                resource_message = (
                    "Live nearby lookup is unavailable. Showing the last saved real resource results."
                    if lookup_error
                    else "No live named facilities were returned. Showing the last saved real resource results."
                )
                resources = cached_resources
                stale_resources = True
            else:
                cached_missing = [
                    item for item in cached_resources
                    if isinstance(item, dict) and item.get("type") in missing_types
                ]
                seen = {
                    item.get("osm_url") or (
                        item.get("type"),
                        item.get("name"),
                        item.get("lat"),
                        item.get("lon"),
                    )
                    for item in resources
                    if isinstance(item, dict)
                }
                additions = [
                    item for item in cached_missing
                    if (item.get("osm_url") or (
                        item.get("type"),
                        item.get("name"),
                        item.get("lat"),
                        item.get("lon"),
                    )) not in seen
                ]
                if additions:
                    resources.extend(additions)
                    stale_resources = True
                    resource_message = (
                        "Some facility types were missing from the live map results. "
                        "Showing the last saved real resource results for those types."
                    )
    if lookup_error:
        if not stale_resources:
            return jsonify({"ok": False, "message": str(lookup_error)}), 502
    conn = get_db()
    if incident_id and resources:
        conn.execute(
            "INSERT INTO resources (incident_id, resource_json, created_at) VALUES (?, ?, ?)",
            (incident_id, json.dumps(resources), now_iso()),
        )
        conn.commit()
    conn.close()
    response_data = {"ok": True, "resources": resources}
    if stale_resources:
        response_data.update({"stale": True, "message": resource_message})
    return jsonify(response_data)


@app.route("/api/transcribe", methods=["POST"])
def api_transcribe():
    upload = request.files.get("audio")
    language = request.form.get("language", "")
    if upload is None:
        return jsonify({"ok": False, "message": "No voice recording was received."}), 400
    if language not in VOICE_LANGUAGES:
        return jsonify({"ok": False, "message": "Choose a supported transcription language."}), 400

    mime_type = (upload.mimetype or "").split(";", 1)[0].lower()
    if mime_type not in {"audio/webm", "audio/ogg", "audio/mp4", "audio/wav", "audio/mpeg"}:
        return jsonify({"ok": False, "message": "This browser's audio format is not supported. Try Chrome or Edge."}), 400

    audio_data = upload.stream.read(MAX_VOICE_AUDIO_SIZE + 1)
    if len(audio_data) > MAX_VOICE_AUDIO_SIZE:
        return jsonify({"ok": False, "message": "The recording is too large. Please record a shorter voice report."}), 413

    try:
        transcript = transcribe_audio(audio_data, mime_type, VOICE_LANGUAGES[language])
    except VoiceTranscriptionError as exc:
        status = 503 if "not configured" in str(exc).lower() else 502
        return jsonify({"ok": False, "message": str(exc)}), status
    return jsonify({"ok": True, "transcript": transcript})


@app.route("/api/route")
def api_route():
    start_lat = request.args.get("start_lat", type=float)
    start_lon = request.args.get("start_lon", type=float)
    end_lat = request.args.get("end_lat", type=float)
    end_lon = request.args.get("end_lon", type=float)
    if start_lat is None or start_lon is None or end_lat is None or end_lon is None:
        return jsonify({"ok": False, "message": "Route unavailable"}), 400
    route = get_route_info(start_lat, start_lon, end_lat, end_lon)
    if not route.get("ok"):
        return jsonify({"ok": False, "message": route.get("message", "Route unavailable")}), 200
    return jsonify({"ok": True, "distance_km": route.get("distance_km"), "duration_min": route.get("duration_min")})


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    payload = request.get_json(silent=True) or {}
    location = payload.get("location") or "Unknown location"
    emergency_type = normalize_emergency_type(payload.get("emergency_type") or "OTHER_EMERGENCY")
    description = payload.get("description") or "Emergency reported."
    severity = payload.get("severity") or "Moderate"
    city = payload.get("city") or ""
    state = payload.get("state") or ""
    analysis = analyze_incident(
        emergency_type=emergency_type,
        description=description,
        location=location,
        severity=severity,
        city=city,
        state=state,
        flood_details=description if emergency_type == "FLOOD" else "",
    )
    return jsonify({"ok": True, **analysis})


if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=5000, debug=True)
