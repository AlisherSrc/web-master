# 🛡️ Online Defense Preparation & Cheat Sheet (5 / 5 Points)

This guide covers everything required during the online defense: screen sharing setup, Postman demo sequence, theoretical Docker questions and sample answers, source code explanations, and solutions to common live modification/debugging tasks.

---

## 🖥️ 1. Defense Day Checklist

1. **Screen Share:** Have your full screen or main window ready to share.
2. **Editor:** Have VS Code (or your code editor) open at the project root (`celestial_classifier`).
3. **Terminal:** Have PowerShell / Terminal open at the project directory.
4. **Postman:** 
   - Import `celestial_classifier.postman_collection.json`
   - Import `celestial_classifier.postman_environment.json` (select "Celestial Classifier - Local Environment")
5. **Browser:** Have `http://localhost:8000` and `http://localhost:8000/docs` ready in tabs.

---

## 🚀 2. Live Startup Demonstration

Run in your terminal:
```bash
docker compose up --build
```

**Explain while running:**
> "Here `docker compose up --build` reads `compose.yaml`. It starts two services: the PostgreSQL database container `celestial-db` and the FastAPI backend `celestial-backend`. Notice that the backend container declares `depends_on: db: condition: service_healthy`, which ensures the backend doesn't start accepting traffic until PostgreSQL has finished initialization and `pg_isready` reports healthy."

---

## 📮 3. Step-by-Step Postman Demonstration

Execute the requests in the collection in order:

1. **System Health (`GET /api/health`):**
   - Click Send. Shows `status: "ok"`, `database: "up"`, active model, and classifier mode.
   - Explain: *"This endpoint actively pings the PostgreSQL container through the user-defined Docker bridge network (`celestial-net`)."*
2. **List Categories (`GET /api/categories`):**
   - Click Send. Returns 14 seeded astronomical categories from the `categories` table.
3. **Classify via Image Upload (`POST /api/classify`):**
   - Send the request with `sample_images/galaxy.jpg`.
   - Returns HTTP 201 Created with JSON analysis (confidence, object name, visual evidence).
   - The test script automatically saves `classification_id` into Postman variables!
4. **Create Manual Observation (`POST /api/classifications`):**
   - Click Send with JSON payload.
   - Returns HTTP 201 Created. Demonstrates standard REST JSON resource creation.
5. **List Observations (`GET /api/classifications`):**
   - Click Send. Shows paginated results and total count.
6. **Filter by Category (`GET /api/classifications?category=galaxy`):**
   - Demonstrates SQL filtering by foreign key slug.
7. **Get by ID (`GET /api/classifications/{{classification_id}}`):**
   - Returns single record with full details.
8. **Get Image (`GET /api/classifications/{{classification_id}}/image`):**
   - Returns the binary image directly from the PostgreSQL `BYTEA` column.
9. **Update via PATCH (`PATCH /api/classifications/{{classification_id}}`):**
   - Sends modified object name/notes. Returns updated object with status 200 OK.
10. **Update via PUT (`PUT /api/classifications/{{classification_id}}`):**
    - Replaces observation fields and validates category constraint.
11. **Observatory Statistics (`GET /api/stats`):**
    - Shows real-time aggregated metrics (total scans, celestial vs imposter counts, average confidence).
12. **Delete (`DELETE /api/classifications/{{classification_id}}`):**
    - Deletes observation. Returns HTTP 204 No Content. Verify deletion with `GET /api/classifications/{{classification_id}}` (returns 404).

---

## 🧠 4. Core Theoretical Questions & Model Answers

### Q1: What is the difference between a Docker Image and a Docker Container?
* **Image:** A read-only, immutable package or blueprint containing the application code, runtime, system libraries, and dependencies.
* **Container:** A runnable, isolated instance of an image. It adds a thin read-write layer on top of the image layers and runs as an isolated process on the host operating system kernel using Linux namespaces and cgroups.

### Q2: Explain the structure of your `Dockerfile` and layer caching.
* **Base Image:** `python:3.12-slim` (minimal attack surface, fast download, small image size).
* **Environment Flags:** `PYTHONDONTWRITEBYTECODE=1` and `PYTHONUNBUFFERED=1` (prevents unnecessary `.pyc` caching and ensures container logs flush immediately).
* **Layer Caching:** We copy `requirements.txt` and run `pip install` **before** copying application code `app/`. Why? Because dependencies change rarely compared to application code. When modifying code, Docker reuses the cached dependency layer, rebuilding in under 2 seconds.
* **Security:** Runs under an unprivileged user `app` (`USER app`) instead of root.
* **Healthcheck:** Native Python `urllib` healthcheck built into the image without needing external utilities like `curl` or `wget`.

