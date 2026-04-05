from __future__ import annotations

import statistics


class PrivacyGradeScorer:
    def grade(
        self,
        entities_redacted: int,
        compliance_result: dict,
        latency_ms: float,
        cache_hit: bool,
    ) -> dict:
        score = 100.0

        score -= entities_redacted * 5
        if cache_hit:
            score += 10

        violations = compliance_result.get("violations", [])
        for violation in violations:
            severity = violation.get("severity", "log")
            if severity == "block":
                score -= 50
            elif severity == "warn":
                score -= 20

        score = max(0.0, min(100.0, score))

        return {
            "privacy_score": round(score, 2),
            "grade": self._letter_grade(score),
            "risk_mitigated": entities_redacted,
            "latency_ms": latency_ms,
            "compliant": compliance_result.get("compliant", True),
        }

    def aggregate(self, sessions: list[dict]) -> dict:
        if not sessions:
            return {
                "mean_privacy_score": 0.0,
                "grade_distribution": {},
                "total_entities_redacted": 0,
                "latency_p50": 0.0,
                "latency_p95": 0.0,
                "latency_p99": 0.0,
            }

        scores = [s["privacy_score"] for s in sessions]
        latencies = sorted(s["latency_ms"] for s in sessions)

        grade_dist: dict[str, int] = {}
        for s in sessions:
            g = s["grade"]
            grade_dist[g] = grade_dist.get(g, 0) + 1

        def _percentile(sorted_data: list[float], pct: float) -> float:
            if not sorted_data:
                return 0.0
            idx = int(len(sorted_data) * pct / 100)
            idx = min(idx, len(sorted_data) - 1)
            return sorted_data[idx]

        return {
            "mean_privacy_score": round(statistics.mean(scores), 2),
            "grade_distribution": grade_dist,
            "total_entities_redacted": sum(s["risk_mitigated"] for s in sessions),
            "latency_p50": _percentile(latencies, 50),
            "latency_p95": _percentile(latencies, 95),
            "latency_p99": _percentile(latencies, 99),
        }

    def _letter_grade(self, score: float) -> str:
        if score >= 90:
            return "A"
        if score >= 75:
            return "B"
        if score >= 60:
            return "C"
        if score >= 40:
            return "D"
        return "F"
