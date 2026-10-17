# 🔭 Celestial Classifier

Upload a space image and **Google Gemini** tells you what it is: black hole, galaxy, star,
planet, moon, nebula, cosmic/star dust, star cluster, supernova remnant, comet, asteroid,
quasar, other celestial object, or **not celestial at all**.
Every classification (including the image) is stored in **PostgreSQL**, so your
observation log and statistics survive container restarts.

```
┌──────────────┐   HTTP :8000   ┌────────────────────┐   SQL (celestial-net)   ┌──────────────────┐
│   Browser    │ ─────────────▶ │  backend (FastAPI) │ ──────────────────────▶ │ db (PostgreSQL)  │
└──────────────┘                └─────────┬──────────┘                         └────────┬─────────┘
                                          │ image + prompt                              │
                                          ▼                                    named volume: celestial_pgdata
                                  Gemini API (AI Studio)
```

## Quick start

```bash
# 1. Create your local env file (never committed)
cp .env.example .env            # PowerShell: Copy-Item .env.example .env

# 2. Edit .env: set POSTGRES_PASSWORD and (optionally) GEMINI_API_KEY
#    Free key: https://aistudio.google.com/apikey

# 3. Start everything
docker compose up --build
```

Open **http://localhost:8000**. The interactive API docs are at **http://localhost:8000/docs**.

> **No API key?** With `CLASSIFIER_MODE=auto` (the default), the app falls back to a
> deterministic **mock classifier** when `GEMINI_API_KEY` is empty. The whole stack
> (upload → DB write → history/stats DB read) still works offline.

## Services

| Service   | Image / build            | Port              | Purpose |
|-----------|--------------------------|-------------------|---------|
| `backend` | `./backend/Dockerfile`   | `${APP_PORT}:8000` | FastAPI REST API + static web UI, calls Gemini |
| `db`      | `postgres:16-alpine`     | internal only     | Stores categories + classifications |

* **Network:** `celestial-net` (bridge). The backend reaches the DB via the service name `db`.
* **Dependency:** `backend` waits for `db` to report **healthy** (`pg_isready`).
* **Volume:** `celestial_pgdata` → `/var/lib/postgresql/data`.
* **Schema:** `db/init.sql` runs automatically on the first start (empty volume).

## API

| Method   | Endpoint                              | DB    | Description |
|----------|---------------------------------------|-------|-------------|
| `POST`   | `/api/classify` (multipart `file`)    | WRITE | Classify an image with Gemini and save it |
| `GET`    | `/api/classifications?category=&limit=&offset=` | READ | Paginated history |
| `GET`    | `/api/classifications/{id}`           | READ  | One classification |
| `GET`    | `/api/classifications/{id}/image`     | READ  | Stored image |
| `DELETE` | `/api/classifications/{id}`           | WRITE | Delete a classification |
| `GET`    | `/api/stats`                          | READ  | Totals and per-category counts / confidence |
| `GET`    | `/api/categories`                     | READ  | Allowed categories |
| `GET`    | `/api/health`                         | READ  | Health, DB status, classifier mode |

Example:

```bash
curl -F "file=@andromeda.jpg" http://localhost:8000/api/classify
curl http://localhost:8000/api/stats
```

## Configuration (`.env`)

| Variable            | Description |
|---------------------|-------------|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | DB credentials (used by both services) |
| `APP_PORT`          | Host port for the web UI / API (default `http://localhost:8000`) |
| `CLASSIFIER_MODE`   | `auto` · `gemini` · `mock` |
| `GEMINI_API_KEY`    | Google AI Studio key (secret) |
| `GEMINI_MODEL`      | e.g. `gemini-2.5-flash` |
| `MAX_UPLOAD_MB`     | Upload size limit (default `5`) |
| `LOG_LEVEL`         | `debug` · `info` · `warning` · `error` |

Secrets exist **only** in `.env`, which is listed in `.gitignore` and `backend/.dockerignore`.
The source code reads everything from environment variables.

## Persistence check

```bash
docker compose up -d            # classify a few images in the UI
docker compose down             # removes containers + network, KEEPS the volume
docker compose up -d            # history and stats are still there ✅
docker compose down -v          # ⚠️ also deletes the volume → data wiped
```

## Project structure

```
celestial_classifier/
├── compose.yaml
├── .env.example          # template, no real credentials
├── .gitignore
├── db/init.sql           # schema + category seed
└── backend/
    ├── Dockerfile
    ├── .dockerignore
    ├── requirements.txt
    └── app/
        ├── main.py       # routes
        ├── config.py     # env-based settings
        ├── db.py         # engine / sessions
        ├── models.py     # ORM models
        ├── schemas.py    # response models
        ├── classifier.py # Gemini + mock classifiers
        └── static/       # index.html, styles.css, app.js
```
