import os
import sqlite3
from datetime import datetime, date

from flask import Flask, render_template, jsonify, request, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import check_password_hash


app = Flask(__name__)


# ============================================================
# CONFIGURATION
# ============================================================

SECRET_KEY = os.environ.get("QNTAAI_SECRET_KEY")

if not SECRET_KEY:
    raise RuntimeError(
        "QNTAAI_SECRET_KEY environment variable is not set."
    )

app.secret_key = SECRET_KEY

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

DATABASE = os.environ.get(
    "DATABASE_PATH",
    os.path.join(BASE_DIR, "attendance.db")
)

LATE_AFTER = "10:00"


# ============================================================
# RATE LIMITER
# ============================================================

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=[]
)


# ============================================================
# DATABASE
# ============================================================

def get_db():

    conn = sqlite3.connect(
        DATABASE,
        timeout=30
    )

    conn.row_factory = sqlite3.Row

    return conn


def init_db():

    print("==========================================")
    print("🔧 QntaAI Attendance Database Initialization")
    print("📁 Database:", os.path.abspath(DATABASE))
    print("==========================================")

    conn = get_db()

    # Team members table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS team_members (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL UNIQUE,

            role TEXT NOT NULL,

            passkey_hash TEXT

        )
    """)

    # Attendance table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS attendance (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            member_id INTEGER NOT NULL,

            date TEXT NOT NULL,

            status TEXT NOT NULL,

            time TEXT NOT NULL,

            FOREIGN KEY (member_id)
                REFERENCES team_members(id),

            UNIQUE(member_id, date)

        )
    """)

    # QntaAI team
    team = [

        (
            "Suryansh",
            "CEO & Founder",
            os.environ.get("SURYANSH_PASSKEY_HASH")
        ),

        (
            "Govind Trivedi",
            "Co-founder / Debugger",
            os.environ.get("GOVIND_PASSKEY_HASH")
        ),

        (
            "Arnav Sharma",
            "UI Designer",
            os.environ.get("ARNAV_PASSKEY_HASH")
        ),

        (
            "Shourya Sharma",
            "Advertiser",
            os.environ.get("SHOURYA_PASSKEY_HASH")
        )

    ]

    for name, role, passkey_hash in team:

        if not passkey_hash:
            print(
                f"⚠️ WARNING: No passkey hash configured for {name}"
            )
        else:
            print(
                f"🔐 Hash loaded for {name}: "
                f"length={len(passkey_hash)}, "
                f"prefix={passkey_hash[:12]}"
            )

        conn.execute(
            """
            INSERT INTO team_members
            (
                name,
                role,
                passkey_hash
            )
            VALUES (?, ?, ?)

            ON CONFLICT(name) DO UPDATE SET
                role = excluded.role,
                passkey_hash = excluded.passkey_hash
            """,
            (
                name,
                role,
                passkey_hash
            )
        )

    conn.commit()

    conn.close()


# IMPORTANT:
# Gunicorn imports "server:app".
# Therefore this must run during module import.


# ============================================================
# SECURITY HEADERS
# ============================================================

