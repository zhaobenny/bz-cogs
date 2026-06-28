import asyncio
import base64
import re
import shutil
import struct
from typing import Tuple

import httpx
from discord.http import Route
from redbot.core import commands
from redbot.core.bot import Red

VOICE_MESSAGE_FLAG = 1 << 13
VOICE_MESSAGE_FILENAME = "voice-message.ogg"
FFMPEG_TIME_RE = re.compile(rb"time=(\d+):(\d+):(\d+(?:\.\d+)?)")
WAVEFORM_SAMPLE_COUNT = 64
WAVEFORM_SAMPLE_RATE = 8000


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
    waveform = base64.b64encode(await _waveform_from_audio(audio)).decode("ascii")

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


async def _waveform_from_audio(audio: bytes) -> bytes:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-i",
        "pipe:0",
        "-ac",
        "1",
        "-ar",
        str(WAVEFORM_SAMPLE_RATE),
        "-f",
        "s16le",
        "pipe:1",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    pcm, _ = await proc.communicate(audio)
    if proc.returncode != 0 or not pcm:
        return bytes(WAVEFORM_SAMPLE_COUNT)

    samples = [
        abs(sample[0])
        for sample in struct.iter_unpack("<h", pcm[: len(pcm) - (len(pcm) % 2)])
    ]
    if not samples:
        return bytes(WAVEFORM_SAMPLE_COUNT)

    bucket_size = len(samples) / WAVEFORM_SAMPLE_COUNT
    buckets = []
    for i in range(WAVEFORM_SAMPLE_COUNT):
        start = int(i * bucket_size)
        end = int((i + 1) * bucket_size)
        bucket = samples[start:end] or samples[start : start + 1]
        buckets.append(max(bucket) if bucket else 0)

    peak = max(buckets)
    if peak <= 0:
        return bytes(WAVEFORM_SAMPLE_COUNT)

    return bytes(min(255, round((value / peak) ** 0.5 * 255)) for value in buckets)


def _duration_from_ffmpeg_progress(stderr: bytes) -> float:
    matches = FFMPEG_TIME_RE.findall(stderr)
    if not matches:
        raise RuntimeError("ffmpeg did not report voice duration")
    hours, minutes, seconds = matches[-1]
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
