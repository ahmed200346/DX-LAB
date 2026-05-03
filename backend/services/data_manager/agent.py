"""
agent.py — Public API entry point.

IntelligentTargetDiscoveryAgent  — thin wrapper over ExtractorAgent.
AgentContext                     — async context manager for clean startup/shutdown.
_demo()                          — runnable demo / smoke test.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from loguru import logger

from config import cfg
from extractor import ExtractorAgent
from models import ACPIntent, ACPRequest, ACPResponse, ContentType
from models import FinalReport
from qa_assistant import QAAssistant

# ── Suppress noisy third-party logs ──────────────────────────────────────────
logging.getLogger("primp").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("huggingface_hub").setLevel(logging.WARNING)

logger.add(
    cfg.LOG_FILE,
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {name}:{function}:{line} | {message}",
    level=cfg.LOG_LEVEL,
    serialize=True,
    rotation="50 MB",
    retention="30 days",
)


# =============================================================================
# INTELLIGENT TARGET DISCOVERY AGENT
# =============================================================================

class IntelligentTargetDiscoveryAgent:
    VERSION = "3.4"

    def __init__(self):
        self._extractor = ExtractorAgent()
        self._started   = False

    async def start(self):
        await self._extractor.initialize()
        self._started = True
        logger.info(
            f"IntelligentTargetDiscoveryAgent v{self.VERSION} started. "
            f"Collections: {list(cfg.COLLECTIONS.keys())}"
        )

    async def stop(self):
        await self._extractor.close()
        self._started = False
        logger.info("IntelligentTargetDiscoveryAgent stopped.")

    async def handle_request(self, request: ACPRequest) -> ACPResponse:
        if not self._started:
            raise RuntimeError("Agent not started. Call await agent.start() first.")
        try:
            return await self._extractor.process_request(request)
        except Exception as exc:
            logger.exception(f"Unhandled error in process_request: {exc}")
            return ACPResponse(
                acp_version=cfg.ACP_VERSION,
                session_id=request.session_id,
                request_id=request.request_id,
                target_agent=request.source_agent,
                data_types=request.data_types,
                payload={},
                validation_score=0.0,
                retrieval_latency_ms=0,
                source_count=0,
                status="error",
                error=str(exc),
            )

    async def discover(
        self,
        query:         str,
        data_types:    Optional[List[ContentType]] = None,
        source_agent:  str = "external",
        filters:       Optional[Dict[str, Any]] = None,
        top_k:         int = cfg.TOP_K_DENSE,
        require_fresh: bool = True,
    ) -> ACPResponse:
        request = ACPRequest(
            source_agent=source_agent,
            query=query,
            data_types=data_types or [ContentType.TEXT, ContentType.PDF],
            filters=filters or {},
            top_k=top_k,
            require_fresh=require_fresh,
        )
        return await self.handle_request(request)
    
    async def generate_report(self, response: ACPResponse, query: str) -> FinalReport:
        """Generate a structured report from a previous discovery response."""
        if not self._started:
            raise RuntimeError("Agent not started. Call await agent.start() first.")
        return await self._extractor.generate_report(response, query)
    async def create_qa_assistant(self, response: ACPResponse) -> QAAssistant:
        """Create a Q&A assistant grounded in the sources of a discovery session."""
        if not self._started:
            raise RuntimeError("Agent not started. Call await agent.start() first.")
        return await self._extractor.create_qa_assistant(response)


# =============================================================================
# ASYNC CONTEXT MANAGER
# =============================================================================

class AgentContext:
    async def __aenter__(self) -> IntelligentTargetDiscoveryAgent:
        self.agent = IntelligentTargetDiscoveryAgent()
        await self.agent.start()
        return self.agent

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.agent.stop()


# =============================================================================
# DEMO / ENTRY POINT
# =============================================================================

async def _demo():
    print("=" * 70)
    print(
        f"INTELLIGENT TARGET DISCOVERY AGENT "
        f"v{IntelligentTargetDiscoveryAgent.VERSION} — Demo"
    )
    print("=" * 70)
    print("NOTE: Set GROQ_API_KEY for HyDE, decomposition, and summarization.")
    print("      Windows: $env:GROQ_API_KEY = 'gsk_...'")
    print("      Linux:   export GROQ_API_KEY=gsk_...")
    print("      Get a free key at: https://console.groq.com")
    print()
    print("NOTE: Set PUBMED_API_KEY env var for higher PubMed rate limits.")
    print("      e.g.  export PUBMED_API_KEY=your_ncbi_api_key")
    print()

    groq_status = "✓ ACTIVE" if cfg.GROQ_API_KEY else "✗ NOT SET (fallback mode)"
    print(f"  Groq ({cfg.GROQ_MODEL}): {groq_status}")
    print(f"  SearXNG engines: {cfg.SEARXNG_ENGINES}")
    print(f"  DATA_FRESHNESS_DAYS: {cfg.DATA_FRESHNESS_DAYS}")
    print(f"  RELEVANCE_THRESHOLD_BASE: {cfg.RELEVANCE_THRESHOLD_BASE}")
    print(f"  RELEVANCE_THRESHOLD_FLOOR: {cfg.RELEVANCE_THRESHOLD_FLOOR}")
    print()

    try:
        async with AgentContext() as agent:
            print("\n[0] Qdrant storage snapshot (before queries)...")
            for col_name in cfg.COLLECTIONS:
                n = await agent._extractor.qdrant_mgr.count_points(col_name)
                print(f"    {col_name:<25} {n:>6} vectors")

            print("\n[TEST] Web search — SearXNG / DDG / Scholar / PubMed test...")
            web_response = await agent.discover(
                query="latest advances CRISPR base editing 2026",
                data_types=[ContentType.TEXT],
                source_agent="test_searxng",
                filters={},
                top_k=5,
                require_fresh=True,
            )
            print(f"    Status:          {web_response.status}")
            print(f"    Items retrieved: {web_response.source_count}")
            print(f"    SGV:             {web_response.validation_score}")
            print(f"    Latency:         {web_response.retrieval_latency_ms}ms")
            if web_response.warning:
                print(f"    ⚠ Warning:       {web_response.warning}")

            print("\n[1] Biomedical target discovery query...")
            response = await agent.discover(
                query="KRAS G12C oncogenic mutation drug targets 2024",
                data_types=[ContentType.TEXT, ContentType.PDF],
                source_agent="discoverer_agent",
                filters={"lang": "en", "score_min": 0.60},
                top_k=10,
            )
            print(f"    Status:           {response.status}")
            print(f"    Validation SGV:   {response.validation_score}")
            print(f"    Items retrieved:  {response.source_count}")
            print(f"    Latency:          {response.retrieval_latency_ms}ms")
            print(f"    Data types:       {list(response.payload.keys())}")
            if response.warning:
                print(f"    ⚠ Warning:        {response.warning}")
            for ctype, items in response.payload.items():
                if items:
                    first = items[0]
                    print(f"\n    First {ctype} result provenance:")
                    print(f"      Title:     {first.get('title', 'N/A')[:60]}")
                    print(f"      PMID:      {first.get('pmid', 'N/A')}")
                    print(f"      DOI:       {first.get('doi', 'N/A')}")
                    print(f"      Citations: {first.get('citation_count', 'N/A')}")
                    print(f"      URL:       {first.get('source_url', '')[:60]}")
                    break

            print("\n[2] Multimodal query (text + image + table)...")
            response2 = await agent.discover(
                query="protein-protein interaction network visualization cancer pathway",
                data_types=[ContentType.TEXT, ContentType.IMAGE, ContentType.TABLE],
                source_agent="reporter_agent",
                top_k=5,
            )
            print(f"    Items: {response2.source_count} | SGV: {response2.validation_score}")
            print(f"    Types returned: {list(response2.payload.keys())}")

            print("\n[3] Full ACP request with all fields...")
            acp_req = ACPRequest(
                source_agent="planner_agent",
                query="clinical trials CAR-T cell therapy acute lymphoblastic leukemia",
                data_types=[ContentType.TEXT, ContentType.PDF, ContentType.TABLE],
                filters={"lang": "en", "score_min": 0.60},
                intent=ACPIntent.FIND,
                top_k=8,
            )
            response3 = await agent.handle_request(acp_req)
            print(f"    Session: {response3.session_id} | Request: {response3.request_id}")
            print(
                f"    Items: {response3.source_count} | "
                f"SGV: {response3.validation_score} | Status: {response3.status}"
            )

            print("\n[4] Qdrant storage snapshot (after queries)...")
            for col_name in cfg.COLLECTIONS:
                n = await agent._extractor.qdrant_mgr.count_points(col_name)
                print(f"    {col_name:<25} {n:>6} vectors")

            print("\n[5] REFRESH test (bypasses cache AND Qdrant)...")
            refresh_req = ACPRequest(
                source_agent="test_agent",
                query="KRAS G12C oncogenic mutation drug targets 2024",
                data_types=[ContentType.TEXT, ContentType.PDF],
                filters={},
                intent=ACPIntent.REFRESH,
                top_k=5,
                require_fresh=True,
            )
            r5 = await agent.handle_request(refresh_req)
            print(
                f"    Items: {r5.source_count} | "
                f"SGV: {r5.validation_score} | Status: {r5.status}"
            )
            for col_name in ["texts_collection", "pdfs_collection"]:
                n = await agent._extractor.qdrant_mgr.count_points(col_name)
                print(f"    {col_name:<25} {n:>6} vectors (post-refresh)")

            print("\n[6] Long-query proactive decomposition test (Groq-powered)...")
            long_query = (
                "What are the molecular mechanisms of KRAS G12C inhibitor resistance "
                "in non-small cell lung cancer and what combination therapies are "
                "currently in clinical trials to overcome this resistance?"
            )
            r6 = await agent.discover(
                query=long_query,
                data_types=[ContentType.TEXT, ContentType.PDF],
                source_agent="decompose_test_agent",
                top_k=5,
            )
            print(f"    Words in query: {len(long_query.split())}")
            print(
                f"    Items: {r6.source_count} | "
                f"SGV: {r6.validation_score} | Status: {r6.status}"
            )

    except KeyboardInterrupt:
        print("\n\n⚠  Interrupted by user — shutting down cleanly.")

async def interactive_terminal():
    """Interactive terminal with forced REFRESH (always runs target extraction)."""
    async with AgentContext() as agent:
        print("\n=== Interactive Terminal (REFRESH mode – always extracts targets) ===")
        print("Type your queries. Type 'exit' or 'quit' to stop.\n")

        while True:
            query = input("Query> ").strip()
            if query.lower() in ("exit", "quit"):
                print("Exiting interactive terminal...")
                break
            if not query:
                continue

            try:
                # Force REFRESH intent to bypass cache and run target extraction
                request = ACPRequest(
                    source_agent="interactive",
                    query=query,
                    data_types=[ContentType.TEXT, ContentType.PDF],
                    filters={},
                    intent=ACPIntent.REFRESH,          # <-- key change
                    top_k=10,
                    require_fresh=True,
                )
                response = await agent.handle_request(request)

                print(f"\nStatus: {response.status}")
                print(f"Validation score: {response.validation_score:.4f}")
                print(f"Items retrieved: {response.source_count}")

                # Show retrieved documents (first per type)
                if response.payload:
                    for ctype, items in response.payload.items():
                        print(f"  [{ctype}] {len(items)} items")
                        if items:
                            first = items[0]
                            print(f"    Title: {first.get('title', 'N/A')[:80]}")
                            print(f"    URL:   {first.get('source_url', '')[:80]}")
                print("-" * 50)

                # --- Display extracted drug targets ---
                if response.targets:
                    print("\n🧬 EXTRACTED DRUG TARGETS:")
                    for t in response.targets:
                        print(f"  • {t.get('gene', '?')} – {t.get('protein', 'N/A')[:60]}")
                        print(f"    UniProt: {t.get('uniprot_id', 'N/A')}")
                        print(f"    Disease: {t.get('disease_context', 'N/A')[:60]}")
                        print(f"    PubMed freq: {t.get('pubmed_frequency_score', 'N/A')}")
                        print(f"    Top pathway: {t.get('top_pathway', 'N/A')}")
                        print()
                else:
                    print("ℹ️ No drug targets extracted.")
                print("-" * 50)
                # --- Offer report and Q&A ---
                while True:
                    print("\nOptions: [R]eport  [Q]uestion  [N]ext query")
                    choice = input("> ").strip().lower()
                    if choice == 'r':
                        try:
                            print("\nGenerating report...")
                            report = await agent.generate_report(response, query)
                            print("\n" + "=" * 70)
                            print(report.to_markdown())
                            print("=" * 70)
                            # Optional: save to file
                            save = input("\nSave report to file? (y/n): ").strip().lower()
                            if save == 'y':
                                filename = f"report_{response.session_id}.md"
                                with open(filename, "w", encoding="utf-8") as f:
                                    f.write(report.to_markdown())
                                print(f"✅ Report saved to {filename}")
                        except Exception as e:
                            print(f"⚠ Report generation failed: {e}")
                    elif choice == 'q':
                        try:
                            print("\nCreating Q&A assistant...")
                            qa = await agent.create_qa_assistant(response)
                            print("Q&A mode active. Type your question (or 'back' to return).")
                            while True:
                                q = input("\nQuestion> ").strip()
                                if q.lower() in ("back", "exit", "quit"):
                                    break
                                if not q:
                                    continue
                                answer = await qa.ask(q)
                                print("\n" + answer.to_text() + "\n")
                        except Exception as e:
                             print(f"⚠ Q&A assistant failed: {e}")
                    elif choice == 'n':
                        break
                    else:
                        print("Invalid choice. Please enter R, Q, or N.")


            except Exception as e:
                print(f"⚠ Error: {e}")


            

if __name__ == "__main__":
    try:
        print("Choose mode:")
        print("  1. Demo")
        print("  2. Interactive terminal")
        choice = input("Enter 1 or 2: ").strip()

        if choice == "1":
            asyncio.run(_demo())
        elif choice == "2":
            asyncio.run(interactive_terminal())
        else:
            print("Invalid choice, exiting.")
    except KeyboardInterrupt:
        print("\n⚠ Ctrl+C received — exited.")