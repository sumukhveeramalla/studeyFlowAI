import axios from "axios";
import type {
  Assignment,
  ChatResponse,
  Course,
  Dashboard,
  DecomposeResult,
  CalendarEvent,
  Exam,
  Preferences,
  Profile,
  Proposal,
  Task,
} from "./types";

export const http = axios.create({ baseURL: "/api", timeout: 60000 });

// ---- Courses ----
export const Courses = {
  list: () => http.get<Course[]>("/courses").then((r) => r.data),
  create: (data: Partial<Course>) =>
    http.post<Course>("/courses", data).then((r) => r.data),
  update: (id: number, data: Partial<Course>) =>
    http.put<Course>(`/courses/${id}`, data).then((r) => r.data),
  remove: (id: number) => http.delete(`/courses/${id}`).then((r) => r.data),
};

// ---- Assignments ----
export const Assignments = {
  list: () => http.get<Assignment[]>("/assignments").then((r) => r.data),
  create: (data: Partial<Assignment>) =>
    http.post<Assignment>("/assignments", data).then((r) => r.data),
  update: (id: number, data: Partial<Assignment>) =>
    http.put<Assignment>(`/assignments/${id}`, data).then((r) => r.data),
  remove: (id: number) => http.delete(`/assignments/${id}`).then((r) => r.data),
  decompose: (id: number) =>
    http.post<DecomposeResult>(`/assignments/${id}/decompose`).then((r) => r.data),
};

// ---- Tasks ----
export const Tasks = {
  list: () => http.get<Task[]>("/tasks").then((r) => r.data),
  create: (data: Partial<Task>) =>
    http.post<Task>("/tasks", data).then((r) => r.data),
  update: (id: number, data: Partial<Task>) =>
    http.put<Task>(`/tasks/${id}`, data).then((r) => r.data),
  remove: (id: number) => http.delete(`/tasks/${id}`).then((r) => r.data),
};

// ---- Exams ----
export const Exams = {
  list: () => http.get<Exam[]>("/exams").then((r) => r.data),
  create: (data: Partial<Exam>) =>
    http.post<Exam>("/exams", data).then((r) => r.data),
  update: (id: number, data: Partial<Exam>) =>
    http.put<Exam>(`/exams/${id}`, data).then((r) => r.data),
  remove: (id: number) => http.delete(`/exams/${id}`).then((r) => r.data),
};

// ---- Events ----
export const Events = {
  list: () => http.get<CalendarEvent[]>("/events").then((r) => r.data),
  create: (data: Partial<CalendarEvent>) =>
    http.post<CalendarEvent>("/events", data).then((r) => r.data),
  update: (id: number, data: Partial<CalendarEvent>) =>
    http.put<CalendarEvent>(`/events/${id}`, data).then((r) => r.data),
  remove: (id: number) => http.delete(`/events/${id}`).then((r) => r.data),
};

// ---- Dashboard / preferences / profile ----
export const Dash = {
  get: (weekOffset = 0) =>
    http.get<Dashboard>(`/dashboard?week_offset=${weekOffset}`).then((r) => r.data),
};

export const Prefs = {
  get: () => http.get<Preferences>("/preferences").then((r) => r.data),
  update: (data: Partial<Preferences>) =>
    http.put<Preferences>("/preferences", data).then((r) => r.data),
};

export const Me = {
  get: () => http.get<Profile>("/profile").then((r) => r.data),
};

// ---- Scheduling / proposals ----
export const Schedule = {
  generate: (horizon_days = 7) =>
    http.post<Proposal>("/schedule/generate", { horizon_days }).then((r) => r.data),
  replan: (payload: {
    new_event?: {
      title: string;
      kind: string;
      start_at: string;
      end_at: string;
    };
    horizon_days?: number;
  }) => http.post<Proposal>("/schedule/replan", payload).then((r) => r.data),
};

export const Proposals = {
  list: () => http.get<Proposal[]>("/proposals").then((r) => r.data),
  get: (id: number) => http.get<Proposal>(`/proposals/${id}`).then((r) => r.data),
  approve: (id: number) =>
    http.post<Proposal>(`/proposals/${id}/approve`).then((r) => r.data),
  reject: (id: number) =>
    http.post<Proposal>(`/proposals/${id}/reject`).then((r) => r.data),
};

// ---- Chat / agents ----
export const Chat = {
  send: (message: string, conversationId?: number | null) =>
    http
      .post<ChatResponse>("/chat", {
        message,
        conversation_id: conversationId ?? null,
      })
      .then((r) => r.data),
};

export const Agents = {
  runs: () => http.get<ChatResponse["run"][]>("/agents/runs").then((r) => r.data),
};
