import os
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash

app = Flask(__name__)
app.secret_key = "queuecare-secret-key-hackathon"

# Path to SQLite database file
DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")

# Department configuration with codes, prefixes, and emojis
DEPARTMENTS = {
    "General Medicine": {"prefix": "A", "icon": "🩺", "code": "GM", "desc": "Fever, cold, general health issues"},
    "Cardiology": {"prefix": "B", "icon": "🫀", "code": "CARD", "desc": "Heart, chest pain, blood pressure"},
    "Orthopedics": {"prefix": "C", "icon": "🦴", "code": "ORTH", "desc": "Bones, joints, knee pain, fractures"},
    "Pediatrics": {"prefix": "D", "icon": "👶", "code": "PED", "desc": "Infants, children, vaccinations"}
}

def get_db_connection():
    """Establish and return a database connection with dict-like row access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Automatically create the database and tables if they do not exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_number TEXT UNIQUE NOT NULL,
            patient_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            department TEXT NOT NULL,
            symptoms TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Waiting', -- 'Waiting', 'Serving', 'Completed', 'Cancelled'
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            called_at TIMESTAMP,
            completed_at TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

# Initialize DB at startup
init_db()

def rule_based_ai_recommend(symptoms_text):
    """
    Simple, robust rule-based symptom analyzer for 2-hour hackathon.
    Analyzes user-entered symptoms and recommends the best hospital department.
    """
    if not symptoms_text:
        return "General Medicine", "Please describe your symptoms for a tailored recommendation."

    text = symptoms_text.lower().strip()

    keyword_map = {
        "Orthopedics": [
            "knee", "bone", "joint", "fracture", "back pain", "spine", "sprain",
            "leg pain", "ankle", "arthritis", "shoulder", "neck pain", "elbow",
            "wrist", "muscle tear", "tendon", "hip", "walking problem", "broken",
            "swelling in leg", "slip disc", "stiffness"
        ],
        "Cardiology": [
            "chest pain", "heart", "heart attack", "palpitation", "palpitations",
            "blood pressure", "high bp", "low bp", "hypertension", "shortness of breath",
            "breathless", "angina", "cardiac", "arrhythmia", "pulse", "tightness in chest",
            "heavy chest", "tachycardia"
        ],
        "Pediatrics": [
            "child", "kid", "baby", "infant", "toddler", "pediatric", "vaccine",
            "vaccination", "newborn", "teething", "growth", "pediatrician", "son", "daughter"
        ],
        "General Medicine": [
            "fever", "headache", "cold", "cough", "flu", "stomach", "vomit", "vomiting",
            "nausea", "dizziness", "fatigue", "weakness", "diarrhea", "throat", "infection",
            "allergy", "rash", "migraine", "chills", "acidity", "indigestion", "tired"
        ]
    }

    # Count matching keyword hits per department
    scores = {dept: 0 for dept in keyword_map}
    for dept, keywords in keyword_map.items():
        for kw in keywords:
            if kw in text:
                # Longer phrases carry more weight
                scores[dept] += 2 if " " in kw else 1

    best_dept = max(scores, key=scores.get)
    if scores[best_dept] > 0:
        return best_dept, f"Based on symptoms like '{text}', our AI recommends consulting {best_dept}."
    
    return "General Medicine", "General symptoms detected. We recommend starting with General Medicine for a full evaluation."


@app.route("/")
def index():
    """Patient registration landing page with live department queue overview."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Calculate queue statistics per department
    dept_stats = {}
    for dept_name, info in DEPARTMENTS.items():
        # Current serving token
        serving_row = cursor.execute(
            "SELECT token_number FROM tokens WHERE department = ? AND status = 'Serving' ORDER BY id DESC LIMIT 1",
            (dept_name,)
        ).fetchone()
        
        # Waiting count
        waiting_count = cursor.execute(
            "SELECT COUNT(*) as count FROM tokens WHERE department = ? AND status = 'Waiting'",
            (dept_name,)
        ).fetchone()["count"]

        dept_stats[dept_name] = {
            "serving": serving_row["token_number"] if serving_row else "--",
            "waiting": waiting_count,
            "prefix": info["prefix"],
            "icon": info["icon"],
            "desc": info["desc"]
        }

    conn.close()
    return render_template("index.html", departments=DEPARTMENTS, dept_stats=dept_stats)


