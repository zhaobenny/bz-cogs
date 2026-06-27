from aiuser.functions.voice.providers import finevoice, openrouter

FINEVOICE = "finevoice"
OPENROUTER = "openrouter"

PROVIDERS = {
    FINEVOICE: finevoice.generate,
    OPENROUTER: openrouter.generate,
}
