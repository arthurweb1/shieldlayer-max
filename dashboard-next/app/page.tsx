// app/page.tsx
"use client";

import { RisksAverted } from "@/components/bento/RisksAverted";
import { ComplianceScore } from "@/components/bento/ComplianceScore";
import { LiveFeed } from "@/components/bento/LiveFeed";
import { AuditExport } from "@/components/bento/AuditExport";
import { useMetricsFeed } from "@/lib/ws";
import { fetchAuditLog } from "@/lib/api";
import { useEffect, useState } from "react";
import type { AuditEntry, MetricsSnapshot } from "@/types/gateway";

const FALLBACK: MetricsSnapshot = {
  risks_averted: 0,
  compliance_rewrites: 0,
  requests_total: 0,
  compliance_score: 100,
};

export default function Dashboard() {
  const metrics = useMetricsFeed(FALLBACK);
  const [audit, setAudit] = useState<AuditEntry[]>([]);

  useEffect(() => {
    fetchAuditLog().then(setAudit).catch(() => {});
  }, []);

  return (
    <div className="p-6 grid gap-4" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))" }}>
      <RisksAverted count={metrics.risks_averted} />
      <ComplianceScore score={metrics.compliance_score} />
      <LiveFeed metrics={metrics} />
      <div style={{ gridColumn: "1 / -1" }}>
        <AuditExport entries={audit} />
      </div>
    </div>
  );
}
