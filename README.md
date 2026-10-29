# HackTrack — Hackathon & Competition Manager

A practical personal organizer for hackathons, competitions, deadlines, tasks, notes, and reminders.

## Features

- Add, edit, delete, complete, and archive competition records (status values include Registered, Preparing, Submitted, Completed, Cancelled, Archived).
- Dashboard with active competitions, urgent deadlines, countdowns, and sorted timeline.
- Track registration, event, and submission dates separately.
- Keep theme, organizer, official URL, deliverables, and notes for each competition.
- Import details from pasted registration-page text or a public URL using Gemini API.
- Separate Notes & Tasks pages for saved links, reminders, and to-dos.
- Optional email reminders through SMTP.
- Export your data as JSON.
- SQLite database: no external database account required for local use.

## Requirements

- Python 3.11 or newer
- Optional Gemini API key from https://aistudio.google.com/
- Optional SMTP email account for email reminders

## Run locally on Windows (PowerShell)

```powershell
# 1. Extract the ZIP and open the hacktrack folder in VS Code
cd path\to\hacktrack

# 2. Create and activate a virtual environment
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install packages
python -m pip install -r requirements.txt

# 4. Create your local environment file
Copy-Item .env.example .env

# 5. Edit .env and add GEMINI_API_KEY for AI import.
#    Add SMTP settings if you want email reminders.

# 6. Start the server
uvicorn app:app --reload

# 7. Open http://127.0.0.1:8000
```

No API key is needed for manual competition, task, or note management. AI import requires a Gemini API key. Do not commit `.env` to GitHub.

## AI import

- Use **Paste page text** for the most reliable results.
- URL import tries to fetch public HTML and extract readable text. JavaScript-heavy sites, login-protected pages, and bot-protected pages may fail.
- AI-extracted fields are returned to an editable review form; verify dates and timezone before saving.
- Unknown dates should remain blank. The app prompts the model not to invent dates.

## Email reminders

Set these in `.env`:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=youraddress@gmail.com
SMTP_PASSWORD=your-16-character-app-password
REMINDER_EMAIL=youraddress@gmail.com
```

For Gmail, create an App Password after enabling 2-Step Verification. Do not use your regular Google account password.

The local scheduler checks once per minute while the app process is running. It emails competition reminders 7, 3, and 1 day before registration deadlines, submission deadlines, and event start dates. It also sends note reminders at their scheduled time and task reminders when tasks become overdue.

**Important limitations:**
- Local email scheduling works only while the Python process is running.
- For production, run the scheduler as a persistent worker or scheduled job. Some free web hosts sleep or stop background processes, so reminders may not run reliably there.
- The current implementation is designed for a single personal user/local MVP, not a multi-user public service.
- Date-only values are interpreted using the server's local timezone. Include a time for more precise reminders.
- Competition reminders are sent only when the scheduler catches the reminder window. Keep the process running; production scheduling should use a robust persistent scheduler and wider missed-run handling.
- Email delivery depends on SMTP provider limits and configuration.

## Data storage and backup

Data is stored in `hacktrack.db` in the project folder by default. Use **Export JSON** regularly to create a backup. Deleting a competition sets associated tasks' competition links to null, rather than deleting the tasks.

## API docs

After starting the server, visit http://127.0.0.1:8000/docs.

## Suggested next improvements

- Add authentication before any public deployment.
- Move to PostgreSQL/Supabase for hosted multi-device usage.
- Add a robust persistent scheduler such as a dedicated worker/cron service.
- Add Google Calendar integration and Telegram notifications.
- Add import support for PDFs and confirmation emails.
- Add tests, migrations, and deployment-specific health checks.
