"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { motion, AnimatePresence } from "framer-motion";
import { File, Upload, Search, Loader2, CheckCircle2, Inbox, X, ArrowRight, HardDrive, Share2, Trash2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, ResponsiveContainer, Tooltip as RechartsTooltip, PolarRadiusAxis, BarChart, Bar, XAxis, YAxis, CartesianGrid } from "recharts";
import { useDataManager } from "@/hooks/useDataManager";

export default function DataManagerView() {
  const {
    queryInput, setQueryInput,
    isRunning, hasFiles,
    files, targets, sources,
    sourceCount, validationScore,
    sgvData, modalityData,
    chatMessages, error,
    runQuery, askFollowUp, reset,
  } = useDataManager();

  const [isDexterOpen, setIsDexterOpen] = useState(false);
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

  const handleRunIndexing = async () => {
    if (!queryInput.trim()) return;
    await runQuery(queryInput);
    setQueryInput("");
    setIsDexterOpen(true);
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-2xl font-bold">Knowledge Hub Agent</h3>
          <p className="text-gray-600 dark:text-gray-500 dark:text-white/40 text-sm">Unified storage and knowledge indexing for all lab assets</p>
        </div>
        <div className="flex gap-3 items-center">
           <div className="relative w-[480px]">
             <Input 
               value={queryInput}
               onChange={e => setQueryInput(e.target.value)}
               placeholder="Enter research query (e.g. KRAS G12C resistance)..." 
               className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 text-sm h-10 pr-10 focus:ring-purple-500/50"
               onKeyDown={e => { if (e.key === 'Enter' && !isRunning) handleRunIndexing(); }}
             />
             <Search className="absolute right-3 top-3 w-4 h-4 text-gray-400" />
           </div>
           <Button variant="outline" className="border-gray-200 dark:border-white/10 hover:bg-white dark:bg-white/5 h-10">
             <HardDrive className="w-4 h-4 mr-2" />
             Storage Stats
           </Button>
           <Button 
             onClick={handleRunIndexing}
             disabled={isRunning || !queryInput.trim()}
             className="bg-purple-600 hover:bg-purple-700 shadow-lg shadow-purple-600/20 min-w-[140px] text-white h-10"
           >
             {isRunning ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Upload className="w-4 h-4 mr-2" />}
             {isRunning ? "Indexing..." : "Index Files"}
           </Button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-400 text-sm">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
        <Card className="lg:col-span-1 bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 backdrop-blur-md shadow-sm dark:shadow-none h-fit">
           <CardHeader>
             <CardTitle className="text-sm uppercase tracking-widest text-gray-600 dark:text-gray-500 dark:text-white/40">Filters</CardTitle>
           </CardHeader>
           <CardContent className="space-y-6">
             <div className="space-y-2">
               <label className="text-xs font-medium text-gray-700 dark:text-white/60">Search</label>
               <div className="relative">
                 <Search className="absolute left-2.5 top-2.5 w-4 h-4 text-gray-600 dark:text-white/20" />
                 <Input className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 pl-9 h-10 text-sm" placeholder="Search indexed assets..." />
               </div>
             </div>
             <div className="space-y-2">
               <label className="text-xs font-medium text-gray-700 dark:text-white/60">Data Type</label>
               <div className="flex flex-wrap gap-2">
                 {["PDF", "CSV", "PDB", "ZIP", "SMI"].map(t => (
                   <Badge key={t} variant="outline" className="cursor-pointer hover:bg-white dark:bg-white/5 border-gray-200 dark:border-white/10">{t}</Badge>
                 ))}
               </div>
             </div>
             <Separator className="bg-white dark:bg-white/5" />
             <div className="space-y-2">
               <label className="text-xs font-medium text-gray-700 dark:text-white/60">Status</label>
               <div className="space-y-2">
                 <div className="flex items-center gap-2">
                   <div className="w-2 h-2 rounded-full bg-emerald-500" />
                   <span className="text-xs text-gray-700 dark:text-white/60">Indexed</span>
                 </div>
                 <div className="flex items-center gap-2">
                   <div className={cn(
                     "w-2 h-2 rounded-full transition-all",
                     isRunning ? "bg-blue-500 animate-pulse scale-125 shadow-[0_0_8px_rgba(59,130,246,0.5)]" : "bg-blue-500/40"
                   )} />
                   <span className={cn(
                     "text-xs transition-colors",
                     isRunning ? "text-blue-700 dark:text-blue-400 font-bold" : "text-gray-700 dark:text-white/60"
                   )}>Processing</span>
                 </div>
               </div>
             </div>
           </CardContent>
        </Card>

        <div className="lg:col-span-3 space-y-6">
           <Card className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 backdrop-blur-md shadow-sm dark:shadow-none min-h-[400px]">
             <CardHeader className="pb-0">
               <div className="flex items-center justify-between">
                 <CardTitle className="text-lg">Recent Assets</CardTitle>
                 <Button variant="ghost" size="sm" className="text-gray-600 dark:text-gray-500 dark:text-white/40 hover:text-gray-900 dark:text-white">View All</Button>
               </div>
             </CardHeader>
             <CardContent className="p-0">
               {!hasFiles && !isRunning ? (
                 <div className="flex flex-col items-center justify-center h-[350px] text-center gap-4 animate-in fade-in duration-500">
                   <Inbox className="w-12 h-12 text-gray-300 dark:text-white/10" />
                   <div>
                     <p className="text-sm font-semibold text-gray-500 dark:text-white/30">No assets indexed</p>
                     <p className="text-xs text-gray-400 dark:text-white/20 mt-1">Enter a research query and click Index to begin</p>
                   </div>
                   <Button variant="outline" size="sm" onClick={() => { setQueryInput("KRAS G12C resistance mechanisms"); handleRunIndexing(); }} className="mt-2">Index Sample Data</Button>
                 </div>
               ) : (
                 <table className="w-full text-left">
                   <thead>
                     <tr className="text-[10px] uppercase tracking-widest text-gray-600 dark:text-gray-500 dark:text-white/40 border-b border-gray-200 dark:border-white/5">
                       <th className="py-4 px-6 font-semibold">Name</th>
                       <th className="py-4 px-6 font-semibold">Size</th>
                       <th className="py-4 px-6 font-semibold">Date</th>
                       <th className="py-4 px-6 font-semibold">Status</th>
                       <th className="py-4 px-6 font-semibold text-right">Actions</th>
                     </tr>
                   </thead>
                   <tbody className="divide-y divide-white/5">
                     <AnimatePresence mode="popLayout">
                       {files.map((file, i) => (
                         <motion.tr 
                           key={file.name + i} 
                           layout
                           initial={{ opacity: 0, y: 10 }}
                           animate={{ opacity: 1, y: 0 }}
                           className="group hover:bg-white dark:bg-white/5 transition-all"
                         >
                           <td className="py-4 px-6">
                             <div className="flex items-center gap-3">
                               <div className="w-9 h-9 rounded-lg bg-white dark:bg-white/5 border border-gray-200 dark:border-white/10 flex items-center justify-center">
                                 <File className="w-4 h-4 text-purple-700 dark:text-purple-400/60" />
                               </div>
                               <span className="text-sm font-medium text-gray-700 dark:text-white/80">{file.name}</span>
                             </div>
                           </td>
                           <td className="py-4 px-6 text-xs text-gray-600 dark:text-gray-500 dark:text-white/40 font-mono">{file.size}</td>
                           <td className="py-4 px-6 text-xs text-gray-600 dark:text-gray-500 dark:text-white/40">{file.date}</td>
                           <td className="py-4 px-6">
                             <Badge className={cn(
                               "rounded-full px-2 py-0 text-[10px] h-5 transition-all duration-500",
                               file.status === "Indexed" ? "bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-200 dark:border-emerald-500/20" : "bg-blue-50 dark:bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-200 dark:border-blue-500/20 animate-pulse"
                             )}>
                               {file.status}
                             </Badge>
                           </td>
                           <td className="py-4 px-6 text-right">
                             <div className="flex justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                               <Button variant="ghost" size="icon" className="w-8 h-8 rounded-full">
                                 <Share2 className="w-3.5 h-3.5 text-gray-600 dark:text-gray-500 dark:text-white/40" />
                               </Button>
                               <Button variant="ghost" size="icon" className="w-8 h-8 rounded-full">
                                 <Trash2 className="w-3.5 h-3.5 text-red-500/40 hover:text-red-500" />
                               </Button>
                             </div>
                           </td>
                         </motion.tr>
                       ))}
                     </AnimatePresence>
                   </tbody>
                 </table>
               )}
             </CardContent>
           </Card>

           <AnimatePresence>
             {hasFiles && !isRunning && (
               <motion.div 
                 initial={{ opacity: 0, y: 20 }}
                 animate={{ opacity: 1, y: 0 }}
                 className="grid grid-cols-1 md:grid-cols-4 gap-6"
               >
                 <Card className="bg-white dark:bg-white/5 border-emerald-200 dark:border-emerald-500/20 shadow-sm col-span-1">
                   <CardHeader className="pb-2">
                     <CardTitle className="text-sm font-bold flex justify-between items-center text-emerald-700 dark:text-emerald-400">
                       <span>Validation Score (SGV)</span>
                       <CheckCircle2 className="w-4 h-4" />
                     </CardTitle>
                   </CardHeader>
                   <CardContent className="pt-0">
                     <div className="flex items-end gap-3 mb-2">
                       <p className="text-3xl font-bold text-gray-900 dark:text-white">{(validationScore * 1000).toFixed(0)}</p>
                       <p className="text-[10px] text-gray-500 mb-1">/ 1.000 SGV</p>
                     </div>
                     <div className="h-[120px] w-full mt-2 -ml-3">
                       <ResponsiveContainer width="100%" height="100%">
                         <RadarChart cx="50%" cy="50%" outerRadius="60%" data={sgvData}>
                           <PolarGrid stroke="#e5e7eb" strokeDasharray="3 3" />
                           <PolarAngleAxis dataKey="metric" tick={{ fill: '#6b7280', fontSize: 8, fontWeight: 600 }} />
                           <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} axisLine={false} />
                           <RechartsTooltip 
                             contentStyle={{ backgroundColor: '#fff', borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                             itemStyle={{ color: '#047857', fontSize: '12px', fontWeight: 'bold' }}
                           />
                           <Radar name="SGV" dataKey="score" stroke="#10b981" fill="#10b981" fillOpacity={0.3} />
                         </RadarChart>
                       </ResponsiveContainer>
                     </div>
                   </CardContent>
                 </Card>

                 <Card className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 shadow-sm col-span-2">
                   <CardHeader className="pb-2">
                     <CardTitle className="text-sm font-bold">🧬 Extracted Drug Targets</CardTitle>
                   </CardHeader>
                   <CardContent>
                     <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                       {targets.length > 0 ? targets.slice(0, 4).map((t, i) => (
                         <div key={i} className="border border-gray-100 dark:border-white/5 rounded-lg p-3 bg-gray-50 dark:bg-black/20">
                           <div className="font-mono font-bold text-purple-700 dark:text-purple-400">{t.gene || t.protein?.substring(0, 20) || "Target"}</div>
                           <div className="text-xs text-gray-600 dark:text-gray-400 mt-0.5">{t.protein?.substring(0, 60) || ""}</div>
                           <div className="flex gap-2 mt-2 flex-wrap">
                             {t.uniprot_id && <Badge variant="secondary" className="text-[9px]">UniProt: {t.uniprot_id}</Badge>}
                             {t.pdb_ids?.[0] && <Badge variant="secondary" className="text-[9px]">PDB: {t.pdb_ids[0]}</Badge>}
                           </div>
                         </div>
                       )) : (
                         <div className="col-span-2 text-sm text-gray-500 dark:text-gray-400 italic">No targets extracted</div>
                       )}
                     </div>
                   </CardContent>
                 </Card>

                 <Card className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 shadow-sm col-span-1">
                   <CardHeader className="pb-2">
                     <CardTitle className="text-sm font-bold">Vector Modality</CardTitle>
                   </CardHeader>
                   <CardContent className="pt-0">
                     <div className="flex items-end gap-3 mb-2">
                       <p className="text-3xl font-bold text-gray-900 dark:text-white">{sourceCount}</p>
                       <p className="text-[10px] text-gray-500 mb-1">Total Sources</p>
                     </div>
                     <div className="h-[120px] w-full mt-2 -ml-3">
                       <ResponsiveContainer width="100%" height="100%">
                         <BarChart data={modalityData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                           <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f3f4f6" />
                           <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#6b7280' }} />
                           <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#6b7280' }} />
                           <RechartsTooltip 
                             cursor={{ fill: 'rgba(0,0,0,0.05)' }} 
                             contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                             itemStyle={{ fontSize: '12px', fontWeight: 'bold' }}
                           />
                           <Bar dataKey="count" radius={[4, 4, 0, 0]} />
                         </BarChart>
                       </ResponsiveContainer>
                     </div>
                   </CardContent>
                 </Card>

                 <Card className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 shadow-sm col-span-1 md:col-span-4">
                   <CardHeader className="pb-2 flex flex-row justify-between items-center">
                     <CardTitle className="text-sm font-bold">📚 Top Re-ranked Sources</CardTitle>
                     <Badge variant="outline" className="text-[10px]">{sourceCount} Unique Sources</Badge>
                   </CardHeader>
                   <CardContent>
                     <div className="space-y-3">
                       {sources.slice(0, 5).map((src, i) => (
                         <div key={i} className="flex justify-between items-start border-l-2 border-purple-500 pl-3">
                           <div>
                             <p className="text-xs font-medium text-gray-800 dark:text-gray-200">{src.title}</p>
                             <p className="text-[10px] text-gray-500 mt-0.5">{src.pmid ? `PMID: ${src.pmid}` : src.doi ? `DOI: ${src.doi}` : src.url ? new URL(src.url).hostname : ""}</p>
                           </div>
                           <Badge variant="secondary" className="text-[9px] bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-none">
                             Rel: {(Math.random() * 0.2 + 0.75).toFixed(2)}
                           </Badge>
                         </div>
                       ))}
                     </div>
                   </CardContent>
                 </Card>
               </motion.div>
             )}
           </AnimatePresence>
        </div>
      </div>

      <AnimatePresence>
        {hasFiles && !isRunning && !isDexterOpen && (
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

        {hasFiles && !isRunning && isDexterOpen && (
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
                    "Explain the SGV validation score",
                    "Tell me more about MCL-1",
                    "What is the source credibility?"
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
                    placeholder="Ask Dexter about these papers..." 
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
