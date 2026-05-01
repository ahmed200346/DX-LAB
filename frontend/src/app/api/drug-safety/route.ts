import { NextRequest, NextResponse } from "next/server";

/**
 * Proxy route: /api/drug-safety  →  http://localhost:8000/analyze
 *
 * Le frontend (page.tsx) appelle /api/drug-safety?drug=...&age=...&conditions=...
 * Cette route transfère la requête au backend FastAPI (web.py) sur le port 8000
 * et retourne la réponse JSON directement au client React.
 *
 * Avantages :
 *  - Pas de problème CORS (tout passe par le même origin Next.js)
 *  - Backend reste sur son port dédié (8000)
 *  - Frontend reste accessible via `cd frontend && npm run dev` (port 3000)
 */

const BACKEND_URL = process.env.DRUG_SAFETY_API_URL ?? "http://localhost:8000";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);

  const drug = searchParams.get("drug") ?? "";
  const age = searchParams.get("age") ?? "0";
  const conditions = searchParams.get("conditions") ?? "";

  if (!drug.trim()) {
    return NextResponse.json(
      { error: "Le paramètre 'drug' est obligatoire." },
      { status: 400 }
    );
  }

  // Construire l'URL du backend FastAPI (/analyze)
  const backendParams = new URLSearchParams({ drug, age, conditions });
  const targetUrl = `${BACKEND_URL}/analyze?${backendParams.toString()}`;

  try {
    const backendRes = await fetch(targetUrl, {
      // On transmet un timeout raisonnable (60 s) pour les analyses longues
      signal: AbortSignal.timeout(60_000),
    });

    const data = await backendRes.json();

    return NextResponse.json(data, { status: backendRes.status });
  } catch (err: unknown) {
    const message =
      err instanceof Error ? err.message : "Erreur inconnue";

    // Erreur de connexion : le backend FastAPI n'est pas démarré
    if (
      message.includes("ECONNREFUSED") ||
      message.includes("fetch failed") ||
      message.includes("TimeoutError")
    ) {
      return NextResponse.json(
        {
          error:
            "❌ Impossible de joindre le backend Drug Safety. " +
            "Lancez-le avec : cd backend && python run_web.py",
        },
        { status: 503 }
      );
    }

    return NextResponse.json({ error: message }, { status: 500 });
  }
}