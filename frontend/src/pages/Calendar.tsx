import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  addDays,
  addMonths,
  endOfMonth,
  format,
  isSameDay,
  isSameMonth,
  parseISO,
  startOfMonth,
  startOfWeek,
} from "date-fns";
import {
  ChevronLeft,
  ChevronRight,
  Plus,
  Sparkles,
  Trash2,
} from "lucide-react";
import { useMemo, useState } from "react";
import { ProposalPreview } from "../components/agent/ProposalPreview";
import { CalendarLegend, WeekCalendar } from "../components/calendar/WeekCalendar";
import { Card, EmptyState, Field, Modal, Spinner } from "../components/ui";
import { Events, Schedule } from "../lib/api";
import { EVENT_COLORS, fmtTime, fromInputValue, toInputValue } from "../lib/format";
import type { CalendarEvent, EventKind, Proposal } from "../lib/types";

type View = "week" | "day" | "month";

const EMPTY = {
  title: "",
  kind: "personal" as EventKind,
  start_at: toInputValue(),
  end_at: toInputValue(new Date(Date.now() + 3600000).toISOString()),
  is_fixed: true,
  location: "",
};

export function CalendarPage() {
  const qc = useQueryClient();
  const { data: events, isLoading } = useQuery({
    queryKey: ["events"],
    queryFn: Events.list,
  });
  const [view, setView] = useState<View>("week");
  const [weekOffset, setWeekOffset] = useState(0);
  const [dayDate, setDayDate] = useState(new Date());
  const [monthDate, setMonthDate] = useState(new Date());
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<CalendarEvent | null>(null);
  const [form, setForm] = useState(EMPTY);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [proposal, setProposal] = useState<Proposal | null>(null);

  const save = useMutation({
    mutationFn: (payload: Partial<CalendarEvent>) =>
      editing ? Events.update(editing.id, payload) : Events.create(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["events"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      setModalOpen(false);
    },
  });
  const remove = useMutation({
    mutationFn: (id: number) => Events.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["events"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      setModalOpen(false);
    },
  });
  const generate = useMutation({
    mutationFn: () => Schedule.generate(7),
    onSuccess: (p) => setProposal(p),
  });

  function openCreate(dt?: Date) {
    setEditing(null);
    const start = dt ?? new Date();
    setForm({
      ...EMPTY,
      start_at: toInputValue(start.toISOString()),
      end_at: toInputValue(new Date(start.getTime() + 3600000).toISOString()),
    });
    setErrors({});
    setModalOpen(true);
  }
  function openEdit(e: CalendarEvent) {
    setEditing(e);
    setForm({
      title: e.title,
      kind: e.kind,
      start_at: toInputValue(e.start_at),
      end_at: toInputValue(e.end_at),
      is_fixed: e.is_fixed,
      location: e.location,
    });
    setErrors({});
    setModalOpen(true);
  }
  function submit() {
    const err: Record<string, string> = {};
    if (!form.title.trim()) err.title = "Title is required";
    if (new Date(form.end_at) <= new Date(form.start_at))
      err.end_at = "End must be after start";
    setErrors(err);
    if (Object.keys(err).length) return;
    save.mutate({
      ...form,
      start_at: fromInputValue(form.start_at),
      end_at: fromInputValue(form.end_at),
    });
  }

  const header = useMemo(() => {
    if (view === "week") {
      const monday = startOfWeek(addDays(new Date(), weekOffset * 7), {
        weekStartsOn: 1,
      });
      return `${format(monday, "MMM d")} – ${format(addDays(monday, 6), "MMM d, yyyy")}`;
    }
    if (view === "day") return format(dayDate, "EEEE, MMM d, yyyy");
    return format(monthDate, "MMMM yyyy");
  }, [view, weekOffset, dayDate, monthDate]);

  return (
    <div className="space-y-5">
      {proposal && (
        <ProposalPreview proposal={proposal} onDecided={() => setProposal(null)} />
      )}
      <Card>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <button
              className="btn-ghost px-2"
              onClick={() => shift(-1)}
              aria-label="Previous"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span className="min-w-[200px] text-center text-sm font-semibold text-slate-700">
              {header}
            </span>
            <button
              className="btn-ghost px-2"
              onClick={() => shift(1)}
              aria-label="Next"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex overflow-hidden rounded-xl border border-slate-200">
              {(["day", "week", "month"] as View[]).map((v) => (
                <button
                  key={v}
                  onClick={() => setView(v)}
                  className={`px-3 py-1.5 text-sm font-medium capitalize ${
                    view === v ? "bg-brand-600 text-white" : "bg-white text-slate-500"
                  }`}
                >
                  {v}
                </button>
              ))}
            </div>
            <button
              className="btn-ghost"
              onClick={() => generate.mutate()}
              disabled={generate.isPending}
            >
              <Sparkles className="h-4 w-4" /> Generate
            </button>
            <button className="btn-primary" onClick={() => openCreate()}>
              <Plus className="h-4 w-4" /> Event
            </button>
          </div>
        </div>

        {isLoading ? (
          <Spinner label="Loading calendar..." />
        ) : view === "week" ? (
          <WeekCalendar
            events={events ?? []}
            weekOffset={weekOffset}
            onEventClick={openEdit}
            onSlotClick={openCreate}
          />
        ) : view === "day" ? (
          <DayView events={events ?? []} date={dayDate} onEventClick={openEdit} />
        ) : (
          <MonthView
            events={events ?? []}
            monthDate={monthDate}
            onDayClick={(d) => {
              setDayDate(d);
              setView("day");
            }}
            onEventClick={openEdit}
          />
        )}

        <div className="mt-3 border-t border-slate-100 pt-3">
          <CalendarLegend />
        </div>
      </Card>

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editing ? "Edit event" : "New event"}
      >
        <div className="space-y-3">
          <Field label="Title" error={errors.title}>
            <input
              className="input"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
            />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Type">
              <select
                className="input"
                value={form.kind}
                onChange={(e) =>
                  setForm({ ...form, kind: e.target.value as EventKind })
                }
              >
                <option value="class">Class</option>
                <option value="exam">Exam</option>
                <option value="study">Study</option>
                <option value="assignment">Assignment</option>
                <option value="meeting">Meeting</option>
                <option value="personal">Personal</option>
              </select>
            </Field>
            <Field label="Location">
              <input
                className="input"
                value={form.location}
                onChange={(e) => setForm({ ...form, location: e.target.value })}
              />
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Start">
              <input
                type="datetime-local"
                className="input"
                value={form.start_at}
                onChange={(e) => setForm({ ...form, start_at: e.target.value })}
              />
            </Field>
            <Field label="End" error={errors.end_at}>
              <input
                type="datetime-local"
                className="input"
                value={form.end_at}
                onChange={(e) => setForm({ ...form, end_at: e.target.value })}
              />
            </Field>
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={form.is_fixed}
              onChange={(e) => setForm({ ...form, is_fixed: e.target.checked })}
            />
            Fixed event (cannot be moved by the scheduler)
          </label>
          <div className="flex items-center justify-between gap-2 pt-2">
            {editing ? (
              <button
                className="btn-danger"
                onClick={() => remove.mutate(editing.id)}
              >
                <Trash2 className="h-4 w-4" /> Delete
              </button>
            ) : (
              <span />
            )}
            <div className="flex gap-2">
              <button className="btn-ghost" onClick={() => setModalOpen(false)}>
                Cancel
              </button>
              <button className="btn-primary" onClick={submit} disabled={save.isPending}>
                {save.isPending ? "Saving..." : editing ? "Save" : "Create"}
              </button>
            </div>
          </div>
        </div>
      </Modal>
    </div>
  );

  function shift(dir: number) {
    if (view === "week") setWeekOffset((w) => w + dir);
    else if (view === "day") setDayDate((d) => addDays(d, dir));
    else setMonthDate((d) => addMonths(d, dir));
  }
}

