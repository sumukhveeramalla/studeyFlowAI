import clsx from "clsx";
import {
  addDays,
  format,
  isSameDay,
  parseISO,
  startOfWeek,
} from "date-fns";
import type { CalendarEvent } from "../../lib/types";
import { EVENT_COLORS, fmtTime } from "../../lib/format";

const DAY_START = 7; // 7am
const DAY_END = 23; // 11pm
const HOUR_PX = 48;

export function WeekCalendar({
  events,
  weekOffset = 0,
  onEventClick,
  onSlotClick,
}: {
  events: CalendarEvent[];
  weekOffset?: number;
  onEventClick?: (e: CalendarEvent) => void;
  onSlotClick?: (date: Date) => void;
}) {
  const base = addDays(new Date(), weekOffset * 7);
  const monday = startOfWeek(base, { weekStartsOn: 1 });
  const days = Array.from({ length: 7 }, (_, i) => addDays(monday, i));
  const hours = Array.from({ length: DAY_END - DAY_START }, (_, i) => DAY_START + i);

  function eventStyle(e: CalendarEvent) {
    const start = parseISO(e.start_at);
    const end = parseISO(e.end_at);
    const top = (start.getHours() + start.getMinutes() / 60 - DAY_START) * HOUR_PX;
    const height = Math.max(
      ((end.getTime() - start.getTime()) / 3600000) * HOUR_PX - 2,
      22
    );
    return { top: `${top}px`, height: `${height}px` };
  }

  // detect overlaps to flag conflicts
  const conflictIds = new Set<number>();
  for (let i = 0; i < events.length; i++) {
    for (let j = i + 1; j < events.length; j++) {
      const a = events[i];
      const b = events[j];
      if (!isSameDay(parseISO(a.start_at), parseISO(b.start_at))) continue;
      if (
        parseISO(a.start_at) < parseISO(b.end_at) &&
        parseISO(b.start_at) < parseISO(a.end_at)
      ) {
        conflictIds.add(a.id);
        conflictIds.add(b.id);
      }
    }
  }

  return (
    <div className="overflow-x-auto">
      <div className="min-w-[760px]">
        {/* header */}
        <div className="grid grid-cols-[52px_repeat(7,1fr)] border-b border-slate-100">
          <div />
          {days.map((d) => {
            const today = isSameDay(d, new Date());
            return (
              <div key={d.toISOString()} className="px-2 py-2 text-center">
                <p className="text-[11px] font-medium uppercase text-slate-400">
                  {format(d, "EEE")}
                </p>
                <p
                  className={clsx(
                    "mx-auto mt-1 flex h-7 w-7 items-center justify-center rounded-full text-sm font-semibold",
                    today ? "bg-brand-600 text-white" : "text-slate-700"
                  )}
                >
                  {format(d, "d")}
                </p>
              </div>
            );
          })}
        </div>

        {/* body */}
        <div className="grid grid-cols-[52px_repeat(7,1fr)]">
          {/* hour labels */}
          <div className="relative">
            {hours.map((h) => (
              <div
                key={h}
                style={{ height: HOUR_PX }}
                className="relative -top-2 pr-2 text-right text-[10px] text-slate-300"
              >
                {format(new Date().setHours(h, 0, 0, 0), "ha")}
              </div>
            ))}
          </div>

          {days.map((d) => {
            const dayEvents = events.filter((e) =>
              isSameDay(parseISO(e.start_at), d)
            );
            return (
              <div
                key={d.toISOString()}
                className="relative border-l border-slate-100"
                style={{ height: hours.length * HOUR_PX }}
              >
                {hours.map((h) => (
                  <div
                    key={h}
                    style={{ height: HOUR_PX }}
                    className="border-b border-slate-50 hover:bg-slate-50/60"
                    onClick={() => {
                      const dt = new Date(d);
                      dt.setHours(h, 0, 0, 0);
                      onSlotClick?.(dt);
                    }}
                  />
                ))}
                {dayEvents.map((e) => {
                  const c = EVENT_COLORS[e.kind];
                  const conflict = conflictIds.has(e.id);
                  return (
                    <button
                      key={e.id}
                      style={eventStyle(e)}
                      onClick={(ev) => {
                        ev.stopPropagation();
                        onEventClick?.(e);
                      }}
                      className={clsx(
                        "absolute left-1 right-1 overflow-hidden rounded-lg border px-2 py-1 text-left text-[11px] leading-tight shadow-sm transition-transform hover:z-10 hover:scale-[1.02]",
                        c.bg,
                        c.text,
                        !e.is_fixed && "border-dashed",
                        conflict && "ring-2 ring-rose-400"
                      )}
                      title={`${e.title} · ${fmtTime(e.start_at)}–${fmtTime(e.end_at)}`}
                    >
                      <p className="truncate font-semibold">{e.title}</p>
                      <p className="truncate opacity-80">{fmtTime(e.start_at)}</p>
                    </button>
                  );
                })}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export function CalendarLegend() {
  const items: { kind: keyof typeof EVENT_COLORS; label: string }[] = [
    { kind: "class", label: "Class" },
    { kind: "exam", label: "Exam" },
    { kind: "study", label: "Study" },
    { kind: "assignment", label: "Assignment" },
    { kind: "meeting", label: "Meeting" },
    { kind: "personal", label: "Personal" },
  ];
  return (
    <div className="flex flex-wrap items-center gap-3">
      {items.map((it) => (
        <div key={it.kind} className="flex items-center gap-1.5 text-xs text-slate-500">
          <span className={clsx("h-2.5 w-2.5 rounded-full", EVENT_COLORS[it.kind].dot)} />
          {it.label}
        </div>
      ))}
      <div className="flex items-center gap-1.5 text-xs text-slate-500">
        <span className="h-2.5 w-4 rounded border border-dashed border-slate-400" />
        Movable study block
      </div>
    </div>
  );
}
