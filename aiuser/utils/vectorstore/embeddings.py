import numpy as np
import tiktoken
from fastembed import TextEmbedding
from fastembed.common.types import NumpyArray

from aiuser.config.constants import EMBEDDING_MODEL, FALLBACK_TOKENIZER
from aiuser.utils.utilities import encode_text_to_tokens, to_thread


async def embed_text(text: str, cache_folder: str) -> NumpyArray:
    token_count = await encode_text_to_tokens(text)
    if token_count > 500:
        text = await truncate_text_to_tokens(text, FALLBACK_TOKENIZER)
    embedding = await embed_sync(text, cache_folder)
    return np.array(embedding, dtype=np.float32)


@to_thread()
def embed_sync(text: str, cache_folder: str) -> NumpyArray:
    model = TextEmbedding(EMBEDDING_MODEL, cache_folder=cache_folder)
    res = model.embed([text])
    return next(iter(res))


@to_thread()
def truncate_text_to_tokens(text: str, max_tokens: int = 450) -> str:
    encoding = tiktoken.get_encoding(FALLBACK_TOKENIZER)
    tokens = encoding.encode(text)[:max_tokens]
    return encoding.decode(tokens)
