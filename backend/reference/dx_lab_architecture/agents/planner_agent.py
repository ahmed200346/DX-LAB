"""
Agent Planner — Analyse des besoins et génération de plans d'exécution.
Reçoit l'input utilisateur, utilise le LLM pour comprendre le besoin,
et génère un plan structuré transmis à l'Executor via ACP.

AJOUTS (persistance) :
- Sauvegarde du résultat (plan) dans output/planner/results/ via metrics_logger
- Sauvegarde des métriques Planner dans output/planner/metrics/ via system_metrics
- Enregistrement des métriques individuelles via metrics_logger.log_metric()
"""

import json
import logging
import time
from typing import Any

from agents.base_agent import BaseAgent
from metrics.metrics_logger import metrics_logger          # ← ajout
from metrics.system_metrics import SystemMetricsCollector  # ← ajout
from prompts.planner_prompts import (
    GENERATE_PLAN_PROMPT,
    REFINE_PLAN_PROMPT,
    UNDERSTAND_NEED_PROMPT,
)
from serveurs.agent_registry import AgentConfig, registry

logger = logging.getLogger(__name__)

# Collecteur système partagé (singleton de module)
_system_collector = SystemMetricsCollector()


class PlannerAgent(BaseAgent):
    """
    Agent Planner : analyse le besoin utilisateur et génère un plan d'exécution.
    """

    def __init__(self):
        super().__init__(
            name="planner",
            description="Agent d'analyse qui comprend les besoins utilisateur et génère des plans d'exécution structurés avec Chain-of-Thought.",
            capabilities=[
                "need_analysis",
                "plan_generation",
                "plan_refinement",
                "requirement_extraction",
                "task_decomposition",
            ],
        )
        self._planner_metrics = {
            "plans_generated": 0,
            "plans_refined": 0,
            "avg_plan_steps": 0.0,
            "total_plan_steps_generated": 0,
            "avg_analysis_time": 0.0,
            "avg_generation_time": 0.0,
            "clarifications_needed": 0,
            "avg_generation_time": 0.0,
            "clarifications_needed": 0,
            "complexity_distribution": {"simple": 0, "moderate": 0, "complex": 0},
            "successful_validations": 0,
            "total_validations": 0,
            "user_validation_score": 0.0,
        }

    async def run(self, input_text: str, context: Any = None) -> Any:
        """
        Point d'entrée du Planner.
        Analyse le besoin et génère un plan d'exécution.
        """
        start_time = time.time()
        self.logger.info("Planner démarré — Analyse du besoin utilisateur...")

        try:
            # Vérifier si l'input est un JSON structuré venant de l'UI
            try:
                request_data = json.loads(input_text)
                if isinstance(request_data, dict) and "action" in request_data:
                    action = request_data["action"]
                    if action == "clarification_response":
                        return await self._handle_clarification_response(request_data)
                    elif action == "refine_plan":
                        return await self._handle_refine_plan(request_data)
                    elif action == "validate_plan":
                        return await self._handle_validate_plan(request_data)
                    elif action == "new":
                        input_text = request_data.get("query", input_text)
            except json.JSONDecodeError:
                pass  # Input texte classique

            # ── Phase 1 : Comprendre le besoin ───────────────────────────────
            analysis_start = time.time()
            need_analysis = await self._understand_need(input_text)
            analysis_time = time.time() - analysis_start

            total = self._planner_metrics["plans_generated"] + 1
            prev_avg = self._planner_metrics["avg_analysis_time"]
            self._planner_metrics["avg_analysis_time"] = (
                (prev_avg * (total - 1) + analysis_time) / total
            )

            # ── Clarification nécessaire ? ────────────────────────────────────
            if need_analysis.get("requires_clarification", False):
                self._planner_metrics["clarifications_needed"] += 1
                self.logger.info("Des clarifications sont nécessaires")

                clarification_result = {
                    "status": "needs_clarification",
                    "analysis": need_analysis,
                    "questions": need_analysis.get("clarification_questions", []),
                }

                # ── PERSISTANCE : sauvegarder le résultat de clarification ──
                self._persist_result(clarification_result, result_type="clarification")

                return json.dumps(clarification_result, ensure_ascii=False, indent=2)

            # ── Phase 2 : Générer le plan ─────────────────────────────────────
            generation_start = time.time()
            plan = await self._generate_plan(need_analysis)
            generation_time = time.time() - generation_start

            prev_gen_avg = self._planner_metrics["avg_generation_time"]
            self._planner_metrics["avg_generation_time"] = (
                (prev_gen_avg * (total - 1) + generation_time) / total
            )

            num_steps = len(plan.get("steps", []))
            self._planner_metrics["plans_generated"] += 1
            self._planner_metrics["total_plan_steps_generated"] += num_steps
            if self._planner_metrics["plans_generated"] > 0:
                self._planner_metrics["avg_plan_steps"] = (
                    self._planner_metrics["total_plan_steps_generated"]
                    / self._planner_metrics["plans_generated"]
                )

            complexity = plan.get("estimated_complexity", "moderate")
            if complexity in self._planner_metrics["complexity_distribution"]:
                self._planner_metrics["complexity_distribution"][complexity] += 1

            processing_time = time.time() - start_time
            self.update_metrics(success=True, processing_time=processing_time)

            self.logger.info(
                f"Plan généré: '{plan.get('plan_title', 'N/A')}' — "
                f"{num_steps} étapes — {processing_time:.2f}s"
            )

            result = {
                "status": "plan_generated",
                "analysis": need_analysis,
                "plan": plan,
                "metrics": {
                    "analysis_time": analysis_time,
                    "generation_time": generation_time,
                    "total_time": processing_time,
                    "num_steps": num_steps,
                },
            }

            # ── PERSISTANCE ───────────────────────────────────────────────────
            self._persist_result(result, result_type="plan")
            self._persist_metrics(processing_time, analysis_time, generation_time, num_steps)

            return json.dumps(result, ensure_ascii=False, indent=2)

        except Exception as e:
            processing_time = time.time() - start_time
            self.update_metrics(success=False, processing_time=processing_time)
            self.logger.error(f"Planner erreur: {e}")

            error_result = {"status": "error", "error": str(e)}

            # ── PERSISTANCE : sauvegarder même en cas d'erreur ───────────────
            self._persist_result(error_result, result_type="error")

            return json.dumps(error_result, ensure_ascii=False, indent=2)

    # ──────────────────────── Handlers UI ──────────────────────────────────────

    async def _handle_clarification_response(self, request_data: dict) -> str:
        """Génère le plan après avoir reçu les clarifications de l'utilisateur."""
        start_time = time.time()
        self.logger.info("Planner — Génération du plan suite à clarification...")
        try:
            need_analysis = request_data.get("analysis", {})
            answers = request_data.get("answers", "")
            need_analysis["user_clarifications"] = answers
            need_analysis["requires_clarification"] = False
            
            generation_start = time.time()
            plan = await self._generate_plan(need_analysis)
            generation_time = time.time() - generation_start

            total = self._planner_metrics["plans_generated"] + 1
            prev_gen_avg = self._planner_metrics["avg_generation_time"]
            self._planner_metrics["avg_generation_time"] = (
                (prev_gen_avg * (total - 1) + generation_time) / total
            )

            num_steps = len(plan.get("steps", []))
            self._planner_metrics["plans_generated"] += 1
            self._planner_metrics["total_plan_steps_generated"] += num_steps
            if self._planner_metrics["plans_generated"] > 0:
                self._planner_metrics["avg_plan_steps"] = (
                    self._planner_metrics["total_plan_steps_generated"]
                    / self._planner_metrics["plans_generated"]
                )

            complexity = plan.get("estimated_complexity", "moderate")
            if complexity in self._planner_metrics["complexity_distribution"]:
                self._planner_metrics["complexity_distribution"][complexity] += 1

            processing_time = time.time() - start_time
            self.update_metrics(success=True, processing_time=processing_time)

            result = {
                "status": "plan_generated",
                "analysis": need_analysis,
                "plan": plan,
                "metrics": {
                    "generation_time": generation_time,
                    "total_time": processing_time,
                    "num_steps": num_steps,
                },
            }
            self._persist_result(result, result_type="plan")
            self._persist_metrics(processing_time, 0.0, generation_time, num_steps)

            return json.dumps(result, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"Erreur clarification: {e}")
            return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False)

    async def _handle_refine_plan(self, request_data: dict) -> str:
        """Raffine le plan selon le feedback utilisateur."""
        start_time = time.time()
        self.logger.info("Planner — Raffinement du plan...")
        try:
            current_plan = request_data.get("current_plan", {})
            feedback = request_data.get("feedback", "")
            
            refined_plan = await self.refine_plan(current_plan, feedback)
            
            processing_time = time.time() - start_time
            self.update_metrics(success=True, processing_time=processing_time)
            
            # Persister ce résultat spécifique
            result = {
                "status": "plan_generated",
                "plan": refined_plan.get("updated_plan", refined_plan),
                "feedback_applied": feedback,
            }
            self._persist_result(result, result_type="plan_refined")
            return json.dumps(result, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"Erreur raffinement: {e}")
            return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False)

    async def _handle_validate_plan(self, request_data: dict) -> str:
        """Enregistre la validation de l'utilisateur et met à jour les scores de performance."""
        self.logger.info("Planner — Validation du plan par l'utilisateur...")
        score = request_data.get("score", 5) # Score sur 5
        
        self._planner_metrics["total_validations"] += 1
        self._planner_metrics["successful_validations"] += 1
        
        total_score = self._planner_metrics["user_validation_score"] * (self._planner_metrics["total_validations"] - 1)
        self._planner_metrics["user_validation_score"] = (total_score + score) / self._planner_metrics["total_validations"]
        
        # Enregistrer la métrique dans le logger central
        metrics_logger.log_metric(self.name, "user_validation_score", self._planner_metrics["user_validation_score"])
        metrics_logger.log_metric(self.name, "total_validations", self._planner_metrics["total_validations"])
        
        result = {
            "status": "plan_validated",
            "message": "Plan validé avec succès par l'utilisateur.",
            "score": score
        }
        self._persist_result(result, result_type="plan_validated")
        
        # Met à jour le collecteur global
        _system_collector.record_agent_metrics(self.name, self.get_planner_metrics())
        
        return json.dumps(result, ensure_ascii=False, indent=2)

    # ──────────────────────── Méthodes de persistance ────────────────────────

    def _persist_result(self, result: dict, result_type: str) -> None:
        """
        Sauvegarde le résultat dans output/planner/results/<type>_<timestamp>.json
        via le MetricsLogger centralisé.
        """
        try:
            filepath = metrics_logger.log_result(
                agent_name=self.name,
                result_data=result,
                result_type=result_type,
            )
            self.logger.info(f"Résultat '{result_type}' sauvegardé → {filepath}")
        except Exception as e:
            self.logger.error(f"Échec sauvegarde résultat '{result_type}': {e}")

    def _persist_metrics(
        self,
        processing_time: float,
        analysis_time: float,
        generation_time: float,
        num_steps: int,
    ) -> None:
        """
        Sauvegarde les métriques dans output/planner/metrics/ via SystemMetricsCollector,
        et enregistre les métriques individuelles dans le log centralisé.
        """
        try:
            combined = self.get_planner_metrics()

            # 1. Enregistrement dans le collecteur système (pour le rapport global)
            _system_collector.record_agent_metrics(self.name, combined)

            # 2. Sauvegarde dans output/planner/metrics/<planner>_metrics_<id>.json
            _system_collector.save_agent_metrics(self.name, combined)

            # 3. Métriques individuelles dans le log centralisé
            metrics_logger.log_metric(self.name, "processing_time_seconds", processing_time)
            metrics_logger.log_metric(self.name, "analysis_time_seconds", analysis_time)
            metrics_logger.log_metric(self.name, "generation_time_seconds", generation_time)
            metrics_logger.log_metric(self.name, "num_steps_generated", num_steps)
            metrics_logger.log_metric(
                self.name,
                "plans_generated_total",
                self._planner_metrics["plans_generated"],
            )
            metrics_logger.log_metric(
                self.name,
                "avg_plan_steps",
                self._planner_metrics["avg_plan_steps"],
            )
            metrics_logger.log_metric(
                self.name,
                "user_validation_score",
                self._planner_metrics["user_validation_score"],
            )

            self.logger.info("Métriques Planner sauvegardées")
        except Exception as e:
            self.logger.error(f"Échec sauvegarde métriques Planner: {e}")

    # ──────────────────────── Phases LLM ─────────────────────────────────────

    async def _understand_need(self, user_input: str) -> dict:
        """Phase 1 : Comprendre le besoin utilisateur via CoT."""
        prompt = UNDERSTAND_NEED_PROMPT.format(user_input=user_input)

        response = await self.call_llm([
            {
                "role": "system",
                "content": (
                    "Tu es un expert en analyse des besoins. "
                    "Utilise le raisonnement Chain-of-Thought pour analyser en profondeur. "
                    "Réponds uniquement en JSON valide."
                ),
            },
            {"role": "user", "content": prompt},
        ])

        return self._parse_json_response(response)

    async def _generate_plan(self, need_analysis: dict) -> dict:
        """Phase 2 : Générer le plan d'exécution via CoT."""
        available_agents = json.dumps(
            registry.get_agents_summary(), ensure_ascii=False
        )

        prompt = GENERATE_PLAN_PROMPT.format(
            need_analysis=json.dumps(need_analysis, ensure_ascii=False),
            available_agents=available_agents,
        )

        response = await self.call_llm([
            {
                "role": "system",
                "content": (
                    "Tu es un expert en planification de projets. "
                    "Utilise le raisonnement Chain-of-Thought pour décomposer le travail. "
                    "Réponds uniquement en JSON valide."
                ),
            },
            {"role": "user", "content": prompt},
        ])

        return self._parse_json_response(response)

    async def refine_plan(self, current_plan: dict, feedback: str) -> dict:
        """Raffine un plan existant en fonction du feedback."""
        prompt = REFINE_PLAN_PROMPT.format(
            current_plan=json.dumps(current_plan, ensure_ascii=False),
            feedback=feedback,
        )

        response = await self.call_llm([
            {
                "role": "system",
                "content": (
                    "Tu es un expert en planification. "
                    "Affine le plan selon le feedback. "
                    "Réponds uniquement en JSON valide."
                ),
            },
            {"role": "user", "content": prompt},
        ])

        result = self._parse_json_response(response)
        self._planner_metrics["plans_refined"] += 1

        # ── PERSISTANCE du plan raffiné ───────────────────────────────────
        self._persist_result(result, result_type="plan_refined")

        return result

    # ──────────────────────── Métriques ──────────────────────────────────────

    def get_planner_metrics(self) -> dict[str, Any]:
        """Retourne les métriques combinées (base + planner)."""
        base = self.get_metrics()
        return {**base, **self._planner_metrics}

    def _parse_json_response(self, response: str) -> dict:
        """Parse une réponse JSON du LLM."""
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

_planner_instance = None


def get_planner_instance() -> PlannerAgent:
    """Retourne l'instance singleton du Planner."""
    global _planner_instance
    if _planner_instance is None:
        _planner_instance = PlannerAgent()
    return _planner_instance


def get_agent_config() -> AgentConfig:
    """Retourne la configuration de l'agent pour le registre dynamique."""
    planner = get_planner_instance()
    return AgentConfig(
        name=planner.name,
        description=planner.description,
        handler=planner.run,
        capabilities=planner.capabilities,
        input_content_types=["text/plain", "application/json"],
        output_content_types=["text/plain", "application/json"],
    )