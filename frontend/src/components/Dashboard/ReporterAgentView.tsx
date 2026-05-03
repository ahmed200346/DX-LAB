"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { motion, AnimatePresence } from "framer-motion";
import { FileText, Download, Share2, Eye, FileSearch, CheckCircle2, Clock, ScrollText, Loader2, Sparkles, Inbox } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Input } from "@/components/ui/input";

export default function ReporterAgentView() {
  const [isRunning, setIsRunning] = useState(false);
  const [hasReport, setHasReport] = useState(false);
  const [subject, setSubject] = useState("");
  const [reports, setReports] = useState<any[]>([]);
  const [currentStep, setCurrentStep] = useState("");

  const generateReport = async () => {
    if (!subject.trim()) return;
    setIsRunning(true);
    setHasReport(false);
    
    setCurrentStep("Compiling molecular characteristics...");
    await new Promise(r => setTimeout(r, 2000 + Math.random() * 1000));
    
    setCurrentStep("Retrieving FAERS toxicity profile...");
    await new Promise(r => setTimeout(r, 2000 + Math.random() * 1000));

    setCurrentStep("Formatting clinical justification...");
    await new Promise(r => setTimeout(r, 3000 + Math.random() * 1000));

    const newReport = {
      id: Date.now(),
      title: subject.includes("BCL-2") ? "Consolidated Insights: BCL-2 Drug Discovery" : `Synthesis Report: ${subject}`,
      date: new Date().toISOString().split("T")[0],
      type: "Discovery Summary",
      status: "Ready"
    };
    setReports(prev => [newReport, ...prev]);
    setHasReport(true);
    setIsRunning(false);
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-2xl font-bold">Reporter Agent</h3>
          <p className="text-gray-600 dark:text-gray-500 dark:text-white/40 text-sm">Automated generation of scientific justifications and interpretations</p>
        </div>
      </div>

      {/* Input Section */}
      <Card className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 backdrop-blur-md shadow-sm dark:shadow-none overflow-hidden">
        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-emerald-500 to-green-500" />
        <CardContent className="p-8">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 items-end">
            <div className="md:col-span-3 space-y-2">
              <label className="text-xs font-semibold text-gray-600 dark:text-gray-500 dark:text-white/40 uppercase tracking-wider">Report Subject / Target</label>
              <Input 
                value={subject} 
                onChange={(e) => setSubject(e.target.value)}
                placeholder="Specify report subject or target area..."
                className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 text-gray-900 dark:text-white focus:ring-emerald-500/50 h-11"
                onKeyDown={(e) => { if (e.key === 'Enter') generateReport(); }}
              />
            </div>
            <div className="md:col-span-1">
              <Button 
                onClick={generateReport} 
                disabled={isRunning || !subject.trim()}
                className="w-full bg-emerald-600 hover:bg-emerald-700 text-white h-11 font-bold shadow-lg shadow-emerald-600/20 rounded-lg group disabled:opacity-40"
              >
                {isRunning ? <Loader2 className="w-5 h-5 animate-spin mr-2" /> : <ScrollText className="w-4 h-4 mr-2" />}
                {isRunning ? "Composing..." : "Generate Report"}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {!hasReport && !isRunning ? (
        <div className="flex flex-col items-center justify-center h-64 rounded-2xl border-2 border-dashed border-gray-200 dark:border-white/10 text-center gap-4 animate-in fade-in duration-500">
          <Inbox className="w-12 h-12 text-gray-300 dark:text-white/10" />
          <div>
            <p className="text-sm font-semibold text-gray-500 dark:text-white/30">No reports generated</p>
            <p className="text-xs text-gray-400 dark:text-white/20 mt-1">Specify a subject above to synthesize a scientific report</p>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 animate-in fade-in zoom-in-95 duration-500">
          <div className="lg:col-span-2 space-y-6">
            <Card className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 backdrop-blur-md shadow-sm dark:shadow-none overflow-hidden relative">
                <AnimatePresence>
                  {isRunning && (
                    <motion.div 
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="absolute inset-0 z-20 bg-gray-900/10 dark:bg-black/60 backdrop-blur-md flex flex-col items-center justify-center space-y-4"
                    >
                        <div className="relative">
                          <FileText className="w-16 h-16 text-emerald-500/40 animate-pulse" />
                          <motion.div 
                              className="absolute inset-0"
                              animate={{ opacity: [0.5, 1, 0.5] }}
                              transition={{ duration: 1.5, repeat: Infinity }}
                          >
                              <Sparkles className="w-8 h-8 text-emerald-600 dark:text-emerald-400 absolute -top-2 -right-2" />
                          </motion.div>
                        </div>
                        <div className="text-center">
                          <p className="text-emerald-700 dark:text-emerald-400 font-bold text-lg">AI Synthesis in Progress</p>
                          <p className="text-emerald-600/70 dark:text-emerald-500/80 text-sm italic font-mono mt-2">{currentStep}</p>
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
                      <article className="prose prose-invert max-w-none space-y-6 text-gray-700 dark:text-white/70">
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
      )}
    </div>
  );
}
