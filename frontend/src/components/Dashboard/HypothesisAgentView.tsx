"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Sparkles, 
  FileText, 
  BrainCircuit, 
  Plus, 
  ArrowRight, 
  ZapOff, 
  Loader2, 
  Search, 
  MessageSquare,
  Bot
} from "lucide-react";
import { Card, CardContent, CardTitle, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";

export default function HypothesisAgentView() {
  const [isRunning, setIsRunning] = useState(false);
  const [hasRun, setHasRun] = useState(false);
  const [query, setQuery] = useState("");
  const [hypotheses, setHypotheses] = useState<any[]>([]);
  const [currentAction, setCurrentAction] = useState("");
  const [selectedHypothesis, setSelectedHypothesis] = useState<any | null>(null);
  const [activities, setActivities] = useState<any[]>([
    { icon: MessageSquare, text: "System standby", time: "1h ago" },
    { icon: FileText, text: "Ingested PDF: 'Emerging targets in CLL'", time: "4h ago" },
  ]);

  const generateHypothesis = async () => {
    if (!query.trim()) return;
    setIsRunning(true);
    setHasRun(false);
    setHypotheses([]);
    
    setCurrentAction("Querying vector database for similar literature...");
    setActivities(prev => [{ icon: Search, text: "Querying vector database...", time: "just now" }, ...prev]);
    await new Promise(r => setTimeout(r, 2000 + Math.random() * 1000));
    
    setCurrentAction("Cross-referencing PubMed and clinical trial data...");
    setActivities(prev => [{ icon: BrainCircuit, text: "Cross-referencing PubMed/ClinicalTrials.gov", time: "just now" }, ...prev]);
    await new Promise(r => setTimeout(r, 2500 + Math.random() * 1000));

    setCurrentAction("Synthesizing mechanistic pathways with LLM...");
    setActivities(prev => [{ icon: Sparkles, text: "Synthesizing novel mechanistic relationships", time: "just now" }, ...prev]);
    await new Promise(r => setTimeout(r, 3000 + Math.random() * 1500));

    const results = [
      { 
        id: 1, 
        title: "MCL-1 Upregulation Mediating Resistance", 
        confidence: 94, 
        category: "Mechanistic",
        impact: "High",
        novelty: "Medium",
        abstract: "Secondary resistance to Venetoclax-Analog is driven by BAX/BAK sequestration via MCL-1 overexpression.",
        rationale: "Analysis of 14 clinical trials indicates tumor cells compensate by upregulating MCL-1 to sequester pro-apoptotic factors.",
        experiment: "In vitro CRISPR/Cas9 knockout of MCL-1 in resistant CLL cell lines to restore Venetoclax sensitivity.",
        citations: ["PMID: 31103752", "PMID: 29401645"]
      },
      { 
        id: 2, 
        title: "BCL-xL Dependency Switch", 
        confidence: 76, 
        category: "Clinical",
        impact: "Medium",
        novelty: "High",
        abstract: "CLL cells shift survival dependency from BCL-2 to BCL-xL under therapeutic pressure.",
        rationale: "Single-cell RNA sequencing reveals sub-populations that switch dependency during deep BCL-2 target engagement.",
        experiment: "Combinatorial treatment with BCL-xL inhibitors and BH3 profiling to measure mitochondrial priming shifts.",
        citations: ["PMID: 26822266", "Nature 2023: Escape"]
      },
      { 
        id: 3, 
        title: "PRAME-Mediated Mitochondrial Escape", 
        confidence: 62, 
        category: "Emerging",
        impact: "Medium",
        novelty: "Very High",
        abstract: "Epigenetic upregulation of PRAME alters mitochondrial membrane potential, reducing BAX insertion efficiency.",
        rationale: "Novel multi-omic integration suggests PRAME modifies mitochondrial lipid composition in resistant clones.",
        experiment: "Lipidomic analysis of mitochondrial membranes in PRAME-high vs PRAME-low Venetoclax resistant models.",
        citations: ["Cell 2024: PRAME Axis", "PMID: 32581902"]
      }
    ];
    
    setHypotheses(results);
    setHasRun(true);
    setIsRunning(false);
    setCurrentAction("");
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-2xl font-bold">Hypothesis Assistant</h3>
          <p className="text-gray-600 dark:text-gray-500 dark:text-white/40 text-sm">AI-driven generation of research directions and mechanism of action models</p>
        </div>
      </div>

      {/* Input Section */}
      <Card className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 backdrop-blur-md shadow-sm dark:shadow-none overflow-hidden">
        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-yellow-500 to-amber-500" />
        <CardContent className="p-8">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 items-end">
            <div className="md:col-span-3 space-y-2">
              <label className="text-xs font-semibold text-gray-600 dark:text-gray-500 dark:text-white/40 uppercase tracking-wider">Research Question / Topic</label>
              <Input 
                value={query} 
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Type your research hypothesis or query here..."
                className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 text-gray-900 dark:text-white focus:ring-yellow-500/50 h-11"
                onKeyDown={(e) => { if (e.key === 'Enter') generateHypothesis(); }}
              />
            </div>
            <div className="md:col-span-1">
              <Button 
                onClick={generateHypothesis} 
                disabled={isRunning || !query.trim()}
                className="w-full bg-yellow-600 hover:bg-yellow-700 text-white h-11 font-bold shadow-lg shadow-yellow-600/20 rounded-lg group disabled:opacity-40"
              >
                {isRunning ? <Loader2 className="w-5 h-5 animate-spin mr-2" /> : <Plus className="w-4 h-4 mr-2" />}
                {isRunning ? "Synthesizing..." : "Generate Ideas"}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {!hasRun && !isRunning ? (
        <div className="flex flex-col items-center justify-center h-64 rounded-2xl border-2 border-dashed border-gray-200 dark:border-white/10 text-center gap-4 animate-in fade-in duration-500">
          <ZapOff className="w-12 h-12 text-gray-300 dark:text-white/10" />
          <div>
            <p className="text-sm font-semibold text-gray-500 dark:text-white/30">No hypotheses generated</p>
            <p className="text-xs text-gray-400 dark:text-white/20 mt-1">Submit a research question above to start AI synthesis</p>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8 animate-in fade-in zoom-in-95 duration-500">
          <div className="lg:col-span-3 space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <AnimatePresence mode="popLayout">
                  {isRunning && (
                    <motion.div 
                      initial={{ opacity: 0, scale: 0.95 }}
                      animate={{ opacity: 1, scale: 1 }}
                      exit={{ opacity: 0, scale: 0.95 }}
                      className="col-span-1 md:col-span-2 flex flex-col items-center justify-center h-48 border-2 border-dashed border-yellow-500/30 rounded-xl bg-yellow-500/5 animate-pulse"
                    >
                      <BrainCircuit className="w-10 h-10 text-yellow-500 mb-4 animate-bounce" />
                      <p className="text-yellow-600 dark:text-yellow-500/80 font-mono text-sm text-center px-4">{currentAction}</p>
                    </motion.div>
                  )}

                  {hypotheses.map((h) => (
                    <motion.div
                      key={h.id}
                      layout
                      initial={{ opacity: 0, scale: 0.9, y: 20 }}
                      animate={{ opacity: 1, scale: 1, y: 0 }}
                      transition={{ duration: 0.4 }}
                    >
                      <Card 
                        className={cn(
                          "bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 hover:border-yellow-300 dark:border-yellow-500/30 transition-all group cursor-pointer h-full relative overflow-hidden",
                          selectedHypothesis?.id === h.id && "ring-2 ring-yellow-500 border-yellow-500"
                        )}
                        onClick={() => setSelectedHypothesis(selectedHypothesis?.id === h.id ? null : h)}
                      >
                        <CardHeader className="pb-3">
                          <div className="flex justify-between items-start">
                             <Badge variant="outline" className="text-yellow-700 dark:text-yellow-400 border-yellow-300 dark:border-yellow-500/30 bg-yellow-500/5">{h.category}</Badge>
                             <span className="text-xs font-bold text-gray-600 dark:text-white/20 group-hover:text-yellow-500/40">Confidence: {h.confidence}%</span>
                          </div>
                          <CardTitle className="mt-4 text-gray-900 dark:text-white/90 group-hover:text-gray-900 dark:text-white transition-colors">{h.title}</CardTitle>
                        </CardHeader>
                        <CardContent>
                          <p className="text-sm text-gray-600 dark:text-gray-500 dark:text-white/40 leading-relaxed line-clamp-3">{h.abstract}</p>
                          
                          <div className="mt-4 flex gap-4">
                             <div className="space-y-1">
                               <p className="text-[9px] uppercase font-bold text-gray-400">Impact</p>
                               <Badge variant="secondary" className="bg-blue-500/10 text-blue-600 dark:text-blue-400 border-none text-[10px]">{h.impact}</Badge>
                             </div>
                             <div className="space-y-1">
                               <p className="text-[9px] uppercase font-bold text-gray-400">Novelty</p>
                               <Badge variant="secondary" className="bg-purple-500/10 text-purple-600 dark:text-purple-400 border-none text-[10px]">{h.novelty}</Badge>
                             </div>
                          </div>

                          <AnimatePresence>
                            {selectedHypothesis?.id === h.id && (
                              <motion.div 
                                initial={{ height: 0, opacity: 0 }}
                                animate={{ height: "auto", opacity: 1 }}
                                exit={{ height: 0, opacity: 0 }}
                                className="mt-4 pt-4 border-t border-gray-200 dark:border-white/10 space-y-4"
                              >
                                <div className="space-y-2">
                                  <h4 className="text-[10px] uppercase tracking-widest font-bold text-yellow-600 dark:text-yellow-500/60">Scientific Rationale</h4>
                                  <p className="text-xs text-gray-700 dark:text-white/70 italic leading-relaxed">{h.rationale}</p>
                                </div>
                                <div className="space-y-2">
                                  <h4 className="text-[10px] uppercase tracking-widest font-bold text-yellow-600 dark:text-yellow-500/60">Proposed Experiment</h4>
                                  <p className="text-xs text-gray-700 dark:text-white/70 leading-relaxed">{h.experiment}</p>
                                </div>
                                <div className="space-y-2">
                                  <h4 className="text-[10px] uppercase tracking-widest font-bold text-yellow-600 dark:text-yellow-500/60">Citations</h4>
                                  <div className="flex flex-wrap gap-2">
                                    {h.citations.map((c: string, i: number) => (
                                      <Badge key={i} variant="secondary" className="text-[9px] bg-gray-100 dark:bg-white/5 border-none">{c}</Badge>
                                    ))}
                                  </div>
                                </div>
                              </motion.div>
                            )}
                          </AnimatePresence>

                          <div className="mt-6 flex items-center text-xs font-bold text-yellow-500 group-hover:gap-2 transition-all">
                             {selectedHypothesis?.id === h.id ? "HIDE DETAILS" : "VIEW DETAILS"} <ArrowRight className={cn("w-3 h-3 ml-1 transition-transform", selectedHypothesis?.id === h.id && "rotate-90")} />
                          </div>
                        </CardContent>
                      </Card>
                    </motion.div>
                  ))}
                </AnimatePresence>
            </div>
          </div>
          <div className="space-y-6">
            {/* Dexter QA Assistant */}
            <Card className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 overflow-hidden h-[380px] flex flex-col shadow-xl">
                <CardHeader className="bg-blue-600 py-3 px-4 flex flex-row items-center justify-between">
                   <div className="flex items-center gap-2">
                     <div className="w-8 h-8 rounded-full bg-white flex items-center justify-center overflow-hidden border-2 border-white/20">
                        <img src="https://api.dicebear.com/7.x/bottts/svg?seed=Dexter&backgroundColor=transparent" alt="Dexter" className="w-full h-full" />
                     </div>
                     <CardTitle className="text-xs font-bold text-white uppercase tracking-wider">Dexter QA Assistant</CardTitle>
                   </div>
                </CardHeader>
                <CardContent className="flex-1 p-0 flex flex-col overflow-hidden">
                   <ScrollArea className="flex-1 p-4 bg-gray-50 dark:bg-black/20">
                      <div className="space-y-4">
                         <div className="bg-white dark:bg-white/5 p-3 rounded-2xl rounded-tl-none border border-gray-100 dark:border-white/5 shadow-sm">
                            <p className="text-[11px] text-gray-700 dark:text-white/80 leading-relaxed">I am **Dexter**. Ask me follow-up questions about the hypotheses, target gaps, or experimental design.</p>
                         </div>
                      </div>
                   </ScrollArea>
                   <div className="p-3 bg-white dark:bg-white/5 border-t border-gray-100 dark:border-white/10 flex gap-2">
                      <Input className="bg-gray-100 dark:bg-white/5 border-none h-9 text-xs" placeholder="Ask Dexter..." />
                      <Button size="sm" className="bg-blue-600 hover:bg-blue-700 h-9 px-3 text-[10px] font-bold uppercase tracking-widest">Send</Button>
                   </div>
                </CardContent>
            </Card>

            {/* Agent Activity */}
            <Card className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10">
                <CardHeader className="pb-2">
                  <CardTitle className="text-xs font-bold uppercase tracking-widest text-gray-400">Agent Activity</CardTitle>
                </CardHeader>
                <CardContent>
                  <ScrollArea className="h-[250px] pr-4">
                      <div className="space-y-4">
                        {activities.map((item, i) => (
                          <div key={i} className="flex gap-3">
                              <div className="w-7 h-7 rounded-lg bg-gray-100 dark:bg-white/5 flex items-center justify-center shrink-0">
                                <item.icon className="w-3.5 h-3.5 text-yellow-500/60" />
                              </div>
                              <div>
                                <p className="text-[11px] text-gray-700 dark:text-white/80 leading-tight">{item.text}</p>
                                <p className="text-[9px] text-gray-400 mt-1">{item.time}</p>
                              </div>
                          </div>
                        ))}
                      </div>
                  </ScrollArea>
                </CardContent>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
