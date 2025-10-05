from dataclasses import dataclass, field
from enum import Enum


@dataclass
class ImageResponse:
    data: bytes = None
    payload: dict = field(default_factory=dict)
    is_nsfw: bool = False
    info_string: str = ""
    extension: str = "png"


class ImageGenerationType(Enum):
    TXT2IMG = "txt2img"
    IMG2IMG = "img2img"