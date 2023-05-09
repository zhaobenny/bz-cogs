import asyncio
import logging
import os
import wave

import discord
from redbot.core import commands

logger = logging.getLogger("red.bz_cogs.ai_user")
logging.debug("Loading TTS packages...")

from balacoon_tts import TTS
from huggingface_hub import hf_hub_download

addon_path = hf_hub_download(repo_id="balacoon/tts", filename="en_us_cmuartic_jets_cpu.addon")

# balacoon needs a manual install.
# https://balacoon.com/use/tts/package
# linux only

logging.debug("Loaded TTS packages...")

async def sent_tts_response(ctx: commands.Context, response):
    tts = TTS(addon_path)
    speaker = 'eey'
    samples = tts.synthesize(response, speaker)

    FILENAME = "audio.wav"

    with wave.open(FILENAME, "w") as fp:
        fp.setparams((1, 2, tts.get_sampling_rate(), len(samples), "NONE", "NONE"))
        fp.writeframes(samples)

    audio_source = discord.FFmpegPCMAudio(FILENAME)

    if not ctx.author.voice:
        audio_file = discord.File(FILENAME)

        await ctx.channel.send(file=audio_file)
        
    voice_client = await ctx.author.voice.channel.connect()

    voice_client.play(audio_source)

    while voice_client.is_playing():
        await asyncio.sleep(1)

    os.remove(FILENAME)
    await voice_client.disconnect()

