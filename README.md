# 🔭 Celestial Classifier

[![Docker](https://img.shields.io/badge/Docker-24%2B-blue?logo=docker)](https://www.docker.com/)
[![Docker Compose](https://img.shields.io/badge/Docker_Compose-v2-blue?logo=docker)](https://docs.docker.com/compose/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16--alpine-336791?logo=postgresql)](https://www.postgresql.org/)
[![Postman](https://img.shields.io/badge/Postman-Collection_v2.1-FF6C37?logo=postman)](https://www.postman.com/)

An end-to-end, multi-container cloud-native application and REST API for deep-space object classification. Upload an astronomical image, and the system analyses visual features using **Google Gemini** (with deterministic offline fallback) to classify the observation into 14 celestial and earthly categories.

Every observation, analytical breakdown, confidence rating, and image binary is securely stored in **PostgreSQL**, with persistence guaranteed across container lifecycles via Docker named volumes.

---

## 🏗️ Architecture & Topology

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
    Google Gemini AI Studio API              (persists across container stops)
```

### Services Specification

| Service | Image / Build | Port Mapping | Storage / Networking | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `backend` | `./backend/Dockerfile` | `8000:8000` | Network: `celestial-net` | FastAPI REST API + interactive observatory web application |
| `db` | `postgres:16-alpine` | Internal `5432` only | Volume: `celestial_pgdata`<br>Network: `celestial-net` | Persistent storage for categories and observation records |

* **Service Discovery:** The backend communicates with PostgreSQL via the service name `db` (resolved automatically by Docker's internal DNS engine).
* **Health Checks & Startup Sequencing:** The `backend` container waits for PostgreSQL to report healthy via `pg_isready` before accepting traffic.
* **Network Isolation:** Port `5432` is not published to the host machine. Database access is strictly constrained to the internal bridge network `celestial-net`.
* **Data Durability:** Stored inside named volume `celestial_pgdata`, surviving container re-creation, updates, and restarts.

---

## ⚡ Getting Started

### 1. Environment Setup
```bash
# Copy example configuration template
cp .env.example .env            # PowerShell: Copy-Item .env.example .env
```

*(Optional)* Configure `GEMINI_API_KEY` with your key from Google AI Studio.
> **Note:** If `GEMINI_API_KEY` is not provided, the application automatically runs in deterministic mock mode. The full stack (upload, SQL persistence, CRUD, statistics) functions entirely offline without internet access.

### 2. Start Services
```bash
docker compose up --build
```

### 3. Access Application
* **Web Observatory:** [http://localhost:8000](http://localhost:8000)
* **Interactive OpenAPI Swagger Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
* **ReDoc Documentation:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 📡 REST API

Complete schemas, query parameters, headers, and status code references are documented in [API_DOCUMENTATION.md](API_DOCUMENTATION.md).

| Method | Endpoint | Operation | DB Action | Description |
| :--- | :--- | :---: | :---: | :--- |
| `GET` | `/api/health` | System | Read | Health status, database connection, active model |
| `GET` | `/api/categories` | Reference | Read | Master list of all 14 supported categories |
| `POST` | `/api/classify` | **Create** | Write | Upload image file, perform inference, persist to DB |
| `POST` | `/api/classifications` | **Create** | Write | Create observation record directly via JSON |
| `GET` | `/api/classifications` | **List** | Read | Paginated observation history (`?limit=&offset=&category=`) |
| `GET` | `/api/classifications/{id}` | **Get by ID** | Read | Retrieve a single observation by ID |
| `GET` | `/api/classifications/{id}/image` | Asset | Read | Stream raw image binary bytes (`BYTEA`) |
| `PATCH` | `/api/classifications/{id}` | **Update** | Write | Partial update of observation fields |
| `PUT` | `/api/classifications/{id}` | **Update** | Write | Full update/replacement of observation attributes |
| `DELETE` | `/api/classifications/{id}` | **Delete** | Write | Permanently delete observation and associated image |
| `GET` | `/api/stats` | Analytics | Read | Real-time aggregate statistics & distribution |

---

## 📮 API Testing with Postman

An exported Postman Collection and Environment are provided in the repository root:
* **Collection:** [`celestial_classifier.postman_collection.json`](celestial_classifier.postman_collection.json) (Postman Schema v2.1.0)
* **Environment:** [`celestial_classifier.postman_environment.json`](celestial_classifier.postman_environment.json)
* **Sample Images:** Available in [`sample_images/`](sample_images/) (`galaxy.jpg`, `nebula.jpg`, `coffee_not_celestial.jpg`)

### Running the Requests
1. Import both JSON files into Postman.
2. Select the **"Celestial Classifier - Local Environment"**.
3. Run the collection to execute all endpoints with automated test assertions (`pm.test`).

---

## 💾 Data Persistence Verification

To verify that observations and stored image binaries persist across container lifecycles:

```bash
# 1. Start containers and create observations via Web UI or Postman
docker compose up -d

# 2. Stop and remove containers and network (volume remains intact)
docker compose down

# 3. Bring the services back up
docker compose up -d

# 4. Verify data survived container removal
curl http://localhost:8000/api/stats
```

To completely reset the database and delete all persistent volumes:
```bash
docker compose down -v
```

---

## 🗂️ Project Structure

```
celestial_classifier/
├── compose.yaml                               # Multi-container service definitions
├── .env.example                               # Environment template
├── .gitignore                                 # Git ignore rules
├── README.md                                  # Application documentation
├── API_DOCUMENTATION.md                       # Comprehensive REST API reference
├── celestial_classifier.postman_collection.json # Exported Postman test collection
├── celestial_classifier.postman_environment.json# Postman environment configuration
├── sample_images/                             # High-resolution test assets
│   ├── galaxy.jpg
│   ├── nebula.jpg
│   └── coffee_not_celestial.jpg
├── db/
│   └── init.sql                               # PostgreSQL schema + category seeding
└── backend/
    ├── Dockerfile                             # Custom multi-layer Python 3.12 image
    ├── .dockerignore                          # Build context exclusion rules
    ├── requirements.txt                       # Python dependencies
    └── app/
        ├── main.py                            # FastAPI application routes (Full CRUD)
        ├── config.py                          # Environment settings loader
        ├── db.py                              # SQLAlchemy database engine & session pool
        ├── models.py                          # Database ORM models
        ├── schemas.py                         # Request/response validation schemas
        ├── classifier.py                      # Gemini AI client & offline mock engine
        └── static/                            # Observatory web application
            ├── index.html                     # HTML5 single-page application
            ├── styles.css                     # Astronomy-themed responsive stylesheet
            └── app.js                         # Client logic with real-time editing
```
