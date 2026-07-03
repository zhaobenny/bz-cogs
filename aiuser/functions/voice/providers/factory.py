from aiuser.functions.voice.providers import elevenlab, finevoice, openai, openrouter
from aiuser.functions.voice.constants import ELEVENLAB, FINEVOICE, OPENAI, OPENROUTER

PROVIDERS = {
    ELEVENLAB: elevenlab.generate,
    FINEVOICE: finevoice.generate,
    OPENAI: openai.generate,
    OPENROUTER: openrouter.generate,
}

DEFAULT_MODELS = {
    ELEVENLAB: elevenlab.DEFAULT_MODEL,
    FINEVOICE: None,
    OPENAI: openai.DEFAULT_MODEL,
    OPENROUTER: openrouter.DEFAULT_MODEL,
}

DEFAULT_VOICES = {
    ELEVENLAB: elevenlab.DEFAULT_VOICE,
    FINEVOICE: finevoice.DEFAULT_VOICE,
    OPENAI: openai.DEFAULT_VOICE,
    OPENROUTER: openrouter.DEFAULT_VOICE,
}
