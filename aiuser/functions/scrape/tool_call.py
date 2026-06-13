import logging
from typing import Any, Dict, Optional

from aiuser.functions import names
from aiuser.functions.context import ToolContext
from aiuser.functions.scrape.scrape import scrape_page
from aiuser.functions.tool_call import ToolCall
from aiuser.functions.types import Function, Parameters, ToolCallSchema

logger = logging.getLogger("red.bz_cogs.aiuser.tools")


class ScrapeToolCall(ToolCall):
    schema = ToolCallSchema(
        function=Function(
            name=names.OPEN_URL,
            description="Opens a URL or link and returns the content of it (Does not support non-text content types!)",
            parameters=Parameters(
                properties={
                    "url": {
                        "type": "string",
                        "description": "The URL or link to open",
                    }
                },
                required=["url"],
            ),
        )
    )
    function_name = schema.function.name

    async def _handle(
        self, tool_context: ToolContext, arguments: Dict[str, Any]
    ) -> Optional[str]:
        logger.info(f"Attempting scrape of {arguments['url']}")
        try:
            return await scrape_page(arguments["url"])
        except Exception:
            logger.debug(f"Failed to scrape {arguments['url']}", exc_info=True)
            return f"Unable to open the requested {arguments['url']}.."
