import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { endOfDay, endOfWeek, isAfter, isBefore, parseISO } from "date-fns";
import { Check, CheckSquare, Link2, Pencil, Plus, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { Card, EmptyState, Field, Modal, Spinner } from "../components/ui";
import { Assignments, Tasks } from "../lib/api";
import { PRIORITY_STYLES, fmtDateTime, fromInputValue, toInputValue } from "../lib/format";
import type { Priority, Task } from "../lib/types";

type Filter = "all" | "today" | "week" | "overdue" | "completed";

const EMPTY = {
  title: "",
  priority: "medium" as Priority,
  estimated_minutes: 60,
  deadline: toInputValue(),
  assignment_id: null as number | null,
};

export function TasksPage() {
  const qc = useQueryClient();
  const { data: tasks, isLoading } = useQuery({ queryKey: ["tasks"], queryFn: Tasks.list });
  const { data: assignments } = useQuery({
    queryKey: ["assignments"],
    queryFn: Assignments.list,
  });
  const [filter, setFilter] = useState<Filter>("all");
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Task | null>(null);
  const [form, setForm] = useState(EMPTY);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const save = useMutation({
    mutationFn: (payload: Partial<Task>) =>
      editing ? Tasks.update(editing.id, payload) : Tasks.create(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tasks"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      setModalOpen(false);
    },
  });
  const toggle = useMutation({
    mutationFn: (t: Task) =>
      Tasks.update(t.id, {
        status: t.status === "completed" ? "not_started" : "completed",
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tasks"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
  const remove = useMutation({
    mutationFn: (id: number) => Tasks.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tasks"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });

  const assignmentName = (id: number | null) =>
    assignments?.find((a) => a.id === id)?.title;

  const counts = useMemo(() => {
    const list = tasks ?? [];
    const now = new Date();
    return {
      all: list.length,
      today: list.filter(
        (t) =>
          t.deadline &&
          t.status !== "completed" &&
          isBefore(parseISO(t.deadline), endOfDay(now))
      ).length,
      week: list.filter(
        (t) =>
          t.deadline &&
          t.status !== "completed" &&
          isBefore(parseISO(t.deadline), endOfWeek(now, { weekStartsOn: 1 }))
      ).length,
      overdue: list.filter(
        (t) =>
          t.deadline && t.status !== "completed" && isAfter(now, parseISO(t.deadline))
      ).length,
      completed: list.filter((t) => t.status === "completed").length,
    };
  }, [tasks]);

  const filtered = useMemo(() => {
    const list = tasks ?? [];
    const now = new Date();
    switch (filter) {
      case "today":
        return list.filter(
          (t) =>
            t.deadline &&
            t.status !== "completed" &&
            isBefore(parseISO(t.deadline), endOfDay(now))
        );
      case "week":
        return list.filter(
          (t) =>
            t.deadline &&
            t.status !== "completed" &&
            isBefore(parseISO(t.deadline), endOfWeek(now, { weekStartsOn: 1 }))
        );
      case "overdue":
        return list.filter(
          (t) =>
            t.deadline &&
            t.status !== "completed" &&
            isAfter(now, parseISO(t.deadline))
        );
      case "completed":
        return list.filter((t) => t.status === "completed");
      default:
        return list;
    }
  }, [tasks, filter]);

  function openCreate() {
    setEditing(null);
    setForm(EMPTY);
    setErrors({});
    setModalOpen(true);
  }
  function openEdit(t: Task) {
    setEditing(t);
    setForm({
      title: t.title,
      priority: t.priority,
      estimated_minutes: t.estimated_minutes,
      deadline: t.deadline ? toInputValue(t.deadline) : toInputValue(),
      assignment_id: t.assignment_id,
    });
    setErrors({});
    setModalOpen(true);
  }
  function submit() {
    const e: Record<string, string> = {};
    if (!form.title.trim()) e.title = "Title is required";
    if (form.estimated_minutes < 5) e.estimated_minutes = "At least 5 minutes";
    setErrors(e);
    if (Object.keys(e).length) return;
    save.mutate({
      ...form,
      deadline: form.deadline ? fromInputValue(form.deadline) : null,
      assignment_id: form.assignment_id || null,
    });
  }

  const TABS: { key: Filter; label: string }[] = [
    { key: "all", label: `All (${counts.all})` },
    { key: "today", label: `Today (${counts.today})` },
    { key: "week", label: `This Week (${counts.week})` },
    { key: "overdue", label: `Overdue (${counts.overdue})` },
    { key: "completed", label: `Completed (${counts.completed})` },
  ];

  const recommendations = useMemo(() => {
    const list = tasks ?? [];
    const overdue = list.filter(
      (t) => t.deadline && t.status !== "completed" && isAfter(new Date(), parseISO(t.deadline))
    );
    const recs: string[] = [];
    if (overdue.length)
      recs.push(`You have ${overdue.length} overdue task(s). Consider replanning your week.`);
    const highOpen = list.filter((t) => t.priority === "high" && t.status !== "completed");
    if (highOpen.length)
      recs.push(`Focus on ${highOpen.length} high-priority task(s) first.`);
    const totalMin = list
      .filter((t) => t.status !== "completed")
      .reduce((s, t) => s + t.estimated_minutes, 0);
    if (totalMin)
      recs.push(
        `About ${Math.round(totalMin / 60)}h of work remaining. Ask the AI to schedule it.`
      );
    return recs;
  }, [tasks]);

  return (
    <div className="space-y-5">
      {recommendations.length > 0 && (
        <Card className="border-brand-100 bg-brand-50/40">
          <p className="mb-2 text-sm font-semibold text-brand-800">AI Recommendations</p>
          <ul className="space-y-1 text-sm text-slate-600">
            {recommendations.map((r, i) => (
              <li key={i}>• {r}</li>
            ))}
          </ul>
        </Card>
      )}

      <Card>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap gap-1.5">
            {TABS.map((t) => (
              <button
                key={t.key}
                onClick={() => setFilter(t.key)}
                className={`rounded-xl px-3 py-1.5 text-sm font-medium ${
                  filter === t.key
                    ? "bg-brand-600 text-white"
                    : "bg-slate-100 text-slate-500 hover:bg-slate-200"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
          <button className="btn-primary" onClick={openCreate}>
            <Plus className="h-4 w-4" /> New task
          </button>
        </div>

        {isLoading ? (
          <Spinner label="Loading tasks..." />
        ) : filtered.length === 0 ? (
          <EmptyState
            title="No tasks here"
            hint="Create a task or generate subtasks from an assignment."
            icon={<CheckSquare className="h-6 w-6" />}
          />
        ) : (
          <ul className="space-y-2">
            {filtered.map((t) => (
              <li
                key={t.id}
                className="flex items-center gap-3 rounded-xl border border-slate-100 p-3 hover:bg-slate-50/60"
              >
                <button
                  onClick={() => toggle.mutate(t)}
                  className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-md border ${
                    t.status === "completed"
                      ? "border-emerald-500 bg-emerald-500 text-white"
                      : "border-slate-300 hover:border-brand-400"
                  }`}
                >
                  {t.status === "completed" && <Check className="h-3.5 w-3.5" />}
                </button>
                <div className="min-w-0 flex-1">
                  <p
                    className={`truncate text-sm font-medium ${
                      t.status === "completed"
                        ? "text-slate-400 line-through"
                        : "text-slate-700"
                    }`}
                  >
                    {t.title}
                  </p>
                  <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
                    <span>{t.estimated_minutes}m</span>
                    {t.deadline && <span>· {fmtDateTime(t.deadline)}</span>}
                    {t.assignment_id && (
                      <span className="inline-flex items-center gap-1 text-violet-500">
                        <Link2 className="h-3 w-3" />
                        {assignmentName(t.assignment_id) ?? "Assignment"}
                      </span>
                    )}
                  </div>
                </div>
                <span
                  className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold ${PRIORITY_STYLES[t.priority]}`}
                >
                  {t.priority}
                </span>
                <button
                  className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100"
                  onClick={() => openEdit(t)}
                >
                  <Pencil className="h-4 w-4" />
                </button>
                <button
                  className="rounded-lg p-1.5 text-rose-400 hover:bg-rose-50"
                  onClick={() => remove.mutate(t.id)}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editing ? "Edit task" : "New task"}
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
            <Field label="Priority">
              <select
                className="input"
                value={form.priority}
                onChange={(e) => setForm({ ...form, priority: e.target.value as Priority })}
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </Field>
            <Field label="Est. minutes" error={errors.estimated_minutes}>
              <input
                type="number"
                min={5}
                step={5}
                className="input"
                value={form.estimated_minutes}
                onChange={(e) =>
                  setForm({ ...form, estimated_minutes: Number(e.target.value) })
                }
              />
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Deadline">
              <input
                type="datetime-local"
                className="input"
                value={form.deadline}
                onChange={(e) => setForm({ ...form, deadline: e.target.value })}
              />
            </Field>
            <Field label="Parent assignment">
              <select
                className="input"
                value={form.assignment_id ?? ""}
                onChange={(e) =>
                  setForm({
                    ...form,
                    assignment_id: e.target.value ? Number(e.target.value) : null,
                  })
                }
              >
                <option value="">None</option>
                {assignments?.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.title}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button className="btn-ghost" onClick={() => setModalOpen(false)}>
              Cancel
            </button>
            <button className="btn-primary" onClick={submit} disabled={save.isPending}>
              {save.isPending ? "Saving..." : editing ? "Save" : "Create"}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
