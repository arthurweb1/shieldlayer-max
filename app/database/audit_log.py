import hashlib
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
    duration_ms INTEGER NOT NULL
);
"""

INSERT_SQL = """
INSERT INTO audit_events
    (request_id, masked_prompt_hash, response_hash, compliant, article_ref, watermark_seed, duration_ms)
VALUES ($1, $2, $3, $4, $5, $6, $7)
"""


class AuditLog:
    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    @classmethod
    async def create(cls, dsn: str) -> "AuditLog":
        pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10)
        async with pool.acquire() as conn:
            await conn.execute(CREATE_TABLE_SQL)
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
