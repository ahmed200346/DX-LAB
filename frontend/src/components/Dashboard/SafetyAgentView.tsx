"use client";

import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
import { ShieldAlert, ShieldCheck, AlertTriangle, Shield, Loader2, ShieldX } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useSafetyAnalysis } from "@/hooks/useSafetyAnalysis";

export default function SafetyAgentView() {
  const {
    smiles, setSmiles,
    patientAge, setPatientAge,
    patientSex, setPatientSex,
    comorbidities, setComorbidities,
    isRunning, hasRun,
    safetyChecks, alerts,
    hazardIndex, overallRisk, error,
    analyze, reset,
  } = useSafetyAnalysis();

  const handleRunScreen = async () => {
    if (!smiles.trim()) return;
    await analyze(smiles, patientAge, patientSex, comorbidities);
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-2xl font-bold">Drug Safety Analysis</h3>
          <p className="text-gray-600 dark:text-gray-500 dark:text-white/40 text-sm">Predictive toxicology and clinical safety screening</p>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-400 text-sm">{error}</div>
      )}

      <Card className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 backdrop-blur-md shadow-sm dark:shadow-none overflow-hidden">
        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-red-500 to-orange-500" />
        <CardContent className="p-8">
          <div className="space-y-6">
            <div className="space-y-2">
              <label className="text-xs font-semibold text-gray-600 dark:text-gray-500 dark:text-white/40 uppercase tracking-wider">Molecule SMILES / Name</label>
              <Input 
                value={smiles} 
                onChange={(e) => setSmiles(e.target.value)}
                placeholder="Enter molecule name or SMILES sequence..."
                className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 text-gray-900 dark:text-white focus:ring-red-500/50 h-11"
              />
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6 items-end pt-2">
              <div className="space-y-2 md:col-span-1">
                <label className="text-xs font-semibold text-gray-600 dark:text-gray-500 dark:text-white/40 uppercase tracking-wider">Patient Age</label>
                <Input 
                  value={patientAge} 
                  onChange={(e) => setPatientAge(e.target.value)}
                  placeholder="Enter age" 
                  className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 text-gray-900 dark:text-white focus:ring-red-500/50 h-11"
                />
              </div>
              <div className="space-y-2 md:col-span-1">
                <label className="text-xs font-semibold text-gray-600 dark:text-gray-500 dark:text-white/40 uppercase tracking-wider">Patient Sex</label>
                <Input 
                  value={patientSex} 
                  onChange={(e) => setPatientSex(e.target.value)}
                  placeholder="M / F / Other" 
                  className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 text-gray-900 dark:text-white focus:ring-red-500/50 h-11"
                />
              </div>
              <div className="space-y-2 md:col-span-1">
                <label className="text-xs font-semibold text-gray-600 dark:text-gray-500 dark:text-white/40 uppercase tracking-wider">Comorbidities</label>
                <Input 
                  value={comorbidities} 
                  onChange={(e) => setComorbidities(e.target.value)}
                  placeholder="Enter comorbidities..." 
                  className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 text-gray-900 dark:text-white focus:ring-red-500/50 h-11"
                />
              </div>
              <div className="md:col-span-1">
                <Button 
                  onClick={handleRunScreen} 
                  disabled={isRunning || !smiles.trim()}
                  className="w-full bg-red-600 hover:bg-red-700 text-white h-11 font-bold shadow-lg shadow-red-600/20 rounded-lg group disabled:opacity-40"
                >
                  {isRunning ? <Loader2 className="w-5 h-5 animate-spin mr-2" /> : <Shield className="w-4 h-4 mr-2" />}
                  {isRunning ? "Screening..." : "Run Full Screen"}
                </Button>
              </div>
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

            {hasRun && alerts.length > 0 && (
              <Card className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 backdrop-blur-md shadow-sm dark:shadow-none animate-in fade-in slide-in-from-bottom-4 duration-500">
                <CardHeader>
                  <CardTitle className="text-lg">Mechanistic Alerts</CardTitle>
                  <CardDescription>Known structural alerts for adverse effects</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {alerts.map((alert, i) => (
                      <div key={i} className={cn(
                        "p-4 rounded-xl flex gap-4 border",
                        alert.level === "red" ? "bg-red-50 dark:bg-red-500/10 border-red-200 dark:border-red-500/20" :
                        alert.level === "yellow" ? "bg-yellow-50 dark:bg-yellow-500/10 border-yellow-200 dark:border-yellow-500/20" :
                        "bg-emerald-50 dark:bg-emerald-500/10 border-emerald-200 dark:border-emerald-500/20"
                      )}>
                        <div className={cn(
                          "shrink-0 w-10 h-10 rounded-lg flex items-center justify-center",
                          alert.level === "red" ? "bg-red-500/20" :
                          alert.level === "yellow" ? "bg-yellow-500/20" : "bg-emerald-500/20"
                        )}>
                          {alert.level === "red" ? <AlertTriangle className="w-5 h-5 text-red-500" /> :
                           alert.level === "yellow" ? <AlertTriangle className="w-5 h-5 text-yellow-500" /> :
                           <ShieldCheck className="w-5 h-5 text-emerald-500" />}
                        </div>
                        <div>
                          <p className={cn(
                            "text-sm font-bold",
                            alert.level === "red" ? "text-red-500" :
                            alert.level === "yellow" ? "text-yellow-500" : "text-emerald-500"
                          )}>{alert.label}</p>
                          <p className="text-xs text-gray-600 dark:text-gray-500 dark:text-white/40 mt-1">{alert.detail}</p>
                        </div>
                      </div>
                    ))}
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
                          animate={{ strokeDashoffset: 283 - (283 * Math.min(1, (1 - hazardIndex))) }}
                          transition={{ duration: 1.5, ease: "easeOut" }}
                          className={cn(
                            overallRisk === "Low" ? "text-emerald-500" :
                            overallRisk === "Moderate" ? "text-yellow-500" : "text-red-500"
                          )} 
                          strokeLinecap="round"
                          transform="rotate(-90 50 50)"
                        />
                      </svg>
                      <div className="absolute inset-0 flex flex-col items-center justify-center">
                        <span className="text-4xl font-bold">{hazardIndex.toFixed(2)}</span>
                        <span className="text-[10px] text-gray-600 dark:text-gray-500 dark:text-white/40 uppercase font-bold tracking-tighter">Hazard Index</span>
                      </div>
                    </>
                  )}
                </div>
                <Badge className={cn(
                  "mt-6 border",
                  isRunning ? "bg-gray-100 text-gray-500 border-gray-200 dark:bg-white/5 dark:text-white/50 dark:border-white/10" :
                  overallRisk === "Low" ? "bg-emerald-500/20 text-emerald-700 dark:text-emerald-400 border-emerald-300 dark:border-emerald-500/30" :
                  overallRisk === "Moderate" ? "bg-yellow-500/20 text-yellow-700 dark:text-yellow-400 border-yellow-300 dark:border-yellow-500/30" :
                  "bg-red-500/20 text-red-700 dark:text-red-400 border-red-300 dark:border-red-500/30"
                )}>
                  {isRunning ? "Running Multi-task Models..." : `${overallRisk || "Low"} Risk Portfolio`}
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
