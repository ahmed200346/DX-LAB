import type { GenerateResponse, AskResponse } from "@/lib/types/data-manager"

const BASE = "/api/data-manager"

export async function generateQuery(
  prompt: string,
  topK = 10
): Promise<GenerateResponse> {
  const res = await fetch(`${BASE}/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      prompt,
      top_k: topK,
      data_types: ["text", "pdf"],
      intent: "refresh",
    }),
    signal: AbortSignal.timeout(120_000),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }))
    throw new Error(err.error || err.detail || `Generation failed: ${res.status}`)
  }
  return res.json()
}

export async function askQuestion(
  sessionId: string,
  question: string
): Promise<AskResponse> {
  const res = await fetch(`${BASE}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, question }),
    signal: AbortSignal.timeout(30_000),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }))
    throw new Error(err.error || err.detail || `Ask failed: ${res.status}`)
  }
  return res.json()
}
