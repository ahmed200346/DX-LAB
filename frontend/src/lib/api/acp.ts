import type { ACPRunResponse } from "@/lib/types/agent"

const ACP_BASE = "/api/acp"

export async function postACPRun(
  agent: string,
  input: string
): Promise<ACPRunResponse> {
  const res = await fetch(`${ACP_BASE}/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ agent, input }),
    signal: AbortSignal.timeout(120_000),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }))
    throw new Error(err.error || `ACP run failed: ${res.status}`)
  }
  return res.json()
}

export async function listAgents(): Promise<string[]> {
  const res = await fetch(`${ACP_BASE}/agents`, {
    signal: AbortSignal.timeout(10_000),
  })
  if (!res.ok) throw new Error(`Failed to list agents: ${res.status}`)
  const data = await res.json()
  return data.agents || data
}
