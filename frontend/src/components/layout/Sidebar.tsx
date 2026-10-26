import clsx from "clsx";
import {
  BarChart3,
  BookOpen,
  Bot,
  Calendar,
  CheckSquare,
  GraduationCap,
  LayoutDashboard,
  Settings,
  Sparkles,
} from "lucide-react";
import { NavLink } from "react-router-dom";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/calendar", label: "Calendar", icon: Calendar },
  { to: "/assignments", label: "Assignments", icon: BookOpen },
  { to: "/exams", label: "Exams", icon: GraduationCap },
  { to: "/tasks", label: "Tasks", icon: CheckSquare },
  { to: "/assistant", label: "AI Assistant", icon: Bot },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <aside className="flex h-full w-64 flex-col border-r border-slate-100 bg-white">
      <div className="flex items-center gap-2.5 px-6 py-6">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-600 text-white">
          <Sparkles className="h-5 w-5" />
        </div>
        <div>
          <p className="text-base font-bold leading-tight text-slate-800">
            StudyFlow <span className="text-brand-600">AI</span>
          </p>
          <p className="text-[11px] text-slate-400">Plan Smarter. Study Better.</p>
        </div>
      </div>

      <nav className="flex-1 space-y-1 px-3">
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            onClick={onNavigate}
            className={({ isActive }) =>
              clsx(
                "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors",
                isActive
                  ? "bg-brand-50 text-brand-700"
                  : "text-slate-500 hover:bg-slate-50 hover:text-slate-700"
              )
            }
          >
            <Icon className="h-[18px] w-[18px]" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="m-3 rounded-2xl bg-gradient-to-br from-brand-600 to-brand-700 p-4 text-white">
        <p className="text-sm font-semibold">Need a plan?</p>
        <p className="mt-1 text-xs text-brand-100">
          Ask the AI assistant to build a conflict-free study schedule.
        </p>
      </div>
    </aside>
  );
}
