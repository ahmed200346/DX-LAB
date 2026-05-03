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
    side_effects?: string | string[];
    interactions?: Interaction[] | string;
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
  const [showFullSideEffects, setShowFullSideEffects] = useState(false);
  const [showFullInteractions, setShowFullInteractions] = useState(false);

  const reportRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!loading) return;
    const iv = setInterval(() => setDots((d) => (d.length >= 3 ? "" : d + ".")), 400);
    return () => clearInterval(iv);
  }, [loading]);

  const getSeverityColor = (sev?: string) => {
    const s = (sev || "").toLowerCase();
    if (s.includes("major") || s.includes("severe") || s.includes("life")) return "#ef4444";
    if (s.includes("moderate")) return "#f59e0b";
    return "#22c55e";
  };

  const getSeverityBg = (sev?: string) => {
    const s = (sev || "").toLowerCase();
    if (s.includes("major") || s.includes("severe") || s.includes("life")) return "rgba(239,68,68,0.08)";
    if (s.includes("moderate")) return "rgba(245,158,11,0.08)";
    return "rgba(34,197,94,0.08)";
  };

  const formatRiskValue = (val: any): string => {
    if (val === null || val === undefined) return "N/A";
    if (typeof val === "number") return val.toString();
    if (typeof val === "string") return val;
    if (typeof val === "object") {
      if ("value" in val) return String(val.value);
      if ("score" in val) return String(val.score);
      if ("risk" in val) return String(val.risk);
      return JSON.stringify(val).slice(0, 20);
    }
    return String(val);
  };

  const getRiskLevel = (val: any): { color: string; label: string } => {
    const num = parseFloat(formatRiskValue(val));
    if (isNaN(num)) return { color: "#94a3b8", label: "Unknown" };
    if (num >= 3) return { color: "#ef4444", label: "High" };
    if (num >= 1) return { color: "#f59e0b", label: "Moderate" };
    return { color: "#22c55e", label: "Low" };
  };

  // Extract common side effects from the long FDA text
  const extractCommonSideEffects = (text: string): string[] => {
    const common = ["headache", "dyspepsia", "abdominal pain", "nausea", "diarrhea", "vomiting", "bleeding", "hemorrhage"];
    const lower = text.toLowerCase();
    return common.filter(term => lower.includes(term));
  };

  // Extract additional side effects from the array (items after the first long string)
  const getExtraSideEffects = (arr: string[] | undefined): string[] => {
    if (!arr || arr.length <= 1) return [];
    return arr.slice(1).filter(item => item && typeof item === "string" && item.length < 100);
  };

  // Extract interaction drug classes from the description text
  const extractInteractionDrugClasses = (desc: string): string[] => {
    const keywords = ["anticoagulants", "antiplatelets", "NSAIDs", "ACE inhibitors", "acetazolamide", "methotrexate", "diuretics", "beta blockers", "oral hypoglycemics", "uricosuric agents"];
    return keywords.filter(kw => desc.toLowerCase().includes(kw));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!drugInput.trim()) return;
    setLoading(true);
    setResult(null);
    setErrorMsg("");
    setShowJson(false);
    setShowFullSideEffects(false);
    setShowFullInteractions(false);

    const params = new URLSearchParams({ drug: drugInput.trim(), age: String(age), conditions });
    try {
      const res = await fetch(`http://localhost:8002/analyze?${params.toString()}`);
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const data = await res.json();
      if (data.error) setErrorMsg(data.error);
      else setResult(data);
    } catch {
      setErrorMsg("❌ Cannot connect to the Drug Safety agent. Make sure the backend is running.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      {/* Hero Section - matches Target Discovery exactly */}
      <section className="relative z-10 overflow-hidden pt-28 pb-10 md:pt-[150px] md:pb-[70px] xl:pt-[180px] xl:pb-[80px] 2xl:pt-[210px] 2xl:pb-[100px] bg-blue-50">
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
                AI‑Powered Drug{" "}
                <span className="text-primary italic">Safety</span> Intelligence
              </h1>
              <p
                className="mx-auto mb-6 max-w-[720px] text-lg font-medium text-body-color"
                style={{ fontFamily: "'Sora', sans-serif" }}
              >
                Enter a drug name and patient profile. Our agent queries openFDA, detects adverse reactions, interactions, and computes clinical risk scores in real time.
              </p>
              <div className="flex justify-center gap-8 flex-wrap">
                <div className="text-center">
                  <div className="text-sm font-mono text-primary font-semibold">openFDA</div>
                  <div className="text-xs text-gray-500 tracking-wide">Primary API</div>
                </div>
                <div className="text-center">
                  <div className="text-sm font-mono text-primary font-semibold">Real‑time</div>
                  <div className="text-xs text-gray-500 tracking-wide">Analysis</div>
                </div>
                <div className="text-center">
                  <div className="text-sm font-mono text-primary font-semibold">HAS‑BLED</div>
                  <div className="text-xs text-gray-500 tracking-wide">Risk Scoring</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Main Form & Results Section */}
      <section className="pb-16 md:pb-20 lg:pb-24 bg-blue-50">
        <div className="container">
          <div className="-mx-4 flex flex-wrap">
            <div className="w-full px-4 lg:w-10/12 xl:w-8/12 mx-auto">
              {/* Query Card */}
              <div className="shadow-three dark:bg-gray-dark rounded-xl bg-white border border-gray-100 px-8 py-10 sm:p-12 dark:shadow-none transition-all hover:shadow-lg">
                <form onSubmit={handleSubmit}>
                  <div className="mb-8">
                    <label
                      htmlFor="drug"
                      className="mb-4 flex items-center text-sm font-semibold text-black dark:text-white"
                      style={{ fontFamily: "'Sora', sans-serif" }}
                    >
                      <span className="mr-2 text-xl">💊</span> Drug Name
                    </label>
                    <input
                      id="drug"
                      type="text"
                      className="border-stroke dark:text-body-color-dark dark:shadow-two text-body-color focus:border-primary focus:ring-4 focus:ring-primary/20 dark:focus:border-primary w-full rounded-lg border bg-[#f8f8f8] px-6 py-5 text-lg outline-none transition-all duration-300 dark:border-transparent dark:bg-[#2C303B] shadow-sm"
                      placeholder="e.g., aspirin, warfarin, metformin..."
                      value={drugInput}
                      onChange={(e) => setDrugInput(e.target.value)}
                      style={{ fontFamily: "'Sora', sans-serif" }}
                    />
                  </div>

                  <div className="mb-6">
                    <label
                      className="mb-4 flex items-center text-sm font-semibold text-black dark:text-white"
                      style={{ fontFamily: "'Sora', sans-serif" }}
                    >
                      <span className="mr-2 text-xl">🧑‍⚕️</span> Patient Profile
                    </label>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                      <div>
                        <label className="block text-xs font-semibold text-gray-600 uppercase mb-1">Age</label>
                        <input
                          type="number"
                          min={0}
                          max={130}
                          value={age}
                          onChange={(e) => setAge(Number(e.target.value))}
                          className="border-stroke dark:text-body-color-dark dark:shadow-two text-body-color focus:border-primary focus:ring-4 focus:ring-primary/20 dark:focus:border-primary w-full rounded-lg border bg-[#f8f8f8] px-5 py-3 outline-none transition-all duration-300 dark:border-transparent dark:bg-[#2C303B]"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-gray-600 uppercase mb-1">Sex</label>
                        <select
                          value={sex}
                          onChange={(e) => setSex(e.target.value)}
                          className="border-stroke dark:text-body-color-dark dark:shadow-two text-body-color focus:border-primary focus:ring-4 focus:ring-primary/20 dark:focus:border-primary w-full rounded-lg border bg-[#f8f8f8] px-5 py-3 outline-none transition-all duration-300 dark:border-transparent dark:bg-[#2C303B]"
                        >
                          <option value="female">Female</option>
                          <option value="male">Male</option>
                        </select>
                      </div>
                      <div className="md:col-span-2">
                        <label className="block text-xs font-semibold text-gray-600 uppercase mb-1">Conditions (comma‑separated)</label>
                        <input
                          type="text"
                          placeholder="e.g., hypertension, diabetes..."
                          value={conditions}
                          onChange={(e) => setConditions(e.target.value)}
                          className="border-stroke dark:text-body-color-dark dark:shadow-two text-body-color focus:border-primary focus:ring-4 focus:ring-primary/20 dark:focus:border-primary w-full rounded-lg border bg-[#f8f8f8] px-5 py-3 outline-none transition-all duration-300 dark:border-transparent dark:bg-[#2C303B]"
                        />
                      </div>
                    </div>
                  </div>

                  {/* Flags Toggle */}
                  <div className="mb-6">
                    <button
                      type="button"
                      onClick={() => setShowFlags(!showFlags)}
                      className="inline-flex items-center gap-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-full px-5 py-2 hover:bg-gray-200 transition"
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                        <polyline points={showFlags ? "18 15 12 9 6 15" : "6 9 12 15 18 9"} />
                      </svg>
                      Clinical flags {showFlags ? "▲" : "▼"}
                    </button>
                    {showFlags && (
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4 p-4 bg-gray-50 rounded-xl">
                        {Object.entries(flags).map(([key, val]) => (
                          <label key={key} className="flex items-center gap-2 text-sm cursor-pointer">
                            <input
                              type="checkbox"
                              checked={val}
                              onChange={(e) => setFlags(f => ({ ...f, [key]: e.target.checked }))}
                              className="rounded border-gray-300 text-primary focus:ring-primary/20"
                            />
                            <span className="capitalize">{key.replace(/_/g, " ")}</span>
                          </label>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="flex justify-end">
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
                          Analyzing{dots}
                        </>
                      ) : (
                        <>⚡ Analyze Drug Safety</>
                      )}
                    </button>
                  </div>
                </form>
              </div>

              {/* Loading State */}
              {loading && (
                <div className="mt-8 rounded-xl bg-white p-10 text-center shadow-md border border-gray-100">
                  <div className="text-4xl mb-3">🛡️</div>
                  <p className="text-lg font-medium text-gray-800">Scanning databases{dots}</p>
                  <p className="text-sm text-gray-500 mt-1">Querying openFDA · Detecting interactions · Computing risk scores</p>
                  <div className="w-48 h-1.5 bg-gray-200 rounded-full mx-auto mt-6 overflow-hidden">
                    <div className="w-2/3 h-full bg-primary rounded-full animate-pulse"></div>
                  </div>
                </div>
              )}

              {/* Error Message */}
              {errorMsg && !loading && (
                <div className="mt-8 rounded-xl bg-red-50 border border-red-200 p-5 text-red-700 text-center">
                  {errorMsg}
                </div>
              )}

              {/* Results Section */}
              {result && !loading && (
                <div className="mt-8 rounded-xl bg-white border border-gray-100 overflow-hidden shadow-md">
                  {/* Toolbar */}
                  <div className="flex flex-wrap items-center justify-between gap-3 p-5 border-b border-gray-100 bg-gray-50/40">
                    <div className="flex items-center gap-3">
                      <span className="text-2xl">🛡️</span>
                      <span className="font-bold text-gray-800 text-lg">{result.drug || drugInput}</span>
                      {result.rxcui && (
                        <span className="bg-blue-100 text-blue-800 text-xs font-mono px-3 py-1 rounded-full">RXCUI: {result.rxcui}</span>
                      )}
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => {
                          const summary = `Drug: ${result.drug}\nRXCUI: ${result.rxcui}\nRisk scores: ${JSON.stringify(result.risk?.clinical)}`;
                          navigator.clipboard.writeText(summary);
                          alert("Copied to clipboard!");
                        }}
                        className="px-3 py-1.5 text-xs font-medium bg-gray-200 text-gray-700 rounded-full hover:bg-gray-300 transition flex items-center gap-1"
                      >
                        📋 Copy Summary
                      </button>
                      <button
                        onClick={() => window.print()}
                        className="px-3 py-1.5 text-xs font-medium bg-gray-200 text-gray-700 rounded-full hover:bg-gray-300 transition flex items-center gap-1"
                      >
                        🖨️ Export PDF
                      </button>
                      <button
                        onClick={() => setShowJson(!showJson)}
                        className="px-3 py-1.5 text-xs font-medium bg-gray-200 text-gray-700 rounded-full hover:bg-gray-300 transition flex items-center gap-1"
                      >
                        {showJson ? "🔽 Hide JSON" : "🔽 View JSON"}
                      </button>
                    </div>
                  </div>

                  <div className="p-6" ref={reportRef}>
                    {/* Side Effects Section */}
                    {(() => {
                      const sideEffectsArray = Array.isArray(result.findings?.side_effects) ? result.findings.side_effects : (result.findings?.side_effects ? [result.findings.side_effects] : []);
                      const mainText = sideEffectsArray[0] || "";
                      const common = extractCommonSideEffects(mainText);
                      const extra = getExtraSideEffects(sideEffectsArray);
                      return (
                        <div className="mb-8">
                          <h3 className="text-md font-bold text-gray-800 mb-3 flex items-center gap-2">
                            <span>⚠️</span> Adverse Reactions & Side Effects
                          </h3>
                          {common.length > 0 && (
                            <div className="flex flex-wrap gap-2 mb-3">
                              {common.map(term => (
                                <span key={term} className="bg-red-100 text-red-800 text-sm px-3 py-1 rounded-full">⚠️ {term}</span>
                              ))}
                            </div>
                          )}
                          {extra.length > 0 && (
                            <div className="flex flex-wrap gap-2 mb-3">
                              {extra.map(term => (
                                <span key={term} className="bg-gray-100 text-gray-700 text-sm px-3 py-1 rounded-full">{term}</span>
                              ))}
                            </div>
                          )}
                          <button
                            onClick={() => setShowFullSideEffects(!showFullSideEffects)}
                            className="text-primary text-sm font-medium hover:underline flex items-center gap-1"
                          >
                            {showFullSideEffects ? "Hide full prescribing information" : "Show full prescribing information"}
                          </button>
                          {showFullSideEffects && (
                            <div className="mt-3 p-4 bg-gray-50 rounded-lg border text-sm max-h-64 overflow-y-auto whitespace-pre-wrap">
                              {mainText}
                            </div>
                          )}
                        </div>
                      );
                    })()}

                    {/* Interactions Section */}
                    {(() => {
                      let interactionDesc = "";
                      let drugClasses: string[] = [];
                      if (result.findings?.interactions) {
                        if (Array.isArray(result.findings.interactions) && result.findings.interactions[0]?.description) {
                          interactionDesc = result.findings.interactions[0].description;
                          drugClasses = extractInteractionDrugClasses(interactionDesc);
                        } else if (typeof result.findings.interactions === "string") {
                          interactionDesc = result.findings.interactions;
                          drugClasses = extractInteractionDrugClasses(interactionDesc);
                        }
                      }
                      return (
                        <div className="mb-8">
                          <h3 className="text-md font-bold text-gray-800 mb-3 flex items-center gap-2">
                            <span>⚡</span> Drug Interactions
                          </h3>
                          {drugClasses.length > 0 && (
                            <div className="flex flex-wrap gap-2 mb-3">
                              {drugClasses.map(cls => (
                                <span key={cls} className="bg-blue-100 text-blue-800 text-sm px-3 py-1 rounded-full">{cls}</span>
                              ))}
                            </div>
                          )}
                          <button
                            onClick={() => setShowFullInteractions(!showFullInteractions)}
                            className="text-primary text-sm font-medium hover:underline flex items-center gap-1"
                          >
                            {showFullInteractions ? "Hide detailed interaction text" : "Show detailed interaction text"}
                          </button>
                          {showFullInteractions && (
                            <div className="mt-3 p-4 bg-gray-50 rounded-lg border text-sm max-h-64 overflow-y-auto whitespace-pre-wrap">
                              {interactionDesc}
                            </div>
                          )}
                        </div>
                      );
                    })()}

                    {/* Clinical Risk Scores */}
                    {result.risk?.clinical && Object.keys(result.risk.clinical).length > 0 && (
                      <div className="mb-8">
                        <h3 className="text-md font-bold text-gray-800 mb-4 flex items-center gap-2">
                          <span>📊</span> Clinical Risk Scores
                        </h3>
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                          {Object.entries(result.risk.clinical).map(([key, val]) => {
                            const { color, label } = getRiskLevel(val);
                            return (
                              <div key={key} className="bg-white border rounded-xl p-4 text-center shadow-sm">
                                <div className="text-3xl font-bold mb-1" style={{ color }}>{formatRiskValue(val)}</div>
                                <div className="text-xs uppercase font-semibold text-gray-500">{key.replace(/_/g, " ")}</div>
                                <div className="text-xs mt-1 font-medium" style={{ color }}>{label}</div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {/* Sources */}
                    {result.findings?.sources && result.findings.sources.length > 0 && (
                      <div>
                        <h3 className="text-md font-bold text-gray-800 mb-3 flex items-center gap-2">
                          <span>📚</span> Information Sources
                        </h3>
                        <div className="flex flex-wrap gap-2">
                          {result.findings.sources.map((src, i) => (
                            src.url ? (
                              <a key={i} href={src.url} target="_blank" rel="noreferrer" className="bg-gray-100 text-primary px-4 py-2 rounded-full text-sm hover:bg-gray-200 transition inline-flex items-center gap-1">
                                🔗 {src.name || src.url}
                              </a>
                            ) : (
                              <span key={i} className="bg-gray-100 text-gray-600 px-4 py-2 rounded-full text-sm">📄 {src.name}</span>
                            )
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* JSON View */}
                  {showJson && (
                    <div className="border-t border-gray-100 p-5 bg-gray-50">
                      <pre className="overflow-auto text-xs font-mono bg-gray-900 text-gray-100 p-4 rounded-lg max-h-96">
                        {JSON.stringify(result, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </section>

      <style jsx global>{`
        /* Blob animations */
        @keyframes float1 {
          0%, 100% { transform: translateY(0px) scale(1); }
          50% { transform: translateY(-24px) scale(1.06); }
        }
        @keyframes float2 {
          0%, 100% { transform: translateY(0px) scale(1); }
          50% { transform: translateY(-18px) scale(1.04); }
        }
        @keyframes float3 {
          0%, 100% { transform: translateY(0px) scale(1); }
          50% { transform: translateY(-12px) scale(1.03); }
        }

        .blob-float-1 {
          animation: float1 8s ease-in-out infinite;
        }
        .blob-float-2 {
          animation: float2 7s ease-in-out 1s infinite;
        }
        .blob-float-3 {
          animation: float3 9s ease-in-out 0.5s infinite;
        }
      `}</style>
    </>
  );
}