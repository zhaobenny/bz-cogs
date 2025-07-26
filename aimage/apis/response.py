from dataclasses import dataclass, field


@dataclass
class ImageResponse:
    data: bytes = None
    payload: dict = field(default_factory=dict)
    is_nsfw: bool = False
    info_string: str = ""
    extension: str = "png"
