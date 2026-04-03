"use client";

import type { MetricsSnapshot } from "@/types/gateway";

interface Props {
  metrics: MetricsSnapshot;
}

export function LiveFeed({ metrics }: Props) {
  return (
    <div className="glass-card p-6 flex flex-col gap-4">
      <p className="text-xs uppercase tracking-widest" style={{ color: "#71717a" }}>
        Live Feed
      </p>
      <div className="flex flex-col gap-3">
        <div className="flex justify-between items-center">
          <span className="text-sm" style={{ color: "#a1a1aa" }}>Total Requests</span>
          <span className="text-xl font-bold tabular-nums" style={{ color: "#60a5fa" }}>
            {metrics.requests_total}
          </span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-sm" style={{ color: "#a1a1aa" }}>Compliance Rewrites</span>
          <span className="text-xl font-bold tabular-nums" style={{ color: "#f59e0b" }}>
            {metrics.compliance_rewrites}
          </span>
        </div>
      </div>
    </div>
  );
}
