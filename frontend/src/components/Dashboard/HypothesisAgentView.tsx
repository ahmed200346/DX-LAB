"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { motion, AnimatePresence } from "framer-motion";
import { Lightbulb, Sparkles, Network, FileText, BrainCircuit, MessageSquare, Plus, ArrowRight, Loader2, Search } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";

export default function HypothesisAgentView() {
  const [isRunning, setIsRunning] = useState(false);
  const [hypotheses, setHypotheses] = useState([
    { 
      id: 1, 
      title: "MCL-1 Upregulation Mediating Resistance", 
      confidence: 94, 
      category: "Mechanistic",
      abstract: "Analyzing multi-omic data suggests that secondary resistance to Venetoclax-Analog is primarily driven by BAX/BAK sequestration via MCL-1 overexpression."
    },
    { 
      id: 2, 
      title: "Role of BCL-xL Bypass Signaling", 
      confidence: 76, 
      category: "Clinical",
      abstract: "In CLL models, reliance on BCL-xL survival pathways may provide an escape mechanism after complete BCL-2 blockade."
    },
  ]);

  const generateHypothesis = async () => {
    setIsRunning(true);
    await new Promise(r => setTimeout(r, 2500));
    const newH = {
      id: Date.now(),
      title: "Dual BCL-2/MCL-1 Inhibitor Scaffold",
      confidence: 88,
      category: "Novel Scaffold",
      abstract: "Exploring covalent interactions in the BH3-binding groove to simultaneously target BCL-2 and MCL-1, overcoming rapid tumor lysis escape."
    };
    setHypotheses(prev => [newH, ...prev]);
    setIsRunning(false);
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-2xl font-bold">Hypothesis Assistant</h3>
          <p className="text-gray-600 dark:text-gray-500 dark:text-white/40 text-sm">AI-driven generation of research directions and mechanism of action models</p>
          <div className="mt-4 flex flex-wrap gap-2 items-center">
            <span className="text-[10px] font-bold text-gray-600 dark:text-white/20 uppercase tracking-widest mr-2">Ideas for:</span>
            {[
              "Synergistic targets for MCL-1 overexpression",
              "Mechanism of action for dual BH3 inhibitors",
              "New scaffolds for BAX/BAK activation",
            ].map((ex) => (
              <button 
                key={ex}
                className="text-[9px] bg-white dark:bg-white/5 hover:bg-yellow-50 dark:bg-yellow-500/10 border border-gray-200 dark:border-white/10 hover:border-yellow-300 dark:border-yellow-500/30 px-3 py-1.5 rounded-full text-white/60 hover:text-yellow-700 dark:text-yellow-400 transition-all"
              >
                {ex}
              </button>
            ))}
          </div>
        </div>
        <Button 
          onClick={generateHypothesis}
          disabled={isRunning}
          className="bg-yellow-600 hover:bg-yellow-700 shadow-lg shadow-yellow-600/20 text-white min-w-[160px]"
        >
          {isRunning ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Plus className="w-4 h-4 mr-2" />}
          {isRunning ? "Synthesizing..." : "New Hypothesis"}
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
        <div className="lg:col-span-3 space-y-6">
           <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <AnimatePresence mode="popLayout">
                {hypotheses.map((h) => (
                  <motion.div
                    key={h.id}
                    layout
                    initial={{ opacity: 0, scale: 0.9, y: 20 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    transition={{ duration: 0.4 }}
                  >
                    <Card className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 hover:border-yellow-300 dark:border-yellow-500/30 transition-colors group cursor-pointer h-full">
                      <CardHeader className="pb-3">
                        <div className="flex justify-between items-start">
                           <Badge variant="outline" className="text-yellow-700 dark:text-yellow-400 border-yellow-300 dark:border-yellow-500/30 bg-yellow-500/5">{h.category}</Badge>
                           <span className="text-xs font-bold text-gray-600 dark:text-white/20 group-hover:text-yellow-500/40">Confidence: {h.confidence}%</span>
                        </div>
                        <CardTitle className="mt-4 text-gray-900 dark:text-white/90 group-hover:text-gray-900 dark:text-white transition-colors">{h.title}</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <p className="text-sm text-gray-600 dark:text-gray-500 dark:text-white/40 leading-relaxed line-clamp-3">{h.abstract}</p>
                        <div className="mt-6 flex items-center text-xs font-bold text-yellow-500 group-hover:gap-2 transition-all">
                           VIEW DETAILS <ArrowRight className="w-3 h-3 ml-1" />
                        </div>
                      </CardContent>
                    </Card>
                  </motion.div>
                ))}
              </AnimatePresence>
           </div>

           <Card className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 backdrop-blur-md shadow-sm dark:shadow-none">
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                   <Network className="w-5 h-5 text-yellow-700 dark:text-yellow-400" />
                   Knowledge Synthesis
                </CardTitle>
                <CardDescription>Cross-referencing papers, patents, and multi-omics</CardDescription>
              </CardHeader>
              <CardContent>
                 <div className="h-[300px] w-full rounded-xl bg-gray-900/5 dark:bg-black/40 border border-gray-200 dark:border-white/5 flex items-center justify-center relative overflow-hidden">
                    <div className="absolute inset-0 opacity-20">
                       <svg className="w-full h-full" viewBox="0 0 400 200">
                          <circle cx="200" cy="100" r="10" fill="#facc15" />
                          <circle cx="150" cy="60" r="6" fill="#facc15" />
                          <circle cx="250" cy="140" r="8" fill="#facc15" />
                          <line x1="200" y1="100" x2="150" y2="60" stroke="#facc15" strokeWidth="1" />
                          <line x1="200" y1="100" x2="250" y2="140" stroke="#facc15" strokeWidth="1" />
                          <motion.circle 
                             cx="200" cy="100" r={isRunning ? 80 : 40} stroke="#facc15" strokeWidth="0.5" fill="none"
                             animate={{ scale: isRunning ? [1, 1.2, 1] : [1, 1.5, 1], opacity: isRunning ? [0.5, 0.2, 0.5] : [0.2, 0.1, 0.2] }}
                             transition={{ duration: isRunning ? 1 : 4, repeat: Infinity }}
                          />
                       </svg>
                    </div>
                    <div className="text-center z-10">
                      {isRunning ? (
                        <div className="flex flex-col items-center gap-3">
                           <Loader2 className="w-8 h-8 text-yellow-500 animate-spin" />
                           <p className="text-sm text-yellow-500/60 font-bold tracking-widest uppercase">Cross-referencing databases...</p>
                        </div>
                      ) : (
                        <p className="text-sm text-gray-600 dark:text-white/20 font-medium italic">Interactive Knowledge Graph Standby</p>
                      )}
                    </div>
                 </div>
              </CardContent>
           </Card>
        </div>

        <div className="space-y-6">
           <Card className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10">
              <CardHeader>
                 <CardTitle className="text-sm">Agent Activity</CardTitle>
              </CardHeader>
              <CardContent>
                 <ScrollArea className="h-[400px] pr-4">
                    <div className="space-y-6">
                       {isRunning && (
                         <div className="flex gap-3 animate-pulse">
                            <div className="w-8 h-8 rounded-lg bg-yellow-50 dark:bg-yellow-500/10 flex items-center justify-center shrink-0">
                               <Search className="w-4 h-4 text-yellow-500" />
                            </div>
                            <div>
                               <p className="text-xs text-yellow-700 dark:text-yellow-400 font-bold">Vector Search in progress...</p>
                               <p className="text-[10px] text-gray-600 dark:text-white/20 mt-1">now</p>
                            </div>
                         </div>
                       )}
                       {[
                         { icon: Sparkles, text: "Extracted novel relationship: MCL-1 <-> Venetoclax Resistance", time: "2m ago" },
                         { icon: BrainCircuit, text: "Synthesized abstract from 14 clinical trials", time: "15m ago" },
                         { icon: MessageSquare, text: "User queried: 'Are there any dual MCL-1/BCL-2 inhibitors?'", time: "1h ago" },
                         { icon: FileText, text: "Ingested PDF: 'Emerging targets in CLL'", time: "4h ago" },
                       ].map((item, i) => (
                         <div key={i} className="flex gap-3">
                            <div className="w-8 h-8 rounded-lg bg-white dark:bg-white/5 flex items-center justify-center shrink-0">
                               <item.icon className="w-4 h-4 text-yellow-500/60" />
                            </div>
                            <div>
                               <p className="text-xs text-gray-700 dark:text-white/80 leading-tight">{item.text}</p>
                               <p className="text-[10px] text-gray-600 dark:text-white/20 mt-1">{item.time}</p>
                            </div>
                         </div>
                       ))}
                    </div>
                 </ScrollArea>
              </CardContent>
           </Card>
        </div>
      </div>
    </div>
  );
}
