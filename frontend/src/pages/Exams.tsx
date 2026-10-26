import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, GraduationCap, Pencil, Plus, Sparkles, Trash2 } from "lucide-react";
import { useState } from "react";
import { ProposalPreview } from "../components/agent/ProposalPreview";
import { Card, EmptyState, Field, Modal, Spinner } from "../components/ui";
import { Courses, Exams, Schedule } from "../lib/api";
import {
  PRIORITY_STYLES,
  fmtDateTime,
  fmtRelative,
  fromInputValue,
  toInputValue,
} from "../lib/format";
import type { Exam, Priority, Proposal } from "../lib/types";

const EMPTY = {
  title: "",
  start_at: toInputValue(),
  end_at: toInputValue(new Date(Date.now() + 2 * 3600000).toISOString()),
  topics: "",
  prep_hours: 6,
  priority: "high" as Priority,
  prep_progress: 0,
  course_id: null as number | null,
};

export function ExamsPage() {
  const qc = useQueryClient();
  const { data: exams, isLoading } = useQuery({ queryKey: ["exams"], queryFn: Exams.list });
  const { data: courses } = useQuery({ queryKey: ["courses"], queryFn: Courses.list });
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Exam | null>(null);
  const [form, setForm] = useState(EMPTY);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [proposal, setProposal] = useState<Proposal | null>(null);

  const save = useMutation({
    mutationFn: (payload: Partial<Exam>) =>
      editing ? Exams.update(editing.id, payload) : Exams.create(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["exams"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      setModalOpen(false);
    },
  });
  const remove = useMutation({
    mutationFn: (id: number) => Exams.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["exams"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
  const plan = useMutation({
    mutationFn: () => Schedule.generate(14),
    onSuccess: (p) => setProposal(p),
  });

  function openCreate() {
    setEditing(null);
    setForm(EMPTY);
    setErrors({});
    setModalOpen(true);
  }
  function openEdit(e: Exam) {
    setEditing(e);
    setForm({
      title: e.title,
      start_at: toInputValue(e.start_at),
      end_at: toInputValue(e.end_at),
      topics: e.topics.join(", "),
      prep_hours: e.prep_hours,
      priority: e.priority,
      prep_progress: e.prep_progress,
      course_id: e.course_id,
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
      topics: form.topics
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean),
      course_id: form.course_id || null,
    });
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-500">
          Track exams and distribute preparation across available days.
        </p>
        <div className="flex gap-2">
          <button className="btn-ghost" onClick={() => plan.mutate()} disabled={plan.isPending}>
            <Sparkles className="h-4 w-4" /> Build prep plan
          </button>
          <button className="btn-primary" onClick={openCreate}>
            <Plus className="h-4 w-4" /> New exam
          </button>
        </div>
      </div>

      {proposal && (
        <ProposalPreview proposal={proposal} onDecided={() => setProposal(null)} />
      )}

      {isLoading ? (
        <Spinner label="Loading exams..." />
      ) : !exams?.length ? (
        <Card>
          <EmptyState
            title="No exams yet"
            hint="Add an exam to plan your preparation."
            icon={<GraduationCap className="h-6 w-6" />}
          />
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {exams.map((e) => (
            <Card key={e.id} className="transition-shadow hover:shadow-cardhover">
              <div className="mb-2 flex items-start justify-between">
                <div>
                  <h3 className="font-semibold text-slate-800">{e.title}</h3>
                  <p className="text-xs text-slate-400">{e.course?.name ?? "—"}</p>
                </div>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-semibold ${PRIORITY_STYLES[e.priority]}`}
                >
                  {e.priority}
                </span>
              </div>
              <div className="mb-3 flex items-center gap-1.5 text-sm text-slate-600">
                <CalendarClock className="h-4 w-4 text-slate-400" />
                {fmtDateTime(e.start_at)}
                <span className="text-xs text-slate-400">({fmtRelative(e.start_at)})</span>
              </div>
              {e.topics.length > 0 && (
                <div className="mb-3 flex flex-wrap gap-1">
                  {e.topics.map((t) => (
                    <span
                      key={t}
                      className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600"
                    >
                      {t}
                    </span>
                  ))}
                </div>
              )}
              <div className="mb-1 flex items-center justify-between text-xs text-slate-500">
                <span>Prep progress ({e.prep_hours}h)</span>
                <span className="font-semibold">{Math.round(e.prep_progress * 100)}%</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                <div
                  className="h-full rounded-full bg-emerald-500"
                  style={{ width: `${e.prep_progress * 100}%` }}
                />
              </div>
              <div className="mt-3 flex justify-end gap-1">
                <button
                  className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100"
                  onClick={() => openEdit(e)}
                >
                  <Pencil className="h-4 w-4" />
                </button>
                <button
                  className="rounded-lg p-1.5 text-rose-400 hover:bg-rose-50"
                  onClick={() => remove.mutate(e.id)}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editing ? "Edit exam" : "New exam"}
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
          <Field label="Topics (comma separated)">
            <input
              className="input"
              value={form.topics}
              onChange={(e) => setForm({ ...form, topics: e.target.value })}
            />
          </Field>
          <div className="grid grid-cols-3 gap-3">
            <Field label="Prep hours">
              <input
                type="number"
                min={0}
                step={0.5}
                className="input"
                value={form.prep_hours}
                onChange={(e) => setForm({ ...form, prep_hours: Number(e.target.value) })}
              />
            </Field>
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
            <Field label="Progress %">
              <input
                type="number"
                min={0}
                max={100}
                className="input"
                value={Math.round(form.prep_progress * 100)}
                onChange={(e) =>
                  setForm({ ...form, prep_progress: Number(e.target.value) / 100 })
                }
              />
            </Field>
          </div>
          <Field label="Course">
            <select
              className="input"
              value={form.course_id ?? ""}
              onChange={(e) =>
                setForm({
                  ...form,
                  course_id: e.target.value ? Number(e.target.value) : null,
                })
              }
            >
              <option value="">No course</option>
              {courses?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </Field>
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
