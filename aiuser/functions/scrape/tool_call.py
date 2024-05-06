

import logging

from aiuser.functions.scrape.scrape import scrape_page
from aiuser.functions.tool_call import ToolCall
from aiuser.functions.types import Function, Parameters, ToolCallSchema

logger = logging.getLogger("red.bz_cogs.aiuser")


class ScrapeToolCall(ToolCall):
    schema = ToolCallSchema(function=Function(
        name="open_url",
        description="Opens a URL or link and returns the content of it",
        parameters=Parameters(
            properties={
                    "url": {
                        "type": "string",
                        "description": "The URL or link to open",
                    }
            },
            required=["query"]
        )))
    function_name = schema.function.name

    async def _handle(self, arguments):
        logger.info(f'Scraping {arguments["url"]} in {self.ctx.guild}')
        return await scrape_page(arguments["url"])
