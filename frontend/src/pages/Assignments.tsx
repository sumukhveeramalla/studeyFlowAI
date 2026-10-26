import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BookOpen,
  CheckCircle2,
  Clock,
  Flame,
  Loader2,
  Pencil,
  Plus,
  Search,
  Sparkles,
  Trash2,
  Wand2,
} from "lucide-react";
import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, EmptyState, Field, Modal, Spinner, StatCard } from "../components/ui";
import { Assignments, Courses, Schedule } from "../lib/api";
import {
  PRIORITY_STYLES,
  STATUS_STYLES,
  fmtDate,
  fromInputValue,
  toInputValue,
} from "../lib/format";
import type { Assignment, AssignmentStatus, Priority } from "../lib/types";
import { ProposalPreview } from "../components/agent/ProposalPreview";
import type { Proposal } from "../lib/types";
import { isWithinInterval, parseISO } from "date-fns";

interface AssignmentForm {
  title: string;
  description: string;
  due_at: string;
  priority: Priority;
  status: AssignmentStatus;
  estimated_hours: number;
  course_id: number | null;
}

const EMPTY: AssignmentForm = {
  title: "",
  description: "",
  due_at: toInputValue(),
  priority: "medium",
  status: "not_started",
  estimated_hours: 2,
  course_id: null,
};

