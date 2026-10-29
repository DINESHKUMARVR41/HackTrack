import os
import json
import sqlite3
import smtplib
import threading
import time
from datetime import datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()
BASE_DIR = Path(__file__).parent
DB_PATH = os.getenv("DATABASE_PATH", str(BASE_DIR / "hacktrack.db"))
app = FastAPI(title="HackTrack", description="Personal hackathon and competition manager")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS competitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            organizer TEXT DEFAULT '',
            theme TEXT DEFAULT '',
            source_url TEXT DEFAULT '',
            registration_deadline TEXT DEFAULT '',
            event_start TEXT DEFAULT '',
            event_end TEXT DEFAULT '',
            submission_deadline TEXT DEFAULT '',
            timezone TEXT DEFAULT 'Asia/Kolkata',
            deliverables TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            status TEXT DEFAULT 'Registered',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            details TEXT DEFAULT '',
            link TEXT DEFAULT '',
            due_at TEXT DEFAULT '',
            completed INTEGER DEFAULT 0,
            competition_id INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY(competition_id) REFERENCES competitions(id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT DEFAULT '',
            link TEXT DEFAULT '',
            remind_at TEXT DEFAULT '',
            reminded INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sent_reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reminder_key TEXT UNIQUE NOT NULL,
            sent_at TEXT NOT NULL
        );
        """)
init_db()

def now_iso():
    return datetime.now().astimezone().isoformat(timespec="minutes")

class CompetitionIn(BaseModel):
    name: str = Field(min_length=1, max_length=250)
    organizer: str = ""
    theme: str = ""
    source_url: str = ""
    registration_deadline: str = ""
    event_start: str = ""
    event_end: str = ""
    submission_deadline: str = ""
    timezone: str = "Asia/Kolkata"
    deliverables: str = ""
    notes: str = ""
    status: str = "Registered"

class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=250)
    details: str = ""
    link: str = ""
    due_at: str = ""
    competition_id: Optional[int] = None
    completed: bool = False

class NoteIn(BaseModel):
    title: str = Field(min_length=1, max_length=250)
    content: str = ""
    link: str = ""
    remind_at: str = ""

class ImportIn(BaseModel):
    text: str = ""
    url: str = ""

def rowdict(row):
    return dict(row) if row else None

@app.get("/", response_class=HTMLResponse)
def home():
    return (BASE_DIR / "static" / "index.html").read_text(encoding="utf-8")

@app.get("/api/health")
def health():
    return {"ok": True, "app": "HackTrack"}

@app.get("/api/competitions")
def list_competitions():
    with db() as con:
        rows = con.execute("SELECT * FROM competitions ORDER BY CASE WHEN submission_deadline != '' THEN submission_deadline WHEN registration_deadline != '' THEN registration_deadline WHEN event_start != '' THEN event_start ELSE '9999' END ASC").fetchall()
    return [rowdict(r) for r in rows]

@app.post("/api/competitions")
def create_competition(item: CompetitionIn):
    stamp = now_iso()
    data = item.model_dump()
    with db() as con:
        cur = con.execute("""INSERT INTO competitions
        (name, organizer, theme, source_url, registration_deadline, event_start, event_end, submission_deadline, timezone, deliverables, notes, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (data["name"], data["organizer"], data["theme"], data["source_url"], data["registration_deadline"], data["event_start"], data["event_end"], data["submission_deadline"], data["timezone"], data["deliverables"], data["notes"], data["status"], stamp, stamp))
        return rowdict(con.execute("SELECT * FROM competitions WHERE id=?", (cur.lastrowid,)).fetchone())

@app.put("/api/competitions/{cid}")
def update_competition(cid: int, item: CompetitionIn):
    data = item.model_dump()
    data["updated_at"] = now_iso()
    with db() as con:
        exists = con.execute("SELECT id FROM competitions WHERE id=?", (cid,)).fetchone()
        if not exists:
            raise HTTPException(404, "Competition not found")
        con.execute("""UPDATE competitions SET name=?, organizer=?, theme=?, source_url=?, registration_deadline=?, event_start=?, event_end=?, submission_deadline=?, timezone=?, deliverables=?, notes=?, status=?, updated_at=? WHERE id=?""",
        (data["name"], data["organizer"], data["theme"], data["source_url"], data["registration_deadline"], data["event_start"], data["event_end"], data["submission_deadline"], data["timezone"], data["deliverables"], data["notes"], data["status"], data["updated_at"], cid))
        return rowdict(con.execute("SELECT * FROM competitions WHERE id=?", (cid,)).fetchone())

