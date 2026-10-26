import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { addDays, format, isSameDay, parseISO, startOfWeek } from "date-fns";
import { Card, Spinner, StatCard } from "../components/ui";
import { Assignments, Events, Tasks } from "../lib/api";
import { BarChart3, CheckCircle2, Clock, Target } from "lucide-react";

export function Analytics() {
  const { data: assignments, isLoading: la } = useQuery({
    queryKey: ["assignments"],
    queryFn: Assignments.list,
  });
  const { data: tasks, isLoading: lt } = useQuery({
    queryKey: ["tasks"],
    queryFn: Tasks.list,
  });
  const { data: events } = useQuery({ queryKey: ["events"], queryFn: Events.list });

  const data = useMemo(() => {
    const a = assignments ?? [];
    const t = tasks ?? [];
    const e = events ?? [];

    const priorityData = (["high", "medium", "low"] as const).map((p) => ({
      name: p,
      value: a.filter((x) => x.priority === p).length,
    }));

    const statusData = [
      { name: "Not started", value: a.filter((x) => x.status === "not_started").length },
      { name: "In progress", value: a.filter((x) => x.status === "in_progress").length },
      { name: "Completed", value: a.filter((x) => x.status === "completed").length },
    ];

    const monday = startOfWeek(new Date(), { weekStartsOn: 1 });
    const workload = Array.from({ length: 7 }, (_, i) => {
      const day = addDays(monday, i);
      const studyMin = e
        .filter((ev) => ev.kind === "study" && isSameDay(parseISO(ev.start_at), day))
        .reduce(
          (s, ev) =>
            s + (parseISO(ev.end_at).getTime() - parseISO(ev.start_at).getTime()) / 60000,
          0
        );
      return { day: format(day, "EEE"), hours: +(studyMin / 60).toFixed(1) };
    });

    const completedTasks = t.filter((x) => x.status === "completed").length;
    const taskCompletion = t.length ? Math.round((completedTasks / t.length) * 100) : 0;
    const totalStudyH =
      workload.reduce((s, w) => s + w.hours, 0);

    return { priorityData, statusData, workload, taskCompletion, completedTasks, totalStudyH };
  }, [assignments, tasks, events]);

  const PIE = ["#f43f5e", "#f59e0b", "#10b981"];
  const STATUS = ["#94a3b8", "#2563eb", "#10b981"];

  if (la || lt) return <Spinner label="Crunching your numbers..." />;

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label="Task Completion"
          value={`${data.taskCompletion}%`}
          icon={<Target className="h-5 w-5" />}
        />
        <StatCard
          label="Tasks Done"
          value={data.completedTasks}
          icon={<CheckCircle2 className="h-5 w-5" />}
          accent="text-emerald-600 bg-emerald-50"
        />
        <StatCard
          label="Study Hours (wk)"
          value={data.totalStudyH}
          icon={<Clock className="h-5 w-5" />}
          accent="text-amber-600 bg-amber-50"
        />
        <StatCard
          label="Assignments"
          value={assignments?.length ?? 0}
          icon={<BarChart3 className="h-5 w-5" />}
          accent="text-violet-600 bg-violet-50"
        />
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <h3 className="mb-3 text-base font-semibold text-slate-800">
            Weekly Study Hours
          </h3>
          <ResponsiveContainer width="100%" height={250}>
            <AreaChart data={data.workload}>
              <defs>
                <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#2563eb" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#2563eb" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="day" fontSize={12} tickLine={false} axisLine={false} />
              <YAxis fontSize={12} tickLine={false} axisLine={false} />
              <Tooltip />
              <Area
                type="monotone"
                dataKey="hours"
                stroke="#2563eb"
                strokeWidth={2}
                fill="url(#g)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </Card>

        <Card>
          <h3 className="mb-3 text-base font-semibold text-slate-800">
            Assignment Status
          </h3>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie
                data={data.statusData}
                dataKey="value"
                nameKey="name"
                innerRadius={55}
                outerRadius={85}
                paddingAngle={2}
              >
                {data.statusData.map((_, i) => (
                  <Cell key={i} fill={STATUS[i]} />
                ))}
              </Pie>
              <Legend />
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </Card>

        <Card>
          <h3 className="mb-3 text-base font-semibold text-slate-800">
            Priority Distribution
          </h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={data.priorityData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="name" fontSize={12} tickLine={false} axisLine={false} />
              <YAxis fontSize={12} tickLine={false} axisLine={false} />
              <Tooltip />
              <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                {data.priorityData.map((_, i) => (
                  <Cell key={i} fill={PIE[i]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card>
          <h3 className="mb-3 text-base font-semibold text-slate-800">
            Workload Trend
          </h3>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={data.workload}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="day" fontSize={12} tickLine={false} axisLine={false} />
              <YAxis fontSize={12} tickLine={false} axisLine={false} />
              <Tooltip />
              <Line
                type="monotone"
                dataKey="hours"
                stroke="#10b981"
                strokeWidth={2}
                dot={{ r: 3 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      </div>
    </div>
  );
}
