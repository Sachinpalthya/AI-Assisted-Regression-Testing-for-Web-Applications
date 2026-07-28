"""
utils/ollama_client.py — Wrapper around the Ollama Python SDK.

Provides:
  - chat()       : multi-turn chat with streaming support
  - generate()   : single-turn generation
  - get_embedding(): get vector embeddings for text
  - is_available(): health-check against the local Ollama server
"""

import ollama
import logging
from typing import Generator

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config

logger = logging.getLogger(__name__)


def is_available() -> bool:
    """Return True if Ollama is running and the configured model exists."""
    try:
        models = ollama.list()
        print(models)
        available = []
        # Support both new ListResponse/Model objects and old dictionary list structures
        model_list = getattr(models, 'models', None) or models.get('models', [])
        for m in model_list:
            name = getattr(m, 'model', None) or (m.get('model') if hasattr(m, 'get') else None) or getattr(m, 'name', None) or (m.get('name') if hasattr(m, 'get') else None)
            if name:
                available.append(name.split(":")[0])
        
        model_base = config.OLLAMA_MODEL.split(":")[0]
        if model_base not in available:
            logger.warning(
                f"Model '{config.OLLAMA_MODEL}' not found in Ollama. "
                f"Available: {available}. "
                f"Run: ollama pull {config.OLLAMA_MODEL}"
            )
            return False
        return True
    except Exception as e:
        logger.error(f"Ollama not reachable at {config.OLLAMA_HOST}: {e}")
        return False


def chat(
    messages: list[dict],
    model: str | None = None,
    stream: bool = True,
) -> str:
    """
    Send a list of messages to Ollama and return the full response text.

    Args:
        messages: List of {"role": "user"|"assistant"|"system", "content": str}
        model:    Override default model from config
        stream:   If True, streams tokens and prints progress dots to stderr

    Returns:
        Full response string
    """
    model = model or config.OLLAMA_MODEL
    full_response = []

    try:
        response = ollama.chat(
            model=model,
            messages=messages,
            stream=stream,
        )

        if stream:
            for chunk in response:
                token = chunk["message"]["content"]
                full_response.append(token)
                print(".", end="", flush=True)
            print()  # newline after streaming dots
        else:
            full_response.append(response["message"]["content"])

    except ollama.ResponseError as e:
        logger.error(f"Ollama ResponseError: {e}")
        raise
    except Exception as e:
        logger.error(f"Ollama chat error: {e}")
        raise

    return "".join(full_response)


def generate(
    prompt: str,
    model: str | None = None,
    stream: bool = True,
) -> str:
    """
    Single-turn generation — simpler than chat(), no history needed.

    Args:
        prompt: The raw prompt string
        model:  Override default model from config
        stream: Stream tokens to reduce timeout risk

    Returns:
        Full generated string
    """
    return chat(
        messages=[{"role": "user", "content": prompt}],
        model=model,
        stream=stream,
    )

def get_embedding(
    text: str,
    model: str | None = None,
) -> list[float]:
    """
    Get embeddings for the provided text using Ollama.
    """
    model = model or getattr(config, 'OLLAMA_EMBED_MODEL', config.OLLAMA_MODEL)
    try:
        response = ollama.embeddings(
            model=model,
            prompt=text,
        )
        return response["embedding"]
    except Exception as e:
        logger.error(f"Ollama embeddings error: {e}")
        raise
