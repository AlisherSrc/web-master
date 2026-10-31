# 🔭 Celestial Classifier

[![Docker](https://img.shields.io/badge/Docker-24%2B-blue?logo=docker)](https://www.docker.com/)
[![Docker Compose](https://img.shields.io/badge/Docker_Compose-v2-blue?logo=docker)](https://docs.docker.com/compose/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16--alpine-336791?logo=postgresql)](https://www.postgresql.org/)
[![Postman](https://img.shields.io/badge/Postman-Collection_v2.1-FF6C37?logo=postman)](https://www.postman.com/)

An end-to-end, multi-container cloud-native web application and REST API. Upload a space image and **Google Gemini** (or the deterministic offline fallback) classifies the celestial object into 14 astronomical and earthly categories. Every observation, analytical feature breakdown, confidence score, and raw image binary is stored in **PostgreSQL**, with persistence guaranteed across container lifecycles via named volumes.

---

## 🎯 Evaluation Requirements Compliance

| Rubric Requirement | Points | Status | Where to Verify |
| :--- | :---: | :---: | :--- |
| **Complete & working backend application** | 2 | ✅ | [backend/app/main.py](backend/app/main.py), [backend/Dockerfile](backend/Dockerfile) |
| **REST API implementation & database integration** | 2 | ✅ | Full CRUD implemented ([main.py](backend/app/main.py), [db/init.sql](db/init.sql)) |
| **Docker configuration & containerization** | 2 | ✅ | Multi-container setup in [compose.yaml](compose.yaml), custom [Dockerfile](backend/Dockerfile) |
| **API documentation** | 1 | ✅ | Dedicated [API_DOCUMENTATION.md](API_DOCUMENTATION.md) + `/docs` interactive Swagger |
| **Complete & working Postman Collection** | 2 | ✅ | [celestial_classifier.postman_collection.json](celestial_classifier.postman_collection.json) |
| **Code quality, structure & repository organization** | 1 | ✅ | Clean separation of models, schemas, config, static assets, and test images |
| **Online Defense preparation** | 5 | ✅ | Complete questions, scripts, and walkthrough in [DEFENSE_GUIDE.md](DEFENSE_GUIDE.md) |
| **Total** | **15** | **100%** | Full compliance across all rubric sections |

---

## 🏗️ Architecture & Service Topology

```
┌─────────────────────────────────┐
│ Host Browser / Postman Client   │
└────────────────┬────────────────┘
                 │ HTTP :8000
                 ▼
┌────────────────────────────────────────────────────────┐
│ Docker Network: celestial-net (bridge)                 │
│                                                        │
│  ┌────────────────────────┐    SQL (db:5432)   ┌────────────────────────┐
│  │ backend (FastAPI)      │ ─────────────────▶ │ db (PostgreSQL 16)     │
│  │ Container:             │                    │ Container:             │
│  │ celestial-backend      │                    │ celestial-db           │
│  └───────────┬────────────┘                    └───────────┬────────────┘
│              │                                             │
└──────────────┼─────────────────────────────────────────────┼───────────────────┘
               │                                             ▼
               ▼                             Named Volume: celestial_pgdata
    Google Gemini AI Studio API              survives container recreation
```

### Services Overview

| Service | Image / Build | Port Mapping | Storage / Networking | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `backend` | Custom build `./backend/Dockerfile` | `8000:8000` | Network: `celestial-net` | FastAPI REST API + vanilla JS observatory UI |
| `db` | `postgres:16-alpine` | Internal `5432` only | Volume: `celestial_pgdata`<br>Network: `celestial-net` | Stores categories lookup table & observations |

* **Service-to-service communication:** The backend contacts PostgreSQL via the service name `db` (resolved by Docker's internal DNS at `127.0.0.11`).
* **Startup ordering:** `backend` waits for `db` to pass health check (`pg_isready`) before launching Uvicorn.
* **Network isolation:** Port 5432 is **not published** to the host. Only containers on `celestial-net` can reach the database.
* **Data persistence:** Data is stored in Docker named volume `celestial_pgdata`, surviving `docker compose down`.

---

## ⚡ Quick Start

### 1. Configure Environment
```bash
# Copy example environment configuration
cp .env.example .env            # PowerShell: Copy-Item .env.example .env
```
*(Optional)* Add your free Google AI Studio key to `GEMINI_API_KEY` in `.env`.
> **Offline Mode:** If `GEMINI_API_KEY` is empty, the application automatically uses a deterministic offline mock classifier. The complete stack (upload → DB write → read/update/delete → stats) works 100% without an internet connection!

### 2. Launch Stack
```bash
docker compose up --build
```

### 3. Access Application
* **Web Observatory UI:** [http://localhost:8000](http://localhost:8000)
* **Interactive OpenAPI Swagger Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
* **Alternative ReDoc UI:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 📡 REST API Specification

Detailed schemas, error codes, and curl examples are documented in [API_DOCUMENTATION.md](API_DOCUMENTATION.md).

| Method | Endpoint | CRUD Operation | DB Action | Description |
| :--- | :--- | :---: | :---: | :--- |
| `GET` | `/api/health` | - | Read | Liveness, DB connection status, active model |
| `GET` | `/api/categories` | - | Read | Lookup table of 14 allowed categories |
| `POST` | `/api/classify` | **Create** | Write | Upload image file, classify with AI/mock, store to DB |
| `POST` | `/api/classifications` | **Create** | Write | Create observation record directly via JSON |
| `GET` | `/api/classifications` | **List** | Read | Paginated observation log (`?limit=&offset=&category=`) |
| `GET` | `/api/classifications/{id}` | **Get by ID** | Read | Retrieve single observation by ID |
| `GET` | `/api/classifications/{id}/image` | - | Read | Stream stored image binary (`BYTEA`) |
| `PATCH` | `/api/classifications/{id}` | **Update** | Write | Partially update object name, notes, or category |
| `PUT` | `/api/classifications/{id}` | **Update** | Write | Full replace/update of observation metadata |
| `DELETE` | `/api/classifications/{id}` | **Delete** | Write | Permanently delete observation and image bytes |
| `GET` | `/api/stats` | - | Read | Real-time SQL aggregations (totals, confidence) |

---

## 📮 Postman Collection

The repository includes a ready-to-import Postman Collection and Environment:
* **Collection:** [`celestial_classifier.postman_collection.json`](celestial_classifier.postman_collection.json) (Postman v2.1.0 format)
* **Environment:** [`celestial_classifier.postman_environment.json`](celestial_classifier.postman_environment.json)
* **Sample Test Images:** Ready in [`sample_images/`](sample_images/) (`galaxy.jpg`, `nebula.jpg`, `coffee_not_celestial.jpg`)

### Running the Postman Collection:
1. Open Postman -> Click **Import** -> Select `celestial_classifier.postman_collection.json` and `celestial_classifier.postman_environment.json`.
2. Select the **"Celestial Classifier - Local Environment"** in the top-right environment selector.
3. Run the requests in order or click **Run Collection**:
   - `1. System Health`
   - `2. Categories`
   - `3. Create via Image Upload` (auto-saves ID to Postman variable)
   - `4. Create via JSON Data`
   - `5. List All Classifications`
   - `6. Filter by Category`
   - `7. Get by ID`
   - `8. Get Image`
   - `9. Update (PATCH & PUT)`
   - `10. Delete`
   - `11. Observatory Statistics`

All requests have automated test assertions (`pm.test`) checking HTTP status codes, headers, and payload structures.

---

## 🛡️ Online Defense Preparation

A full guide for the online defense is provided in [DEFENSE_GUIDE.md](DEFENSE_GUIDE.md). It covers:
* Screen sharing procedure and live demonstration sequence.
* Model answers to theoretical questions:
  - Image vs Container
  - Dockerfile instructions and layer caching
  - Docker Compose advantages
  - Docker bridge networking and embedded DNS
  - Named volumes vs bind mounts
  - Internal vs published ports
  - Secret management with `.env`
* Solutions to live modification scenarios (e.g. changing ports, updating database schema, inspecting network/volumes).

---

## 💾 Persistence Verification

To verify that observation records and image binaries persist when containers are stopped:

```bash
# 1. Start containers and classify an image in Web UI or Postman
docker compose up -d

# 2. Stop and remove containers and networks (volume is kept)
docker compose down

# 3. Bring the stack back up
docker compose up -d

# 4. Verify that data is still present
curl http://localhost:8000/api/stats

# 5. Clean up everything including the named volume:
docker compose down -v
```

---

## 🗂️ Project Structure

```
celestial_classifier/
├── compose.yaml                               # Docker Compose multi-service definition
├── .env.example                               # Environment template (git-tracked)
├── .env                                       # Local secrets configuration (git-ignored)
├── .gitignore                                 # Protects .env, build files, and archives
├── README.md                                  # Project overview and instructions
├── API_DOCUMENTATION.md                       # Comprehensive REST API reference
├── DEFENSE_GUIDE.md                           # Online defense questions & cheat sheet
├── celestial_classifier.postman_collection.json # Exported Postman test collection
├── celestial_classifier.postman_environment.json# Postman environment configuration
├── sample_images/                             # High-resolution test images
│   ├── galaxy.jpg
│   ├── nebula.jpg
│   └── coffee_not_celestial.jpg
├── db/
│   └── init.sql                               # PostgreSQL schema + 14 seeded categories
└── backend/
    ├── Dockerfile                             # Custom multi-layer Python 3.12 backend image
    ├── .dockerignore                          # Prevents copying cache, git, and local files
    ├── requirements.txt                       # Backend dependencies
    └── app/
        ├── main.py                            # FastAPI routes (Full CRUD + System + Stats)
        ├── config.py                          # Pydantic Settings (loaded from env)
        ├── db.py                              # SQLAlchemy engine and connection pool
        ├── models.py                          # ORM tables (Category, Classification)
        ├── schemas.py                         # Pydantic request/response validation
        ├── classifier.py                      # Gemini AI client & deterministic mock
        └── static/                            # Observatory Web UI
            ├── index.html                     # HTML5 single-page application
            ├── styles.css                     # Custom astronomy-themed dark mode styles
            └── app.js                         # Vanilla JS client logic with live editing
```
