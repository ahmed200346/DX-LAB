"""
agents/memory_agent.py (minimal, no deprecated LangChain memory)
"""

import json
import os
from typing import Any, Dict, List, Optional

from rich.console import Console
from utils.llm import get_hypothesis_llm

console = Console()

FOLLOW_UP_SYSTEM = (
    "You are a research assistant with memory of an ongoing scientific analysis session. "
    "Use the stored context and conversation history to answer helpfully."
)


class MemoryAgent:
    def __init__(self, history_size: int = 6):
        self._llm = get_hypothesis_llm()
        self._history: List[Dict[str, str]] = []  # list of {role, content}
        self._query = ""
        self._summary = ""
        self._history_size = history_size

    def store_pipeline_result(self, result: Dict[str, Any]) -> None:
        self._query = result.get("query", "")
        hypotheses = result.get("hypotheses_ranked", result.get("hypotheses", []))
        hyp_text = "\n".join(
            f"H{h.get('index', i+1)}: {h.get('statement', '')}"
            for i, h in enumerate(hypotheses)
        )
        gaps = result.get("gaps", "")
        conflicts = result.get("conflicts", "")
        self._summary = (
            f"I completed a full literature analysis on '{self._query}'.\n\n"
            f"HYPOTHESES GENERATED:\n{hyp_text}\n\n"
            f"KEY GAPS:\n{gaps[:600]}\n\n"
            f"CONFLICTS DETECTED:\n{conflicts[:400]}"
        )
        # Initialize history with a system-like message
        self._history = [
            {"role": "system", "content": FOLLOW_UP_SYSTEM},
            {"role": "assistant", "content": self._summary},
        ]
        console.print("\n[dim]Memory agent ready — you can now ask follow-up questions.[/dim]")

    def follow_up(self, user_request: str) -> str:
        # Build prompt from limited history (keep last N exchanges)
        recent = self._history[-self._history_size * 2 :]  # each exchange = 2 messages
        # Construct a chat prompt for the LLM (Ollama format)
        messages = recent + [{"role": "user", "content": user_request}]
        # Combine into a single string (Ollama chat format via langchain-ollama? 
        # Our llm wrapper expects a prompt string, so we'll format manually)
        prompt = self._format_chat_prompt(messages)

        try:
            response = self._llm.invoke(prompt)
            result = response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            result = f"Follow-up failed: {e}"

        # Save exchange
        self._history.append({"role": "user", "content": user_request})
        self._history.append({"role": "assistant", "content": result})
        return result

    def _format_chat_prompt(self, messages: List[Dict[str, str]]) -> str:
        """Convert list of role/content messages to a single prompt string."""
        # Use a simple format that local models understand.
        lines = []
        for m in messages:
            role = m["role"]
            content = m["content"]
            if role == "system":
                lines.append(f"<|system|>\n{content}")
            elif role == "user":
                lines.append(f"<|user|>\n{content}")
            elif role == "assistant":
                lines.append(f"<|assistant|>\n{content}")
        lines.append("<|assistant|>")
        return "\n".join(lines)

    def save_session(self, filepath: str) -> None:
        data = {"query": self._query, "history": self._history}
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        console.print(f"[dim]Session saved to {filepath}[/]")

    def load_session(self, filepath: str) -> None:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._query = data["query"]
        self._history = data["history"]
        console.print(f"[dim]Session resumed from {filepath}[/]")

    def interactive_session(self) -> None:
        console.print(
            "\n[bold cyan]Interactive Mode[/] — ask follow-up questions about the analysis."
        )
        console.print("[dim]Type 'exit' to quit, 'clear' to reset memory, 'save [path]' to persist.[/dim]\n")
        while True:
            try:
                user_input = input("You: ").strip()
            except (KeyboardInterrupt, EOFError):
                break
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "q"):
                break
            if user_input.lower() == "clear":
                self._history = self._history[:2]  # keep system+summary
                console.print("[dim]Memory cleared.[/dim]")
                continue
            if user_input.lower().startswith("save"):
                parts = user_input.split(maxsplit=1)
                path = parts[1] if len(parts) > 1 else "session.json"
                self.save_session(path)
                continue
            response = self.follow_up(user_input)
            console.print(f"\n[green]Assistant:[/] {response}\n")