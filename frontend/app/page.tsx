"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  AnalyzeResponse,
  ApiError,
  CompanyResponse,
  CompetitorListResponse,
  CompetitorResponse,
  JobStatusResponse,
  JsonMap,
  ReportJsonResponse,
  apiFetch,
  reportDownloadUrl,
} from "@/lib/api";

const POLL_INTERVAL_MS = 3000;

type TabKey = "business" | "visual" | "dom";
type CompetitorTab = "local" | "global";

function labelize(value: string) {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function valueToString(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return "N/A";
  }

  if (Array.isArray(value)) {
    return value.map((item) => String(item)).join(", ");
  }

  if (typeof value === "object") {
    return JSON.stringify(value, null, 2);
  }

  return String(value);
}

function isRecord(value: unknown): value is JsonMap {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function MetricCard({
  label,
  value,
}: {
  label: string;
  value: unknown;
}) {
  return (
    <div className="metric-card">
      <span>{label}</span>
      <strong>{valueToString(value)}</strong>
    </div>
  );
}

function KeyValueList({ data }: { data?: JsonMap | null }) {
  if (!data || Object.keys(data).length === 0) {
    return <p className="empty-state">No data available.</p>;
  }

  return (
    <dl className="key-value-list">
      {Object.entries(data).map(([key, value]) => (
        <div key={key}>
          <dt>{labelize(key)}</dt>
          <dd>
            {Array.isArray(value) ? (
              <ul className="inline-list">
                {value.map((item, index) => (
                  <li key={`${key}-${index}`}>{valueToString(item)}</li>
                ))}
              </ul>
            ) : isRecord(value) ? (
              <pre>{JSON.stringify(value, null, 2)}</pre>
            ) : (
              valueToString(value)
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function StatusBadge({ status }: { status: JobStatusResponse["status"] }) {
  return <span className={`status-badge ${status}`}>{labelize(status)}</span>;
}

function CompetitorBars({
  competitors,
}: {
  competitors: CompetitorResponse[];
}) {
  const maxScore = Math.max(
    1,
    ...competitors.map((competitor) => competitor.similarity_score ?? 0),
  );

  return (
    <div className="bar-list" aria-label="Similarity scores">
      {competitors.map((competitor) => {
        const score = competitor.similarity_score ?? 0;
        const width = Math.max(5, Math.round((score / maxScore) * 100));

        return (
          <div className="bar-row" key={competitor.id}>
            <span>{competitor.name || "Unknown"}</span>
            <div className="bar-track">
              <div className="bar-fill" style={{ width: `${width}%` }} />
            </div>
            <strong>{score.toFixed(2)}</strong>
          </div>
        );
      })}
    </div>
  );
}

function CompetitorList({
  competitors,
  label,
}: {
  competitors: CompetitorResponse[];
  label: string;
}) {
  if (competitors.length === 0) {
    return <p className="empty-state">No {label} competitors discovered.</p>;
  }

  return (
    <div className="competitor-section">
      <CompetitorBars competitors={competitors} />

      <div className="competitor-list">
        {competitors.map((competitor) => (
          <details className="competitor-card" key={competitor.id}>
            <summary>
              <span>{competitor.name || "Unknown competitor"}</span>
              <strong>
                {(competitor.similarity_score ?? 0).toFixed(2)}
              </strong>
            </summary>
            <a href={competitor.url} target="_blank" rel="noreferrer">
              {competitor.url}
            </a>
            <KeyValueList data={competitor.json_profile} />
          </details>
        ))}
      </div>
    </div>
  );
}

function ReportHighlights({ report }: { report?: JsonMap | null }) {
  if (!report || Object.keys(report).length === 0) {
    return <p className="empty-state">No report highlights are available yet.</p>;
  }

  const keys = [
    "positioning_comparison",
    "pricing_comparison",
    "market_saturation_estimate",
  ];

  const available = keys
    .map((key) => [key, report[key]] as const)
    .filter(([, value]) => value);

  if (available.length === 0) {
    return <KeyValueList data={report} />;
  }

  return (
    <dl className="report-highlights">
      {available.map(([key, value]) => (
        <div key={key}>
          <dt>{labelize(key)}</dt>
          <dd>
            {isRecord(value) ? (
              <pre>{JSON.stringify(value, null, 2)}</pre>
            ) : (
              valueToString(value)
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export default function Home() {
  const [url, setUrl] = useState("");
  const [job, setJob] = useState<JobStatusResponse | null>(null);
  const [company, setCompany] = useState<CompanyResponse | null>(null);
  const [competitors, setCompetitors] =
    useState<CompetitorListResponse | null>(null);
  const [report, setReport] = useState<ReportJsonResponse | null>(null);
  const [profileTab, setProfileTab] = useState<TabKey>("business");
  const [competitorTab, setCompetitorTab] =
    useState<CompetitorTab>("local");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const progress = useMemo(() => {
    if (!job) {
      return 0;
    }
    if (job.status === "completed") {
      return 100;
    }
    if (job.status === "failed") {
      return 0;
    }
    if (job.status === "running") {
      return 62;
    }
    return 18;
  }, [job]);

  useEffect(() => {
    if (!job || job.status === "completed" || job.status === "failed") {
      return;
    }

    const timer = window.setInterval(async () => {
      try {
        const status = await apiFetch<JobStatusResponse>(
          `/status/${job.job_id}`,
          { cache: "no-store" },
        );
        setJob(status);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not poll status.");
      }
    }, POLL_INTERVAL_MS);

    return () => window.clearInterval(timer);
  }, [job]);

  useEffect(() => {
    if (job?.status !== "completed" || !job.company_id) {
      return;
    }

    let cancelled = false;

    async function loadResults(companyId: number) {
      try {
        const [companyData, competitorData, reportData] = await Promise.all([
          apiFetch<CompanyResponse>(`/company/${companyId}`, {
            cache: "no-store",
          }),
          apiFetch<CompetitorListResponse>(
            `/company/${companyId}/competitors`,
            { cache: "no-store" },
          ),
          apiFetch<ReportJsonResponse>(`/company/${companyId}/report/json`, {
            cache: "no-store",
          }),
        ]);

        if (!cancelled) {
          setCompany(companyData);
          setCompetitors(competitorData);
          setReport(reportData);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Could not load analysis.",
          );
        }
      }
    }

    loadResults(job.company_id);

    return () => {
      cancelled = true;
    };
  }, [job]);

  async function handleAnalyze(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const cleanUrl = url.trim();
    if (!cleanUrl || !cleanUrl.includes(".")) {
      setError("Please enter a valid domain, for example example.com.");
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setCompany(null);
    setCompetitors(null);
    setReport(null);

    try {
      const response = await apiFetch<AnalyzeResponse>("/analyze", {
        method: "POST",
        body: JSON.stringify({ url: cleanUrl }),
      });

      setJob({
        job_id: response.job_id,
        status: response.status,
        progress: response.message,
      });
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        setError("An analysis is already running. Please wait for it to finish.");
      } else {
        setError(err instanceof Error ? err.message : "Could not start analysis.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  function handleReset() {
    setUrl("");
    setJob(null);
    setCompany(null);
    setCompetitors(null);
    setReport(null);
    setError(null);
    setProfileTab("business");
    setCompetitorTab("local");
  }

  const profile = company?.json_profile ?? {};
  const visual = company?.visual_profile ?? {};
  const domFeatures = company?.dom_features ?? {};
  const localCompetitors = competitors?.local_competitors ?? [];
  const globalCompetitors = competitors?.global_competitors ?? [];
  const totalCompetitors = localCompetitors.length + globalCompetitors.length;

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <span>CI</span>
          <div>
            <strong>Competitor Intelligence</strong>
            <small>Discovery, comparison, reports</small>
          </div>
        </div>

        <nav className="pipeline-list" aria-label="Pipeline steps">
          <span>Adaptive crawling</span>
          <span>Business extraction</span>
          <span>Visual brand analysis</span>
          <span>Semantic matching</span>
          <span>Competitor discovery</span>
          <span>PDF intelligence report</span>
        </nav>
      </aside>

      <section className="workspace">
        <header className="hero">
          <div>
            <p>AI-powered market research</p>
            <h1>AI Competitor Intelligence Engine</h1>
            <span>
              Analyze a website, discover competitors, compare positioning, and
              generate a report from the FastAPI pipeline.
            </span>
          </div>
        </header>

        <form className="analysis-form" onSubmit={handleAnalyze}>
          <label htmlFor="website-url">Website URL</label>
          <div className="form-row">
            <input
              id="website-url"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              placeholder="https://example.com"
              type="text"
            />
            <button disabled={isSubmitting} type="submit">
              {isSubmitting ? "Starting..." : "Analyze"}
            </button>
            <button className="secondary" onClick={handleReset} type="button">
              Reset
            </button>
          </div>
        </form>

        {error ? <div className="alert error">{error}</div> : null}

        {job ? (
          <section className="status-panel" aria-live="polite">
            <div>
              <StatusBadge status={job.status} />
              <strong>{job.progress || "Queued for analysis"}</strong>
              <small>Job ID: {job.job_id}</small>
            </div>
            <div className="progress-track">
              <div style={{ width: `${progress}%` }} />
            </div>
          </section>
        ) : null}

        {company ? (
          <section className="results-section">
            <div className="section-heading">
              <div>
                <p>Company profile</p>
                <h2>{company.name || "Company Profile"}</h2>
              </div>
              <a href={company.url} target="_blank" rel="noreferrer">
                Visit website
              </a>
            </div>

            <div className="metric-grid">
              <MetricCard label="Industry" value={profile.industry ?? company.industry} />
              <MetricCard
                label="CTA Score"
                value={profile.CTA_aggressiveness_score}
              />
              <MetricCard
                label="Design Modernity"
                value={visual.design_modernity_score}
              />
              <MetricCard
                label="Trust Score"
                value={visual.trust_signal_score}
              />
            </div>

            <div className="tabs" role="tablist" aria-label="Profile details">
              <button
                className={profileTab === "business" ? "active" : ""}
                onClick={() => setProfileTab("business")}
                type="button"
              >
                Business
              </button>
              <button
                className={profileTab === "visual" ? "active" : ""}
                onClick={() => setProfileTab("visual")}
                type="button"
              >
                Visual
              </button>
              <button
                className={profileTab === "dom" ? "active" : ""}
                onClick={() => setProfileTab("dom")}
                type="button"
              >
                DOM
              </button>
            </div>

            <div className="detail-panel">
              {profileTab === "business" ? <KeyValueList data={profile} /> : null}
              {profileTab === "visual" ? <KeyValueList data={visual} /> : null}
              {profileTab === "dom" ? <KeyValueList data={domFeatures} /> : null}
            </div>
          </section>
        ) : null}

        {competitors ? (
          <section className="results-section">
            <div className="section-heading">
              <div>
                <p>Discovered competitors</p>
                <h2>{totalCompetitors} competitors found</h2>
              </div>
            </div>

            <div className="tabs" role="tablist" aria-label="Competitor scope">
              <button
                className={competitorTab === "local" ? "active" : ""}
                onClick={() => setCompetitorTab("local")}
                type="button"
              >
                Local ({localCompetitors.length})
              </button>
              <button
                className={competitorTab === "global" ? "active" : ""}
                onClick={() => setCompetitorTab("global")}
                type="button"
              >
                Global ({globalCompetitors.length})
              </button>
            </div>

            {competitorTab === "local" ? (
              <CompetitorList competitors={localCompetitors} label="local" />
            ) : (
              <CompetitorList competitors={globalCompetitors} label="global" />
            )}
          </section>
        ) : null}

        {job?.status === "completed" && job.company_id ? (
          <section className="report-section">
            <div>
              <p>Intelligence report</p>
              <h2>Comparative analysis highlights</h2>
              <ReportHighlights report={report?.report} />
            </div>
            <a className="download-button" href={reportDownloadUrl(job.company_id)}>
              Download PDF Report
            </a>
          </section>
        ) : null}
      </section>
    </main>
  );
}
