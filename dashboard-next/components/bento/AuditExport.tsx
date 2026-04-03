import type { AuditEntry } from "@/types/gateway";

interface Props {
  entries: AuditEntry[];
}

export function AuditExport({ entries }: Props) {
  if (entries.length === 0) {
    return (
      <div className="glass-card p-6 flex items-center justify-center">
        <p className="text-sm" style={{ color: "#52525b" }}>No audit entries</p>
      </div>
    );
  }

  return (
    <div className="glass-card p-6 flex flex-col gap-3">
      <p className="text-xs uppercase tracking-widest" style={{ color: "#71717a" }}>
        Audit Log
      </p>
      <div className="flex flex-col gap-2 overflow-auto max-h-64">
        {entries.map((entry) => (
          <div key={entry.id} className="flex items-center justify-between text-xs py-2 border-b" style={{ borderColor: "#27272a" }}>
            <span className="font-mono" style={{ color: "#a1a1aa" }}>{entry.id}</span>
            <div className="flex items-center gap-2">
              {entry.watermarked && (
                <span className="px-2 py-0.5 rounded text-xs" style={{ background: "#1e3a5f", color: "#60a5fa" }}>
                  Watermarked
                </span>
              )}
              {entry.violations.length > 0 && (
                <span className="px-2 py-0.5 rounded text-xs" style={{ background: "#3b1a1a", color: "#f87171" }}>
                  {entry.violations.length} violation{entry.violations.length > 1 ? "s" : ""}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
