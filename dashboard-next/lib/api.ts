// lib/api.ts
import type { AuditEntry, MetricsSnapshot } from "@/types/gateway";

const BASE =
  process.env.NEXT_PUBLIC_GATEWAY_URL ?? "http://localhost:8000";

export async function fetchMetrics(): Promise<MetricsSnapshot> {
  const res = await fetch(`${BASE}/v1/metrics`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Metrics fetch failed: ${res.status}`);
  return res.json();
}

export async function fetchAuditLog(): Promise<AuditEntry[]> {
  const res = await fetch(`${BASE}/v1/audit`, { cache: "no-store" });
  if (!res.ok) return [];
  return res.json();
}
