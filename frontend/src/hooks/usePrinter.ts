"use client"

import { useState, useCallback } from "react"
import type { PrinterResult } from "@/lib/types/agent"
import { submitPrintJob } from "@/lib/api/printer"

export function usePrinter() {
  const [moleculeName, setMoleculeName] = useState("")
  const [isRunning, setIsRunning] = useState(false)
  const [hasRun, setHasRun] = useState(false)
  const [result, setResult] = useState<PrinterResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const submitMolecule = useCallback(async (name: string) => {
    setIsRunning(true)
    setHasRun(false)
    setError(null)
    setResult(null)

    try {
      const response = await submitPrintJob(name)

      if (response.success && response.data) {
        setResult(response.data)
        setHasRun(true)
      } else {
        setError(response.error || "Failed to process molecule")
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Print job failed"
      setError(msg)
    } finally {
      setIsRunning(false)
    }
  }, [])

  const reset = useCallback(() => {
    setIsRunning(false)
    setHasRun(false)
    setResult(null)
    setError(null)
  }, [])

  return {
    moleculeName, setMoleculeName,
    isRunning, hasRun,
    result, error,
    submitMolecule, reset,
  }
}
