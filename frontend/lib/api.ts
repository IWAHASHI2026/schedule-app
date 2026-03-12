const API_BASE = "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `API error: ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// ---- Employees ----
export interface JobType {
  id: number;
  name: string;
  color: string | null;
}

export interface Employee {
  id: number;
  name: string;
  employment_type: string;  // "full_time" or "dependent"
  sort_order: number;
  job_types: JobType[];
}

export const getEmployees = () => request<Employee[]>("/employees");
export const createEmployee = (name: string, employment_type: string = "full_time") =>
  request<Employee>("/employees", { method: "POST", body: JSON.stringify({ name, employment_type }) });
export const updateEmployee = (id: number, name: string, employment_type: string = "full_time") =>
  request<Employee>(`/employees/${id}`, { method: "PUT", body: JSON.stringify({ name, employment_type }) });
export const deleteEmployee = (id: number) =>
  request<void>(`/employees/${id}`, { method: "DELETE" });
export const updateEmployeeJobTypes = (id: number, job_type_ids: number[]) =>
  request<Employee>(`/employees/${id}/job-types`, {
    method: "PUT",
    body: JSON.stringify({ job_type_ids }),
  });
export const updateEmployeeFull = (id: number, name: string, employment_type: string, job_type_ids: number[]) =>
  request<Employee>(`/employees/${id}/full`, {
    method: "PUT",
    body: JSON.stringify({ name, employment_type, job_type_ids }),
  });
export const reorderEmployees = (employee_ids: number[]) =>
  request<Employee[]>("/employees/reorder", {
    method: "PUT",
    body: JSON.stringify({ employee_ids }),
  });

// ---- Job Types ----
export const getJobTypes = () => request<JobType[]>("/job-types");

export const getJobTypeAbbr = (name: string | null | undefined): string => {
  if (!name) return "";
  if (name === "lkデータ") return "Lデ";
  if (name === "uv/cpデータ") return "Uデ";
  if (name === "手紙") return "手";
  return name.charAt(0);
};

// ---- Shift Requests ----
export interface RequestDetail {
  id: number;
  date: string;
  period: string;  // "am", "pm", or "all_day"
}

export interface ShiftRequest {
  id: number;
  employee_id: number;
  employee_name: string;
  target_month: string;
  requested_work_days: string | null;  // "1"-"23" or "max"
  weekly_work_day_limit: number | null;
  note: string | null;
  details: RequestDetail[];
}

export interface RequestStatus {
  employee_id: number;
  employee_name: string;
  has_request: boolean;
}

export const getRequests = (month: string) =>
  request<ShiftRequest[]>(`/requests?month=${month}`);
export const getRequestStatus = (month: string) =>
  request<RequestStatus[]>(`/requests/status?month=${month}`);
export const getEmployeeRequest = (employeeId: number, month: string) =>
  request<ShiftRequest>(`/requests/${employeeId}?month=${month}`);
export const upsertRequest = (data: {
  employee_id: number;
  target_month: string;
  requested_work_days?: string | null;  // "1"-"23" or "max"
  weekly_work_day_limit?: number | null;
  note?: string | null;
  days_off: { date: string; period: string }[];
}) => request<ShiftRequest>("/requests", { method: "POST", body: JSON.stringify(data) });
export const clearAllRequests = (month: string) =>
  request<{ status: string; cleared: number }>("/requests/clear-all", {
    method: "POST", body: JSON.stringify({ month }),
  });
export interface RequestBackupInfo {
  employee_id: number;
  employee_name: string;
  created_at: string | null;
}
export const getRequestBackups = (month: string) =>
  request<RequestBackupInfo[]>(`/requests/backups?month=${month}`);
export const restoreRequest = (employeeId: number, month: string) =>
  request<ShiftRequest>(`/requests/${employeeId}/restore`, {
    method: "POST", body: JSON.stringify({ month }),
  });

// ---- Daily Requirements ----
export interface DailyRequirement {
  id: number;
  date: string;
  job_type_id: number;
  job_type_name: string;
  required_count: number;
}

export const getRequirements = (month: string) =>
  request<DailyRequirement[]>(`/requirements?month=${month}`);
export const upsertRequirements = (items: { date: string; job_type_id: number; required_count: number }[]) =>
  request<{ status: string }>("/requirements", { method: "POST", body: JSON.stringify({ items }) });
