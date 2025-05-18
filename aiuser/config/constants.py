import re

IMAGE_REQUEST_CHECK_PROMPT = "As an AI, named {botname}, you are tasked to analyze messages directed towards you. Your role is to identify whether each specific message is asking you to send a picture of yourself or not. Messages can be phrased in a variety of ways, so you should look for key contextual clues such as requests for images, photographs, selfies, or other synonyms, but make sure it's specifically asking for a picture of 'you'. If the message explicitly requests a picture of {botname}, you are to respond with 'True'. If the message doesn't solicit a picture of 'you', then respond with 'False'."
IMAGE_REQUEST_REPLY_PROMPT = "You sent the picture above. Respond accordingly."
IMAGE_REQUEST_AIHORDE_URL = "https://aihorde.net/api"

RANDOM_MESSAGE_TASK_RETRY_SECONDS = 33 * 60

# regex patterns
URL_PATTERN = re.compile(r"(https?://\S+)")
YOUTUBE_URL_PATTERN = re.compile(r"(?:https?:\/\/)?(?:www\.)?(?:youtube\.com|youtu\.be)\/(?:watch\?v=)?(.+)")
YOUTUBE_VIDEO_ID_PATTERN = re.compile(
    r"(?:youtube(?:-nocookie)?\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/|v\/|t\/\S*?\/?)([a-zA-Z0-9_-]{11})")
SINGULAR_MENTION_PATTERN = re.compile(r"^<@!?&?(\d+)>$")
REGEX_RUN_TIMEOUT = 5


OPENROUTER_URL = "https://openrouter.ai/api/"
