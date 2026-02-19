# HIVE Food Coordinator (MVP)

A small web app to coordinate office food orders between different companies/teams in the HIVE (Göppingen).

## What it does (MVP)

- Web-based (browser accessible)
- User management via company email (domain allow-list)
- Create "Order Sessions" (restaurant + deadline)
- People add their items (name, qty, price, notes)
- Live order board and summary (total per person, total for session)
- Lock/close an order when placed; export a concise "order text" for WhatsApp/call
- Basic roles:
  - **Admin** (e.g., HIVE managers): can see all sessions, can create/close, can manage allowed domains via config
  - **User**: can create sessions, join sessions, add/edit their own items

> This is an MVP intentionally kept simple: SQLite DB, cookie-session auth, server-rendered templates.

---

## Tech Stack

- **FastAPI** (Python) for web server and routing
- **Jinja2** templates for HTML
- **SQLModel + SQLite** for persistence
- **HTMX** for small interactive updates (no heavy SPA required)

---

## Setup (Local)

### 1) Prerequisites
- Python 3.11+ recommended

### 2) Install & configure
```bash
git clone <this-repo>
cd hive-food-coordinator

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:
- `SECRET_KEY`: set to a random value
- `ALLOWED_EMAIL_DOMAINS`: comma-separated list (e.g. `mira-vision.com,company2.de`)
- `ADMIN_BOOTSTRAP_EMAIL` / `ADMIN_BOOTSTRAP_PASSWORD`: initial admin login

### 3) Run
```bash
uvicorn app.main:app --reload
```

Open:
- http://127.0.0.1:8000

---

## Setup (Docker)

```bash
docker build -t hive-food .
docker run --rm -p 8000:8000 --env-file .env -v "$(pwd)/hive_food.db:/app/hive_food.db" hive-food
```

Open:
- http://127.0.0.1:8000

---

## Using the App

### First login (bootstrap admin)
1. Go to `/login`
2. Sign in using `ADMIN_BOOTSTRAP_EMAIL` / `ADMIN_BOOTSTRAP_PASSWORD`
3. From the dashboard, create an order session.

### Invite users
Users can self-register with their **company email**, as long as the domain is on the allow-list:
- Example: `@mira-vision.com`, `@hive-gp.de`, `@partner-company.de`

### Create an order session
- Restaurant name + optional URL
- Deadline (after that, the session auto-locks for edits)
- Optional notes (e.g., “Please add price if possible”)

### Join / add items
- Open the session
- Add items
- Edit/delete your own items until the session is locked/closed

### Place order / close session
- Click **Close session**
- Copy the “Order Text” block to call/WhatsApp the restaurant
- Export CSV if needed

---

## Deploy to the Cloud (share a link)

The easiest way to host this app for free and get a shareable URL is **[Render.com](https://render.com)**:

### One-click deploy with Render

1. Push this repo to your GitHub account (or fork it).
2. Go to [https://dashboard.render.com/](https://dashboard.render.com/) and sign up / log in.
3. Click **New → Blueprint** and connect your GitHub repository.
4. Render will detect the `render.yaml` file and set up the service automatically.
5. Update the environment variables (`ADMIN_BOOTSTRAP_EMAIL`, `ADMIN_BOOTSTRAP_PASSWORD`, `ALLOWED_EMAIL_DOMAINS`) in the Render dashboard under **Environment**.
6. Your app will be live at `https://hive-food.onrender.com` (or a similar URL).

> **Tip:** On the free plan, the service spins down after 15 minutes of inactivity. The first request after that takes ~30 seconds to wake up.

> **⚠️ Data persistence:** Render's free tier uses an ephemeral filesystem — SQLite data is lost on every redeploy or restart. For production use, switch to a managed PostgreSQL database (Render offers a free PostgreSQL instance).

### Manual deploy with Render

1. Go to [https://dashboard.render.com/](https://dashboard.render.com/) and click **New → Web Service**.
2. Connect your GitHub repo and select it.
3. Choose **Docker** as the environment.
4. Set the following environment variables:
   - `SECRET_KEY` — a random string (Render can generate one for you)
   - `ALLOWED_EMAIL_DOMAINS` — e.g., `mira-vision.com,company2.de`
   - `ADMIN_BOOTSTRAP_EMAIL` — initial admin email
   - `ADMIN_BOOTSTRAP_PASSWORD` — initial admin password
   - `DATABASE_URL` — `sqlite:///./hive_food.db`
5. Click **Create Web Service** and share the URL!

### Other hosting options

You can deploy this app anywhere Docker is supported:

| Platform | Free tier | Notes |
|----------|-----------|-------|
| [Render](https://render.com) | ✅ Yes | Recommended — `render.yaml` included |
| [Fly.io](https://fly.io) | ✅ Yes | Use `fly launch` with the existing Dockerfile |
| [Railway](https://railway.app) | Trial | Auto-detects Dockerfile |
| Any VPS | N/A | `docker build -t hive-food . && docker run -p 8000:8000 --env-file .env hive-food` |

---

## Security Notes (MVP)

- Passwords are hashed (bcrypt).
- Cookie-based session auth (server-side signing).
- Domain allow-list to enforce "company email" usage.

For production:
- Use HTTPS
- Add email verification and/or SSO (Microsoft Entra / Google Workspace)
- Move to Postgres and add migrations (Alembic)
- Add audit logs and rate limiting

---

## Future features (ideas)

See section 1.2 in the accompanying write-up in the chat response (architecture notes).
