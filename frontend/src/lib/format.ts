import { format, formatDistanceToNowStrict, isToday, parseISO } from "date-fns";
import type { EventKind, Priority } from "./types";

export const PRIORITY_STYLES: Record<Priority, string> = {
  high: "bg-rose-50 text-rose-600 border border-rose-100",
  medium: "bg-amber-50 text-amber-600 border border-amber-100",
  low: "bg-emerald-50 text-emerald-600 border border-emerald-100",
};

export const STATUS_STYLES: Record<string, string> = {
  not_started: "bg-slate-100 text-slate-600",
  in_progress: "bg-brand-50 text-brand-700",
  completed: "bg-emerald-50 text-emerald-600",
};

export const EVENT_COLORS: Record<EventKind, { bg: string; text: string; dot: string }> = {
  class: { bg: "bg-brand-50 border-brand-200", text: "text-brand-700", dot: "bg-brand-500" },
  exam: { bg: "bg-rose-50 border-rose-200", text: "text-rose-700", dot: "bg-rose-500" },
  assignment: { bg: "bg-violet-50 border-violet-200", text: "text-violet-700", dot: "bg-violet-500" },
  study: { bg: "bg-emerald-50 border-emerald-200", text: "text-emerald-700", dot: "bg-emerald-500" },
  personal: { bg: "bg-slate-50 border-slate-200", text: "text-slate-700", dot: "bg-slate-400" },
  meeting: { bg: "bg-amber-50 border-amber-200", text: "text-amber-700", dot: "bg-amber-500" },
};

export function fmtDate(iso: string): string {
  return format(parseISO(iso), "MMM d, yyyy");
}

export function fmtDateTime(iso: string): string {
  return format(parseISO(iso), "MMM d, h:mm a");
}

export function fmtTime(iso: string): string {
  return format(parseISO(iso), "h:mm a");
}

export function fmtRelative(iso: string): string {
  const d = parseISO(iso);
  if (isToday(d)) return "Today";
  return formatDistanceToNowStrict(d, { addSuffix: true });
}

export function fmtDuration(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h && m) return `${h}h ${m}m`;
  if (h) return `${h}h`;
  return `${m}m`;
}

// For <input type="datetime-local"> round-tripping (local time).
export function toInputValue(iso?: string | null): string {
  const d = iso ? parseISO(iso) : new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(
    d.getHours()
  )}:${pad(d.getMinutes())}`;
}

export function fromInputValue(value: string): string {
  // value is local time with no tz; convert to ISO with local offset.
  return new Date(value).toISOString();
}
