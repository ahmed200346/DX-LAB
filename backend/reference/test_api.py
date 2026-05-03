"""
Script de test pour le serveur ACP.
─────────────────────────────────────
IMPORTANT : Le navigateur envoie des requêtes GET.
Or /runs n'accepte que POST → 405 Method Not Allowed est normal depuis un navigateur.
Ce script effectue les appels HTTP corrects pour tester le serveur.

Usage :
    python test_api.py
"""

import asyncio
import json
import sys

# ── Test 1 : liste des agents (GET /agents) ──────────────────────────────────
def test_list_agents():
    """GET /agents — doit retourner la liste des agents enregistrés."""
    try:
        import urllib.request
        url = "http://127.0.0.1:8000/agents"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
            print("✅ GET /agents →", json.dumps(data, indent=2, ensure_ascii=False))
            return True
    except Exception as e:
        print(f"❌ GET /agents → {e}")
        return False


# ── Test 2 : exécution synchrone via acp_sdk client ─────────────────────────
async def test_run_agent(agent_name: str, message: str):
    """POST /runs — exécute un agent via le client ACP officiel."""
    try:
        from acp_sdk.client import Client
        from acp_sdk.models import Message, MessagePart

        async with Client(base_url="http://127.0.0.1:8000") as client:
            run = await client.run_sync(
                agent=agent_name,
                input=[
                    Message(
                        parts=[MessagePart(content=message, content_type="text/plain")]
                    )
                ],
            )
            print(f"\n✅ Agent '{agent_name}' — réponse reçue :")
            for msg in run.output:
                for part in msg.parts:
                    if hasattr(part, "content"):
                        print(part.content)
            return True
    except Exception as e:
        print(f"❌ Agent '{agent_name}' → erreur : {e}")
        return False


# ── Test 3 : appel HTTP brut avec POST /runs ─────────────────────────────────
def test_raw_post(agent_name: str, message: str):
    """
    POST /runs avec urllib — montre la différence GET vs POST.
    C'est exactement ce qu'un navigateur ne fait PAS (il envoie GET).
    """
    try:
        import urllib.request
        url = "http://127.0.0.1:8000/runs"
        payload = json.dumps({
            "agent": agent_name,
            "input": [
                {
                    "parts": [
                        {"content": message, "content_type": "text/plain"}
                    ]
                }
            ],
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            print(f"\n✅ POST /runs (raw) → {json.dumps(data, indent=2, ensure_ascii=False)}")
            return True
    except Exception as e:
        print(f"❌ POST /runs (raw) → {e}")
        return False


# ── Équivalents curl ─────────────────────────────────────────────────────────
def print_curl_examples():
    print("\n" + "="*60)
    print("ÉQUIVALENTS CURL pour tester depuis le terminal :")
    print("="*60)
    print("\n# 1. Lister les agents")
    print("curl http://127.0.0.1:8000/agents")
    print("\n# 2. Exécuter le planner")
    print("""curl -X POST http://127.0.0.1:8000/runs \\
  -H "Content-Type: application/json" \\
  -d '{
    "agent": "planner",
    "input": [
      {
        "parts": [
          {"content": "Créer une API REST en Python avec FastAPI", "content_type": "text/plain"}
        ]
      }
    ]
  }'""")
    print("\n# 3. Exécuter l'executor")
    print("""curl -X POST http://127.0.0.1:8000/runs \\
  -H "Content-Type: application/json" \\
  -d '{
    "agent": "executor",
    "input": [
      {
        "parts": [
          {"content": "Analyser ce besoin et créer un plan", "content_type": "text/plain"}
        ]
      }
    ]
  }'""")


if __name__ == "__main__":
    print("=" * 60)
    print("  Test du serveur ACP — http://127.0.0.1:8000")
    print("=" * 60)
    print("\n⚠️  Note : Un navigateur envoie GET vers /runs → 405 est NORMAL.")
    print("   /runs n'accepte que POST (protocole ACP).\n")

    # Test liste des agents
    ok = test_list_agents()

    if ok:
        # Test via le client ACP officiel
        asyncio.run(test_run_agent("planner", "pourriez vous me générer un rapport à propos les différents types d'alchool et leurs formules chimiques, le rapport doit avoir les images des molécules les caractèristique et l'usage de chaque une"))
    else:
        print("\n⚠️  Le serveur ne répond pas. Vérifiez qu'il est démarré avec : python main.py")

    print_curl_examples()