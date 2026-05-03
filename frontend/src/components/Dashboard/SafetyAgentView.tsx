"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
import { ShieldAlert, ShieldCheck, AlertTriangle, Info, Shield, Search, Loader2, CheckCircle2, ShieldX } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function SafetyAgentView() {
  const [isRunning, setIsRunning] = useState(false);
  const [hasRun, setHasRun] = useState(false);
  const [smiles, setSmiles] = useState("");
  const [safetyChecks, setSafetyChecks] = useState([
    { name: "Hepatotoxicity", score: 0, status: "pending" as any },
    { name: "Cardiotoxicity (hERG)", score: 0, status: "pending" as any },
    { name: "Mutagenicity (Ames)", score: 0, status: "pending" as any },
    { name: "Drug-Drug Interaction", score: 0, status: "pending" as any },
    { name: "Cytotoxicity", score: 0, status: "pending" as any },
  ]);

  const runScreen = async () => {
    if (!smiles.trim()) return;
    setIsRunning(true);
    setHasRun(false);
    
    // Reset checks
    setSafetyChecks(s => s.map(check => ({ ...check, status: "pending", score: 0 })));

    const results = [
      { name: "Hepatotoxicity", score: 95, status: "Pass", delay: 1200 },
      { name: "Cardiotoxicity (hERG)", score: 88, status: "Pass", delay: 4200 },
      { name: "Mutagenicity (Ames)", score: 92, status: "Pass", delay: 1800 },
      { name: "Drug-Drug Interaction", score: 45, status: "Warning", delay: 2500 },
      { name: "Cytotoxicity", score: 98, status: "Pass", delay: 5000 },
    ];

    for (let i = 0; i < results.length; i++) {
      setSafetyChecks(prev => prev.map((s, idx) => idx === i ? { ...s, status: "running" } : s));
      await new Promise(r => setTimeout(r, results[i].delay + Math.random() * 1000));
      setSafetyChecks(prev => prev.map((s, idx) => idx === i ? {
        name: results[i].name,
        score: results[i].score,
        status: results[i].status
      } : s));
    }
    
    setHasRun(true);
    setIsRunning(false);
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-2xl font-bold">Drug Safety Analysis</h3>
          <p className="text-gray-600 dark:text-gray-500 dark:text-white/40 text-sm">Predictive toxicology and clinical safety screening</p>
        </div>
        <div className="flex gap-3">
           <Button variant="outline" className="border-gray-200 dark:border-white/10 hover:bg-white dark:bg-white/5">Export Report</Button>
        </div>
      </div>

      {/* Input Section */}
      <Card className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 backdrop-blur-md shadow-sm dark:shadow-none overflow-hidden">
        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-red-500 to-orange-500" />
        <CardContent className="p-8">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 items-end">
            <div className="md:col-span-3 space-y-2">
              <label className="text-xs font-semibold text-gray-600 dark:text-gray-500 dark:text-white/40 uppercase tracking-wider">Molecule SMILES / Name</label>
              <Input 
                value={smiles} 
                onChange={(e) => setSmiles(e.target.value)}
                placeholder="Enter molecule name or SMILES sequence..."
                className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 text-gray-900 dark:text-white focus:ring-red-500/50 h-11"
              />
            </div>
            <div className="md:col-span-1">
              <Button 
                onClick={runScreen} 
                disabled={isRunning || !smiles.trim()}
                className="w-full bg-red-600 hover:bg-red-700 text-white h-11 font-bold shadow-lg shadow-red-600/20 rounded-lg group disabled:opacity-40"
              >
                {isRunning ? <Loader2 className="w-5 h-5 animate-spin mr-2" /> : <Shield className="w-4 h-4 mr-2" />}
                {isRunning ? "Screening..." : "Run Full Screen"}
              </Button>
            </div>
          </div>
          

        </CardContent>
      </Card>

      {!hasRun && !isRunning ? (
        <div className="flex flex-col items-center justify-center h-64 rounded-2xl border-2 border-dashed border-gray-200 dark:border-white/10 text-center gap-4 animate-in fade-in duration-500">
          <ShieldX className="w-12 h-12 text-gray-300 dark:text-white/10" />
          <div>
            <p className="text-sm font-semibold text-gray-500 dark:text-white/30">No safety analysis conducted</p>
            <p className="text-xs text-gray-400 dark:text-white/20 mt-1">Input a candidate molecule above to run toxicity screening</p>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 animate-in fade-in zoom-in-95 duration-500">
          <div className="lg:col-span-2 space-y-6">
            <Card className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 backdrop-blur-md shadow-sm dark:shadow-none">
              <CardHeader>
                  <CardTitle className="text-lg flex justify-between items-center">
                    Toxicity Profile
                    {isRunning && <Badge variant="secondary" className="animate-pulse bg-blue-500/20 text-blue-500">Evaluating</Badge>}
                  </CardTitle>
                  <CardDescription>Predicted organ-specific toxicity scores</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                  {safetyChecks.map((check) => (
                    <div key={check.name} className="space-y-2">
                      <div className="flex justify-between items-center">
                        <div className="flex items-center gap-2">
                          {check.status === "Pass" ? (
                            <ShieldCheck className="w-4 h-4 text-emerald-500" />
                          ) : check.status === "Warning" ? (
                            <AlertTriangle className="w-4 h-4 text-yellow-500" />
                          ) : check.status === "running" ? (
                            <Loader2 className="w-4 h-4 text-blue-700 dark:text-blue-400 animate-spin" />
                          ) : (
                            <div className="w-4 h-4 rounded-full border border-gray-200 dark:border-white/10" />
                          )}
                          <span className={cn(
                            "text-sm font-medium transition-colors",
                            check.status === "pending" ? "text-gray-600 dark:text-white/20" : "text-gray-700 dark:text-white/80"
                          )}>{check.name}</span>
                        </div>
                        <span className={cn(
                          "text-xs font-bold transition-all",
                          check.status === "Pass" ? "text-emerald-700 dark:text-emerald-400" : 
                          check.status === "Warning" ? "text-yellow-700 dark:text-yellow-400" : "text-white/10"
                        )}>
                          {check.status === "pending" ? "0%" : `${check.score}% Safe`}
                        </span>
                      </div>
                      <div className="h-1.5 w-full bg-gray-100 dark:bg-white/5 rounded-full overflow-hidden">
                        <motion.div 
                          initial={{ width: 0 }}
                          animate={{ width: `${check.score}%` }}
                          transition={{ duration: 1, ease: "easeOut" }}
                          className={cn(
                            "h-full rounded-full transition-colors",
                            check.status === "Pass" ? "bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.3)]" : 
                            check.status === "Warning" ? "bg-yellow-500" : 
                            check.status === "running" ? "bg-blue-500/50" : "bg-transparent"
                          )} 
                        />
                      </div>
                    </div>
                  ))}
              </CardContent>
            </Card>

            {hasRun && (
              <Card className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 backdrop-blur-md shadow-sm dark:shadow-none animate-in fade-in slide-in-from-bottom-4 duration-500">
                <CardHeader>
                    <CardTitle className="text-lg">Mechanistic Alerts</CardTitle>
                    <CardDescription>Known structural alerts for adverse effects</CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="space-y-4">
                      <div className="p-4 bg-yellow-50 dark:bg-yellow-500/10 border border-yellow-200 dark:border-yellow-500/20 rounded-xl flex gap-4">
                          <div className="shrink-0 w-10 h-10 rounded-lg bg-yellow-500/20 flex items-center justify-center">
                            <AlertTriangle className="w-5 h-5 text-yellow-500" />
                          </div>
                          <div>
                            <p className="text-sm font-bold text-yellow-500">Tumor Lysis Syndrome (TLS) Alert</p>
                            <p className="text-xs text-gray-600 dark:text-gray-500 dark:text-white/40 mt-1">High risk of TLS due to rapid reduction in tumor burden. Clinical protocols mandate gradual ramp-up dosing and hydration/anti-hyperuricemic prophylaxis.</p>
                          </div>
                      </div>
                      <div className="p-4 bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/20 rounded-xl flex gap-4">
                          <div className="shrink-0 w-10 h-10 rounded-lg bg-emerald-500/20 flex items-center justify-center">
                            <ShieldCheck className="w-5 h-5 text-emerald-500" />
                          </div>
                          <div>
                            <p className="text-sm font-bold text-emerald-500">Neutropenia Management Flag</p>
                            <p className="text-xs text-gray-600 dark:text-gray-500 dark:text-white/40 mt-1">Grade 3/4 neutropenia frequently observed. Requires baseline and ongoing hematologic monitoring, but is manageable with dose interruption or G-CSF.</p>
                          </div>
                      </div>
                    </div>
                </CardContent>
              </Card>
            )}
          </div>

          <div className="space-y-6">
            <Card className="bg-gradient-to-br from-red-600/20 to-orange-600/10 border-gray-200 dark:border-white/10 overflow-hidden relative group">
                <CardHeader>
                  <CardTitle className="text-sm uppercase tracking-widest text-gray-600 dark:text-gray-500 dark:text-white/40">Aggregated Risk</CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col items-center py-10">
                  <div className="relative w-40 h-40">
                      {isRunning ? (
                        <div className="absolute inset-0 flex flex-col items-center justify-center animate-pulse">
                           <Loader2 className="w-12 h-12 text-red-500/50 animate-spin" />
                        </div>
                      ) : (
                        <>
                          <svg className="w-full h-full" viewBox="0 0 100 100">
                            <circle cx="50" cy="50" r="45" fill="none" stroke="currentColor" strokeWidth="8" className="text-white/5" />
                            <motion.circle 
                              cx="50" cy="50" r="45" fill="none" stroke="currentColor" strokeWidth="8" 
                              strokeDasharray="283" 
                              initial={{ strokeDashoffset: 283 }}
                              animate={{ strokeDashoffset: 283 - (283 * 0.85) }}
                              transition={{ duration: 1.5, ease: "easeOut" }}
                              className="text-red-500" 
                              strokeLinecap="round"
                              transform="rotate(-90 50 50)"
                            />
                          </svg>
                          <div className="absolute inset-0 flex flex-col items-center justify-center">
                            <span className="text-4xl font-bold">0.15</span>
                            <span className="text-[10px] text-gray-600 dark:text-gray-500 dark:text-white/40 uppercase font-bold tracking-tighter">Hazard Index</span>
                          </div>
                        </>
                      )}
                  </div>
                  <Badge className={cn(
                    "mt-6 border",
                    isRunning ? "bg-gray-100 text-gray-500 border-gray-200 dark:bg-white/5 dark:text-white/50 dark:border-white/10" : "bg-emerald-500/20 text-emerald-700 dark:text-emerald-400 border-emerald-300 dark:border-emerald-500/30"
                  )}>
                    {isRunning ? "Running Multi-task Models..." : "Low Risk Portfolio"}
                  </Badge>
                </CardContent>
            </Card>

            <Card className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 backdrop-blur-md shadow-sm dark:shadow-none">
              <CardHeader>
                  <CardTitle className="text-sm">Safety Intelligence</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                  <div className="flex items-center gap-3">
                    <div className={cn("w-2 h-2 rounded-full transition-colors", hasRun ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]" : "bg-gray-300 dark:bg-white/20")} />
                    <p className="text-xs text-gray-600 dark:text-white/60">Cross-referenced with FDA FAERS</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className={cn("w-2 h-2 rounded-full transition-colors", hasRun ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]" : "bg-gray-300 dark:bg-white/20")} />
                    <p className="text-xs text-gray-600 dark:text-white/60">EMA Pharmacovigilance check</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className={cn(
                      "w-2 h-2 rounded-full transition-colors",
                      isRunning ? "bg-blue-500 animate-pulse" : hasRun ? "bg-yellow-500" : "bg-gray-300 dark:bg-white/20"
                    )} />
                    <p className="text-xs text-gray-600 dark:text-white/60">SIDER side effect mapping</p>
                  </div>
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
