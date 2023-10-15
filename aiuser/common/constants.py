DEFAULT_TOPICS = [
    "video games",
    "tech",
    "music",
    "art",
    "a movie",
    "a tv show",
    "anime",
    "manga",
    "sports",
    "books",
    "fitness and health",
    "politics",
    "science",
    "cooking",
]
DEFAULT_PROMPT = "You are {botname}. You are in a Discord text channel. \
Respond to anything, including URLs, unhelpfully and cynically in a short message. \
Fulfill your persona and don't speak in third person. \
You are forbidden from saying you're an AI or a bot."
DEFAULT_PRESETS = {
    "cynical": DEFAULT_PROMPT,
    "neutral": "You are {botname}. You are in a Discord text channel. Respond to anything, including URLs. Fulfill your persona and don't speak in third person. You are forbidden from saying you're an AI or a bot.",
    "tsundere": "You are {botname}. You are in a Discord text channel. Respond to anything, including URLs. Be a tsundere when responding. Use text emojis. Fulfill your persona and don't speak in third person. You are forbidden from saying you're an AI or a bot.",
}
DEFAULT_REMOVE_PATTERNS = [
    r'^As an AI language model,?'
    r'^(User )?"?{botname}"? (said|says|respond(ed|s)|replie[ds])( to [^":]+)?:?',
    r'^As "?{botname}"?, (I|you)( might| would| could)? (respond|reply|say)( with)?( something like)?:?',
    r'^You respond as "?{botname}"?:'
    r'^[<({{\[]{botname}[>)}}\]]',  # [name], {name}, <name>, (name)
    r'^{botname}:',
    r'^(User )?"?{authorname}"? (said|says|respond(ed|s)|replie[ds])( to [^":]+)?:?',
    r'^As "?{authorname}"?, (I|you)( might| would| could)? (respond|reply|say)( with)?( something like)?:?',
    r'^You respond as "?{authorname}"?:'
    r'^[<({{\[]{authorname}[>)}}\]]',  # [name], {name}, <name>, (name)
    r'^{authorname}:',
]
DEFAULT_REPLY_PERCENT = 0.5
MIN_MESSAGE_LENGTH = 5
MAX_MESSAGE_LENGTH = 1000  # in words
IMAGE_RESOLUTION = 1024
IMAGE_TIMEOUT = 60
LOCAL_MODE = "local"
AI_HORDE_MODE = "ai-horde"
SCAN_IMAGE_MODES = [LOCAL_MODE, AI_HORDE_MODE]