@app.delete("/api/competitions/{cid}")
def delete_competition(cid: int):
    with db() as con:
        cur = con.execute("DELETE FROM competitions WHERE id=?", (cid,))
        if not cur.rowcount:
            raise HTTPException(404, "Competition not found")
    return {"ok": True}

@app.get("/api/tasks")
def list_tasks():
    with db() as con:
        rows = con.execute("""SELECT tasks.*, competitions.name AS competition_name FROM tasks
        LEFT JOIN competitions ON competitions.id=tasks.competition_id
        ORDER BY CASE WHEN due_at != '' THEN due_at ELSE '9999' END ASC, completed ASC""").fetchall()
    return [rowdict(r) for r in rows]

@app.post("/api/tasks")
def create_task(item: TaskIn):
    if item.competition_id:
        with db() as con:
            if not con.execute("SELECT id FROM competitions WHERE id=?", (item.competition_id,)).fetchone():
                raise HTTPException(400, "Competition does not exist")
    with db() as con:
        cur = con.execute("INSERT INTO tasks(title, details, link, due_at, completed, competition_id, created_at) VALUES(?,?,?,?,?,?,?)",
            (item.title, item.details, item.link, item.due_at, int(item.completed), item.competition_id, now_iso()))
        return rowdict(con.execute("""SELECT tasks.*, competitions.name AS competition_name FROM tasks LEFT JOIN competitions ON competitions.id=tasks.competition_id WHERE tasks.id=?""", (cur.lastrowid,)).fetchone())

@app.patch("/api/tasks/{tid}")
def toggle_task(tid: int):
    with db() as con:
        row = con.execute("SELECT completed FROM tasks WHERE id=?", (tid,)).fetchone()
        if not row:
            raise HTTPException(404, "Task not found")
        newval = 0 if row["completed"] else 1
        con.execute("UPDATE tasks SET completed=? WHERE id=?", (newval, tid))
        return {"id": tid, "completed": bool(newval)}

@app.delete("/api/tasks/{tid}")
def delete_task(tid: int):
    with db() as con:
        cur = con.execute("DELETE FROM tasks WHERE id=?", (tid,))
        if not cur.rowcount:
            raise HTTPException(404, "Task not found")
    return {"ok": True}

@app.get("/api/notes")
def list_notes():
    with db() as con:
        rows = con.execute("SELECT * FROM notes ORDER BY CASE WHEN remind_at != '' THEN remind_at ELSE '9999' END ASC, id DESC").fetchall()
    return [rowdict(r) for r in rows]

@app.post("/api/notes")
def create_note(item: NoteIn):
    with db() as con:
        cur = con.execute("INSERT INTO notes(title, content, link, remind_at, created_at) VALUES(?,?,?,?,?)",
            (item.title, item.content, item.link, item.remind_at, now_iso()))
        return rowdict(con.execute("SELECT * FROM notes WHERE id=?", (cur.lastrowid,)).fetchone())

@app.delete("/api/notes/{nid}")
def delete_note(nid: int):
    with db() as con:
        cur = con.execute("DELETE FROM notes WHERE id=?", (nid,))
        if not cur.rowcount:
            raise HTTPException(404, "Note not found")
    return {"ok": True}

@app.get("/api/export")
def export_data():
    with db() as con:
        competitions = [rowdict(r) for r in con.execute("SELECT * FROM competitions").fetchall()]
        tasks = [rowdict(r) for r in con.execute("SELECT * FROM tasks").fetchall()]
        notes = [rowdict(r) for r in con.execute("SELECT * FROM notes").fetchall()]
    return {"exported_at": now_iso(), "competitions": competitions, "tasks": tasks, "notes": notes}

