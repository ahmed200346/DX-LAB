"use client";

import { useState, useRef, useEffect } from "react";

interface Interaction {
  drug?: string;
  severity?: string;
  description?: string;
}

interface DrugResult {
  drug: string;
  rxcui?: string;
  findings?: {
    side_effects?: string | string[];
    interactions?: Interaction[] | string;
    sources?: { name?: string; url?: string }[];
  };
  risk?: {
    clinical?: {
      has_bled?: { score: number; category: string; components?: any };
      tisdale?: { score: number; category: string; components?: any };
      major_interaction?: boolean;
    };
  };
  error?: string;
}

interface MultiDrugResponse {
  results: DrugResult[];
  cross_interactions: Array<{
    drug_a: string;
    drug_b: string;
    severity: string;
    description: string;
  }>;
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
  const [multiResult, setMultiResult] = useState<MultiDrugResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [showJson, setShowJson] = useState(false);
  const [dots, setDots] = useState("");
  const [expandedDrug, setExpandedDrug] = useState<string | null>(null);

  const reportRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!loading) return;
    const iv = setInterval(() => setDots((d) => (d.length >= 3 ? "" : d + ".")), 400);
    return () => clearInterval(iv);
  }, [loading]);

  // Helper: icon for side effects
  const getSideEffectIcon = (term: string): string => {
    const lower = term.toLowerCase();
    if (lower.includes("headache")) return "🤕";
    if (lower.includes("nausea")) return "🤢";
    if (lower.includes("vomit")) return "🤮";
    if (lower.includes("diarrhea")) return "💩";
    if (lower.includes("constipation")) return "🚽";
    if (lower.includes("rash")) return "🌿";
    if (lower.includes("pain")) return "💢";
    if (lower.includes("fatigue")) return "😴";
    if (lower.includes("dizzy")) return "🌀";
    if (lower.includes("cough")) return "😷";
    if (lower.includes("dyspnea") || lower.includes("dyspnoea")) return "🫁";
    if (lower.includes("diabetes")) return "🍬";
    if (lower.includes("muscle")) return "💪";
    return "⚠️";
  };

  const extractInteractionDrugs = (text: string): string[] => {
    if (!text) return [];
    const drugSet = new Set<string>();
    const examplesRegex = /Examples?:?\s*([^.]+(?:\.\s*[A-Z][a-z]+[^.]*)?)/gi;
    let match;
    while ((match = examplesRegex.exec(text)) !== null) {
      const exampleLine = match[1];
      const candidates = exampleLine.split(/(?:,|\band\b|•|\n)/);
      for (let cand of candidates) {
        let drug = cand.trim().replace(/^\W+/, "").replace(/\s+$/, "");
        if (drug.length > 2 && drug.length < 50 && !drug.toLowerCase().includes("table") && !drug.toLowerCase().includes("clinical impact")) {
          drugSet.add(drug);
        }
      }
    }
    const bulletRegex = /(?:^|\n)\s*[•\-*○§#\d.]+\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)/gm;
    while ((match = bulletRegex.exec(text)) !== null) {
      let drug = match[1].trim();
      if (drug.length > 2 && !drug.toLowerCase().includes("table")) drugSet.add(drug);
    }
    const commonDrugs = [
      "Carbonic anhydrase inhibitors", "Topiramate", "Zonisamide", "Acetazolamide", "Dichlorphenamide",
      "Ranolazine", "Vandetanib", "Dolutegravir", "Cimetidine", "Alcohol", "Insulin secretagogues",
      "Sulfonylurea", "Insulin", "Thiazides", "Corticosteroids", "Phenothiazines", "Estrogens",
      "Oral contraceptives", "Phenytoin", "Nicotinic acid", "Sympathomimetics", "Calcium channel blockers",
      "Isoniazid", "Cyclosporine", "Gemfibrozil", "Rifampin", "Clarithromycin", "Itraconazole",
      "Ketoconazole", "Erythromycin", "Colchicine", "Niacin", "Grapefruit juice", "Warfarin",
      "Aspirin", "Clopidogrel", "Digoxin"
    ];
    for (const drug of commonDrugs) {
      if (text.toLowerCase().includes(drug.toLowerCase())) {
        drugSet.add(drug);
      }
    }
    const suchAsRegex = /such as ([^.]{5,100}?)(?=\.|;| and | or |$)/gi;
    while ((match = suchAsRegex.exec(text)) !== null) {
      const part = match[1];
      const candidates = part.split(/(?:,|\band\b)/);
      for (let cand of candidates) {
        let drug = cand.trim();
        if (drug.length > 2 && drug.length < 50 && !drug.toLowerCase().includes("such as")) {
          drugSet.add(drug);
        }
      }
    }
    return Array.from(drugSet).sort();
  };

  const getClinicalScore = (obj: any): number | null => {
    if (obj === null || obj === undefined) return null;
    if (typeof obj === "number") return obj;
    if (typeof obj === "object" && "score" in obj) return obj.score;
    return null;
  };

  const formatRiskValue = (val: any): string => {
    const score = getClinicalScore(val);
    if (score !== null) return score.toString();
    if (typeof val === "string") return val;
    if (val === true) return "Yes";
    if (val === false) return "No";
    return "N/A";
  };

  const getRiskLevel = (val: any): { color: string; label: string } => {
    const score = getClinicalScore(val);
    if (score === null) return { color: "#94a3b8", label: "Unknown" };
    if (score >= 3) return { color: "#ef4444", label: "High" };
    if (score >= 1) return { color: "#f59e0b", label: "Moderate" };
    return { color: "#22c55e", label: "Low" };
  };

  const extractCommonSideEffects = (text: string): string[] => {
    const common = ["headache", "dyspepsia", "abdominal pain", "nausea", "diarrhea", "vomiting", "bleeding", "hemorrhage"];
    const lower = text.toLowerCase();
    return common.filter(term => lower.includes(term));
  };

  const getExtraSideEffects = (arr: string[] | undefined): string[] => {
    if (!arr || arr.length <= 1) return [];
    return arr.slice(1).filter(item => item && typeof item === "string" && item.length < 100);
  };

  // Parse input: split by comma, newline, or semicolon
  const parseDrugList = (input: string): string[] => {
    return input.split(/[,\n;]+/).map(d => d.trim()).filter(d => d.length > 0);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const drugList = parseDrugList(drugInput);
    if (drugList.length === 0) return;

    setLoading(true);
    setMultiResult(null);
    setErrorMsg("");
    setShowJson(false);
    setExpandedDrug(null);

    const params = new URLSearchParams({
      drugs: drugList.join(","),
      age: String(age),
      conditions,
      ...flags,
    });
    try {
      const res = await fetch(`http://localhost:8002/analyze-multi?${params.toString()}`);
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const data = await res.json();
      if (data.error) setErrorMsg(data.error);
      else setMultiResult(data);
    } catch {
      setErrorMsg("❌ Cannot connect to the Drug Safety agent. Make sure the backend is running on port 8002.");
    } finally {
      setLoading(false);
    }
  };

  const toggleDrugDetails = (drugName: string) => {
    setExpandedDrug(expandedDrug === drugName ? null : drugName);
  };

  return (
    <>
      {/* Hero Section (unchanged) */}
      <section className="relative z-10 overflow-hidden pt-28 pb-10 md:pt-[150px] md:pb-[70px] xl:pt-[180px] xl:pb-[80px] 2xl:pt-[210px] 2xl:pb-[100px] bg-blue-50">
        <div className="absolute inset-0 opacity-[0.06] pointer-events-none" style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%233b82f6' fill-opacity='1'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`, backgroundRepeat: "repeat", backgroundSize: "120px 120px" }} />
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
              <h1 className="mb-5 text-4xl font-extrabold leading-tight tracking-tight text-black sm:text-5xl md:text-6xl" style={{ fontFamily: "'DM Serif Display', serif" }}>
                AI‑Powered Drug{" "}
                <span className="text-primary italic">Safety</span> Intelligence
              </h1>
              <p className="mx-auto mb-6 max-w-[720px] text-lg font-medium text-body-color" style={{ fontFamily: "'Sora', sans-serif" }}>
                Enter one or more drugs (comma, newline, or semicolon separated) and patient profile. We check interactions between them.
              </p>
              <div className="flex justify-center gap-8 flex-wrap">
                <div className="text-center"><div className="text-sm font-mono text-primary font-semibold">openFDA</div><div className="text-xs text-gray-500 tracking-wide">Primary API</div></div>
                <div className="text-center"><div className="text-sm font-mono text-primary font-semibold">Multi‑drug</div><div className="text-xs text-gray-500 tracking-wide">Interaction Check</div></div>
                <div className="text-center"><div className="text-sm font-mono text-primary font-semibold">HAS‑BLED</div><div className="text-xs text-gray-500 tracking-wide">Risk Scoring</div></div>
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
                    <label htmlFor="drug" className="mb-4 flex items-center text-sm font-semibold text-black dark:text-white" style={{ fontFamily: "'Sora', sans-serif" }}>
                      <span className="mr-2 text-xl">💊</span> Drug(s) – separate with commas, newlines, or semicolons
                    </label>
                    <textarea
                      id="drug"
                      rows={3}
                      className="border-stroke dark:text-body-color-dark dark:shadow-two text-body-color focus:border-primary focus:ring-4 focus:ring-primary/20 dark:focus:border-primary w-full rounded-lg border bg-[#f8f8f8] px-6 py-5 text-lg outline-none transition-all duration-300 dark:border-transparent dark:bg-[#2C303B] shadow-sm"
                      placeholder="e.g.:&#10;aspirin, warfarin&#10;metformin&#10;atorvastatin"
                      value={drugInput}
                      onChange={(e) => setDrugInput(e.target.value)}
                    />
                  </div>

                  <div className="mb-6">
                    <label className="mb-4 flex items-center text-sm font-semibold text-black dark:text-white" style={{ fontFamily: "'Sora', sans-serif" }}>
                      <span className="mr-2 text-xl">🧑‍⚕️</span> Patient Profile
                    </label>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                      <div>
                        <label className="block text-xs font-semibold text-gray-600 uppercase mb-1">Age</label>
                        <input type="number" min={0} max={130} value={age} onChange={(e) => setAge(Number(e.target.value))} className="border-stroke dark:text-body-color-dark dark:shadow-two text-body-color focus:border-primary focus:ring-4 focus:ring-primary/20 dark:focus:border-primary w-full rounded-lg border bg-[#f8f8f8] px-5 py-3 outline-none transition-all duration-300 dark:border-transparent dark:bg-[#2C303B]" />
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-gray-600 uppercase mb-1">Sex</label>
                        <select value={sex} onChange={(e) => setSex(e.target.value)} className="border-stroke dark:text-body-color-dark dark:shadow-two text-body-color focus:border-primary focus:ring-4 focus:ring-primary/20 dark:focus:border-primary w-full rounded-lg border bg-[#f8f8f8] px-5 py-3 outline-none transition-all duration-300 dark:border-transparent dark:bg-[#2C303B]">
                          <option value="female">Female</option>
                          <option value="male">Male</option>
                        </select>
                      </div>
                      <div className="md:col-span-2">
                        <label className="block text-xs font-semibold text-gray-600 uppercase mb-1">Conditions (comma‑separated)</label>
                        <input type="text" placeholder="e.g., hypertension, diabetes..." value={conditions} onChange={(e) => setConditions(e.target.value)} className="border-stroke dark:text-body-color-dark dark:shadow-two text-body-color focus:border-primary focus:ring-4 focus:ring-primary/20 dark:focus:border-primary w-full rounded-lg border bg-[#f8f8f8] px-5 py-3 outline-none transition-all duration-300 dark:border-transparent dark:bg-[#2C303B]" />
                      </div>
                    </div>
                  </div>

                  {/* Flags Toggle */}
                  <div className="mb-6">
                    <button type="button" onClick={() => setShowFlags(!showFlags)} className="inline-flex items-center gap-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-full px-5 py-2 hover:bg-gray-200 transition">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points={showFlags ? "18 15 12 9 6 15" : "6 9 12 15 18 9"} /></svg>
                      Clinical flags {showFlags ? "▲" : "▼"}
                    </button>
                    {showFlags && (
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4 p-4 bg-gray-50 rounded-xl">
                        {Object.entries(flags).map(([key, val]) => (
                          <label key={key} className="flex items-center gap-2 text-sm cursor-pointer">
                            <input type="checkbox" checked={val} onChange={(e) => setFlags(f => ({ ...f, [key]: e.target.checked }))} className="rounded border-gray-300 text-primary focus:ring-primary/20" />
                            <span className="capitalize">{key.replace(/_/g, " ")}</span>
                          </label>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="flex justify-end">
                    <button type="submit" disabled={loading} className="shadow-submit dark:shadow-submit-dark rounded-full bg-primary px-10 py-4 text-lg font-bold text-white transition-all duration-300 ease-in-out hover:bg-blue-600 hover:shadow-lg disabled:opacity-50 flex items-center gap-2">
                      {loading ? (
                        <>
                          <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
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
                  <p className="text-lg font-medium text-gray-800">Scanning databases & checking interactions{dots}</p>
                  <p className="text-sm text-gray-500 mt-1">Querying openFDA · Detecting interactions · Computing risk scores</p>
                  <div className="w-48 h-1.5 bg-gray-200 rounded-full mx-auto mt-6 overflow-hidden"><div className="w-2/3 h-full bg-primary rounded-full animate-pulse"></div></div>
                </div>
              )}

              {/* Error Message */}
              {errorMsg && !loading && (
                <div className="mt-8 rounded-xl bg-red-50 border border-red-200 p-5 text-red-700 text-center">{errorMsg}</div>
              )}

              {/* Results Section */}
              {multiResult && !loading && (
                <div className="mt-8 rounded-xl bg-white border border-gray-100 overflow-hidden shadow-md">
                  <div className="flex flex-wrap items-center justify-between gap-3 p-5 border-b border-gray-100 bg-gray-50/40">
                    <div className="flex items-center gap-3">
                      <span className="text-2xl">🛡️</span>
                      <span className="font-bold text-gray-800 text-lg">Multi‑drug analysis</span>
                    </div>
                    <div className="flex gap-2">
                      <button onClick={() => { const summary = JSON.stringify(multiResult.cross_interactions, null, 2); navigator.clipboard.writeText(summary); alert("Interaction summary copied!"); }} className="px-3 py-1.5 text-xs font-medium bg-gray-200 text-gray-700 rounded-full hover:bg-gray-300 transition flex items-center gap-1">📋 Copy Interactions</button>
                      <button onClick={() => window.print()} className="px-3 py-1.5 text-xs font-medium bg-gray-200 text-gray-700 rounded-full hover:bg-gray-300 transition flex items-center gap-1">🖨️ Export PDF</button>
                      <button onClick={() => setShowJson(!showJson)} className="px-3 py-1.5 text-xs font-medium bg-gray-200 text-gray-700 rounded-full hover:bg-gray-300 transition flex items-center gap-1">{showJson ? "🔽 Hide JSON" : "🔽 View JSON"}</button>
                    </div>
                  </div>

                  <div className="p-6" ref={reportRef}>
                    {/* Cross‑interactions section */}
                    {/* Cross‑interactions section */}
                    <div className="mb-10">
                    <h3 className="text-xl font-bold text-gray-800 mb-4 flex items-center gap-2 border-l-4 border-red-500 pl-3">
                        <span>⚠️</span> Drug‑Drug Interactions
                    </h3>
                    {multiResult.cross_interactions && multiResult.cross_interactions.length > 0 ? (
                        <div className="space-y-3">
                        {multiResult.cross_interactions.map((inter, idx) => (
                            <div key={idx} className="bg-red-50 border border-red-200 rounded-lg p-4">
                            <div className="font-bold text-red-800">{inter.drug_a} ⚡ {inter.drug_b}</div>
                            <div className="text-sm text-red-700 mt-1">{inter.description}</div>
                            <div className="text-xs text-red-600 mt-1 font-semibold">Severity: {inter.severity}</div>
                            </div>
                        ))}
                        </div>
                    ) : (
                        <div className="bg-green-50 border border-green-200 rounded-lg p-4 text-green-800">
                        ✅ No known interactions detected between the entered drugs based on FDA labeling.
                        </div>
                    )}
                    </div>                    

                    {/* Individual drug results (collapsible) */}
                    <div className="space-y-6">
                      {multiResult.results.map((drugRes, idx) => {
                        const sideEffectsArray = Array.isArray(drugRes.findings?.side_effects) 
                          ? drugRes.findings.side_effects 
                          : (drugRes.findings?.side_effects ? [drugRes.findings.side_effects] : []);
                        const mainText = sideEffectsArray[0] || "";
                        const commonTerms = extractCommonSideEffects(mainText);
                        const extraTerms = getExtraSideEffects(sideEffectsArray);
                        const allTerms = [...new Set([...commonTerms, ...extraTerms])].filter(t => t && t.length > 0);
                        
                        let interactionDesc = "";
                        let interactionDrugs: string[] = [];
                        if (drugRes.findings?.interactions) {
                          if (Array.isArray(drugRes.findings.interactions) && drugRes.findings.interactions[0]?.description) {
                            interactionDesc = drugRes.findings.interactions[0].description;
                            interactionDrugs = extractInteractionDrugs(interactionDesc);
                          } else if (typeof drugRes.findings.interactions === "string") {
                            interactionDesc = drugRes.findings.interactions;
                            interactionDrugs = extractInteractionDrugs(interactionDesc);
                          }
                        }
                        const hasInteractions = interactionDrugs.length > 0;
                        const isExpanded = expandedDrug === drugRes.drug;
                        
                        return (
                          <div key={idx} className="border border-gray-200 rounded-xl overflow-hidden">
                            <button
                              onClick={() => toggleDrugDetails(drugRes.drug)}
                              className="w-full text-left p-4 bg-gray-50 hover:bg-gray-100 transition flex justify-between items-center"
                            >
                              <div className="flex items-center gap-3">
                                <span className="text-2xl">💊</span>
                                <span className="font-bold text-gray-800 text-lg">{drugRes.drug}</span>
                                {drugRes.rxcui && <span className="bg-blue-100 text-blue-800 text-xs font-mono px-3 py-1 rounded-full">RXCUI: {drugRes.rxcui}</span>}
                              </div>
                              <span className="text-gray-500">{isExpanded ? "▲" : "▼"}</span>
                            </button>
                            
                            {isExpanded && (
                              <div className="p-5">
                                {/* Adverse Reactions */}
                                <div className="mb-6">
                                  <h4 className="font-bold text-gray-800 mb-2 flex items-center gap-2">⚠️ Adverse Reactions</h4>
                                  {allTerms.length > 0 ? (
                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                                      {allTerms.map(term => (
                                        <div key={term} className="flex items-center gap-2 bg-gray-50 rounded-lg px-3 py-2">
                                          <span className="text-xl">{getSideEffectIcon(term)}</span>
                                          <span className="text-gray-700">{term}</span>
                                        </div>
                                      ))}
                                    </div>
                                  ) : <p className="text-gray-500 italic">No common side effects listed.</p>}
                                </div>
                                
                                {/* Interactions (only the drug's own interaction list) */}
                                <div className="mb-6">
                                  <h4 className="font-bold text-gray-800 mb-2 flex items-center gap-2">⚡ Known Interactions</h4>
                                  {hasInteractions ? (
                                    <div className="flex flex-wrap gap-2">
                                      {interactionDrugs.map(drug => (
                                        <span key={drug} className="bg-yellow-100 text-yellow-800 text-sm px-3 py-1 rounded-full">⚠️ {drug}</span>
                                      ))}
                                    </div>
                                  ) : <p className="text-gray-500 italic">No specific interactions listed in FDA label.</p>}
                                </div>
                                
                                {/* Clinical Risk Scores */}
                                {drugRes.risk?.clinical && (
                                  <div className="mb-6">
                                    <h4 className="font-bold text-gray-800 mb-2 flex items-center gap-2">📊 Clinical Risk Scores</h4>
                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                      {drugRes.risk.clinical.has_bled && (
                                        <div className="bg-white border rounded-lg p-3 text-center">
                                          <div className="text-2xl font-bold" style={{ color: getRiskLevel(drugRes.risk.clinical.has_bled).color }}>
                                            {formatRiskValue(drugRes.risk.clinical.has_bled)}
                                          </div>
                                          <div className="text-xs uppercase text-gray-500">HAS-BLED</div>
                                          <div className="text-xs" style={{ color: getRiskLevel(drugRes.risk.clinical.has_bled).color }}>
                                            {getRiskLevel(drugRes.risk.clinical.has_bled).label}
                                          </div>
                                        </div>
                                      )}
                                      {drugRes.risk.clinical.tisdale && (
                                        <div className="bg-white border rounded-lg p-3 text-center">
                                          <div className="text-2xl font-bold" style={{ color: getRiskLevel(drugRes.risk.clinical.tisdale).color }}>
                                            {formatRiskValue(drugRes.risk.clinical.tisdale)}
                                          </div>
                                          <div className="text-xs uppercase text-gray-500">Tisdale QT Risk</div>
                                          <div className="text-xs" style={{ color: getRiskLevel(drugRes.risk.clinical.tisdale).color }}>
                                            {getRiskLevel(drugRes.risk.clinical.tisdale).label}
                                          </div>
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                )}
                                
                                {/* Sources */}
                                {drugRes.findings?.sources && drugRes.findings.sources.length > 0 && (
                                  <div>
                                    <h4 className="font-bold text-gray-800 mb-2 flex items-center gap-2">📚 Sources</h4>
                                    <div className="flex flex-wrap gap-2">
                                      {drugRes.findings.sources.map((src, i) => (
                                        src.url ? <a key={i} href={src.url} target="_blank" rel="noreferrer" className="bg-gray-100 text-primary px-3 py-1 rounded-full text-xs hover:bg-gray-200">🔗 {src.name}</a>
                                          : <span key={i} className="bg-gray-100 text-gray-600 px-3 py-1 rounded-full text-xs">📄 {src.name}</span>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* JSON View */}
                  {showJson && (
                    <div className="border-t border-gray-100 p-5 bg-gray-50">
                      <pre className="overflow-auto text-xs font-mono bg-gray-900 text-gray-100 p-4 rounded-lg max-h-96">{JSON.stringify(multiResult, null, 2)}</pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </section>

      <style jsx global>{`
        @keyframes float1 { 0%, 100% { transform: translateY(0px) scale(1); } 50% { transform: translateY(-24px) scale(1.06); } }
        @keyframes float2 { 0%, 100% { transform: translateY(0px) scale(1); } 50% { transform: translateY(-18px) scale(1.04); } }
        @keyframes float3 { 0%, 100% { transform: translateY(0px) scale(1); } 50% { transform: translateY(-12px) scale(1.03); } }
        .blob-float-1 { animation: float1 8s ease-in-out infinite; }
        .blob-float-2 { animation: float2 7s ease-in-out 1s infinite; }
        .blob-float-3 { animation: float3 9s ease-in-out 0.5s infinite; }
      `}</style>
    </>
  );
}