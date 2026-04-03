// components/bento/ComplianceScore.tsx
interface Props {
  score: number;
}

export function ComplianceScore({ score }: Props) {
  // Radial progress using SVG (testable, no Recharts dependency)
  const radius = 36;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;

  return (
    <div className="glass-card p-6 flex flex-col gap-2 items-center">
      <p className="text-xs uppercase tracking-widest self-start" style={{ color: "#71717a" }}>
        Compliance Score
      </p>
      <svg width="100" height="100" viewBox="0 0 100 100">
        <circle cx="50" cy="50" r={radius} fill="none" stroke="#27272a" strokeWidth="8" />
        <circle
          cx="50"
          cy="50"
          r={radius}
          fill="none"
          stroke="#3b82f6"
          strokeWidth="8"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform="rotate(-90 50 50)"
        />
      </svg>
      <p className="text-2xl font-bold" style={{ color: "#60a5fa" }}>
        {score}%
      </p>
    </div>
  );
}
