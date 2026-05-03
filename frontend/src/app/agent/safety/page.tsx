"use client";

import { useState, useRef, useEffect } from "react";

interface Interaction {
  drug?: string;
  severity?: string;
  description?: string;
}

interface DrugResult {
  drug?: string;
  rxcui?: string;
  findings?: {
    side_effects?: string[];
    interactions?: Interaction[];
    sources?: { name?: string; url?: string }[];
  };
  risk?: { clinical?: Record<string, any> };
  error?: string;
}

export default function DrugSafetyPage() {
  const [drugInput, setDrugInput] = useState("");
  const [age, setAge] = useState(65);
  const [sex, setSex] = useState("female");
  const [conditions, setConditions] = useState("");
  const [showFlags, setShowFlags] = useState(false);
  const [flags, setFlags] = useState({
    hypertension: false,
    renal_dysfunction: false,
    liver_disease: false,
    stroke: false,
    bleeding_history: false,
    labile_inr: false,
    alcohol_use: false,
  });

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<DrugResult | null>(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [showJson, setShowJson] = useState(false);
  const [dots, setDots] = useState("");

  const reportRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!loading) return;
    const iv = setInterval(
      () => setDots((d) => (d.length >= 3 ? "" : d + ".")),
      400,
    );
    return () => clearInterval(iv);
  }, [loading]);

  const getSeverityColor = (sev?: string) => {
    const s = (sev || "").toLowerCase();
    if (s.includes("major") || s.includes("severe") || s.includes("life"))
      return "#ef4444";
    if (s.includes("moderate")) return "#f59e0b";
    return "#22c55e";
  };

  const getSeverityBg = (sev?: string) => {
    const s = (sev || "").toLowerCase();
    if (s.includes("major") || s.includes("severe") || s.includes("life"))
      return "rgba(239,68,68,0.08)";
    if (s.includes("moderate")) return "rgba(245,158,11,0.08)";
    return "rgba(34,197,94,0.08)";
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!drugInput.trim()) return;

    setLoading(true);
    setResult(null);
    setErrorMsg("");
    setShowJson(false);

    const params = new URLSearchParams({
      drug: drugInput.trim(),
      age: String(age),
      conditions,
    });

    try {
      const res = await fetch(`/api/drug-safety?${params.toString()}`);
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const data = await res.json();
      if (data.error) setErrorMsg(data.error);
      else setResult(data);
    } catch {
      setErrorMsg(
        "❌ Cannot connect to the Drug Safety agent. Make sure the backend is running.",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;600&display=swap');

        .agent-page {
          font-family: 'DM Sans', sans-serif;
          background: #f0f4ff;
          min-height: 100vh;
        }

        .agent-hero {
          background: linear-gradient(135deg, #0a0f2e 0%, #0d1b4b 50%, #0f2460 100%);
          padding: 120px 0 60px;
          position: relative;
          overflow: hidden;
        }
        .agent-hero::before {
          content: '';
          position: absolute;
          inset: 0;
          background-image:
            radial-gradient(circle at 15% 60%, rgba(239,68,68,0.1) 0%, transparent 45%),
            radial-gradient(circle at 80% 20%, rgba(59,130,246,0.1) 0%, transparent 40%);
        }
        .grid-overlay {
          position: absolute;
          inset: 0;
          background-image:
            linear-gradient(rgba(59,130,246,0.06) 1px, transparent 1px),
            linear-gradient(90deg, rgba(59,130,246,0.06) 1px, transparent 1px);
          background-size: 40px 40px;
        }
        .agent-hero .container {
          position: relative;
          z-index: 2;
          max-width: 900px;
          margin: 0 auto;
          padding: 0 24px;
          text-align: center;
        }
        .agent-badge {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          background: rgba(239,68,68,0.15);
          border: 1px solid rgba(239,68,68,0.3);
          border-radius: 100px;
          padding: 6px 16px;
          font-family: 'Space Mono', monospace;
          font-size: 11px;
          letter-spacing: 0.1em;
          color: #fca5a5;
          margin-bottom: 24px;
          text-transform: uppercase;
        }
        .agent-badge-dot {
          width: 6px; height: 6px;
          background: #f87171;
          border-radius: 50%;
          animation: pulse-dot 2s infinite;
        }
        @keyframes pulse-dot {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.5; transform: scale(0.8); }
        }
        .agent-hero h1 {
          font-family: 'DM Sans', sans-serif;
          font-size: clamp(2rem, 5vw, 3.5rem);
          font-weight: 600;
          color: #fff;
          line-height: 1.15;
          margin-bottom: 16px;
          letter-spacing: -0.02em;
        }
        .agent-hero h1 em { font-style: normal; color: #f87171; }
        .agent-hero p {
          color: #94a3b8;
          font-size: 1.05rem;
          max-width: 580px;
          margin: 0 auto 32px;
          line-height: 1.7;
          font-weight: 300;
        }
        .hero-stats { display: flex; justify-content: center; gap: 40px; flex-wrap: wrap; }
        .hero-stat { text-align: center; }
        .hero-stat-num {
          font-family: 'Space Mono', monospace;
          font-size: 1.4rem; color: #f87171; font-weight: 700;
        }
        .hero-stat-label {
          font-size: 0.75rem; color: #64748b;
          text-transform: uppercase; letter-spacing: 0.08em; margin-top: 2px;
        }

        .agent-main { padding: 48px 24px 80px; max-width: 900px; margin: 0 auto; }

        /* ── shared card styles identical to data-manager ── */
        .query-card {
          background: #fff; border-radius: 20px; border: 1px solid #e2e8f0;
          padding: 36px; box-shadow: 0 4px 24px rgba(15,36,96,0.08); margin-bottom: 28px;
        }
        .query-label {
          display: flex; align-items: center; gap: 10px;
          font-size: 0.8rem; font-family: 'Space Mono', monospace;
          letter-spacing: 0.08em; text-transform: uppercase;
          color: #64748b; margin-bottom: 14px;
        }
        .query-label-line { flex: 1; height: 1px; background: #e2e8f0; }

        .drug-input-full {
          width: 100%; border: 1.5px solid #e2e8f0; border-radius: 12px;
          padding: 16px 20px; font-family: 'DM Sans', sans-serif; font-size: 1rem;
          color: #1e293b; background: #f8fafc; outline: none;
          transition: border-color 0.2s, box-shadow 0.2s; margin-bottom: 20px;
        }
        .drug-input-full:focus {
          border-color: #3b82f6; box-shadow: 0 0 0 4px rgba(59,130,246,0.1); background: #fff;
        }
        .drug-input-full::placeholder { color: #94a3b8; }

        .field-row {
          display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px;
        }
        @media(max-width:600px) { .field-row { grid-template-columns: 1fr; } }

        .field-group label {
          display: block; font-size: 0.78rem; font-weight: 500; color: #64748b;
          text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 6px;
        }
        .field-input, .field-select {
          width: 100%; border: 1.5px solid #e2e8f0; border-radius: 12px;
          padding: 13px 16px; font-family: 'DM Sans', sans-serif; font-size: 0.92rem;
          color: #1e293b; background: #f8fafc; outline: none;
          transition: border-color 0.2s, box-shadow 0.2s;
        }
        .field-input:focus, .field-select:focus {
          border-color: #3b82f6; box-shadow: 0 0 0 4px rgba(59,130,246,0.1); background: #fff;
        }
        .field-input::placeholder { color: #94a3b8; }

        .flags-toggle {
          display: inline-flex; align-items: center; gap: 6px;
          background: #f8fafc; border: 1.5px solid #e2e8f0; border-radius: 10px;
          padding: 9px 16px; font-family: 'DM Sans', sans-serif; font-size: 0.82rem;
          font-weight: 500; color: #475569; cursor: pointer; margin-bottom: 14px;
          transition: border-color 0.2s, color 0.2s;
        }
        .flags-toggle:hover { border-color: #3b82f6; color: #3b82f6; }

        .flags-grid {
          display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
          gap: 10px; padding: 16px; background: #f8fafc;
          border-radius: 12px; border: 1px solid #f1f5f9; margin-bottom: 20px;
        }
        .flag-item {
          display: flex; align-items: center; gap: 8px;
          font-size: 0.82rem; color: #475569; cursor: pointer;
        }
        .flag-item input[type="checkbox"] {
          width: 15px; height: 15px; accent-color: #3b82f6; cursor: pointer;
        }

        .query-footer {
          display: flex; align-items: center; justify-content: space-between;
          margin-top: 16px; flex-wrap: wrap; gap: 12px;
        }
        .submit-btn {
          display: inline-flex; align-items: center; gap: 10px;
          background: linear-gradient(135deg, #1d4ed8, #3b82f6);
          color: white; border: none; border-radius: 12px; padding: 14px 28px;
          font-family: 'DM Sans', sans-serif; font-size: 0.95rem; font-weight: 600;
          cursor: pointer; transition: all 0.2s; box-shadow: 0 4px 14px rgba(59,130,246,0.35);
        }
        .submit-btn:hover:not(:disabled) {
          transform: translateY(-1px); box-shadow: 0 6px 20px rgba(59,130,246,0.45);
        }
        .submit-btn:disabled { opacity: 0.7; cursor: not-allowed; transform: none; }
        .spin { animation: spin 1s linear infinite; width: 18px; height: 18px; }
        @keyframes spin { to { transform: rotate(360deg); } }

        .loading-state {
          background: #fff; border-radius: 20px; border: 1px solid #e2e8f0;
          padding: 48px 36px; text-align: center; box-shadow: 0 4px 24px rgba(15,36,96,0.08);
        }
        .loading-icon {
          width: 56px; height: 56px; margin: 0 auto 20px; border-radius: 16px;
          background: linear-gradient(135deg, #1d4ed8, #3b82f6);
          display: flex; align-items: center; justify-content: center; font-size: 1.5rem;
        }
        .loading-bar-track {
          width: 200px; height: 3px; background: #e2e8f0;
          border-radius: 100px; margin: 20px auto 0; overflow: hidden;
        }
        .loading-bar-fill {
          height: 100%; width: 40%;
          background: linear-gradient(90deg, #3b82f6, #818cf8);
          border-radius: 100px; animation: loading-slide 1.5s ease-in-out infinite;
        }
        @keyframes loading-slide {
          0% { transform: translateX(-200%); } 100% { transform: translateX(600%); }
        }

        .error-box {
          background: #fff5f5; border: 1px solid #fecaca; border-radius: 14px;
          padding: 18px 20px; color: #dc2626; font-size: 0.88rem; margin-bottom: 24px;
        }

        .results-card {
          background: #fff; border-radius: 20px; border: 1px solid #e2e8f0;
          overflow: hidden; box-shadow: 0 4px 24px rgba(15,36,96,0.08);
          animation: fadeUp 0.4s ease;
        }
        @keyframes fadeUp {
          from { opacity: 0; transform: translateY(16px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        .results-toolbar {
          display: flex; align-items: center; justify-content: space-between;
          padding: 16px 24px; border-bottom: 1px solid #f1f5f9;
          background: #f8fafc; flex-wrap: wrap; gap: 10px;
        }
        .results-drug-name {
          display: flex; align-items: center; gap: 8px;
          font-weight: 600; font-size: 1rem; color: #1e293b;
        }
        .rxcui-badge {
          font-family: 'Space Mono', monospace; font-size: 0.68rem;
          background: #eff6ff; border: 1px solid #bfdbfe;
          border-radius: 6px; padding: 3px 8px; color: #1d4ed8;
        }
        .toolbar-actions { display: flex; gap: 8px; }
        .action-btn {
          display: inline-flex; align-items: center; gap: 6px;
          border: 1.5px solid #e2e8f0; border-radius: 9px; padding: 7px 14px;
          font-family: 'DM Sans', sans-serif; font-size: 0.8rem; font-weight: 500;
          cursor: pointer; background: #fff; color: #475569; transition: all 0.15s;
        }
        .action-btn:hover { border-color: #3b82f6; color: #3b82f6; }
        .action-btn.green { background: #f0fdf4; border-color: #bbf7d0; color: #16a34a; }
        .action-btn.green:hover { background: #dcfce7; border-color: #86efac; }

        .results-body { padding: 28px 32px; display: flex; flex-direction: column; gap: 28px; }

        .result-section h4 {
          font-family: 'Space Mono', monospace; font-size: 0.72rem;
          letter-spacing: 0.1em; text-transform: uppercase; color: #94a3b8;
          margin-bottom: 14px; display: flex; align-items: center; gap: 8px;
        }
        .result-section h4::after { content: ''; flex: 1; height: 1px; background: #f1f5f9; }

        .effects-list { display: flex; flex-wrap: wrap; gap: 8px; }
        .effect-tag {
          background: #f8fafc; border: 1px solid #e2e8f0;
          border-radius: 8px; padding: 5px 12px; font-size: 0.8rem; color: #475569;
        }

        .interaction-item {
          border-radius: 12px; padding: 14px 16px; margin-bottom: 10px; border-left: 3px solid;
        }
        .interaction-top {
          display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px;
        }
        .interaction-drug { font-weight: 600; font-size: 0.88rem; color: #1e293b; }
        .severity-badge {
          font-family: 'Space Mono', monospace; font-size: 0.65rem;
          letter-spacing: 0.06em; text-transform: uppercase;
          padding: 3px 8px; border-radius: 6px; font-weight: 700;
        }
        .interaction-desc { font-size: 0.82rem; color: #64748b; line-height: 1.5; }

        .risk-grid {
          display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 12px;
        }
        .risk-item {
          background: #f8fafc; border: 1px solid #e2e8f0;
          border-radius: 12px; padding: 14px 16px; text-align: center;
        }
        .risk-score {
          font-family: 'Space Mono', monospace; font-size: 1.4rem; font-weight: 700; color: #1d4ed8;
        }
        .risk-name {
          font-size: 0.72rem; color: #94a3b8;
          text-transform: uppercase; letter-spacing: 0.06em; margin-top: 4px;
        }

        .sources-list { display: flex; flex-direction: column; gap: 6px; }
        .source-item {
          font-size: 0.8rem; color: #3b82f6; text-decoration: none;
          display: flex; align-items: center; gap: 6px;
        }
        .source-item:hover { text-decoration: underline; }

        .json-block {
          background: #0f172a; border-radius: 12px; padding: 20px;
          font-family: 'Space Mono', monospace; font-size: 0.72rem;
          color: #94a3b8; overflow: auto; max-height: 400px; line-height: 1.6;
        }
      `}</style>

      <div className="agent-page">
        {/* Hero */}
        <section className="agent-hero">
          <div className="grid-overlay" />
          <div className="container">
            <div className="agent-badge">
              <span className="agent-badge-dot" />
              Drug Safety Agent · Active
            </div>
            <h1>
              AI-Powered Drug <em>Safety</em> Analysis
            </h1>
            <p>
              Enter a drug name and patient profile. Our agent searches trusted
              pharmacological sources, detects side effects, interactions, and
              computes clinical risk scores.
            </p>
            <div className="hero-stats">
              <div className="hero-stat">
                <div className="hero-stat-num">openFDA</div>
                <div className="hero-stat-label">Primary source</div>
              </div>
              <div className="hero-stat">
                <div className="hero-stat-num">Real-time</div>
                <div className="hero-stat-label">Analysis</div>
              </div>
              <div className="hero-stat">
                <div className="hero-stat-num">HAS-BLED</div>
                <div className="hero-stat-label">Risk scoring</div>
              </div>
            </div>
          </div>
        </section>

        <div className="agent-main">
          {/* Form */}
          <div className="query-card">
            <form onSubmit={handleSubmit}>
              <div className="query-label">
                <span>Drug name</span>
                <span className="query-label-line" />
              </div>
              <input
                className="drug-input-full"
                type="text"
                placeholder="e.g., aspirin, warfarin, metformin..."
                value={drugInput}
                onChange={(e) => setDrugInput(e.target.value)}
              />

              <div className="query-label">
                <span>Patient profile</span>
                <span className="query-label-line" />
              </div>
              <div className="field-row">
                <div className="field-group">
                  <label>Age</label>
                  <input
                    className="field-input"
                    type="number"
                    min={0}
                    max={130}
                    value={age}
                    onChange={(e) => setAge(Number(e.target.value))}
                  />
                </div>
                <div className="field-group">
                  <label>Sex</label>
                  <select
                    className="field-select"
                    value={sex}
                    onChange={(e) => setSex(e.target.value)}
                  >
                    <option value="female">Female</option>
                    <option value="male">Male</option>
                  </select>
                </div>
                <div className="field-group" style={{ gridColumn: "1 / -1" }}>
                  <label>Conditions (comma-separated)</label>
                  <input
                    className="field-input"
                    type="text"
                    placeholder="e.g., hypertension, diabetes..."
                    value={conditions}
                    onChange={(e) => setConditions(e.target.value)}
                  />
                </div>
              </div>

              <button
                type="button"
                className="flags-toggle"
                onClick={() => setShowFlags(!showFlags)}
              >
                <svg
                  width="13"
                  height="13"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                >
                  <polyline
                    points={showFlags ? "18 15 12 9 6 15" : "6 9 12 15 18 9"}
                  />
                </svg>
                Clinical flags {showFlags ? "▲" : "▼"}
              </button>

              {showFlags && (
                <div className="flags-grid">
                  {Object.entries(flags).map(([key, val]) => (
                    <label key={key} className="flag-item">
                      <input
                        type="checkbox"
                        checked={val}
                        onChange={(e) =>
                          setFlags((f) => ({ ...f, [key]: e.target.checked }))
                        }
                      />
                      {key
                        .replace(/_/g, " ")
                        .replace(/\b\w/g, (c) => c.toUpperCase())}
                    </label>
                  ))}
                </div>
              )}

              <div className="query-footer">
                <button type="submit" className="submit-btn" disabled={loading}>
                  {loading ? (
                    <>
                      <svg
                        className="spin"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                      >
                        <path
                          d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                          strokeOpacity="0.25"
                        />
                        <path d="M21 12a9 9 0 00-9-9" />
                      </svg>
                      Analyzing{dots}
                    </>
                  ) : (
                    <>
                      <svg
                        width="16"
                        height="16"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2.5"
                      >
                        <path d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                      </svg>
                      Analyze Drug Safety
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>

          {/* Loading */}
          {loading && (
            <div className="loading-state">
              <div className="loading-icon">🛡️</div>
              <p style={{ color: "#475569", fontWeight: 500, marginBottom: 4 }}>
                Scanning databases{dots}
              </p>
              <p style={{ color: "#94a3b8", fontSize: "0.82rem" }}>
                Querying openFDA · Detecting interactions · Computing risk
                scores
              </p>
              <div className="loading-bar-track">
                <div className="loading-bar-fill" />
              </div>
            </div>
          )}

          {/* Error */}
          {errorMsg && !loading && <div className="error-box">{errorMsg}</div>}

          {/* Results */}
          {result && !loading && (
            <div className="results-card">
              <div className="results-toolbar">
                <div className="results-drug-name">
                  🛡️ {result.drug || drugInput}
                  {result.rxcui && (
                    <span className="rxcui-badge">RXCUI: {result.rxcui}</span>
                  )}
                </div>
                <div className="toolbar-actions">
                  <button
                    className="action-btn green"
                    onClick={() => window.print()}
                  >
                    <svg
                      width="13"
                      height="13"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.5"
                    >
                      <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3" />
                    </svg>
                    Export PDF
                  </button>
                  <button
                    className="action-btn"
                    onClick={() => setShowJson(!showJson)}
                  >
                    <svg
                      width="13"
                      height="13"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.5"
                    >
                      <polyline points="16 18 22 12 16 6" />
                      <polyline points="8 6 2 12 8 18" />
                    </svg>
                    {showJson ? "Hide" : "JSON"}
                  </button>
                </div>
              </div>

              <div className="results-body" ref={reportRef}>
                {result.findings?.side_effects &&
                  result.findings.side_effects.length > 0 && (
                    <div className="result-section">
                      <h4>⚠️ Side Effects</h4>
                      <div className="effects-list">
                        {result.findings.side_effects.map((se, i) => (
                          <span key={i} className="effect-tag">
                            {se}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                {result.findings?.interactions &&
                  result.findings.interactions.length > 0 && (
                    <div className="result-section">
                      <h4>⚡ Drug Interactions</h4>
                      {result.findings.interactions.map((inter, i) => (
                        <div
                          key={i}
                          className="interaction-item"
                          style={{
                            borderLeftColor: getSeverityColor(inter.severity),
                            background: getSeverityBg(inter.severity),
                          }}
                        >
                          <div className="interaction-top">
                            <span className="interaction-drug">
                              {inter.drug || `Interaction ${i + 1}`}
                            </span>
                            {inter.severity && (
                              <span
                                className="severity-badge"
                                style={{
                                  color: getSeverityColor(inter.severity),
                                  background: getSeverityBg(inter.severity),
                                }}
                              >
                                {inter.severity}
                              </span>
                            )}
                          </div>
                          {inter.description && (
                            <p className="interaction-desc">
                              {inter.description}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                {result.risk?.clinical &&
                  Object.keys(result.risk.clinical).length > 0 && (
                    <div className="result-section">
                      <h4>📊 Clinical Risk Scores</h4>
                      <div className="risk-grid">
                        {Object.entries(result.risk.clinical).map(
                          ([key, val]) => (
                            <div key={key} className="risk-item">
                              <div className="risk-score">{String(val)}</div>
                              <div className="risk-name">
                                {key.replace(/_/g, " ")}
                              </div>
                            </div>
                          ),
                        )}
                      </div>
                    </div>
                  )}

                {result.findings?.sources &&
                  result.findings.sources.length > 0 && (
                    <div className="result-section">
                      <h4>📚 Sources</h4>
                      <div className="sources-list">
                        {result.findings.sources.map((src, i) =>
                          src.url ? (
                            <a
                              key={i}
                              className="source-item"
                              href={src.url}
                              target="_blank"
                              rel="noreferrer"
                            >
                              <svg
                                width="12"
                                height="12"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2.5"
                              >
                                <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6M15 3h6v6M10 14L21 3" />
                              </svg>
                              {src.name || src.url}
                            </a>
                          ) : (
                            <span
                              key={i}
                              className="source-item"
                              style={{ color: "#64748b", cursor: "default" }}
                            >
                              {src.name}
                            </span>
                          ),
                        )}
                      </div>
                    </div>
                  )}
              </div>

              {showJson && (
                <div style={{ padding: "0 32px 28px" }}>
                  <pre className="json-block">
                    {JSON.stringify(result, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
