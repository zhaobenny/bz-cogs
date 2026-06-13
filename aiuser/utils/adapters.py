"""Small explicit adapters for discord.py objects.

Red's ``bot.ignored_channel_or_guild`` assumes a :class:`discord.Member`
author (it touches ``author._roles`` and ``author.is_timed_out``). Webhook and
DM-style messages carry a plain :class:`discord.User`, so we wrap those in an
adapter that supplies exactly the two member-only members Red touches and
delegates everything else to the wrapped user.
"""

from __future__ import annotations

import discord


class _EmptyRoles:
    """Mimics discord.py's internal ``Member._roles`` SnowflakeList: empty."""

    def has(self, role_id) -> bool:
        return False

    def __iter__(self):
        return iter(())

    def __contains__(self, role_id) -> bool:
        return False

    def __repr__(self) -> str:
        return "_EmptyRoles()"


class MemberLikeUser:
    """A :class:`discord.User` that can pass Red's member-only checks."""

    def __init__(self, user: discord.User):
        # bypass __getattr__ delegation for our own attributes
        object.__setattr__(self, "_wrapped_user", user)
        object.__setattr__(self, "_roles", _EmptyRoles())

    def is_timed_out(self) -> bool:
        return False

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_wrapped_user"), name)

    def __repr__(self) -> str:
        return f"MemberLikeUser({object.__getattribute__(self, '_wrapped_user')!r})"


def ensure_member_like(author):
    """Return ``author`` unchanged if it is a Member, else a MemberLikeUser."""
    if isinstance(author, discord.Member):
        return author
    return MemberLikeUser(author)
