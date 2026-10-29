import os
import json
import re
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
        CREATE TABLE IF NOT EXISTS app_settings (setting_key TEXT PRIMARY KEY, setting_value TEXT DEFAULT '');
        """)
init_db()

# Lightweight schema migration for existing local databases.
def ensure_column(table: str, column: str, definition: str):
    with db() as con:
        columns = {row["name"] for row in con.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in columns:
            con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

for column, definition in [
    ("eligibility", "TEXT DEFAULT ''"),
    ("prizes", "TEXT DEFAULT ''"),
    ("important_links", "TEXT DEFAULT ''"),
]:
    ensure_column("competitions", column, definition)

def now_iso():
    return datetime.now().astimezone().isoformat(timespec="minutes")

class CompetitionIn(BaseModel):
    name: str = Field(min_length=1, max_length=250)
    organizer: str = ""
    theme: str = ""
    eligibility: str = ""
    prizes: str = ""
    important_links: str = ""
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

class AIMessageIn(BaseModel):
    message: str = Field(min_length=5, max_length=20000)
    title: str = "College message"
    link: str = ""

class ReminderEmailsIn(BaseModel):
    emails: list[str] = []

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
        (name, organizer, theme, eligibility, prizes, important_links, source_url, registration_deadline, event_start, event_end, submission_deadline, timezone, deliverables, notes, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (data["name"], data["organizer"], data["theme"], data["eligibility"], data["prizes"], data["important_links"], data["source_url"], data["registration_deadline"], data["event_start"], data["event_end"], data["submission_deadline"], data["timezone"], data["deliverables"], data["notes"], data["status"], stamp, stamp))
        return rowdict(con.execute("SELECT * FROM competitions WHERE id=?", (cur.lastrowid,)).fetchone())

@app.put("/api/competitions/{cid}")
def update_competition(cid: int, item: CompetitionIn):
    data = item.model_dump()
    data["updated_at"] = now_iso()
    with db() as con:
        exists = con.execute("SELECT id FROM competitions WHERE id=?", (cid,)).fetchone()
        if not exists:
            raise HTTPException(404, "Competition not found")
        con.execute("""UPDATE competitions SET name=?, organizer=?, theme=?, eligibility=?, prizes=?, important_links=?, source_url=?, registration_deadline=?, event_start=?, event_end=?, submission_deadline=?, timezone=?, deliverables=?, notes=?, status=?, updated_at=? WHERE id=?""",
        (data["name"], data["organizer"], data["theme"], data["eligibility"], data["prizes"], data["important_links"], data["source_url"], data["registration_deadline"], data["event_start"], data["event_end"], data["submission_deadline"], data["timezone"], data["deliverables"], data["notes"], data["status"], data["updated_at"], cid))
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

@app.get("/api/settings/reminder-emails")
def get_reminder_emails():
    with db() as con:
        row = con.execute("SELECT setting_value FROM app_settings WHERE setting_key='reminder_emails'").fetchone()
    extras = json.loads(row["setting_value"]) if row and row["setting_value"] else []
    primary = os.getenv("REMINDER_EMAIL", "").strip()
    return {"emails": list(dict.fromkeys(([primary] if primary else []) + extras)), "primary_email": primary}

@app.put("/api/settings/reminder-emails")
def save_reminder_emails(item: ReminderEmailsIn):
    cleaned = []
    for email in item.emails:
        email = email.strip().lower()
        if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise HTTPException(400, f"Invalid email address: {email}")
        if email and email not in cleaned:
            cleaned.append(email)
    primary = os.getenv("REMINDER_EMAIL", "").strip().lower()
    extras = [e for e in cleaned if e != primary]
    with db() as con:
        con.execute("INSERT INTO app_settings(setting_key,setting_value) VALUES('reminder_emails',?) ON CONFLICT(setting_key) DO UPDATE SET setting_value=excluded.setting_value", (json.dumps(extras),))
    return {"emails": list(dict.fromkeys(([primary] if primary else []) + extras)), "primary_email": primary}

@app.post("/api/notes/ai-save")
def ai_save_message(item: AIMessageIn):
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise HTTPException(400, "AI message analysis needs GEMINI_API_KEY in your .env file.")
    import requests
    prompt = f"""Read this copied college/organizer message and extract actionable tasks and deadlines. Return ONLY valid JSON with keys: summary (short title), important_dates (short summary), tasks (array of objects with title, details, due_at, link). Do not invent deadlines. Convert explicit dates to YYYY-MM-DDTHH:MM when time is given, or YYYY-MM-DD when only date is given. Resolve relative dates only when the message provides a reliable sent/current date; otherwise leave due_at empty and mention ambiguity in details. Create only actionable tasks. Preserve the original message context in details. If there are no tasks, return an empty tasks array.

