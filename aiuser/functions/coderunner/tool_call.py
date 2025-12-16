import logging
import uuid
from typing import TYPE_CHECKING

import modal

from aiuser.functions.tool_call import ToolCall
from aiuser.functions.types import Function, Parameters, ToolCallSchema

if TYPE_CHECKING:
    from aiuser.response.llm_pipeline import LLMPipeline

logger = logging.getLogger("red.bz_cogs.aiuser")


class CodeRunnerToolCall(ToolCall):
    schema = ToolCallSchema(
        function=Function(
            name="run_python_code",
            description="Use this to run Python 3.12 scripts in an ephemeral session. If you need output, it should be in a print statement.",
            parameters=Parameters(
                properties={
                    "code": {
                        "type": "string",
                        "description": "The Python script to run.",
                    }
                },
                required=["code"],
            ),
        )
    )
    function_name = schema.function.name

    async def _handle(self, request: "LLMPipeline", arguments):
        tokens = await self.bot.get_shared_api_tokens("modal")
        token_id = tokens.get("token_id")
        token_secret = tokens.get("token_secret")

        if not token_id or not token_secret:
            return "Modal API credentials not configured."

        code = arguments.get("code", "")
        if not code:
            return "No code provided to execute."

        sandbox_name = uuid.uuid4().hex[:8]
        logger.debug("Executing code on Modal Sandbox %s: \n%s", sandbox_name, code)

        try:
            client = modal.Client.from_credentials(token_id, token_secret)
            app = modal.App.lookup(
                "aiuser-code-runner", client=client, create_if_missing=True
            )

            sandbox = modal.Sandbox.create(
                "python",
                "-c",
                code,
                image=modal.Image.debian_slim(python_version="3.12"),
                timeout=15,
                name=sandbox_name,
                app=app,
            )

            await sandbox.wait.aio()

            stdout = await sandbox.stdout.read.aio()
            stderr = await sandbox.stderr.read.aio()

            output = ""
            if stdout:
                output += stdout
            if stderr:
                output += f"\n[stderr]: {stderr}"

            return f"Code execution result:\n{output.strip() or 'Code executed successfully (no output - use print statements if you need output)'}"

        except Exception as e:
            logger.warning("Failed to execute code on code runner", exc_info=e)
            return f"Error executing code: \n {str(e)}"
