"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { motion, AnimatePresence } from "framer-motion";
import { FileText, Download, Share2, Eye, FileSearch, CheckCircle2, Clock, ScrollText, Loader2, Sparkles } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";

export default function ReporterAgentView() {
  const [isRunning, setIsRunning] = useState(false);
  const [reports, setReports] = useState([
    { id: 1, title: "Discovery Report: BCL-2 (P10415)", date: "2026-05-03", type: "Full Synthesis", status: "Ready" },
    { id: 2, title: "Safety Audit: Venetoclax-Analog", date: "2026-05-02", type: "Tox Screening", status: "Ready" },
    { id: 3, title: "Hypothesis Validation: MCL-1 Resistance", date: "2026-05-01", type: "Literature Review", status: "Archived" },
  ]);

  const generateReport = async () => {
    setIsRunning(true);
    await new Promise(r => setTimeout(r, 3000));
    const newReport = {
      id: Date.now(),
      title: "Consolidated Insights: BCL-2 Drug Discovery",
      date: new Date().toISOString().split("T")[0],
      type: "Discovery Summary",
      status: "Ready"
    };
    setReports(prev => [newReport, ...prev]);
    setIsRunning(false);
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-2xl font-bold">Reporter Agent</h3>
          <p className="text-gray-600 dark:text-gray-500 dark:text-white/40 text-sm">Automated generation of scientific justifications, interpretations, and results</p>
        </div>
        <Button 
          onClick={generateReport}
          disabled={isRunning}
          className="bg-emerald-600 hover:bg-emerald-700 shadow-lg shadow-emerald-600/20 text-white min-w-[160px]"
        >
           {isRunning ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <ScrollText className="w-4 h-4 mr-2" />}
           {isRunning ? "Composing..." : "New Report"}
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 space-y-6">
           <Card className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 backdrop-blur-md shadow-sm dark:shadow-none overflow-hidden relative">
             <AnimatePresence>
               {isRunning && (
                 <motion.div 
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="absolute inset-0 z-20 bg-gray-900 dark:bg-black/60 backdrop-blur-sm flex flex-col items-center justify-center space-y-4"
                 >
                    <div className="relative">
                       <FileText className="w-16 h-16 text-emerald-500/20" />
                       <motion.div 
                          className="absolute inset-0"
                          animate={{ opacity: [0.5, 1, 0.5] }}
                          transition={{ duration: 1.5, repeat: Infinity }}
                       >
                          <Sparkles className="w-8 h-8 text-emerald-700 dark:text-emerald-400 absolute -top-2 -right-2" />
                       </motion.div>
                    </div>
                    <div className="text-center">
                       <p className="text-emerald-700 dark:text-emerald-400 font-bold text-lg">AI Synthesis in Progress</p>
                       <p className="text-gray-600 dark:text-gray-500 dark:text-white/40 text-sm italic">Formatting technical justifications and citations...</p>
                    </div>
                 </motion.div>
               )}
             </AnimatePresence>

             <CardHeader className="border-b border-gray-200 dark:border-white/5 bg-gray-50 dark:bg-white/[0.02]">
                <div className="flex items-center justify-between">
                   <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-emerald-50 dark:bg-emerald-500/10 flex items-center justify-center">
                         <FileSearch className="w-5 h-5 text-emerald-700 dark:text-emerald-400" />
                      </div>
                      <div>
                         <CardTitle className="text-gray-900 dark:text-white/90">Report Preview</CardTitle>
                         <CardDescription>Scientific Justification & Interpretation</CardDescription>
                      </div>
                   </div>
                   <div className="flex gap-2">
                      <Button variant="outline" size="sm" className="border-gray-200 dark:border-white/10 text-xs">
                         <Download className="w-3.5 h-3.5 mr-2" />
                         DOCX
                      </Button>
                      <Button variant="outline" size="sm" className="border-gray-200 dark:border-white/10 text-xs">
                         <Download className="w-3.5 h-3.5 mr-2" />
                         PDF
                      </Button>
                   </div>
                </div>
             </CardHeader>
             <CardContent className="p-0">
                <ScrollArea className="h-[500px] p-8">
                   <article className="prose prose-invert max-w-none space-y-6 text-white/70">
                      <div className="text-center space-y-2 mb-10">
                         <h1 className="text-3xl font-bold text-gray-900 dark:text-white tracking-tight">Technical Justification Report</h1>
                         <p className="text-sm font-mono uppercase tracking-[0.2em] text-emerald-500/60">Confidential Discovery Payload</p>
                      </div>

                      <section className="space-y-3">
                         <h2 className="text-xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
                            <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                            Executive Summary
                         </h2>
                          <p className="text-sm leading-relaxed">
                             This report presents the scientific justification for candidate <strong>Venetoclax-Analog</strong> targeting <strong>BCL-2 (UniProt: P10415)</strong> in Chronic Lymphocytic Leukemia (CLL). 
                             The automated pipeline leveraged REINVENT generative models for scaffold synthesis, Boltz-1 for 3D structure prediction, and ensemble deep learning for binding affinity scoring (pKd = 11.4).
                          </p>
                      </section>

                      <section className="space-y-3">
                         <h2 className="text-xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
                            <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                            Binding Mode Interpretation
                         </h2>
                          <p className="text-sm leading-relaxed">
                             The molecule exhibits a non-covalent binding mechanism within the <em>BH3-binding groove</em> of BCL-2, competing with pro-apoptotic BH3-domain proteins (BAX, BAK). 
                             Computational models indicate 98% groove occupancy and nanomolar affinity, consistent with the known Venetoclax pharmacophore.
                          </p>
                          <div className="p-4 bg-emerald-500/5 border border-emerald-500/10 rounded-lg italic text-xs">
                             <strong className="text-yellow-500">⚠ TLS Mitigation Strategy:</strong> Due to rapid apoptosis induction, clinical protocol recommends a 5-week ramp-up: 20mg → 50mg → 100mg → 200mg → 400mg. Prophylactic hydration and allopurinol required.
                          </div>
                      </section>

                      <section className="space-y-3">
                         <h2 className="text-xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
                            <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                            Source Attribution
                         </h2>
                         <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {[
                               { source: "PMID: 26822266", context: "Venetoclax in relapsed/refractory CLL" },
                                { source: "ChEMBL Dataset v32", context: "SMILES scaffold validation" },
                                { source: "RCSB PDB: 4MAN", context: "BCL-2/BAX complex structural reference" },
                                { source: "Internal Vector DB", context: "High-throughput CellTiter-Glo screening results" }
                            ].map((s, i) => (
                               <div key={i} className="flex flex-col p-3 bg-white dark:bg-white/5 rounded border border-gray-200 dark:border-white/5">
                                  <span className="text-xs font-bold text-emerald-700 dark:text-emerald-400">{s.source}</span>
                                  <span className="text-[10px] text-gray-600 dark:text-gray-500 dark:text-white/40 mt-1">{s.context}</span>
                               </div>
                            ))}
                         </div>
                      </section>
                   </article>
                </ScrollArea>
             </CardContent>
           </Card>
        </div>

        <div className="space-y-6">
           <Card className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 backdrop-blur-md shadow-sm dark:shadow-none">
             <CardHeader>
                <CardTitle className="text-sm">Recent Reports</CardTitle>
             </CardHeader>
             <CardContent>
                <div className="space-y-4">
                   <AnimatePresence mode="popLayout">
                    {reports.map((r) => (
                      <motion.div 
                        key={r.id} 
                        layout
                        initial={{ opacity: 0, x: 20 }}
                        animate={{ opacity: 1, x: 0 }}
                        className="group p-3 rounded-lg border border-gray-200 dark:border-white/5 hover:border-emerald-300 dark:border-emerald-500/30 hover:bg-emerald-500/5 transition-all cursor-pointer"
                      >
                         <div className="flex justify-between items-start mb-2">
                            <p className="text-xs font-bold text-gray-700 dark:text-white/80 group-hover:text-emerald-700 dark:text-emerald-400 transition-colors">{r.title}</p>
                            <Badge variant="outline" className="text-[10px] h-4 border-emerald-200 dark:border-emerald-500/20 text-emerald-500">{r.status}</Badge>
                         </div>
                         <div className="flex items-center justify-between text-[10px] text-gray-600 dark:text-white/30">
                            <span>{r.type}</span>
                            <span className="flex items-center gap-1"><Clock className="w-2.5 h-2.5" /> {r.date}</span>
                         </div>
                      </motion.div>
                    ))}
                   </AnimatePresence>
                </div>
             </CardContent>
           </Card>

           <Card className="bg-gradient-to-br from-emerald-600/20 to-teal-600/10 border-gray-200 dark:border-white/10 p-6">
              <div className="space-y-4 text-center">
                 <div className="w-12 h-12 rounded-full bg-emerald-500/20 flex items-center justify-center mx-auto">
                    <Share2 className="w-6 h-6 text-emerald-700 dark:text-emerald-400" />
                 </div>
                 <h4 className="text-sm font-bold">Collaborative Export</h4>
                 <p className="text-xs text-gray-600 dark:text-gray-500 dark:text-white/40 leading-relaxed">Share discovery insights directly with your team or clinical stakeholders.</p>
                 <Button className="w-full bg-white text-black hover:bg-white/90 text-xs font-bold">Invite Reviewers</Button>
              </div>
           </Card>
        </div>
      </div>
    </div>
  );
}
