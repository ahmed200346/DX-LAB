"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { motion, AnimatePresence } from "framer-motion";
import { Database, File, Upload, Search, Filter, MoreVertical, HardDrive, Share2, Trash2, Loader2, CheckCircle2, Inbox } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";

export default function DataManagerView() {
  const [isRunning, setIsRunning] = useState(false);
  const [hasFiles, setHasFiles] = useState(false);
  const [files, setFiles] = useState<any[]>([]);
  const [doiInput, setDoiInput] = useState("");

  const runIndexing = async () => {
    setIsRunning(true);
    setHasFiles(true);
    
    let itemsToIndex = [];

    if (doiInput.trim()) {
      itemsToIndex = [{ 
        name: `Extracted_Paper_${doiInput.replace(/[^a-zA-Z0-9]/g, '_')}.pdf`, 
        size: (Math.random() * 4 + 1).toFixed(1) + " MB", 
        type: "pdf", 
        date: new Date().toISOString().split("T")[0], 
        status: "Indexing..." 
      }];
    } else {
      setFiles([]);
      itemsToIndex = [
        { name: "BCL2_P10415_Complex_PDB.zip", size: "42.5 MB", type: "zip", date: "2026-05-01", status: "Indexing..." },
        { name: "PMID: 26822266_Venetoclax_CLL.pdf", size: "1.2 MB", type: "pdf", date: "2026-05-02", status: "Indexing..." },
        { name: "Ensemble_Docking_Scores_BCL2.json", size: "2.4 MB", type: "json", date: new Date().toISOString().split("T")[0], status: "Indexing..." },
        { name: "Venetoclax_Analog_SMILES.smi", size: "15.8 MB", type: "smi", date: "2026-04-28", status: "Indexing..." },
      ];
    }
    
    for (let i = 0; i < itemsToIndex.length; i++) {
      // Add file as "Indexing..."
      setFiles(prev => [itemsToIndex[i], ...prev]);
      await new Promise(r => setTimeout(r, 1500 + Math.random() * 1500));
      // Update file to "Indexed"
      setFiles(prev => prev.map(f => f.name === itemsToIndex[i].name ? { ...f, status: "Indexed" } : f));
    }
    
    setDoiInput("");
    setIsRunning(false);
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-2xl font-bold">Data Management</h3>
          <p className="text-gray-600 dark:text-gray-500 dark:text-white/40 text-sm">Unified storage and knowledge indexing for all lab assets</p>
        </div>
        <div className="flex gap-3 items-center">
           <div className="relative w-[280px]">
             <Input 
               value={doiInput}
               onChange={e => setDoiInput(e.target.value)}
               placeholder="Import via DOI or PMID..." 
               className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 text-sm h-10 pr-10 focus:ring-purple-500/50"
               onKeyDown={e => { if (e.key === 'Enter' && !isRunning) runIndexing(); }}
             />
             <Search className="absolute right-3 top-3 w-4 h-4 text-gray-400" />
           </div>
           <Button variant="outline" className="border-gray-200 dark:border-white/10 hover:bg-white dark:bg-white/5 h-10">
              <HardDrive className="w-4 h-4 mr-2" />
              Storage Stats
           </Button>
           <Button 
             onClick={runIndexing}
             disabled={isRunning || (hasFiles && !doiInput.trim())}
             className="bg-purple-600 hover:bg-purple-700 shadow-lg shadow-purple-600/20 min-w-[140px] text-white h-10"
           >
              {isRunning ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Upload className="w-4 h-4 mr-2" />}
              {isRunning ? "Indexing..." : "Index Files"}
           </Button>
        </div>
      </div>

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
                      <p className="text-xs text-gray-400 dark:text-white/20 mt-1">Upload research documents or structural data to begin</p>
                    </div>
                    <Button variant="outline" size="sm" onClick={runIndexing} className="mt-2">Index Sample Data</Button>
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
                              key={file.name} 
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

           <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <Card className="bg-gradient-to-br from-purple-600/10 to-transparent border-gray-200 dark:border-white/10">
                 <CardHeader>
                    <CardTitle className="text-sm">Knowledge Coverage</CardTitle>
                 </CardHeader>
                 <CardContent>
                    <div className="flex items-end gap-4">
                       <p className="text-4xl font-bold">{isRunning ? "Updating..." : (hasFiles ? "14,250" : "0")}</p>
                       <p className="text-xs text-gray-600 dark:text-gray-500 dark:text-white/40 mb-1.5">Indexed Entities</p>
                    </div>
                    <div className="mt-4 flex gap-1 h-2 w-full rounded-full overflow-hidden bg-white dark:bg-white/5">
                       <motion.div 
                         animate={{ width: isRunning ? "65%" : (hasFiles ? "60%" : "0%") }}
                         className="h-full bg-purple-500 shadow-[0_0_8px_rgba(168,85,247,0.4)]" 
                       />
                       <div className="h-full bg-blue-500 w-[25%]" style={{ width: hasFiles ? '25%' : '0%' }} />
                       <div className="h-full bg-emerald-500 w-[15%]" style={{ width: hasFiles ? '15%' : '0%' }} />
                    </div>
                 </CardContent>
              </Card>

              <Card className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 flex items-center justify-center p-8">
                 <div className="text-center space-y-4">
                    <Database className={cn(
                      "w-10 h-10 text-purple-700 dark:text-purple-400 mx-auto transition-all duration-1000",
                      isRunning ? "opacity-100 scale-110 rotate-12" : "opacity-20"
                    )} />
                    <p className="text-sm text-gray-600 dark:text-gray-500 dark:text-white/40 italic">"Connect to external databases like ChEMBL, UniProt or PubMed to expand your knowledge base."</p>
                    <Button variant="link" className="text-purple-700 dark:text-purple-400 h-auto p-0">Configure Adapters</Button>
                 </div>
              </Card>
           </div>
        </div>
      </div>
    </div>
  );
}
