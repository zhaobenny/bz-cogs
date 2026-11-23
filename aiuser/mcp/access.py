from __future__ import annotations

from typing import TypedDict

import discord


class AccessRule(TypedDict):
    everyone: bool
    members: list[int]
    roles: list[int]


class ServerAccess(TypedDict, total=False):
    default: AccessRule
    tools: dict[str, AccessRule]


def access_rule(everyone: bool = False) -> AccessRule:
    return {"everyone": everyone, "members": [], "roles": []}


def allows_tool(access: ServerAccess, tool: str, member: discord.Member | None) -> bool:
    rule = access.get("tools", {}).get(tool, access.get("default"))
    if rule is None or rule["everyone"]:
        return True
    return member is not None and (
        member.id in rule["members"]
        or any(role.id in rule["roles"] for role in member.roles)
    )
