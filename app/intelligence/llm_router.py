import re
import json
from typing import Optional, Dict, Any
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from app.config import config

class OutreachGenerationOutput(BaseModel):
    decision: str = Field(description="SEND or NOT_TO_SEND")
    framework: str = Field(description="Selected framework name")
    subject: str = Field(description="Direct, personalized email subject line")
    body: str = Field(description="Concise body text under 120 words")
    reason: str = Field(description="Justification for outreach")
    relevance_score: int = Field(default=50, description="1 to 100 score")

class LLMRouter:
    def __init__(self):
        self.nvidia_client = AsyncOpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=config.nvidia_api_key
        ) if config.nvidia_api_key else None
        
        self.openrouter_client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=config.openrouter_api_key
        ) if config.openrouter_api_key else None

    @staticmethod
    def clean_output(text: str) -> str:
        if not text:
            return ""
        # Strip thinking tags and process lines
        text = re.sub(r"(?i)<think>.*?</think>", "", text, flags=re.DOTALL)
        text = re.sub(r"(?i)Here'?s a thinking process:.*?\n\n", "", text, flags=re.DOTALL)
        
        # If wrapped in markdown code blocks
        if "```" in text:
            # Extract json or text inside block
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
            if match:
                text = match.group(1)
        return text.strip()

    async def complete(self, prompt: str, system_prompt: str = "", temperature: float = 0.2, max_tokens: int = 1024) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        # Try OpenRouter first if configured
        if self.openrouter_client:
            try:
                resp = await self.openrouter_client.chat.completions.create(
                    model=config.openrouter_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                return self.clean_output(resp.choices[0].message.content)
            except Exception as e:
                print(f"[LLMRouter] OpenRouter failed ({e}). Falling back to Nvidia NIM...")
                
        # Primary / Fallback: Nvidia NIM
        if self.nvidia_client:
            resp = await self.nvidia_client.chat.completions.create(
                model=config.nvidia_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}}
            )
            return self.clean_output(resp.choices[0].message.content)
            
        raise ValueError("No LLM client configured (both NVIDIA_API_KEY and OPENROUTER_API_KEY are missing).")

llm_router = LLMRouter()