def extract_with_gemini(text: str, url: str = ""):
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise HTTPException(400, "Add GEMINI_API_KEY to .env to enable AI extraction. You can still add competitions manually.")
    import requests
    prompt = f"""Extract hackathon/competition details from the provided content. Return ONLY valid JSON with these keys:
name, organizer, theme, source_url, registration_deadline, event_start, event_end, submission_deadline, timezone, deliverables, notes.
Use empty strings for unknown values. Do not guess dates. Dates must be ISO-like local datetime strings YYYY-MM-DDTHH:MM when a time is known, or YYYY-MM-DD when only date is known. Keep deliverables concise.
Source URL: {url}
Content:
{text[:18000]}"""
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    response = requests.post(endpoint, json={"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"temperature":0.1,"responseMimeType":"application/json"}}, timeout=45)
    if response.status_code >= 400:
        raise HTTPException(502, f"Gemini API error ({response.status_code}): {response.text[:300]}")
    body = response.json()
    try:
        content = body["candidates"][0]["content"]["parts"][0]["text"]
        data = json.loads(content)
        if not isinstance(data, dict):
            raise ValueError("Expected a JSON object")
        data.setdefault("source_url", url)
        return data
    except Exception:
        raise HTTPException(502, "AI returned an unexpected format. Try pasting more of the competition page text or add it manually.")

@app.post("/api/import")
def import_competition(item: ImportIn):
    text = item.text.strip()
    url = item.url.strip()
    if not text and not url:
        raise HTTPException(400, "Paste page text or provide a URL.")
    if url and not text:
        # Fetch simple public pages; JS-heavy/login-protected pages may not work.
        import requests
        try:
            r = requests.get(url, timeout=15, headers={"User-Agent":"HackTrack/1.0 (personal competition organizer)"})
            r.raise_for_status()
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(r.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            text = soup.get_text(" ", strip=True)[:18000]
        except Exception as exc:
            raise HTTPException(400, f"Could not read this URL ({str(exc)[:150]}). Paste the page text instead.")
    return extract_with_gemini(text, url)

def parse_datetime(value):
    if not value:
        return None
    try:
        # Browser datetime-local values have no timezone; interpret in server local timezone.
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.astimezone()
        return parsed
    except Exception:
        return None

def send_email(subject, body):
    host = os.getenv("SMTP_HOST", "").strip()
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    to = os.getenv("REMINDER_EMAIL", "").strip()
    port = int(os.getenv("SMTP_PORT", "587"))
    if not all([host, user, password, to]):
        return False, "SMTP settings not configured"
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to
    msg.set_content(body)
    try:
        with smtplib.SMTP(host, port, timeout=20) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(msg)
        return True, "sent"
    except Exception as exc:
        return False, str(exc)

def reminder_loop():
    # Local development scheduler. Production deployment should use a persistent worker/cron.
    while True:
        try:
            current = datetime.now().astimezone()
            with db() as con:
                competitions = con.execute("SELECT * FROM competitions WHERE status NOT IN ('Completed','Cancelled','Archived')").fetchall()
                notes = con.execute("SELECT * FROM notes WHERE reminded=0 AND remind_at!=''").fetchall()
                tasks = con.execute("SELECT * FROM tasks WHERE completed=0 AND due_at!=''").fetchall()
                for comp in competitions:
                    for field in ["registration_deadline", "submission_deadline", "event_start"]:
                        due = parse_datetime(comp[field])
                        if not due:
                            continue
                        for days_before in [7, 3, 1]:
                            target = due - timedelta(days=days_before)
                            # Send within a 20-minute window after the target.
                            if target <= current < target + timedelta(minutes=20):
                                key = f"competition:{comp['id']}:{field}:{days_before}"
                                exists = con.execute("SELECT id FROM sent_reminders WHERE reminder_key=?", (key,)).fetchone()
                                if not exists:
                                    ok, _ = send_email(f"HackTrack reminder: {comp['name']}", f"{comp['name']} has {field.replace('_',' ')} in {days_before} day(s).\nDeadline: {comp[field]}\nTheme: {comp['theme']}\nLink: {comp['source_url']}")
                                    if ok:
                                        con.execute("INSERT OR IGNORE INTO sent_reminders(reminder_key, sent_at) VALUES(?,?)", (key, now_iso()))
                for note in notes:
                    due = parse_datetime(note["remind_at"])
                    if due and due <= current:
                        key = f"note:{note['id']}"
                        ok, _ = send_email(f"HackTrack note reminder: {note['title']}", f"{note['title']}\n\n{note['content']}\n{note['link']}")
                        if ok:
                            con.execute("UPDATE notes SET reminded=1 WHERE id=?", (note["id"],))
                            con.execute("INSERT OR IGNORE INTO sent_reminders(reminder_key, sent_at) VALUES(?,?)", (key, now_iso()))
                for task in tasks:
                    due = parse_datetime(task["due_at"])
                    if due and current >= due:
                        key = f"task-overdue:{task['id']}"
                        exists = con.execute("SELECT id FROM sent_reminders WHERE reminder_key=?", (key,)).fetchone()
                        if not exists:
                            ok, _ = send_email(f"HackTrack task due: {task['title']}", f"Task: {task['title']}\nDue: {task['due_at']}\n{task['details']}\n{task['link']}")
                            if ok:
                                con.execute("INSERT OR IGNORE INTO sent_reminders(reminder_key, sent_at) VALUES(?,?)", (key, now_iso()))
        except Exception as exc:
            print("Reminder scheduler error:", exc)
        time.sleep(60)

@app.on_event("startup")
def startup():
    if os.getenv("ENABLE_LOCAL_SCHEDULER", "true").lower() == "true":
        threading.Thread(target=reminder_loop, daemon=True).start()
