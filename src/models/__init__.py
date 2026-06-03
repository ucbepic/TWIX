import os

from langchain_core.language_models.chat_models import BaseChatModel

_PROVIDERS: dict[str, str] = {
    "openai": "src.models.openai",
    "azure":  "src.models.azure",
}


def get_llm() -> BaseChatModel:
    """Instantiate the LLM for the provider named in LLM_PROVIDER (default: openai).

    To add a new provider:
        1. Create src/models/<provider>.py with a get_model() -> BaseChatModel function.
        2. Add an entry to _PROVIDERS above.
    """
    provider = os.getenv("LLM_PROVIDER", "openai").lower()

    if provider not in _PROVIDERS:
        raise ValueError(
            f"Unknown LLM provider '{provider}'. "
            f"Available: {', '.join(_PROVIDERS)}"
        )

    module_path = _PROVIDERS[provider]
    import importlib
    module = importlib.import_module(module_path)
    return module.get_model()
