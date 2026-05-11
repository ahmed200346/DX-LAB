"use client";

import { cn } from "@/lib/utils";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Binary, ListTodo, Activity, Terminal, Play, Pause, Square, Zap, Layers, ChevronRight,
  Loader2, CheckCircle2, AlertCircle
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Progress } from "@/components/ui/progress";
import { useOrchestrator } from "@/hooks/useOrchestrator";

export default function OrchestratorView() {
  const {
    plan, logs,
    isRunning, progress, error,
    executePlan, reset,
  } = useOrchestrator();

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
            onClick={executePlan}
            disabled={isRunning}
            className="bg-orange-600 hover:bg-orange-700 shadow-lg shadow-orange-600/20 text-white min-w-[140px]"
          >
            {isRunning ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Play className="w-4 h-4 mr-2" />}
            {isRunning ? "Executing..." : "Execute Plan"}
          </Button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-400 text-sm">{error}</div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 space-y-6">
          <Card className="bg-white dark:bg-white/5 border-gray-200 dark:border-white/10 backdrop-blur-md shadow-sm dark:shadow-none">
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="text-lg">Workflow Plan</CardTitle>
                <CardDescription>Hierarchical task breakdown for discovery run</CardDescription>
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
                      <Progress value={65} className="h-1 bg-white dark:bg-white/5" />
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
                  { label: "Progress", val: progress },
                  { label: "Plan Steps", val: plan.filter(s => s.status !== "pending").length * 20 },
                  { label: "Completed", val: plan.filter(s => s.status === "completed").length > 0 ? Math.round((plan.filter(s => s.status === "completed").length / plan.length) * 100) : 0 },
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
