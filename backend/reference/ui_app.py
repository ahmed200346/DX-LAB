"""
Interface utilisateur (UI) basée sur Gradio pour interagir avec l'agent Planner.
Permet :
1. De discuter avec le Planner (Génération de plan, clarification, raffinement, validation).
2. De visualiser les métriques de performance des agents.
"""

import gradio as gr
import json
import httpx
import os
import glob
import asyncio
from pathlib import Path
from acp_sdk.client import Client
from acp_sdk.models import Message, MessagePart
from settings.config import ACP_SERVER_URL

# Configuration du serveur ACP
#ACP_SERVER_URL = "http://127.0.0.1:8000"

async def _call_acp_agent(agent_name: str, payload_str: str) -> str:
    """Appelle le serveur ACP via le SDK officiel."""
    async with Client(base_url=ACP_SERVER_URL, timeout=60.0) as client:
        run = await client.run_sync(
            agent=agent_name,
            input=[
                Message(
                    parts=[MessagePart(content=payload_str, content_type="text/plain")]
                )
            ],
        )
        
        output_content = ""
        for msg in run.output:
            for part in msg.parts:
                if hasattr(part, "content") and isinstance(part.content, str):
                    output_content += part.content + "\n"
        return output_content

async def send_to_planner(message: str, state: dict) -> tuple[str, dict]:
    """
    Communique avec le serveur ACP (agent planner) en utilisant un dictionnaire d'état
    pour déterminer l'action en cours.
    """
    if state is None:
        state = {"awaiting_action": None, "analysis": {}, "plan": {}}

    payload = {}
    
    if state["awaiting_action"] == "clarification":
        payload = {
            "action": "clarification_response",
            "analysis": state["analysis"],
            "answers": message
        }
    elif state["awaiting_action"] == "validation":
        # Check if the user is providing a score (1-5) to validate or feedback to refine
        try:
            score = int(message.strip())
            if 1 <= score <= 5:
                payload = {
                    "action": "validate_plan",
                    "score": score
                }
            else:
                payload = {
                    "action": "refine_plan",
                    "current_plan": state["plan"],
                    "feedback": message
                }
        except ValueError:
            # Not an integer, treat as feedback for refinement
            payload = {
                "action": "refine_plan",
                "current_plan": state["plan"],
                "feedback": message
            }
    else:
        payload = {
            "action": "new",
            "query": message
        }

    # Appel au serveur ACP via le SDK
    try:
        output_content = await _call_acp_agent("planner", json.dumps(payload))
        
        # Le output_content est un JSON renvoyé par le planner_agent
        try:
            result = json.loads(output_content)
            status = result.get("status")
            
            if status == "needs_clarification":
                state["awaiting_action"] = "clarification"
                state["analysis"] = result.get("analysis", {})
                
                questions = result.get("questions", [])
                response_text = "J'ai besoin de clarifications pour générer ce plan :\n\n"
                for i, q in enumerate(questions, 1):
                    response_text += f"{i}. {q}\n"
                response_text += "\n*Veuillez répondre à ces questions pour continuer.*"
                
                return response_text, state

            elif status == "plan_generated":
                state["awaiting_action"] = "validation"
                plan = result.get("plan", {})
                state["plan"] = plan
                
                response_text = f"**Plan généré avec succès : {plan.get('plan_title', 'Sans Títre')}**\n\n"
                response_text += plan.get('plan_description', '') + "\n\n"
                for step in plan.get('steps', []):
                    response_text += f"**Étape {step.get('step_id', '?')}**: {step.get('title', '')} (Agent: {step.get('target_agent', '')})\n"
                    response_text += f"- {step.get('description', '')}\n"
                
                response_text += "\n*Pour valider le plan, entrez une note entre 1 et 5.*\n"
                response_text += "*Pour modifier le plan, écrivez simplement vos remarques ou modifications souhaitées.*"
                
                return response_text, state

            elif status == "plan_validated":
                state["awaiting_action"] = None
                return f"✅ **Plan validé avec une note de {result.get('score', 5)}/5!** Il est prêt pour l'exécution par l'Executor.\n*(Vous pouvez formuler un autre besoin)*", state
            
            elif status == "error":
                return f"❌ Une erreur est survenue lors de la planification : {result.get('error')}", state

            else:
                return f"Réponse inattendue : {output_content}", state

        except json.JSONDecodeError:
            # Fallback for plain text responses
            return output_content, state

    except Exception as e:
        return f"Erreur de communication avec le serveur ACP : {str(e)}\n\nAssurez-vous que le serveur est démarré (`python main.py`).", state

