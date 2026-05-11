"use client"

import { useState, useCallback } from "react"
import type { PlanStep, LogEntry } from "@/lib/types/agent"
import { postACPRun } from "@/lib/api/acp"

const INITIAL_PLAN: PlanStep[] = [
  { id: 1, task: "Analyze Target Context", agent: "Planner", status: "pending" },
  { id: 2, task: "Extract Protein Structure", agent: "Discovery", status: "pending" },
  { id: 3, task: "Sample Molecule Space", agent: "Discovery", status: "pending" },
  { id: 4, task: "Safety Screening", agent: "Safety", status: "pending" },
  { id: 5, task: "Synthesis Feasibility", agent: "Executor", status: "pending" },
]

export function useOrchestrator() {
  const [isRunning, setIsRunning] = useState(false)
  const [progress, setProgress] = useState(0)
  const [plan, setPlan] = useState<PlanStep[]>(INITIAL_PLAN)
  const [logs, setLogs] = useState<LogEntry[]>([
    { time: new Date().toLocaleTimeString(), msg: "System standby. Ready to execute.", type: "info", agent: "Core" },
  ])
  const [error, setError] = useState<string | null>(null)

  const executePlan = useCallback(async () => {
    setIsRunning(true)
    setError(null)
    setProgress(0)
    setPlan(INITIAL_PLAN.map((p) => ({ ...p, status: "pending" as const })))
    setLogs([{ time: new Date().toLocaleTimeString(), msg: "Starting execution...", type: "info", agent: "Core" }])

    try {
      const response = await postACPRun("executor", "Execute full discovery workflow for BCL-2 targets")
      const data = JSON.parse(response.result)

      if (data.logs) {
        setLogs(data.logs.map((l: LogEntry) => ({
          ...l,
          time: l.time || new Date().toLocaleTimeString(),
        })))
      }
      if (data.plan) setPlan(data.plan)
      if (data.progress !== undefined) setProgress(data.progress)
      else setProgress(100)
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Execution failed"
      setError(msg)
      setLogs((prev) => [...prev, { time: new Date().toLocaleTimeString(), msg: `Error: ${msg}`, type: "error", agent: "Core" }])
    } finally {
      setIsRunning(false)
    }
  }, [])

  const reset = useCallback(() => {
    setIsRunning(false)
    setProgress(0)
    setPlan(INITIAL_PLAN)
    setLogs([{ time: new Date().toLocaleTimeString(), msg: "System standby. Ready to execute.", type: "info", agent: "Core" }])
    setError(null)
  }, [])

  return {
    plan, logs,
    isRunning, progress, error,
    executePlan, reset,
  }
}
