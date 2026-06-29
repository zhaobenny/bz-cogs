from aiuser.functions.voice.providers import elevenlab, finevoice, openrouter
from aiuser.functions.voice.constants import ELEVENLAB, FINEVOICE, OPENROUTER

PROVIDERS = {
    ELEVENLAB: elevenlab.generate,
    FINEVOICE: finevoice.generate,
    OPENROUTER: openrouter.generate,
}

DEFAULT_MODELS = {
    ELEVENLAB: elevenlab.DEFAULT_MODEL,
    FINEVOICE: None,
    OPENROUTER: openrouter.DEFAULT_MODEL,
}

DEFAULT_VOICES = {
    ELEVENLAB: elevenlab.DEFAULT_VOICE,
    FINEVOICE: finevoice.DEFAULT_VOICE,
    OPENROUTER: openrouter.DEFAULT_VOICE,
}
