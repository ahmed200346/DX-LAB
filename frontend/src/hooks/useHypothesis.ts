"use client"

import { useState, useCallback } from "react"
import type { Hypothesis, ChatMessage, HypothesisActivity } from "@/lib/types/hypothesis"
import { generateHypotheses, askHypothesis } from "@/lib/api/hypothesis"

export function useHypothesis() {
  const [query, setQuery] = useState("")
  const [isRunning, setIsRunning] = useState(false)
  const [hasRun, setHasRun] = useState(false)
  const [hypotheses, setHypotheses] = useState<Hypothesis[]>([])
  const [currentAction, setCurrentAction] = useState("")
  const [selectedHypothesis, setSelectedHypothesis] = useState<Hypothesis | null>(null)
  const [activities, setActivities] = useState<HypothesisActivity[]>([])
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const generate = useCallback(async (queryVal: string) => {
    setIsRunning(true)
    setHasRun(false)
    setError(null)
    setHypotheses([])
    setChatMessages([])
    setSessionId(null)
    setCurrentAction("Querying vector database...")
    setActivities([{ icon: "MessageSquare", text: "Starting analysis...", time: "now" }])

    try {
      const result = await generateHypotheses(queryVal)

      if (result.success && result.hypotheses) {
        const mapped: Hypothesis[] = result.hypotheses.map((h, i) => ({
          id: i + 1,
          title: h.title || `Hypothesis ${i + 1}`,
          confidence: h.confidence || 50,
          category: h.category || "General",
          impact: h.impact || "Medium",
          novelty: h.novelty || "Medium",
          abstract: h.abstract,
          rationale: h.rationale || "",
          experiment: h.experiment || "",
          citations: h.citations || [],
        }))
        setHypotheses(mapped)
        setSessionId(result.session_id)
        setCurrentAction("Analysis complete")

        const newActivities: HypothesisActivity[] = [
          { icon: "Search", text: `Analyzed: "${queryVal.substring(0, 50)}..."`, time: "just now" },
          { icon: "FileText", text: `Generated ${mapped.length} hypotheses`, time: "just now" },
        ]
        if (result.literature_gaps?.length) {
          newActivities.push({ icon: "AlertCircle", text: `${result.literature_gaps.length} literature gaps identified`, time: "just now" })
        }
        setActivities(newActivities)

        if (result.summary) {
          setChatMessages([
            { role: "dexter", content: `**Analysis complete!**\n\n${result.summary}\n\nSelect a hypothesis to explore details, or ask me a follow-up question.` },
          ])
        }
      } else {
        setError("No hypotheses were generated")
      }

      setHasRun(true)
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Generation failed"
      setError(msg)
    } finally {
      setIsRunning(false)
    }
  }, [])

  const askFollowUp = useCallback(async (question: string) => {
    if (!sessionId) {
      setChatMessages((prev) => [...prev, { role: "user", content: question }, { role: "dexter", content: "Please run a hypothesis generation first." }])
      return
    }

    setChatMessages((prev) => [...prev, { role: "user", content: question }])

    try {
      const result = await askHypothesis(sessionId, question)
      setChatMessages((prev) => [...prev, { role: "dexter", content: result.answer }])
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to get answer"
      setChatMessages((prev) => [...prev, { role: "dexter", content: `Sorry, I encountered an error: ${msg}` }])
    }
  }, [sessionId])

  const reset = useCallback(() => {
    setIsRunning(false)
    setHasRun(false)
    setHypotheses([])
    setCurrentAction("")
    setSelectedHypothesis(null)
    setActivities([])
    setChatMessages([])
    setSessionId(null)
    setError(null)
  }, [])

  return {
    query, setQuery,
    isRunning, hasRun,
    hypotheses, currentAction,
    selectedHypothesis, setSelectedHypothesis,
    activities, chatMessages, sessionId, error,
    generate, askFollowUp, reset,
  }
}
