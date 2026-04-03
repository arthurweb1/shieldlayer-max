// components/layout/TopBar.tsx
export function TopBar() {
  return (
    <header
      style={{
        background: "rgba(15,15,16,0.8)",
        borderBottom: "1px solid rgba(255,255,255,0.05)",
        backdropFilter: "blur(12px)",
      }}
      className="fixed top-0 left-16 right-0 h-14 flex items-center justify-between px-8 z-40"
    >
      <h1 className="text-sm font-medium tracking-widest uppercase" style={{ color: "#71717a" }}>
        ShieldLayer <span style={{ color: "#60a5fa" }}>Max</span>
      </h1>
      <span
        className="text-xs px-2 py-1 rounded border"
        style={{ color: "#60a5fa", borderColor: "rgba(59,130,246,0.3)" }}
      >
        EU AI Act Compliant
      </span>
    </header>
  );
}
