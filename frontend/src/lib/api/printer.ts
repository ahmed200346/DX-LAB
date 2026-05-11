import type { PrinterApiResponse } from "@/lib/types/agent"

const BASE = "/api/printer"

export async function submitPrintJob(
  description: string
): Promise<PrinterApiResponse> {
  const res = await fetch(`${BASE}/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ description }),
    signal: AbortSignal.timeout(120_000),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }))
    throw new Error(err.error || `3D print job failed: ${res.status}`)
  }
  return res.json()
}
