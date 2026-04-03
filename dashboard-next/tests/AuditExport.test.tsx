// tests/AuditExport.test.tsx
import { render, screen } from "@testing-library/react";
import { AuditExport } from "@/components/bento/AuditExport";
import type { AuditEntry } from "@/types/gateway";

const entries: AuditEntry[] = [
  {
    id: "req-001",
    timestamp: "2026-01-01T00:00:00Z",
    session_id: "sess-abc",
    pii_types: ["PERSON", "EMAIL"],
    violations: [],
    watermarked: true,
  },
];

test("renders entry id", () => {
  render(<AuditExport entries={entries} />);
  expect(screen.getByText(/req-001/)).toBeInTheDocument();
});

test("renders watermarked badge", () => {
  render(<AuditExport entries={entries} />);
  expect(screen.getByText(/watermarked/i)).toBeInTheDocument();
});

test("renders empty state when no entries", () => {
  render(<AuditExport entries={[]} />);
  expect(screen.getByText(/no audit entries/i)).toBeInTheDocument();
});