### Q3: What is Docker Compose and why do we use it?
* Docker Compose is a declarative tool for defining and running multi-container Docker applications using a YAML file (`compose.yaml`).
* Without Compose, we would have to manually run `docker network create`, `docker volume create`, `docker run` with dozens of `--network`, `-e`, `-v`, and `-p` flags in the right order. Compose handles service dependencies, networks, volumes, health checks, and startup ordering with a single command (`docker compose up`).

### Q4: How does Docker Networking and service-to-service communication work in your project?
* We define a custom bridge network `celestial-net`.
* When containers are on a user-defined bridge network, Docker provides an **embedded DNS server** at `127.0.0.11`.
* The backend does **not** hardcode an IP address; it reaches PostgreSQL using the Compose service name `db` (e.g., `db:5432`). Docker's DNS automatically resolves `db` to the internal IP of the database container.
* The database port `5432` is **not published** to the host machine. It is reachable only by containers on `celestial-net`, providing network isolation and security.

### Q5: What is the difference between a Named Volume and a Bind Mount?
* **Named Volume (`celestial_pgdata`):** Managed completely by Docker inside Docker's storage directory (`/var/lib/docker/volumes/`). It is completely independent of the container lifecycle. Data persists even if containers are stopped, removed (`docker compose down`), or upgraded.
* **Bind Mount (`./db/init.sql`):** Mounts a specific file or directory from the host filesystem directly into the container. Used here to execute our schema and seed data when the database initializes for the first time.
* **Persistence Test:** Running `docker compose down` removes containers and networks but **preserves** `celestial_pgdata`. Running `docker compose down -v` removes the volume and wipes the data.

### Q6: How are Environment Variables handled and why is it secure?
* Configuration variables (passwords, ports, API keys) are defined in `.env` and declared in `compose.yaml`.
* `.env` is listed in `.gitignore` and `.dockerignore`, ensuring secrets are **never committed** to git or baked into Docker images.
* We provide `.env.example` as a template with placeholder values for other developers.
* Docker Compose injects environment variables into the containers at runtime. The backend loads them using `pydantic-settings`.

---

## 🛠️ 5. Live Modification & Troubleshooting Tasks

During the defense, the professor may ask you to make a live change and demonstrate it. Here are the most common scenarios:

### Task A: "Change the application port from 8000 to 8080"
1. Open `.env` and change `APP_PORT=8000` to `APP_PORT=8080`.
2. Run:
   ```bash
   docker compose up -d
   ```
3. Open `http://localhost:8080` in the browser or update `baseUrl` in Postman to `http://localhost:8080`.

### Task B: "Connect to the running PostgreSQL database and run a SQL query"
Open terminal and run:
```bash
docker exec -it celestial-db psql -U celestial -d celestial_db
```
Inside the `psql` shell:
```sql
\dt                                  -- List tables (categories, classifications)
SELECT id, category, object_name, confidence FROM classifications;
\q                                   -- Exit
```

### Task C: "Inspect the Docker network and volume"
Run:
```bash
docker network inspect celestial-net
docker volume inspect celestial_pgdata
```
Show the professor that both `celestial-db` and `celestial-backend` are attached to `celestial-net` with their respective IP addresses.

### Task D: "Prove that data persists across container destruction"
1. Classify an image or create an observation via Postman or Web UI.
2. Run:
   ```bash
   docker compose down
   ```
   Explain: *"Containers and network are now removed."*
3. Run:
   ```bash
   docker compose up -d
   ```
4. Query `GET /api/classifications` in Postman.
   Explain: *"The observations and statistics are fully intact because the named volume `celestial_pgdata` was preserved."*

### Task E: "Add a new field (e.g. `notes`) to the update schema"
1. In [schemas.py](file:///d:/web_world_wide_or_whatever/celestial_classifier/backend/app/schemas.py), add `notes: str | None = None` to `ClassificationUpdate`.
2. In [main.py](file:///d:/web_world_wide_or_whatever/celestial_classifier/backend/app/main.py), add handling under `update_classification`:
   ```python
   if payload.notes is not None:
       record.fun_fact = payload.notes
   ```
3. Run `docker compose up --build backend` and demonstrate in Postman.
