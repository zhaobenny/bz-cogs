import asyncio

import aiohttp
import discord

from aimage.constants import VIEW_TIMEOUT


def round_to_nearest(x, base):
    return int(base * round(x/base))

# https://github.com/hollowstrawberry/crab-cogs/blob/b1f28057ae9760dbc1d51dadb290bdeb141642bf/novelai/novelai.py#L200C1-L200C74
async def delete_button_after(msg: discord.Message):
    await asyncio.sleep(VIEW_TIMEOUT)
    try:
        await msg.edit(view=None)
    except:
        return

def get_auth(auth_str: str):
    """ Format auth string to aiohttp.BasicAuth """
    auth = None
    if auth_str:
        username, password = auth_str.split(':')
        auth = aiohttp.BasicAuth(username, password)
    return auth
