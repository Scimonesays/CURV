import { useCallback, useEffect, useMemo, useState } from "react";
import {
  CatalogItem,
  CertDetail,
  CertSummary,
  Identity,
  Job,
  Lane,
  Policy,
  RegistryPayload,
  Repro,
  RunDetail,
  Status,
  Survivorship,
  TimelineEvent,
  View,
  artifactUrl,
  cancelJob,
  createJob,
  fetchArtifactScan,
  fetchCatalog,
  fetchCertDetail,
  fetchCertification,
  fetchIdentity,
  fetchLanes,
  fetchRepro,
  fetchRegistry,
  fetchRun,
  fetchSurvivorship,
  fetchTimeline,
} from "./api";
import { StatusToken } from "./components/StatusToken";

const PROMO_STEPS = ["none", "gate0", "candidate", "strong_candidate", "investigate", "certified"];

const DEFAULT_REG: Record<Lane, string> = {
  theory: "results_registry",
  claims: "ufo_observable_registry",
  exotic: "exotic_tripwire_registry",
  certification: "",
};

export default function App() {
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [lane, setLane] = useState<Lane>("theory");
  const [view, setView] = useState<View>("evidence");
  const [policy, setPolicy] = useState<Policy>("strict");
  const [speculative, setSpeculative] = useState(false);
  const [regsByLane, setRegsByLane] = useState<Record<string, string[]>>({});
  const [registryName, setRegistryName] = useState("results_registry");
  const [registry, setRegistry] = useState<RegistryPayload | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [run, setRun] = useState<RunDetail | null>(null);
  const [repro, setRepro] = useState<Repro | null>(null);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [catalog, setCatalog] = useState<CatalogItem[]>([]);
  const [launchId, setLaunchId] = useState<string>("");
  const [launchParams, setLaunchParams] = useState<Record<string, unknown>>({});
  const [activeJob, setActiveJob] = useState<Job | null>(null);
  const [jobLog, setJobLog] = useState("");
  const [certLatest, setCertLatest] = useState<CertSummary | null>(null);
  const [certDetail, setCertDetail] = useState<CertDetail | null>(null);
  const [survivorship, setSurvivorship] = useState<Survivorship | null>(null);
  const [atlasDirs, setAtlasDirs] = useState<{ run_id: string; indexed: boolean }[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [jsonPreview, setJsonPreview] = useState<string>("");

  const refreshChrome = useCallback(async () => {
    const [id, lanes, tl, cert] = await Promise.all([
      fetchIdentity(),
      fetchLanes(),
      fetchTimeline(),
      fetchCertification(),
    ]);
    setIdentity(id);
    setRegsByLane(lanes.registries_by_lane);
    setTimeline(tl.events);
    setCertLatest(cert.latest);
  }, []);

  const loadRegistry = useCallback(async (name: string) => {
    if (!name) {
      setRegistry(null);
      return;
    }
    const data = await fetchRegistry(name);
    setRegistry(data);
  }, []);

  useEffect(() => {
    refreshChrome().catch((e) => setError(String(e)));
    const t = setInterval(() => {
      fetchTimeline()
        .then((tl) => setTimeline(tl.events))
        .catch(() => undefined);
      fetchIdentity()
        .then(setIdentity)
        .catch(() => undefined);
    }, 8000);
    return () => clearInterval(t);
  }, [refreshChrome]);

  useEffect(() => {
    const next = DEFAULT_REG[lane];
    setRegistryName(next);
    setView(lane === "certification" ? "certification" : "evidence");
    if (lane !== "certification") {
      loadRegistry(next).catch((e) => setError(String(e)));
    }
    if (lane === "certification") {
      fetchCertification()
        .then(async (c) => {
          setCertLatest(c.latest);
          if (c.latest) {
            setCertDetail(await fetchCertDetail(c.latest.cert_id));
          }
        })
        .catch((e) => setError(String(e)));
    }
    fetchCatalog(lane === "certification" ? undefined : lane)
      .then((c) => {
        const items =
          lane === "certification"
            ? c.items.filter((i) => i.lane === "certification")
            : c.items;
        setCatalog(items);
        setLaunchId(items[0]?.id || "");
        const first = items[0];
        if (first) {
          const defaults: Record<string, unknown> = {};
          for (const f of first.fields) defaults[f.name] = f.default ?? "";
          setLaunchParams(defaults);
        }
      })
      .catch((e) => setError(String(e)));
    if (lane === "exotic") {
      fetchArtifactScan()
        .then((d) => setAtlasDirs(d.dirs))
        .catch(() => undefined);
    }
  }, [lane, loadRegistry]);

  useEffect(() => {
    if (!selectedRunId) {
      setRun(null);
      setRepro(null);
      return;
    }
    Promise.all([fetchRun(selectedRunId), fetchRepro(selectedRunId)])
      .then(([r, rp]) => {
        setRun(r);
        setRepro(rp);
        setSelectedFile(null);
        setJsonPreview("");
      })
      .catch((e) => setError(String(e)));
  }, [selectedRunId]);

  useEffect(() => {
    if (view === "survivorship" && selectedRunId) {
      fetchSurvivorship(selectedRunId)
        .then(setSurvivorship)
        .catch((e) => setError(String(e)));
    }
  }, [view, selectedRunId]);

  const promoLevel = useMemo(() => {
    const level = (run?.promotion?.level || "none").toLowerCase();
    if (certLatest?.overall_status === "PASS" && lane === "certification") return "certified";
    return level;
  }, [run, certLatest, lane]);

  const selectRun = (runId: string) => {
    setSelectedRunId(runId);
    setView("run");
  };

  const onLaunchCatalogChange = (id: string) => {
    setLaunchId(id);
    const item = catalog.find((c) => c.id === id);
    if (!item) return;
    const defaults: Record<string, unknown> = {};
    for (const f of item.fields) defaults[f.name] = f.default ?? "";
    setLaunchParams(defaults);
  };

  const startJob = async () => {
    if (!launchId) return;
    setError(null);
    setJobLog("");
    try {
      const job = await createJob({
        catalog_id: launchId,
        params: launchParams,
        policy,
        speculative,
      });
      setActiveJob(job);
      const es = new EventSource(`/api/jobs/${job.job_id}/logs`);
      es.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data);
          if (data.chunk) setJobLog((prev) => prev + data.chunk);
          if (data.job) setActiveJob(data.job);
          if (data.done) {
            es.close();
            refreshChrome();
            if (registryName) loadRegistry(registryName);
            if (data.job?.run_id) setSelectedRunId(data.job.run_id);
          }
        } catch {
          /* ignore */
        }
      };
      es.onerror = () => es.close();
    } catch (e) {
      setError(String(e));
    }
  };

  const copyRepro = async () => {
    const cmd = repro?.cli_command;
    if (!cmd) {
      setError("No stored CLI command for this run. Launch from the instrument to capture argv.");
      return;
    }
    await navigator.clipboard.writeText(cmd);
  };

  const openFile = async (path: string) => {
    setSelectedFile(path);
    if (path.endsWith(".json")) {
      const res = await fetch(`/api/artifacts/json?path=${encodeURIComponent(path)}`);
      const data = await res.json();
      setJsonPreview(JSON.stringify(data, null, 2));
    } else if (path.endsWith(".csv") || path.endsWith(".txt") || path.endsWith(".log")) {
      const res = await fetch(artifactUrl(path));
      setJsonPreview(await res.text());
    } else {
      setJsonPreview("");
    }
  };

  const laneRegs = regsByLane[lane] || [];

  const viewTabs: { id: View; label: string; show: boolean }[] = [
    { id: "evidence", label: "Evidence", show: lane !== "certification" },
    { id: "run", label: "Run Detail", show: true },
    { id: "launch", label: "Launch", show: true },
    { id: "survivorship", label: "Survivorship", show: lane === "theory" },
    { id: "scorecard", label: "Scorecard", show: lane === "claims" },
    { id: "ladder", label: "Ladder", show: lane === "claims" },
    { id: "atlas", label: "Atlas", show: lane === "exotic" },
    { id: "certification", label: "Certification", show: lane === "certification" },
  ];

  return (
    <div className="instrument">
      <div className="bezel policy-bezel">
        <div className="bezel-row">
          <div className="brand">CURV Instrument</div>
          <div className="policy-bar">
            {(["strict", "normal", "sandbox"] as Policy[]).map((p) => (
              <button
                key={p}
                type="button"
                className={`seg ${policy === p ? "on" : ""}`}
                onClick={() => setPolicy(p)}
              >
                {p}
              </button>
            ))}
            <button
              type="button"
              className={`spec ${speculative ? "yes" : "no"}`}
              onClick={() => setSpeculative((v) => !v)}
            >
              SPECULATIVE: {speculative ? "YES" : "NO"}
            </button>
          </div>
        </div>
      </div>

      <div className="bezel">
        <div className="timeline">
          {timeline.length === 0 && <span className="muted">No session events yet</span>}
          {timeline.map((ev, i) => (
            <button
              key={`${ev.timestamp_utc}-${ev.label}-${i}`}
              type="button"
              className="timeline-item"
              onClick={() => ev.run_id && selectRun(ev.run_id)}
            >
              <span>{ev.time_display}</span>
              <span>{ev.label}</span>
              <StatusToken status={ev.status as Status} />
            </button>
          ))}
        </div>
      </div>

      <div className="bezel">
        <div className="bezel-row">
          <div className="git-id">
            <span>{identity?.branch ?? "—"}</span>
            <span>{identity?.commit ?? "—"}</span>
            <span>{identity?.dirty_label ?? "—"}</span>
            <span>{identity?.date ?? "—"}</span>
            <span>py {identity?.python ?? "—"}</span>
          </div>
        </div>
      </div>

      <div className="bezel">
        <div className="promo-strip">
          <span>Promotion</span>
          {PROMO_STEPS.map((step, idx) => (
            <span key={step}>
              {idx > 0 && <span className="arrow">→</span>}
              <span className={`step ${promoLevel === step ? "on" : ""}`}>{step}</span>
            </span>
          ))}
        </div>
      </div>

      <div className="body">
        <nav className="lane-rail">
          {(
            [
              ["theory", "Theory"],
              ["claims", "Claims"],
              ["exotic", "Exotic"],
              ["certification", "Certification"],
            ] as [Lane, string][]
          ).map(([id, label]) => (
            <button key={id} type="button" className={lane === id ? "on" : ""} onClick={() => setLane(id)}>
              {label}
            </button>
          ))}
        </nav>

        <main className="main">
          {speculative && <div className="banner-spec">SPECULATIVE MODE</div>}
          {error && (
            <div className="banner-spec" style={{ borderColor: "var(--fail)", color: "var(--fail)" }}>
              {error}
            </div>
          )}

          {lane !== "certification" && certLatest && (
            <div className="latest-cert">
              Latest certified: {certLatest.cert_id}{" "}
              <StatusToken status={(certLatest.overall_status as Status) || "WARNING"} />{" "}
              <button type="button" onClick={() => setLane("certification")}>
                Open
              </button>
            </div>
          )}

          <div className="view-tabs">
            {viewTabs
              .filter((t) => t.show)
              .map((t) => (
                <button
                  key={t.id}
                  type="button"
                  className={view === t.id ? "on" : ""}
                  onClick={() => setView(t.id)}
                >
                  {t.label}
                </button>
              ))}
          </div>

          {view === "evidence" && (
            <EvidenceView
              laneRegs={laneRegs}
              registryName={registryName}
              registry={registry}
              selectedRunId={selectedRunId}
              onRegistryChange={(name) => {
                setRegistryName(name);
                loadRegistry(name).catch((e) => setError(String(e)));
              }}
              onSelect={selectRun}
            />
          )}

          {view === "run" && (
            <RunDetailView
              run={run}
              selectedFile={selectedFile}
              jsonPreview={jsonPreview}
              onOpenFile={openFile}
            />
          )}

          {view === "launch" && (
            <LaunchView
              catalog={catalog}
              launchId={launchId}
              launchParams={launchParams}
              policy={policy}
              speculative={speculative}
              activeJob={activeJob}
              jobLog={jobLog}
              onCatalogChange={onLaunchCatalogChange}
              onParamChange={(k, v) => setLaunchParams((p) => ({ ...p, [k]: v }))}
              onStart={startJob}
              onCancel={async () => {
                if (!activeJob) return;
                const j = await cancelJob(activeJob.job_id);
                setActiveJob(j);
              }}
            />
          )}

          {view === "survivorship" && (
            <SurvivorshipView data={survivorship} onSelectPlot={openFile} />
          )}

          {view === "scorecard" && <ScorecardView run={run} />}

          {view === "ladder" && <LadderView run={run} />}

          {view === "atlas" && (
            <AtlasView
              dirs={atlasDirs}
              onSelect={(id) => selectRun(id)}
              refresh={() =>
                fetchArtifactScan()
                  .then((d) => setAtlasDirs(d.dirs))
                  .catch((e) => setError(String(e)))
              }
            />
          )}

          {view === "certification" && <CertificationView detail={certDetail} latest={certLatest} />}
        </main>

        <aside className="side">
          <h2>Reproducibility</h2>
          {!repro && <div className="empty">Select a run</div>}
          {repro && (
            <div className="repro">
              <dl>
                <dt>Run ID</dt>
                <dd>{repro.run_id}</dd>
                <dt>Script</dt>
                <dd>{repro.script || "—"}</dd>
                <dt>Git</dt>
                <dd>{typeof repro.git === "string" ? repro.git : JSON.stringify(repro.git) || "—"}</dd>
                <dt>Python</dt>
                <dd>{repro.python || "—"}</dd>
                <dt>Registry</dt>
                <dd>{repro.registry || "—"}</dd>
                <dt>Artifacts</dt>
                <dd>
                  {repro.artifact_counts.png} PNG / {repro.artifact_counts.csv} CSV /{" "}
                  {repro.artifact_counts.json} JSON
                </dd>
                <dt>Duration</dt>
                <dd>{repro.duration_s != null ? `${repro.duration_s}s` : "—"}</dd>
                <dt>Policy</dt>
                <dd>{(repro.policy || policy).toUpperCase()}</dd>
                <dt>Speculative</dt>
                <dd>{repro.speculative ? "YES" : "NO"}</dd>
                <dt>Job history</dt>
                <dd>{repro.from_job_history ? "yes" : "no"}</dd>
              </dl>
              <hr className="hairline" />
              <button type="button" onClick={copyRepro}>
                Copy Reproduction Command
              </button>
              {repro.cli_command && (
                <>
                  <hr className="hairline" />
                  <div className="pre">{repro.cli_command}</div>
                </>
              )}
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}

function EvidenceView(props: {
  laneRegs: string[];
  registryName: string;
  registry: RegistryPayload | null;
  selectedRunId: string | null;
  onRegistryChange: (name: string) => void;
  onSelect: (runId: string) => void;
}) {
  const cols = useMemo(() => {
    const preferred = [
      "timestamp_utc",
      "run_id",
      "batch_id",
      "model_mode",
      "profile",
      "policy",
      "verdict",
      "gateA_pass",
      "tripwire_pass",
      "promotion_level",
      "git_hash",
      "n_failed_gates",
      "deepest_step",
    ];
    if (!props.registry) return preferred;
    const available = props.registry.columns;
    const show = preferred.filter((c) => available.includes(c));
    return show.length ? show : available.slice(0, 8);
  }, [props.registry]);

  return (
    <div>
      <div className="toolbar">
        <label className="muted">
          Registry{" "}
          <select
            value={props.registryName}
            onChange={(e) => props.onRegistryChange(e.target.value)}
          >
            {props.laneRegs.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </label>
        <span className="muted mono">
          {props.registry?.exists ? `${props.registry.total} rows` : "empty"}
        </span>
      </div>
      {!props.registry?.exists || props.registry.total === 0 ? (
        <div className="empty">No registry rows yet. Launch a run to append evidence.</div>
      ) : (
        <table className="registry">
          <thead>
            <tr>
              {cols.map((c) => (
                <th key={c}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {props.registry.rows.map((row) => {
              const rid = row.run_id || row.batch_id || "";
              return (
                <tr
                  key={rid + (row.timestamp_utc || "")}
                  className={props.selectedRunId === rid ? "selected" : ""}
                  onClick={() => rid && props.onSelect(rid)}
                >
                  {cols.map((c) => (
                    <td key={c} title={row[c]}>
                      {row[c]}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

function RunDetailView(props: {
  run: RunDetail | null;
  selectedFile: string | null;
  jsonPreview: string;
  onOpenFile: (path: string) => void;
}) {
  const run = props.run;
  if (!run) return <div className="empty">Select a run from Evidence or Timeline</div>;
  return (
    <div>
      <h2>Run</h2>
      <div className="mono">{run.run_id}</div>
      {!run.indexed && <div className="banner-spec">UNINDEXED — artifact-only</div>}
      <hr className="hairline" />
      <h3>Summary</h3>
      <div className="gate-list">
        <div className="gate-row">
          <span>Status</span>
          <StatusToken status={run.status} />
        </div>
        <div className="gate-row">
          <span>Promotion</span>
          <span className="mono">{run.promotion?.level || "none"}</span>
        </div>
        <div className="gate-row">
          <span>Git</span>
          <span className="mono">{run.git_hash || "—"}</span>
        </div>
        <div className="gate-row">
          <span>Registry</span>
          <span className="mono">{run.registry || "—"}</span>
        </div>
      </div>
      <hr className="hairline" />
      <h3>Gates</h3>
      {run.gates.length === 0 && <div className="empty">No gate fields parsed</div>}
      <div className="gate-list">
        {run.gates.map((g, i) => (
          <div className="gate-row" key={i}>
            <span>
              {g.name}
              {g.severity === "hard" ? " [hard]" : ""}
              {g.lane ? ` (${g.lane})` : ""}
            </span>
            <StatusToken
              status={g.passed === "true" ? "PASS" : g.passed === "na" ? "WARNING" : "FAIL"}
            />
          </div>
        ))}
      </div>
      <hr className="hairline" />
      <h3>Plots</h3>
      <div className="plots">
        {run.files.plots.map((p) => (
          <img key={p.path} src={artifactUrl(p.path)} alt={p.name} title={p.name} />
        ))}
        {run.files.plots.length === 0 && <div className="empty">No plots</div>}
      </div>
      <hr className="hairline" />
      <h3>Metrics / Raw</h3>
      <ul className="file-list">
        {[...run.files.metrics, ...run.files.raw, ...run.files.other].map((f) => (
          <li
            key={f.path}
            className={props.selectedFile === f.path ? "on" : ""}
            onClick={() => props.onOpenFile(f.path)}
          >
            {f.path}
          </li>
        ))}
      </ul>
      {props.jsonPreview && <div className="pre">{props.jsonPreview}</div>}
    </div>
  );
}

function LaunchView(props: {
  catalog: CatalogItem[];
  launchId: string;
  launchParams: Record<string, unknown>;
  policy: Policy;
  speculative: boolean;
  activeJob: Job | null;
  jobLog: string;
  onCatalogChange: (id: string) => void;
  onParamChange: (k: string, v: unknown) => void;
  onStart: () => void;
  onCancel: () => void;
}) {
  const item = props.catalog.find((c) => c.id === props.launchId);
  return (
    <div>
      <h2>Launch</h2>
      <p className="muted">Secondary control surface. Evidence remains the default view.</p>
      <div className="form-grid">
        <label>
          Script
          <select value={props.launchId} onChange={(e) => props.onCatalogChange(e.target.value)}>
            {props.catalog.map((c) => (
              <option key={c.id} value={c.id}>
                {c.label} — {c.script}
              </option>
            ))}
          </select>
        </label>
        <div className="mono muted">
          Policy {props.policy.toUpperCase()} · Speculative {props.speculative ? "YES" : "NO"}
        </div>
        {item?.fields.map((f) => (
          <label key={f.name}>
            {f.name}
            {f.type === "bool" ? (
              <input
                type="checkbox"
                checked={Boolean(props.launchParams[f.name])}
                onChange={(e) => props.onParamChange(f.name, e.target.checked)}
              />
            ) : f.type === "choice" ? (
              <select
                value={String(props.launchParams[f.name] ?? "")}
                onChange={(e) => props.onParamChange(f.name, e.target.value)}
              >
                {(f.choices || []).map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            ) : (
              <input
                value={String(props.launchParams[f.name] ?? "")}
                onChange={(e) =>
                  props.onParamChange(
                    f.name,
                    f.type === "int" || f.type === "float"
                      ? e.target.value === ""
                        ? ""
                        : Number(e.target.value)
                      : e.target.value,
                  )
                }
              />
            )}
          </label>
        ))}
        <div className="toolbar">
          <button type="button" onClick={props.onStart}>
            Start
          </button>
          {props.activeJob?.status === "RUNNING" && (
            <button type="button" className="danger" onClick={props.onCancel}>
              Cancel
            </button>
          )}
          {props.activeJob && (
            <span className="mono">
              {props.activeJob.job_id} <StatusToken status={props.activeJob.status as Status} />
            </span>
          )}
        </div>
      </div>
      {props.jobLog && (
        <>
          <hr className="hairline" />
          <h3>Stdout</h3>
          <div className="pre">{props.jobLog}</div>
        </>
      )}
    </div>
  );
}

function SurvivorshipView(props: { data: Survivorship | null; onSelectPlot: (path: string) => void }) {
  if (!props.data) return <div className="empty">Select a sweep run first</div>;
  return (
    <div>
      <h2>Survivorship</h2>
      <div className="mono">{props.data.run_id}</div>
      <div className="gate-row" style={{ marginTop: "0.5rem" }}>
        <span>Status</span>
        <StatusToken status={props.data.status} />
      </div>
      <hr className="hairline" />
      <h3>Heatmaps</h3>
      <div className="plots">
        {props.data.heatmaps.map((p) => (
          <img
            key={p.path}
            src={artifactUrl(p.path)}
            alt={p.name}
            onClick={() => props.onSelectPlot(p.path)}
          />
        ))}
        {props.data.heatmaps.length === 0 && <div className="empty">No heatmap PNGs</div>}
      </div>
      <hr className="hairline" />
      <h3>Survivor table</h3>
      {!props.data.preview && <div className="empty">No survivor CSV</div>}
      {props.data.preview && (
        <table className="registry">
          <thead>
            <tr>
              {props.data.preview.columns.slice(0, 10).map((c) => (
                <th key={c}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {props.data.preview.rows.slice(0, 80).map((row, i) => (
              <tr key={i}>
                {props.data!.preview!.columns.slice(0, 10).map((c) => (
                  <td key={c}>{row[c]}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function ScorecardView(props: { run: RunDetail | null }) {
  const j = props.run?.primary_json as Record<string, unknown> | null;
  if (!props.run) return <div className="empty">Select a claims run</div>;
  if (!j) return <div className="empty">No scorecard JSON on this run</div>;
  const failed = (j.failed_gates as unknown[]) || [];
  const lanes = (j.lane_rankings as { lane: string; passed: boolean; fail_count: number }[]) || [];
  return (
    <div>
      <h2>Scorecard</h2>
      <div className="gate-list">
        <div className="gate-row">
          <span>Verdict</span>
          <span className="mono">{String(j.verdict || "")}</span>
        </div>
        <div className="gate-row">
          <span>Failed gates</span>
          <span className="mono">{String(j.n_failed_gates ?? failed.length)}</span>
        </div>
      </div>
      <hr className="hairline" />
      <h3>Lane rankings</h3>
      {lanes.map((l) => (
        <div className="gate-row" key={l.lane}>
          <span>{l.lane}</span>
          <span>
            <StatusToken status={l.passed ? "PASS" : "FAIL"} /> fail_count={l.fail_count}
          </span>
        </div>
      ))}
      <hr className="hairline" />
      <h3>Failed gates</h3>
      <div className="pre">{JSON.stringify(failed, null, 2)}</div>
    </div>
  );
}

function LadderView(props: { run: RunDetail | null }) {
  const j = props.run?.primary_json as {
    overall?: Record<string, unknown>;
    steps?: { step: number; name: string; verdict: string; n_failed_gates: number }[];
  } | null;
  if (!props.run) return <div className="empty">Select a breakthrough ladder run</div>;
  if (!j?.steps) return <div className="empty">No ladder JSON on this run</div>;
  return (
    <div>
      <h2>Breakthrough Ladder</h2>
      <div className="gate-list">
        <div className="gate-row">
          <span>Deepest without speculation</span>
          <span className="mono">{String(j.overall?.deepest_step_reached_without_speculation)}</span>
        </div>
        <div className="gate-row">
          <span>First failure</span>
          <span className="mono">{String(j.overall?.first_failure_step)}</span>
        </div>
      </div>
      <hr className="hairline" />
      {j.steps.map((s) => (
        <div className="gate-row" key={s.step}>
          <span>
            {s.step} {s.name}
          </span>
          <span className="mono">
            n_failed={s.n_failed_gates} · {s.verdict}
          </span>
        </div>
      ))}
    </div>
  );
}

function AtlasView(props: {
  dirs: { run_id: string; indexed: boolean }[];
  onSelect: (id: string) => void;
  refresh: () => void;
}) {
  return (
    <div>
      <h2>Source / Exotic Atlas</h2>
      <p className="muted">Artifact directories under results/artifacts — phase maps may be unindexed.</p>
      <button type="button" onClick={props.refresh}>
        Refresh
      </button>
      <hr className="hairline" />
      <ul className="file-list">
        {props.dirs.map((d) => (
          <li key={d.run_id} onClick={() => props.onSelect(d.run_id)}>
            {d.run_id} {d.indexed ? "" : "[unindexed]"}
          </li>
        ))}
      </ul>
      {props.dirs.length === 0 && <div className="empty">No artifact directories</div>}
    </div>
  );
}

function CertificationView(props: { detail: CertDetail | null; latest: CertSummary | null }) {
  const report = props.detail?.report;
  const tests = report?.tests || props.latest?.tests || {};
  return (
    <div>
      <h2>Certification</h2>
      <div className="gate-row">
        <span>{props.detail?.cert_id || props.latest?.cert_id || "none"}</span>
        <StatusToken status={(report?.overall_status || props.latest?.overall_status || "WARNING") as Status} />
      </div>
      <hr className="hairline" />
      <div className="cert-matrix">
        {Object.keys(tests).length === 0 && <div className="empty">No certification reports under results/certification</div>}
        {Object.entries(tests).map(([name, t]) => (
          <div className="cert-row" key={name}>
            <span>{name}</span>
            <StatusToken status={(t.status || "WARNING") as Status} />
            <span className="muted">{t.details || ""}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
