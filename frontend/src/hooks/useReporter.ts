"use client"

import { useState, useCallback } from "react"
import { postACPRun } from "@/lib/api/acp"

const STEPS = [
  "Auditing Knowledge Hub Agent outputs...",
  "Aggregating Discovery Agent binding scores...",
  "Compiling Safety Agent toxicity flags...",
  "Cross-referencing Hypothesis Agent resistance models...",
  "Generating NER entity frequency analysis...",
  "Formatting clinical justification (Groq LLM)...",
  "Rendering final DOCX & PDF payloads...",
]

export function useReporter() {
  const [subject, setSubject] = useState("")
  const [isRunning, setIsRunning] = useState(false)
  const [hasReport, setHasReport] = useState(false)
  const [currentStep, setCurrentStep] = useState("")
  const [stepIndex, setStepIndex] = useState(0)
  const [reportData, setReportData] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const generateReport = useCallback(async (subjectVal: string) => {
    setIsRunning(true)
    setHasReport(false)
    setError(null)
    setStepIndex(0)

    try {
      const response = await postACPRun("executor", `Generate comprehensive report for ${subjectVal}`)
      const data = JSON.parse(response.result)
      setReportData(data.report || data.result || response.result)
      setHasReport(true)
      setCurrentStep("Report generated successfully")
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Report generation failed"
      setError(msg)
    } finally {
      setIsRunning(false)
    }
  }, [])

  const reset = useCallback(() => {
    setIsRunning(false)
    setHasReport(false)
    setCurrentStep("")
    setStepIndex(0)
    setReportData(null)
    setError(null)
  }, [])

  return {
    subject, setSubject,
    isRunning, hasReport,
    currentStep, stepIndex, setStepIndex,
    steps: STEPS,
    reportData, error,
    generateReport, reset,
  }
}
