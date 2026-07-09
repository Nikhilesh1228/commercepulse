# CommercePulse interview preparation

Do not memorize only the summary. Run the code, then answer these questions aloud.

## Project explanation

“CommercePulse is a collaborative-commerce backend. I used GraphQL for flexible catalog
and campaign operations, REST for auth and the Chrome extension, PostgreSQL for
transactions, Elasticsearch for search, Redis for disposable caches, MongoDB for flexible
price history, and Kafka for domain events. The unusual feature is a group-buy threshold
that atomically unlocks a discount. A transactional outbox prevents dual-write loss.”

## Follow-up questions

### Why both REST and GraphQL?

GraphQL lets web clients request product/campaign shapes without endpoint proliferation.
REST is simpler for OAuth callbacks, health probes, and a small extension contract. The
split follows client needs rather than treating one protocol as universally better.

### Why PostgreSQL and MongoDB?

PostgreSQL owns transactional state and constraints. MongoDB only receives append-style
price snapshots for flexible analytics. If the scale did not justify two stores, keeping
history in PostgreSQL would be the simpler choice.

### Why is Elasticsearch not the source of truth?

Search indexes are eventually consistent and rebuildable. Orders resolve product IDs
against PostgreSQL and never trust an indexed price or inventory value.

### What problem does the outbox solve?

Writing the database and Kafka separately can lose an event or publish an event for a
rolled-back transaction. The service inserts an outbox row in the same transaction, then a
publisher retries delivery. Consumers still need idempotency because delivery is at least once.

### How is overselling prevented?

Order creation locks selected product rows, validates every requested quantity, then
decrements inventory and inserts the order before commit. Price changes use a version check
so concurrent updates cannot overwrite silently.

### What is cached?

Redis caches only ordered product ID lists for a normalized search query. Product records
are re-read from PostgreSQL, so stale cached IDs cannot change transactional truth.

### How does SSO work?

Authlib reads the provider’s OIDC discovery document, redirects with state stored in a
signed session cookie, validates the callback, upserts the provider subject/email, and
issues the same internal JWT used by local login.

### What would you improve for production?

Use managed services and TLS, an external outbox worker, per-merchant authorization,
idempotency keys, schema registry, Kafka ACLs, OpenTelemetry, dead-letter handling,
Elasticsearch index versioning, secrets management, and load/chaos tests.

## Hands-on checklist

1. Run all tests and explain one optimistic-lock conflict test.
2. Create two users and unlock a two-member campaign through GraphQL.
3. Stop Redis and Elasticsearch, then demonstrate SQL fallback.
4. Inspect an outbox row before and after Kafka publication.
5. Load the unpacked extension and create a watch for an indexed URL.