@app.route("/get-token", methods=["POST"])
def get_token():
    """Generates a sequential department token and redirects to the token tracking page."""
    patient_name = request.form.get("patient_name", "").strip()
    phone = request.form.get("phone", "").strip()
    department = request.form.get("department", "").strip()
    symptoms = request.form.get("symptoms", "").strip()

    if not patient_name or not phone or department not in DEPARTMENTS:
        flash("Please provide all required fields correctly.", "danger")
        return redirect(url_for("index"))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Determine next sequence token number (e.g., A-001, A-002, B-001)
    prefix = DEPARTMENTS[department]["prefix"]
    count_row = cursor.execute(
        "SELECT COUNT(*) as total FROM tokens WHERE department = ?",
        (department,)
    ).fetchone()
    next_number = (count_row["total"] if count_row else 0) + 1
    token_number = f"{prefix}-{next_number:03d}"

    # Handle rare collision if data was modified
    while cursor.execute("SELECT id FROM tokens WHERE token_number = ?", (token_number,)).fetchone():
        next_number += 1
        token_number = f"{prefix}-{next_number:03d}"

    cursor.execute("""
        INSERT INTO tokens (token_number, patient_name, phone, department, symptoms, status)
        VALUES (?, ?, ?, ?, ?, 'Waiting')
    """, (token_number, patient_name, phone, department, symptoms))

    conn.commit()
    conn.close()

    return redirect(url_for("view_token", token_number=token_number))


@app.route("/token/<token_number>")
def view_token(token_number):
    """Displays token details, live queue position, and currently serving token."""
    conn = get_db_connection()
    cursor = conn.cursor()

    token = cursor.execute("SELECT * FROM tokens WHERE token_number = ?", (token_number,)).fetchone()
    if not token:
        conn.close()
        flash(f"Token '{token_number}' not found.", "warning")
        return redirect(url_for("index"))

    dept_name = token["department"]

    # Currently serving token for this department
    serving_row = cursor.execute(
        "SELECT token_number FROM tokens WHERE department = ? AND status = 'Serving' ORDER BY id DESC LIMIT 1",
        (dept_name,)
    ).fetchone()
    currently_serving = serving_row["token_number"] if serving_row else "--"

    # Count how many waiting patients are ahead of this token
    people_ahead = 0
    if token["status"] == "Waiting":
        people_ahead = cursor.execute("""
            SELECT COUNT(*) as ahead FROM tokens
            WHERE department = ? AND status = 'Waiting' AND id < ?
        """, (dept_name, token["id"])).fetchone()["ahead"]

    conn.close()

    dept_info = DEPARTMENTS.get(dept_name, {"icon": "🏥", "prefix": "A"})

    return render_template(
        "token.html",
        token=token,
        currently_serving=currently_serving,
        people_ahead=people_ahead,
        dept_info=dept_info
    )


