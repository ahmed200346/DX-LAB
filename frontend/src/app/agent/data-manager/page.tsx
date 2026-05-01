"use client";

import { useState, useRef, useEffect } from "react";
import { toPng } from "html-to-image";
import jsPDF from "jspdf";
import TargetDashboard from "@/components/Dashboard/TargetDashboard";

export default function AgentPage() {
  const [prompt, setPrompt] = useState("");
  const [resultHtml, setResultHtml] = useState("");
  const [loading, setLoading] = useState(false);
  const [targets, setTargets] = useState<any[]>([]);
  const [sources, setSources] = useState<any[]>([]);
  const [sourceCount, setSourceCount] = useState(0);
  const [validationScore, setValidationScore] = useState(0);
  const [fullResponse, setFullResponse] = useState<any>(null);
  const [showJson, setShowJson] = useState(false);
  const [viewMode, setViewMode] = useState<"report" | "dashboard">("report");
  const [isAssistantOpen, setIsAssistantOpen] = useState(false);
  const [messages, setMessages] = useState<
    { role: "user" | "assistant"; content: string }[]
  >([]);
  const [inputQuestion, setInputQuestion] = useState("");
  const [isAsking, setIsAsking] = useState(false);
  const [dots, setDots] = useState("");

  const reportRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!loading) return;
    const interval = setInterval(() => {
      setDots((d) => (d.length >= 3 ? "" : d + "."));
    }, 400);
    return () => clearInterval(interval);
  }, [loading]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;

    setLoading(true);
    setResultHtml("");
    setFullResponse(null);
    setShowJson(false);
    setTargets([]);
    setSources([]);
    setSourceCount(0);
    setValidationScore(0);
    setViewMode("report");
    setMessages([]);
    setIsAssistantOpen(false);

    try {
      const response = await fetch("http://localhost:8000/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: prompt.trim(),
          top_k: 10,
          data_types: ["text", "pdf"],
          intent: "refresh",
        }),
      });
      const data = await response.json();

      if (data.success) {
        setResultHtml(data.result);
        setTargets(data.targets || []);
        setSources(data.sources || []);
        setSourceCount(data.source_count);
        setValidationScore(data.validation_score);
        setFullResponse(data);
      } else {
        setResultHtml(`<p class='error-msg'>❌ Error: ${data.error}</p>`);
        setFullResponse(data);
      }
    } catch (err) {
      setResultHtml(
        "<p class='error-msg'>❌ Cannot connect to the agent server. Make sure it's running on port 8000.</p>",
      );
    } finally {
      setLoading(false);
    }
  };

  const downloadPDF = async () => {
    if (!reportRef.current) return;
    try {
      const dataUrl = await toPng(reportRef.current, {
        quality: 1,
        pixelRatio: 2,
        cacheBust: true,
      });
      const pdf = new jsPDF({
        unit: "mm",
        format: "a4",
        orientation: "portrait",
      });
      const imgProps = pdf.getImageProperties(dataUrl);
      const pdfWidth = pdf.internal.pageSize.getWidth();
      const pdfHeight = (imgProps.height * pdfWidth) / imgProps.width;
      let heightLeft = pdfHeight;
      let position = 0;
      pdf.addImage(dataUrl, "PNG", 0, position, pdfWidth, pdfHeight);
      heightLeft -= pdf.internal.pageSize.getHeight();
      while (heightLeft > 0) {
        position = heightLeft - pdfHeight;
        pdf.addPage();
        pdf.addImage(dataUrl, "PNG", 0, position, pdfWidth, pdfHeight);
        heightLeft -= pdf.internal.pageSize.getHeight();
      }
      pdf.save(`target_report_${new Date().toISOString().slice(0, 19)}.pdf`);
    } catch (err) {
      console.error("PDF generation failed:", err);
    }
  };

  const sendQuestion = async () => {
    const sessionId = fullResponse?.session_id;
    if (!inputQuestion.trim() || !sessionId) return;
    const userMsg = inputQuestion.trim();
    setMessages((prev) => [...prev, { role: "user", content: userMsg }]);
    setInputQuestion("");
    setIsAsking(true);

    try {
      const res = await fetch("http://localhost:8000/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, question: userMsg }),
      });
      const data = await res.json();
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.answer },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Sorry, an error occurred." },
      ]);
    } finally {
      setIsAsking(false);
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
            radial-gradient(circle at 20% 50%, rgba(59,130,246,0.15) 0%, transparent 50%),
            radial-gradient(circle at 80% 20%, rgba(99,102,241,0.1) 0%, transparent 40%);
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
          background: rgba(59,130,246,0.15);
          border: 1px solid rgba(59,130,246,0.3);
          border-radius: 100px;
          padding: 6px 16px;
          font-family: 'Space Mono', monospace;
          font-size: 11px;
          letter-spacing: 0.1em;
          color: #93c5fd;
          margin-bottom: 24px;
          text-transform: uppercase;
        }

        .agent-badge-dot {
          width: 6px;
          height: 6px;
          background: #60a5fa;
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

        .agent-hero h1 em {
          font-style: normal;
          color: #60a5fa;
        }

        .agent-hero p {
          color: #94a3b8;
          font-size: 1.05rem;
          max-width: 580px;
          margin: 0 auto 32px;
          line-height: 1.7;
          font-weight: 300;
        }

        .hero-stats {
          display: flex;
          justify-content: center;
          gap: 40px;
          flex-wrap: wrap;
        }

        .hero-stat {
          text-align: center;
        }

        .hero-stat-num {
          font-family: 'Space Mono', monospace;
          font-size: 1.4rem;
          color: #60a5fa;
          font-weight: 700;
        }

        .hero-stat-label {
          font-size: 0.75rem;
          color: #64748b;
          text-transform: uppercase;
          letter-spacing: 0.08em;
          margin-top: 2px;
        }

        /* Main section */
        .agent-main {
          padding: 48px 24px 80px;
          max-width: 900px;
          margin: 0 auto;
        }

        /* Query card */
        .query-card {
          background: #fff;
          border-radius: 20px;
          border: 1px solid #e2e8f0;
          padding: 36px;
          box-shadow: 0 4px 24px rgba(15,36,96,0.08);
          margin-bottom: 28px;
        }

        .query-label {
          display: flex;
          align-items: center;
          gap: 10px;
          font-size: 0.8rem;
          font-family: 'Space Mono', monospace;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          color: #64748b;
          margin-bottom: 14px;
        }

        .query-label-line {
          flex: 1;
          height: 1px;
          background: #e2e8f0;
        }

        .query-textarea {
          width: 100%;
          border: 1.5px solid #e2e8f0;
          border-radius: 12px;
          padding: 18px 20px;
          font-family: 'DM Sans', sans-serif;
          font-size: 0.95rem;
          color: #1e293b;
          background: #f8fafc;
          resize: vertical;
          outline: none;
          transition: border-color 0.2s, box-shadow 0.2s;
          line-height: 1.6;
          min-height: 110px;
        }

        .query-textarea:focus {
          border-color: #3b82f6;
          box-shadow: 0 0 0 4px rgba(59,130,246,0.1);
          background: #fff;
        }

        .query-textarea::placeholder {
          color: #94a3b8;
        }

        .query-footer {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-top: 16px;
          flex-wrap: wrap;
          gap: 12px;
        }

        .submit-btn {
          display: inline-flex;
          align-items: center;
          gap: 10px;
          background: linear-gradient(135deg, #1d4ed8, #3b82f6);
          color: white;
          border: none;
          border-radius: 12px;
          padding: 14px 28px;
          font-family: 'DM Sans', sans-serif;
          font-size: 0.95rem;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
          box-shadow: 0 4px 14px rgba(59,130,246,0.35);
        }

        .submit-btn:hover:not(:disabled) {
          transform: translateY(-1px);
          box-shadow: 0 6px 20px rgba(59,130,246,0.45);
        }

        .submit-btn:disabled {
          opacity: 0.7;
          cursor: not-allowed;
          transform: none;
        }

        .spin {
          animation: spin 1s linear infinite;
          width: 18px;
          height: 18px;
        }

        @keyframes spin {
          to { transform: rotate(360deg); }
        }

        .stats-pill {
          display: flex;
          align-items: center;
          gap: 12px;
          background: #f0f9ff;
          border: 1px solid #bae6fd;
          border-radius: 100px;
          padding: 8px 16px;
          font-family: 'Space Mono', monospace;
          font-size: 0.75rem;
          color: #0369a1;
        }

        .stats-pill-divider {
          width: 1px;
          height: 14px;
          background: #bae6fd;
        }

        /* Loading state */
        .loading-state {
          background: #fff;
          border-radius: 20px;
          border: 1px solid #e2e8f0;
          padding: 48px 36px;
          text-align: center;
          box-shadow: 0 4px 24px rgba(15,36,96,0.08);
        }

        .loading-icon {
          width: 56px;
          height: 56px;
          margin: 0 auto 20px;
          border-radius: 16px;
          background: linear-gradient(135deg, #1d4ed8, #3b82f6);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 1.5rem;
        }

        .loading-bar-track {
          width: 200px;
          height: 3px;
          background: #e2e8f0;
          border-radius: 100px;
          margin: 20px auto 0;
          overflow: hidden;
        }

        .loading-bar-fill {
          height: 100%;
          width: 40%;
          background: linear-gradient(90deg, #3b82f6, #818cf8);
          border-radius: 100px;
          animation: loading-slide 1.5s ease-in-out infinite;
        }

        @keyframes loading-slide {
          0% { transform: translateX(-200%); }
          100% { transform: translateX(600%); }
        }

        /* Results card */
        .results-card {
          background: #fff;
          border-radius: 20px;
          border: 1px solid #e2e8f0;
          overflow: hidden;
          box-shadow: 0 4px 24px rgba(15,36,96,0.08);
          animation: fadeUp 0.4s ease;
        }

        @keyframes fadeUp {
          from { opacity: 0; transform: translateY(16px); }
          to { opacity: 1; transform: translateY(0); }
        }

        .results-toolbar {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 16px 24px;
          border-bottom: 1px solid #f1f5f9;
          background: #f8fafc;
          flex-wrap: wrap;
          gap: 10px;
        }

        .view-tabs {
          display: flex;
          background: #e2e8f0;
          border-radius: 10px;
          padding: 3px;
          gap: 2px;
        }

        .view-tab {
          border: none;
          background: transparent;
          border-radius: 8px;
          padding: 7px 16px;
          font-family: 'DM Sans', sans-serif;
          font-size: 0.82rem;
          font-weight: 500;
          cursor: pointer;
          color: #64748b;
          transition: all 0.15s;
        }

        .view-tab.active {
          background: #fff;
          color: #1d4ed8;
          box-shadow: 0 1px 4px rgba(0,0,0,0.08);
        }

        .toolbar-actions {
          display: flex;
          gap: 8px;
        }

        .action-btn {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          border: 1.5px solid #e2e8f0;
          border-radius: 9px;
          padding: 7px 14px;
          font-family: 'DM Sans', sans-serif;
          font-size: 0.8rem;
          font-weight: 500;
          cursor: pointer;
          background: #fff;
          color: #475569;
          transition: all 0.15s;
        }

        .action-btn:hover {
          border-color: #3b82f6;
          color: #3b82f6;
        }

        .action-btn.green {
          background: #f0fdf4;
          border-color: #bbf7d0;
          color: #16a34a;
        }

        .action-btn.green:hover {
          background: #dcfce7;
          border-color: #86efac;
        }

        .results-content {
          padding: 28px 32px;
        }

        .results-content :global(.error-msg) {
          color: #ef4444;
          font-size: 0.9rem;
        }

        .json-block {
          background: #0f172a;
          border-radius: 12px;
          padding: 20px;
          margin-top: 20px;
          font-family: 'Space Mono', monospace;
          font-size: 0.72rem;
          color: #94a3b8;
          overflow: auto;
          max-height: 400px;
          line-height: 1.6;
        }

        /* Floating chat button */
        .chat-float-btn {
          position: fixed;
          bottom: 28px;
          right: 28px;
          z-index: 50;
          width: 56px;
          height: 56px;
          border-radius: 50%;
          background: linear-gradient(135deg, #1d4ed8, #6366f1);
          border: none;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          box-shadow: 0 8px 24px rgba(29,78,216,0.4);
          transition: all 0.2s;
        }

        .chat-float-btn:hover {
          transform: scale(1.08);
          box-shadow: 0 12px 32px rgba(29,78,216,0.5);
        }

        .chat-float-btn svg {
          width: 22px;
          height: 22px;
          color: white;
        }

        /* Chat modal */
        .chat-backdrop {
          position: fixed;
          inset: 0;
          z-index: 50;
          background: rgba(15,23,42,0.6);
          backdrop-filter: blur(4px);
          display: flex;
          align-items: flex-end;
          justify-content: flex-end;
          padding: 24px;
        }

        .chat-modal {
          width: 100%;
          max-width: 400px;
          height: 520px;
          background: #fff;
          border-radius: 20px;
          display: flex;
          flex-direction: column;
          box-shadow: 0 24px 64px rgba(15,23,42,0.2);
          overflow: hidden;
          animation: slideUp 0.25s ease;
        }

        @keyframes slideUp {
          from { opacity: 0; transform: translateY(24px); }
          to { opacity: 1; transform: translateY(0); }
        }

        .chat-header {
          background: linear-gradient(135deg, #0a0f2e, #1d4ed8);
          padding: 16px 20px;
          display: flex;
          align-items: center;
          justify-content: space-between;
        }

        .chat-header-info {
          display: flex;
          align-items: center;
          gap: 10px;
        }

        .chat-avatar {
          width: 36px;
          height: 36px;
          border-radius: 50%;
          background: rgba(255,255,255,0.15);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 1rem;
        }

        .chat-header-name {
          font-weight: 600;
          color: #fff;
          font-size: 0.9rem;
        }

        .chat-header-sub {
          font-size: 0.72rem;
          color: #93c5fd;
          font-family: 'Space Mono', monospace;
        }

        .chat-close-btn {
          background: rgba(255,255,255,0.1);
          border: none;
          border-radius: 8px;
          width: 32px;
          height: 32px;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          color: #fff;
          transition: background 0.15s;
        }

        .chat-close-btn:hover {
          background: rgba(255,255,255,0.2);
        }

        .chat-messages {
          flex: 1;
          overflow-y: auto;
          padding: 16px;
          display: flex;
          flex-direction: column;
          gap: 10px;
          background: #f8fafc;
        }

        .chat-empty {
          text-align: center;
          color: #94a3b8;
          font-size: 0.82rem;
          margin: auto;
          max-width: 220px;
          line-height: 1.6;
        }

        .chat-bubble {
          max-width: 82%;
          padding: 10px 14px;
          border-radius: 14px;
          font-size: 0.85rem;
          line-height: 1.5;
        }

        .chat-bubble.user {
          align-self: flex-end;
          background: linear-gradient(135deg, #1d4ed8, #3b82f6);
          color: white;
          border-bottom-right-radius: 4px;
        }

        .chat-bubble.assistant {
          align-self: flex-start;
          background: #fff;
          color: #1e293b;
          border: 1px solid #e2e8f0;
          border-bottom-left-radius: 4px;
          box-shadow: 0 1px 4px rgba(0,0,0,0.05);
        }

        .chat-thinking {
          align-self: flex-start;
          background: #fff;
          border: 1px solid #e2e8f0;
          border-radius: 14px;
          border-bottom-left-radius: 4px;
          padding: 12px 16px;
          display: flex;
          gap: 4px;
        }

        .thinking-dot {
          width: 6px;
          height: 6px;
          background: #94a3b8;
          border-radius: 50%;
          animation: thinking 1.2s infinite;
        }

        .thinking-dot:nth-child(2) { animation-delay: 0.2s; }
        .thinking-dot:nth-child(3) { animation-delay: 0.4s; }

        @keyframes thinking {
          0%, 60%, 100% { transform: translateY(0); }
          30% { transform: translateY(-6px); }
        }

        .chat-input-area {
          padding: 12px 16px;
          border-top: 1px solid #f1f5f9;
          display: flex;
          gap: 8px;
        }

        .chat-input {
          flex: 1;
          border: 1.5px solid #e2e8f0;
          border-radius: 10px;
          padding: 10px 14px;
          font-family: 'DM Sans', sans-serif;
          font-size: 0.85rem;
          color: #1e293b;
          outline: none;
          transition: border-color 0.2s;
        }

        .chat-input:focus {
          border-color: #3b82f6;
        }

        .chat-send-btn {
          background: linear-gradient(135deg, #1d4ed8, #3b82f6);
          border: none;
          border-radius: 10px;
          width: 40px;
          height: 40px;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: opacity 0.15s;
        }

        .chat-send-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .chat-send-btn svg {
          width: 16px;
          height: 16px;
          color: white;
        }
      `}</style>

      <div className="agent-page">
        {/* Hero */}
        <section className="agent-hero">
          <div className="grid-overlay" />
          <div className="container">
            <div className="agent-badge">
              <span className="agent-badge-dot" />
              Data Manager Agent · Active
            </div>
            <h1>
              Intelligent Target <em>Discovery</em>
            </h1>
            <p>
              Ask about drug targets, genes, and diseases. Our multi-agent AI
              searches PubMed, extracts validated targets, and returns
              structured clinical insights.
            </p>
            <div className="hero-stats">
              <div className="hero-stat">
                <div className="hero-stat-num">100M+</div>
                <div className="hero-stat-label">Compounds indexed</div>
              </div>
              <div className="hero-stat">
                <div className="hero-stat-num">PubMed</div>
                <div className="hero-stat-label">Primary source</div>
              </div>
              <div className="hero-stat">
                <div className="hero-stat-num">Real-time</div>
                <div className="hero-stat-label">Processing</div>
              </div>
            </div>
          </div>
        </section>

        {/* Main interface */}
        <div className="agent-main">
          {/* Query card */}
          <div className="query-card">
            <div className="query-label">
              <span>Query</span>
              <span className="query-label-line" />
            </div>
            <form onSubmit={handleSubmit}>
              <textarea
                className="query-textarea"
                rows={4}
                placeholder="e.g., Identify novel targets for triple‑negative breast cancer, or What are the mechanisms of KRAS G12C inhibitor resistance?"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
              />
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
                      Discovering{dots}
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
                        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
                      </svg>
                      Run Discovery Agent
                    </>
                  )}
                </button>

                {sourceCount > 0 && (
                  <div className="stats-pill">
                    <span>{sourceCount} sources</span>
                    <span className="stats-pill-divider" />
                    <span>SGV {validationScore.toFixed(3)}</span>
                  </div>
                )}
              </div>
            </form>
          </div>

          {/* Loading */}
          {loading && (
            <div className="loading-state">
              <div className="loading-icon">⚗️</div>
              <p style={{ color: "#475569", fontWeight: 500, marginBottom: 4 }}>
                Scanning databases{dots}
              </p>
              <p style={{ color: "#94a3b8", fontSize: "0.82rem" }}>
                Searching PubMed · Extracting targets · Validating evidence
              </p>
              <div className="loading-bar-track">
                <div className="loading-bar-fill" />
              </div>
            </div>
          )}

          {/* Results */}
          {resultHtml && !loading && (
            <div className="results-card">
              <div className="results-toolbar">
                <div className="view-tabs">
                  <button
                    className={`view-tab ${viewMode === "report" ? "active" : ""}`}
                    onClick={() => setViewMode("report")}
                  >
                    📄 Report
                  </button>
                  <button
                    className={`view-tab ${viewMode === "dashboard" ? "active" : ""}`}
                    onClick={() => setViewMode("dashboard")}
                  >
                    📊 Dashboard
                  </button>
                </div>

                <div className="toolbar-actions">
                  <button className="action-btn green" onClick={downloadPDF}>
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
                  {fullResponse && (
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
                  )}
                </div>
              </div>

              <div className="results-content" ref={reportRef}>
                {viewMode === "report" && (
                  <div dangerouslySetInnerHTML={{ __html: resultHtml }} />
                )}
                {viewMode === "dashboard" && targets.length > 0 && (
                  <TargetDashboard targets={targets} />
                )}
                {viewMode === "dashboard" && targets.length === 0 && (
                  <div
                    style={{
                      textAlign: "center",
                      padding: "48px 0",
                      color: "#94a3b8",
                    }}
                  >
                    No targets extracted. Try a different query.
                  </div>
                )}
              </div>

              {showJson && fullResponse && (
                <div style={{ padding: "0 32px 28px" }}>
                  <pre className="json-block">
                    {JSON.stringify(fullResponse, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Floating chat button */}
      {fullResponse?.session_id && (
        <button
          className="chat-float-btn"
          onClick={() => setIsAssistantOpen(true)}
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
          </svg>
        </button>
      )}

      {/* Chat modal */}
      {isAssistantOpen && fullResponse?.session_id && (
        <div
          className="chat-backdrop"
          onClick={() => setIsAssistantOpen(false)}
        >
          <div className="chat-modal" onClick={(e) => e.stopPropagation()}>
            <div className="chat-header">
              <div className="chat-header-info">
                <div className="chat-avatar">🤖</div>
                <div>
                  <div className="chat-header-name">AI Assistant</div>
                  <div className="chat-header-sub">Ask about your results</div>
                </div>
              </div>
              <button
                className="chat-close-btn"
                onClick={() => setIsAssistantOpen(false)}
              >
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                >
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>

            <div className="chat-messages">
              {messages.length === 0 && (
                <p className="chat-empty">
                  Ask anything about the retrieved documents or identified
                  targets.
                </p>
              )}
              {messages.map((msg, idx) => (
                <div key={idx} className={`chat-bubble ${msg.role}`}>
                  {msg.content}
                </div>
              ))}
              {isAsking && (
                <div className="chat-thinking">
                  <span className="thinking-dot" />
                  <span className="thinking-dot" />
                  <span className="thinking-dot" />
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            <div className="chat-input-area">
              <input
                type="text"
                className="chat-input"
                value={inputQuestion}
                onChange={(e) => setInputQuestion(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && sendQuestion()}
                placeholder="Ask a question..."
              />
              <button
                className="chat-send-btn"
                onClick={sendQuestion}
                disabled={isAsking}
              >
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                >
                  <line x1="22" y1="2" x2="11" y2="13" />
                  <polygon points="22 2 15 22 11 13 2 9 22 2" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
