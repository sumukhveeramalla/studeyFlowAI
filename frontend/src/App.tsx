import { Route, Routes } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { Analytics } from "./pages/Analytics";
import { AssignmentsPage } from "./pages/Assignments";
import { Assistant } from "./pages/Assistant";
import { CalendarPage } from "./pages/Calendar";
import { Dashboard } from "./pages/Dashboard";
import { ExamsPage } from "./pages/Exams";
import { SettingsPage } from "./pages/Settings";
import { TasksPage } from "./pages/Tasks";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Dashboard />} />
        <Route path="calendar" element={<CalendarPage />} />
        <Route path="assignments" element={<AssignmentsPage />} />
        <Route path="exams" element={<ExamsPage />} />
        <Route path="tasks" element={<TasksPage />} />
        <Route path="assistant" element={<Assistant />} />
        <Route path="analytics" element={<Analytics />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  );
}
