"use client";

import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Binary, 
  ListTodo, 
  Activity, 
  Terminal, 
  Play, 
  Pause, 
  Square, 
  Zap, 
  Layers, 
  ChevronRight,
  Loader2,
  CheckCircle2,
  AlertCircle
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Progress } from "@/components/ui/progress";

interface LogEntry {
  time: string;
  msg: string;
  type: "info" | "success" | "warning" | "error";
  agent: string;
}

export default function OrchestratorView() {
  const [isRunning, setIsRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [logs, setLogs] = useState<LogEntry[]>([
    { time: "22:30:01", msg: "System standby. Waiting for intent...", type: "info", agent: "Core" },
  ]);
  const [plan, setPlan] = useState([
    { id: 1, task: "Analyze Target Context", agent: "Planner", status: "pending" },
    { id: 2, task: "Extract Protein Structure", agent: "Discovery", status: "pending" },
    { id: 3, task: "Sample Molecule Space", agent: "Discovery", status: "pending" },
    { id: 4, task: "Safety Screening", agent: "Safety", status: "pending" },
    { id: 5, task: "Synthesis Feasibility", agent: "Executor", status: "pending" },
  ]);

  const addLog = (msg: string, agent: string, type: LogEntry["type"] = "info") => {
    const time = new Date().toLocaleTimeString([], { hour12: false });
    setLogs(prev => [...prev, { time, msg, agent, type }]);
  };

  const runSimulation = async () => {
    if (isRunning) return;
    setIsRunning(true);
    setProgress(0);
    setLogs([]);
    
    // Reset plan
    setPlan(p => p.map(s => ({ ...s, status: "pending" })));

    const steps = [
      { id: 1, msg: "Analyzing user intent: 'Find BCL-2 inhibitors'", agent: "Planner" },
      { id: 1, msg: "Plan #005 generated: 5 critical milestones identified", agent: "Planner", status: "completed" },
      { id: 2, msg: "Requesting protein structure for P10415 (BCL-2)...", agent: "Executor" },
      { id: 2, msg: "Structure extracted from AlphaFold Database", agent: "Discovery", status: "completed" },
      { id: 3, msg: "Initiating REINVENT pooling (Iteration 1/2)", agent: "Discovery" },
      { id: 3, msg: "250 candidates generated. Ranking top 10...", agent: "Discovery", status: "completed" },
      { id: 4, msg: "Safety screen started: ADMET filtering active", agent: "Safety" },
      { id: 4, msg: "No high-risk liabilities found in top hits", agent: "Safety", status: "completed" },
      { id: 5, msg: "Checking lab inventory for precursor availability", agent: "Executor" },
      { id: 5, msg: "Synthesis plan validated for Bioprinter Alpha", agent: "Executor", status: "completed" },
    ];

    for (const step of steps) {
      addLog(step.msg, step.agent, step.status === "completed" ? "success" : "info");
      if (step.status) {
        setPlan(prev => prev.map(s => s.id === step.id ? { ...s, status: step.status as any } : s));
      } else {
        setPlan(prev => prev.map(s => s.id === step.id ? { ...s, status: "running" } : s));
      }
      setProgress(prev => Math.min(prev + 10, 100));
      await new Promise(r => setTimeout(r, 1200 + Math.random() * 800));
    }

    setProgress(100);
    addLog("Orchestration complete. Handoff to Reporter Agent.", "Core", "success");
    setIsRunning(false);
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-2xl font-bold">Lab Orchestrator</h3>
          <p className="text-gray-600 dark:text-gray-500 dark:text-white/40 text-sm">Combined Planner & Executor layer managing multi-agent workflows</p>
        </div>
        <div className="flex gap-3">
           <Button variant="outline" className="border-gray-200 dark:border-white/10 hover:bg-white dark:bg-white/5">
              <Layers className="w-4 h-4 mr-2" />
              Architecture
           </Button>
           <Button 
             onClick={runSimulation}
             disabled={isRunning}
             className="bg-orange-600 hover:bg-orange-700 shadow-lg shadow-orange-600/20 text-white min-w-[140px]"
           >
              {isRunning ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Play className="w-4 h-4 mr-2" />}
              {isRunning ? "Executing..." : "Execute Plan"}
           </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 space-y-6">
           <Card className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 backdrop-blur-md shadow-sm dark:shadow-none">
             <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="text-lg">Workflow Plan</CardTitle>
                  <CardDescription>Hierarchical task breakdown for discovery run #005</CardDescription>
                </div>
                <Badge className={cn(
                  "border-orange-300 dark:border-orange-500/30 text-orange-700 dark:text-orange-400 bg-orange-50 dark:bg-orange-500/10",
                  isRunning && "animate-pulse"
                )}>
                  {isRunning ? "Execution In Progress" : "System Ready"}
                </Badge>
             </CardHeader>
             <CardContent className="space-y-5">
                {plan.map((step, i) => (
                  <div key={step.id} className="flex items-center gap-4 group">
                     <div className={cn(
                        "w-8 h-8 rounded-lg flex items-center justify-center shrink-0 border transition-all duration-500",
                        step.status === "completed" ? "bg-orange-500 border-orange-500 text-gray-900 dark:text-white" :
                        step.status === "running" ? "bg-orange-500/20 border-orange-500 text-orange-700 dark:text-orange-400 animate-pulse" :
                        "bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 text-gray-600 dark:text-white/20"
                     )}>
                        {step.status === "completed" ? <CheckCircle2 className="w-4 h-4" /> : <span className="text-xs font-bold">{i + 1}</span>}
                     </div>
                     <div className="flex-1">
                        <p className={cn(
                           "text-sm font-medium transition-colors duration-500",
                           step.status === "pending" ? "text-gray-600 dark:text-white/20" : "text-gray-900 dark:text-white/90"
                        )}>{step.task}</p>
                        <p className="text-[10px] text-gray-600 dark:text-white/20 uppercase tracking-widest">{step.agent}</p>
                     </div>
                     {step.status === "running" && (
                        <div className="w-24">
                           <Progress value={65} className="h-1 bg-white dark:bg-white/5" indicatorClassName="bg-orange-500" />
                        </div>
                     )}
                  </div>
                ))}
             </CardContent>
           </Card>

           <Card className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 backdrop-blur-md shadow-sm dark:shadow-none">
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                   <Terminal className="w-5 h-5 text-orange-700 dark:text-orange-400" />
                   ACP Execution Console
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                 <div className="h-[300px] w-full bg-gray-900 dark:bg-gray-900 dark:bg-black/60 p-6 font-mono text-white/80 text-[11px] overflow-hidden group border-y border-gray-200 dark:border-white/5">
                    <ScrollArea className="h-full pr-4">
                       <AnimatePresence initial={false}>
                        {logs.map((log, i) => (
                          <motion.div 
                            key={i} 
                            initial={{ opacity: 0, x: -5 }}
                            animate={{ opacity: 1, x: 0 }}
                            className="flex gap-4 mb-2"
                          >
                             <span className="text-gray-500 dark:text-white/40 select-none">[{log.time}]</span>
                             <span className={cn(
                               "font-bold min-w-[70px]",
                               log.agent === "Planner" ? "text-blue-700 dark:text-blue-400" :
                               log.agent === "Discovery" ? "text-purple-700 dark:text-purple-400" :
                               log.agent === "Safety" ? "text-red-700 dark:text-red-400" :
                               log.agent === "Executor" ? "text-orange-700 dark:text-orange-400" : "text-emerald-700 dark:text-emerald-400"
                             )}>{log.agent}:</span>
                             <span className={cn(
                               "text-white/60",
                               log.type === "success" ? "text-emerald-700 dark:text-emerald-400/80" :
                               log.type === "warning" ? "text-yellow-700 dark:text-yellow-400/80" :
                               log.type === "error" ? "text-red-700 dark:text-red-400/80" : ""
                             )}>{log.msg}</span>
                          </motion.div>
                        ))}
                       </AnimatePresence>
                       <div className="flex gap-4">
                          <span className="text-orange-500 animate-pulse">_</span>
                       </div>
                    </ScrollArea>
                 </div>
              </CardContent>
           </Card>
        </div>

        <div className="space-y-6">
           <Card className="bg-gradient-to-br from-orange-600/20 to-amber-600/10 border-gray-200 dark:border-white/10 p-6 relative overflow-hidden">
              <div className="absolute top-0 right-0 w-32 h-32 bg-orange-50 dark:bg-orange-500/10 rounded-full blur-3xl -mr-16 -mt-16" />
              <div className="space-y-4">
                 <div className="flex items-center justify-between">
                    <p className="text-sm font-bold">Execution Intensity</p>
                    <Zap className="w-4 h-4 text-orange-700 dark:text-orange-400" />
                 </div>
                 <div className="space-y-4 pt-2">
                    {[
                      { label: "CPU Utilization", val: isRunning ? 74 : 12 },
                      { label: "Memory Pipeline", val: isRunning ? 92 : 45 },
                      { label: "Agent Sync Rate", val: isRunning ? 99 : 100 },
                    ].map(m => (
                       <div key={m.label} className="space-y-1.5">
                          <div className="flex justify-between text-[10px]">
                             <span className="text-gray-600 dark:text-gray-500 dark:text-white/40">{m.label}</span>
                             <span className="text-gray-900 dark:text-white/90">{m.val}%</span>
                          </div>
                          <div className="h-1 w-full bg-white dark:bg-white/5 rounded-full overflow-hidden">
                             <motion.div 
                               animate={{ width: `${m.val}%` }}
                               className="h-full bg-orange-500" 
                             />
                          </div>
                       </div>
                    ))}
                 </div>
              </div>
           </Card>

           <Card className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10">
              <CardHeader>
                 <CardTitle className="text-sm">Active Toolset</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                 {[
                   { name: "REINVENT-MCP", status: "Active", type: "Discovery" },
                   { name: "MediSafe-Core", status: "Ready", type: "Safety" },
                   { name: "BioPrint-V3", status: "Standby", type: "Automation" },
                 ].map(tool => (
                   <div key={tool.name} className="flex items-center justify-between p-2.5 rounded-lg bg-gray-50 dark:bg-white/[0.03] border border-gray-200 dark:border-white/5">
                      <div>
                        <p className="text-xs font-bold text-gray-900 dark:text-white/90">{tool.name}</p>
                        <p className="text-[10px] text-gray-600 dark:text-white/30">{tool.type}</p>
                      </div>
                      <Badge variant="outline" className={cn(
                        "text-[9px] h-5 border-gray-200 dark:border-white/10",
                        tool.status === "Active" && "text-emerald-700 dark:text-emerald-400 border-emerald-200 dark:border-emerald-500/20 bg-emerald-500/5"
                      )}>{tool.status}</Badge>
                   </div>
                 ))}
              </CardContent>
           </Card>
        </div>
      </div>
    </div>
  );
}
