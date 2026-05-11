"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Sparkles, FileText, BrainCircuit, Plus, ArrowRight, ZapOff, Loader2, Search, MessageSquare, X
} from "lucide-react";
import { Card, CardContent, CardTitle, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useHypothesis } from "@/hooks/useHypothesis";

export default function HypothesisAgentView() {
  const {
    query, setQuery,
    isRunning, hasRun,
    hypotheses, currentAction,
    selectedHypothesis, setSelectedHypothesis,
    activities, chatMessages, error,
    generate, askFollowUp, reset,
  } = useHypothesis();

  const [isDexterOpen, setIsDexterOpen] = useState(true);
  const [dexterInput, setDexterInput] = useState("");
  const [isDexterThinking, setIsDexterThinking] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [chatMessages, isDexterThinking]);

  const handleDexterSubmit = async (text: string) => {
    if (!text.trim() || isDexterThinking) return;
    setDexterInput("");
    setIsDexterThinking(true);
    await askFollowUp(text);
    setIsDexterThinking(false);
  };

  const handleGenerate = async () => {
    if (!query.trim()) return;
    await generate(query);
    setIsDexterOpen(true);
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-2xl font-bold">Hypothesis Assistant</h3>
          <p className="text-gray-600 dark:text-gray-500 dark:text-white/40 text-sm">AI-driven generation of research directions and mechanism of action models</p>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-400 text-sm">{error}</div>
      )}

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
                onKeyDown={(e) => { if (e.key === 'Enter') handleGenerate(); }}
              />
            </div>
            <div className="md:col-span-1">
              <Button 
                onClick={handleGenerate} 
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
                    <p className="text-yellow-600 dark:text-yellow-500/80 font-mono text-sm text-center px-4">{currentAction || "Processing..."}</p>
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
                          <FileText className="w-3.5 h-3.5 text-yellow-500/60" />
                        </div>
                        <div>
                          <p className="text-[11px] text-gray-700 dark:text-white/80 leading-tight">{item.text}</p>
                          <p className="text-[9px] text-gray-400 mt-1">{item.time}</p>
                        </div>
                      </div>
                    ))}
                    {isRunning && (
                      <div className="flex gap-3">
                        <div className="w-7 h-7 rounded-lg bg-yellow-500/10 flex items-center justify-center shrink-0 animate-pulse">
                          <Search className="w-3.5 h-3.5 text-yellow-500" />
                        </div>
                        <div>
                          <p className="text-[11px] text-yellow-600 dark:text-yellow-400 leading-tight">{currentAction}</p>
                          <p className="text-[9px] text-gray-400 mt-1">processing...</p>
                        </div>
                      </div>
                    )}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      <AnimatePresence>
        {hasRun && !isRunning && !isDexterOpen && (
          <motion.div
            initial={{ opacity: 0, scale: 0 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0 }}
            className="fixed bottom-24 right-6 z-50"
          >
            <Button 
              onClick={() => setIsDexterOpen(true)}
              className="w-14 h-14 rounded-full bg-blue-600 hover:bg-blue-700 shadow-2xl shadow-blue-600/30 p-0 relative group"
            >
              <div className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 rounded-full border-2 border-white animate-pulse" />
              <img src="https://api.dicebear.com/7.x/bottts/svg?seed=Dexter&backgroundColor=transparent" alt="Dexter" className="w-10 h-10 group-hover:scale-110 transition-transform" />
            </Button>
          </motion.div>
        )}

        {hasRun && !isRunning && isDexterOpen && (
          <motion.div
            initial={{ opacity: 0, y: 50, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 50, scale: 0.9 }}
            className="fixed bottom-24 right-6 w-[360px] z-50"
          >
            <Card className="bg-white dark:bg-slate-900 border-gray-200 dark:border-white/10 overflow-hidden h-[480px] flex flex-col shadow-2xl rounded-xl">
              <CardHeader className="bg-blue-600 py-3 px-4 flex flex-row items-center justify-between shadow-md z-10">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-white flex items-center justify-center overflow-hidden border-2 border-white/20 shadow-inner">
                    <img src="https://api.dicebear.com/7.x/bottts/svg?seed=Dexter&backgroundColor=transparent" alt="Dexter" className="w-full h-full" />
                  </div>
                  <div>
                    <CardTitle className="text-sm font-bold text-white tracking-wide">Dexter Assistant</CardTitle>
                    <p className="text-[10px] text-blue-200">Online • Context Aware</p>
                  </div>
                </div>
                <Button variant="ghost" size="icon" className="text-white hover:bg-blue-700 w-8 h-8 rounded-full" onClick={() => setIsDexterOpen(false)}>
                  <X className="w-4 h-4" />
                </Button>
              </CardHeader>
              
              <CardContent className="flex-1 p-0 flex flex-col bg-gray-50 dark:bg-black/40 overflow-hidden">
                <ScrollArea className="flex-1 p-4">
                  <div className="space-y-4 pb-4">
                    {chatMessages.map((msg, i) => (
                      <div key={i} className={cn("flex", msg.role === 'user' ? "justify-end" : "justify-start")}>
                        <div className={cn(
                          "p-3 rounded-2xl max-w-[85%] shadow-sm",
                          msg.role === 'user' 
                            ? "bg-blue-600 text-white rounded-tr-sm" 
                            : "bg-white dark:bg-slate-800 border border-gray-100 dark:border-white/5 rounded-tl-sm text-gray-700 dark:text-gray-300"
                        )}>
                          <p className="text-[12px] leading-relaxed">{msg.content}</p>
                        </div>
                      </div>
                    ))}
                    
                    {isDexterThinking && (
                      <div className="flex justify-start">
                        <div className="bg-white dark:bg-slate-800 border border-gray-100 dark:border-white/5 p-3 rounded-2xl rounded-tl-sm shadow-sm flex gap-1 items-center">
                          <div className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                          <div className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                          <div className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                        </div>
                      </div>
                    )}
                    <div ref={scrollRef} />
                  </div>
                </ScrollArea>
                
                <div className="px-3 pb-2 flex gap-2 overflow-x-auto no-scrollbar">
                  {chatMessages.length === 1 && !isDexterThinking && [
                    "How do we validate MCL-1 dependency?",
                    "What's the toxicity profile of BCL-xL inhibitors?",
                    "Elaborate on PRAME lipidomic shifts"
                  ].map((sq, i) => (
                    <button 
                      key={i}
                      onClick={() => handleDexterSubmit(sq)}
                      className="shrink-0 bg-blue-50 hover:bg-blue-100 text-blue-700 border border-blue-200 text-[10px] px-3 py-1.5 rounded-full font-medium transition-colors whitespace-nowrap"
                    >
                      {sq}
                    </button>
                  ))}
                </div>

                <div className="p-3 bg-white dark:bg-slate-900 border-t border-gray-100 dark:border-white/10 flex gap-2 shadow-inner items-center">
                  <Input 
                    value={dexterInput}
                    onChange={(e) => setDexterInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') handleDexterSubmit(dexterInput); }}
                    className="bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 h-10 text-xs rounded-full px-4 focus-visible:ring-blue-500 flex-1" 
                    placeholder="Ask Dexter..." 
                    disabled={isDexterThinking}
                  />
                  <Button 
                    size="icon" 
                    onClick={() => handleDexterSubmit(dexterInput)}
                    disabled={!dexterInput.trim() || isDexterThinking}
                    className="bg-blue-600 hover:bg-blue-700 h-10 w-10 shrink-0 rounded-full shadow-md transition-transform hover:scale-105 disabled:opacity-50"
                  >
                    <ArrowRight className="w-4 h-4 text-white" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
