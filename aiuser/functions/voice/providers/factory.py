from aiuser.functions.voice.providers import elevenlab, finevoice, openrouter

ELEVENLAB = "elevenlab"
FINEVOICE = "finevoice"
OPENROUTER = "openrouter"

PROVIDERS = {
    ELEVENLAB: elevenlab.generate,
    FINEVOICE: finevoice.generate,
    OPENROUTER: openrouter.generate,
}
