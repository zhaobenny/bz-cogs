import os

from redbot.core import Config
from redbot.core.data_manager import core_data_path

CODEX_ENDPOINT_MODE = "codex"


async def is_codex_endpoint_mode(config: Config) -> bool:
    return await config.custom_openai_endpoint() == CODEX_ENDPOINT_MODE


def secure_token_store_permissions():
    path = core_data_path() / "settings.json"
    if path.exists():
        os.chmod(path, 0o600)