async def chat_interface(user_message, history, state):
    """Fonction principale pour l'interface de chat."""
    bot_response, new_state = await send_to_planner(user_message, state)
    history.append((user_message, bot_response))
    return "", history, new_state

def get_latest_metrics(agent_name: str) -> str:
    """Récupère et formatte les dernières métriques d'un agent."""
    metrics_pattern = f"output/{agent_name}/metrics/{agent_name}_metrics_*.json"
    files = glob.glob(metrics_pattern)
    if not files:
        return f"Aucune métrique trouvée pour l'agent '{agent_name}'."
    
    # Prendre le fichier le plus récent
    latest_file = max(files, key=os.path.getctime)
    
    try:
        with open(latest_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Formatting as pretty JSON or specific markdown
            markdown = f"### Dernières métriques ({Path(latest_file).name})\n\n"
            
            markdown += "#### Performance & Fiabilité\n"
            markdown += f"- **Requêtes totales:** {data.get('total_requests', 0)}\n"
            markdown += f"- **Requêtes réussies:** {data.get('successful_requests', 0)}\n"
            markdown += f"- **Temps moyen de traitement:** {data.get('avg_processing_time', 0):.2f}s\n"
            markdown += f"- **Erreurs:** {data.get('error_count', 0)}\n\n"
            
            if agent_name == "planner":
                markdown += "#### Statistiques d'Analyse (Planner)\n"
                markdown += f"- **Plans générés:** {data.get('plans_generated', 0)}\n"
                markdown += f"- **Plans raffinés:** {data.get('plans_refined', 0)}\n"
                markdown += f"- **Clarifications requises:** {data.get('clarifications_needed', 0)}\n"
                markdown += f"- **Temps moyen d'analyse:** {data.get('avg_analysis_time', 0):.2f}s\n"
                markdown += f"- **Moyenne d'étapes par plan:** {data.get('avg_plan_steps', 0):.2f}\n"
                markdown += f"- **Validations Utilisateur réussies:** {data.get('successful_validations', 0)}\n"
                markdown += f"- **Note moyenne utilisateur:** {data.get('user_validation_score', 0):.2f}/5\n"
            
            return markdown
    except Exception as e:
        return f"Erreur de lecture des métriques: {e}"

def refresh_metrics():
    """Rafraîchit les affichages des métriques."""
    return get_latest_metrics("planner"), get_latest_metrics("executor")

# ─── Configuration de l'Interface Gradio ───────────────────────────────────────

with gr.Blocks(title="Système Multi-Agent PI - Dashboard", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🤖 Architecture Multi-Agent (Protocole ACP)")
    
    state = gr.State(value={"awaiting_action": None, "analysis": {}, "plan": {}})
    
    with gr.Tabs():
        # Onglet 1 : Espace utilisateur / Planner
        with gr.Tab("Interaction Planner"):
            gr.Markdown("### Discuter avec l'Agent Planner\nExprimez votre besoin, répondez aux éventuelles questions de clarification, puis validez ou modifiez le plan généré.")
            
            chatbot = gr.Chatbot(height=500, label="Dialogue avec Planner")
            msg = gr.Textbox(placeholder="Ex: Je souhaite analyser les performances du système...", label="Votre Message")
            clear = gr.Button("Effacer la conversation")
            
            msg.submit(chat_interface, [msg, chatbot, state], [msg, chatbot, state])
            
            def clear_chat():
                return [], {"awaiting_action": None, "analysis": {}, "plan": {}}
                
            clear.click(clear_chat, inputs=None, outputs=[chatbot, state])
            
        # Onglet 2 : Dashboard des Métriques
        with gr.Tab("Dashboard Métriques (Performances)"):
            gr.Markdown("### 📊 Scores & Performances des Agents")
            refresh_btn = gr.Button("Rafraîchir les métriques 🔄")
            
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### 🧠 Agent Planner")
                    planner_metrics_display = gr.Markdown("*(Cliquez sur Rafraîchir)*")
                with gr.Column():
                    gr.Markdown("### ⚙️ Agent Executor")
                    executor_metrics_display = gr.Markdown("*(Cliquez sur Rafraîchir)*")
                    
            refresh_btn.click(refresh_metrics, inputs=None, outputs=[planner_metrics_display, executor_metrics_display])
            demo.load(refresh_metrics, inputs=None, outputs=[planner_metrics_display, executor_metrics_display])

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860, share=False)