function DayView({
  events,
  date,
  onEventClick,
}: {
  events: CalendarEvent[];
  date: Date;
  onEventClick: (e: CalendarEvent) => void;
}) {
  const dayEvents = events
    .filter((e) => isSameDay(parseISO(e.start_at), date))
    .sort((a, b) => parseISO(a.start_at).getTime() - parseISO(b.start_at).getTime());
  if (!dayEvents.length)
    return <EmptyState title="Nothing scheduled" hint="Add an event for this day." />;
  return (
    <div className="space-y-2">
      {dayEvents.map((e) => {
        const c = EVENT_COLORS[e.kind];
        return (
          <button
            key={e.id}
            onClick={() => onEventClick(e)}
            className={`flex w-full items-center gap-3 rounded-xl border p-3 text-left ${c.bg} ${
              !e.is_fixed ? "border-dashed" : ""
            }`}
          >
            <span className={`h-2.5 w-2.5 rounded-full ${c.dot}`} />
            <div className="flex-1">
              <p className={`font-semibold ${c.text}`}>{e.title}</p>
              <p className="text-xs text-slate-500">
                {fmtTime(e.start_at)} – {fmtTime(e.end_at)}
                {e.location && ` · ${e.location}`}
              </p>
            </div>
            <span className="text-xs capitalize text-slate-400">{e.kind}</span>
          </button>
        );
      })}
    </div>
  );
}

