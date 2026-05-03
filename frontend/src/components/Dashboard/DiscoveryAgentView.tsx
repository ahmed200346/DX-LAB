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
import Script from "next/script";
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

// Sub-component for 3D Viewer to handle its own lifecycle
const Molecule3DViewer = ({ smiles, viewerId }: { smiles: string, viewerId: string }) => {
  useEffect(() => {
    let viewer: any = null;
    const initViewer = async () => {
      try {
        const w = window as any;
        if (!w.$3Dmol) return;

        const el = document.getElementById(viewerId);
        if (!el) return;
        
        // Clear previous content
        el.innerHTML = '';

        const url = `https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/${encodeURIComponent(smiles)}/SDF`;
        const res = await fetch(url);
        if (!res.ok) throw new Error("Fetch failed");
        const sdfData = await res.text();

        viewer = w.$3Dmol.createViewer(el, { backgroundColor: '#020617' }); // Slate-950
        viewer.addModel(sdfData, "sdf");
        viewer.setStyle({}, { stick: { radius: 0.15, colorscheme: "Jmol" } });
        viewer.zoomTo();
        viewer.render();
        viewer.spin(true);
      } catch (err) {
        console.error("3Dmol initialization error:", err);
      }
    };

    // Initial attempt
    initViewer();

    // Secondary attempt to handle library load delay
    const timer = setTimeout(initViewer, 500);

    return () => {
      clearTimeout(timer);
      if (viewer) {
        viewer.clear();
      }
    };
  }, [smiles, viewerId]);

  return <div id={viewerId} className="w-full h-full cursor-crosshair relative" />;
};

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
      // Step 1: Extraction (Fast)
      updateStep("extraction", "running");
      await new Promise(r => setTimeout(r, 800 + Math.random() * 500));
      updateStep("extraction", "completed", "Resolved: BCL-2 (P10415)");

      // Step 2: Pooling (Slower - Generative Models)
      updateStep("pooling", "running");
      await new Promise(r => setTimeout(r, 3500 + Math.random() * 1500));
      updateStep("pooling", "completed", "Generated 250 unique candidates");

      // Step 3: Prediction (Medium)
      updateStep("prediction", "running");
      await new Promise(r => setTimeout(r, 2200 + Math.random() * 1000));
      updateStep("prediction", "completed", "Affinity and toxicity screens passed");
      
      // Load mock candidates
      setCandidates([
        { id: 1, name: "Venetoclax-Analog", smiles: "CC1(C)CCC(CN2CCN(c3ccc(C(=O)NS(=O)(=O)c4ccc(NCC5CCOCC5)c([N+](=O)[O-])c4)c(Oc4cnc5[nH]ccc5c4)c3)CC2)=C(c2ccc(Cl)cc2)C1", pkd: 11.4, qed: 0.25, sa: 3.8, status: "Lead" },
        { id: 2, name: "DXL-102", smiles: "C=C(F)C(=O)N1CCN(c2nc(OC[C@@H]3CCCN3C)nc3c2CCN(c2cccc4cccc(Cl)c24)C3)C[C@@H]1CC#N", pkd: 8.75, qed: 0.82, sa: 2.3, status: "Lead" },
        { id: 3, name: "DXL-103", smiles: "Cc1cccc(C)c1-n1c(=O)nc2c(F)cc(F)cc21", pkd: 7.21, qed: 0.65, sa: 1.8, status: "Candidate" },
      ]);

      // Step 4: Refinement (Slower - LLM Optimization)
      updateStep("refinement", "running");
      await new Promise(r => setTimeout(r, 4000 + Math.random() * 1000));
      updateStep("refinement", "completed", "Optimized 2 lead scaffolds");

      // Step 5: Boltz (Very Slow - 3D Folding)
      updateStep("boltz", "running");
      await new Promise(r => setTimeout(r, 5500 + Math.random() * 2000));
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
      <Script 
        src="https://3Dmol.csb.pitt.edu/build/3Dmol-min.js" 
        strategy="afterInteractive"
      />
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
                placeholder="Enter target protein name..."
                className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 text-gray-900 dark:text-white focus:ring-blue-500/50 h-11"
              />
            </div>
            <div className="md:col-span-2 space-y-2">
              <label className="text-xs font-semibold text-gray-600 dark:text-gray-500 dark:text-white/40 uppercase tracking-wider">Disease Context</label>
              <Input 
                value={disease} 
                onChange={(e) => setDisease(e.target.value)}
                placeholder="Enter disease context or therapeutic area..."
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
           <>
             {/* Visual Section */}
             <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {steps[0].status === "completed" && (
                  <Card className="bg-gradient-to-br from-blue-600/10 to-indigo-600/5 border-gray-200 dark:border-white/10 relative overflow-hidden group animate-in zoom-in-95 duration-500">
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
                )}

                {steps[2].status === "completed" && (
                  <Card className="bg-gradient-to-br from-purple-600/10 to-pink-600/5 border-gray-200 dark:border-white/10 relative overflow-hidden group animate-in zoom-in-95 duration-500">
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
                )}
             </div>

             {/* Candidates Details */}
             {candidates.length > 0 && (
               <div className="space-y-6 animate-in fade-in duration-700">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="text-lg font-bold text-gray-900 dark:text-white">Generated Candidates</h4>
                      <p className="text-sm text-gray-600 dark:text-gray-500 dark:text-white/40">Molecular structures and predicted metrics</p>
                    </div>
                    <div className="flex gap-2">
                      <Button variant="outline" size="sm" className="border-gray-200 dark:border-white/10" disabled={steps[4].status !== "completed"}>
                        <Download className="w-4 h-4 mr-2" /> Export SDF
                      </Button>
                    </div>
                  </div>

                  <div className="space-y-6">
                    {/* Inject 3Dmol script dynamically if needed */}
                    {steps[4].status === "completed" && (
                      <script src="https://3Dmol.csb.pitt.edu/build/3Dmol-min.js" defer></script>
                    )}
                    
                    {candidates.map((mol, idx) => {
                      const viewerId = `viewer-${idx}`;
                      
                      // Render 3D model when script is loaded and step 5 is done
                      if (typeof window !== 'undefined' && steps[4].status === "completed") {
                        setTimeout(async () => {
                          try {
                            const w = window as any;
                            if (w.$3Dmol) {
                              const el = document.getElementById(viewerId);
                              if (el && !el.hasChildNodes()) {
                                const url = `https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/${encodeURIComponent(mol.smiles)}/SDF`;
                                const res = await fetch(url);
                                if (!res.ok) throw new Error("Fetch failed");
                                const sdfData = await res.text();
                                
                                const viewer = w.$3Dmol.createViewer(el, { backgroundColor: '#0a0a0f' });
                                viewer.addModel(sdfData, "sdf");
                                viewer.setStyle({}, { stick: { colorscheme: "Jmol" } });
                                viewer.zoomTo();
                                viewer.spin(true);
                                viewer.render();
                              }
                            }
                          } catch (err) {
                            console.error("Failed to load 3D viewer:", err);
                          }
                        }, 500); // short delay to ensure DOM and script
                      }

                      return (
                        <Card key={mol.id} className="relative overflow-hidden bg-white dark:bg-[#0a0a0f] border-gray-200 dark:border-white/10 shadow-sm dark:shadow-none">
                          <div className={cn(
                            "absolute top-0 left-0 w-1 h-full",
                            mol.status === "Lead" ? "bg-emerald-500" : "bg-blue-500"
                          )} />
                          
                          <CardHeader className="pb-4 border-b border-gray-200 dark:border-white/5">
                            <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
                              <div className="flex-1 space-y-3 max-w-3xl">
                                <div className="flex items-center gap-3">
                                  <CardTitle className="text-xl flex items-center gap-2">
                                    <FlaskConical className={cn(
                                      "w-5 h-5",
                                      mol.status === "Lead" ? "text-emerald-600 dark:text-emerald-400" : "text-blue-600 dark:text-blue-400"
                                    )} />
                                    {mol.name}
                                  </CardTitle>
                                  <Badge className={cn(
                                    "rounded-full px-3 py-0.5 text-xs",
                                    mol.status === "Lead" ? "bg-emerald-500/20 text-emerald-700 dark:text-emerald-400 border-none" : "bg-blue-500/20 text-blue-700 dark:text-blue-400 border-none"
                                  )}>
                                    {mol.status}
                                  </Badge>
                                </div>
                                <div className="bg-gray-50 dark:bg-white/5 p-3 rounded-lg border border-gray-200 dark:border-white/5">
                                  <p className="font-mono text-xs text-gray-700 dark:text-gray-300 break-all leading-relaxed select-all">
                                    {mol.smiles}
                                  </p>
                                </div>
                              </div>
                              
                              <div className="flex gap-6 shrink-0 pt-2">
                                <div className="text-center">
                                  <p className="text-[10px] text-gray-500 uppercase tracking-widest font-bold mb-1">pKd</p>
                                  <p className="text-2xl font-black text-gray-900 dark:text-white">{mol.pkd}</p>
                                </div>
                                <div className="text-center">
                                  <p className="text-[10px] text-gray-500 uppercase tracking-widest font-bold mb-1">QED</p>
                                  <p className="text-2xl font-black text-gray-900 dark:text-white">{mol.qed}</p>
                                </div>
                                <div className="text-center">
                                  <p className="text-[10px] text-gray-500 uppercase tracking-widest font-bold mb-1">SA Score</p>
                                  <p className="text-2xl font-black text-gray-900 dark:text-white">{mol.sa}</p>
                                </div>
                              </div>
                            </div>
                          </CardHeader>
                          
                          <CardContent className="p-6">
                            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 h-64">
                              {/* 2D Structure Rendering via PubChem */}
                              <div className="rounded-xl border border-gray-200 dark:border-white/10 bg-white flex flex-col overflow-hidden h-full">
                                <div className="bg-gray-50 border-b border-gray-200 px-4 py-2 text-[10px] font-bold text-gray-500 uppercase tracking-widest flex justify-between items-center">
                                    <span>2D Structure (PubChem API)</span>
                                    <Database className="w-3 h-3" />
                                </div>
                                <div className="flex-1 flex items-center justify-center p-4">
                                    <img 
                                        src={`https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/${encodeURIComponent(mol.smiles)}/PNG?record_type=2d&image_size=400x400`} 
                                        alt={`2D structure of ${mol.name}`}
                                        className="h-full w-full object-contain mix-blend-multiply"
                                        onError={(e) => {
                                            (e.target as HTMLImageElement).src = "https://placehold.co/400x400/f8fafc/94a3b8?text=Render+Failed";
                                        }}
                                    />
                                </div>
                              </div>

                              {/* 3D Structure via 3Dmol.js */}
                              <div className="rounded-xl border border-gray-200 dark:border-white/10 bg-[#0a0a0f] flex flex-col overflow-hidden h-full relative">
                                <div className="bg-black/60 border-b border-white/5 px-4 py-2 text-[10px] font-bold text-gray-400 uppercase tracking-widest flex justify-between items-center z-10 absolute top-0 w-full backdrop-blur-sm">
                                    <span className="flex items-center gap-2">
                                      {steps[4].status !== "completed" && <Loader2 className="w-3 h-3 animate-spin text-blue-500" />} 
                                      3D Structure (Boltz-1)
                                    </span>
                                    {steps[4].status === "completed" && <Badge variant="outline" className="text-[9px] h-4 border-blue-500/30 text-blue-400">Interactive</Badge>}
                                </div>
                                
                                {steps[4].status === "completed" ? (
                                  <>
                                    <Molecule3DViewer smiles={mol.smiles} viewerId={viewerId} />
                                    <div className="absolute bottom-2 right-2 text-[9px] text-white/30 font-mono pointer-events-none">
                                      Powered by 3Dmol.js
                                    </div>
                                  </>
                                ) : (
                                  <div className="w-full h-full flex flex-col items-center justify-center relative overflow-hidden">
                                    <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-blue-900/10 via-gray-950 to-gray-950"></div>
                                    <Loader2 className="w-10 h-10 animate-spin text-blue-500/50 mb-4 relative z-10" />
                                    <p className="text-sm font-mono text-blue-400/70 relative z-10">Awaiting Boltz-1 Prediction...</p>
                                    <p className="text-[10px] font-mono text-gray-500 mt-2 relative z-10">Folding protein-ligand complex</p>
                                  </div>
                                )}
                              </div>
                            </div>
                          </CardContent>
                        </Card>
                      );
                    })}
                  </div>
               </div>
             )}
           </>
           )}
        </div>
      </div>
    </div>
  );
}
