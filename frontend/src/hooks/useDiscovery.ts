"use client"

import { useState, useCallback } from "react"
import type { PipelineStep, Candidate } from "@/lib/types/agent"
import { postACPRun } from "@/lib/api/acp"

const INITIAL_STEPS: PipelineStep[] = [
  { id: "extraction", name: "Target Extraction", description: "Identifying gene, fasta and seed SMILES", status: "pending" },
  { id: "pooling", name: "Candidate Generation", description: "Running REINVENT generative models", status: "pending" },
  { id: "prediction", name: "Property Prediction", description: "Calculating pKd and ADMET scores", status: "pending" },
  { id: "refinement", name: "Iterative Refinement", description: "LLM-based lead optimization", status: "pending" },
  { id: "boltz", name: "Structure Prediction", description: "Boltz 3D folding for top hits", status: "pending" },
]

export function useDiscovery() {
  const [protein, setProtein] = useState("")
  const [disease, setDisease] = useState("")
  const [isRunning, setIsRunning] = useState(false)
  const [hasRun, setHasRun] = useState(false)
  const [runId, setRunId] = useState<string | null>(null)
  const [steps, setSteps] = useState<PipelineStep[]>(INITIAL_STEPS)
  const [candidates, setCandidates] = useState<Candidate[]>([])
  const [error, setError] = useState<string | null>(null)

  const updateStep = (id: string, update: Partial<PipelineStep>) =>
    setSteps((prev) => prev.map((s) => (s.id === id ? { ...s, ...update } : s)))

  const startPipeline = useCallback(async (proteinVal: string, diseaseVal: string) => {
    setIsRunning(true)
    setHasRun(false)
    setError(null)
    setSteps(INITIAL_STEPS.map((s) => ({ ...s, status: "pending" as const })))
    setCandidates([])

    try {
      const response = await postACPRun("executor", `Target ${proteinVal} for ${diseaseVal}`)
      const data = JSON.parse(response.result)
      setRunId(data.runId || `run_${Date.now()}`)
      if (data.steps) setSteps(data.steps)
      if (data.candidates) setCandidates(data.candidates)
      setHasRun(true)
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Pipeline failed"
      setError(msg)
      updateStep("extraction", { status: "error", details: msg })
    } finally {
      setIsRunning(false)
    }
  }, [])

  const reset = useCallback(() => {
    setIsRunning(false)
    setHasRun(false)
    setRunId(null)
    setSteps(INITIAL_STEPS)
    setCandidates([])
    setError(null)
  }, [])

  return {
    protein, setProtein,
    disease, setDisease,
    isRunning, hasRun, runId,
    steps, candidates, error,
    startPipeline, reset,
  }
}
