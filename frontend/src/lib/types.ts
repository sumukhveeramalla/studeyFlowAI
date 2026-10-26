export type Priority = "low" | "medium" | "high";
export type AssignmentStatus = "not_started" | "in_progress" | "completed";
export type TaskStatus = "not_started" | "in_progress" | "completed";
export type EventKind =
  | "class"
  | "exam"
  | "assignment"
  | "study"
  | "personal"
  | "meeting";

export interface Course {
  id: number;
  name: string;
  code: string;
  color: string;
  instructor: string;
}

export interface Assignment {
  id: number;
  title: string;
  description: string;
  due_at: string;
  priority: Priority;
  status: AssignmentStatus;
  estimated_hours: number;
  course_id: number | null;
  completed_at: string | null;
  course?: Course | null;
}

export interface Task {
  id: number;
  title: string;
  priority: Priority;
  estimated_minutes: number;
  deadline: string | null;
  status: TaskStatus;
  order_index: number;
  assignment_id: number | null;
  completed_at: string | null;
}

export interface Exam {
  id: number;
  title: string;
  start_at: string;
  end_at: string;
  topics: string[];
  prep_hours: number;
  priority: Priority;
  prep_progress: number;
  course_id: number | null;
  course?: Course | null;
}

export interface CalendarEvent {
  id: number;
  title: string;
  kind: EventKind;
  start_at: string;
  end_at: string;
  is_fixed: boolean;
  color: string | null;
  location: string;
  task_id: number | null;
  assignment_id: number | null;
  exam_id: number | null;
  source: string;
}

export interface Preferences {
  study_start_hour: number;
  study_end_hour: number;
  session_length_min: number;
  break_min: number;
  available_days: string;
  default_priority: Priority;
  timezone: string;
}

export interface DashboardStats {
  upcoming_assignments: number;
  upcoming_exams: number;
  todays_tasks: number;
  conflicts_resolved: number;
}

export interface StudyProgress {
  label: string;
  completed: number;
  total: number;
  percent: number;
}

export interface Dashboard {
  stats: DashboardStats;
  week_events: CalendarEvent[];
  upcoming_deadlines: Assignment[];
  focus_tasks: Task[];
  progress: StudyProgress[];
}

export interface ScheduleBlock {
  title: string;
  kind: string;
  start_at: string;
  end_at: string;
  task_id: number | null;
  assignment_id: number | null;
  exam_id: number | null;
}

export interface ProposalSummary {
  original: Array<Record<string, unknown>>;
  proposed: Array<Record<string, unknown>>;
  added_count: number;
  moved_count: number;
  removed_count: number;
  infeasible: Array<{
    label: string;
    needed_minutes: number;
    placed_minutes: number;
    reason: string;
  }>;
  new_event: Record<string, unknown> | null;
}

export interface Proposal {
  id: number;
  status: "pending" | "approved" | "rejected";
  reason: string;
  summary: ProposalSummary;
  changes: {
    added: ScheduleBlock[];
    moved: Array<Record<string, unknown>>;
    removed: number[];
  };
  created_at: string;
  decided_at: string | null;
}

export interface AgentStep {
  idx: number;
  agent: string;
  tool: string;
  note: string;
  validation: { ok: boolean; errors: { code: string; message: string }[] } | null;
}

export interface AgentRun {
  id: number;
  user_message: string;
  intent: string;
  status: string;
  mode: string;
  reply: string;
  proposal_id: number | null;
  created_at: string;
  steps: AgentStep[];
}

export interface CreatedItem {
  type: "assignment" | "exam" | "task";
  id: number;
  title: string;
  subtask_count: number;
}

export interface ChatResponse {
  run: AgentRun;
  reply: string;
  mode: string;
  intent: string;
  proposal: Proposal | null;
  conversation_id: number | null;
  awaiting_input: boolean;
  created_items: CreatedItem[];
}

export interface DecomposeResult {
  assignment_id: number;
  mode: "llm" | "demo";
  tasks: Task[];
}

export interface Profile {
  id: number;
  name: string;
  email: string;
  timezone: string;
  llm_enabled: boolean;
}
