from dataclasses import dataclass, field
from typing import Optional

from discord import app_commands


@dataclass
class ImageGenParams:
    prompt: str
    negative_prompt: str = None
    style: str = None
    width: int = None
    height: int = None
    cfg: int = None
    sampler: str = None
    scheduler: str = None
    steps: int = None
    seed: int = -1
    variation: int = 0
    variation_seed: int = -1
    checkpoint: str = None
    vae: str = None
    lora: str = ""
    subseed: int = -1
    subseed_strength: float = 0.0
    # img2img
    init_image: bytes = field(default_factory=bytes)
    denoising: float = None
