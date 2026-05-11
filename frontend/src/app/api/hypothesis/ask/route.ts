import { NextRequest, NextResponse } from "next/server"

const BACKEND_URL = process.env.HYPOTHESIS_API_URL ?? "http://127.0.0.1:8003"

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const targetUrl = `${BACKEND_URL}/ask`

    const backendRes = await fetch(targetUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(30_000),
    })

    const data = await backendRes.json()
    return NextResponse.json(data, { status: backendRes.status })
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Unknown error"
    if (message.includes("ECONNREFUSED") || message.includes("fetch failed")) {
      return NextResponse.json({ answer: "Cannot reach Hypothesis Assistant. Please ensure the service is running on port 8003." }, { status: 503 })
    }
    return NextResponse.json({ answer: `Error: ${message}` }, { status: 500 })
  }
}
