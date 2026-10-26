import { useQuery } from "@tanstack/react-query";
import {
  BookOpen,
  CalendarCheck,
  ChevronLeft,
  ChevronRight,
  GraduationCap,
  ListChecks,
  Sparkles,
} from "lucide-react";
import { useState } from "react";
import { CalendarLegend, WeekCalendar } from "../components/calendar/WeekCalendar";
import { ChatPanel } from "../components/agent/ChatPanel";
import { Card, EmptyState, Modal, Spinner, StatCard } from "../components/ui";
import { Dash } from "../lib/api";
import {
  EVENT_COLORS,
  PRIORITY_STYLES,
  fmtDateTime,
  fmtRelative,
  fmtTime,
} from "../lib/format";
import type { CalendarEvent } from "../lib/types";

export function Dashboard() {
  const [weekOffset, setWeekOffset] = useState(0);
  const [selected, setSelected] = useState<CalendarEvent | null>(null);
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard", weekOffset],
    queryFn: () => Dash.get(weekOffset),
  });

  return (
    <div className="space-y-5">
      {/* Overview cards */}
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <StatCard
          label="Upcoming Assignments"
          value={data?.stats.upcoming_assignments ?? "—"}
          icon={<BookOpen className="h-5 w-5" />}
        />
        <StatCard
          label="Upcoming Exams"
          value={data?.stats.upcoming_exams ?? "—"}
          icon={<GraduationCap className="h-5 w-5" />}
          accent="text-rose-600 bg-rose-50"
        />
        <StatCard
          label="Today's Study Tasks"
          value={data?.stats.todays_tasks ?? "—"}
          icon={<ListChecks className="h-5 w-5" />}
          accent="text-emerald-600 bg-emerald-50"
        />
        <StatCard
          label="Conflicts Resolved"
          value={data?.stats.conflicts_resolved ?? "—"}
          icon={<CalendarCheck className="h-5 w-5" />}
          accent="text-violet-600 bg-violet-50"
        />
      </div>

      <div className="grid gap-5 xl:grid-cols-3">
        {/* Weekly calendar */}
        <Card className="xl:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-slate-800">This Week</h2>
              <p className="text-sm text-slate-400">
                {weekOffset === 0
                  ? "Current week"
                  : weekOffset > 0
                  ? `${weekOffset} week(s) ahead`
                  : `${Math.abs(weekOffset)} week(s) ago`}
              </p>
            </div>
            <div className="flex items-center gap-1">
              <button
                className="btn-ghost px-2"
                onClick={() => setWeekOffset((w) => w - 1)}
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <button className="btn-ghost" onClick={() => setWeekOffset(0)}>
                Today
              </button>
              <button
                className="btn-ghost px-2"
                onClick={() => setWeekOffset((w) => w + 1)}
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
          {isLoading ? (
            <Spinner label="Loading your week..." />
          ) : (
            <>
              <WeekCalendar
                events={data?.week_events ?? []}
                weekOffset={weekOffset}
                onEventClick={setSelected}
              />
              <div className="mt-3 border-t border-slate-100 pt-3">
                <CalendarLegend />
              </div>
            </>
          )}
        </Card>

        {/* AI assistant panel */}
        <Card className="flex flex-col xl:col-span-1">
          <div className="mb-2 flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-white">
              <Sparkles className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-slate-800">AI Assistant</h2>
              <p className="text-xs text-slate-400">Plan, decompose, replan</p>
            </div>
          </div>
          <ChatPanel heightClass="h-[380px]" showActivity />
        </Card>
      </div>

      {/* Bottom cards */}
      <div className="grid gap-5 lg:grid-cols-3">
        <Card>
          <h3 className="mb-3 text-base font-semibold text-slate-800">
            Upcoming Deadlines
          </h3>
          {isLoading ? (
            <Spinner />
          ) : data?.upcoming_deadlines.length ? (
            <ul className="space-y-2.5">
              {data.upcoming_deadlines.map((a) => (
                <li key={a.id} className="flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-slate-700">
                      {a.title}
                    </p>
                    <p className="text-xs text-slate-400">{fmtDateTime(a.due_at)}</p>
                  </div>
                  <span
                    className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold ${PRIORITY_STYLES[a.priority]}`}
                  >
                    {fmtRelative(a.due_at)}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState title="No upcoming deadlines" hint="You're all caught up." />
          )}
        </Card>

        <Card>
          <h3 className="mb-3 text-base font-semibold text-slate-800">
            Today's Focus Tasks
          </h3>
          {isLoading ? (
            <Spinner />
          ) : data?.focus_tasks.length ? (
            <ul className="space-y-2.5">
              {data.focus_tasks.map((t) => (
                <li key={t.id} className="flex items-center gap-2.5">
                  <span
                    className={`h-2 w-2 shrink-0 rounded-full ${
                      t.priority === "high"
                        ? "bg-rose-500"
                        : t.priority === "medium"
                        ? "bg-amber-500"
                        : "bg-emerald-500"
                    }`}
                  />
                  <p className="min-w-0 flex-1 truncate text-sm text-slate-700">
                    {t.title}
                  </p>
                  <span className="shrink-0 text-xs text-slate-400">
                    {t.estimated_minutes}m
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState title="No focus tasks" hint="Generate tasks from an assignment." />
          )}
        </Card>

        <Card>
          <h3 className="mb-3 text-base font-semibold text-slate-800">Study Progress</h3>
          {isLoading ? (
            <Spinner />
          ) : (
            <div className="space-y-4">
              {data?.progress.map((p) => (
                <div key={p.label}>
                  <div className="mb-1 flex items-center justify-between text-sm">
                    <span className="text-slate-600">{p.label}</span>
                    <span className="font-semibold text-slate-700">{p.percent}%</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                    <div
                      className="h-full rounded-full bg-brand-500 transition-all"
                      style={{ width: `${p.percent}%` }}
                    />
                  </div>
                  <p className="mt-1 text-xs text-slate-400">
                    {p.completed} of {p.total}
                  </p>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      <Modal
        open={!!selected}
        onClose={() => setSelected(null)}
        title={selected?.title ?? "Event"}
      >
        {selected && (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span
                className={`h-3 w-3 rounded-full ${EVENT_COLORS[selected.kind].dot}`}
              />
              <span className="text-sm capitalize text-slate-600">{selected.kind}</span>
              {!selected.is_fixed && (
                <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs text-emerald-600">
                  Movable study block
                </span>
              )}
            </div>
            <p className="text-sm text-slate-600">
              {fmtDateTime(selected.start_at)} → {fmtTime(selected.end_at)}
            </p>
            {selected.location && (
              <p className="text-sm text-slate-500">📍 {selected.location}</p>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}
