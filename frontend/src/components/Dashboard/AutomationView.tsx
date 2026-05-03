"use client";

import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { motion, AnimatePresence } from "framer-motion";
import { Cpu, Printer, Play, Square, Settings, Activity, Gauge, Terminal, AlertCircle, Loader2 } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";

export default function AutomationView() {
  const [isRunning, setIsRunning] = useState(false);
  const [printProgress, setPrintProgress] = useState(68);
  const [logs, setLogs] = useState([
    { time: "22:15:18", msg: "pipette.transfer(10, reagent_plate['A1'], assay_plate['H12']) ; CellTiter-Glo" },
    { time: "22:15:16", msg: "robot.move_to(deck_slot=3, well='G11') ; Venetoclax-Analog 100nM" },
    { time: "22:15:14", msg: "pipette.mix(3, 50, assay_plate['H12']) ; Homogenize" },
  ]);

  useEffect(() => {
    if (!isRunning) return;
    const interval = setInterval(() => {
      setPrintProgress(prev => (prev < 100 ? prev + 1 : 100));
      const time = new Date().toLocaleTimeString([], { hour12: false });
      const cmds = [
        `pipette.aspirate(${(Math.random()*10+5).toFixed(1)}, reagent_plate['${String.fromCharCode(65+Math.floor(Math.random()*8))}${Math.floor(Math.random()*12+1)}'])`,
        `pipette.dispense(${(Math.random()*10+5).toFixed(1)}, assay_plate['${String.fromCharCode(65+Math.floor(Math.random()*8))}${Math.floor(Math.random()*12+1)}']) ; Venetoclax-Analog`,
        `robot.delay(seconds=300) ; Incubation step`,
        `luminometer.read_plate(assay_plate) ; CellTiter-Glo readout`,
      ];
      const msg = cmds[Math.floor(Math.random() * cmds.length)];
      setLogs(prev => [{ time, msg }, ...prev.slice(0, 10)]);
    }, 1000);
    return () => clearInterval(interval);
  }, [isRunning]);

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-2xl font-bold">Lab Automation</h3>
          <p className="text-gray-600 dark:text-gray-500 dark:text-white/40 text-sm">Orchestration and monitoring of 3D bioprinting and fluidics</p>
        </div>
        <div className="flex gap-3">
           <Button variant="outline" className="border-gray-200 dark:border-white/10 hover:bg-white dark:bg-white/5">Calibration</Button>
           <Button 
             onClick={() => setIsRunning(!isRunning)}
             className={cn(
               "shadow-lg transition-all min-w-[140px]",
               isRunning ? "bg-red-600 hover:bg-red-700 shadow-red-600/20" : "bg-emerald-600 hover:bg-emerald-700 shadow-emerald-600/20"
             )}
           >
              {isRunning ? <Square className="w-4 h-4 mr-2" /> : <Play className="w-4 h-4 mr-2" />}
              {isRunning ? "Stop Queue" : "Start Queue"}
           </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 space-y-6">
           <Card className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 backdrop-blur-md shadow-sm dark:shadow-none overflow-hidden group relative">
              <AnimatePresence>
                {isRunning && (
                  <motion.div 
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="absolute top-4 right-4 z-10 flex items-center gap-2 bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/20 px-3 py-1 rounded-full"
                  >
                     <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.8)]" />
                     <span className="text-[10px] font-bold text-emerald-700 dark:text-emerald-400 uppercase tracking-widest">Live Printing</span>
                  </motion.div>
                )}
              </AnimatePresence>
              <CardHeader>
                 <div className="flex justify-between items-start">
                    <div className="flex items-center gap-3">
                       <div className={cn(
                         "w-12 h-12 rounded-xl border flex items-center justify-center transition-all duration-1000",
                         isRunning ? "bg-emerald-500/20 border-emerald-500/40 rotate-12" : "bg-white dark:bg-white/5 border-gray-200 dark:border-white/10"
                       )}>
                          <Printer className={cn("w-6 h-6", isRunning ? "text-emerald-700 dark:text-emerald-400" : "text-gray-600 dark:text-white/20")} />
                       </div>
                       <div>
                          <CardTitle className="text-gray-900 dark:text-white/90 font-bold">Opentrons OT-2</CardTitle>
                          <CardDescription className="text-gray-600 dark:text-gray-500 dark:text-white/40">{isRunning ? "Running CellTiter-Glo Apoptosis Assay" : "Ready — Protocol loaded: Venetoclax-Analog_v3.py"}</CardDescription>
                       </div>
                    </div>
                    <Button variant="ghost" size="icon" className="text-gray-600 dark:text-white/20 hover:text-gray-900 dark:text-white">
                       <Settings className="w-4 h-4" />
                    </Button>
                 </div>
              </CardHeader>
              <CardContent className="space-y-6">
                 <div className="space-y-2">
                    <div className="flex justify-between text-xs">
                       <span className="text-gray-600 dark:text-gray-500 dark:text-white/40 font-bold uppercase tracking-widest">Progress</span>
                       <span className="text-emerald-700 dark:text-emerald-400 font-bold">{printProgress}%</span>
                    </div>
                    <div className="h-2 w-full bg-white dark:bg-white/5 rounded-full overflow-hidden">
                       <motion.div 
                         animate={{ width: `${printProgress}%` }}
                         transition={{ duration: 1 }}
                         className="h-full bg-emerald-500 shadow-[0_0_15px_rgba(16,185,129,0.3)]"
                       />
                    </div>
                 </div>
                 <div className="grid grid-cols-2 gap-4">
                    <div className="bg-white dark:bg-white/5 rounded-xl p-4 border border-gray-200 dark:border-white/5 group-hover:border-emerald-200 dark:border-emerald-500/20 transition-colors">
                       <div className="flex items-center gap-2 mb-2 text-gray-600 dark:text-gray-500 dark:text-white/40">
                          <Gauge className="w-3.5 h-3.5" />
                          <span className="text-[10px] uppercase font-bold tracking-wider">Nozzle Temp</span>
                       </div>
                       <p className="text-2xl font-bold text-gray-900 dark:text-white/90">{isRunning ? "37.0°C" : "25.0°C"}</p>
                    </div>
                    <div className="bg-white dark:bg-white/5 rounded-xl p-4 border border-gray-200 dark:border-white/5 group-hover:border-emerald-200 dark:border-emerald-500/20 transition-colors">
                       <div className="flex items-center gap-2 mb-2 text-gray-600 dark:text-gray-500 dark:text-white/40">
                          <Activity className="w-3.5 h-3.5" />
                          <span className="text-[10px] uppercase font-bold tracking-wider">Aspiration Volume</span>
                       </div>
                       <p className="text-2xl font-bold text-gray-900 dark:text-white/90">{isRunning ? "10.0 μL" : "0.0 μL"}</p>
                    </div>
                 </div>
              </CardContent>
           </Card>

           <Card className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 backdrop-blur-md shadow-sm dark:shadow-none">
              <CardHeader>
                 <CardTitle className="text-lg flex items-center gap-2">
                    <Terminal className="w-5 h-5 text-emerald-700 dark:text-emerald-400" />
                    Opentrons Protocol Live Stream
                 </CardTitle>
              </CardHeader>
              <CardContent>
                 <div className="h-[250px] w-full rounded-xl bg-gray-900 dark:bg-black/60 border border-gray-200 dark:border-white/5 p-6 font-mono text-[10px] overflow-hidden group">
                    <ScrollArea className="h-full pr-4">
                       <AnimatePresence initial={false}>
                        {logs.map((line, i) => (
                          <motion.div 
                            key={line.time + line.msg} 
                            initial={{ opacity: 0, x: -5 }}
                            animate={{ opacity: 1, x: 0 }}
                            className="flex gap-4 mb-1.5"
                          >
                             <span className="text-emerald-500/40 select-none">[{line.time}]</span>
                             <span className="text-white/60">{line.msg}</span>
                          </motion.div>
                        ))}
                       </AnimatePresence>
                       <div className="flex gap-4">
                          <span className="text-emerald-500 animate-pulse">_</span>
                       </div>
                    </ScrollArea>
                 </div>
              </CardContent>
           </Card>
        </div>

        <div className="space-y-6">
           <Card className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 backdrop-blur-md shadow-sm dark:shadow-none">
             <CardHeader>
                <CardTitle className="text-sm">Maintenance Alerts</CardTitle>
             </CardHeader>
             <CardContent className="space-y-4">
                <div className="p-3 bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 rounded-lg flex gap-3">
                   <AlertCircle className="w-4 h-4 text-red-500 shrink-0" />
                   <p className="text-[10px] text-red-700 dark:text-red-200 leading-tight">Tip rack on Deck Slot 1 low (4 tips remaining). Replace before next protocol run.</p>
                </div>
                <div className="p-3 bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/20 rounded-lg flex gap-3">
                   <Activity className="w-4 h-4 text-blue-500 shrink-0" />
                   <p className="text-[10px] text-blue-700 dark:text-blue-200 leading-tight">OT-2 P20 Single-Channel calibration verified. Volume accuracy ±0.1μL confirmed.</p>
                </div>
             </CardContent>
           </Card>

           <Card className="bg-gradient-to-br from-emerald-600/20 to-transparent border-gray-200 dark:border-white/10 p-6">
              <div className="space-y-4">
                 <h4 className="text-xs font-bold uppercase tracking-widest text-gray-600 dark:text-gray-500 dark:text-white/40">Resource Monitoring</h4>
                 <div className="space-y-4">
                    <div>
                       <div className="flex justify-between text-[10px] mb-1.5">
                          <span className="text-gray-600 dark:text-gray-500 dark:text-white/40 uppercase">CellTiter-Glo Reagent</span>
                          <span className="text-gray-900 dark:text-white/90">42%</span>
                       </div>
                       <div className="h-1 w-full bg-white dark:bg-white/5 rounded-full overflow-hidden">
                          <motion.div 
                            animate={{ width: "42%" }}
                            className="h-full bg-emerald-500" 
                          />
                       </div>
                    </div>
                    <div>
                       <div className="flex justify-between text-[10px] mb-1.5">
                          <span className="text-gray-600 dark:text-gray-500 dark:text-white/40 uppercase">Venetoclax-Analog Stock</span>
                          <span className="text-gray-900 dark:text-white/90">88%</span>
                       </div>
                       <div className="h-1 w-full bg-white dark:bg-white/5 rounded-full overflow-hidden">
                          <motion.div 
                            animate={{ width: "88%" }}
                            className="h-full bg-blue-500" 
                          />
                       </div>
                    </div>
                 </div>
              </div>
           </Card>
        </div>
      </div>
    </div>
  );
}