Copied message:
{item.message}"""
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    try:
        response = requests.post(endpoint, json={"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"temperature":0.1,"responseMimeType":"application/json"}}, timeout=45)
        if response.status_code >= 400:
            raise HTTPException(502, f"Gemini API error ({response.status_code}): {response.text[:250]}")
        extracted = json.loads(response.json()["candidates"][0]["content"]["parts"][0]["text"])
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"AI could not analyse this message: {str(exc)[:200]}")
    title = (extracted.get("summary") or item.title or "College message")[:250]
    with db() as con:
        cur = con.execute("INSERT INTO notes(title,content,link,remind_at,created_at) VALUES(?,?,?,?,?)", (title, item.message, item.link, "", now_iso()))
        note = rowdict(con.execute("SELECT * FROM notes WHERE id=?", (cur.lastrowid,)).fetchone())
    created = []
    for task in (extracted.get("tasks") or [])[:15]:
        if not isinstance(task, dict) or not str(task.get("title", "")).strip():
            continue
        created.append(create_task(TaskIn(title=str(task["title"])[:250], details=str(task.get("details") or "Extracted from pasted college message"), link=str(task.get("link") or item.link or ""), due_at=str(task.get("due_at") or ""))))
    return {"note": note, "tasks_created": created, "important_dates": str(extracted.get("important_dates") or ""), "message": f"Saved message and created {len(created)} task(s). Verify extracted dates."}

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
        raise HTTPException(400, "AI import needs GEMINI_API_KEY in your .env file. Add it, restart HackTrack, and retry.")
    import requests
    prompt = f"""You are extracting facts from a hackathon or competition website. Return ONLY valid JSON with these keys:
