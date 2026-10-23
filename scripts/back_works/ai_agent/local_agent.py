from typing import Optional
from scripts.config import Settings, get_settings
from scripts.back_works.ai_agent.openai_agent import OpenAILLMService


class LocalLLMService(OpenAILLMService):
    """
    Local LLM service connecting to an OpenAI-compatible local server
    such as llama.cpp (llama-server) or Ollama.
    Methods are inherited from OpenAILLMService, but load is local.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        settings: Optional[Settings] = None,
    ):
        cfg = settings or get_settings()
        target_url = (base_url or cfg.LOCAL_SERVER_URL).rstrip("/")
        if not target_url.endswith("/v1"):
            target_url = f"{target_url}/v1"

        super().__init__(
            base_url=target_url,
            api_key=api_key or cfg.LOCAL_LLM_API_KEY,
            model=model or cfg.LOCAL_LLM_MODEL,
        )
