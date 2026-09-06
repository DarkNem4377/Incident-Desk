"""
Incident Reporting Platform — backend API.

Flask + SQLite. No ORM: the schema is small enough that raw SQL is clearer
and has zero hidden behavior. Run with `python app.py`.
"""

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask, g, jsonify, request, send_from_directory

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "incidents.db"

app = Flask(__name__, static_folder="static", template_folder="templates")

# ---------------------------------------------------------------------------
# Fixed vocabularies. Enforced server-side — the frontend dropdowns mirror
# these but the server is the source of truth.
# ---------------------------------------------------------------------------
INCIDENT_TYPES = [
    "Unauthorized Access",
    "Suspicious Transaction",
    "Phishing",
    "Data Exfiltration",
    "Failed Authentication",
    "Malware/Ransomware",
    "Insider Threat",
    "System Outage",
    "Other",
]
SEVERITIES = ["Low", "Medium", "High", "Critical"]
STATUSES = ["Open", "Investigating", "Resolved", "Closed"]


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS incidents (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_type     TEXT NOT NULL,
            discovery_time    TEXT NOT NULL,
            description       TEXT NOT NULL,
            severity          TEXT NOT NULL,
            initial_severity  TEXT NOT NULL,
            reporter          TEXT NOT NULL,
            status            TEXT NOT NULL DEFAULT 'Open',
            created_at        TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS timeline_entries (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id  INTEGER NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
            author       TEXT NOT NULL,
            note         TEXT NOT NULL,
            entry_type   TEXT NOT NULL DEFAULT 'note',
            timestamp    TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS reports (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id      INTEGER NOT NULL UNIQUE REFERENCES incidents(id) ON DELETE CASCADE,
            root_cause       TEXT NOT NULL DEFAULT '',
            remediation      TEXT NOT NULL DEFAULT '',
            lessons_learned  TEXT NOT NULL DEFAULT '',
            generated_at     TEXT NOT NULL,
            updated_at       TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_timeline_incident ON timeline_entries(incident_id);
        """
    )
    db.commit()
    db.close()


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------
class ValidationError(Exception):
    def __init__(self, errors):
        self.errors = errors  # dict of field -> message
        super().__init__(str(errors))


@app.errorhandler(ValidationError)
def handle_validation_error(err):
    return jsonify({"errors": err.errors}), 422


def require_str(payload, field, errors, max_len=None):
    val = payload.get(field)
    if not isinstance(val, str) or not val.strip():
        errors[field] = "This field is required."
        return None
    val = val.strip()
    if max_len and len(val) > max_len:
        errors[field] = f"Must be {max_len} characters or fewer."
        return None
    return val


def require_choice(payload, field, choices, errors):
    val = payload.get(field)
    if val not in choices:
        errors[field] = f"Must be one of: {', '.join(choices)}."
        return None
    return val


def require_datetime(payload, field, errors):
    val = payload.get(field)
    if not isinstance(val, str) or not val.strip():
        errors[field] = "This field is required."
        return None
    try:
        parsed = datetime.fromisoformat(val.replace("Z", "+00:00"))
    except ValueError:
        errors[field] = "Must be a valid date/time."
        return None
    reference_now = datetime.now(parsed.tzinfo) if parsed.tzinfo else datetime.now()
    if parsed > reference_now:
        errors[field] = "Discovery time can't be in the future."
        return None
    return val.strip()


def validate_incident_payload(payload):
    errors = {}
    incident_type = require_choice(payload, "incident_type", INCIDENT_TYPES, errors)
    discovery_time = require_datetime(payload, "discovery_time", errors)
    description = require_str(payload, "description", errors, max_len=5000)
    severity = require_choice(payload, "initial_severity", SEVERITIES, errors)
    reporter = require_str(payload, "reporter", errors, max_len=120)
    if errors:
        raise ValidationError(errors)
    return {
        "incident_type": incident_type,
        "discovery_time": discovery_time,
        "description": description,
        "initial_severity": severity,
        "reporter": reporter,
    }


def row_to_dict(row):
    return dict(row) if row else None


def fetch_incident_or_404(db, incident_id):
    row = db.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
    if row is None:
        return None
    return row


def add_timeline_entry(db, incident_id, author, note, entry_type="note"):
    db.execute(
        "INSERT INTO timeline_entries (incident_id, author, note, entry_type, timestamp) "
        "VALUES (?, ?, ?, ?, ?)",
        (incident_id, author, note, entry_type, now_iso()),
    )


# ---------------------------------------------------------------------------
# Static frontend
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory(app.template_folder, "index.html")


@app.route("/api/meta")
def meta():
    return jsonify(
        {
            "incident_types": INCIDENT_TYPES,
            "severities": SEVERITIES,
            "statuses": STATUSES,
        }
    )


# ---------------------------------------------------------------------------
# Incidents
# ---------------------------------------------------------------------------
@app.route("/api/incidents", methods=["GET"])
def list_incidents():
    db = get_db()
    status = request.args.get("status")
    severity = request.args.get("severity")
    sort = request.args.get("sort", "created_desc")

    query = "SELECT * FROM incidents WHERE 1=1"
    params = []
    if status and status in STATUSES:
        query += " AND status = ?"
        params.append(status)
    if severity and severity in SEVERITIES:
        query += " AND severity = ?"
        params.append(severity)

    sort_map = {
        "created_desc": "created_at DESC",
        "created_asc": "created_at ASC",
        "severity_desc": (
            "CASE severity WHEN 'Critical' THEN 4 WHEN 'High' THEN 3 "
            "WHEN 'Medium' THEN 2 WHEN 'Low' THEN 1 ELSE 0 END DESC"
        ),
        "discovery_desc": "discovery_time DESC",
    }
    query += " ORDER BY " + sort_map.get(sort, sort_map["created_desc"])

    rows = db.execute(query, params).fetchall()
    incidents = [row_to_dict(r) for r in rows]

    # attach timeline entry counts cheaply for the list view
    counts = db.execute(
        "SELECT incident_id, COUNT(*) as c FROM timeline_entries GROUP BY incident_id"
    ).fetchall()
    count_map = {r["incident_id"]: r["c"] for r in counts}
    for inc in incidents:
        inc["timeline_count"] = count_map.get(inc["id"], 0)

    return jsonify(incidents)


@app.route("/api/incidents", methods=["POST"])
def create_incident():
    payload = request.get_json(silent=True) or {}
    clean = validate_incident_payload(payload)
    db = get_db()
    cur = db.execute(
        """INSERT INTO incidents
           (incident_type, discovery_time, description, severity, initial_severity,
            reporter, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, 'Open', ?)""",
        (
            clean["incident_type"],
            clean["discovery_time"],
            clean["description"],
            clean["initial_severity"],
            clean["initial_severity"],
            clean["reporter"],
            now_iso(),
        ),
    )
    incident_id = cur.lastrowid
    add_timeline_entry(
        db,
        incident_id,
        clean["reporter"],
        f"Incident reported. Initial severity set to {clean['initial_severity']}.",
        entry_type="system",
    )
    db.commit()
    row = fetch_incident_or_404(db, incident_id)
    return jsonify(row_to_dict(row)), 201


@app.route("/api/incidents/<int:incident_id>", methods=["GET"])
def get_incident(incident_id):
    db = get_db()
    row = fetch_incident_or_404(db, incident_id)
    if row is None:
        return jsonify({"error": "Incident not found."}), 404
    incident = row_to_dict(row)
    timeline = db.execute(
        "SELECT * FROM timeline_entries WHERE incident_id = ? ORDER BY timestamp ASC, id ASC",
        (incident_id,),
    ).fetchall()
    incident["timeline"] = [row_to_dict(t) for t in timeline]
    report = db.execute(
        "SELECT * FROM reports WHERE incident_id = ?", (incident_id,)
    ).fetchone()
    incident["report"] = row_to_dict(report)
    return jsonify(incident)


@app.route("/api/incidents/<int:incident_id>", methods=["PATCH"])
def update_incident(incident_id):
    db = get_db()
    row = fetch_incident_or_404(db, incident_id)
    if row is None:
        return jsonify({"error": "Incident not found."}), 404
    if row["status"] == "Closed":
        return (
            jsonify(
                {
                    "error": "This incident is closed and can't be edited. "
                    "Reopen it first."
                }
            ),
            409,
        )

    payload = request.get_json(silent=True) or {}
    author = (payload.get("author") or "Unknown").strip() or "Unknown"
    updates = []
    params = []

    new_status = payload.get("status")
    if new_status is not None:
        if new_status not in STATUSES:
            return jsonify({"errors": {"status": "Invalid status."}}), 422
        if new_status != row["status"]:
            updates.append("status = ?")
            params.append(new_status)
            add_timeline_entry(
                db,
                incident_id,
                author,
                f"Status changed from {row['status']} to {new_status}.",
                entry_type="status_change",
            )

    new_severity = payload.get("severity")
    if new_severity is not None:
        if new_severity not in SEVERITIES:
            return jsonify({"errors": {"severity": "Invalid severity."}}), 422
        if new_severity != row["severity"]:
            updates.append("severity = ?")
            params.append(new_severity)
            add_timeline_entry(
                db,
                incident_id,
                author,
                f"Severity changed from {row['severity']} to {new_severity}.",
                entry_type="severity_change",
            )

    if not updates:
        return jsonify(row_to_dict(row))

    params.append(incident_id)
    db.execute(f"UPDATE incidents SET {', '.join(updates)} WHERE id = ?", params)
    db.commit()
    updated = fetch_incident_or_404(db, incident_id)
    return jsonify(row_to_dict(updated))


@app.route("/api/incidents/<int:incident_id>/reopen", methods=["POST"])
def reopen_incident(incident_id):
    db = get_db()
    row = fetch_incident_or_404(db, incident_id)
    if row is None:
        return jsonify({"error": "Incident not found."}), 404
    if row["status"] != "Closed":
        return jsonify({"error": "Only closed incidents can be reopened."}), 409

    payload = request.get_json(silent=True) or {}
    author = (payload.get("author") or "Unknown").strip() or "Unknown"
    reason = (payload.get("reason") or "").strip()

    db.execute(
        "UPDATE incidents SET status = 'Investigating' WHERE id = ?", (incident_id,)
    )
    note = "Incident reopened."
    if reason:
        note += f" Reason: {reason}"
    add_timeline_entry(db, incident_id, author, note, entry_type="status_change")
    db.commit()
    updated = fetch_incident_or_404(db, incident_id)
    return jsonify(row_to_dict(updated))


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------
@app.route("/api/incidents/<int:incident_id>/timeline", methods=["POST"])
def add_timeline(incident_id):
    db = get_db()
    row = fetch_incident_or_404(db, incident_id)
    if row is None:
        return jsonify({"error": "Incident not found."}), 404
    if row["status"] == "Closed":
        return (
            jsonify({"error": "This incident is closed. Reopen it to add updates."}),
            409,
        )

    payload = request.get_json(silent=True) or {}
    errors = {}
    author = require_str(payload, "author", errors, max_len=120)
    note = require_str(payload, "note", errors, max_len=3000)
    if errors:
        raise ValidationError(errors)

    add_timeline_entry(db, incident_id, author, note, entry_type="note")
    db.commit()
    timeline = db.execute(
        "SELECT * FROM timeline_entries WHERE incident_id = ? ORDER BY timestamp ASC, id ASC",
        (incident_id,),
    ).fetchall()
    return jsonify([row_to_dict(t) for t in timeline]), 201


# ---------------------------------------------------------------------------
# Post-incident report auto-fill
# ---------------------------------------------------------------------------
@app.route("/api/incidents/<int:incident_id>/report", methods=["GET"])
def get_report(incident_id):
    db = get_db()
    incident = fetch_incident_or_404(db, incident_id)
    if incident is None:
        return jsonify({"error": "Incident not found."}), 404

    report = db.execute(
        "SELECT * FROM reports WHERE incident_id = ?", (incident_id,)
    ).fetchone()
    if report is None:
        ts = now_iso()
        db.execute(
            "INSERT INTO reports (incident_id, generated_at, updated_at) VALUES (?, ?, ?)",
            (incident_id, ts, ts),
        )
        db.commit()
        report = db.execute(
            "SELECT * FROM reports WHERE incident_id = ?", (incident_id,)
        ).fetchone()

    timeline = db.execute(
        "SELECT * FROM timeline_entries WHERE incident_id = ? ORDER BY timestamp ASC, id ASC",
        (incident_id,),
    ).fetchall()

    return jsonify(
        {
            "incident": row_to_dict(incident),
            "timeline": [row_to_dict(t) for t in timeline],
            "report": row_to_dict(report),
        }
    )


@app.route("/api/incidents/<int:incident_id>/report", methods=["PUT"])
def save_report(incident_id):
    db = get_db()
    incident = fetch_incident_or_404(db, incident_id)
    if incident is None:
        return jsonify({"error": "Incident not found."}), 404

    payload = request.get_json(silent=True) or {}
    root_cause = (payload.get("root_cause") or "").strip()
    remediation = (payload.get("remediation") or "").strip()
    lessons_learned = (payload.get("lessons_learned") or "").strip()

    existing = db.execute(
        "SELECT id FROM reports WHERE incident_id = ?", (incident_id,)
    ).fetchone()
    ts = now_iso()
    if existing:
        db.execute(
            """UPDATE reports SET root_cause = ?, remediation = ?, lessons_learned = ?,
               updated_at = ? WHERE incident_id = ?""",
            (root_cause, remediation, lessons_learned, ts, incident_id),
        )
    else:
        db.execute(
            """INSERT INTO reports
               (incident_id, root_cause, remediation, lessons_learned, generated_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (incident_id, root_cause, remediation, lessons_learned, ts, ts),
        )
    db.commit()
    report = db.execute(
        "SELECT * FROM reports WHERE incident_id = ?", (incident_id,)
    ).fetchone()
    return jsonify(row_to_dict(report))


# ---------------------------------------------------------------------------
# Trends
# ---------------------------------------------------------------------------
def _parse_discovery(value):
    """discovery_time is stored as an ISO string (see iso() in seed_data.py /
    the /api/incidents POST handler); tolerate a trailing 'Z' or no tzinfo."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _bucket_granularity(days):
    # Day buckets stay readable up to ~2 weeks; beyond that too many bars of
    # height 0-1 make the chart show noise instead of a shape. Week buckets
    # carry the mid-range views, month buckets carry the year view.
    if days <= 14:
        return "day"
    if days <= 120:
        return "week"
    return "month"


def _bucket_key_and_label(dt, granularity):
    if granularity == "day":
        key = dt.date().isoformat()
        label = f"{dt.strftime('%b')} {dt.day}"
    elif granularity == "week":
        monday = dt.date() - timedelta(days=dt.weekday())
        key = monday.isoformat()
        label = f"{monday.strftime('%b')} {monday.day}"
    else:  # month
        key = dt.strftime("%Y-%m")
        label = dt.strftime("%b %Y")
    return key, label


@app.route("/api/trends")
def trends():
    db = get_db()
    try:
        days = int(request.args.get("days", 30))
    except ValueError:
        days = 30
    days = max(1, min(days, 365))
    granularity = _bucket_granularity(days)

    rows = db.execute(
        """SELECT incident_type, discovery_time FROM incidents
           WHERE date(discovery_time) >= date('now', ?)
           ORDER BY discovery_time ASC""",
        (f"-{days} days",),
    ).fetchall()

    counts = {}  # (bucket_key, incident_type) -> count
    labels = {}  # bucket_key -> label
    for row in rows:
        dt = _parse_discovery(row["discovery_time"])
        key, label = _bucket_key_and_label(dt, granularity)
        labels[key] = label
        counts[(key, row["incident_type"])] = counts.get((key, row["incident_type"]), 0) + 1

    by_bucket = [
        {"bucket_key": key, "bucket_label": labels[key], "incident_type": itype, "c": c}
        for (key, itype), c in counts.items()
    ]
    by_bucket.sort(key=lambda r: r["bucket_key"])

    totals_rows = db.execute(
        """SELECT incident_type, COUNT(*) as c FROM incidents
           WHERE date(discovery_time) >= date('now', ?)
           GROUP BY incident_type ORDER BY c DESC""",
        (f"-{days} days",),
    ).fetchall()

    return jsonify(
        {
            "granularity": granularity,
            "by_bucket": by_bucket,
            "totals_by_type": [row_to_dict(r) for r in totals_rows],
            "days": days,
        }
    )


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5050)