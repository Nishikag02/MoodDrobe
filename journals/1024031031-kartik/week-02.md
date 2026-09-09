# Weekly Engineering Journal — Week 2

- **Name:** Kartik
- **Roll Number:** 1024031031
- **Date Range:** 27 Aug 2026 – 02 Sep 2026
- **Module / Component:** SE Project Report & PostgreSQL Containerization

---

## 1. Goal & Objectives
- Author and complete the formal Software Engineering Project Report.
- Deploy an isolated PostgreSQL 17 database service via Docker Compose.
- Establish persistent data volumes and automated container health checks.

---

## 2. Technical Activities & Implementation

### A. Comprehensive SE Project Report Drafting
- Authored the comprehensive Software Engineering Project Report:
  - System scope and feasibility analysis.
  - Entity-Relationship (ER) model design for user accounts, credentials, and wardrobe metadata.
  - Architectural pipeline specifying visual similarity search flow using CLIP vector embeddings.

### B. Database Containerization
- Authored `backend/docker-compose.yml`:
  - Selected `postgres:17` image.
  - Configured persistent local storage volume mapping (`postgres_data:/var/lib/postgresql/data`).
  - Added container health check commands using `pg_isready -U postgres -d mydb`.
  - Exposed database traffic on standard port `5432:5432`.

---

## 3. Snippets & Patterns (MWE / Ready Reckoner)

### PostgreSQL Service Specification (`backend/docker-compose.yml`)
```yaml
services:
  postgres:
    image: postgres:17
    container_name: mooddrobe_postgres
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: mypassword
      POSTGRES_DB: mydb
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d mydb"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:

```

---

## 4. Challenges & Mitigations
- **Challenge:** Ensuring dependent services wait until PostgreSQL is completely initialized and accepting connections.
  - **Mitigation:** Implemented container-native `healthcheck` specifications via `pg_isready` before running migrations.

---

## 5. Next Week Objectives
- Model relational schemas in Drizzle ORM.
- Configure Better-Auth server engine with Express 5.