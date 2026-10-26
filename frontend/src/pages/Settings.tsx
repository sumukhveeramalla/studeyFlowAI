import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Plus, Save, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Card, Field, Spinner } from "../components/ui";
import { Courses, Me, Prefs } from "../lib/api";
import type { Course, Preferences, Priority } from "../lib/types";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function SettingsPage() {
  const qc = useQueryClient();
  const { data: prefs, isLoading } = useQuery({ queryKey: ["prefs"], queryFn: Prefs.get });
  const { data: profile } = useQuery({ queryKey: ["profile"], queryFn: Me.get });
  const { data: courses } = useQuery({ queryKey: ["courses"], queryFn: Courses.list });

  const [form, setForm] = useState<Preferences | null>(null);
  const [saved, setSaved] = useState(false);
  const [newCourse, setNewCourse] = useState({ name: "", code: "", color: "#2563eb" });

  useEffect(() => {
    if (prefs) setForm(prefs);
  }, [prefs]);

  const save = useMutation({
    mutationFn: (p: Partial<Preferences>) => Prefs.update(p),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["prefs"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    },
  });
  const addCourse = useMutation({
    mutationFn: (c: Partial<Course>) => Courses.create(c),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["courses"] });
      setNewCourse({ name: "", code: "", color: "#2563eb" });
    },
  });
  const delCourse = useMutation({
    mutationFn: (id: number) => Courses.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["courses"] }),
  });

  if (isLoading || !form) return <Spinner label="Loading settings..." />;

  const days = form.available_days.split(",").filter(Boolean).map(Number);
  const toggleDay = (i: number) => {
    const set = new Set(days);
    set.has(i) ? set.delete(i) : set.add(i);
    setForm({
      ...form,
      available_days: Array.from(set).sort((a, b) => a - b).join(","),
    });
  };

  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <Card>
        <h2 className="mb-1 text-lg font-semibold text-slate-800">Study Preferences</h2>
        <p className="mb-4 text-sm text-slate-400">
          The scheduling engine uses these when generating study blocks.
        </p>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <Field label="Study start hour (24h)">
              <input
                type="number"
                min={0}
                max={23}
                className="input"
                value={form.study_start_hour}
                onChange={(e) =>
                  setForm({ ...form, study_start_hour: Number(e.target.value) })
                }
              />
            </Field>
            <Field label="Study end hour (24h)">
              <input
                type="number"
                min={1}
                max={24}
                className="input"
                value={form.study_end_hour}
                onChange={(e) =>
                  setForm({ ...form, study_end_hour: Number(e.target.value) })
                }
              />
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Session length (min)">
              <input
                type="number"
                min={15}
                step={15}
                className="input"
                value={form.session_length_min}
                onChange={(e) =>
                  setForm({ ...form, session_length_min: Number(e.target.value) })
                }
              />
            </Field>
            <Field label="Break (min)">
              <input
                type="number"
                min={0}
                step={5}
                className="input"
                value={form.break_min}
                onChange={(e) => setForm({ ...form, break_min: Number(e.target.value) })}
              />
            </Field>
          </div>
          <Field label="Available days">
            <div className="flex flex-wrap gap-1.5">
              {DAYS.map((d, i) => (
                <button
                  key={d}
                  onClick={() => toggleDay(i)}
                  className={`rounded-lg px-3 py-1.5 text-sm font-medium ${
                    days.includes(i)
                      ? "bg-brand-600 text-white"
                      : "bg-slate-100 text-slate-500"
                  }`}
                >
                  {d}
                </button>
              ))}
            </div>
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Default priority">
              <select
                className="input"
                value={form.default_priority}
                onChange={(e) =>
                  setForm({ ...form, default_priority: e.target.value as Priority })
                }
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </Field>
            <Field label="Time zone">
              <input
                className="input"
                value={form.timezone}
                onChange={(e) => setForm({ ...form, timezone: e.target.value })}
              />
            </Field>
          </div>
          <button
            className="btn-primary w-full"
            onClick={() => save.mutate(form)}
            disabled={save.isPending}
          >
            {saved ? (
              <>
                <Check className="h-4 w-4" /> Saved
              </>
            ) : (
              <>
                <Save className="h-4 w-4" /> Save preferences
              </>
            )}
          </button>
        </div>
      </Card>

      <div className="space-y-5">
        <Card>
          <h2 className="mb-1 text-lg font-semibold text-slate-800">Profile</h2>
          <p className="mb-4 text-sm text-slate-400">Local demo student profile.</p>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-slate-500">Name</span>
              <span className="font-medium text-slate-700">{profile?.name}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Email</span>
              <span className="font-medium text-slate-700">{profile?.email}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">AI mode</span>
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                  profile?.llm_enabled
                    ? "bg-brand-50 text-brand-700"
                    : "bg-slate-100 text-slate-500"
                }`}
              >
                {profile?.llm_enabled ? "LLM connected" : "Demo (deterministic)"}
              </span>
            </div>
          </div>
        </Card>

        <Card>
          <h2 className="mb-3 text-lg font-semibold text-slate-800">Courses</h2>
          <div className="mb-3 space-y-2">
            {courses?.map((c) => (
              <div
                key={c.id}
                className="flex items-center gap-2 rounded-xl border border-slate-100 p-2.5"
              >
                <span
                  className="h-4 w-4 rounded-full"
                  style={{ backgroundColor: c.color }}
                />
                <div className="flex-1">
                  <p className="text-sm font-medium text-slate-700">{c.name}</p>
                  <p className="text-xs text-slate-400">{c.code}</p>
                </div>
                <button
                  className="rounded-lg p-1.5 text-rose-400 hover:bg-rose-50"
                  onClick={() => delCourse.mutate(c.id)}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
          <div className="flex items-end gap-2">
            <div className="flex-1">
              <Field label="New course">
                <input
                  className="input"
                  placeholder="Course name"
                  value={newCourse.name}
                  onChange={(e) =>
                    setNewCourse({ ...newCourse, name: e.target.value })
                  }
                />
              </Field>
            </div>
            <input
              className="input w-24"
              placeholder="Code"
              value={newCourse.code}
              onChange={(e) => setNewCourse({ ...newCourse, code: e.target.value })}
            />
            <input
              type="color"
              className="h-10 w-12 cursor-pointer rounded-lg border border-slate-200"
              value={newCourse.color}
              onChange={(e) => setNewCourse({ ...newCourse, color: e.target.value })}
            />
            <button
              className="btn-primary"
              onClick={() => newCourse.name && addCourse.mutate(newCourse)}
              disabled={addCourse.isPending}
            >
              <Plus className="h-4 w-4" />
            </button>
          </div>
        </Card>
      </div>
    </div>
  );
}
