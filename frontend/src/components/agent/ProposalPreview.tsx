import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Check, Minus, Plus, X } from "lucide-react";
import { Proposals } from "../../lib/api";
import type { Proposal } from "../../lib/types";
import { fmtDateTime } from "../../lib/format";

function blockTime(b: Record<string, unknown>): string {
  const s = b.start_at as string;
  const e = b.end_at as string;
  return `${fmtDateTime(s)} → ${fmtDateTime(e)}`;
}

export function ProposalPreview({
  proposal,
  onDecided,
}: {
  proposal: Proposal;
  onDecided?: (status: "approved" | "rejected") => void;
}) {
  const qc = useQueryClient();
  const invalidate = () => {
    ["dashboard", "events", "proposals", "agent-runs", "tasks"].forEach((k) =>
      qc.invalidateQueries({ queryKey: [k] })
    );
  };

  const approve = useMutation({
    mutationFn: () => Proposals.approve(proposal.id),
    onSuccess: () => {
      invalidate();
      onDecided?.("approved");
    },
  });
  const reject = useMutation({
    mutationFn: () => Proposals.reject(proposal.id),
    onSuccess: () => {
      invalidate();
      onDecided?.("rejected");
    },
  });

  const decided = proposal.status !== "pending";
  const s = proposal.summary;
  const addedBlocks = proposal.changes.added ?? [];
  const removedOriginals = (s.original ?? []).filter((o) =>
    proposal.changes.removed?.includes(o.id as number)
  );

  return (
    <div className="rounded-2xl border border-brand-100 bg-brand-50/50 p-4">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-sm font-semibold text-brand-800">Proposed schedule changes</p>
        <span
          className={
            "rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize " +
            (proposal.status === "approved"
              ? "bg-emerald-100 text-emerald-700"
              : proposal.status === "rejected"
              ? "bg-slate-200 text-slate-600"
              : "bg-amber-100 text-amber-700")
          }
        >
          {proposal.status}
        </span>
      </div>

      <p className="mb-3 text-sm text-slate-600">{proposal.reason}</p>

      <div className="grid gap-3 md:grid-cols-2">
        <div className="rounded-xl bg-white p-3">
          <p className="mb-2 text-xs font-semibold uppercase text-slate-400">
            Original schedule ({s.original?.length ?? 0})
          </p>
          <div className="space-y-1.5">
            {(s.original ?? []).length === 0 && (
              <p className="text-xs text-slate-400">No study blocks yet.</p>
            )}
            {(s.original ?? []).map((b, i) => (
              <div key={i} className="text-xs text-slate-600">
                <span className="font-medium">{String(b.title)}</span>
                <span className="block text-slate-400">{blockTime(b)}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-xl bg-white p-3">
          <p className="mb-2 text-xs font-semibold uppercase text-slate-400">
            Proposed schedule ({s.proposed?.length ?? 0})
          </p>
          <div className="space-y-1.5">
            {(s.proposed ?? []).map((b, i) => (
              <div key={i} className="text-xs text-slate-600">
                <span className="font-medium">{String(b.title)}</span>
                <span className="block text-slate-400">{blockTime(b)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* diff */}
      <div className="mt-3 space-y-1.5">
        {addedBlocks.map((b, i) => (
          <div key={`a${i}`} className="flex items-center gap-2 text-xs text-emerald-700">
            <Plus className="h-3.5 w-3.5" /> Add <b>{b.title}</b> ({blockTime(b as never)})
          </div>
        ))}
        {removedOriginals.map((b, i) => (
          <div key={`r${i}`} className="flex items-center gap-2 text-xs text-rose-600">
            <Minus className="h-3.5 w-3.5" /> Remove <b>{String(b.title)}</b> ({blockTime(b)})
          </div>
        ))}
        {(proposal.changes.moved ?? []).map((_m, i) => (
          <div key={`m${i}`} className="flex items-center gap-2 text-xs text-amber-700">
            <ArrowRight className="h-3.5 w-3.5" /> Move block
          </div>
        ))}
        {s.new_event && (
          <div className="flex items-center gap-2 text-xs text-slate-600">
            <ArrowRight className="h-3.5 w-3.5" /> New fixed event:{" "}
            <b>{String((s.new_event as Record<string, unknown>).title)}</b>
          </div>
        )}
        {(s.infeasible ?? []).map((inf, i) => (
          <div key={`i${i}`} className="text-xs text-rose-600">
            ⚠ {inf.label}: scheduled {inf.placed_minutes} of {inf.needed_minutes} min —{" "}
            {inf.reason}
          </div>
        ))}
      </div>

      {!decided && (
        <div className="mt-4 flex gap-2">
          <button
            className="btn-primary flex-1"
            onClick={() => approve.mutate()}
            disabled={approve.isPending || reject.isPending}
          >
            <Check className="h-4 w-4" /> Approve
          </button>
          <button
            className="btn-ghost flex-1"
            onClick={() => reject.mutate()}
            disabled={approve.isPending || reject.isPending}
          >
            <X className="h-4 w-4" /> Reject
          </button>
        </div>
      )}
    </div>
  );
}
