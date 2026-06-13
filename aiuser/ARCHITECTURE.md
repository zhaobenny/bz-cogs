# aiuser architecture

One page to hold the whole cog in your head. If you change the structure,
change this file (and `tests/test_layering.py`, which enforces the layers in CI).

## The layers

Imports point **down** only. `if TYPE_CHECKING:` imports are exempt.

```
L7  core/        composition root: the cog class, listeners, background tasks,
                 AIUserServices wiring. The ONLY layer that may import settings/.
L6  settings/    Discord command mixins (thin: parse → config/services → embed)
L6  dashboard/   Red web-dashboard pages
L5  response/    one response, end to end: pipeline.py (LLM round loop),
                 sender.py (cleanup + send), response.py (orchestration)
L4  context/     building the conversation payload: conversation.py (dumb
                 ordered list + token budget), assembler.py (the build),
                 converter/ (Discord msg -> chat entries), memory/, compaction
L3  functions/   tools the LLM can call. registry.py lists them ALL explicitly;
                 context.py (ToolContext) is the entire API a tool may touch.
L2  llm/         providers (openai-compatible, codex) behind LLMProvider
L2  consent/     ConsentService: the ONLY owner of opt-in/opt-out state
L1  utils/       cache, tokenizer, restricted HTTP, adapters — no business logic
L1  types/       MixinMeta + shared typing helpers
L0  config/      defaults, constants, generated model tables, and the two
                 brains: resolver.py (scoped settings) + model_info.py
```

## The five things to know

1. **`AIUserServices` (core/services.py)** is built once in `cog_load` and
   holds every dependency: consent, resolver, guild cache, vectorstore,
   compaction, tool-call cache, openai client. Nothing takes "the cog"
   anymore; settings mixins reach it via `self.services`.

2. **`ScopedConfigResolver` (config/resolver.py)** is the only implementation
   of `member > role (highest position) > channel > guild` setting resolution.
   Never hand-roll an `or`-chain over config scopes — call the resolver.

3. **`ConsentService` (consent/)** is the only reader/writer of opt-in/out.
   Reads are in-memory sets; writes are locked. Commands, the consent embed
   buttons, the dashboard, GDPR deletion, and history filtering all go
   through it.

4. **Tools** = subclass `ToolCall`, implement `_handle(tool_context, args)`,
   add the class to `functions/registry.ALL_TOOLS` and its name to
   `functions/names.py`. A tool sees a `ToolContext` (ctx, config, bot,
   memories, `attach_file()`, `suppress()`) and *nothing else* — tools must
   never import `response/`.

5. **`GuildSettingsCache` (core/services.py)** is the write-through cache for
   the three per-guild options read on every message (channels whitelist,
   optin-by-default, compiled ignore regex). Mutate them only through its
   setters or config and cache will disagree.

## Message lifecycle

```
on_message_without_command                       core/aiuser.py
  handle_message(services, message)              core/handlers.py
    is_valid_message()                           core/validators.py
      guild perms → channel whitelist → user/consent → content
    check_triggers() or reply_percent roll       core/triggers.py
    create_response(services, ctx)               response/response.py
      ConversationAssembler(services, ctx).build()   context/assembler.py
        payload order (oldest → newest):
          [summary][history… (+ cached tool calls)][system prompt]
          [memory][replied-to reference][trigger message]
        history walks newest→oldest and *prepends* until the token
        budget is spent — there is no insert-at-index anywhere
      LLMPipeline(services, ctx, conversation).run()  response/pipeline.py
        loop: chat step → tool calls → ToolManager → ToolContext
      remove_patterns_from_response / send_response   response/sender.py
      cache tool-call entries for future context rebuilds
```

Slash commands enter via `handle_slash_command`; random messages via
`RandomMessageTask` (an object owned by the cog — not a mixin), which builds
with `prompt_override=…, include_history=False, include_trigger=False`.

## Conventions & invariants

- `Conversation` is mutated only via `append*` / `prepend*`. If you need a
  message "in the middle", you are assembling in the wrong order.
- System messages that are *context*, not persona, carry a `name` tag
  (`"memory"`, `"summary"`). Providers (codex) classify by tag — never by
  matching content strings.
- Model capabilities (vision / tools / logit_bias / token limit) come from
  `config/model_info.get_model_info()`. Never substring-match the generated
  tables in `config/models.py` directly.
- Swallowed exceptions must be logged. Config reads are not wrapped in
  try/except — a missing default is a programming error you want loud.
- `unittest.mock` never appears in production code; webhook authors are
  adapted with `utils/adapters.ensure_member_like`.
- Python 3.9 compatible: no `X | Y` unions at runtime.

## Command-group plumbing (the one weird trick)

discord.py re-parents subcommands onto the command with the same qualified
name defined on the final cog class. Settings mixins therefore attach
subcommands to the module-level stub in `settings/_groups.py`, and
`settings/base.Settings` defines the real `aiuser` group. Same pattern one
level down for `functions` in `settings/functions/utilities.py`.

## Tests

```
.venv/bin/python -m pytest aiuser/tests/ -q
```

- `test_layering.py` — enforces the import layers above (fails the suite on
  any upward import).
- `test_message_thread.py` / `test_tool_call_cache.py` — conversation
  assembly order, pruning, cached tool-call re-injection.
- `test_triggers.py` — the resolver precedence matrix (member/role/channel/
  guild, highest-role-wins).
- `conftest.py` builds a real `AIUserServices` against dpytest + a real Red
  Config; prefer extending it over ad-hoc mocks.
