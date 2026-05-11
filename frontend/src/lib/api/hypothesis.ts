import type { HypothesisResult } from "@/lib/types/hypothesis"

const BASE = "/api/hypothesis"

export async function generateHypotheses(
  query: string,
  numHypotheses = 3
): Promise<HypothesisResult> {
  const res = await fetch(`${BASE}/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, num_hypotheses: numHypotheses }),
    signal: AbortSignal.timeout(120_000),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }))
    throw new Error(err.detail || err.error || `Hypothesis generation failed: ${res.status}`)
  }
  return res.json()
}

export async function askHypothesis(
  sessionId: string,
  question: string
): Promise<{ answer: string }> {
  const res = await fetch(`${BASE}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, question }),
    signal: AbortSignal.timeout(30_000),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }))
    throw new Error(err.detail || err.error || `Ask failed: ${res.status}`)
  }
  return res.json()
}
