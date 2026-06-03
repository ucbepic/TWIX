import os

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import AzureChatOpenAI


def get_model() -> BaseChatModel:
    """Return an AzureChatOpenAI model bound to the configured deployment.

    Required environment variables:
        AZURE_ENDPOINT                 – Resource endpoint, e.g. https://<resource>.openai.azure.com/
        AZURE_OPENAI_API_KEY           – Azure OpenAI API key.
        AZURE_OPENAI_DEPLOYMENT_NAME   – Deployment name (default: gpt-5.4-mini).
    """
    return AzureChatOpenAI(
        azure_endpoint=os.environ["AZURE_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        azure_deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-5.4"),
        openai_api_version="2024-12-01-preview",
        temperature=0,
    )
