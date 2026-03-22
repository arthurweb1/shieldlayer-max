import hashlib
import json
from typing import Optional

import asyncpg

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    request_id TEXT NOT NULL,
    masked_prompt_hash TEXT NOT NULL,
    response_hash TEXT NOT NULL,
    compliant BOOLEAN NOT NULL,
    article_ref TEXT,
    watermark_seed TEXT NOT NULL,
    duration_ms INTEGER NOT NULL,
    pii_stats JSONB NOT NULL DEFAULT '{}',
    cached BOOLEAN NOT NULL DEFAULT FALSE
);
"""

MIGRATE_SQL = """
ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS pii_stats JSONB NOT NULL DEFAULT '{}';
ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS cached BOOLEAN NOT NULL DEFAULT FALSE;
"""

INSERT_SQL = """
INSERT INTO audit_events
    (request_id, masked_prompt_hash, response_hash, compliant, article_ref,
     watermark_seed, duration_ms, pii_stats, cached)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
"""

CREATE_RO_USER_SQL = """
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'shieldlayer_ro') THEN
        EXECUTE format('CREATE ROLE shieldlayer_ro LOGIN PASSWORD %L', $1);
        GRANT CONNECT ON DATABASE current_database() TO shieldlayer_ro;
        GRANT USAGE ON SCHEMA public TO shieldlayer_ro;
        GRANT SELECT ON ALL TABLES IN SCHEMA public TO shieldlayer_ro;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO shieldlayer_ro;
    END IF;
END $$;
"""


async def _init_conn(conn: asyncpg.Connection) -> None:
    """Register asyncpg JSONB codec so dicts round-trip without manual json.dumps."""
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )


class AuditLog:
    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    @classmethod
    async def create(cls, dsn: str, ro_password: Optional[str] = None) -> "AuditLog":
        pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10, init=_init_conn)
        async with pool.acquire() as conn:
            await conn.execute(CREATE_TABLE_SQL)
            await conn.execute(MIGRATE_SQL)
            if ro_password:
                await conn.execute(CREATE_RO_USER_SQL, ro_password)
        return cls(pool=pool)

    async def write(
        self,
        *,
        request_id: str,
        masked_prompt_hash: str,
        response_hash: str,
        compliant: bool,
        article_ref: Optional[str],
        watermark_seed: str,
        duration_ms: int,
        pii_stats: Optional[dict] = None,
        cached: bool = False,
    ) -> None:
        """Write audit entry. Raises on failure — audit is in the critical path (EU AI Act Art. 12)."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                INSERT_SQL,
                request_id,
                masked_prompt_hash,
                response_hash,
                compliant,
                article_ref,
                watermark_seed,
                duration_ms,
                pii_stats or {},
                cached,
            )

    @staticmethod
    def hash(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:32]

    async def fetch_range(
        self,
        from_ts: Optional[str],
        to_ts: Optional[str],
        limit: int,
    ) -> list[dict]:
        query = "SELECT * FROM audit_events WHERE 1=1"
        params: list = []
        if from_ts:
            params.append(from_ts)
            query += f" AND ts >= ${len(params)}::timestamptz"
        if to_ts:
            params.append(to_ts)
            query += f" AND ts <= ${len(params)}::timestamptz"
        query += f" ORDER BY ts DESC LIMIT {limit}"
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
        return [dict(r) for r in rows]
