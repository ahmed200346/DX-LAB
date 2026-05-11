"use client";

import { useEffect } from "react";
import { cn } from "@/lib/utils";
import { motion, AnimatePresence } from "framer-motion";
import { Cuboid, Play, Download, Settings2, Box, RotateCcw, Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import Script from "next/script";
import { usePrinter } from "@/hooks/usePrinter";

const Molecule3DViewer = ({ chemicalName, viewerId, structure }: { chemicalName: string, viewerId: string, structure?: string }) => {
  useEffect(() => {
    let viewer: any = null;
    const initViewer = async () => {
      try {
        const w = window as any;
        if (!w.$3Dmol) return;

        const el = document.getElementById(viewerId);
        if (!el) return;

        el.innerHTML = '';

        let modelData: string;
        let format: string;

        if (structure) {
          modelData = structure;
          format = structure.startsWith("ATOM") || structure.startsWith("HETATM") ? "pdb" : "sdf";
        } else {
          const url = `https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/${encodeURIComponent(chemicalName)}/SDF`;
          const res = await fetch(url);
          if (!res.ok) throw new Error("Fetch failed");
          modelData = await res.text();
          format = "sdf";
        }

        viewer = w.$3Dmol.createViewer(el, { backgroundColor: '#0f172a' });
        viewer.addModel(modelData, format);
        viewer.setStyle({}, { stick: { radius: 0.15, colorscheme: "Jmol" } });
        viewer.zoomTo();
        viewer.render();
        viewer.spin(true);
      } catch (err) {
        console.error("3Dmol initialization error:", err);
      }
    };

    initViewer();
    const timer = setTimeout(initViewer, 500);

    return () => {
      clearTimeout(timer);
      if (viewer) viewer.clear();
    };
  }, [chemicalName, viewerId, structure]);

  return <div id={viewerId} className="w-full h-full cursor-crosshair relative" />;
};

export default function PrinterAgentView() {
  const {
    moleculeName, setMoleculeName,
    isRunning, hasRun,
    result, error,
    submitMolecule, reset,
  } = usePrinter();

  const handlePrint = async () => {
    if (!moleculeName.trim()) return;
    await submitMolecule(moleculeName.trim());
  };

  const structure = result?.printer?.structure;
  const smiles = result?.ranker?.validation?.smiles;

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <Script src="https://3Dmol.csb.pitt.edu/build/3Dmol-min.js" strategy="lazyOnload" />
      
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-2xl font-bold flex items-center gap-2">
            <Cuboid className="w-6 h-6 text-indigo-500" />
            3D Molecular Printer
          </h3>
          <p className="text-gray-600 dark:text-gray-500 dark:text-white/40 text-sm mt-1">
            Instantly render and interact with 3D structural conformations of target compounds.
          </p>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-400 text-sm">{error}</div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
        <Card className="lg:col-span-1 bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 backdrop-blur-md shadow-sm h-fit">
          <CardHeader>
            <CardTitle className="text-sm uppercase tracking-widest text-gray-600 dark:text-gray-500 dark:text-white/40">Printer Configuration</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-2">
              <label className="text-xs font-medium text-gray-700 dark:text-white/60">Chemical Name</label>
              <Input 
                value={moleculeName}
                onChange={e => setMoleculeName(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && !isRunning) handlePrint(); }}
                className="bg-gray-50 dark:bg-white/5 border-gray-200 dark:border-white/10 h-10 text-sm" 
                placeholder="e.g., Venetoclax, Aspirin..." 
              />
            </div>

            <div className="space-y-2 pt-2">
              <Button 
                onClick={handlePrint}
                disabled={isRunning || !moleculeName.trim()}
                className="w-full bg-indigo-600 hover:bg-indigo-700 shadow-lg shadow-indigo-600/20 text-white h-11"
              >
                {isRunning ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Play className="w-4 h-4 mr-2" />}
                {isRunning ? "Initializing Printer..." : "Render 3D Structure"}
              </Button>
            </div>

            {hasRun && result && (
              <>
                <Separator className="bg-white dark:bg-white/5" />
                <div className="space-y-3">
                  <label className="text-xs font-medium text-gray-700 dark:text-white/60">Analysis</label>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-gray-600 dark:text-gray-400">Case Type</span>
                      <Badge variant="outline" className="text-[10px]">Case {result.ranker.case}</Badge>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-gray-600 dark:text-gray-400">Confidence</span>
                      <span className="text-[10px] text-gray-500">{(result.ranker.confidence * 100).toFixed(0)}%</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-gray-600 dark:text-gray-400">Pipeline Score</span>
                      <span className="text-[10px] text-gray-500">{(result.metrics.pipeline.global * 100).toFixed(0)}%</span>
                    </div>
                    {smiles && (
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-gray-600 dark:text-gray-400">SMILES</span>
                        <span className="text-[8px] text-gray-500 max-w-[120px] truncate">{smiles}</span>
                      </div>
                    )}
                  </div>
                </div>
              </>
            )}

            <Separator className="bg-white dark:bg-white/5" />
            
            <div className="space-y-4">
              <label className="text-xs font-medium text-gray-700 dark:text-white/60">Printer Status</label>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-600 dark:text-gray-400">Connection</span>
                  <Badge variant="outline" className="text-[10px] text-emerald-500 border-emerald-500/30">Online</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-600 dark:text-gray-400">Source</span>
                  <span className="text-[10px] text-gray-500">{structure ? "Backend" : "PubChem"}</span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="lg:col-span-3">
          <Card className="bg-slate-900 border-slate-800 shadow-2xl overflow-hidden h-[600px] flex flex-col relative group">
            <CardHeader className="bg-slate-900/80 backdrop-blur-sm border-b border-white/5 absolute top-0 w-full z-10 p-4 flex flex-row items-center justify-between">
              <div className="flex items-center gap-3">
                <Box className="w-5 h-5 text-indigo-400" />
                <CardTitle className="text-base text-white tracking-wide">
                  {hasRun ? moleculeName : "Waiting for input..."}
                </CardTitle>
              </div>
              {hasRun && (
                <div className="flex gap-2">
                  <Button variant="ghost" size="icon" className="text-slate-400 hover:text-white h-8 w-8 rounded-full bg-white/5 hover:bg-white/10">
                    <RotateCcw className="w-4 h-4" />
                  </Button>
                  <Button variant="ghost" size="icon" className="text-slate-400 hover:text-white h-8 w-8 rounded-full bg-white/5 hover:bg-white/10">
                    <Settings2 className="w-4 h-4" />
                  </Button>
                </div>
              )}
            </CardHeader>
            
            <CardContent className="flex-1 p-0 relative">
              {!hasRun && !isRunning ? (
                <div className="absolute inset-0 flex flex-col items-center justify-center text-center gap-4">
                  <div className="w-20 h-20 rounded-full bg-slate-800 flex items-center justify-center border border-slate-700 shadow-inner">
                    <Cuboid className="w-10 h-10 text-slate-600" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-slate-400">No Molecule Loaded</p>
                    <p className="text-xs text-slate-500 mt-1 max-w-[200px] mx-auto">Enter a chemical name on the left to begin 3D rendering.</p>
                  </div>
                </div>
              ) : isRunning ? (
                <div className="absolute inset-0 flex flex-col items-center justify-center text-center gap-4">
                  <Loader2 className="w-12 h-12 text-indigo-500 animate-spin" />
                  <p className="text-sm text-indigo-400 animate-pulse">Computing 3D Conformation...</p>
                </div>
              ) : (
                <div className="w-full h-full relative" style={{ minHeight: '600px' }}>
                  <Molecule3DViewer chemicalName={moleculeName} viewerId="dedicated-3d-printer" structure={structure} />
                  <div className="absolute bottom-4 right-4 flex gap-2">
                    <Badge variant="outline" className="bg-slate-900/80 backdrop-blur-sm border-slate-700 text-slate-300 pointer-events-none">Interactive Mode</Badge>
                    <Badge variant="outline" className="bg-slate-900/80 backdrop-blur-sm border-slate-700 text-indigo-400 pointer-events-none">Jmol Colors</Badge>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
