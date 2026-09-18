import logging

import psycopg

from ask.snapshot import SnapshotIndex

logger = logging.getLogger(__name__)

SCHEMA_STATEMENTS = (
    "CREATE EXTENSION IF NOT EXISTS vector",
    """
    CREATE TABLE IF NOT EXISTS normative_acts (
        id TEXT PRIMARY KEY,
        identity TEXT NOT NULL,
        act_type TEXT NOT NULL,
        number TEXT NOT NULL,
        year INTEGER NOT NULL,
        status TEXT NOT NULL,
        source_url TEXT NOT NULL,
        retrieved_at DATE NOT NULL,
        checksum_sha256 TEXT NOT NULL,
        pdf_name TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS articles (
        id TEXT PRIMARY KEY,
        act_id TEXT NOT NULL REFERENCES normative_acts(id),
        article TEXT NOT NULL,
        page INTEGER NOT NULL,
        body TEXT NOT NULL
    )
    """,
)


def persist_snapshot(database_url: str, snapshot: SnapshotIndex) -> None:
    with psycopg.connect(database_url, autocommit=True) as connection:
        for statement in SCHEMA_STATEMENTS:
            connection.execute(statement)
        for act in snapshot.acts:
            connection.execute(
                """
                INSERT INTO normative_acts (
                    id, identity, act_type, number, year, status,
                    source_url, retrieved_at, checksum_sha256, pdf_name
                ) VALUES (
                    %(id)s, %(identity)s, %(act_type)s, %(number)s, %(year)s,
                    %(status)s, %(source_url)s, %(retrieved_at)s,
                    %(checksum_sha256)s, %(pdf_name)s
                )
                ON CONFLICT (id) DO UPDATE SET
                    identity = EXCLUDED.identity,
                    act_type = EXCLUDED.act_type,
                    number = EXCLUDED.number,
                    year = EXCLUDED.year,
                    status = EXCLUDED.status,
                    source_url = EXCLUDED.source_url,
                    retrieved_at = EXCLUDED.retrieved_at,
                    checksum_sha256 = EXCLUDED.checksum_sha256,
                    pdf_name = EXCLUDED.pdf_name
                """,
                {
                    "id": act.id,
                    "identity": act.identity,
                    "act_type": act.type,
                    "number": act.number,
                    "year": act.year,
                    "status": act.status,
                    "source_url": act.source_url,
                    "retrieved_at": act.retrieved_at,
                    "checksum_sha256": act.checksum_sha256,
                    "pdf_name": act.file,
                },
            )
        for article in snapshot.articles:
            connection.execute(
                """
                INSERT INTO articles (id, act_id, article, page, body)
                VALUES (%(id)s, %(act_id)s, %(article)s, %(page)s, %(body)s)
                ON CONFLICT (id) DO UPDATE SET
                    act_id = EXCLUDED.act_id,
                    article = EXCLUDED.article,
                    page = EXCLUDED.page,
                    body = EXCLUDED.body
                """,
                {
                    "id": article.id,
                    "act_id": article.act_id,
                    "article": article.article,
                    "page": article.page,
                    "body": article.text,
                },
            )
    logger.info(
        "persisted snapshot acts=%s articles=%s",
        len(snapshot.acts),
        len(snapshot.articles),
    )
