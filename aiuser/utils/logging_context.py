import contextvars
import functools
import logging
import os
import sys
from typing import Any, Callable, TypeVar

_AIUSER_LOGGER_PREFIX = "red.bz_cogs.aiuser"
_ANSI_GRAY = "\x1b[90m"
_ANSI_RESET = "\x1b[0m"
_LOG_CONTEXT: contextvars.ContextVar[str] = contextvars.ContextVar(
    "aiuser_log_context", default=""
)
_F = TypeVar("_F", bound=Callable[..., Any])


def _supports_color() -> bool:
    if os.getenv("NO_COLOR"):
        return False
    return sys.stderr.isatty()


def _colorize_gray(text: str) -> str:
    if not _supports_color():
        return text
    return f"{_ANSI_GRAY}{text}{_ANSI_RESET}"


def _build_log_prefix(guild: Any, channel: Any) -> str:
    parts = []

    guild_name = getattr(guild, "name", None) if guild is not None else None
    if guild_name:
        parts.append(f"guild={guild_name}")

    channel_name = getattr(channel, "name", None) if channel is not None else None
    if channel_name:
        parts.append(f"channel=#{channel_name}")

    if not parts:
        return ""

    return _colorize_gray(f"[{' '.join(parts)}] ")


def _resolve_log_context(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    # Prefer keyword values, then positional args.
    for value in tuple(kwargs.values()) + args:
        if all(hasattr(value, attr) for attr in ("channel", "guild")):
            return _build_log_prefix(
                getattr(value, "guild", None),
                getattr(value, "channel", None),
            )

    return ""


class _AIUserContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not record.name.startswith(_AIUSER_LOGGER_PREFIX):
            return True

        prefix = _LOG_CONTEXT.get()
        if not prefix:
            return True

        record.msg = f"{prefix}{record.getMessage()}"
        record.args = ()
        return True


_AIUSER_CONTEXT_FILTER = _AIUserContextFilter()


def install_aiuser_log_filters() -> None:
    logger = logging.getLogger(_AIUSER_LOGGER_PREFIX)
    handlers = logger.handlers or logging.getLogger().handlers
    for handler in handlers:
        if _AIUSER_CONTEXT_FILTER not in handler.filters:
            handler.addFilter(_AIUSER_CONTEXT_FILTER)


def with_discord_log_context(_source: str) -> Callable[[_F], _F]:
    def decorator(func: _F) -> _F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any):
            install_aiuser_log_filters()
            token = _LOG_CONTEXT.set(_resolve_log_context(args, kwargs))
            try:
                return await func(*args, **kwargs)
            finally:
                _LOG_CONTEXT.reset(token)

        return wrapper

    return decorator


install_aiuser_log_filters()
