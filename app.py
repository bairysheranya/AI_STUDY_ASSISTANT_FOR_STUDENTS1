"""
AI Study Assistant - Complete Flask Backend
===========================================
Routes:
  /                      Landing page
  /signup  /login  /logout   Auth
  /dashboard             Main dashboard
  /upload                Upload notes (PDF/TXT/MD)
  /summary/<id>          AI summary of a note
  /ask                   AI Q&A from notes
  /quiz                  Generate + take quiz
  /quiz/submit           Score quiz, detect weak topics
  /weak-topics           View knowledge gaps
  /planner               Smart study planner
  /concept-map/<id>      Visual concept map
  /estimator/<id>        Study time estimator
  /profile               User profile + password change
  /api/notes/<id>        DELETE a note (JSON)
  /health                Health check (JSON)
"""

import os, json, sqlite3, hashlib, secrets, re
from datetime import datetime
from functools import wraps

# Load .env if python-dotenv is installed
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from flask import (Flask, render_template, request, redirect,
                   url_for, session, jsonify, flash)

# ── Optional PDF support ──────────────────────────────────────────
try:
    import PyPDF2
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

# ── Optional OpenAI ───────────────────────────────────────────────
# ── Groq AI Setup ───────────────────────────────────────────────
# ── Groq AI Setup ───────────────────────────────────────────────
try:
    from openai import OpenAI
    import os

    client = OpenAI(
        api_key=os.environ.get("GROQ_API_KEY"),
        base_url="https://api.groq.com/openai/v1"
    )

    AI_READY = True

except Exception as e:
    print("Groq AI not available:", e)
    client = None
    AI_READY = False

# ─────────────────────────────────────────────────────────────────
# App setup
# ─────────────────────────────────────────────────────────────────
app = Flask(__name__)



# Flask session secret
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.config["UPLOAD_FOLDER"]      = "uploads"
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024   # 16 MB
ALLOWED_EXT = {"pdf", "txt", "md"}
os.makedirs("uploads", exist_ok=True)

# Security headers on every response
@app.after_request
def sec(r):
    r.headers["X-Content-Type-Options"] = "nosniff"
    r.headers["X-Frame-Options"]        = "SAMEORIGIN"
    return r

