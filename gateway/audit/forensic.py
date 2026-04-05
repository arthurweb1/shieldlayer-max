from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone


class ForensicAudit:
    def __init__(self, log_path: str) -> None:
        self._log_path = log_path
        self._prev_chain_hash: str = "0" * 64
        os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)

        if os.path.exists(log_path):
            self._prev_chain_hash = self._load_last_chain_hash()

    async def log(
        self,
        *,
        session_id: str,
        redacted_body: bytes,
        response_body: bytes,
        entities_redacted: int,
        compliance_result: dict,
        latency_ms: float,
    ) -> None:
        request_hash = self._hash(redacted_body.decode("utf-8", errors="replace"))
        response_hash = self._hash(response_body.decode("utf-8", errors="replace"))
        chain_hash = self._hash(self._prev_chain_hash + request_hash)

        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
            "request_hash": request_hash,
            "response_hash": response_hash,
            "chain_hash": chain_hash,
            "entities_redacted": entities_redacted,
            "compliance_result": compliance_result,
            "latency_ms": latency_ms,
        }

        with open(self._log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
            fh.flush()
            os.fsync(fh.fileno())

        self._prev_chain_hash = chain_hash

    async def verify_chain(self) -> bool:
        if not os.path.exists(self._log_path):
            return True

        prev_hash = "0" * 64
        with open(self._log_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    return False

                expected_chain = self._hash(prev_hash + entry["request_hash"])
                if expected_chain != entry["chain_hash"]:
                    return False

                prev_hash = entry["chain_hash"]

        return True

    def _hash(self, data: str) -> str:
        return hashlib.sha256(data.encode()).hexdigest()

    def _load_last_chain_hash(self) -> str:
        last_hash = "0" * 64
        with open(self._log_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    last_hash = entry.get("chain_hash", last_hash)
                except json.JSONDecodeError:
                    continue
        return last_hash
