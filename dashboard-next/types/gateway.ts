// dashboard-next/types/gateway.ts
export interface MetricsSnapshot {
  risks_averted: number;
  compliance_rewrites: number;
  requests_total: number;
  compliance_score: number;
}

export interface AuditEntry {
  id: string;
  timestamp: string;
  session_id: string;
  pii_types: string[];
  violations: string[];
  watermarked: boolean;
}
