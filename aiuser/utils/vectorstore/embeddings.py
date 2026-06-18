import logging
import shutil
from pathlib import Path

import numpy as np
import tiktoken
from fastembed import TextEmbedding
from fastembed.common.types import NumpyArray

from aiuser.config.constants import (
    EMBEDDING_CACHE_DIR_NAME,
    EMBEDDING_MODEL,
    FALLBACK_TOKENIZER,
)
from aiuser.utils.utilities import encode_text_to_tokens, to_thread

logger = logging.getLogger("red.bz_cogs.aiuser.memory")

CACHE_ERROR_TERMS = (
    "cache",
    "config.json",
    "corrupt",
    "download",
    "load model",
    "model.onnx",
    "snapshot",
    "special_tokens_map.json",
    "tokenizer.json",
)


async def embed_text(text: str, cache_folder: str) -> NumpyArray:
    token_count = await encode_text_to_tokens(text)
    if token_count > 500:
        text = await truncate_text_to_tokens(text, FALLBACK_TOKENIZER)
    try:
        embedding = await embed_sync(text, cache_folder)
    except Exception as exc:
        if not _is_probable_cache_error(exc):
            raise

        logger.warning(
            "FastEmbed cache appears invalid; clearing cache and retrying once",
            exc_info=True,
        )
        await clear_embedding_cache(cache_folder)
        embedding = await embed_sync(text, cache_folder)
    return np.array(embedding, dtype=np.float32)


@to_thread()
def embed_sync(text: str, cache_folder: str) -> NumpyArray:
    model = TextEmbedding(EMBEDDING_MODEL, cache_dir=cache_folder)
    res = model.embed([text])
    return next(iter(res))


def _is_probable_cache_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(term in message for term in CACHE_ERROR_TERMS)


@to_thread()
def clear_embedding_cache(cache_folder: str) -> None:
    cache_path = Path(cache_folder)
    if cache_path.name != EMBEDDING_CACHE_DIR_NAME:
        raise RuntimeError(f"Refusing to clear unexpected cache path: {cache_path}")
    if cache_path.is_symlink():
        cache_path.unlink()
    elif cache_path.exists():
        shutil.rmtree(cache_path)


@to_thread()
def truncate_text_to_tokens(text: str, max_tokens: int = 450) -> str:
    encoding = tiktoken.get_encoding(FALLBACK_TOKENIZER)
    tokens = encoding.encode(text)[:max_tokens]
    return encoding.decode(tokens)