export function AssignmentsPage() {
  const qc = useQueryClient();
  const { data: assignments, isLoading } = useQuery({
    queryKey: ["assignments"],
    queryFn: Assignments.list,
  });
  const { data: courses } = useQuery({ queryKey: ["courses"], queryFn: Courses.list });

  const [search, setSearch] = useState("");
  const [courseFilter, setCourseFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [priorityFilter, setPriorityFilter] = useState<string>("all");
  const [sortByDue, setSortByDue] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Assignment | null>(null);
  const [form, setForm] = useState(EMPTY);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [decomposeMsg, setDecomposeMsg] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: (payload: Partial<Assignment>) =>
      editing
        ? Assignments.update(editing.id, payload)
        : Assignments.create(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["assignments"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      setModalOpen(false);
    },
  });
  const remove = useMutation({
    mutationFn: (id: number) => Assignments.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["assignments"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
  const complete = useMutation({
    mutationFn: (a: Assignment) =>
      Assignments.update(a.id, {
        status: a.status === "completed" ? "in_progress" : "completed",
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["assignments"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
  const decompose = useMutation({
    mutationFn: (id: number) => Assignments.decompose(id),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["tasks"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      setDecomposeMsg(
        `Generated ${res.tasks.length} subtasks (${res.mode === "llm" ? "LLM" : "demo"} mode).`
      );
      setTimeout(() => setDecomposeMsg(null), 4000);
    },
  });
  const scheduleOne = useMutation({
    mutationFn: () => Schedule.generate(7),
    onSuccess: (p) => setProposal(p),
  });

  const metrics = useMemo(() => {
    const list = assignments ?? [];
    const now = new Date();
    const weekEnd = new Date(now.getTime() + 7 * 864e5);
    return {
      total: list.length,
      dueThisWeek: list.filter(
        (a) =>
          a.status !== "completed" &&
          isWithinInterval(parseISO(a.due_at), { start: now, end: weekEnd })
      ).length,
      inProgress: list.filter((a) => a.status === "in_progress").length,
      completed: list.filter((a) => a.status === "completed").length,
      highPriority: list.filter(
        (a) => a.priority === "high" && a.status !== "completed"
      ).length,
    };
  }, [assignments]);

  const filtered = useMemo(() => {
    let list = assignments ?? [];
    if (search)
      list = list.filter((a) =>
        a.title.toLowerCase().includes(search.toLowerCase())
      );
    if (courseFilter !== "all")
      list = list.filter((a) => String(a.course_id) === courseFilter);
    if (statusFilter !== "all") list = list.filter((a) => a.status === statusFilter);
    if (priorityFilter !== "all")
      list = list.filter((a) => a.priority === priorityFilter);
    list = [...list].sort((a, b) =>
      sortByDue
        ? parseISO(a.due_at).getTime() - parseISO(b.due_at).getTime()
        : a.title.localeCompare(b.title)
    );
    return list;
  }, [assignments, search, courseFilter, statusFilter, priorityFilter, sortByDue]);

  const charts = useMemo(() => {
    const list = assignments ?? [];
    const priorityData = (["high", "medium", "low"] as Priority[]).map((p) => ({
      name: p,
      value: list.filter((a) => a.priority === p).length,
    }));
    const workloadByCourse = (courses ?? []).map((c) => ({
      name: c.code || c.name.slice(0, 8),
      hours: list
        .filter((a) => a.course_id === c.id && a.status !== "completed")
        .reduce((s, a) => s + a.estimated_hours, 0),
    }));
    const completion = [
      { name: "Completed", value: metrics.completed },
      { name: "Remaining", value: metrics.total - metrics.completed },
    ];
    return { priorityData, workloadByCourse, completion };
  }, [assignments, courses, metrics]);

  function openCreate() {
    setEditing(null);
    setForm(EMPTY);
    setErrors({});
    setModalOpen(true);
  }
  function openEdit(a: Assignment) {
    setEditing(a);
    setForm({
      title: a.title,
      description: a.description,
      due_at: toInputValue(a.due_at),
      priority: a.priority,
      status: a.status,
      estimated_hours: a.estimated_hours,
      course_id: a.course_id,
    });
    setErrors({});
    setModalOpen(true);
  }
  function submit() {
    const e: Record<string, string> = {};
    if (!form.title.trim()) e.title = "Title is required";
    if (!form.due_at) e.due_at = "Due date is required";
    if (form.estimated_hours <= 0) e.estimated_hours = "Must be greater than 0";
    setErrors(e);
    if (Object.keys(e).length) return;
    save.mutate({
      ...form,
      due_at: fromInputValue(form.due_at),
      course_id: form.course_id || null,
    });
  }

  const PIE_COLORS = ["#f43f5e", "#f59e0b", "#10b981"];

  return (
    <div className="space-y-5">
      {/* Metrics */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <StatCard label="Total" value={metrics.total} icon={<BookOpen className="h-5 w-5" />} />
        <StatCard
          label="Due This Week"
          value={metrics.dueThisWeek}
          icon={<Clock className="h-5 w-5" />}
          accent="text-amber-600 bg-amber-50"
        />
        <StatCard
          label="In Progress"
          value={metrics.inProgress}
          icon={<Loader2 className="h-5 w-5" />}
          accent="text-brand-600 bg-brand-50"
        />
        <StatCard
          label="Completed"
          value={metrics.completed}
          icon={<CheckCircle2 className="h-5 w-5" />}
          accent="text-emerald-600 bg-emerald-50"
        />
        <StatCard
          label="High Priority"
          value={metrics.highPriority}
          icon={<Flame className="h-5 w-5" />}
          accent="text-rose-600 bg-rose-50"
        />
      </div>

      {decomposeMsg && (
        <div className="rounded-xl border border-emerald-100 bg-emerald-50 px-4 py-2 text-sm text-emerald-700">
          {decomposeMsg}
        </div>
      )}

      {proposal && (
        <ProposalPreview proposal={proposal} onDecided={() => setProposal(null)} />
      )}

      {/* Table + controls */}
      <Card>
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <div className="relative flex-1 min-w-[180px]">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input
              className="input pl-9"
              placeholder="Search assignments..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <select
            className="input w-auto"
            value={courseFilter}
            onChange={(e) => setCourseFilter(e.target.value)}
          >
            <option value="all">All courses</option>
            {courses?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <select
            className="input w-auto"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="all">All status</option>
            <option value="not_started">Not started</option>
            <option value="in_progress">In progress</option>
            <option value="completed">Completed</option>
          </select>
          <select
            className="input w-auto"
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value)}
          >
            <option value="all">All priority</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
          <button className="btn-ghost" onClick={() => setSortByDue((s) => !s)}>
            Sort: {sortByDue ? "Due date" : "Name"}
          </button>
          <button className="btn-primary" onClick={openCreate}>
            <Plus className="h-4 w-4" /> New
          </button>
        </div>

        {isLoading ? (
          <Spinner label="Loading assignments..." />
        ) : filtered.length === 0 ? (
          <EmptyState
            title="No assignments found"
            hint="Create one or adjust your filters."
            action={
              <button className="btn-primary" onClick={openCreate}>
                <Plus className="h-4 w-4" /> New assignment
              </button>
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-left text-xs uppercase text-slate-400">
                  <th className="pb-2 font-semibold">Assignment</th>
                  <th className="pb-2 font-semibold">Course</th>
                  <th className="pb-2 font-semibold">Due</th>
                  <th className="pb-2 font-semibold">Priority</th>
                  <th className="pb-2 font-semibold">Status</th>
                  <th className="pb-2 font-semibold">Est.</th>
                  <th className="pb-2 text-right font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((a) => (
                  <tr key={a.id} className="border-b border-slate-50 hover:bg-slate-50/50">
                    <td className="py-2.5 pr-2">
                      <p className="font-medium text-slate-700">{a.title}</p>
                      {a.description && (
                        <p className="max-w-xs truncate text-xs text-slate-400">
                          {a.description}
                        </p>
                      )}
                    </td>
                    <td className="py-2.5 pr-2 text-slate-500">
                      {a.course?.name ?? "—"}
                    </td>
                    <td className="py-2.5 pr-2 text-slate-500">{fmtDate(a.due_at)}</td>
                    <td className="py-2.5 pr-2">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-semibold ${PRIORITY_STYLES[a.priority]}`}
                      >
                        {a.priority}
                      </span>
                    </td>
                    <td className="py-2.5 pr-2">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-semibold capitalize ${STATUS_STYLES[a.status]}`}
                      >
                        {a.status.replace("_", " ")}
                      </span>
                    </td>
                    <td className="py-2.5 pr-2 text-slate-500">{a.estimated_hours}h</td>
                    <td className="py-2.5">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          title="Generate subtasks with AI"
                          className="rounded-lg p-1.5 text-violet-500 hover:bg-violet-50"
                          onClick={() => decompose.mutate(a.id)}
                          disabled={decompose.isPending}
                        >
                          <Wand2 className="h-4 w-4" />
                        </button>
                        <button
                          title="Mark complete"
                          className="rounded-lg p-1.5 text-emerald-500 hover:bg-emerald-50"
                          onClick={() => complete.mutate(a)}
                        >
                          <CheckCircle2 className="h-4 w-4" />
                        </button>
                        <button
                          title="Edit"
                          className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100"
                          onClick={() => openEdit(a)}
                        >
                          <Pencil className="h-4 w-4" />
                        </button>
                        <button
                          title="Delete"
                          className="rounded-lg p-1.5 text-rose-400 hover:bg-rose-50"
                          onClick={() => remove.mutate(a.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="mt-4 flex items-center justify-between border-t border-slate-100 pt-3">
          <p className="text-sm text-slate-400">
            Tip: use the AI wand to break an assignment into tasks.
          </p>
          <button
            className="btn-ghost"
            onClick={() => scheduleOne.mutate()}
            disabled={scheduleOne.isPending}
          >
            <Sparkles className="h-4 w-4" /> Generate study schedule
          </button>
        </div>
      </Card>

      {/* Analytics */}
      <div className="grid gap-5 lg:grid-cols-3">
        <Card>
          <h3 className="mb-3 text-base font-semibold text-slate-800">Completion</h3>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie
                data={charts.completion}
                dataKey="value"
                innerRadius={50}
                outerRadius={75}
                paddingAngle={2}
              >
                <Cell fill="#10b981" />
                <Cell fill="#e2e8f0" />
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
          <p className="text-center text-sm text-slate-500">
            {metrics.completed} of {metrics.total} completed
          </p>
        </Card>
        <Card>
          <h3 className="mb-3 text-base font-semibold text-slate-800">
            Weekly Workload (hrs)
          </h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={charts.workloadByCourse}>
              <XAxis dataKey="name" fontSize={11} tickLine={false} axisLine={false} />
              <YAxis fontSize={11} tickLine={false} axisLine={false} />
              <Tooltip />
              <Bar dataKey="hours" fill="#2563eb" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
        <Card>
          <h3 className="mb-3 text-base font-semibold text-slate-800">
            Priority Distribution
          </h3>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={charts.priorityData} dataKey="value" outerRadius={75} label>
                {charts.priorityData.map((_, i) => (
                  <Cell key={i} fill={PIE_COLORS[i]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {/* Create / edit modal */}
      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editing ? "Edit assignment" : "New assignment"}
      >
        <div className="space-y-3">
          <Field label="Title" error={errors.title}>
            <input
              className="input"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
            />
          </Field>
          <Field label="Description">
            <textarea
              className="input"
              rows={2}
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Due date" error={errors.due_at}>
              <input
                type="datetime-local"
                className="input"
                value={form.due_at}
                onChange={(e) => setForm({ ...form, due_at: e.target.value })}
              />
            </Field>
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
          </div>
          <div className="grid grid-cols-3 gap-3">
            <Field label="Priority">
              <select
                className="input"
                value={form.priority}
                onChange={(e) =>
                  setForm({ ...form, priority: e.target.value as Priority })
                }
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </Field>
            <Field label="Status">
              <select
                className="input"
                value={form.status}
                onChange={(e) =>
                  setForm({ ...form, status: e.target.value as typeof form.status })
                }
              >
                <option value="not_started">Not started</option>
                <option value="in_progress">In progress</option>
                <option value="completed">Completed</option>
              </select>
            </Field>
            <Field label="Est. hours" error={errors.estimated_hours}>
              <input
                type="number"
                min={0.5}
                step={0.5}
                className="input"
                value={form.estimated_hours}
                onChange={(e) =>
                  setForm({ ...form, estimated_hours: Number(e.target.value) })
                }
              />
            </Field>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button className="btn-ghost" onClick={() => setModalOpen(false)}>
              Cancel
            </button>
            <button className="btn-primary" onClick={submit} disabled={save.isPending}>
              {save.isPending ? "Saving..." : editing ? "Save changes" : "Create"}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
