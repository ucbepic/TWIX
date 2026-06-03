import os

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI


def get_model() -> BaseChatModel:
    """Return a vision-capable OpenAI chat model.

    Reads:
        OPENAI_API_KEY  – required, set in the environment.
        OPENAI_MODEL    – optional, defaults to "gpt-4o".
    """
    return ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-5.4"),
        temperature=0,
    )
