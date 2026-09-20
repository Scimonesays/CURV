import type { Status } from "../api";

export function StatusToken({ status }: { status: Status | string }) {
  const s = String(status || "WARNING").toUpperCase();
  const cls =
    s === "PASS" || s === "FAIL" || s === "RUNNING" || s === "WARNING" ? s : "WARNING";
  return <span className={`status ${cls}`}>{cls}</span>;
}
