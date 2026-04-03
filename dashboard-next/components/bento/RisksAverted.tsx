// components/bento/RisksAverted.tsx
interface Props {
  count: number;
}

export function RisksAverted({ count }: Props) {
  return (
    <div className="glass-card p-6 flex flex-col gap-2">
      <p className="text-xs uppercase tracking-widest" style={{ color: "#71717a" }}>
        Risks Averted
      </p>
      <p className="text-5xl font-bold tabular-nums" style={{ color: "#60a5fa" }}>
        {count.toLocaleString("en-US")}
      </p>
      <p className="text-xs" style={{ color: "#52525b" }}>
        PII tokens intercepted this session
      </p>
    </div>
  );
}
