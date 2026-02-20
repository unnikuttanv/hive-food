# HIVE Food Coordinator

A web app to coordinate office food orders between different companies/teams in the HIVE (Göppingen).

## Features

- **Restaurant & menu management** — Admins add restaurants and their menu items
- **Order sessions** — Create a session with a restaurant, deadline, and notes
- **Dropdown ordering** — Users pick from the restaurant's menu (or type a custom item)
- **Live order board** — Real-time view of all items, summary per person, and grand total
- **Order text** — Copy/paste-ready text for WhatsApp or phone orders
- **CSV export** — Download session data as a CSV file
- **User management** — Admin-managed accounts with company email domain restriction
- **Password management** — Users can change their own password

## Live Site

The app is hosted on Render:

> **URL:** [https://hive-food.onrender.com](https://hive-food.onrender.com)

**Note:** On the free plan, the service may spin down after inactivity. The first request after that takes ~30 seconds to wake up.

## Tech Stack

- **FastAPI** (Python) — web server and routing
- **Jinja2** — server-rendered HTML templates
- **SQLModel + SQLite** — database
- **HTMX** — lightweight interactivity without a JS framework
- **Docker** — containerised deployment on Render

## Local Development

```bash
git clone <this-repo>
cd hive-food-coordinator

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

Create a `.env` file:
```
SECRET_KEY=some-random-string
ALLOWED_EMAIL_DOMAINS=mira-vision.com
ADMIN_BOOTSTRAP_EMAIL=admin@example.com
ADMIN_BOOTSTRAP_PASSWORD=YourPassword123
```

Run:
```bash
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000

## Usage

### Admin workflow
1. Log in with the bootstrap admin credentials
2. Go to **Manage Restaurants** — add restaurants and their menu items
3. Go to **Manage Users** — create accounts for team members
4. Create an **Order Session** — pick a restaurant, set a deadline
5. Share the session link with the team
6. Close the session when the order is placed

### User workflow
1. Log in and open an active session
2. Click **Add item** — pick from the restaurant's menu dropdown
3. Adjust quantity, override price, or add notes
4. Done — the admin handles the rest

## Security Notes

- Passwords are hashed with bcrypt
- Cookie-based session auth (signed tokens)
- Company email domain allow-list for account creation