@app.after_request
def security_headers(response):

    response.headers[
        "Cache-Control"
    ] = "no-store"

    response.headers[
        "X-Content-Type-Options"
    ] = "nosniff"

    response.headers[
        "X-Frame-Options"
    ] = "DENY"

    response.headers[
        "Referrer-Policy"
    ] = "no-referrer"

    return response


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/api/health")
def health():

    try:

        conn = get_db()

        tables = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            ORDER BY name
            """
        ).fetchall()

        team_count = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM team_members
            """
        ).fetchone()["count"]

        attendance_count = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM attendance
            """
        ).fetchone()["count"]

        conn.close()

        return jsonify({

            "ok": True,

            "database": DATABASE,

            "tables": [
                row["name"]
                for row in tables
            ],

            "team_members": team_count,

            "attendance_records":
                attendance_count

        })

    except Exception as e:

        return jsonify({

            "ok": False,

            "error": str(e)

        }), 500


# ============================================================
# LOGIN
# ============================================================

@app.post("/api/login")
@limiter.limit("5 per minute")
def login():

    data = request.get_json(
        silent=True
    ) or {}

    passkey = data.get(
        "passkey"
    )

    if not passkey:

        return jsonify({

            "success": False,

            "error":
                "Passkey is required."

        }), 400

    conn = get_db()

    members = conn.execute(
        """
        SELECT

            id,
            name,
            role,
            passkey_hash

        FROM team_members

        WHERE passkey_hash IS NOT NULL
        """
    ).fetchall()

    authenticated_member = None

    for member in members:

        print(
            f"🔎 Login check: {member['name']} | "
            f"hash_present={bool(member['passkey_hash'])} | "
            f"hash_length={len(member['passkey_hash']) if member['passkey_hash'] else 0}"
        )

        try:

            if check_password_hash(
                member["passkey_hash"],
                passkey
            ):

                authenticated_member = member

                break

        except Exception:

            # Ignore malformed hash entries
            # rather than crashing the entire login endpoint.
            continue

    conn.close()

    if authenticated_member is None:

        return jsonify({

            "success": False,

            "error":
                "Invalid passkey."

        }), 401

    # Prevent old session data from carrying over.
    session.clear()

    session["member_id"] = (
        authenticated_member["id"]
    )

    return jsonify({

        "success": True,

        "name":
            authenticated_member["name"],

        "role":
            authenticated_member["role"]

    })


# ============================================================
# CURRENT USER
# ============================================================

@app.get("/api/me")
def current_user():

    member_id = session.get(
        "member_id"
    )

    if not member_id:

        return jsonify({

            "authenticated": False

        })

    conn = get_db()

    member = conn.execute(
        """
        SELECT

            id,
            name,
            role

        FROM team_members

        WHERE id = ?
        """,
        (member_id,)
    ).fetchone()

    conn.close()

    if member is None:

        session.clear()

        return jsonify({

            "authenticated": False

        })

    return jsonify({

        "authenticated": True,

        "id":
            member["id"],

        "name":
            member["name"],

        "role":
            member["role"]

    })


# ============================================================
# LOGOUT
# ============================================================

@app.post("/api/logout")
def logout():

    session.clear()

    return jsonify({

        "success": True

    })


# ============================================================
# TEAM ATTENDANCE
# ============================================================

@app.get("/api/team")
def api_team():

    requested_date = request.args.get(
        "date"
    )

    if requested_date:

        try:

            date.fromisoformat(
                requested_date
            )

        except ValueError:

            return jsonify({

                "error":
                    "Invalid date. Use YYYY-MM-DD."

            }), 400

    else:

        requested_date = (
            date.today().isoformat()
        )

    conn = get_db()

    members = conn.execute(
        """
        SELECT

            team_members.id,

            team_members.name,

            team_members.role,

            attendance.status,

            attendance.time

        FROM team_members

        LEFT JOIN attendance

            ON team_members.id =
               attendance.member_id

            AND attendance.date = ?

        ORDER BY team_members.id
        """,
        (
            requested_date,
        )
    ).fetchall()

    conn.close()

    return jsonify([

        {

            "id":
                member["id"],

            "name":
                member["name"],

            "role":
                member["role"],

            "status":
                member["status"]
                or "absent",

            "time":
                member["time"]

        }

        for member in members

    ])


# ============================================================
# MARK ATTENDANCE
# ============================================================

@app.post("/api/attendance")
@limiter.limit("10 per minute")
def mark_attendance():

    member_id = session.get(
        "member_id"
    )

    if not member_id:

        return jsonify({

            "success": False,

            "error":
                "You must sign in first."

        }), 401

    conn = get_db()

    member = conn.execute(
        """
        SELECT

            id,
            name,
            role

        FROM team_members

        WHERE id = ?
        """,
        (
            member_id,
        )
    ).fetchone()

    if member is None:

        conn.close()

        session.clear()

        return jsonify({

            "success": False,

            "error":
                "Invalid session."

        }), 401

    now = datetime.now()

    today = now.date().isoformat()

    current_time = now.strftime(
        "%H:%M:%S"
    )

    # Check whether today's attendance already exists.
    existing = conn.execute(
        """
        SELECT

            status,
            time

        FROM attendance

        WHERE member_id = ?

        AND date = ?
        """,
        (
            member_id,
            today
        )
    ).fetchone()

    if existing:

        conn.close()

        return jsonify({

            "success": False,

            "error":
                "Attendance already marked for today.",

            "status":
                existing["status"],

            "time":
                existing["time"]

        }), 409

    # Before 10:00 = present.
    # 10:00 or later = late.
    if now.strftime("%H:%M") < LATE_AFTER:

        status = "present"

    else:

        status = "late"

    try:

        conn.execute(
            """
            INSERT INTO attendance
            (
                member_id,
                date,
                status,
                time
            )

            VALUES (?, ?, ?, ?)
            """,
            (
                member_id,
                today,
                status,
                current_time
            )
        )

        conn.commit()

    except sqlite3.IntegrityError:

        conn.close()

        return jsonify({

            "success": False,

            "error":
                "Attendance already marked for today."

        }), 409

    conn.close()

    return jsonify({

        "success": True,

        "name":
            member["name"],

        "role":
            member["role"],

        "status":
            status,

        "time":
            current_time

    })


# ============================================================
# START LOCAL SERVER
# ============================================================

# ============================================================
# DATABASE INITIALIZATION
# ============================================================
# Gunicorn imports this module instead of running it as __main__.
# Therefore the database must be initialized during import.



# ============================================================
# LOCAL DEVELOPMENT SERVER
# ============================================================

# ============================================================
# DATABASE INITIALIZATION
# ============================================================
# Gunicorn imports server.py instead of running it as __main__.
# Initialize SQLite when the application module is imported.



# ============================================================
# LOCAL DEVELOPMENT SERVER
# ============================================================


init_db()
if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
