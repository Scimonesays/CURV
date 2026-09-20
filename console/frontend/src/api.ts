export type Policy = "strict" | "normal" | "sandbox";
export type Lane = "theory" | "claims" | "exotic" | "certification";
export type View =
  | "evidence"
  | "run"
  | "launch"
  | "survivorship"
  | "scorecard"
  | "ladder"
  | "atlas"
  | "certification";

export type Status = "PASS" | "FAIL" | "RUNNING" | "WARNING";

const BASE = "";

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json() as Promise<T>;
}

export const fetchIdentity = () => api<Identity>("/api/identity");
export const fetchLanes = () => api<{ lanes: { id: Lane; label: string }[]; registries_by_lane: Record<string, string[]> }>("/api/lanes");
export const fetchRegistries = () => api<{ registries: RegistryInfo[] }>("/api/registries");
export const fetchRegistry = (name: string, limit = 200) =>
  api<RegistryPayload>(`/api/registries/${encodeURIComponent(name)}?limit=${limit}`);
export const fetchRun = (runId: string) => api<RunDetail>(`/api/runs/${encodeURIComponent(runId)}`);
export const fetchRepro = (runId: string) => api<Repro>(`/api/runs/${encodeURIComponent(runId)}/repro`);
export const fetchTimeline = () => api<{ events: TimelineEvent[] }>("/api/timeline");
export const fetchCatalog = (lane?: Lane) =>
  api<{ items: CatalogItem[] }>(lane ? `/api/catalog?lane=${lane}` : "/api/catalog");
export const fetchCertification = () => api<{ items: CertSummary[]; latest: CertSummary | null }>("/api/certification");
export const fetchCertDetail = (id: string) => api<CertDetail>(`/api/certification/${encodeURIComponent(id)}`);
export const fetchSurvivorship = (runId: string) =>
  api<Survivorship>(`/api/survivorship/${encodeURIComponent(runId)}`);
export const fetchArtifactScan = () => api<{ dirs: ArtifactDir[] }>("/api/artifacts/scan");
export const fetchJobs = () => api<{ jobs: Job[] }>("/api/jobs");
export const fetchJob = (id: string) => api<Job>(`/api/jobs/${encodeURIComponent(id)}`);
export const createJob = (body: {
  catalog_id: string;
  params: Record<string, unknown>;
  policy: Policy;
  speculative: boolean;
}) =>
  api<Job>("/api/jobs", {
    method: "POST",
    body: JSON.stringify(body),
  });
export const cancelJob = (id: string) =>
  api<Job>(`/api/jobs/${encodeURIComponent(id)}/cancel`, { method: "POST" });

export function artifactUrl(path: string): string {
  return `/api/artifacts?path=${encodeURIComponent(path)}`;
}

export interface Identity {
  branch: string;
  commit: string;
  dirty: boolean;
  dirty_label: string;
  date: string;
  python: string;
}

export interface RegistryInfo {
  name: string;
  csv_exists: boolean;
  row_count: number;
  lanes: string[];
}

export interface RegistryPayload {
  name: string;
  columns: string[];
  rows: Record<string, string>[];
  total: number;
  exists: boolean;
}

export interface FileEntry {
  path: string;
  name: string;
  suffix: string;
}

export interface RunDetail {
  run_id: string;
  registry: string | null;
  row: Record<string, string> | null;
  indexed: boolean;
  artifact_dir: string | null;
  files: {
    plots: FileEntry[];
    metrics: FileEntry[];
    raw: FileEntry[];
    other: FileEntry[];
  };
  gates: { name: string; passed: string; severity: string; lane: string }[];
  promotion: { level: string; reasons: string[]; order: string[] };
  status: Status;
  git_hash?: string;
  timestamp_utc?: string;
  policy?: string;
  primary_json: unknown;
}

export interface Repro {
  run_id: string;
  script?: string;
  arguments: unknown[];
  argv: string[];
  cli_command?: string;
  git?: unknown;
  python?: string;
  registry?: string | null;
  artifact_counts: Record<string, number>;
  duration_s?: number;
  policy?: string;
  speculative?: boolean;
  from_job_history: boolean;
}

export interface TimelineEvent {
  source: string;
  run_id?: string;
  job_id?: string;
  timestamp_utc: string;
  label: string;
  status: string;
  time_display: string;
}

export interface CatalogItem {
  id: string;
  label: string;
  lane: string;
  script: string;
  fields: {
    name: string;
    flag: string;
    type: string;
    default?: unknown;
    choices?: string[];
    required?: boolean;
    speculative?: boolean;
  }[];
  inject_policy?: boolean;
  unindexed?: boolean;
}

export interface CertSummary {
  cert_id: string;
  overall_status?: string;
  cert_version?: string;
  failure_codes?: string[];
  tests?: Record<string, { status?: string; details?: string }>;
  report_path?: string;
}

export interface CertDetail {
  cert_id: string;
  report?: {
    overall_status?: string;
    tests?: Record<string, { status?: string; details?: string; failure_codes?: string[] }>;
    failure_codes?: string[];
  };
}

export interface Survivorship {
  run_id: string;
  survivors: FileEntry[];
  heatmaps: FileEntry[];
  preview: { columns: string[]; rows: Record<string, string>[] } | null;
  promotion: { level: string };
  status: Status;
}

export interface ArtifactDir {
  run_id: string;
  path: string;
  indexed: boolean;
  registry: string | null;
}

export interface Job {
  job_id: string;
  catalog_id: string;
  script: string;
  argv: string[];
  cli_command: string;
  status: string;
  run_id?: string | null;
  policy: string;
  speculative: boolean;
  duration_s?: number | null;
  exit_code?: number | null;
  log_tail?: string;
  error?: string | null;
}
