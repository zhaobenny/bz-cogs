import shutil
import threading
from pathlib import Path
from typing import Dict

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

# loading the ONNX model takes seconds, so keep one instance per cache folder
_models: Dict[str, TextEmbedding] = {}
_models_lock = threading.Lock()


def _get_model(cache_folder: str) -> TextEmbedding:
    with _models_lock:
        model = _models.get(cache_folder)
        if model is None:
            model = TextEmbedding(EMBEDDING_MODEL, cache_dir=cache_folder)
            _models[cache_folder] = model
        return model


async def embed_text(text: str, cache_folder: str) -> NumpyArray:
    token_count = await encode_text_to_tokens(text)
    if token_count > 500:
        text = await truncate_text_to_tokens(text, FALLBACK_TOKENIZER)
    embedding = await embed_sync(text, cache_folder)
    return np.array(embedding, dtype=np.float32)


@to_thread()
def embed_sync(text: str, cache_folder: str) -> NumpyArray:
    try:
        model = _get_model(cache_folder)
        res = model.embed([text])
        return next(iter(res))
    except (OSError, ValueError):
        cache_path = Path(cache_folder)
        if cache_path.name != EMBEDDING_CACHE_DIR_NAME:
            raise
        with _models_lock:
            _models.pop(cache_folder, None)
        if cache_path.exists():
            shutil.rmtree(cache_path)
        model = _get_model(cache_folder)
        res = model.embed([text])
        return next(iter(res))


@to_thread()
def truncate_text_to_tokens(text: str, max_tokens: int = 450) -> str:
    encoding = tiktoken.get_encoding(FALLBACK_TOKENIZER)
    tokens = encoding.encode(text)[:max_tokens]
    return encoding.decode(tokens)