export const applyTemplate = (data: {
  month: string;
  weekday_requirements: Record<number, { job_type_id: number; required_count: number }[]>;
}) => request<{ status: string }>("/requirements/template", { method: "POST", body: JSON.stringify(data) });

// ---- Schedules ----
export interface Schedule {
  id: number;
  target_month: string;
  status: string;
  generated_at: string | null;
  confirmed_at: string | null;
}

export interface ShiftAssignment {
  id: number;
  schedule_id: number;
  employee_id: number;
  employee_name: string;
  date: string;
  job_type_id: number | null;
  job_type_name: string | null;
  job_type_color: string | null;
  work_type: string;
  headcount_value: number;
}

export const getSchedules = (month?: string) =>
  request<Schedule[]>(`/schedules${month ? `?month=${month}` : ""}`);
export const generateSchedule = (month: string) =>
  request<{ schedule_id: number; assignment_count: number; violations: string[] }>(
    "/schedules/generate",
    { method: "POST", body: JSON.stringify({ month }) }
  );
export const getAssignments = (scheduleId: number) =>
  request<ShiftAssignment[]>(`/schedules/${scheduleId}/assignments`);
export const updateAssignments = (
  scheduleId: number,
  items: { employee_id: number; date: string; job_type_id: number | null; work_type: string }[]
) =>
  request<{ status: string }>(`/schedules/${scheduleId}/assignments`, {
    method: "PUT",
    body: JSON.stringify(items),
  });
export const updateScheduleStatus = (scheduleId: number, status: string) =>
  request<{ status: string }>(`/schedules/${scheduleId}/status`, {
    method: "PUT",
    body: JSON.stringify({ status }),
  });

// ---- NLP Modify ----
export interface NlpModifyResult {
  log_id: number;
  new_schedule_id: number;
  parsed_instruction: Record<string, unknown>[];
  changes: {
    employee_id: number;
    employee_name: string;
    date: string;
    old_job_type: string;
    new_job_type: string;
  }[];
  violations: string[];
}

export const nlpModify = (scheduleId: number, input_text: string) =>
  request<NlpModifyResult>(`/schedules/${scheduleId}/nlp-modify`, {
    method: "POST",
    body: JSON.stringify({ input_text }),
  });
export const approveNlpLog = (logId: number) =>
  request<{ status: string }>(`/nlp-logs/${logId}/approve`, { method: "PUT" });
export const rejectNlpLog = (logId: number) =>
  request<{ status: string }>(`/nlp-logs/${logId}/reject`, { method: "PUT" });

// ---- Reports ----
export interface EmployeeReport {
  employee_id: number;
  employee_name: string;
  total_work_days: number;
  total_days_off: number;
  requested_work_days: string | null;  // "1"-"23" or "max"
  weekly_work_day_limit: number | null;
  job_type_counts: Record<string, number>;
  comment: string;
}

export interface Report {
  month: string;
  employees: EmployeeReport[];
}

export const getReport = (month: string) => request<Report>(`/reports?month=${month}`);

// ---- Holidays ----
export interface Holiday {
  date: string;
  name: string;
}

export const getHolidays = (year: number) => request<Holiday[]>(`/holidays?year=${year}`);

// ---- Staff Portal ----
export interface StaffPortalInfo {
  employee_id: number;
  employee_name: string;
  employment_type: string;
  target_month: string;
  existing_request: ShiftRequest | null;
}

export interface EmployeeToken {
  employee_id: number;
  employee_name: string;
  staff_token: string | null;
}

export const getStaffPortalInfo = (token: string, month: string) =>
  request<StaffPortalInfo>(`/staff-portal/${token}?month=${month}`);
export const submitStaffRequest = (token: string, data: {
  target_month: string;
  requested_work_days?: string | null;
  weekly_work_day_limit?: number | null;
  note?: string | null;
  days_off: { date: string; period: string }[];
}) => request<ShiftRequest>(`/staff-portal/${token}`, { method: "POST", body: JSON.stringify(data) });
export const getEmployeeTokens = () => request<EmployeeToken[]>("/employees/tokens");
export const generateToken = (employeeId: number) =>
  request<EmployeeToken>(`/employees/${employeeId}/token`, { method: "POST" });
export const revokeToken = (employeeId: number) =>
  request<void>(`/employees/${employeeId}/token`, { method: "DELETE" });

// ---- Export ----
export const getExportUrl = (type: "csv" | "excel" | "pdf", month: string) =>
  `${API_BASE}/export/${type}?month=${month}`;
