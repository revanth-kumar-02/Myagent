import os
import json
import httpx
from abc import ABC, abstractmethod
from typing import Dict, Any, Type, TypeVar, Optional
from pydantic import BaseModel
from config import settings

T = TypeVar("T", bound=BaseModel)

class LLMProviderError(Exception):
    pass

class LLMTimeoutError(LLMProviderError):
    pass

class LLMRateLimitError(LLMProviderError):
    pass

class BaseLLMProvider(ABC):
    @abstractmethod
    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        pass

    @abstractmethod
    async def generate_structured(self, prompt: str, schema: Type[T], system_prompt: Optional[str] = None) -> T:
        pass

class GroqProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile"):
        self.api_key = api_key
        self.model = model
        self.endpoint = "https://api.groq.com/openai/v1/chat/completions"

    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                res = await client.post(self.endpoint, headers=headers, json=payload)
                if res.status_code == 429:
                    raise LLMRateLimitError("Groq API rate limit exceeded")
                if res.status_code != 200:
                    raise LLMProviderError(f"Groq API error {res.status_code}: {res.text}")
                data = res.json()
                return data["choices"][0]["message"]["content"]
            except httpx.TimeoutException:
                raise LLMTimeoutError("Groq API request timed out")
            except httpx.RequestError as e:
                raise LLMProviderError(f"Groq connection error: {str(e)}")

    async def generate_structured(self, prompt: str, schema: Type[T], system_prompt: Optional[str] = None) -> T:
        schema_json = json.dumps(schema.model_json_schema())
        struct_prompt = (
            f"{prompt}\n\n"
            f"You MUST respond ONLY with a valid JSON object strictly matching this JSON schema:\n"
            f"{schema_json}\n"
            f"Do NOT include markdown block formatting, extra text, or explanations."
        )
        raw_res = await self.generate_text(struct_prompt, system_prompt)
        cleaned = raw_res.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        try:
            parsed = json.loads(cleaned)
            return schema.model_validate(parsed)
        except Exception as e:
            raise LLMProviderError(f"Failed to parse structured response into schema {schema.__name__}: {str(e)}. Response: {cleaned}")

class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.api_key = api_key
        self.model = model
        self.endpoint = "https://api.openai.com/v1/chat/completions"

    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                res = await client.post(self.endpoint, headers=headers, json=payload)
                if res.status_code == 429:
                    raise LLMRateLimitError("OpenAI API rate limit exceeded")
                if res.status_code != 200:
                    raise LLMProviderError(f"OpenAI API error {res.status_code}: {res.text}")
                data = res.json()
                return data["choices"][0]["message"]["content"]
            except httpx.TimeoutException:
                raise LLMTimeoutError("OpenAI API request timed out")
            except httpx.RequestError as e:
                raise LLMProviderError(f"OpenAI connection error: {str(e)}")

    async def generate_structured(self, prompt: str, schema: Type[T], system_prompt: Optional[str] = None) -> T:
        schema_json = json.dumps(schema.model_json_schema())
        struct_prompt = (
            f"{prompt}\n\n"
            f"You MUST respond ONLY with a valid JSON object matching this schema:\n"
            f"{schema_json}"
        )
        raw_res = await self.generate_text(struct_prompt, system_prompt)
        cleaned = raw_res.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        parsed = json.loads(cleaned)
        return schema.model_validate(parsed)

class GeminiProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str = "gemini-1.5-pro"):
        self.api_key = api_key
        self.model = model
        self.endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"

    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": f"System Instruction: {system_prompt}"}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        payload = {"contents": contents}

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                res = await client.post(self.endpoint, json=payload)
                if res.status_code == 429:
                    raise LLMRateLimitError("Gemini API rate limit exceeded")
                if res.status_code != 200:
                    raise LLMProviderError(f"Gemini API error {res.status_code}: {res.text}")
                data = res.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
            except httpx.TimeoutException:
                raise LLMTimeoutError("Gemini API request timed out")
            except httpx.RequestError as e:
                raise LLMProviderError(f"Gemini connection error: {str(e)}")

    async def generate_structured(self, prompt: str, schema: Type[T], system_prompt: Optional[str] = None) -> T:
        schema_json = json.dumps(schema.model_json_schema())
        struct_prompt = (
            f"{prompt}\n\nRespond ONLY with a valid JSON object matching this schema:\n{schema_json}"
        )
        raw_res = await self.generate_text(struct_prompt, system_prompt)
        cleaned = raw_res.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        parsed = json.loads(cleaned)
        return schema.model_validate(parsed)

class RuleBasedLLMProvider(BaseLLMProvider):
    """Local rule-based fallback provider when no remote API key is supplied."""
    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        return f"RuleBasedLLM response for prompt: {prompt[:100]}..."

    async def generate_structured(self, prompt: str, schema: Type[T], system_prompt: Optional[str] = None) -> T:
        # Dynamically build a valid mock instance based on schema field types
        fields = schema.model_fields
        mock_data: Dict[str, Any] = {}
        for f_name, f_info in fields.items():
            if f_name == "goal":
                mock_data["goal"] = prompt[:100]
            elif f_name == "steps":
                mock_data["steps"] = [
                    {
                        "id": "step_1",
                        "title": "Analyze user request and gather context",
                        "description": "Examine requirements and identify initial targets",
                        "tool": "web_search",
                        "status": "pending"
                    },
                    {
                        "id": "step_2",
                        "title": "Inspect filesystem resources",
                        "description": "Read project directory and verify local files",
                        "tool": "filesystem",
                        "status": "pending"
                    },
                    {
                        "id": "step_3",
                        "title": "Synthesize results and verify goal completion",
                        "description": "Formulate final findings and verify requirements",
                        "tool": "browser",
                        "status": "pending"
                    }
                ]
            elif f_name == "success":
                mock_data["success"] = True
            elif f_name == "reason":
                mock_data["reason"] = "All step objectives verified and completed successfully."
            elif f_name == "needs_retry":
                mock_data["needs_retry"] = False
            else:
                mock_data[f_name] = "default_value"
        return schema.model_validate(mock_data)

class LLMProviderGateway:
    _instance: Optional[BaseLLMProvider] = None

    @classmethod
    def get_provider(cls, provider_type: Optional[str] = None, api_key: Optional[str] = None, model: Optional[str] = None) -> BaseLLMProvider:
        p_type = (provider_type or os.getenv("LLM_PROVIDER") or settings.LLM_PROVIDER).lower()
        key = api_key or os.getenv("LLM_API_KEY") or os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY") or settings.LLM_API_KEY
        m_name = model or os.getenv("LLM_MODEL") or settings.LLM_MODEL

        if not key or key == "none" or key == "sk-placeholder":
            return RuleBasedLLMProvider()

        if p_type == "groq":
            return GroqProvider(api_key=key, model=m_name or "llama-3.3-70b-versatile")
        elif p_type == "openai":
            return OpenAIProvider(api_key=key, model=m_name or "gpt-4o")
        elif p_type == "gemini":
            return GeminiProvider(api_key=key, model=m_name or "gemini-1.5-pro")
        else:
            return RuleBasedLLMProvider()