@app.route("/admin")
def admin():
    """Admin dashboard showing separate queues for each department."""
    conn = get_db_connection()
    cursor = conn.cursor()

    selected_dept = request.args.get("department", "General Medicine")
    if selected_dept not in DEPARTMENTS:
        selected_dept = "General Medicine"

    # Fetch currently serving patient for selected department
    current_serving = cursor.execute("""
        SELECT * FROM tokens 
        WHERE department = ? AND status = 'Serving' 
        ORDER BY id DESC LIMIT 1
    """, (selected_dept,)).fetchone()

    # Fetch waiting queue for selected department (in arrival order)
    waiting_patients = cursor.execute("""
        SELECT * FROM tokens 
        WHERE department = ? AND status = 'Waiting' 
        ORDER BY id ASC
    """, (selected_dept,)).fetchall()

    # Fetch recent completed patients for selected department
    completed_patients = cursor.execute("""
        SELECT * FROM tokens 
        WHERE department = ? AND status = 'Completed' 
        ORDER BY completed_at DESC, id DESC LIMIT 8
    """, (selected_dept,)).fetchall()

    # Stats summary for all departments
    summary = {}
    for d_name in DEPARTMENTS:
        serving_cnt = cursor.execute(
            "SELECT token_number FROM tokens WHERE department = ? AND status = 'Serving' LIMIT 1", (d_name,)
        ).fetchone()
        wait_cnt = cursor.execute(
            "SELECT COUNT(*) as c FROM tokens WHERE department = ? AND status = 'Waiting'", (d_name,)
        ).fetchone()["c"]
        comp_cnt = cursor.execute(
            "SELECT COUNT(*) as c FROM tokens WHERE department = ? AND status = 'Completed'", (d_name,)
        ).fetchone()["c"]

        summary[d_name] = {
            "serving": serving_cnt["token_number"] if serving_cnt else "--",
            "waiting": wait_cnt,
            "completed": comp_cnt
        }

    conn.close()

    return render_template(
        "admin.html",
        departments=DEPARTMENTS,
        selected_dept=selected_dept,
        current_serving=current_serving,
        waiting_patients=waiting_patients,
        completed_patients=completed_patients,
        summary=summary
    )


@app.route("/admin/call-next", methods=["POST"])
def call_next_patient():
    """
    Calls the next patient in queue:
    1. Previous serving patient for this department becomes 'Completed'
    2. First waiting patient becomes 'Serving'
    """
    department = request.form.get("department", "").strip()
    if department not in DEPARTMENTS:
        flash("Invalid department.", "danger")
        return redirect(url_for("admin"))

    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. Mark currently serving patient in this department as 'Completed'
    cursor.execute("""
        UPDATE tokens 
        SET status = 'Completed', completed_at = ? 
        WHERE department = ? AND status = 'Serving'
    """, (now_str, department))

    # 2. Pick earliest waiting patient in this department
    next_patient = cursor.execute("""
        SELECT id, token_number, patient_name FROM tokens 
        WHERE department = ? AND status = 'Waiting' 
        ORDER BY id ASC LIMIT 1
    """, (department,)).fetchone()

    if next_patient:
        cursor.execute("""
            UPDATE tokens 
            SET status = 'Serving', called_at = ? 
            WHERE id = ?
        """, (now_str, next_patient["id"]))
        conn.commit()
        flash(f"Now Serving: {next_patient['token_number']} ({next_patient['patient_name']}) in {department}.", "success")
    else:
        conn.commit()
        flash(f"No patients waiting in {department}. Current consultation marked completed.", "info")

    conn.close()
    return redirect(url_for("admin", department=department))


# ---------------- API ENDPOINTS FOR LIVE REFRESH & AI ---------------- #

@app.route("/api/recommend", methods=["POST"])
def api_recommend():
    """Endpoint for Simple Rule-based AI Department Recommendation."""
    data = request.get_json(silent=True) or {}
    symptoms = data.get("symptoms", "")
    department, reason = rule_based_ai_recommend(symptoms)
    return jsonify({
        "department": department,
        "reason": reason,
        "icon": DEPARTMENTS.get(department, {}).get("icon", "🏥")
    })


