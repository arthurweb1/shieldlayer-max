// tests/LiveFeed.test.tsx
import { render, screen } from "@testing-library/react";
import { LiveFeed } from "@/components/bento/LiveFeed";
import type { MetricsSnapshot } from "@/types/gateway";

const snapshot: MetricsSnapshot = {
  risks_averted: 42,
  compliance_rewrites: 3,
  requests_total: 100,
  compliance_score: 97,
};

test("renders requests total", () => {
  render(<LiveFeed metrics={snapshot} />);
  expect(screen.getByText("100")).toBeInTheDocument();
});

test("renders compliance rewrites count", () => {
  render(<LiveFeed metrics={snapshot} />);
  expect(screen.getByText("3")).toBeInTheDocument();
});
