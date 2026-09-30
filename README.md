# CommercePulse: Scalable E-Commerce Microservices Backend

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Core-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![GraphQL](https://img.shields.io/badge/GraphQL-Strawberry-E10098?style=flat&logo=graphql&logoColor=white)](https://graphql.org/)
[![Kafka](https://img.shields.io/badge/Apache%20Kafka-Events-231F20?style=flat&logo=apachekafka&logoColor=white)](https://kafka.apache.org/)
[![Elasticsearch](https://img.shields.io/badge/Elasticsearch-Search-005571?style=flat&logo=elasticsearch&logoColor=white)](https://www.elastic.co/)

CommercePulse is a modern, high-performance e-commerce backend platform featuring hybrid REST and GraphQL APIs, asynchronous event processing, distributed search, multi-database persistence, and JWT/OIDC authentication.

## 📌 Architectural Overview
Designed for high scalability and throughput, CommercePulse orchestrates:
- **REST & GraphQL Gateways:** Dual API interface for flexible product querying and checkout operations.
- **Distributed Search Engine:** Fast product catalog indexing using Elasticsearch.
- **Event-Driven Architecture:** Asynchronous event streaming via Apache Kafka.
- **Polyglot Persistence:** PostgreSQL for relational transactional data, MongoDB for unstructured catalog specs, and Redis for high-speed caching and rate limiting.

---

## ✨ Key Features
- **Hybrid API Endpoints:** Synchronous FastAPI endpoints alongside Strawberry GraphQL queries.
- **Event-Driven Messaging:** Kafka topics for order creation, inventory sync, and notifications.
- **Full-Text Catalog Search:** Elasticsearch integration for faceted search and filtering.
- **Authentication & Security:** JWT authentication with OIDC-ready SSO compatibility.
- **Chrome Extension Support:** Companion browser extension for quick shopping cart syncing.

---

## 🛠️ Tech Stack
- **Core Backend:** Python, FastAPI, Strawberry GraphQL, Pydantic
- **Databases:** PostgreSQL, MongoDB, Redis, Elasticsearch
- **Event Streaming:** Apache Kafka, Zookeeper / KRaft
- **DevOps:** Docker, Docker Compose, Alembic DB Migrations

---

## 🚀 Getting Started

### Installation & Run
1. Clone the repository:
   ```bash
   git clone https://github.com/Nikhilesh1228/commercepulse.git
   cd commercepulse
   ```

2. Copy environment file:
   ```bash
   cp .env.example .env
   ```

3. Spin up full service stack:
   ```bash
   docker compose up --build -d
   ```

4. Explore APIs:
   - **Swagger REST Docs:** `http://localhost:8000/docs`
   - **GraphQL Playground:** `http://localhost:8000/graphql`
