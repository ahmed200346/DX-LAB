from typing import Optional

from langchain.agents import initialize_agent, AgentType
from langchain.callbacks import get_openai_callback
from langchain.memory import ConversationBufferMemory
from DiscoveryAgent.prompts.base_template import PREFIX, FORMAT_INSTRUCTIONS, SUFFIX
from DiscoveryAgent.llm import chat_llm
import os
from configs.secret_keys import serper_api_key
import warnings
warnings.filterwarnings('ignore')


os.environ["SERPER_API_KEY"] = serper_api_key


class DiscoveryAgent:
    def __init__(
        self,
        tools,
        model=None,
        temp=0.1,
        agent_type=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        max_iterations=100,
        max_execution_time: Optional[float] = None,
        **kwargs
    ):
        self.tools = tools
        self.suffix = kwargs.get('suffix',
                                 SUFFIX.format(tool_desc="{tool_desc}",
                                        input="{input}",
                                        agent_scratchpad="{agent_scratchpad}"))
        self.prefix = kwargs.get('prefix')
        self.format_instructions = kwargs.get('format_instructions',
                                              FORMAT_INSTRUCTIONS.format(tool_names="{tool_names}"))
        self.callbacks = kwargs.get('callbacks', None)

        self.model = chat_llm(model=model, temperature=temp)

        # Conversation buffer only. VectorStoreRetrieverMemory + NVIDIA embeddings
        # caused NIM HTTP 500s ("'list' object has no attribute 'strip'") on agent runs.
        memory = ConversationBufferMemory(
            memory_key="chat_history",
            input_key="input",
            output_key="output",
            return_messages=True,
        )

        executor_kwargs: dict = {
            "tools": self.tools,
            "llm": self.model,
            "agent": agent_type,
            "verbose": True,
            "memory": memory,
            "handle_parsing_errors": True,
            "max_iterations": max_iterations,
            "agent_kwargs": {
                "system_message": """You are an expert drug discovery AI assistant. You must:
                    1. Always check chat history before responding
                    2. Use information from previous messages (like names, preferences, or context)
                    3. Maintain consistent knowledge of previous interactions
                    4. Never reintroduce yourself if you've already done so""",
                "prefix": self.prefix,
                "suffix": self.suffix,
                "format_instructions": self.format_instructions,
                "input_variables": [
                    "input",
                    "agent_scratchpad",
                    "chat_history",
                ],
            },
            "return_intermediate_steps": True,
            "callbacks": self.callbacks,
        }
        if max_execution_time is not None:
            executor_kwargs["max_execution_time"] = max_execution_time

        self.agent = initialize_agent(**executor_kwargs)

    def __call__(self, prompt):
        tool_desc = [tool.description for tool in self.tools]
        try:
            with get_openai_callback() as cb:
                result = self.agent.invoke({"input": prompt, "tool_desc": tool_desc})
        except Exception:
            result = self.agent.invoke({"input": prompt, "tool_desc": tool_desc})
        return result
