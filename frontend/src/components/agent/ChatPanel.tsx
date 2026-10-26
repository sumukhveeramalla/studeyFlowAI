import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Bot, CheckCircle2, Send, Sparkles, User } from "lucide-react";
import { useRef, useState } from "react";
import { Chat } from "../../lib/api";
import type { ChatResponse, Proposal } from "../../lib/types";
import { AgentActivity } from "./AgentActivity";
import { ProposalPreview } from "./ProposalPreview";

interface Message {
  role: "user" | "assistant";
  text: string;
  response?: ChatResponse;
}

const SUGGESTIONS = [
  "I have an ML assignment due next Friday, ~6 hours, and a Chemistry midterm on Monday",
  "Add a Data Structures project due in 5 days",
  "Create a study plan for this week",
  "Break down my Machine Learning assignment",
  "I have an unexpected meeting tomorrow from 9 AM to 11 AM. Rearrange my schedule.",
  "Prioritize my tasks",
];

export function ChatPanel({
  showActivity = true,
  heightClass = "h-[420px]",
}: {
  showActivity?: boolean;
  heightClass?: string;
}) {
  const qc = useQueryClient();
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      text: "Hi! I'm your StudyFlow assistant. Just tell me what you have — like \"I have an ML assignment due Friday and a Chemistry midterm Monday\" — and I'll ask any follow-ups, then create it all and plan your week.",
    },
  ]);
  const [input, setInput] = useState("");
  const [lastProposal, setLastProposal] = useState<Proposal | null>(null);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [awaiting, setAwaiting] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const send = useMutation({
    mutationFn: (msg: string) => Chat.send(msg, conversationId),
    onSuccess: (res) => {
      setMessages((m) => [
        ...m,
        { role: "assistant", text: res.reply, response: res },
      ]);
      setLastProposal(res.proposal ?? null);

      // Track multi-turn intake conversation state.
      if (res.awaiting_input) {
        setConversationId(res.conversation_id);
        setAwaiting(true);
      } else {
        setConversationId(null);
        setAwaiting(false);
      }

      // When items are created, refresh every view that shows them.
      if (res.created_items.length > 0) {
        ["assignments", "tasks", "exams", "events", "dashboard"].forEach((k) =>
          qc.invalidateQueries({ queryKey: [k] })
        );
      }
      qc.invalidateQueries({ queryKey: ["agent-runs"] });

      setTimeout(
        () => scrollRef.current?.scrollTo({ top: 1e9, behavior: "smooth" }),
        50
      );
    },
    onError: () => {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          text: "Sorry, I couldn't reach the planning service. Make sure the backend is running.",
        },
      ]);
    },
  });

  function submit(text: string) {
    const msg = text.trim();
    if (!msg || send.isPending) return;
    setMessages((m) => [...m, { role: "user", text: msg }]);
    setInput("");
    send.mutate(msg);
    setTimeout(
      () => scrollRef.current?.scrollTo({ top: 1e9, behavior: "smooth" }),
      50
    );
  }

  const lastResponse = [...messages].reverse().find((m) => m.response)?.response;

  return (
    <div className="flex h-full flex-col">
      <div ref={scrollRef} className={`flex-1 space-y-3 overflow-y-auto pr-1 ${heightClass}`}>
        {messages.map((m, i) => (
          <div
            key={i}
            className={`flex gap-2 ${m.role === "user" ? "flex-row-reverse" : ""}`}
          >
            <div
              className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${
                m.role === "user"
                  ? "bg-slate-200 text-slate-600"
                  : "bg-brand-600 text-white"
              }`}
            >
              {m.role === "user" ? (
                <User className="h-4 w-4" />
              ) : (
                <Bot className="h-4 w-4" />
              )}
            </div>
            <div className="max-w-[85%]">
              <div
                className={`whitespace-pre-wrap rounded-2xl px-3 py-2 text-sm ${
                  m.role === "user"
                    ? "bg-brand-600 text-white"
                    : "bg-slate-50 text-slate-700"
                }`}
              >
                {m.text}
              </div>
              {m.response?.created_items && m.response.created_items.length > 0 && (
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {m.response.created_items.map((c) => (
                    <span
                      key={`${c.type}-${c.id}`}
                      className="inline-flex items-center gap-1 rounded-full border border-emerald-100 bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700"
                    >
                      <CheckCircle2 className="h-3 w-3" />
                      {c.type}: {c.title}
                      {c.subtask_count > 0 && ` (+${c.subtask_count} tasks)`}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {send.isPending && (
          <div className="flex gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-600 text-white">
              <Bot className="h-4 w-4" />
            </div>
            <div className="flex items-center gap-1 rounded-2xl bg-slate-50 px-3 py-3">
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.2s]" />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.1s]" />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400" />
            </div>
          </div>
        )}

        {lastProposal && (
          <ProposalPreview
            proposal={lastProposal}
            onDecided={() => setLastProposal(null)}
          />
        )}

        {showActivity && lastResponse?.run.steps && (
          <div className="rounded-2xl border border-slate-100 bg-slate-50/60 p-3">
            <AgentActivity
              steps={lastResponse.run.steps}
              mode={lastResponse.mode}
              compact
            />
          </div>
        )}
      </div>

      {messages.length <= 1 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => submit(s)}
              className="flex items-center gap-1 rounded-full border border-brand-100 bg-brand-50 px-2.5 py-1 text-xs font-medium text-brand-700 hover:bg-brand-100"
            >
              <Sparkles className="h-3 w-3" /> {s}
            </button>
          ))}
        </div>
      )}

      <form
        className="mt-3 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          submit(input);
        }}
      >
        <input
          className="input"
          placeholder={
            awaiting ? "Answer the assistant..." : "Tell me what you have, or ask me to plan..."
          }
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
        <button type="submit" className="btn-primary px-3" disabled={send.isPending}>
          <Send className="h-4 w-4" />
        </button>
      </form>
    </div>
  );
}
