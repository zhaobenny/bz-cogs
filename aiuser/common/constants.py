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
    r'^As an AI language model,?',
    r'^(User )?"?{botname}"? (said|says|respond(ed|s)|replie[ds])( to [^":]+)?:?',
    r'^As "?{botname}"?, (I|you)( might| would| could)? (respond|reply|say)( with)?( something like)?:?',
    r'^You respond as "?{botname}"?:',
    r'^[<({{\[]{botname}[>)}}\]]',  # [name], {name}, <name>, (name)
    r'^{botname}:',
    r'^(User )?"?{authorname}"? (said|says|respond(ed|s)|replie[ds])( to [^":]+)?:?',
    r'^As "?{authorname}"?, (I|you)( might| would| could)? (respond|reply|say)( with)?( something like)?:?',
    r'^You respond as "?{authorname}"?:',
    r'^[<({{\[]{authorname}[>)}}\]]',  # [name], {name}, <name>, (name)
    r'^{authorname}:',
    r'\n*\[Image[^\]]+\]'
]
DEFAULT_REPLY_PERCENT = 0.5
MIN_MESSAGE_LENGTH = 5
MAX_MESSAGE_LENGTH = 1000  # in words
# image captioning
IMAGE_RESOLUTION = 1024
# for rudimentary SD request checks
RELATED_IMAGE_WORDS = ["image", "images", "picture", "pictures", "photo", "photos", "photograph", "photographes"]
SECOND_PERSON_WORDS = ["yourself", "you"]
IMAGE_CHECK_REQUEST_PROMPT = "Your task is to classify messages. You are {botname}. Is the following a message asking for a picture, image, or photo that includes yourself or {botname}?  Answer with True/False."
IMAGE_GENERATION_PROMPT = """
I want you to act as a Stable Diffusion Art Prompt Generator. The formula for a prompt is made of parts, the parts are indicated by brackets. The [Subject] is the person place or thing the image is focused on. [Emotions] is the emotional look the subject or scene might have. [Verb] is What the subject is doing, such as standing, jumping, working and other varied that match the subject. [Adjectives] like beautiful, rendered, realistic, tiny, colorful and other varied that match the subject. The [Environment] in which the subject is in, [Lighting] of the scene like moody, ambient, sunny, foggy and others that match the Environment and compliment the subject. [Photography type] like Polaroid, long exposure, monochrome, GoPro, fisheye, bokeh and others. And [Quality] like High definition, 4K, 8K, 64K UHD, SDR and other. The subject and environment should match and have the most emphasis.
It is ok to omit one of the other formula parts. I will give you a [Subject], you will respond with a full prompt. Present the result as one full sentence, no line breaks, no delimiters, and keep it as concise as possible while still conveying a full scene.

Here is a sample of how it should be output: "Beautiful woman, contemplative and reflective, sitting on a bench, cozy sweater, autumn park with colorful leaves, soft overcast light, muted color photography style, 4K quality."

Convert the below message to a Stable Diffusion Art Prompt.  The prompt should be a full sentence, no second person references, no line breaks, no delimiters, and keep it as concise as possible while still conveying a full scene.
"""
# keep
LOCAL_MODE = "local"
AI_HORDE_MODE = "ai-horde"
SCAN_IMAGE_MODES = [LOCAL_MODE, AI_HORDE_MODE]