# ─────────────────────────────────────────────────────────────────
# Database
# ─────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            username   TEXT UNIQUE NOT NULL,
            email      TEXT UNIQUE NOT NULL,
            password   TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS notes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            filename    TEXT NOT NULL,
            content     TEXT NOT NULL,
            uploaded_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS quizzes (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id   INTEGER NOT NULL,
            note_id   INTEGER,
            questions TEXT NOT NULL,
            score     INTEGER,
            taken_at  TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS weak_topics (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            topic       TEXT NOT NULL,
            detected_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS study_plans (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            subject    TEXT NOT NULL,
            exam_date  TEXT NOT NULL,
            plan       TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
    """)
    conn.commit()
    conn.close()

init_db()

# ─────────────────────────────────────────────────────────────────
# Auth helpers
# ─────────────────────────────────────────────────────────────────
SALT = "studyai2024"

def hash_pw(pw):
    return hashlib.sha256((SALT + pw).encode()).hexdigest()

def login_required(f):
    @wraps(f)
    def wrapped(*a, **kw):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return f(*a, **kw)
    return wrapped

def allowed(fn):
    return "." in fn and fn.rsplit(".", 1)[1].lower() in ALLOWED_EXT

# ─────────────────────────────────────────────────────────────────
# OpenAI + demo mode
# ─────────────────────────────────────────────────────────────────


DEMO = {

    "summary": (
        "## Key Points\n"
        "- **Demo mode** is active — add your `GROQ_API_KEY` to `.env` to enable real AI.\n"
        "- All non-AI features work: upload, quiz scoring, planner UI, profile.\n"
        "- Key ideas from your notes will appear as bullet points here.\n"
        "- Definitions of important terms are listed under Core Concepts.\n"
        "- A short revision paragraph appears at the bottom for quick review.\n\n"

        "## Core Concepts\n"
        "**Demo Mode:** The app runs fully without an API key. Only AI generation "
        "(summary, Q&A, quiz questions, concept map, study plan) needs one.\n\n"

        "## Quick Revision\n"
        "Add `GROQ_API_KEY=your_key_here` to your `.env` file and restart the server "
        "with `python app.py`."
    ),

    "ask": (
        "**Demo Mode** — AI answers need a Groq API key.\n\n"
        "**Steps to enable:**\n"
        "1. Go to https://console.groq.com/keys\n"
        "2. Create a new API key\n"
        "3. Open `.env` and add `GROQ_API_KEY=your_key_here`\n"
        "4. Restart the server using `python app.py`"
    ),

    "quiz": json.dumps([
        {
            "question": "This is a demo quiz. Which file holds your Groq API key?",
            "type": "mcq",
            "options": [
                "A) app.py",
                "B) .env",
                "C) requirements.txt",
                "D) database.db"
            ],
            "answer": "B"
        },
        {
            "question": "How do you restart the Flask server after adding your API key?",
            "type": "short",
            "answer": "python app.py"
        }
    ]),

    "plan": json.dumps({
        "overview": "Demo plan — add GROQ_API_KEY to .env to generate a real personalised schedule.",
        "daily_plan": [
            {
                "day": 1,
                "date": "Day 1",
                "focus": "Enable AI Features",
                "tasks": [
                    "Get your key at https://console.groq.com/keys",
                    "Add GROQ_API_KEY to .env file",
                    "Restart the app with: python app.py"
                ]
            },
            {
                "day": 2,
                "date": "Day 2",
                "focus": "Start Studying!",
                "tasks": [
                    "Upload your first note",
                    "Generate an AI summary",
                    "Take your first quiz"
                ]
            }
        ]
    }),

    "map": json.dumps({
        "root": "Demo Mode",
        "nodes": [
            {"id": 0, "label": "Demo Mode", "parent": None, "level": 0},
            {"id": 1, "label": "Add API Key", "parent": 0, "level": 1},
            {"id": 2, "label": "Restart App", "parent": 0, "level": 1},
            {"id": 3, "label": "Groq API", "parent": 1, "level": 2},
            {"id": 4, "label": ".env File", "parent": 1, "level": 2},
            {"id": 5, "label": "python app.py", "parent": 2, "level": 2}
        ]
    }),

    "estimate": json.dumps({
        "difficulty": "Demo",
        "difficulty_score": 5,
        "estimated_hours": 0,
        "practice_questions": 0,
        "key_areas": [
            "Add GROQ_API_KEY to .env",
            "Restart the server"
        ],
        "tips": [
            "Get your API key at https://console.groq.com/keys",
            "Add GROQ_API_KEY=your_key_here to your .env file",
            "Restart with: python app.py"
        ]
    })
}

def ask_ai(system, user, max_tokens=1500, demo_key="ask"):

    if not AI_READY or client is None:
        return DEMO.get(demo_key, DEMO["ask"])

    try:
        response = client.chat.completions.create(
    model="llama-3.1-8b-instant",
    messages=[
        {"role": "system", "content": system},
        {"role": "user", "content": user}
    ],
    max_tokens=max_tokens,
    temperature=0.7
)

        return response.choices[0].message.content.strip()

    except Exception as e:
        return f"AI error: {str(e)}"
       

def parse_json(raw):
    """Strip markdown fences and parse JSON."""
    clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.M)
    return json.loads(clean)

def extract_text(path, filename):
    """Extract text from uploaded file."""
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext == "pdf":
        if not PDF_SUPPORT:
            return "PDF parsing unavailable. Install PyPDF2: pip install PyPDF2"
        try:
            pages = []
            with open(path, "rb") as f:
                for page in PyPDF2.PdfReader(f).pages:
                    pages.append(page.extract_text() or "")
            return "\n".join(pages)
        except Exception as e:
            return f"Could not read PDF: {e}"
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception as e:
        return f"Could not read file: {e}"

# ─────────────────────────────────────────────────────────────────
# Error handlers
# ─────────────────────────────────────────────────────────────────
@app.errorhandler(404)
def e404(e): return render_template("404.html"), 404

@app.errorhandler(500)
def e500(e): return render_template("500.html"), 500

@app.errorhandler(413)
def e413(e):
    flash("File too large. Maximum is 16 MB.", "danger")
    return redirect(url_for("upload"))

# ─────────────────────────────────────────────────────────────────
# Public routes
# ─────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("index.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not (username and email and password):
            flash("All fields are required.", "danger")
        elif len(username) < 3:
            flash("Username must be at least 3 characters.", "danger")
        elif len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
        else:
            db = get_db()
            try:
                db.execute(
                    "INSERT INTO users (username, email, password) VALUES (?,?,?)",
                    (username, email, hash_pw(password))
                )
                db.commit()
                flash("Account created! Please log in.", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("That username or email is already taken.", "danger")
            finally:
                db.close()
    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        db   = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE email=? AND password=?",
            (email, hash_pw(password))
        ).fetchone()
        db.close()
        if user:
            session["user_id"]  = user["id"]
            session["username"] = user["username"]
            flash(f"Welcome back, {user['username']}! 👋", "success")
            return redirect(url_for("dashboard"))
        flash("Incorrect email or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You've been logged out.", "info")
    return redirect(url_for("index"))

# ─────────────────────────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────────────────────────
@app.route("/dashboard")
@login_required
def dashboard():
    uid = session["user_id"]
    db  = get_db()
    stats = {
        "notes":   db.execute("SELECT COUNT(*) FROM notes WHERE user_id=?",       (uid,)).fetchone()[0],
        "quizzes": db.execute("SELECT COUNT(*) FROM quizzes WHERE user_id=?",     (uid,)).fetchone()[0],
        "weak":    db.execute("SELECT COUNT(*) FROM weak_topics WHERE user_id=?", (uid,)).fetchone()[0],
        "plans":   db.execute("SELECT COUNT(*) FROM study_plans WHERE user_id=?", (uid,)).fetchone()[0],
    }
    recent = db.execute(
        "SELECT id, filename, uploaded_at FROM notes WHERE user_id=? "
        "ORDER BY uploaded_at DESC LIMIT 5", (uid,)
    ).fetchall()
    has_key = bool(os.environ.get("GROQ_API_KEY", "").strip())
    db.close()
    return render_template("dashboard.html", stats=stats, recent_notes=recent, has_key=has_key)

# ─────────────────────────────────────────────────────────────────
# Upload Notes
# ─────────────────────────────────────────────────────────────────
@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "POST":
        f = request.files.get("file")
        if not f or not f.filename:
            flash("Please select a file.", "danger")
            return redirect(request.url)
        if not allowed(f.filename):
            flash("Only PDF, TXT, and MD files are supported.", "danger")
            return redirect(request.url)
        fn   = f.filename
        path = os.path.join(app.config["UPLOAD_FOLDER"], fn)
        f.save(path)
        content = extract_text(path, fn)
        if not content.strip():
            flash("No text could be extracted from this file.", "warning")
            return redirect(request.url)
        db = get_db()
        db.execute("INSERT INTO notes (user_id, filename, content) VALUES (?,?,?)",
                   (session["user_id"], fn, content))
        db.commit()
        db.close()
        flash(f"'{fn}' uploaded and processed successfully! ✅", "success")
        return redirect(url_for("upload"))
    db    = get_db()
    notes = db.execute(
        "SELECT id, filename, uploaded_at FROM notes "
        "WHERE user_id=? ORDER BY uploaded_at DESC", (session["user_id"],)
    ).fetchall()
    db.close()
    return render_template("upload.html", notes=notes)

# ─────────────────────────────────────────────────────────────────
# AI Summary
# ─────────────────────────────────────────────────────────────────
@app.route("/summary/<int:note_id>")
@login_required
def summary(note_id):
    db   = get_db()
    note = db.execute("SELECT * FROM notes WHERE id=? AND user_id=?",
                      (note_id, session["user_id"])).fetchone()
    db.close()
    if not note:
        flash("Note not found.", "danger")
        return redirect(url_for("upload"))
    result = ask_ai(
        system=(
            "You are an expert academic tutor. Analyse the study notes and return "
            "a structured summary with these exact markdown sections:\n\n"
            "## Key Points\n5-7 bullet points of the most important ideas.\n\n"
            "## Core Concepts\nDefinitions of 3-5 key terms in bold.\n\n"
            "## Quick Revision\nA 3-sentence paragraph a student can memorise quickly."
        ),
        user=note["content"][:4000],
        demo_key="summary"
    )
    return render_template("summary.html", note=note, summary_text=result)

# ─────────────────────────────────────────────────────────────────
# Ask AI
# ─────────────────────────────────────────────────────────────────
@app.route("/ask", methods=["GET", "POST"])
@login_required
def ask():
    db    = get_db()
    notes = db.execute(
        "SELECT id, filename FROM notes WHERE user_id=? ORDER BY uploaded_at DESC",
        (session["user_id"],)
    ).fetchall()
    db.close()
    answer = None
    question = ""
    selected_note_id = ""
    if request.method == "POST":
        question         = request.form.get("question", "").strip()
        selected_note_id = request.form.get("note_id", "")
        if not question:
            flash("Please enter a question.", "warning")
        elif not selected_note_id:
            flash("Please select a note.", "warning")
        else:
            db   = get_db()
            note = db.execute("SELECT content FROM notes WHERE id=? AND user_id=?",
                              (selected_note_id, session["user_id"])).fetchone()
            db.close()
            if note:
                answer = ask_ai(
                    system=(
                        "You are a knowledgeable academic tutor. Answer the student's question "
                        "using the provided study notes. If the exact answer is not in the notes, "
                        "say so clearly and give a helpful general explanation. "
                        "Format your answer with markdown."
                    ),
                    user=f"Study Notes:\n{note['content'][:3500]}\n\nStudent Question: {question}",
                    demo_key="ask"
                )
            else:
                flash("Note not found.", "danger")
    return render_template("ask.html", notes=notes, answer=answer,
                           question=question, selected_note_id=selected_note_id)

# ─────────────────────────────────────────────────────────────────
# Quiz Generator
# ─────────────────────────────────────────────────────────────────
@app.route("/quiz", methods=["GET", "POST"])
@login_required
def quiz():
    db    = get_db()
    notes = db.execute(
        "SELECT id, filename FROM notes WHERE user_id=? ORDER BY uploaded_at DESC",
        (session["user_id"],)
    ).fetchall()
    db.close()
    questions = None
    note_id   = ""
    if request.method == "POST":
        note_id = request.form.get("note_id", "")
        num_q   = max(2, min(10, int(request.form.get("num_questions", 5))))
        db   = get_db()
        note = db.execute("SELECT * FROM notes WHERE id=? AND user_id=?",
                          (note_id, session["user_id"])).fetchone()
        db.close()
        if not note:
            flash("Note not found.", "danger")
            return redirect(url_for("quiz"))
        raw = ask_ai(
            system=(
                "You are an expert quiz creator. Generate quiz questions from the study notes. "
                "Return ONLY a valid JSON array — no markdown, no explanation, no text outside the array.\n"
                "Each MCQ must have: {\"question\":\"...\",\"type\":\"mcq\","
                "\"options\":[\"A) ...\",\"B) ...\",\"C) ...\",\"D) ...\"],\"answer\":\"A\"}\n"
                "Each short answer: {\"question\":\"...\",\"type\":\"short\",\"answer\":\"...\"}"
            ),
            user=(f"Create {num_q} quiz questions (mix of MCQ and short answer) "
                  f"from these study notes:\n\n{note['content'][:3500]}"),
            max_tokens=2000,
            demo_key="quiz"
        )
        try:
            questions = parse_json(raw)
            db = get_db()
            db.execute("INSERT INTO quizzes (user_id, note_id, questions) VALUES (?,?,?)",
                       (session["user_id"], note_id, json.dumps(questions)))
            db.commit()
            db.close()
        except Exception:
            flash("Could not parse the quiz. Please try again.", "danger")
            questions = None
    return render_template("quiz.html", notes=notes, questions=questions, note_id=note_id)

# ─────────────────────────────────────────────────────────────────
# Quiz Submit
# ─────────────────────────────────────────────────────────────────
@app.route("/quiz/submit", methods=["POST"])
@login_required
def quiz_submit():
    data      = request.get_json(force=True)
    questions = data.get("questions", [])
    answers   = data.get("answers", {})
    correct   = 0
    wrong_qs  = []
    for i, q in enumerate(questions):
        ua = answers.get(str(i), "").strip().lower()
        ca = q.get("answer", "").strip().lower()
        # Accept if user answer starts with correct letter (handles "A" vs "A) ...")
        if ua and ca and (ua == ca or ua[0] == ca[0]):
            correct += 1
        else:
            wrong_qs.append(q.get("question", "Unknown topic"))
    score = int(correct / len(questions) * 100) if questions else 0
    weak  = []
    if wrong_qs:
        raw = ask_ai(
            system=(
                "You are an academic advisor. Given quiz questions a student got wrong, "
                "identify the weak topics and suggest how to revise each one. "
                "Return ONLY a valid JSON array: "
                "[{\"topic\":\"Topic Name\",\"suggestion\":\"How to revise\"}]"
            ),
            user=json.dumps(wrong_qs),
            max_tokens=600,
            demo_key="ask"
        )
        try:
            weak = parse_json(raw)
        except Exception:
            weak = [{"topic": q[:60], "suggestion": "Review this topic in your notes."}
                    for q in wrong_qs]
        db = get_db()
        for item in weak:
            db.execute("INSERT INTO weak_topics (user_id, topic) VALUES (?,?)",
                       (session["user_id"], item.get("topic", "Unknown")))
        db.commit()
        db.close()
    return jsonify({"score": score, "correct": correct, "total": len(questions), "weak": weak})

# ─────────────────────────────────────────────────────────────────
# Weak Topics
# ─────────────────────────────────────────────────────────────────
@app.route("/weak-topics")
@login_required
def weak_topics():
    db     = get_db()
    topics = db.execute(
        "SELECT topic, detected_at FROM weak_topics WHERE user_id=? ORDER BY detected_at DESC",
        (session["user_id"],)
    ).fetchall()
    db.close()
    return render_template("weak_topics.html", topics=topics)

# ─────────────────────────────────────────────────────────────────
# Study Planner
# ─────────────────────────────────────────────────────────────────
@app.route("/planner", methods=["GET", "POST"])
@login_required
def planner():
    db   = get_db()
    past = db.execute(
        "SELECT subject, exam_date, created_at FROM study_plans "
        "WHERE user_id=? ORDER BY created_at DESC LIMIT 5",
        (session["user_id"],)
    ).fetchall()
    db.close()
    plan = None
    if request.method == "POST":
        subject   = request.form.get("subject", "").strip()
        exam_date = request.form.get("exam_date", "").strip()
        hours     = request.form.get("hours_per_day", "2")
        if not subject or not exam_date:
            flash("Please fill in both fields.", "warning")
        else:
            try:
                days = max(1, (datetime.strptime(exam_date, "%Y-%m-%d") - datetime.now()).days)
            except ValueError:
                days = 14
            raw = ask_ai(
                system=(
                    "You are an expert study planner. Return ONLY valid JSON:\n"
                    "{\"overview\":\"2-sentence overview\","
                    "\"daily_plan\":[{\"day\":1,\"date\":\"Mon 1 Jan\","
                    "\"focus\":\"Topic name\",\"tasks\":[\"Task 1\",\"Task 2\"]}]}"
                ),
                user=(f"Subject: {subject}\nExam date: {exam_date}\n"
                      f"Days remaining: {days}\nHours per day: {hours}\n"
                      "Create a comprehensive day-by-day study schedule."),
                max_tokens=2000,
                demo_key="plan"
            )
            try:
                plan_data = parse_json(raw)
                db = get_db()
                db.execute(
                    "INSERT INTO study_plans (user_id, subject, exam_date, plan) VALUES (?,?,?,?)",
                    (session["user_id"], subject, exam_date, json.dumps(plan_data))
                )
                db.commit()
                db.close()
                plan = {"subject": subject, "exam_date": exam_date, "data": plan_data}
            except Exception:
                flash("Could not generate plan. Please try again.", "danger")
    return render_template("planner.html", plan=plan, existing_plans=past)

# ─────────────────────────────────────────────────────────────────
# Concept Map
# ─────────────────────────────────────────────────────────────────
@app.route("/concept-map/<int:note_id>")
@login_required
def concept_map(note_id):
    db   = get_db()
    note = db.execute("SELECT * FROM notes WHERE id=? AND user_id=?",
                      (note_id, session["user_id"])).fetchone()
    db.close()
    if not note:
        flash("Note not found.", "danger")
        return redirect(url_for("upload"))
    raw = ask_ai(
        system=(
            "You are a knowledge mapper. Extract the main topic and subtopics from study notes. "
            "Return ONLY valid JSON:\n"
            "{\"root\":\"Main Topic\",\"nodes\":["
            "{\"id\":0,\"label\":\"Main Topic\",\"parent\":null,\"level\":0},"
            "{\"id\":1,\"label\":\"Subtopic\",\"parent\":0,\"level\":1}]}\n"
            "Include 8 to 14 nodes. Root node always has id=0 and parent=null."
        ),
        user=note["content"][:3500],
        max_tokens=900,
        demo_key="map"
    )
    map_data = "null"
    try:
        map_data = json.dumps(parse_json(raw))
    except Exception:
        flash("Could not generate concept map.", "warning")
    return render_template("concept_map.html", note=note, map_data=map_data)

# ─────────────────────────────────────────────────────────────────
# Study Time Estimator
# ─────────────────────────────────────────────────────────────────
@app.route("/estimator/<int:note_id>")
@login_required
def estimator(note_id):
    db   = get_db()
    note = db.execute("SELECT * FROM notes WHERE id=? AND user_id=?",
                      (note_id, session["user_id"])).fetchone()
    db.close()
    if not note:
        flash("Note not found.", "danger")
        return redirect(url_for("upload"))
    raw = ask_ai(
        system=(
            "You are an academic analyst. Estimate how long a student needs to study these notes. "
            "Return ONLY valid JSON:\n"
            "{\"difficulty\":\"Easy|Medium|Hard\","
            "\"difficulty_score\":5,"
            "\"estimated_hours\":3.5,"
            "\"practice_questions\":20,"
            "\"key_areas\":[\"area1\",\"area2\",\"area3\"],"
            "\"tips\":[\"tip1\",\"tip2\",\"tip3\"]}"
        ),
        user=note["content"][:3500],
        max_tokens=600,
        demo_key="estimate"
    )
    estimate = None
    try:
        estimate = parse_json(raw)
    except Exception:
        flash("Could not generate estimate.", "warning")
    return render_template("estimator.html", note=note, estimate=estimate)

# ─────────────────────────────────────────────────────────────────
# Profile
# ─────────────────────────────────────────────────────────────────
@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    uid = session["user_id"]
    db  = get_db()
    if request.method == "POST":
        action = request.form.get("action", "")
        if action == "change_password":
            cur  = request.form.get("current_password", "")
            new  = request.form.get("new_password", "")
            conf = request.form.get("confirm_password", "")
            user = db.execute("SELECT * FROM users WHERE id=? AND password=?",
                              (uid, hash_pw(cur))).fetchone()
            if not user:
                flash("Current password is incorrect.", "danger")
            elif new != conf:
                flash("New passwords do not match.", "danger")
            elif len(new) < 6:
                flash("Password must be at least 6 characters.", "danger")
            else:
                db.execute("UPDATE users SET password=? WHERE id=?", (hash_pw(new), uid))
                db.commit()
                flash("Password updated successfully!", "success")
        elif action == "delete_data":
            for t in ("notes", "quizzes", "weak_topics", "study_plans"):
                db.execute(f"DELETE FROM {t} WHERE user_id=?", (uid,))
            db.commit()
            flash("All study data deleted.", "info")
        db.close()
        return redirect(url_for("profile"))
    user  = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    stats = {
        "notes":   db.execute("SELECT COUNT(*) FROM notes WHERE user_id=?",       (uid,)).fetchone()[0],
        "quizzes": db.execute("SELECT COUNT(*) FROM quizzes WHERE user_id=?",     (uid,)).fetchone()[0],
        "weak":    db.execute("SELECT COUNT(*) FROM weak_topics WHERE user_id=?", (uid,)).fetchone()[0],
        "plans":   db.execute("SELECT COUNT(*) FROM study_plans WHERE user_id=?", (uid,)).fetchone()[0],
    }
    db.close()
    return render_template("profile.html", user=user, stats=stats)

# ─────────────────────────────────────────────────────────────────
# Delete note API
# ─────────────────────────────────────────────────────────────────
@app.route("/api/notes/<int:note_id>", methods=["DELETE"])
@login_required
def delete_note(note_id):
    db   = get_db()
    note = db.execute("SELECT filename FROM notes WHERE id=? AND user_id=?",
                      (note_id, session["user_id"])).fetchone()
    if note:
        db.execute("DELETE FROM notes WHERE id=?", (note_id,))
        db.execute("DELETE FROM quizzes WHERE note_id=?", (note_id,))
        db.commit()
        fp = os.path.join(app.config["UPLOAD_FOLDER"], note["filename"])
        if os.path.exists(fp):
            try: os.remove(fp)
            except: pass
    db.close()
    return jsonify({"success": True})

# ─────────────────────────────────────────────────────────────────
# Health check
# ─────────────────────────────────────────────────────────────────
@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "ai_ready": AI_READY
    })

# ─────────────────────────────────────────────────────────────────
# Run
# ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port  = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV", "development") != "production"
    app.run(debug=debug, host="0.0.0.0", port=port, use_reloader=False)
