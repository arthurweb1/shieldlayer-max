// tests/RisksAverted.test.tsx
import { render, screen } from "@testing-library/react";
import { RisksAverted } from "@/components/bento/RisksAverted";

test("renders formatted count", () => {
  render(<RisksAverted count={1234} />);
  expect(screen.getByText("1,234")).toBeInTheDocument();
});

test("renders zero count", () => {
  render(<RisksAverted count={0} />);
  expect(screen.getByText("0")).toBeInTheDocument();
});