function MonthView({
  events,
  monthDate,
  onDayClick,
  onEventClick,
}: {
  events: CalendarEvent[];
  monthDate: Date;
  onDayClick: (d: Date) => void;
  onEventClick: (e: CalendarEvent) => void;
}) {
  const start = startOfWeek(startOfMonth(monthDate), { weekStartsOn: 1 });
  const end = endOfMonth(monthDate);
  const weeks: Date[][] = [];
  let cur = start;
  while (cur <= end || weeks.length < 6) {
    const week: Date[] = [];
    for (let i = 0; i < 7; i++) {
      week.push(cur);
      cur = addDays(cur, 1);
    }
    weeks.push(week);
    if (weeks.length >= 6) break;
  }
  return (
    <div>
      <div className="grid grid-cols-7 border-b border-slate-100 pb-1 text-center text-xs font-semibold uppercase text-slate-400">
        {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => (
          <div key={d}>{d}</div>
        ))}
      </div>
      <div className="grid grid-cols-7">
        {weeks.flat().map((d) => {
          const dayEvents = events.filter((e) =>
            isSameDay(parseISO(e.start_at), d)
          );
          const inMonth = isSameMonth(d, monthDate);
          const today = isSameDay(d, new Date());
          return (
            <div
              key={d.toISOString()}
              onClick={() => onDayClick(d)}
              className={`min-h-[92px] cursor-pointer border-b border-r border-slate-50 p-1.5 ${
                inMonth ? "" : "bg-slate-50/40 text-slate-300"
              }`}
            >
              <div
                className={`mb-1 inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold ${
                  today ? "bg-brand-600 text-white" : ""
                }`}
              >
                {format(d, "d")}
              </div>
              <div className="space-y-0.5">
                {dayEvents.slice(0, 3).map((e) => (
                  <button
                    key={e.id}
                    onClick={(ev) => {
                      ev.stopPropagation();
                      onEventClick(e);
                    }}
                    className={`block w-full truncate rounded px-1 py-0.5 text-left text-[10px] ${EVENT_COLORS[e.kind].bg} ${EVENT_COLORS[e.kind].text}`}
                  >
                    {e.title}
                  </button>
                ))}
                {dayEvents.length > 3 && (
                  <p className="text-[10px] text-slate-400">+{dayEvents.length - 3} more</p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
