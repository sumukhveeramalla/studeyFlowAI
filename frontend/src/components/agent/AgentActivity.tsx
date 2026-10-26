import clsx from "clsx";
import {
  Activity,
  BrainCircuit,
  CalendarClock,
  CheckCircle2,
  ListTree,
  RefreshCw,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import type { AgentStep } from "../../lib/types";

const AGENT_ICON: Record<string, typeof Activity> = {
  supervisor: BrainCircuit,
  academic: ListTree,
  task_planner: ListTree,
  scheduler: CalendarClock,
  replanner: RefreshCw,
  validator: ShieldCheck,
};

export function AgentActivity({
  steps,
  mode,
  compact,
}: {
  steps: AgentStep[];
  mode?: string;
  compact?: boolean;
}) {
  if (!steps?.length) {
    return (
      <div className="flex items-center gap-2 text-sm text-slate-400">
        <Activity className="h-4 w-4" /> No agent activity yet.
      </div>
    );
  }
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
          <Activity className="h-3.5 w-3.5" /> Agent Activity
        </p>
        {mode && (
          <span
            className={clsx(
              "rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase",
              mode === "llm"
                ? "bg-brand-100 text-brand-700"
                : "bg-slate-100 text-slate-500"
            )}
          >
            {mode === "llm" ? "LLM" : "Demo"} mode
          </span>
        )}
      </div>
      <ol className="space-y-2">
        {steps.map((s) => {
          const Icon = AGENT_ICON[s.agent] ?? Activity;
          const v = s.validation;
          return (
            <li
              key={s.idx}
              className="flex gap-2.5 rounded-xl border border-slate-100 bg-white p-2.5"
            >
              <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
                <Icon className="h-4 w-4" />
              </div>
              <div className="min-w-0">
                <p className="flex flex-wrap items-center gap-1.5 text-[13px] font-semibold capitalize text-slate-700">
                  {s.agent.replace("_", " ")}
                  {s.tool && (
                    <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium normal-case text-slate-500">
                      {s.tool}
                    </span>
                  )}
                </p>
                {!compact && <p className="text-xs text-slate-500">{s.note}</p>}
                {v && (
                  <p
                    className={clsx(
                      "mt-1 inline-flex items-center gap-1 text-[11px] font-medium",
                      v.ok ? "text-emerald-600" : "text-rose-600"
                    )}
                  >
                    {v.ok ? (
                      <CheckCircle2 className="h-3 w-3" />
                    ) : (
                      <XCircle className="h-3 w-3" />
                    )}
                    {v.ok
                      ? "Validation passed"
                      : `Validation failed (${v.errors.length})`}
                  </p>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