name, organizer, theme, eligibility, prizes, important_links, source_url, registration_deadline, event_start, event_end, submission_deadline, timezone, deliverables, notes, tasks.
Use empty strings for unknown fields. Never invent dates, prizes, eligibility, or links.
Dates: YYYY-MM-DDTHH:MM when time is stated, or YYYY-MM-DD when only a date is stated.
important_links: concise text containing the most useful official links found in the page (registration, rules, FAQ, submission, Discord/community, schedule), with their URLs.
tasks: array of objects, each with title, details, due_at, link. Generate only 2-6 useful tasks when supported by the competition instructions, such as read rules, form a team, choose a problem statement, prepare a prototype, create a pitch deck, submit final materials. Use empty due_at if no grounded due date is available. Do not generate generic tasks if the page gives no useful requirements.
deliverables: summarize required final submission materials.
notes: summarize other important constraints or instructions.
Source URL: {url}
Page content:
{text[:22000]}"""
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    try:
        response = requests.post(endpoint, json={"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"temperature":0.1,"responseMimeType":"application/json"}}, timeout=45)
    except requests.RequestException as exc:
        raise HTTPException(502, f"Could not reach Gemini API: {str(exc)[:200]}")
    if response.status_code >= 400:
        raise HTTPException(502, f"Gemini API error ({response.status_code}): {response.text[:300]}")
    try:
        body = response.json()
        content = body["candidates"][0]["content"]["parts"][0]["text"]
        data = json.loads(content)
        if not isinstance(data, dict) or not str(data.get("name", "")).strip():
            raise ValueError("Competition name missing")
        data.setdefault("source_url", url)
        return data
    except Exception:
        raise HTTPException(502, "AI could not reliably extract the competition details. Try a more direct official registration/rules URL or paste the page text.")

@app.post("/api/import")
def import_competition(item: ImportIn):
    text = item.text.strip()
    url = item.url.strip()
    if not text and not url:
        raise HTTPException(400, "Paste a public competition URL to import automatically.")
    if url and not text:
        # Read a public HTML page and include relevant page links as extraction context.
        import requests
        from urllib.parse import urljoin, urlparse
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                raise ValueError("Please provide a valid http:// or https:// URL.")
            r = requests.get(url, timeout=20, headers={"User-Agent":"Mozilla/5.0 (compatible; HackTrack/1.0)"})
            r.raise_for_status()
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(r.text, "html.parser")
            link_lines = []
            for a in soup.find_all("a", href=True):
                label = " ".join(a.get_text(" ", strip=True).split())
                href = urljoin(url, a["href"])
                if href.startswith(("http://", "https://")) and label and len(label) < 140:
                    link_lines.append(f"{label}: {href}")
            for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
                tag.decompose()
            page_text = soup.get_text(" ", strip=True)
            text = page_text[:18000] + "\n\nLinks found on source page:\n" + "\n".join(link_lines[:80])
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(400, f"Could not read this URL ({str(exc)[:150]}). Try the official event page or paste its text.")
    extracted = extract_with_gemini(text, url)
    extracted["source_url"] = extracted.get("source_url") or url
    extracted["status"] = "Registered"
    # Save the competition immediately: no manual form re-entry after import.
    comp_input = CompetitionIn(
        name=str(extracted.get("name") or "Untitled competition")[:250],
        organizer=str(extracted.get("organizer") or ""),
        theme=str(extracted.get("theme") or ""),
        eligibility=str(extracted.get("eligibility") or ""),
        prizes=str(extracted.get("prizes") or ""),
        important_links=str(extracted.get("important_links") or ""),
        source_url=str(extracted.get("source_url") or url),
        registration_deadline=str(extracted.get("registration_deadline") or ""),
        event_start=str(extracted.get("event_start") or ""),
        event_end=str(extracted.get("event_end") or ""),
        submission_deadline=str(extracted.get("submission_deadline") or ""),
        timezone=str(extracted.get("timezone") or "Asia/Kolkata"),
        deliverables=str(extracted.get("deliverables") or ""),
        notes=str(extracted.get("notes") or ""),
        status="Registered",
    )
    comp = create_competition(comp_input)
    created_tasks = []
    raw_tasks = extracted.get("tasks", [])
    if isinstance(raw_tasks, list):
        for task in raw_tasks[:8]:
            if not isinstance(task, dict) or not str(task.get("title", "")).strip():
                continue
            task_input = TaskIn(
                title=str(task["title"])[:250],
                details=str(task.get("details") or ""),
                link=str(task.get("link") or comp["source_url"] or ""),
                due_at=str(task.get("due_at") or ""),
                competition_id=comp["id"],
                completed=False,
            )
            created_tasks.append(create_task(task_input))
    return {"competition": comp, "tasks_created": created_tasks, "message": f"Imported {comp['name']} and created {len(created_tasks)} suggested task(s)."}

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
    primary = os.getenv("REMINDER_EMAIL", "").strip()
    port = int(os.getenv("SMTP_PORT", "587"))
    with db() as con:
        row = con.execute("SELECT setting_value FROM app_settings WHERE setting_key='reminder_emails'").fetchone()
    extras = json.loads(row["setting_value"]) if row and row["setting_value"] else []
    recipients = list(dict.fromkeys(([primary] if primary else []) + extras))
    if not all([host, user, password]) or not recipients:
        return False, "SMTP settings or reminder recipients not configured"
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = ", ".join(recipients)
    msg.set_content(body)
    try:
        with smtplib.SMTP(host, port, timeout=20) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(msg, to_addrs=recipients)
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
                    submission_due = parse_datetime(comp["submission_deadline"])
                    if submission_due:
                        hours_left = (submission_due - current).total_seconds() / 3600
                        if 0 < hours_left <= 24:
                            bucket = int((24 - hours_left) // 3)
                            key = f"submission-3hour:{comp['id']}:{bucket}"
                            exists = con.execute("SELECT id FROM sent_reminders WHERE reminder_key=?", (key,)).fetchone()
                            if not exists:
                                ok, _ = send_email(f"HackTrack: submission due soon — {comp['name']}", f"Submission deadline is approaching.\n\nCompetition: {comp['name']}\nTime remaining: about {hours_left:.1f} hours\nDeadline: {comp['submission_deadline']}\nRequired deliverables: {comp['deliverables']}\nOpen competition: {comp['source_url']}\n\nPlease verify the deadline and submit on time.")
                                if ok:
                                    con.execute("INSERT OR IGNORE INTO sent_reminders(reminder_key, sent_at) VALUES(?,?)", (key, now_iso()))
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
