"""
Agent Executor — Orchestrateur principal du système multi-agent.
Utilise LangGraph (StateGraph) pour coordonner l'exécution des plans,
router les requêtes vers les agents appropriés, et suivre l'avancement.

AJOUTS (persistance) :
- Sauvegarde du résultat final dans output/executor/results/ via metrics_logger
- Sauvegarde des métriques Executor dans output/executor/metrics/ via ExecutorMetricsCollector
- Enregistrement des métriques dans le rapport système via SystemMetricsCollector
- Enregistrement des métriques individuelles via metrics_logger.log_metric()
"""

import json
import logging
import time
from typing import Any, Annotated, TypedDict

from langgraph.graph import StateGraph, END

from agents.base_agent import BaseAgent
from metrics.executor_metrics import ExecutorMetricsCollector  # ← ajout
from metrics.metrics_logger import metrics_logger               # ← ajout
from metrics.system_metrics import SystemMetricsCollector       # ← ajout
from prompts.executor_prompts import (
    ANALYZE_REQUEST_PROMPT,
    DISPATCH_PROMPT,
    FINALIZE_PROMPT,
    NEED_HANDLING_PROMPT,
    PROGRESS_CHECK_PROMPT,
    ROUTE_PROMPT,
)
from serveurs.agent_registry import AgentConfig, registry

logger = logging.getLogger(__name__)

# Collecteurs de métriques (singletons de module)
_executor_metrics_collector = ExecutorMetricsCollector()
_system_collector = SystemMetricsCollector()


# ──────────────────────── État LangGraph ────────────────────────

class ExecutorState(TypedDict):
    """État du graphe LangGraph pour l'Executor."""
    input_text: str
    plan: dict
    current_step_index: int
    steps_results: list[dict]
    completed_steps: list[int]
    failed_steps: list[int]
    pending_needs: list[dict]
    final_result: str
    status: str  # analyzing|routing|dispatching|checking|handling_need|finalizing|done|error
    error: str
    metrics: dict


# ──────────────────────── Agent Executor ────────────────────────

