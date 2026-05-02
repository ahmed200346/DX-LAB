"use client";

import { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// ── Score ring (uses inherited font, we’ll apply DM Serif via CSS) ──
function ScoreRing({ score, size = 48 }: { score: number; size?: number }) {
  const radius = 18;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 10) * circumference;
  const strokeColor =
    score >= 8 ? "#10b981" : score >= 6 ? "#f59e0b" : "#ef4444";

  return (
    <svg width={size} height={size} className="inline-block shrink-0">
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="transparent"
        stroke="#e5e7eb"
        strokeWidth={3}
      />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="transparent"
        stroke={strokeColor}
        strokeWidth={3}
        strokeLinecap="round"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
      <text
        x="50%"
        y="50%"
        dominantBaseline="middle"
        textAnchor="middle"
        className="text-xs font-bold"
        fill={strokeColor}
        style={{ fontFamily: "'DM Serif Display', serif" }}
      >
        {score.toFixed(1)}
      </text>
    </svg>
  );
}

export default function HypothesisGeneratorPage() {
  const [prompt, setPrompt] = useState("");
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showJson, setShowJson] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);

  // Floating assistant state
  const [isAssistantOpen, setIsAssistantOpen] = useState(false);
  const [messages, setMessages] = useState<{ role: "user" | "assistant"; content: string }[]>([]);
  const [inputQuestion, setInputQuestion] = useState("");
  const [isAsking, setIsAsking] = useState(false);

  const reportRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") setIsAssistantOpen(false);
    };
    window.addEventListener("keydown", handleEsc);
    return () => window.removeEventListener("keydown", handleEsc);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setShowJson(false);
    setMessages([]);
    setIsAssistantOpen(false);

    try {
      const res = await fetch("http://localhost:8001/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: prompt.trim(), num_hypotheses: 3 }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Request failed");
      }
      const data = await res.json();
      if (data.success) {
        setResult(data);
        setSessionId(data.session_id);
      } else {
        setError(data.error || "Unknown error");
      }
    } catch (err: any) {
      setError(err.message || "Cannot connect to the agent server.");
    } finally {
      setLoading(false);
    }
  };

  const sendQuestion = async () => {
    if (!inputQuestion.trim() || !sessionId) return;
    const userMsg = inputQuestion.trim();
    setMessages((prev) => [...prev, { role: "user", content: userMsg }]);
    setInputQuestion("");
    setIsAsking(true);
    try {
      const res = await fetch("http://localhost:8001/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, question: userMsg }),
      });
      const data = await res.json();
      setMessages((prev) => [...prev, { role: "assistant", content: data.answer }]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Sorry, an error occurred." },
      ]);
    } finally {
      setIsAsking(false);
    }
  };

  const noveltyVariant = (flag: string) => {
    switch (flag) {
      case "novel": return { border: "border-l-green-500", bg: "bg-green-50", text: "text-green-700" };
      case "likely_known": return { border: "border-l-amber-500", bg: "bg-amber-50", text: "text-amber-700" };
      case "verbatim_match": return { border: "border-l-coral-500", bg: "bg-red-50", text: "text-red-700" };
      default: return { border: "border-l-gray-300", bg: "bg-white", text: "text-gray-600" };
    }
  };

  return (
    <>
      {/* Import fonts in layout or global CSS:
          @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=Sora:wght@300;400;500;600;700&display=swap');
          body { font-family: 'Sora', sans-serif; }
          h1, .score-font { font-family: 'DM Serif Display', serif; }
      */}

      {/* Header – updated copy and typography with floating blobs & hexagon pattern */}
        <section className="relative z-10 overflow-hidden pt-28 pb-8 md:pt-[150px] md:pb-[60px] xl:pt-[180px] xl:pb-[80px] 2xl:pt-[210px] 2xl:pb-[100px] bg-blue-50">
        {/* Subtle molecular‑hexagon pattern (base layer) */}
        <div
            className="absolute inset-0 opacity-[0.06] pointer-events-none"
            style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%233b82f6' fill-opacity='1'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
            backgroundRepeat: "repeat",
            backgroundSize: "120px 120px",
            }}
        />

        {/* Floating decorative blobs (semi‑transparent, animated) */}
        <div className="absolute inset-0 pointer-events-none overflow-hidden">
            <div className="absolute -top-28 left-1/4 w-80 h-80 bg-blue-300/20 rounded-full filter blur-3xl opacity-60 blob-float-1" />
            <div className="absolute -bottom-24 right-1/4 w-96 h-96 bg-indigo-300/20 rounded-full filter blur-3xl opacity-60 blob-float-2" />
            <div className="absolute top-1/3 left-3/4 w-56 h-56 bg-purple-300/20 rounded-full filter blur-3xl opacity-50 blob-float-3" />
            <div className="absolute bottom-10 left-10 w-72 h-72 bg-cyan-300/20 rounded-full filter blur-3xl opacity-50 blob-float-1" />
            <div className="absolute top-1/2 left-1/2 w-48 h-48 bg-primary/15 rounded-full filter blur-2xl opacity-60 blob-float-2" />
        </div>

        <div className="container relative z-10">
            <div className="-mx-4 flex flex-wrap items-center">
            <div className="w-full px-4 text-center">
                <h1
                className="mb-5 text-4xl font-extrabold leading-tight tracking-tight text-black sm:text-5xl md:text-6xl"
                style={{ fontFamily: "'DM Serif Display', serif" }}
                >
                Turn Questions into{" "}
                <span className="text-primary italic">Breakthrough Hypotheses</span>
                </h1>
                <p
                className="mx-auto mb-6 max-w-[720px] text-lg font-medium text-body-color"
                style={{ fontFamily: "'Sora', sans-serif" }}
                >
                Ask any biomedical research question. Our multi‑agent system searches
                PubMed, maps the landscape of evidence, and surfaces novel, testable
                research hypotheses.
                </p>
            </div>
            </div>
        </div>
        </section>

      {/* Main Interface */}
      <section className="pb-16 md:pb-20 lg:pb-24 bg-blue-50">
        <div className="container">
          <div className="-mx-4 flex flex-wrap">
            <div className="w-full px-4 lg:w-10/12 xl:w-8/12 mx-auto">
              <div className="shadow-three dark:bg-gray-dark rounded-xl bg-white border border-gray-100 px-8 py-10 sm:p-12 dark:shadow-none transition-all hover:shadow-lg">
                <form onSubmit={handleSubmit}>
                  <div className="mb-8">
                    <label
                      htmlFor="prompt"
                      className="mb-4 flex items-center text-sm font-semibold text-black dark:text-white"
                      style={{ fontFamily: "'Sora', sans-serif" }}
                    >
                      <span className="mr-2 text-xl">💬</span> What would you like to explore?
                    </label>
                    <textarea
                      id="prompt"
                      rows={4}
                      className="border-stroke dark:text-body-color-dark dark:shadow-two text-body-color focus:border-primary focus:ring-4 focus:ring-primary/20 dark:focus:border-primary w-full rounded-lg border bg-[#f8f8f8] px-6 py-5 text-lg outline-none transition-all duration-300 dark:border-transparent dark:bg-[#2C303B] shadow-sm resize-y"
                      placeholder="e.g., KRAS inhibitor resistance in NSCLC"
                      value={prompt}
                      onChange={(e) => setPrompt(e.target.value)}
                      style={{ fontFamily: "'Sora', sans-serif" }}
                    />
                  </div>
                  <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
                    <button
                      type="submit"
                      disabled={loading}
                      className="shadow-submit dark:shadow-submit-dark rounded-full bg-primary px-10 py-4 text-lg font-bold text-white transition-all duration-300 ease-in-out hover:bg-blue-600 hover:shadow-lg disabled:opacity-50 flex items-center gap-2"
                      style={{ fontFamily: "'Sora', sans-serif" }}
                    >
                      {loading ? (
                        <>
                          <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                          </svg>
                          Generating Hypotheses...
                        </>
                      ) : (
                        <>✨ Generate Hypotheses</>
                      )}
                    </button>
                    {result?.gaps && (
                      <span className="text-sm text-body-color dark:text-body-color-dark" style={{ fontFamily: "'Sora', sans-serif" }}>
                        {result.hypotheses?.length || 0} hypotheses found
                      </span>
                    )}
                  </div>
                </form>

                {error && (
                  <div className="bg-red-100 text-red-800 p-4 rounded mb-4" style={{ fontFamily: "'Sora', sans-serif" }}>{error}</div>
                )}

                {result && (
                  <div className="mt-10">
                    {/* Single "Report" button + JSON toggle */}
                    <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
                      <button
                        className="px-4 py-1 rounded-full text-sm font-medium bg-primary text-white shadow"
                        style={{ fontFamily: "'Sora', sans-serif" }}
                      >
                        📄 Report
                      </button>
                      <button
                        onClick={() => setShowJson(!showJson)}
                        className="rounded-full bg-gray-200 px-4 py-1 text-xs font-medium text-gray-700 hover:bg-gray-300 dark:bg-gray-700 dark:text-gray-200"
                        style={{ fontFamily: "'Sora', sans-serif" }}
                      >
                        {showJson ? "Hide JSON" : "Show JSON"}
                      </button>
                    </div>

                    {/* Report content – using DM Serif for section headings */}
                    <div ref={reportRef} className="space-y-8">
                      {/* Gaps & Conflicts side-by-side */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="bg-gradient-to-br from-yellow-50 to-orange-50 border border-yellow-100 rounded-xl p-5 shadow-sm">
                          <div className="flex items-center gap-2 mb-3">
                            <span className="text-2xl">🔍</span>
                            <h2
                              className="font-bold text-gray-800"
                              style={{ fontFamily: "'DM Serif Display', serif" }}
                            >
                              Research Gaps
                            </h2>
                          </div>
                          <pre
                            className="whitespace-pre-wrap text-sm text-gray-700 font-sans leading-relaxed"
                            style={{ fontFamily: "'Sora', sans-serif" }}
                          >
                            {result.gaps}
                          </pre>
                        </div>
                        <div className="bg-gradient-to-br from-red-50 to-pink-50 border border-red-100 rounded-xl p-5 shadow-sm">
                          <div className="flex items-center gap-2 mb-3">
                            <span className="text-2xl">⚠️</span>
                            <h2
                              className="font-bold text-gray-800"
                              style={{ fontFamily: "'DM Serif Display', serif" }}
                            >
                              Conflicts
                            </h2>
                          </div>
                          <pre
                            className="whitespace-pre-wrap text-sm text-gray-700 font-sans leading-relaxed"
                            style={{ fontFamily: "'Sora', sans-serif" }}
                          >
                            {result.conflicts}
                          </pre>
                        </div>
                      </div>

                      {/* Hypotheses cards */}
                      <section>
                        <h2
                          className="text-2xl font-bold text-gray-800 mb-4"
                          style={{ fontFamily: "'DM Serif Display', serif" }}
                        >
                          💡 Hypotheses
                        </h2>
                        <div className="grid grid-cols-1 gap-6">
                          {result.hypotheses?.map((h: any) => {
                            const variant = noveltyVariant(h.novelty_flag);
                            return (
                              <div
                                key={h.index}
                                className={`border-l-4 ${variant.border} rounded-xl bg-white shadow-sm hover:shadow-md transition-shadow p-5 flex flex-col sm:flex-row gap-4`}
                              >
                                <div className="flex items-center justify-center sm:items-start">
                                  <ScoreRing score={h.composite_score} size={56} />
                                </div>
                                <div className="flex-1 space-y-3">
                                  <div className="flex items-center gap-2 flex-wrap">
                                    <span className={`inline-block w-3 h-3 rounded-full ${variant.border.replace("border-l-", "bg-")}`} />
                                    <h3
                                      className="text-lg font-bold text-gray-900"
                                      style={{ fontFamily: "'DM Serif Display', serif" }}
                                    >
                                      Hypothesis {h.index}
                                    </h3>
                                    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${variant.bg} ${variant.text}`} style={{ fontFamily: "'Sora', sans-serif" }}>
                                      {h.novelty_flag.replace("_", " ")}
                                    </span>
                                    <span className="text-xs text-gray-500 ml-auto" style={{ fontFamily: "'Sora', sans-serif" }}>
                                      Impact: {h.impact_score} · Novelty: {h.novelty_score}
                                    </span>
                                  </div>

                                  <p className="text-sm text-gray-800 leading-relaxed" style={{ fontFamily: "'Sora', sans-serif" }}>
                                    <strong>Statement:</strong> {h.statement}
                                  </p>

                                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-2">
                                    <div className="bg-gray-50 rounded-lg p-3 border border-gray-100">
                                      <strong className="text-xs uppercase text-gray-500" style={{ fontFamily: "'Sora', sans-serif" }}>Rationale</strong>
                                      <p className="text-sm mt-1 text-gray-700" style={{ fontFamily: "'Sora', sans-serif" }}>{h.rationale}</p>
                                    </div>
                                    <div className="bg-gray-50 rounded-lg p-3 border border-gray-100">
                                      <strong className="text-xs uppercase text-gray-500" style={{ fontFamily: "'Sora', sans-serif" }}>Experiment</strong>
                                      <p className="text-sm mt-1 text-gray-700" style={{ fontFamily: "'Sora', sans-serif" }}>{h.experiment}</p>
                                    </div>
                                  </div>

                                  <div className="flex flex-wrap items-center gap-2 text-sm text-gray-600" style={{ fontFamily: "'Sora', sans-serif" }}>
                                    <span className="font-medium">Theme:</span>
                                    <span className="bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full text-xs">{h.theme}</span>
                                  </div>

                                  {h.citations?.length > 0 && (
                                    <details className="mt-2 group">
                                      <summary className="cursor-pointer text-sm text-primary hover:underline font-medium" style={{ fontFamily: "'Sora', sans-serif" }}>
                                        View References ({h.citations.length})
                                      </summary>
                                      <ul className="mt-2 space-y-1 pl-4 border-l-2 border-gray-200">
                                        {h.citations.map((url: string, idx: number) => (
                                          <li key={idx} className="text-xs break-all" style={{ fontFamily: "'Sora', sans-serif" }}>
                                            <a href={url} target="_blank" className="text-blue-600 hover:underline" rel="noopener noreferrer">
                                              {url}
                                            </a>
                                          </li>
                                        ))}
                                      </ul>
                                    </details>
                                  )}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </section>

                      {/* Emerging Themes */}
                      {result.themes && (
                        <section>
                          <div className="bg-gradient-to-r from-indigo-50 via-purple-50 to-pink-50 border border-indigo-100 rounded-xl p-6 shadow-sm">
                            <h2
                              className="text-xl font-bold text-gray-800 mb-3"
                              style={{ fontFamily: "'DM Serif Display', serif" }}
                            >
                              🎯 Emerging Themes
                            </h2>
                            <pre
                              className="whitespace-pre-wrap text-sm text-gray-700 font-sans leading-relaxed"
                              style={{ fontFamily: "'Sora', sans-serif" }}
                            >
                              {result.themes}
                            </pre>
                          </div>
                        </section>
                      )}
                    </div>

                    {showJson && result && (
                      <div className="mt-6">
                        <h4 className="font-semibold text-black dark:text-white mb-2" style={{ fontFamily: "'DM Serif Display', serif" }}>📄 Full JSON Response</h4>
                        <pre className="overflow-auto rounded-sm bg-gray-100 p-4 text-xs text-gray-800 dark:bg-gray-900 dark:text-gray-200 max-h-96" style={{ fontFamily: "'Sora', sans-serif" }}>
                          {JSON.stringify(result, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Floating assistant (unchanged) */}
      {sessionId && (
        <button
          onClick={() => setIsAssistantOpen(!isAssistantOpen)}
          className="fixed bottom-24 right-6 z-50 flex items-center justify-center rounded-full bg-primary p-1 shadow-lg hover:bg-primary/90 focus:outline-none transition-all duration-200 hover:scale-105 border-2 border-white"
          aria-label="Open assistant"
        >
          <img
            src="/dexter-avatar.png"
            alt="Assistant"
            className="h-14 w-14 rounded-full object-cover"
          />
        </button>
      )}

      {isAssistantOpen && sessionId && (
        <div className="fixed bottom-24 right-6 z-50 w-[380px] h-[500px] bg-white rounded-xl shadow-2xl flex flex-col overflow-hidden border border-gray-200 dark:bg-gray-800 dark:border-gray-700">
          <div className="flex items-center justify-between bg-primary px-4 py-3 text-white">
            <div className="flex items-center gap-2">
              <img
                src="/dexter-avatar.png"
                alt="Assistant"
                className="h-12 w-12 rounded-full object-cover border-2 border-white"
              />
              <h3 className="font-semibold" style={{ fontFamily: "'Sora', sans-serif" }}>Lab Assistant</h3>
            </div>
            <button
              onClick={() => setIsAssistantOpen(false)}
              className="text-white hover:text-gray-200 transition"
              aria-label="Close"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-gray-50 dark:bg-gray-900">
            {messages.length === 0 && (
              <p className="text-center text-sm text-gray-500 dark:text-gray-400" style={{ fontFamily: "'Sora', sans-serif" }}>
                Ask follow‑up questions about the hypotheses, gaps, or experiments.
              </p>
            )}
            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
                    msg.role === "user"
                      ? "bg-primary text-white"
                      : "bg-white text-gray-800 dark:bg-gray-700 dark:text-gray-200 shadow-sm"
                  }`}
                  style={{ fontFamily: "'Sora', sans-serif" }}
                >
                  {msg.role === "user" ? (
                    msg.content
                  ) : (
                    <div className="markdown-assistant">
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          a: ({ node, ...props }) => (
                            <a {...props} target="_blank" rel="noopener noreferrer" className="text-blue-600 underline" />
                          ),
                          ul: ({ node, ...props }) => <ul className="list-disc pl-4 my-1" {...props} />,
                          ol: ({ node, ...props }) => <ol className="list-decimal pl-4 my-1" {...props} />,
                          p: ({ node, ...props }) => <p className="mb-1" {...props} />,
                        }}
                      >
                        {msg.content}
                      </ReactMarkdown>
                    </div>
                  )}
                </div>
              </div>
            ))}
            {isAsking && (
              <div className="flex justify-start">
                <div className="rounded-lg bg-white px-3 py-2 text-gray-500 text-sm shadow dark:bg-gray-700" style={{ fontFamily: "'Sora', sans-serif" }}>
                  Thinking...
                </div>
              </div>
            )}
          </div>

          <div className="border-t p-3 bg-white dark:bg-gray-800 dark:border-gray-700">
            <div className="flex gap-2">
              <input
                type="text"
                value={inputQuestion}
                onChange={(e) => setInputQuestion(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && sendQuestion()}
                placeholder="Ask a question..."
                className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                style={{ fontFamily: "'Sora', sans-serif" }}
              />
              <button
                onClick={sendQuestion}
                disabled={isAsking}
                className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary/90 disabled:opacity-50"
                style={{ fontFamily: "'Sora', sans-serif" }}
              >
                Send
              </button>
            </div>
          </div>
        </div>
      )}

      <style jsx global>{`
        .markdown-assistant {
          font-size: 0.85rem;
          line-height: 1.4;
        }
        .markdown-assistant ul,
        .markdown-assistant ol {
          margin: 0.25rem 0;
        }
      `}</style>
    </>
  );
}