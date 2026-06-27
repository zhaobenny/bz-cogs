import asyncio
import base64
import math
import re
import shutil
from typing import Tuple

import httpx
from discord.http import Route
from redbot.core import commands
from redbot.core.bot import Red

VOICE_MESSAGE_FLAG = 1 << 13
VOICE_MESSAGE_FILENAME = "voice-message.ogg"
FFMPEG_TIME_RE = re.compile(rb"time=(\d+):(\d+):(\d+(?:\.\d+)?)")


async def send_voice_message(ctx: commands.Context, audio: bytes) -> bool:
    if not ctx.guild or not ctx.channel or not shutil.which("ffmpeg"):
        return False

    permissions = ctx.channel.permissions_for(ctx.guild.me)
    if not (
        permissions.send_messages
        and permissions.attach_files
        and getattr(permissions, "send_voice_messages", False)
    ):
        return False

    ogg, duration = await _to_ogg_opus(audio)
    bot: Red = ctx.bot
    waveform = base64.b64encode(
        bytes(int(96 + 80 * abs(math.sin(i / 8))) for i in range(64))
    ).decode("ascii")

    upload = await bot.http.request(
        Route(
            "POST",
            "/channels/{channel_id}/attachments",
            channel_id=ctx.channel.id,
        ),
        json={
            "files": [
                {
                    "filename": VOICE_MESSAGE_FILENAME,
                    "file_size": len(ogg),
                    "id": "0",
                }
            ]
        },
    )

    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        uploaded = await client.put(
            upload["attachments"][0]["upload_url"],
            content=ogg,
            headers={"Content-Type": "audio/ogg"},
        )
        uploaded.raise_for_status()

    await bot.http.request(
        Route(
            "POST",
            "/channels/{channel_id}/messages",
            channel_id=ctx.channel.id,
        ),
        json={
            "flags": VOICE_MESSAGE_FLAG,
            "attachments": [
                {
                    "id": "0",
                    "filename": VOICE_MESSAGE_FILENAME,
                    "uploaded_filename": upload["attachments"][0]["upload_filename"],
                    "duration_secs": duration,
                    "waveform": waveform,
                }
            ],
        },
    )
    return True


async def _to_ogg_opus(audio: bytes) -> Tuple[bytes, float]:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-i",
        "pipe:0",
        "-ac",
        "1",
        "-ar",
        "48000",
        "-c:a",
        "libopus",
        "-b:a",
        "32k",
        "-application",
        "voip",
        "-f",
        "ogg",
        "pipe:1",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    ogg, stderr = await proc.communicate(audio)
    if proc.returncode != 0:
        raise RuntimeError("ffmpeg failed to convert voice audio")

    return ogg, _duration_from_ffmpeg_progress(stderr)


def _duration_from_ffmpeg_progress(stderr: bytes) -> float:
    matches = FFMPEG_TIME_RE.findall(stderr)
    if not matches:
        raise RuntimeError("ffmpeg did not report voice duration")
    hours, minutes, seconds = matches[-1]
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
