# AGENTS.md

You are in WSL. 

Commit messages on main should be prefixed by the cog being modified. Omit the cog prefix for commits on feature branches.

When changing aiuser, bump `__version__` in `aiuser/core/aiuser.py` on feature branches as well as main. The pre-push version check skips feature branches.

Do not add unit/regression tests by default. Prefer existing tests, integration checks, or live probe validation unless the user explicitly asks for tests or the change cannot be credibly verified otherwise.

Keep fixes minimal and local. Do not introduce new wrappers, helpers, mixins, aliases, dedicated resolvers, or “cleanup” abstractions unless they are clearly necessary for the requested change.

This repo still runs under Python 3.9 in the Redbot venv. For any runtime module that uses modern type unions, add `from __future__ import annotations` or use `typing.Optional`/`typing.Union` so imports do not fail under 3.9.

For third-party behavior or compatibility questions, verify directly from upstream source/docs/commits rather than relying on memory or shallow search. Cloning to /tmp for inspection is acceptable.
/
