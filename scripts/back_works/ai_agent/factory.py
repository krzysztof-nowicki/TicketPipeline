from scripts.config import get_settings
from scripts.back_works.ai_agent.base import LLMService
from scripts.back_works.ai_agent.fake_llm import FakeLLMService
from scripts.back_works.ai_agent.local_agent import LocalLLMService
from scripts.back_works.ai_agent.openai_agent import OpenAILLMService


def get_llm_service() -> LLMService:
    settings = get_settings()
    mode = settings.LLM_MODE.lower()
    if mode in ("local", "local_llm", "ollama", "llama_cpp", "llamacpp"):
        return LocalLLMService(settings=settings)
    if mode == "openai":
        return OpenAILLMService()
    return FakeLLMService()
