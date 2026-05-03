"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { 
  Play, 
  RotateCcw, 
  Download, 
  ExternalLink, 
  Activity, 
  Database, 
  FlaskConical,
  CheckCircle2,
  Circle,
  Loader2,
  Info,
  Beaker,
  AlertCircle
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { 
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface PipelineStep {
  id: string;
  name: string;
  description: string;
  status: "pending" | "running" | "completed" | "error";
  progress?: number;
  details?: string;
}

export default function DiscoveryAgentView() {
  const [protein, setProtein] = useState("");
  const [disease, setDisease] = useState("");
  const [isRunning, setIsRunning] = useState(false);
  const [hasRun, setHasRun] = useState(false);
  const [runId, setRunId] = useState<string | null>(null);
  const [steps, setSteps] = useState<PipelineStep[]>([
    { id: "extraction", name: "Target Extraction", description: "Identifying gene, fasta and seed SMILES", status: "pending" },
    { id: "pooling", name: "Candidate Generation", description: "Running REINVENT generative models", status: "pending" },
    { id: "prediction", name: "Property Prediction", description: "Calculating pKd and ADMET scores", status: "pending" },
    { id: "refinement", name: "Iterative Refinement", description: "LLM-based lead optimization", status: "pending" },
    { id: "boltz", name: "Structure Prediction", description: "Boltz 3D folding for top hits", status: "pending" },
  ]);

  const [candidates, setCandidates] = useState<any[]>([]);

  const startPipeline = async () => {
    if (!protein.trim() || !disease.trim()) return;
    setIsRunning(true);
    setHasRun(false);
    setCandidates([]);
    setRunId("demo_" + Date.now());
    
    // Reset steps
    setSteps(s => s.map(step => ({ ...step, status: "pending" })));

    // Mock progress for demo
    const updateStep = (id: string, status: PipelineStep["status"], details?: string) => {
      setSteps(prev => prev.map(s => s.id === id ? { ...s, status, details } : s));
    };

    try {
      // Step 1: Extraction
      updateStep("extraction", "running");
      await new Promise(r => setTimeout(r, 1500));
      updateStep("extraction", "completed", "Resolved: BCL-2 (P10415)");

      // Step 2: Pooling
      updateStep("pooling", "running");
      await new Promise(r => setTimeout(r, 2000));
      updateStep("pooling", "completed", "Generated 250 unique candidates");

      // Step 3: Prediction
      updateStep("prediction", "running");
      await new Promise(r => setTimeout(r, 2500));
      updateStep("prediction", "completed", "Affinity and toxicity screens passed");
      
      // Load mock candidates
      setCandidates([
        { id: 1, name: "Venetoclax-Analog", smiles: "CC1(C)CCC(CN2CCN(c3ccc(C(=O)NS(=O)(=O)c4ccc(NCC5CCOCC5)c([N+](=O)[O-])c4)c(Oc4cnc5[nH]ccc5c4)c3)CC2)=C(c2ccc(Cl)cc2)C1", pkd: 11.4, qed: 0.25, sa: 3.8, status: "Lead" },
        { id: 2, name: "DXL-102", smiles: "C=C(F)C(=O)N1CCN(c2nc(OC[C@@H]3CCCN3C)nc3c2CCN(c2cccc4cccc(Cl)c24)C3)C[C@@H]1CC#N", pkd: 8.75, qed: 0.82, sa: 2.3, status: "Lead" },
        { id: 3, name: "DXL-103", smiles: "Cc1cccc(C)c1-n1c(=O)nc2c(F)cc(F)cc21", pkd: 7.21, qed: 0.65, sa: 1.8, status: "Candidate" },
      ]);

      // Step 4: Refinement
      updateStep("refinement", "running");
      await new Promise(r => setTimeout(r, 1500));
      updateStep("refinement", "completed", "Optimized 2 lead scaffolds");

      // Step 5: Boltz
      updateStep("boltz", "running");
      await new Promise(r => setTimeout(r, 2000));
      updateStep("boltz", "completed", "3D complexes generated");
      setHasRun(true);

    } catch (err) {
      console.error(err);
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
      {/* Search & Config */}
      <Card className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 backdrop-blur-md shadow-sm dark:shadow-none overflow-hidden">
        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-blue-500 via-cyan-500 to-indigo-500" />
        <CardContent className="p-8">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 items-end">
            <div className="md:col-span-1 space-y-2">
              <label className="text-xs font-semibold text-gray-600 dark:text-gray-500 dark:text-white/40 uppercase tracking-wider">Target Protein</label>
              <Input 
                value={protein} 
                onChange={(e) => setProtein(e.target.value)}
                placeholder="e.g. BCL-2"
                className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 text-gray-900 dark:text-white focus:ring-blue-500/50 h-11"
              />
            </div>
            <div className="md:col-span-2 space-y-2">
              <label className="text-xs font-semibold text-gray-600 dark:text-gray-500 dark:text-white/40 uppercase tracking-wider">Disease Context</label>
              <Input 
                value={disease} 
                onChange={(e) => setDisease(e.target.value)}
                placeholder="e.g. Chronic Lymphocytic Leukemia"
                className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 text-gray-900 dark:text-white focus:ring-blue-500/50 h-11"
              />
            </div>
            <div className="md:col-span-1">
              <Button 
                onClick={startPipeline} 
                disabled={isRunning || !protein.trim() || !disease.trim()}
                className="w-full bg-blue-600 hover:bg-blue-700 text-white h-11 font-bold shadow-lg shadow-blue-600/20 rounded-lg group disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {isRunning ? (
                  <Loader2 className="w-5 h-5 animate-spin mr-2" />
                ) : (
                  <Play className="w-4 h-4 mr-2 group-hover:scale-110 transition-transform" />
                )}
                {isRunning ? "Running Agent..." : "Start Discovery"}
              </Button>
            </div>
          </div>
          
          <div className="mt-8 flex flex-wrap gap-3 items-center">
            <span className="text-[10px] font-bold text-gray-600 dark:text-white/20 uppercase tracking-widest mr-2">Try Examples:</span>
            {[
              { label: "BCL-2 / CLL", protein: "BCL-2", disease: "Chronic Lymphocytic Leukemia" },
              { label: "MCL-1 / DLBCL", protein: "MCL-1", disease: "Diffuse Large B-Cell Lymphoma" },
              { label: "BACE1 / Alzheimer's", protein: "BACE1", disease: "Alzheimer's Disease" },
            ].map((ex) => (
              <button 
                key={ex.label}
                onClick={() => {
                  setProtein(ex.protein);
                  setDisease(ex.disease);
                }}
                className="text-[10px] bg-white dark:bg-white/5 hover:bg-blue-50 dark:bg-blue-500/10 border border-gray-200 dark:border-white/10 hover:border-blue-300 dark:border-blue-500/30 px-3 py-1.5 rounded-full text-gray-600 dark:text-white/60 hover:text-blue-700 dark:text-blue-400 transition-all"
              >
                {ex.label}
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
        {/* Pipeline Stepper */}
        <Card className="xl:col-span-1 bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 backdrop-blur-md shadow-sm dark:shadow-none">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Activity className="w-5 h-5 text-blue-700 dark:text-blue-400" />
              Pipeline Execution
            </CardTitle>
            <CardDescription className="text-gray-600 dark:text-gray-500 dark:text-white/40">Step-by-step progress monitoring</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {steps.map((step, idx) => (
              <div key={step.id} className="flex gap-4 relative">
                {idx < steps.length - 1 && (
                  <div className={cn(
                    "absolute left-3.5 top-8 w-[2px] h-10 transition-colors duration-500",
                    step.status === "completed" ? "bg-blue-500/50" : "bg-white dark:bg-white/5"
                  )} />
                )}
                <div className={cn(
                  "w-7 h-7 rounded-full flex items-center justify-center shrink-0 z-10 transition-all duration-500",
                  step.status === "completed" ? "bg-blue-500 shadow-[0_0_15px_rgba(59,130,246,0.5)]" : 
                  step.status === "running" ? "bg-blue-500/20 border-2 border-blue-500 animate-pulse" : 
                  "bg-white dark:bg-white/5 border border-gray-200 dark:border-white/10"
                )}>
                  {step.status === "completed" ? (
                    <CheckCircle2 className="w-4 h-4 text-gray-900 dark:text-white" />
                  ) : step.status === "running" ? (
                    <Loader2 className="w-3 h-3 text-blue-700 dark:text-blue-400 animate-spin" />
                  ) : (
                    <div className="w-1.5 h-1.5 rounded-full bg-white/20" />
                  )}
                </div>
                <div className="flex-1 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className={cn(
                      "text-sm font-semibold transition-colors",
                      step.status === "pending" ? "text-gray-600 dark:text-gray-500 dark:text-white/40" : "text-gray-900 dark:text-white/90"
                    )}>
                      {step.name}
                    </span>
                    {step.status === "running" && (
                      <span className="text-[10px] text-blue-700 dark:text-blue-400 font-bold animate-pulse uppercase tracking-widest">Active</span>
                    )}
                  </div>
                  <p className="text-xs text-gray-600 dark:text-white/30 leading-relaxed">{step.description}</p>
                  {step.details && (
                    <motion.div 
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      className="mt-2 py-1.5 px-2 bg-white dark:bg-white/5 rounded border border-gray-200 dark:border-white/5 text-[10px] font-mono text-blue-300 flex items-center gap-2"
                    >
                      <div className="w-1 h-1 rounded-full bg-blue-400" />
                      {step.details}
                    </motion.div>
                  )}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Intelligence / Results */}
        <div className="xl:col-span-2 space-y-8">
           {/* Idle placeholder – shown before any run */}
           {!hasRun && !isRunning && (
             <div className="flex flex-col items-center justify-center h-64 rounded-2xl border-2 border-dashed border-gray-200 dark:border-white/10 text-center gap-4 animate-in fade-in duration-500">
               <Beaker className="w-12 h-12 text-gray-300 dark:text-white/10" />
               <div>
                 <p className="text-sm font-semibold text-gray-500 dark:text-white/30">No results yet</p>
                 <p className="text-xs text-gray-400 dark:text-white/20 mt-1">Enter a target protein and disease context above, then click <strong>Start Discovery</strong></p>
               </div>
             </div>
           )}

           {/* Results cards – only shown after a run */}
           {(hasRun || isRunning) && (
           <>{/* Visual Section */}
           <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

              <Card className="bg-gradient-to-br from-blue-600/10 to-indigo-600/5 border-gray-200 dark:border-white/10 relative overflow-hidden group">
                <div className="absolute -right-4 -bottom-4 opacity-10 group-hover:scale-110 transition-transform duration-1000">
                  <Beaker className="w-32 h-32 text-blue-700 dark:text-blue-400" />
                </div>
                <CardHeader>
                  <CardTitle className="text-sm uppercase tracking-widest text-gray-600 dark:text-gray-500 dark:text-white/40">Target Insights</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div className="flex items-end justify-between">
                       <p className="text-4xl font-bold text-gray-900 dark:text-white tracking-tighter">P10415</p>
                       <Badge className="bg-emerald-500/20 text-emerald-700 dark:text-emerald-400 border-emerald-300 dark:border-emerald-500/30">Verified</Badge>
                    </div>
                    <div className="grid grid-cols-2 gap-4 pt-4 border-t border-gray-200 dark:border-white/5">
                       <div>
                         <p className="text-xs text-gray-600 dark:text-gray-500 dark:text-white/40">Druggability</p>
                         <p className="text-xl font-bold text-blue-700 dark:text-blue-400">High (0.84)</p>
                       </div>
                       <div>
                         <p className="text-xs text-gray-600 dark:text-gray-500 dark:text-white/40">PDB Records</p>
                         <p className="text-xl font-bold">142</p>
                       </div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card className="bg-gradient-to-br from-purple-600/10 to-pink-600/5 border-gray-200 dark:border-white/10 relative overflow-hidden group">
                <div className="absolute -right-4 -bottom-4 opacity-10 group-hover:scale-110 transition-transform duration-1000">
                  <Activity className="w-32 h-32 text-purple-700 dark:text-purple-400" />
                </div>
                <CardHeader>
                  <CardTitle className="text-sm uppercase tracking-widest text-gray-600 dark:text-gray-500 dark:text-white/40">Discovery Score</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div className="flex items-end justify-between">
                       <p className="text-4xl font-bold text-gray-900 dark:text-white tracking-tighter">92.4<span className="text-xl text-gray-600 dark:text-gray-500 dark:text-white/40">/100</span></p>
                       <Badge className="bg-purple-500/20 text-purple-700 dark:text-purple-400 border-purple-300 dark:border-purple-500/30">Excellent</Badge>
                    </div>
                    <div className="pt-4 border-t border-gray-200 dark:border-white/5">
                       <div className="flex justify-between text-xs mb-1.5">
                          <span className="text-gray-600 dark:text-gray-500 dark:text-white/40">Confidence Interval</span>
                          <span className="text-gray-900 dark:text-white/90">89.2% - 94.8%</span>
                       </div>
                       <div className="h-1.5 w-full bg-white dark:bg-white/5 rounded-full overflow-hidden">
                          <motion.div 
                            initial={{ width: 0 }}
                            animate={{ width: "92.4%" }}
                            className="h-full bg-gradient-to-r from-purple-500 to-indigo-500" 
                          />
                       </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
           </div>

           {/* Candidates Table */}
           <Card className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 backdrop-blur-md shadow-sm dark:shadow-none">
             <CardHeader className="flex flex-row items-center justify-between border-b border-gray-200 dark:border-white/5 pb-4">
                <div>
                  <CardTitle>Screened Candidates</CardTitle>
                  <CardDescription>Molecules ranked by predicted binding affinity</CardDescription>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" size="icon" className="w-8 h-8 rounded-full border-gray-200 dark:border-white/10">
                    <RotateCcw className="w-3.5 h-3.5" />
                  </Button>
                  <Button variant="outline" size="icon" className="w-8 h-8 rounded-full border-gray-200 dark:border-white/10">
                    <Download className="w-3.5 h-3.5" />
                  </Button>
                </div>
             </CardHeader>
             <CardContent className="p-0">
               <ScrollArea className="h-[400px]">
                 {candidates.length === 0 ? (
                   <div className="flex flex-col items-center justify-center h-[300px] text-gray-600 dark:text-white/20">
                      <Beaker className="w-12 h-12 mb-4 opacity-5" />
                      <p className="text-sm font-medium">Start discovery to generate candidates</p>
                   </div>
                 ) : (
                   <table className="w-full text-left border-collapse">
                     <thead>
                       <tr className="text-[10px] uppercase tracking-widest text-gray-600 dark:text-gray-500 dark:text-white/40 border-b border-gray-200 dark:border-white/5">
                         <th className="py-4 px-6 font-semibold">Candidate</th>
                         <th className="py-4 px-6 font-semibold text-center">pKd</th>
                         <th className="py-4 px-6 font-semibold text-center">QED</th>
                         <th className="py-4 px-6 font-semibold text-center">SA Score</th>
                         <th className="py-4 px-6 font-semibold text-right">Status</th>
                       </tr>
                     </thead>
                     <tbody className="divide-y divide-white/5">
                       {candidates.map((mol) => (
                         <tr key={mol.id} className="group hover:bg-white dark:bg-white/5 transition-all duration-300 cursor-pointer">
                           <td className="py-5 px-6">
                             <div className="flex items-center gap-3">
                               <div className="w-10 h-10 rounded-lg bg-white dark:bg-white/5 border border-gray-200 dark:border-white/10 flex items-center justify-center group-hover:border-blue-500/50 group-hover:bg-blue-500/5 transition-all">
                                 <FlaskConical className="w-5 h-5 text-blue-700 dark:text-blue-400/60" />
                               </div>
                               <div>
                                 <p className="text-sm font-bold text-gray-900 dark:text-white/90">{mol.name}</p>
                                 <p className="text-[10px] text-gray-600 dark:text-white/30 font-mono mt-0.5 truncate max-w-[140px]">{mol.smiles}</p>
                               </div>
                             </div>
                           </td>
                           <td className="py-5 px-6 text-center">
                             <span className="text-base font-bold text-blue-700 dark:text-blue-400">{mol.pkd}</span>
                           </td>
                           <td className="py-5 px-6 text-center">
                             <span className="text-sm font-medium text-white/70">{mol.qed}</span>
                           </td>
                           <td className="py-5 px-6 text-center">
                             <span className="text-sm font-medium text-white/70">{mol.sa}</span>
                           </td>
                           <td className="py-5 px-6 text-right">
                              <Badge className={cn(
                                "rounded-full px-2 py-0.5 text-[10px]",
                                mol.status === "Lead" ? "bg-emerald-500/20 text-emerald-700 dark:text-emerald-400 border-emerald-300 dark:border-emerald-500/30" : "bg-blue-500/20 text-blue-700 dark:text-blue-400 border-blue-300 dark:border-blue-500/30"
                              )}>
                                {mol.status}
                              </Badge>
                           </td>
                         </tr>
                       ))}
                     </tbody>
                   </table>
                 )}
               </ScrollArea>
             </CardContent>
           </Card>
        </div>
      </div>
    </div>
  );
}
