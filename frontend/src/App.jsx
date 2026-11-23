import { useEffect, useState } from "react";

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"
).replace(/\/+$/, "");
const REASONS = [
  "MISSING_IN_B",
  "ORPHAN_IN_B",
  "DUPLICATE_IN_B",
  "SPLIT_ENTRY",
  "VALUE_MISMATCH",
  "MISSING_VALUE_IN_B",
];

function formatValue(value) {
  if (value === null || value === undefined) return "";
  const number = Number(value);
  return Number.isFinite(number)
    ? new Intl.NumberFormat("en-IN", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }).format(number)
    : value;
}

async function getJson(url, signal) {
  const response = await fetch(url, { signal });
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.detail || `Request failed (${response.status})`);
  }
  return body;
}

export default function App() {
  const [orgs, setOrgs] = useState([]);
  const [org, setOrg] = useState("ORG-A");
  const [reason, setReason] = useState("");
  const [sort, setSort] = useState("asc");
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState(null);

  const countReasons = (...reasons) =>
    items.filter((item) => reasons.includes(item.reason)).length;
  const summaryStats = [
    {
      label: "Visible findings",
      value: items.length,
      note: reason ? `Filtered by ${reason.replaceAll("_", " ")}` : "Across all reasons",
      tone: "blue",
    },
    {
      label: "Value issues",
      value: countReasons("VALUE_MISMATCH", "MISSING_VALUE_IN_B"),
      note: "Mismatched or missing values",
      tone: "amber",
    },
    {
      label: "Record gaps",
      value: countReasons("MISSING_IN_B", "ORPHAN_IN_B"),
      note: "Missing or orphaned records",
      tone: "rose",
    },
    {
      label: "Duplicate entries",
      value: countReasons("DUPLICATE_IN_B"),
      note: "Repeated entries that do not reconcile",
      tone: "violet",
    },
  ];

  useEffect(() => {
    const controller = new AbortController();
    getJson(`${API_BASE_URL}/api/orgs/`, controller.signal)
      .then((available) => {
        setOrgs(available);
        if (available.length && !available.includes(org)) setOrg(available[0]);
      })
      .catch((requestError) => {
        if (requestError.name !== "AbortError") setError(requestError.message);
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!org) return undefined;
    const controller = new AbortController();
    const params = new URLSearchParams({ org, sort });
    if (reason) params.set("reason", reason);
    setLoading(true);
    setError("");

    getJson(
      `${API_BASE_URL}/api/disagreements/?${params.toString()}`,
      controller.signal,
    )
      .then((data) => {
        setItems(data);
        setLastUpdated(new Date());
      })
      .catch((requestError) => {
        if (requestError.name !== "AbortError") setError(requestError.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [org, reason, sort]);

  return (
    <main className="page-shell">
      <header className="page-header">
        <div>
          <p className="eyebrow">DEALEROS · DATA QUALITY</p>
          <h1>Reconciliation</h1>
          <p className="subtitle">
            Compare operational records with imported settlement entries.
          </p>
        </div>
        <div className="header-status">
          <span className={`connection-status${error ? " is-error" : ""}`}>
            <span className="status-dot" />
            {error
              ? "API unavailable"
              : lastUpdated
                ? `Synced ${lastUpdated.toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}`
                : "Connecting"}
          </span>
          <span className="record-count">
            {loading ? "Loading…" : `${items.length} findings`}
          </span>
        </div>
      </header>

      <section className="controls" aria-label="Reconciliation filters">
        <label>
          Organization
          <select value={org} onChange={(event) => setOrg(event.target.value)}>
            {orgs.map((availableOrg) => (
              <option key={availableOrg} value={availableOrg}>
                {availableOrg}
              </option>
            ))}
          </select>
        </label>
        <label>
          Disagreement reason
          <select value={reason} onChange={(event) => setReason(event.target.value)}>
            <option value="">All reasons</option>
            {REASONS.map((availableReason) => (
              <option key={availableReason} value={availableReason}>
                {availableReason.replaceAll("_", " ")}
              </option>
            ))}
          </select>
        </label>
        <label>
          Sort by value
          <select value={sort} onChange={(event) => setSort(event.target.value)}>
            <option value="asc">Lowest first</option>
            <option value="desc">Highest first</option>
          </select>
        </label>
      </section>

      <section className="summary-grid" aria-label="Live finding summary" aria-live="polite">
        {summaryStats.map((stat) => (
          <article
            className={`summary-card summary-${stat.tone}`}
            key={stat.label}
          >
            <p>{stat.label}</p>
            <strong key={`${org}-${reason}-${sort}-${stat.value}`}>
              {loading ? "—" : stat.value}
            </strong>
            <span>{stat.note}</span>
          </article>
        ))}
      </section>

      {error && <p className="error-banner" role="alert">{error}</p>}

      <section className="table-card" aria-label="Disagreements">
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Reason</th>
                <th>Record ID</th>
                <th>Location</th>
                <th className="numeric">System A Value</th>
                <th className="numeric">System B Value</th>
                <th className="numeric">Difference (B − A)</th>
              </tr>
            </thead>
            <tbody>
              {!loading &&
                !error &&
                items.map((item, index) => (
                  <tr key={`${item.reason}-${item.record_id}-${index}`}>
                    <td>
                      <span className={`reason-badge reason-${item.reason.toLowerCase()}`}>
                        {item.reason.replaceAll("_", " ")}
                      </span>
                    </td>
                    <td className="record-id">{item.record_id || "—"}</td>
                    <td>
                      <span className="location-name">
                        {item.location_name || item.location_id}
                      </span>
                      <span className="location-id">{item.location_id}</span>
                    </td>
                    <td className="numeric">{formatValue(item.system_a_value)}</td>
                    <td className="numeric">{formatValue(item.system_b_value)}</td>
                    <td className="numeric">
                      {formatValue(item.difference)}
                      <details className="details">
                        <summary>Details</summary>
                        <pre>{JSON.stringify(item.details, null, 2)}</pre>
                      </details>
                    </td>
                  </tr>
                ))}
              {!loading && !error && items.length === 0 && (
                <tr>
                  <td className="empty-state" colSpan="6">
                    No disagreements match these filters.
                  </td>
                </tr>
              )}
              {loading && (
                <tr>
                  <td className="empty-state" colSpan="6">Loading findings…</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
