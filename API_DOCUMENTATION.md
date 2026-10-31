# 🌌 Celestial Classifier — REST API Documentation

Comprehensive REST API reference for the **Celestial Classifier** multi-container application.

Interactive Swagger/OpenAPI documentation is available at:
* **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
* **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
* **OpenAPI Specification (JSON):** [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

---

## 🧭 Overview & Architecture

* **Base URL:** `http://localhost:8000`
* **Transport:** HTTP / JSON (multipart/form-data for file uploads)
* **Database:** PostgreSQL 16 (persisted via `celestial_pgdata` named volume)
* **Container Network:** `celestial-net` bridge network (backend communicates with PostgreSQL at `db:5432`)
* **Standard Response Format:** JSON (`application/json; charset=utf-8`)

---

## 📋 Endpoint Index

| Method | Endpoint | Description | Database Action | Status Code |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/health` | System health, DB connection, and model info | Read (ping) | `200` / `503` |
| `GET` | `/api/categories` | Retrieve all 14 celestial/earthly categories | Read | `200` |
| `POST` | `/api/classify` | Upload image, classify with AI/mock, save to DB | Write | `201` |
| `POST` | `/api/classifications` | Create manual observation record via JSON | Write | `201` |
| `GET` | `/api/classifications` | List observations (paginated, filterable) | Read | `200` |
| `GET` | `/api/classifications/{id}` | Retrieve a single observation by ID | Read | `200` / `404` |
| `GET` | `/api/classifications/{id}/image` | Stream stored image binary bytes | Read (BYTEA) | `200` / `404` |
| `PATCH` | `/api/classifications/{id}` | Partially update an observation's fields | Write | `200` / `404` |
| `PUT` | `/api/classifications/{id}` | Replace/update observation attributes | Write | `200` / `404` |
| `DELETE` | `/api/classifications/{id}` | Permanently delete an observation and image | Write | `204` / `404` |
| `GET` | `/api/stats` | Aggregated metrics and category counts | Read | `200` |

---

## 🛠️ Endpoints Reference

### 1. System Health Check
`GET /api/health`

Verifies that the FastAPI application is alive and can communicate with PostgreSQL across Docker's internal network (`celestial-net`).

#### Response `200 OK`
```json
{
  "status": "ok",
  "database": "up",
  "classifier_mode": "auto",
  "model": "gemini-2.5-flash",
  "max_upload_mb": 5
}
```

#### Example cURL
```bash
curl -X GET http://localhost:8000/api/health
```

---

### 2. List Allowed Categories
`GET /api/categories`

Retrieves the lookup table of classification categories pre-seeded in PostgreSQL.

#### Response `200 OK`
```json
[
  {
    "slug": "galaxy",
    "label": "Galaxy",
    "description": "A gravitationally bound system of billions of stars, gas and dust...",
    "is_celestial": true
  },
  {
    "slug": "not_celestial",
    "label": "Not Celestial",
    "description": "The image does not show an astronomical object...",
    "is_celestial": false
  }
]
```

#### Example cURL
```bash
curl -X GET http://localhost:8000/api/categories
```

---

### 3. Classify Image (Create via Upload)
`POST /api/classify`

Accepts an image upload, sniffs the true MIME type from magic bytes, submits to Google Gemini (or deterministic offline mock fallback), and saves the metadata + image binary to PostgreSQL.

#### Request
* **Content-Type:** `multipart/form-data`
* **Form Field:** `file` (Binary JPEG, PNG, or WebP; maximum size configured by `MAX_UPLOAD_MB`)

#### Response `201 Created`
```json
{
  "id": 1,
  "original_name": "andromeda.jpg",
  "mime_type": "image/jpeg",
  "image_size": 895481,
  "image_url": "/api/classifications/1/image",
  "category": "galaxy",
  "category_label": "Galaxy",
  "is_celestial": true,
  "confidence": 0.985,
  "object_name": "Andromeda Galaxy (M31)",
  "description": "A grand spiral galaxy located roughly 2.5 million light-years away.",
  "visual_features": [
    "bright central core",
    "prominent spiral arms",
    "dark dust absorption lanes"
  ],
  "fun_fact": "Andromeda and our Milky Way are projected to merge in about 4.5 billion years.",
  "model_used": "gemini-2.5-flash",
  "created_at": "2026-10-31T07:30:00.000000Z"
}
```

#### Error Responses
* `400 Bad Request`: Empty file payload.
* `413 Payload Too Large`: Upload exceeds `MAX_UPLOAD_MB`.
* `415 Unsupported Media Type`: Non-image file provided.
* `502 Bad Gateway`: AI upstream error / invalid API key.

#### Example cURL
```bash
curl -X POST http://localhost:8000/api/classify \
  -F "file=@sample_images/galaxy.jpg"
```

---

### 4. Create Observation (Direct JSON Entry)
`POST /api/classifications`

Enables creating a classification record directly via a structured JSON payload (ideal for programmatic pipelines and standard REST API compliance).

#### Request
* **Content-Type:** `application/json`

```json
{
  "category": "nebula",
  "object_name": "Carina Nebula (NGC 3372)",
  "description": "A massive diffuse nebula containing key stellar nurseries.",
  "fun_fact": "Hosts Eta Carinae, a luminous hypergiant star system.",
  "confidence": 0.99,
  "visual_features": ["ionized hydrogen", "stellar winds", "dark pillars"],
  "original_name": "carina_survey.jpg"
}
```

#### Response `201 Created`
Returns the saved classification object with assigned primary key `id`.

#### Example cURL
```bash
curl -X POST http://localhost:8000/api/classifications \
  -H "Content-Type: application/json" \
  -d '{"category": "nebula", "object_name": "Carina Nebula", "confidence": 0.99}'
```

---

### 5. List Classifications (Paginated)
`GET /api/classifications`

Returns a paginated list of observations ordered newest first. Image binary data is deferred in the SQL query for high performance.

#### Query Parameters
| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `category` | string | `null` | Optional filter by category slug (e.g. `galaxy`, `black_hole`) |
| `limit` | integer | `12` | Number of items to return (1 – 100) |
| `offset` | integer | `0` | Number of items to skip |

#### Response `200 OK`
```json
{
  "items": [
    {
      "id": 1,
      "original_name": "andromeda.jpg",
      "mime_type": "image/jpeg",
      "image_size": 895481,
      "image_url": "/api/classifications/1/image",
      "category": "galaxy",
      "category_label": "Galaxy",
      "is_celestial": true,
      "confidence": 0.985,
      "object_name": "Andromeda Galaxy (M31)",
      "description": "A grand spiral galaxy...",
      "visual_features": ["spiral arms", "bright core"],
      "fun_fact": "Merge in 4.5 billion years.",
      "model_used": "gemini-2.5-flash",
      "created_at": "2026-10-31T07:30:00.000000Z"
    }
  ],
  "total": 1,
  "limit": 12,
  "offset": 0
}
```

#### Example cURL
```bash
curl -X GET "http://localhost:8000/api/classifications?limit=10&offset=0"
curl -X GET "http://localhost:8000/api/classifications?category=galaxy"
```

---

### 6. Get Classification by ID
`GET /api/classifications/{id}`

Retrieves full metadata for a specific observation.

#### Path Parameters
* `id` (integer, required): Unique observation ID.

#### Response `200 OK`
Returns single `ClassificationOut` object.

#### Error Response
* `404 Not Found`: If record with given ID does not exist.

#### Example cURL
```bash
curl -X GET http://localhost:8000/api/classifications/1
```

---

### 7. Get Classification Image
`GET /api/classifications/{id}/image`

Streams the raw image binary stored in the PostgreSQL `BYTEA` column.

#### Response `200 OK`
* **Content-Type:** Matches original MIME type (e.g., `image/jpeg`, `image/png`, `image/webp`).
* **Cache-Control:** `public, max-age=86400, immutable`

#### Example cURL
```bash
curl -X GET http://localhost:8000/api/classifications/1/image --output downloaded_image.jpg
```

---

### 8. Update Classification (Partial or Full)
`PATCH /api/classifications/{id}` and `PUT /api/classifications/{id}`

Updates an existing observation in PostgreSQL. Validates that `category` (if updated) exists in the `categories` lookup table and that `confidence` is between `0.0` and `1.0`.

#### Request
* **Content-Type:** `application/json`

```json
{
  "object_name": "Andromeda Galaxy (M31 / NGC 224) - Verified",
  "category": "galaxy",
  "description": "Updated observation log: high-contrast dust lanes and satellite galaxies M32 and NGC 205 visible.",
  "fun_fact": "Approaching our galaxy at approximately 110 kilometers per second.",
  "confidence": 0.99
}
```

#### Response `200 OK`
Returns updated `ClassificationOut` object.

#### Error Responses
* `400 Bad Request`: Unknown category slug or confidence out of bounds.
* `404 Not Found`: No observation found for given ID.

#### Example cURL
```bash
curl -X PATCH http://localhost:8000/api/classifications/1 \
  -H "Content-Type: application/json" \
  -d '{"object_name": "Updated Galaxy Name", "description": "New notes"}'
```

---

### 9. Delete Classification
`DELETE /api/classifications/{id}`

Permanently removes the classification record and stored image data from PostgreSQL.

#### Response `204 No Content`
Empty response body indicating successful deletion.

#### Error Response
* `404 Not Found`: If ID does not exist.

#### Example cURL
```bash
curl -X DELETE http://localhost:8000/api/classifications/1
```

---

### 10. Observatory Statistics
`GET /api/stats`

Executes real-time SQL aggregation across the `classifications` and `categories` tables to compute totals, celestial vs imposter counts, average confidence, and per-category distributions.

#### Response `200 OK`
```json
{
  "total": 12,
  "celestial": 10,
  "not_celestial": 2,
  "avg_confidence": 0.942,
  "last_classified_at": "2026-10-31T07:35:12.000000Z",
  "by_category": [
    {
      "slug": "black_hole",
      "label": "Black Hole",
      "is_celestial": true,
      "count": 2,
      "avg_confidence": 0.965
    },
    {
      "slug": "galaxy",
      "label": "Galaxy",
      "is_celestial": true,
      "count": 5,
      "avg_confidence": 0.978
    },
    {
      "slug": "not_celestial",
      "label": "Not Celestial",
      "is_celestial": false,
      "count": 2,
      "avg_confidence": 0.99
    }
  ]
}
```

#### Example cURL
```bash
curl -X GET http://localhost:8000/api/stats
```
