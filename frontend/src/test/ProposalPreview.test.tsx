import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ProposalPreview } from "../components/agent/ProposalPreview";
import type { Proposal } from "../lib/types";

const proposal: Proposal = {
  id: 1,
  status: "pending",
  reason: "Rescheduled affected work around the new meeting.",
  summary: {
    original: [
      {
        id: 10,
        title: "Study: ML",
        start_at: "2026-01-02T14:00:00+00:00",
        end_at: "2026-01-02T16:00:00+00:00",
      },
    ],
    proposed: [
      {
        id: null,
        title: "Study: ML",
        start_at: "2026-01-02T18:00:00+00:00",
        end_at: "2026-01-02T20:00:00+00:00",
      },
    ],
    added_count: 1,
    moved_count: 0,
    removed_count: 1,
    infeasible: [],
    new_event: { title: "Unexpected meeting" },
  },
  changes: {
    added: [
      {
        title: "Study: ML",
        kind: "study",
        start_at: "2026-01-02T18:00:00+00:00",
        end_at: "2026-01-02T20:00:00+00:00",
        task_id: null,
        assignment_id: 1,
        exam_id: null,
      },
    ],
    moved: [],
    removed: [10],
  },
  created_at: "2026-01-01T00:00:00+00:00",
  decided_at: null,
};

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient();
  return <QueryClientProvider client={qc}>{ui}</QueryClientProvider>;
}

describe("ProposalPreview", () => {
  it("renders original/proposed and approve controls for a pending proposal", () => {
    render(wrap(<ProposalPreview proposal={proposal} />));
    expect(screen.getByText(/Proposed schedule changes/i)).toBeInTheDocument();
    expect(screen.getByText(/Original schedule/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /approve/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reject/i })).toBeInTheDocument();
  });
});
