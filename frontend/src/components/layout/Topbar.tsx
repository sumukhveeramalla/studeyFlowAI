import { useQuery } from "@tanstack/react-query";
import { Bell, Menu, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Assignments, Me } from "../../lib/api";

export function Topbar({
  title,
  onMenu,
}: {
  title: string;
  onMenu: () => void;
}) {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const { data: profile } = useQuery({ queryKey: ["profile"], queryFn: Me.get });
  const { data: assignments } = useQuery({
    queryKey: ["assignments"],
    queryFn: Assignments.list,
  });

  const results = useMemo(() => {
    if (!q.trim() || !assignments) return [];
    return assignments
      .filter((a) => a.title.toLowerCase().includes(q.toLowerCase()))
      .slice(0, 5);
  }, [q, assignments]);

  const initials = (profile?.name ?? "A J")
    .split(" ")
    .map((s) => s[0])
    .join("")
    .slice(0, 2);

  return (
    <header className="sticky top-0 z-30 flex items-center gap-3 border-b border-slate-100 bg-canvas/80 px-4 py-3 backdrop-blur md:px-8">
      <button
        className="rounded-lg p-2 text-slate-500 hover:bg-white lg:hidden"
        onClick={onMenu}
        aria-label="Open menu"
      >
        <Menu className="h-5 w-5" />
      </button>
      <h1 className="text-xl font-bold text-slate-800">{title}</h1>

      <div className="relative ml-auto hidden w-72 md:block">
        <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
        <input
          className="input pl-9"
          placeholder="Search assignments..."
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
        />
        {open && results.length > 0 && (
          <div className="absolute mt-1 w-full overflow-hidden rounded-xl border border-slate-100 bg-white shadow-cardhover">
            {results.map((a) => (
              <button
                key={a.id}
                className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-slate-50"
                onMouseDown={() => navigate("/assignments")}
              >
                <span className="truncate text-slate-700">{a.title}</span>
                <span className="text-xs capitalize text-slate-400">{a.priority}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      <button
        className="relative rounded-xl border border-slate-200 bg-white p-2 text-slate-500 hover:bg-slate-50"
        aria-label="Notifications"
      >
        <Bell className="h-5 w-5" />
        <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-rose-500" />
      </button>

      <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white py-1.5 pl-1.5 pr-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-sm font-bold text-white">
          {initials}
        </div>
        <div className="hidden sm:block">
          <p className="text-sm font-semibold leading-tight text-slate-700">
            {profile?.name ?? "Student"}
          </p>
          <p className="text-[11px] text-slate-400">
            {profile?.llm_enabled ? "LLM mode" : "Demo mode"}
          </p>
        </div>
      </div>
    </header>
  );
}
