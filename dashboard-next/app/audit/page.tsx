// app/audit/page.tsx
"use client";

import { useEffect, useState } from "react";
import { fetchAuditLog } from "@/lib/api";
import type { AuditEntry } from "@/types/gateway";

export default function AuditPage() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAuditLog()
      .then(setEntries)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-6">
      <h1 className="text-xl font-semibold mb-6" style={{ color: "#e4e4e7" }}>
        Audit Log
      </h1>

      {loading ? (
        <p className="text-sm" style={{ color: "#52525b" }}>Loading…</p>
      ) : entries.length === 0 ? (
        <p className="text-sm" style={{ color: "#52525b" }}>No audit entries yet.</p>
      ) : (
        <div className="glass-card overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr style={{ background: "#18181b" }}>
                {["Request ID", "Timestamp", "Session", "PII Types", "Violations", "Watermarked"].map((h) => (
                  <th key={h} className="px-4 py-3 text-left font-medium" style={{ color: "#71717a" }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {entries.map((entry, i) => (
                <tr key={entry.id} style={{ background: i % 2 === 0 ? "#09090b" : "#111113" }}>
                  <td className="px-4 py-3 font-mono" style={{ color: "#a1a1aa" }}>{entry.id.slice(0, 12)}…</td>
                  <td className="px-4 py-3" style={{ color: "#71717a" }}>{new Date(entry.timestamp).toLocaleString()}</td>
                  <td className="px-4 py-3 font-mono" style={{ color: "#a1a1aa" }}>{entry.session_id.slice(0, 8)}</td>
                  <td className="px-4 py-3" style={{ color: "#60a5fa" }}>{entry.pii_types.join(", ") || "—"}</td>
                  <td className="px-4 py-3">
                    {entry.violations.length > 0 ? (
                      <span style={{ color: "#f87171" }}>{entry.violations.join(", ")}</span>
                    ) : (
                      <span style={{ color: "#4ade80" }}>Clean</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {entry.watermarked ? (
                      <span style={{ color: "#60a5fa" }}>✓</span>
                    ) : (
                      <span style={{ color: "#52525b" }}>—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
