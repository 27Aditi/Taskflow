# TaskFlow

A lightweight, multi-user task board — think a minimal Trello/Jira. Built to practice core backend engineering: auth, relational data modeling, REST API design, and access control, with a small vanilla JS frontend on top.

**Live demo:** _add your Render URL here after deploying_

## Features

- Email/password signup and login with JWT authentication
- Create boards and invite teammates by email
- Owner vs member roles per board
- Create, assign, update, and delete tasks
- Three-column status view: To do / In progress / Done
- Access control — a user can only see boards they own or were invited to

## Tech stack

| Layer     | Choice                                  |
|-----------|------------------------------------------|
| Backend   | FastAPI (Python), Pydantic v2            |
| Auth      | JWT (python-jose) + bcrypt password hashing |
| Database  | SQLAlchemy ORM — SQLite locally, PostgreSQL in production |
| Frontend  | Vanilla JS, HTML, CSS (no framework/build step) |
| Testing   | Pytest + FastAPI TestClient              |
| Hosting   | Render (web service + managed Postgres)  |

## Project structure

```
taskflow/
├── backend/
│   ├── main.py          # FastAPI app + all routes
│   ├── models.py        # SQLAlchemy models (User, Board, BoardMember, Task)
│   ├── schemas.py        # Pydantic request/response schemas
│   ├── auth.py           # Password hashing, JWT issuing/verification
│   ├── database.py       # DB engine/session setup
│   └── test_main.py      # API test suite
├── static/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── requirements.txt
├── render.yaml            # One-click Render deployment config
└── .env.example
```

## Architecture

```
Browser (static/*)
     │  fetch() calls, JWT in Authorization header
     ▼
FastAPI app (backend/main.py)
     │  Depends(get_current_user) on every protected route
     ▼
SQLAlchemy ORM (backend/models.py)
     │
     ▼
SQLite (dev)  /  PostgreSQL (prod, via Render)
```

The backend serves both the JSON API (`/api/...`) and the static frontend from a single FastAPI process, so there's only one service to deploy.

**Data model:** `User` 1—N `Board` (as owner), `Board` N—N `User` through `BoardMember` (for invited teammates + roles), `Board` 1—N `Task`, `Task` N—1 `User` (assignee).

## Running locally

```bash
git clone <your-repo-url>
cd taskflow

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env            # then edit SECRET_KEY

cd backend
uvicorn main:app --reload
```

Visit `http://localhost:8000`. By default it uses a local SQLite file (`taskflow.db`) — no extra setup needed.

## Running tests

```bash
cd backend
pytest -v
```

Covers signup/login, board creation, the full task lifecycle (create → update → delete), and access control (a user can't reach another user's board).

## Deploying to Render

This repo includes a `render.yaml` (Render's "Infrastructure as Code" blueprint), so deployment is mostly one click:

1. Push this repo to GitHub.
2. In Render, choose **New → Blueprint** and point it at the repo. Render reads `render.yaml` and provisions:
   - a **web service** (installs `requirements.txt`, runs `uvicorn main:app` from `backend/`)
   - a **free PostgreSQL database**, wired up automatically via the `DATABASE_URL` env var
3. Render also auto-generates a random `SECRET_KEY` for JWT signing — no manual setup needed.
4. Wait for the build to finish, then open the service URL. That's it — frontend and API are both served from that one URL.

No Blueprint support, or want to configure manually instead:

- **Build command:** `pip install -r requirements.txt`
- **Start command:** `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Environment variables:** `SECRET_KEY` (any long random string), `DATABASE_URL` (Render Postgres connection string — the app auto-converts `postgres://` to `postgresql://` if needed)

## Design/trade-off notes

- **SQLite → Postgres switch is env-driven**, not hardcoded — `database.py` reads `DATABASE_URL` and falls back to SQLite, so the same codebase runs locally with zero config and in production against a real database.
- **JWT over server-side sessions** — keeps the API stateless, which matters if this ever needs to scale past one instance.
- **Single-process deploy** (API + static files from one FastAPI app) instead of a separate frontend build/deploy — fewer moving parts for a project this size; would split them if the frontend grew into a real SPA framework.
- **No task board drag-and-drop yet** — status changes go through the task modal rather than drag events. Kept scope tight to ship a complete, tested vertical slice rather than a half-built stretch feature.

## Possible next steps

- WebSocket-based live updates when teammates move tasks
- Drag-and-drop between columns
- Due dates + email reminders
- Board-level activity log
