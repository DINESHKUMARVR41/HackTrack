# HackTrack — Hackathon & Competition Manager

HackTrack is a personal organizer for hackathons, competitions, deadlines, tasks, notes, and reminders.

## Features

- Add, edit, delete, complete, and archive competitions.
- Dashboard with upcoming deadlines and countdowns.
- Track registration, event, and submission dates separately.
- Save organizer, theme, official URL, deliverables, eligibility, prizes, important links, and notes.
- Import a public competition URL with Gemini AI and save the extracted details.
- Paste college/organizer messages for AI-assisted task and deadline extraction.
- Create notes and tasks with due dates.
- Select reminder provider using `REMINDER_MODE`: `ntfy`, `textbee`, or `email`.
- Send a test notification from the app.
- Export data as JSON.
- SQLite storage for local use.

## Requirements

- Python 3.11 or newer
- Optional Gemini API key from https://aistudio.google.com/ for AI extraction
- One optional reminder provider: ntfy, Textbee, or email

## Run locally on Windows (PowerShell)

1. Extract the ZIP and open the project folder in VS Code.
2. In PowerShell, navigate to the project directory:

```powershell
cd path\to\HackTrack-main
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

3. Open `.env` in VS Code and configure the AI key if you want AI extraction and configure one notification provider using the instructions below.
4. Start HackTrack:

```powershell
uvicorn app:app --reload
```

5. Open http://127.0.0.1:8000. The **Notification setup** panel shows the selected provider and includes a test notification button.

No Gemini key is required for manually adding competitions, tasks, and notes.

## Option A — ntfy push notifications (recommended for easiest setup)

ntfy sends a push notification to the ntfy app on your phone. It does not require a SIM or an SMS provider.

1. Install the ntfy app from https://ntfy.sh/ or your device's app store.
2. Open the app and subscribe to a topic.
3. Choose a long, unpredictable topic name. Example format: `hacktrack-dinesh-` followed by a long random string. Do not use the example literally.
4. In `.env`, set:

```env
REMINDER_MODE=ntfy
NTFY_SERVER=https://ntfy.sh
NTFY_TOPIC=your-long-random-topic-name
NTFY_TOKEN=
NTFY_PRIORITY=3
```

5. Save `.env`, restart the server, and click **Send test notification** in HackTrack.
6. If the phone receives the test notification, ntfy is configured.

**Privacy note:** public ntfy topics are not private by default. Anyone who discovers the topic may be able to publish to or read messages from it. Use an unpredictable topic name and avoid sending sensitive personal information. For stronger access control, use an authenticated ntfy setup/server and configure `NTFY_TOKEN` if applicable.

## Option B — Textbee SMS

Textbee sends SMS using your own Android phone and SIM. The phone needs Android 7.0 or newer, an active SIM capable of sending SMS, internet access, and permission to run in the background. Check current plan limits and carrier charges before relying on it.

1. Create an account at https://textbee.dev/ and verify your email.
2. Download and install the Android app from https://textbee.dev/download.
3. Register your phone using the dashboard QR code or the app's manual registration flow.
4. Grant the required SMS permission. Set the app's battery use to unrestricted and keep the phone connected to the internet.
5. Create an API key in the Textbee dashboard.
6. In `.env`, set:

```env
REMINDER_MODE=textbee
TEXTBEE_API_KEY=your_textbee_api_key
TEXTBEE_RECIPIENTS=+91XXXXXXXXXX
TEXTBEE_API_URL=https://api.textbee.dev/api/v1/gateway/send-sms
```

Replace `+91XXXXXXXXXX` with the recipient's number in international format. Multiple recipients can be comma-separated. Do not commit your API key to GitHub.

7. Save `.env`, restart HackTrack, and click **Send test notification**.
8. If the API accepts the message, check Textbee's message history and your phone's SMS app to verify actual delivery. An API success response means the request was accepted, not necessarily delivered.

Textbee's free plan and usage limits may change. The phone must stay powered on, connected, and allowed to run in the background. Messages can be delayed if the phone is offline or Android pauses the app.

## Option C — Email reminders

Set `REMINDER_MODE=email` and configure SMTP settings in `.env`:

```env
REMINDER_MODE=email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=youraddress@gmail.com
SMTP_PASSWORD=your-gmail-app-password
REMINDER_EMAIL=youraddress@gmail.com
```

For Gmail, use an App Password (after enabling 2-Step Verification), not your normal Google password. Additional email recipients can still be managed using the existing reminder-email API endpoints.

## Reminder schedule

The scheduler checks once per minute while the local application process is running. It sends:

- Competition reminders 7, 3, and 1 day before registration deadlines, submission deadlines, and event start dates.
- Extra submission reminders every 3 hours during the final 24 hours before a submission deadline.
- Note reminders at the requested time.
- Task reminders when tasks become overdue.

Successful reminder requests are recorded to reduce duplicate notifications. A notification provider accepting a request does not guarantee final delivery.

## Deployment notes — important

- `ENABLE_LOCAL_SCHEDULER=true` starts the scheduler inside the web application. This is suitable for local testing, but a host that sleeps, restarts, or runs multiple app instances can miss or duplicate reminders.
- For hosted deployment, use a persistent database and a separate scheduled job/worker. If a GitHub Actions workflow runs the reminder checker, set `ENABLE_LOCAL_SCHEDULER=false` on the web service and make the scheduled job use the same database. GitHub scheduled workflows can be delayed; do not treat them as exact-time delivery guarantees.
- The default database is `hacktrack.db`, a local SQLite file. Do not rely on it for permanent storage on hosts with ephemeral filesystems. Back it up using Export JSON or move to persistent storage/PostgreSQL for hosted deployment.
- This project is a single-user personal MVP and does not include authentication. Do not expose it publicly with private data or notification controls until authentication and appropriate access restrictions have been added.
- Keep `.env`, API keys, and private notification topic details out of GitHub.

## Data storage and backup

By default, data is stored in `hacktrack.db` in the project folder. Use **Export JSON** regularly. Deleting a competition unlinks associated tasks rather than deleting them.

## API documentation

After starting the server, visit http://127.0.0.1:8000/docs.
