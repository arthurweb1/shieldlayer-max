// tests/ComplianceScore.test.tsx
import { render, screen } from "@testing-library/react";
import { ComplianceScore } from "@/components/bento/ComplianceScore";

test("renders score percentage", () => {
  render(<ComplianceScore score={87} />);
  expect(screen.getByText("87%")).toBeInTheDocument();
});

test("renders 100% when perfect", () => {
  render(<ComplianceScore score={100} />);
  expect(screen.getByText("100%")).toBeInTheDocument();
});