@app.route("/api/token/<token_number>")
def api_token_status(token_number):
    """JSON status for a specific token to enable live auto-updates on token.html."""
    conn = get_db_connection()
    cursor = conn.cursor()

    token = cursor.execute("SELECT * FROM tokens WHERE token_number = ?", (token_number,)).fetchone()
    if not token:
        conn.close()
        return jsonify({"error": "Token not found"}), 404

    dept_name = token["department"]

    serving_row = cursor.execute(
        "SELECT token_number FROM tokens WHERE department = ? AND status = 'Serving' ORDER BY id DESC LIMIT 1",
        (dept_name,)
    ).fetchone()
    currently_serving = serving_row["token_number"] if serving_row else "--"

    people_ahead = 0
    if token["status"] == "Waiting":
        people_ahead = cursor.execute("""
            SELECT COUNT(*) as ahead FROM tokens
            WHERE department = ? AND status = 'Waiting' AND id < ?
        """, (dept_name, token["id"])).fetchone()["ahead"]

    conn.close()

    return jsonify({
        "token_number": token["token_number"],
        "patient_name": token["patient_name"],
        "department": token["department"],
        "status": token["status"],
        "currently_serving": currently_serving,
        "people_ahead": people_ahead
    })


@app.route("/api/admin/queue/<department>")
def api_admin_queue(department):
    """JSON queue status for admin live updates."""
    if department not in DEPARTMENTS:
        return jsonify({"error": "Invalid department"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    current = cursor.execute("""
        SELECT id, token_number, patient_name, phone, status, called_at 
        FROM tokens WHERE department = ? AND status = 'Serving' 
        ORDER BY id DESC LIMIT 1
    """, (department,)).fetchone()

    waiting = cursor.execute("""
        SELECT id, token_number, patient_name, phone, status, created_at 
        FROM tokens WHERE department = ? AND status = 'Waiting' 
        ORDER BY id ASC
    """, (department,)).fetchall()

    conn.close()

    return jsonify({
        "department": department,
        "current_serving": dict(current) if current else None,
        "waiting_patients": [dict(w) for w in waiting],
        "waiting_count": len(waiting)
    })


@app.route("/admin/seed-demo", methods=["POST"])
def seed_demo_data():
    """Helper button for hackathons: populates clean sample data instantly."""
    conn = get_db_connection()
    cursor = conn.cursor()

    samples = [
        ("A-001", "David Miller", "9876543210", "General Medicine", "Mild fever and sore throat", "Completed"),
        ("A-002", "Sarah Connor", "9876543211", "General Medicine", "Persistent cough and headache", "Serving"),
        ("A-003", "James Wilson", "9876543212", "General Medicine", "Stomach ache after dinner", "Waiting"),
        ("A-004", "Emily Clark", "9876543213", "General Medicine", "Seasonal flu symptoms", "Waiting"),
        ("B-001", "Robert Davis", "9123456780", "Cardiology", "High blood pressure checkup", "Serving"),
        ("B-002", "Alice Johnson", "9123456781", "Cardiology", "Occasional heart palpitations", "Waiting"),
        ("C-001", "Michael Brown", "9988776655", "Orthopedics", "Severe knee pain when walking", "Serving"),
        ("C-002", "Jessica Taylor", "9988776656", "Orthopedics", "Ankle sprain while playing sports", "Waiting"),
        ("C-003", "Daniel Thomas", "9988776657", "Orthopedics", "Lower back ache for two weeks", "Waiting"),
        ("D-001", "Baby Oliver", "9011223344", "Pediatrics", "Routine 6-month vaccination", "Serving"),
        ("D-002", "Chloe Evans (Child)", "9011223345", "Pediatrics", "Teething fever and cold", "Waiting")
    ]

    cursor.execute("DELETE FROM tokens")
    for tok, name, phone, dept, symp, stat in samples:
        cursor.execute("""
            INSERT INTO tokens (token_number, patient_name, phone, department, symptoms, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (tok, name, phone, dept, symp, stat))

    conn.commit()
    conn.close()
    flash("Demo data loaded successfully for quick presentation!", "success")
    return redirect(url_for("admin"))


if __name__ == "__main__":
    # Run simple Flask server on port 5000 with debug mode enabled
    print("=" * 60)
    print(" QueueCare - Smart Hospital Token System is running!")
    print(" Patient Portal: http://127.0.0.1:5000")
    print(" Admin Portal:   http://127.0.0.1:5000/admin")
    print("=" * 60)
    app.run(debug=True, host="127.0.0.1", port=5000)
