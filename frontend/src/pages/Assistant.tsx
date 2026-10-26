import { useQuery } from "@tanstack/react-query";
import { Bot, History } from "lucide-react";
import { ChatPanel } from "../components/agent/ChatPanel";
import { AgentActivity } from "../components/agent/AgentActivity";
import { Card, EmptyState, Spinner } from "../components/ui";
import { Agents } from "../lib/api";
import { fmtDateTime } from "../lib/format";

export function Assistant() {
  const { data: runs, isLoading } = useQuery({
    queryKey: ["agent-runs"],
    queryFn: Agents.runs,
    refetchInterval: 4000,
  });

  return (
    <div className="grid gap-5 lg:grid-cols-3">
      <Card className="flex flex-col lg:col-span-2">
        <div className="mb-3 flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-600 text-white">
            <Bot className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-slate-800">AI Assistant</h2>
            <p className="text-sm text-slate-400">
              Natural-language planning backed by a multi-agent workflow.
            </p>
          </div>
        </div>
        <ChatPanel heightClass="h-[calc(100vh-280px)]" showActivity />
      </Card>

      <Card className="lg:col-span-1">
        <div className="mb-3 flex items-center gap-2">
          <History className="h-4 w-4 text-slate-400" />
          <h2 className="text-base font-semibold text-slate-800">Agent Run History</h2>
        </div>
        {isLoading ? (
          <Spinner />
        ) : !runs?.length ? (
          <EmptyState title="No runs yet" hint="Send a message to start a workflow." />
        ) : (
          <div className="max-h-[calc(100vh-260px)] space-y-4 overflow-y-auto pr-1">
            {runs.map((run) => (
              <div key={run.id} className="rounded-xl border border-slate-100 p-3">
                <div className="mb-2 flex items-center justify-between">
                  <span className="rounded-full bg-brand-50 px-2 py-0.5 text-xs font-semibold capitalize text-brand-700">
                    {run.intent || "run"}
                  </span>
                  <span className="text-[11px] text-slate-400">
                    {fmtDateTime(run.created_at)}
                  </span>
                </div>
                <p className="mb-2 line-clamp-2 text-xs text-slate-500">
                  “{run.user_message}”
                </p>
                <AgentActivity steps={run.steps} mode={run.mode} compact />
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
