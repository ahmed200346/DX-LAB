"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { motion, AnimatePresence } from "framer-motion";
import {
  FileText, Download, Share2, FileSearch, CheckCircle2, Clock,
  ScrollText, Loader2, Sparkles, Inbox, ChevronRight, FlaskConical,
  Database, BookOpen, BarChart2, Microscope, Network, BrainCircuit, Dna,
  Zap, ShieldAlert, Lightbulb, AlertTriangle
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { useReporter } from "@/hooks/useReporter";

const REPORT_SECTIONS = [
  {
    id: "exec", title: "Executive Summary", icon: "ScrollText", color: "text-emerald-500", bg: "bg-emerald-500/10", border: "border-emerald-500/20",
    content: "This report summarises the findings of a biomedical discovery query targeting BCL-2 inhibition in Chronic Lymphocytic Leukaemia (CLL). The pipeline identified **2 drug targets** (BCL-2, MCL-1) and **3 small molecules** across **12 validated sources** (SGV = 0.823).\n\nThe lead candidate **Venetoclax-Analog (DX-BCL2-01)** achieved a binding affinity of pKd = 11.4 against BCL-2 (UniProt: P10415), with nanomolar groove occupancy confirmed by Boltz-1 3D structure prediction. Secondary resistance mechanisms via MCL-1 upregulation were identified as the primary clinical liability, consistent with findings in Guieze et al. (2019) and Roberts et al. (2016).",
  },
  {
    id: "targets", title: "Drug Target Analysis", icon: "Dna", color: "text-purple-500", bg: "bg-purple-500/10", border: "border-purple-500/20",
    table: { headers: ["Gene","Protein","Disease","UniProt","Evidence Tier","Top Pathway"], rows: [["BCL-2","Apoptosis regulator Bcl-2","CLL","P10415","Tier 1","Intrinsic Apoptosis"],["MCL-1","Myeloid cell leukemia 1","CLL / Resistance","Q07820","Tier 1","Apoptotic Regulation"]] },
    bullets: ["BCL-2 — PDB Structures: 6O0K, 6QZ8, 4MAN","MCL-1 — Supporting PMIDs: 31560917, 26822266","BCL-2 mutations: G101V (resistance-associated variant)"],
  },
  {
    id: "chemicals", title: "Chemical Landscape", icon: "FlaskConical", color: "text-blue-500", bg: "bg-blue-500/10", border: "border-blue-500/20",
    table: { headers: ["Name","Formula","MW (Da)","Phase","ChEMBL","pKd"], rows: [["Venetoclax-Analog","C45H50ClN7O7S","868.4","Pre-clinical","CHEMBL3137309","11.4"],["Navitoclax","C47H55ClFN7O6S","974.5","Phase II","CHEMBL502835","9.2"],["DXL-102","C24H26FN5O2","451.5","Pre-clinical","—","8.75"]] },
    bullets: ["Venetoclax-Analog: BH3-binding groove occupancy 98%, QED 0.25, SA 3.8","Navitoclax: BCL-xL/BCL-2 dual inhibitor, dose-limited by thrombocytopenia"],
  },
  {
    id: "pathways", title: "Pathway & Network Context", icon: "Network", color: "text-indigo-500", bg: "bg-indigo-500/10", border: "border-indigo-500/20",
    content: "BCL-2 and MCL-1 participate in converging nodes of the intrinsic apoptotic pathway (Reactome: R-HSA-109581). Cross-target pathway overlap includes the PI3K/AKT survival axis and NF-kB signalling, both of which upregulate anti-apoptotic BCL-2 family members under therapeutic pressure.",
    table: { headers: ["Gene","Source","Pathway"], rows: [["BCL-2","Reactome","Intrinsic Pathway for Apoptosis (R-HSA-109581)"],["BCL-2","KEGG","Apoptosis — hsa04210"],["MCL-1","Reactome","Regulation of Apoptosis (R-HSA-169911)"],["MCL-1","KEGG","PI3K-Akt Signaling — hsa04151"]] },
  },
  {
    id: "evidence", title: "Clinical Evidence", icon: "BookOpen", color: "text-amber-500", bg: "bg-amber-500/10", border: "border-amber-500/20",
    sources: [
      { label: "PMID: 31560917", desc: "Guieze et al. — MCL-1 amplification drives venetoclax resistance. Cancer Cell (2019)", score: "0.89" },
      { label: "PMID: 26822266", desc: "Bojarczuk et al. — Microenvironmental BCL-xL upregulation. Blood (2016)", score: "0.85" },
      { label: "PMID: 26815805", desc: "Roberts et al. — Targeting BCL2 with Venetoclax in CLL. NEJM (2016)", score: "0.84" },
      { label: "PMID: 36724018", desc: "Liu et al. — Epigenetic reprogramming drives venetoclax resistance. Blood Adv. (2023)", score: "0.78" },
    ],
  },
  {
    id: "quality", title: "Source Quality Metrics", icon: "BarChart2", color: "text-emerald-500", bg: "bg-emerald-500/10", border: "border-emerald-500/20",
    metrics: [
      { label: "Validation Score (SGV)", value: "0.8230", bar: 82 },
      { label: "Faithfulness", value: "0.92", bar: 92 },
      { label: "Answer Relevancy", value: "0.85", bar: 85 },
      { label: "Context Recall", value: "0.88", bar: 88 },
      { label: "Credibility Score", value: "0.95", bar: 95 },
      { label: "Contradiction Rate", value: "0.20 (low)", bar: 20, invert: true },
    ],
    stats: [
      { label: "Sources Retrieved", value: "12" },
      { label: "Pipeline Latency", value: "1842 ms" },
      { label: "Pipeline Status", value: "success" },
      { label: "Data Types", value: "text, pdf, table" },
    ],
  },
  {
    id: "ner", title: "Interim NER Analysis", icon: "BrainCircuit", color: "text-rose-500", bg: "bg-rose-500/10", border: "border-rose-500/20",
    table: { headers: ["Entity Type","Entities Detected"], rows: [["Genes / Proteins","BCL-2, MCL-1, BCL-xL, BAX, BAK, BIM, PUMA"],["Small Molecules","Venetoclax, Navitoclax, ABT-199, S63845"],["Diseases","CLL, AML, Diffuse Large B-Cell Lymphoma"],["Mutations","G101V (BCL-2), G12C (KRAS co-morbidity)"],["Pathways","Intrinsic Apoptosis, PI3K/AKT, NF-kB"],["Clinical Terms","BH3 Profiling, ADMET, IC50, pKd, TLS Risk"]] },
  },
  {
    id: "discovery", title: "Discovery Agent Output", icon: "Zap", color: "text-cyan-500", bg: "bg-cyan-500/10", border: "border-cyan-500/20",
    content: "The **Discovery Agent** ran a 5-step generative pipeline targeting BCL-2 (P10415). REINVENT generative models produced **250 unique candidates**. After ensemble pKd scoring and ADMET filtering, **3 leads** were selected for Boltz-1 structure prediction and LLM-guided scaffold refinement.",
    table: { headers: ["Rank","Name","SMILES (truncated)","pKd","QED","SA","Status"], rows: [["#1","Venetoclax-Analog","CC1(C)CCC(CN2CCN(c3ccc...)CC2)=C...","11.4","0.25","3.8","Lead"],["#2","DXL-102","C=C(F)C(=O)N1CCN(c2nc(OC...","8.75","0.82","2.3","Lead"],["#3","DXL-103","Cc1cccc(C)c1-n1c(=O)nc2c...","7.21","0.65","1.8","Candidate"]] },
    bullets: ["Pipeline steps: Target Extraction → Candidate Generation (REINVENT) → Property Prediction → Iterative Refinement → Boltz-1 Structure Prediction","Docking Score (Venetoclax-Analog): −10.5 kcal/mol against BCL-2 BH3-binding groove","Lipinski Rule-of-5: MW=868.4, HBD=3, HBA=10, LogP=5.1 — borderline compliant","Boltz-1 3D fold confirmed: 98% groove occupancy, nanomolar affinity (IC50 ≈ 0.01 µM)"],
  },
  {
    id: "safety", title: "Safety Agent Output", icon: "ShieldAlert", color: "text-red-500", bg: "bg-red-500/10", border: "border-red-500/20",
    content: "The **Safety Agent** performed patient-specific ADMET screening for a **68-year-old male with Stage 2 CKD (mild renal impairment)**. One critical risk was flagged.",
    alerts: [
      { level: "critical", label: "Tumor Lysis Syndrome (TLS)", detail: "High risk in CLL patients. Requires mandatory 5-week dose ramp-up and prophylaxis." },
      { level: "warning", label: "Thrombocytopenia (BCL-xL off-target)", detail: "Platelets rely on BCL-xL for survival. Monitor platelet count weekly." },
      { level: "ok", label: "Hepatotoxicity", detail: "No significant ALT/AST elevation predicted." },
    ],
    table: { headers: ["ADMET Parameter","Value","Status"], rows: [["Oral Bioavailability (%F)","58%","Pass"],["CYP3A4 Inhibition","Moderate","Monitor"],["BBB Penetration","Low","Pass"],["hERG IC50",">30 µM","Pass"],["Renal Clearance","Reduced (CKD stage 2)","Adjust dose"]] },
  },
  {
    id: "hypothesis", title: "Hypothesis Agent Output", icon: "Lightbulb", color: "text-violet-500", bg: "bg-violet-500/10", border: "border-violet-500/20",
    content: "The **Hypothesis Agent** synthesised **3 resistance models** ranked by confidence and cross-validated against the Knowledge Hub's vector database.",
    hypotheses: [
      { id: 1, title: "MCL-1 Upregulation Mediating Resistance", confidence: 94, category: "Mechanistic", impact: "High", novelty: "Medium", rationale: "Analysis of 14 clinical trials indicates tumor cells compensate by upregulating MCL-1.", experiment: "CRISPR/Cas9 knockout of MCL-1 in resistant CLL cell lines.", citations: ["PMID: 31560917","PMID: 26815805"] },
      { id: 2, title: "BCL-xL Dependency Switch", confidence: 76, category: "Clinical", impact: "Medium", novelty: "High", rationale: "scRNA-seq reveals sub-populations switching from BCL-2 to BCL-xL dependency.", experiment: "Combinatorial BCL-xL inhibitor + BH3 profiling.", citations: ["PMID: 26822266","Choudhary et al., 2015"] },
      { id: 3, title: "Epigenetic Mitochondrial Escape", confidence: 62, category: "Emerging", impact: "Medium", novelty: "Very High", rationale: "Multi-omic integration suggests epigenetic shifts modify mitochondrial lipid composition.", experiment: "Lipidomic analysis of mitochondrial membranes.", citations: ["PMID: 36724018","Jones et al., 2021"] },
    ],
  },
  {
    id: "method", title: "Methodology", icon: "Microscope", color: "text-slate-400", bg: "bg-slate-400/10", border: "border-slate-400/20",
    bullets: ["Web Search — SearXNG + DuckDuckGo + PubMed + Semantic Scholar","Content Extraction — Jina.ai / trafilatura with domain filtering","Validation — SGV scoring (faithfulness, relevancy, credibility, NLI)","Vectorisation — BAAI/bge-base-en (768-dim) with section-aware PDF chunking","Retrieval — Dense → BM25 → RRF fusion → Cross-encoder → MMR","Target Enrichment — BioNER + Groq LLM + UniProt + PDB + AlphaFold + Reactome/KEGG"],
    meta: "Session: demo_1746315882  |  ACP Version: 3.4",
  },
];

const sectionIconMap: Record<string, React.ElementType> = {
  ScrollText, Dna, FlaskConical, Network, BookOpen, BarChart2, BrainCircuit, Zap, ShieldAlert, Lightbulb, Microscope,
};

export default function ReporterAgentView() {
  const {
    subject, setSubject, isRunning, hasReport,
    currentStep, stepIndex, steps, reportData, error,
    generateReport, reset,
  } = useReporter();

  const [activeSection, setActiveSection] = useState("exec");
  const [reports, setReports] = useState<any[]>([]);

  const handleGenerate = async () => {
    if (!subject.trim()) return;
    await generateReport(subject);
    setReports(prev => [{
      id: Date.now(),
      title: `Pre-clinical Report: ${subject}`,
      date: new Date().toLocaleDateString(),
      type: "Multi-Agent Synthesis",
      status: "Ready",
    }, ...prev]);
  };

  const activeData = REPORT_SECTIONS.find(s => s.id === activeSection)!;

  const downloadPDF = () => {
    const win = window.open('', '_blank');
    if (!win) return;

    const sectionsHTML = REPORT_SECTIONS.map(sec => {
      let body = "";
      if (sec.content) {
        body += `<p style="line-height:1.8;margin-bottom:12px;">${sec.content.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').split('\n\n').join('</p><p style="line-height:1.8;margin-bottom:12px;">')}</p>`;
      }
      if ((sec as any).table) {
        const t = (sec as any).table;
        body += `<table style="width:100%;border-collapse:collapse;margin:16px 0;font-size:11px"><thead><tr>${t.headers.map((h: string) => `<th style="border:1px solid #ddd;padding:6px 10px;background:#f8fafc;text-align:left;font-weight:600;color:#475569">${h}</th>`).join('')}</tr></thead><tbody>${t.rows.map((row: string[]) => `<tr>${row.map((cell: string, j: number) => `<td style="border:1px solid #eee;padding:6px 10px;${j === 0 ? 'font-weight:700;color:#6d28d9' : ''}">${cell}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
      }
      if ((sec as any).bullets) {
        body += `<ul style="margin:12px 0;padding-left:20px">${(sec as any).bullets.map((b: string) => `<li style="margin-bottom:6px;font-size:12px;line-height:1.6">${b}</li>`).join('')}</ul>`;
      }
      if ((sec as any).sources) {
        body += (sec as any).sources.map((s: any) => `<div style="border-left:3px solid #f59e0b;padding:6px 12px;margin:8px 0"><strong style="font-size:11px">${s.label}</strong><p style="font-size:10px;color:#6b7280;margin:2px 0">${s.desc}</p><span style="font-size:10px;color:#059669;font-weight:600">Relevance: ${s.score}</span></div>`).join('');
      }
      if ((sec as any).metrics) {
        body += (sec as any).metrics.map((m: any) => `<div style="margin:8px 0"><div style="display:flex;justify-content:space-between;font-size:11px;margin-bottom:3px"><span>${m.label}</span><strong style="color:${m.invert ? '#ef4444' : '#10b981'}">${m.value}</strong></div><div style="background:#f1f5f9;height:6px;border-radius:999px;overflow:hidden"><div style="background:${m.invert ? '#ef4444' : '#10b981'};width:${m.bar}%;height:100%;border-radius:999px"></div></div></div>`).join('');
      }
      if ((sec as any).alerts) {
        body += (sec as any).alerts.map((a: any) => `<div style="padding:10px 14px;border-radius:8px;margin:8px 0;border-left:4px solid ${a.level === 'critical' ? '#ef4444' : a.level === 'warning' ? '#f59e0b' : '#10b981'};background:${a.level === 'critical' ? '#fef2f2' : a.level === 'warning' ? '#fffbeb' : '#f0fdf4'}"><strong style="font-size:11px">${a.label}</strong><p style="font-size:10px;color:#6b7280;margin:4px 0 0">${a.detail}</p></div>`).join('');
      }
      if ((sec as any).hypotheses) {
        body += (sec as any).hypotheses.map((h: any) => `<div style="border:1px solid #e2e8f0;border-radius:10px;padding:14px;margin:10px 0"><strong style="font-size:12px">${h.id}. ${h.title}</strong><p style="font-size:10px;color:#6b7280;margin:6px 0"><strong>Rationale:</strong> ${h.rationale}</p><p style="font-size:10px;margin:6px 0"><strong>Experiment:</strong> ${h.experiment}</p><p style="font-size:10px;color:#7c3aed">${h.citations.join(' | ')}</p></div>`).join('');
      }
      if ((sec as any).meta) {
        body += `<p style="font-size:10px;font-family:monospace;color:#94a3b8;background:#f8fafc;padding:8px 12px;border-radius:6px;margin-top:12px">${(sec as any).meta}</p>`;
      }
      return `<div style="page-break-inside:avoid;margin-bottom:32px"><h2 style="font-size:15px;font-weight:700;color:#0f172a;border-bottom:2px solid #e2e8f0;padding-bottom:8px;margin-bottom:14px">${sec.title}</h2>${body}</div>`;
    }).join('');

    win.document.write(`<!DOCTYPE html><html><head><title>DX-LAB Discovery Report</title><meta charset="UTF-8"><style>*{box-sizing:border-box;margin:0;padding:0}body{font-family:'Segoe UI',Arial,sans-serif;color:#1e293b;padding:40px;font-size:12px}@media print{body{padding:20px}@page{size:A4;margin:15mm}}</style></head><body><div style="border-bottom:3px solid #10b981;padding-bottom:20px;margin-bottom:28px"><h1 style="font-size:22px;font-weight:800;color:#0f172a">DX-LAB Discovery Report</h1><p style="font-size:12px;color:#64748b;margin-top:4px">Subject: <strong>${subject}</strong></p></div>${sectionsHTML}<div style="margin-top:40px;border-top:1px solid #e2e8f0;padding-top:12px;font-size:10px;color:#94a3b8">Generated by IntelligentTargetDiscoveryAgent v3.4</div></body></html>`);
    win.document.close();
    setTimeout(() => { win.print(); }, 500);
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-2xl font-bold">Reporter Agent</h3>
          <p className="text-gray-600 dark:text-white/40 text-sm mt-1">Multi-agent synthesis report</p>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-400 text-sm">{error}</div>
      )}

      <Card className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 overflow-hidden relative">
        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-emerald-500 to-teal-500" />
        <CardContent className="p-8">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 items-end">
            <div className="md:col-span-3 space-y-2">
              <label className="text-xs font-semibold text-gray-600 dark:text-white/40 uppercase tracking-wider">Report Subject / Molecule / Target</label>
              <Input value={subject} onChange={e => setSubject(e.target.value)} placeholder="Enter report subject, molecule or target area..." className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 h-11 focus:ring-emerald-500/50" onKeyDown={e => { if (e.key === 'Enter') handleGenerate(); }} />
            </div>
            <div className="md:col-span-1">
              <Button onClick={handleGenerate} disabled={isRunning || !subject.trim()} className="w-full bg-emerald-600 hover:bg-emerald-700 text-white h-11 font-bold shadow-lg shadow-emerald-600/20 rounded-lg disabled:opacity-40">
                {isRunning ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <ScrollText className="w-4 h-4 mr-2" />}
                {isRunning ? "Composing..." : "Generate Report"}
              </Button>
            </div>
          </div>

          <AnimatePresence>
            {isRunning && (
              <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="mt-6 space-y-3">
                <Progress value={(stepIndex / steps.length) * 100} className="h-1.5" />
                <p className="text-xs font-mono text-emerald-600 dark:text-emerald-400 animate-pulse">{currentStep}</p>
              </motion.div>
            )}
          </AnimatePresence>
        </CardContent>
      </Card>

      {!hasReport && !isRunning && (
        <div className="flex flex-col items-center justify-center h-64 rounded-2xl border-2 border-dashed border-gray-200 dark:border-white/10 text-center gap-4">
          <Inbox className="w-12 h-12 text-gray-300 dark:text-white/10" />
          <div>
            <p className="text-sm font-semibold text-gray-500 dark:text-white/30">No reports generated</p>
            <p className="text-xs text-gray-400 dark:text-white/20 mt-1">Enter a subject above to synthesize a cross-agent scientific report</p>
          </div>
        </div>
      )}

      {hasReport && !isRunning && (
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="grid grid-cols-1 lg:grid-cols-4 gap-8">
          <div className="lg:col-span-1 space-y-4">
            <Card className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10">
              <CardHeader className="pb-3">
                <CardTitle className="text-xs uppercase tracking-widest text-gray-400">Report Sections</CardTitle>
              </CardHeader>
              <CardContent className="p-2 space-y-0.5">
                {REPORT_SECTIONS.map(sec => {
                  const Icon = sectionIconMap[sec.icon] || ScrollText;
                  return (
                    <button key={sec.id} onClick={() => setActiveSection(sec.id)} className={cn("w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left text-xs font-medium transition-all", activeSection === sec.id ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400" : "text-gray-600 dark:text-white/50 hover:bg-gray-100 dark:hover:bg-white/5")}>
                      <Icon className={cn("w-3.5 h-3.5 shrink-0", activeSection === sec.id ? sec.color : "")} />
                      <span className="truncate">{sec.title}</span>
                      {activeSection === sec.id && <ChevronRight className="w-3 h-3 ml-auto shrink-0" />}
                    </button>
                  );
                })}
              </CardContent>
            </Card>

            <Card className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10">
              <CardHeader className="pb-2">
                <CardTitle className="text-xs uppercase tracking-widest text-gray-400">Recent Reports</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 p-3 pt-0">
                {reports.map(r => (
                  <div key={r.id} className="group p-2.5 rounded-lg border border-gray-100 dark:border-white/5 hover:border-emerald-300 dark:hover:border-emerald-500/30 hover:bg-emerald-500/5 transition-all cursor-pointer">
                    <p className="text-[11px] font-bold text-gray-700 dark:text-white/80 line-clamp-2 group-hover:text-emerald-600 dark:group-hover:text-emerald-400 transition-colors">{r.title}</p>
                    <div className="flex items-center justify-between mt-1.5">
                      <Badge variant="outline" className="text-[9px] h-4 border-emerald-200 dark:border-emerald-500/20 text-emerald-500">{r.status}</Badge>
                      <span className="text-[9px] text-gray-400 flex items-center gap-1"><Clock className="w-2.5 h-2.5" />{r.date}</span>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>

          <div className="lg:col-span-3">
            <AnimatePresence mode="wait">
              <motion.div key={activeSection} initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -10 }} transition={{ duration: 0.2 }}>
                <Card className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 overflow-hidden">
                  <CardHeader className="border-b border-gray-200 dark:border-white/5 bg-gray-50 dark:bg-white/[0.02]">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className={cn("w-10 h-10 rounded-lg flex items-center justify-center", activeData.bg)}>
                          {(() => { const Icon = sectionIconMap[activeData.icon] || ScrollText; return <Icon className={cn("w-5 h-5", activeData.color)} />; })()}
                        </div>
                        <div>
                          <CardTitle className="text-gray-900 dark:text-white">{activeData.title}</CardTitle>
                          <CardDescription className="text-xs">FinalReport schema</CardDescription>
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <Button onClick={downloadPDF} variant="outline" size="sm" className="border-emerald-200 dark:border-emerald-500/20 text-emerald-700 dark:text-emerald-400 text-xs h-8 hover:bg-emerald-50 dark:hover:bg-emerald-500/10">
                          <Download className="w-3.5 h-3.5 mr-1.5" />Export PDF
                        </Button>
                        <Button variant="outline" size="sm" className="border-gray-200 dark:border-white/10 text-xs h-8">
                          <Share2 className="w-3.5 h-3.5 mr-1.5" />Share
                        </Button>
                      </div>
                    </div>
                  </CardHeader>

                  <CardContent className="p-0">
                    <ScrollArea className="h-[540px] p-8">
                      <div className="space-y-6 text-sm text-gray-700 dark:text-white/70">
                        {activeData.content && (
                          <div className="leading-relaxed space-y-3">
                            {activeData.content.split('\n\n').map((para, i) => (
                              <p key={i} className="leading-7" dangerouslySetInnerHTML={{ __html: para.replace(/\*\*(.+?)\*\*/g, '<strong class="text-gray-900 dark:text-white font-semibold">$1</strong>') }} />
                            ))}
                          </div>
                        )}

                        {(activeData as any).table && (
                          <div className="overflow-x-auto rounded-lg border border-gray-100 dark:border-white/5">
                            <table className="w-full text-xs">
                              <thead className="bg-gray-50 dark:bg-white/[0.03]">
                                <tr>{(activeData as any).table.headers.map((h: string) => (<th key={h} className="py-3 px-4 text-left font-semibold text-gray-500 dark:text-white/40 uppercase tracking-wider text-[10px]">{h}</th>))}</tr>
                              </thead>
                              <tbody className="divide-y divide-gray-100 dark:divide-white/5">
                                {(activeData as any).table.rows.map((row: string[], i: number) => (
                                  <tr key={i} className="hover:bg-gray-50 dark:hover:bg-white/[0.02] transition-colors">
                                    {row.map((cell, j) => (<td key={j} className={cn("py-3 px-4", j === 0 ? "font-mono font-bold text-purple-700 dark:text-purple-400" : "text-gray-600 dark:text-white/60")}>{cell}</td>))}
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}

                        {(activeData as any).bullets && (
                          <ul className="space-y-2">{(activeData as any).bullets.map((b: string, i: number) => (<li key={i} className="flex items-start gap-2.5"><CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" /><span className="text-xs leading-relaxed">{b}</span></li>))}</ul>
                        )}

                        {(activeData as any).sources && (
                          <div className="space-y-3">{(activeData as any).sources.map((s: any, i: number) => (<div key={i} className="flex items-start justify-between gap-4 border-l-2 border-amber-400 pl-4 py-1"><div><p className="text-xs font-bold text-gray-800 dark:text-white">{s.label}</p><p className="text-[11px] text-gray-500 dark:text-white/40 mt-0.5">{s.desc}</p></div><Badge variant="secondary" className="text-[9px] shrink-0 bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-none">Rel: {s.score}</Badge></div>))}</div>
                        )}

                        {(activeData as any).metrics && (
                          <div className="space-y-4">
                            {(activeData as any).metrics.map((m: any, i: number) => (
                              <div key={i} className="space-y-1.5">
                                <div className="flex justify-between text-xs"><span className="font-medium text-gray-700 dark:text-white/70">{m.label}</span><span className={cn("font-mono font-bold", m.invert ? "text-red-400" : "text-emerald-500")}>{m.value}</span></div>
                                <div className="h-1.5 w-full bg-gray-100 dark:bg-white/5 rounded-full overflow-hidden"><motion.div initial={{ width: 0 }} animate={{ width: `${m.bar}%` }} transition={{ duration: 0.8, delay: i * 0.1 }} className={cn("h-full rounded-full", m.invert ? "bg-red-400" : "bg-emerald-500")} /></div>
                              </div>
                            ))}
                            <Separator className="bg-gray-100 dark:bg-white/5 my-4" />
                            <div className="grid grid-cols-2 gap-3">{(activeData as any).stats?.map((st: any, i: number) => (<div key={i} className="bg-gray-50 dark:bg-white/[0.03] rounded-lg p-3 border border-gray-100 dark:border-white/5"><p className="text-[10px] text-gray-400 uppercase tracking-wider">{st.label}</p><p className="text-sm font-bold text-gray-800 dark:text-white mt-0.5">{st.value}</p></div>))}</div>
                          </div>
                        )}

                        {(activeData as any).alerts && (
                          <div className="space-y-3">{(activeData as any).alerts.map((alert: any, i: number) => (
                            <div key={i} className={cn("flex gap-3 p-4 rounded-xl border", alert.level === "critical" ? "bg-red-50 dark:bg-red-500/10 border-red-200 dark:border-red-500/20" : alert.level === "warning" ? "bg-amber-50 dark:bg-amber-500/10 border-amber-200 dark:border-amber-500/20" : "bg-emerald-50 dark:bg-emerald-500/10 border-emerald-200 dark:border-emerald-500/20")}>
                              <AlertTriangle className={cn("w-4 h-4 shrink-0 mt-0.5", alert.level === "critical" ? "text-red-500" : alert.level === "warning" ? "text-amber-500" : "text-emerald-500")} />
                              <div><p className="text-xs font-bold text-gray-900 dark:text-white">{alert.label}</p><p className="text-[11px] text-gray-600 dark:text-white/50 leading-relaxed">{alert.detail}</p></div>
                            </div>
                          ))}</div>
                        )}

                        {(activeData as any).hypotheses && (
                          <div className="space-y-4">{(activeData as any).hypotheses.map((h: any) => (
                            <div key={h.id} className="border border-gray-100 dark:border-white/5 rounded-xl p-5 bg-gray-50 dark:bg-white/[0.02] space-y-3">
                              <p className="text-sm font-bold text-gray-900 dark:text-white">{h.id}. {h.title}</p>
                              <p className="text-xs text-gray-600 dark:text-white/60 leading-relaxed"><strong>Rationale:</strong> {h.rationale}</p>
                              <p className="text-xs text-gray-600 dark:text-white/60 leading-relaxed"><strong>Experiment:</strong> {h.experiment}</p>
                              <p className="text-[10px] text-violet-600 dark:text-violet-400 font-mono">{h.citations.join(' | ')}</p>
                            </div>
                          ))}</div>
                        )}

                        {(activeData as any).meta && (
                          <div className="mt-4 p-3 bg-gray-50 dark:bg-white/[0.03] rounded-lg border border-gray-100 dark:border-white/5">
                            <p className="text-[11px] font-mono text-gray-500 dark:text-white/30">{(activeData as any).meta}</p>
                          </div>
                        )}
                      </div>
                    </ScrollArea>
                  </CardContent>
                </Card>
              </motion.div>
            </AnimatePresence>
          </div>
        </motion.div>
      )}
    </div>
  );
}