class ExecutorAgent(BaseAgent):
    """
    Agent Executor : orchestre l'exécution du plan via LangGraph.
    """

    def __init__(self):
        super().__init__(
            name="executor",
            description="Agent orchestrateur qui coordonne l'exécution des plans entre les agents du système via le protocole ACP.",
            capabilities=[
                "orchestration",
                "routing",
                "coordination",
                "plan_execution",
                "progress_tracking",
                "need_handling",
            ],
        )
        self._executor_metrics = {
            "plans_executed": 0,
            "total_steps_executed": 0,
            "steps_succeeded": 0,
            "steps_failed": 0,
            "total_routing_decisions": 0,
            "routing_changes": 0,
            "total_dispatches": 0,
            "avg_step_time": 0.0,
            "total_needs_handled": 0,
            "needs_resolved": 0,
            "needs_unresolved": 0,
            "total_acp_messages_sent": 0,
            "total_acp_messages_received": 0,
            "avg_acp_latency": 0.0,
            "plan_completion_rate": 0.0,
            "total_retries": 0,
            "error_count": 0,
        }
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Construit le graphe LangGraph de l'Executor."""
        graph = StateGraph(ExecutorState)

        graph.add_node("analyze_request", self._analyze_request)
        graph.add_node("route_to_agent", self._route_to_agent)
        graph.add_node("dispatch_request", self._dispatch_request)
        graph.add_node("collect_response", self._collect_response)
        graph.add_node("check_progress", self._check_progress)
        graph.add_node("handle_needs", self._handle_needs)
        graph.add_node("finalize", self._finalize)

        graph.set_entry_point("analyze_request")

        graph.add_conditional_edges(
            "analyze_request",
            self._after_analyze,
            {"route": "route_to_agent", "error": "finalize"},
        )

        graph.add_edge("route_to_agent", "dispatch_request")
        graph.add_edge("dispatch_request", "collect_response")

        graph.add_conditional_edges(
            "collect_response",
            self._after_collect,
            {"check": "check_progress", "handle_need": "handle_needs"},
        )

        graph.add_conditional_edges(
            "check_progress",
            self._after_progress_check,
            {"continue": "route_to_agent", "finalize": "finalize", "handle_need": "handle_needs"},
        )

        graph.add_conditional_edges(
            "handle_needs",
            self._after_handle_needs,
            {"continue": "route_to_agent", "check": "check_progress"},
        )

        graph.add_edge("finalize", END)
        return graph.compile()

    # ──────────────────────── Nœuds du graphe ────────────────────────

    async def _analyze_request(self, state: ExecutorState) -> dict:
        self.logger.info("Analyse de la requête entrante...")

        available_agents = registry.list_agent_names()
        prompt = ANALYZE_REQUEST_PROMPT.format(
            available_agents=json.dumps(available_agents, ensure_ascii=False),
            input_text=state["input_text"],
        )

        try:
            response = await self.call_llm([
                {"role": "system", "content": "Tu es un orchestrateur intelligent. Réponds uniquement en JSON valide."},
                {"role": "user", "content": prompt},
            ])
            plan = self._parse_json_response(response)
            return {
                "plan": plan,
                "current_step_index": 0,
                "status": "analyzing",
                "metrics": {
                    "analysis_time": time.time(),
                    "total_planned_steps": len(plan.get("steps", [])),
                },
            }
        except Exception as e:
            self.logger.error(f"Erreur d'analyse: {e}")
            return {"status": "error", "error": str(e)}

    async def _route_to_agent(self, state: ExecutorState) -> dict:
        steps = state["plan"].get("steps", [])
        idx = state["current_step_index"]

        if idx >= len(steps):
            return {"status": "finalizing"}

        current_step = steps[idx]
        self.logger.info(
            f"Routage de l'étape {idx + 1}/{len(steps)}: "
            f"{current_step.get('title', current_step.get('description', ''))}"
        )

        agents_info = json.dumps(registry.get_agents_summary(), ensure_ascii=False)
        plan_context = json.dumps(state["plan"], ensure_ascii=False)

        prompt = ROUTE_PROMPT.format(
            agents_info=agents_info,
            step_description=json.dumps(current_step, ensure_ascii=False),
            plan_context=plan_context,
        )

        try:
            response = await self.call_llm([
                {"role": "system", "content": "Tu es un orchestrateur intelligent. Réponds uniquement en JSON valide."},
                {"role": "user", "content": prompt},
            ])

            routing_decision = self._parse_json_response(response)
            self._executor_metrics["total_routing_decisions"] += 1

            target_agent = routing_decision.get("selected_agent", current_step.get("target_agent", ""))
            steps[idx]["routed_agent"] = target_agent

            updated_plan = state["plan"].copy()
            updated_plan["steps"] = steps

            return {"plan": updated_plan, "status": "routing"}
        except Exception as e:
            self.logger.error(f"Erreur de routage: {e}")
            return {"status": "error", "error": str(e)}

    async def _dispatch_request(self, state: ExecutorState) -> dict:
        steps = state["plan"].get("steps", [])
        idx = state["current_step_index"]
        current_step = steps[idx]
        target_agent = current_step.get("routed_agent", current_step.get("target_agent", ""))

        self.logger.info(f"Dispatch vers agent '{target_agent}'...")
        self._executor_metrics["total_dispatches"] += 1

        previous_results = json.dumps(state.get("steps_results", []), ensure_ascii=False)
        plan_context = json.dumps(state["plan"], ensure_ascii=False)

        prompt = DISPATCH_PROMPT.format(
            target_agent=target_agent,
            task_description=json.dumps(current_step, ensure_ascii=False),
            plan_context=plan_context,
            previous_results=previous_results,
        )

        try:
            dispatch_message = await self.call_llm([
                {"role": "system", "content": "Tu es un orchestrateur. Formule une requête claire pour l'agent cible."},
                {"role": "user", "content": prompt},
            ])

            self._executor_metrics["total_acp_messages_sent"] += 1
            start_time = time.time()

            try:
                response = await self.send_to_agent(target_agent, dispatch_message)
                acp_latency = time.time() - start_time
                self._executor_metrics["total_acp_messages_received"] += 1

                total_msgs = self._executor_metrics["total_acp_messages_received"]
                prev_avg = self._executor_metrics["avg_acp_latency"]
                self._executor_metrics["avg_acp_latency"] = (
                    (prev_avg * (total_msgs - 1) + acp_latency) / total_msgs
                )
            except Exception as acp_err:
                self.logger.warning(
                    f"Communication ACP échouée avec '{target_agent}': {acp_err}. "
                    "Traitement local via LLM."
                )
                response = await self.call_llm([
                    {"role": "system", "content": f"Tu es l'agent {target_agent}. Exécute la tâche suivante."},
                    {"role": "user", "content": dispatch_message},
                ])

            step_result = {
                "step_id": current_step.get("step_id", idx + 1),
                "agent": target_agent,
                "response": response,
                "timestamp": time.time(),
                "success": True,
            }

            results = state.get("steps_results", []).copy()
            results.append(step_result)
            return {"steps_results": results, "status": "dispatching"}

        except Exception as e:
            self.logger.error(f"Erreur de dispatch: {e}")
            step_result = {
                "step_id": current_step.get("step_id", idx + 1),
                "agent": target_agent,
                "response": str(e),
                "timestamp": time.time(),
                "success": False,
            }
            results = state.get("steps_results", []).copy()
            results.append(step_result)
            self._executor_metrics["steps_failed"] += 1
            return {"steps_results": results, "status": "error", "error": str(e)}

    async def _collect_response(self, state: ExecutorState) -> dict:
        results = state.get("steps_results", [])
        idx = state["current_step_index"]

        if results and len(results) > idx:
            last_result = results[idx]
            if last_result.get("success"):
                completed = state.get("completed_steps", []).copy()
                completed.append(idx)
                self._executor_metrics["steps_succeeded"] += 1
                self._executor_metrics["total_steps_executed"] += 1

                response_text = str(last_result.get("response", ""))
                has_need = any(
                    kw in response_text.lower()
                    for kw in ["besoin", "nécessite", "manque", "require", "need", "missing"]
                )

                if has_need:
                    needs = state.get("pending_needs", []).copy()
                    needs.append({
                        "step_id": idx,
                        "description": response_text,
                        "from_agent": last_result.get("agent", ""),
                    })
                    return {"completed_steps": completed, "pending_needs": needs, "status": "need_detected"}

                return {"completed_steps": completed, "status": "collected"}
            else:
                failed = state.get("failed_steps", []).copy()
                failed.append(idx)
                return {"failed_steps": failed, "status": "step_failed"}

        return {"status": "collected"}

    async def _check_progress(self, state: ExecutorState) -> dict:
        steps = state["plan"].get("steps", [])
        completed = state.get("completed_steps", [])
        idx = state["current_step_index"]

        self.logger.info(
            f"Vérification avancement: {len(completed)}/{len(steps)} étapes complétées"
        )

        plan_json = json.dumps(state["plan"], ensure_ascii=False)
        results_json = json.dumps(state.get("steps_results", []), ensure_ascii=False)
        completed_json = json.dumps(completed, ensure_ascii=False)
        current_step = steps[idx] if idx < len(steps) else {}

        prompt = PROGRESS_CHECK_PROMPT.format(
            plan=plan_json,
            completed_steps=completed_json,
            current_step=json.dumps(current_step, ensure_ascii=False),
            results_so_far=results_json,
        )

        try:
            response = await self.call_llm([
                {"role": "system", "content": "Tu es un orchestrateur. Évalue l'avancement. Réponds en JSON."},
                {"role": "user", "content": prompt},
            ])
            progress = self._parse_json_response(response)

            if len(steps) > 0:
                self._executor_metrics["plan_completion_rate"] = len(completed) / len(steps)

            next_idx = idx + 1
            return {
                "current_step_index": next_idx,
                "status": "progress_checked",
                "metrics": {
                    **state.get("metrics", {}),
                    "progress_percentage": progress.get("progress_percentage", 0),
                    "quality_assessment": progress.get("quality_assessment", ""),
                },
            }
        except Exception as e:
            self.logger.error(f"Erreur vérification: {e}")
            return {"current_step_index": idx + 1, "status": "progress_checked"}

    async def _handle_needs(self, state: ExecutorState) -> dict:
        needs = state.get("pending_needs", [])
        if not needs:
            return {"status": "no_needs"}

        current_need = needs[0]
        self.logger.info(f"Traitement du besoin: {current_need.get('description', '')[:100]}...")
        self._executor_metrics["total_needs_handled"] += 1

        available_agents = json.dumps(registry.list_agent_names(), ensure_ascii=False)

        prompt = NEED_HANDLING_PROMPT.format(
            requesting_agent=current_need.get("from_agent", "unknown"),
            need_description=current_need.get("description", ""),
            task_context=json.dumps(state["plan"], ensure_ascii=False),
            available_agents=available_agents,
        )

        try:
            response = await self.call_llm([
                {"role": "system", "content": "Tu es un orchestrateur. Gère ce besoin. Réponds en JSON."},
                {"role": "user", "content": prompt},
            ])
            need_resolution = self._parse_json_response(response)

            if need_resolution.get("can_be_resolved", False):
                self._executor_metrics["needs_resolved"] += 1

                target = need_resolution.get("target_agent")
                if target and registry.has_agent(target):
                    try:
                        resolution_response = await self.send_to_agent(
                            target, need_resolution.get("request_to_send", "")
                        )
                        results = state.get("steps_results", []).copy()
                        results.append({
                            "step_id": f"need_resolution_{len(results)}",
                            "agent": target,
                            "response": resolution_response,
                            "timestamp": time.time(),
                            "success": True,
                            "type": "need_resolution",
                        })
                        remaining_needs = needs[1:]
                        return {
                            "steps_results": results,
                            "pending_needs": remaining_needs,
                            "status": "need_resolved",
                        }
                    except Exception as e:
                        self.logger.warning(f"Résolution du besoin échouée: {e}")

            self._executor_metrics["needs_unresolved"] += 1
            remaining_needs = needs[1:]
            return {"pending_needs": remaining_needs, "status": "need_unresolved"}

        except Exception as e:
            self.logger.error(f"Erreur gestion besoin: {e}")
            return {"status": "error", "error": str(e)}

    async def _finalize(self, state: ExecutorState) -> dict:
        self.logger.info("Finalisation de l'exécution du plan...")
        self._executor_metrics["plans_executed"] += 1

        plan_json = json.dumps(state.get("plan", {}), ensure_ascii=False)
        results_json = json.dumps(state.get("steps_results", []), ensure_ascii=False)
        metrics_json = json.dumps(state.get("metrics", {}), ensure_ascii=False)

        prompt = FINALIZE_PROMPT.format(
            plan=plan_json,
            all_results=results_json,
            execution_metrics=metrics_json,
        )

        try:
            response = await self.call_llm([
                {"role": "system", "content": "Tu es un orchestrateur. Compile les résultats finaux. Réponds en JSON."},
                {"role": "user", "content": prompt},
            ])
            final = self._parse_json_response(response)
            return {
                "final_result": json.dumps(final, ensure_ascii=False, indent=2),
                "status": "done",
            }
        except Exception as e:
            self.logger.error(f"Erreur finalisation: {e}")
            return {
                "final_result": json.dumps({
                    "summary": "Exécution terminée avec des erreurs",
                    "results": state.get("steps_results", []),
                    "error": str(e),
                }, ensure_ascii=False, indent=2),
                "status": "done",
            }

    # ──────────────────────── Conditions de transition ────────────────────────

    def _after_analyze(self, state: ExecutorState) -> str:
        return "error" if state.get("status") == "error" else "route"

    def _after_collect(self, state: ExecutorState) -> str:
        return "handle_need" if state.get("status") == "need_detected" else "check"

    def _after_progress_check(self, state: ExecutorState) -> str:
        steps = state["plan"].get("steps", [])
        idx = state.get("current_step_index", 0)
        if idx >= len(steps):
            return "finalize"
        if state.get("pending_needs", []):
            return "handle_need"
        return "continue"

    def _after_handle_needs(self, state: ExecutorState) -> str:
        return "check" if state.get("pending_needs", []) else "continue"

    # ──────────────────────── Méthode principale ─────────────────────────────

    async def run(self, input_text: str, context: Any = None) -> Any:
        """
        Point d'entrée de l'Executor.
        Reçoit un plan ou une requête et orchestre son exécution via LangGraph.
        """
        start_time = time.time()
        self.logger.info(f"Executor démarré avec input: {input_text[:200]}...")

        initial_state: ExecutorState = {
            "input_text": input_text,
            "plan": {},
            "current_step_index": 0,
            "steps_results": [],
            "completed_steps": [],
            "failed_steps": [],
            "pending_needs": [],
            "final_result": "",
            "status": "analyzing",
            "error": "",
            "metrics": {},
        }

        try:
            final_state = await self.graph.ainvoke(initial_state)

            processing_time = time.time() - start_time
            success = final_state.get("status") == "done"
            self.update_metrics(success=success, processing_time=processing_time)

            total_steps = self._executor_metrics["total_steps_executed"]
            if total_steps > 0:
                self._executor_metrics["avg_step_time"] = processing_time / total_steps

            self.logger.info(
                f"Executor terminé en {processing_time:.2f}s — "
                f"Statut: {final_state.get('status')}"
            )

            output = final_state.get("final_result", "Exécution terminée sans résultat")

            # ── PERSISTANCE ─────────────────────────────────────────────────
            self._persist_result(final_state, output, processing_time, success)
            self._persist_metrics(processing_time)

            return output

        except Exception as e:
            processing_time = time.time() - start_time
            self.update_metrics(success=False, processing_time=processing_time)
            self._executor_metrics["error_count"] += 1
            self.logger.error(f"Executor erreur: {e}")

            error_output = json.dumps({
                "error": str(e),
                "status": "failed",
                "processing_time": processing_time,
            })

            # ── PERSISTANCE de l'erreur ──────────────────────────────────────
            self._persist_result({}, error_output, processing_time, success=False)
            self._persist_metrics(processing_time)

            return error_output

    # ──────────────────────── Méthodes de persistance ────────────────────────

    def _persist_result(
        self,
        final_state: dict,
        output: str,
        processing_time: float,
        success: bool,
    ) -> None:
        """
        Sauvegarde le résultat final dans output/executor/results/<type>_<timestamp>.json
        """
        try:
            result_data = {
                "success": success,
                "processing_time_seconds": processing_time,
                "status": final_state.get("status", "unknown"),
                "steps_results": final_state.get("steps_results", []),
                "completed_steps": final_state.get("completed_steps", []),
                "failed_steps": final_state.get("failed_steps", []),
                "final_output": output,
                "plan_summary": {
                    k: v for k, v in final_state.get("plan", {}).items()
                    if k != "steps"  # les steps sont déjà dans steps_results
                },
            }

            result_type = "execution" if success else "execution_error"
            filepath = metrics_logger.log_result(
                agent_name=self.name,
                result_data=result_data,
                result_type=result_type,
            )
            self.logger.info(f"Résultat Executor sauvegardé → {filepath}")
        except Exception as e:
            self.logger.error(f"Échec sauvegarde résultat Executor: {e}")

    def _persist_metrics(self, processing_time: float) -> None:
        """
        Sauvegarde les métriques dans output/executor/metrics/ via ExecutorMetricsCollector,
        enregistre dans le rapport système via SystemMetricsCollector,
        et enregistre les métriques individuelles dans le log centralisé.
        """
        try:
            combined = self.get_executor_metrics()

            # 1. Snapshot dans ExecutorMetricsCollector → output/executor/metrics/
            _executor_metrics_collector.record_execution(combined)
            metrics_path = _executor_metrics_collector.save_metrics()
            self.logger.info(f"Métriques Executor sauvegardées → {metrics_path}")

            # 2. Enregistrement dans le collecteur système (rapport global)
            _system_collector.record_agent_metrics(self.name, combined)
            _system_collector.save_agent_metrics(self.name, combined)

            # 3. Métriques individuelles dans le log centralisé
            metrics_logger.log_metric(self.name, "processing_time_seconds", processing_time)
            metrics_logger.log_metric(self.name, "plans_executed", self._executor_metrics["plans_executed"])
            metrics_logger.log_metric(self.name, "steps_succeeded", self._executor_metrics["steps_succeeded"])
            metrics_logger.log_metric(self.name, "steps_failed", self._executor_metrics["steps_failed"])
            metrics_logger.log_metric(self.name, "plan_completion_rate", self._executor_metrics["plan_completion_rate"])
            metrics_logger.log_metric(self.name, "avg_acp_latency_seconds", self._executor_metrics["avg_acp_latency"])
            metrics_logger.log_metric(self.name, "total_routing_decisions", self._executor_metrics["total_routing_decisions"])

        except Exception as e:
            self.logger.error(f"Échec sauvegarde métriques Executor: {e}")

    # ──────────────────────── Métriques & utilitaires ────────────────────────

    def get_executor_metrics(self) -> dict[str, Any]:
        """Retourne les métriques combinées (base + executor)."""
        base = self.get_metrics()
        return {**base, **self._executor_metrics}

    def _parse_json_response(self, response: str) -> dict:
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            import re
            json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass

            brace_match = re.search(r"\{[\s\S]*\}", response)
            if brace_match:
                try:
                    return json.loads(brace_match.group())
                except json.JSONDecodeError:
                    pass

            self.logger.warning("Impossible de parser la réponse JSON, retour brut")
            return {"raw_response": response}


# ──────────────────────── Factory pour le registre ────────────────────────

_executor_instance = None


def get_executor_instance() -> ExecutorAgent:
    global _executor_instance
    if _executor_instance is None:
        _executor_instance = ExecutorAgent()
    return _executor_instance


def get_agent_config() -> AgentConfig:
    executor = get_executor_instance()
    return AgentConfig(
        name=executor.name,
        description=executor.description,
        handler=executor.run,
        capabilities=executor.capabilities,
        input_content_types=["text/plain", "application/json"],
        output_content_types=["text/plain", "application/json"],
    )