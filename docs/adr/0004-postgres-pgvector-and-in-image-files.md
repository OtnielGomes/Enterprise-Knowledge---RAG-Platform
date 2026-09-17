# v1 runtime is Postgres/pgvector plus PDFs in the image, not a storage platform

Retrieval and metadata live in PostgreSQL with pgvector; the five PDFs ship in the Docker image and run on a DigitalOcean droplet via the same Compose file as local dev. MinIO, Redis, and a dedicated vector database were rejected: five files do not justify object storage, and one datastore matches a solo 4–6 week slice. FastAPI owns ingestion, retrieval, filters, and the citation gate; Next.js is a single chat shell.

**Status:** accepted
