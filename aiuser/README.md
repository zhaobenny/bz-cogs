# How to use 🛠️

The bot will generate responses in enabled reply channels. Bot owners can enable one using:
```
[p]aiuser channels add <CHANNEL>
```

Bot owners can change the percentage of eligible message bursts to reply to:
```
[p]aiuser reply chance set <PERCENT>
```

Bot owners can change the LLM endpoint used for generating responses (for example, OpenRouter, Codex, or a custom URL; compatibility may vary) using:
```
[p]aiuserowner endpoint set <ENDPOINT>
```

Users will also have to opt-in (bot-wide) into having their messages used:
```
[p]aiuser optin
```

Admins can modify prompt settings in:
```
[p]aiuser prompt
```

Bot owners can manage tools (for example, generating images or searching the web) using:
```
[p]aiuser tools
```

Some additional settings are restricted to bot owner only.
See other settings using:
```
[p]aiuserowner
[p]aiuser
```

## Remote MCP tools

Bot owners can run `[p]aiuser tools mcp` and click **Open MCP setup**. The private panel handles adding, selecting, editing, and removing servers. Use **Check connection** for a saved endpoint or **Sign in** if credentials are required. Once connected, **Review and enable** shows the tools and their access before you turn them on for the current Discord server. Use **More actions** to edit or remove the connection. Server URLs and credentials are shared bot-wide.

Choose **Tool access** to edit the server default or select an individual tool. Access rules apply to the current Discord server.

Choose **Everyone**, **No one**, or select the members and roles to allow. A match on either list grants access. Changes apply when you click **Save access**. A tool with its own rule can return to **Use server default**. The default is Everyone until you change it.

Existing text subcommands such as `mcp add`, `mcp info`, and `mcp access` are still available. Run `[p]help aiuser tools mcp` for the full list.

Access rules control who can trigger MCP tools. A reply posted in a channel is visible to everyone who can read that channel.

### Have fun. 🎉
![repetition](https://user-images.githubusercontent.com/46238123/227853613-1a524915-ed46-45f7-a154-94e90daf0cd7.jpg)

---

## Custom LLM Endpoints
Bot owners can globally change the AI backend endpoint using:
`[p]aiuserowner endpoint set <endpoint>`

* OpenRouter is supported via API key authentication, set up with:
  - `[p]aiuserowner endpoint set openrouter`
  - `[p]set api openrouter api_key,INSERT_API_KEY`
  - More details: [OpenRouter Docs](https://openrouter.ai/docs#models)
* ChatGPT plan access is supported via Sign in with ChatGPT. Start the process with:
  - `[p]aiuserowner endpoint set chatgpt`
* Other OpenAI-completions compatible endpoint support may vary and can be setup directly with:
  -`[p]aiuserowner endpoint set <ENDPOINT_URL>`

### Disclaimers when using custom endpoints:
* Models may need changing per server to have a valid model or match the provider's available models.
* Custom parameters set via `[p]aiuser response parameters set` per server may need changing to support different providers/models
* Performance varies by models; some third-party models may yield undesirable results.

---

## Image inputs 🖼️

![image_seeing](https://github.com/zhaobenny/bz-cogs/assets/46238123/8b0019f3-8b38-4578-b511-a350e10fce2d)

Enabling image processing allows the bot to incorporate attached images into the prompt. The selected model must support vision.

Image attachments are sent to the configured LLM endpoint for processing.

Bot owners can configure image processing with the following commands:
- `[p]aiuser media images show`
- `[p]aiuser media images enable|disable`
- `[p]aiuser media images max_size [set]`
  - Set the maximum image size (in MB) for an image that can be used
- `[p]aiuser media images detail [set]`
  - Set the level of detail for image processing. Options are `low`, `high`, and `auto`.
- `[p]aiuser media images model [list|set|clear]`

## Memory 🧠

Memory lets the bot recall stored information automatically without stuffing the prompt.
It includes relevant saved details when generating responses. Memories can be added manually, or the model can save them automatically when the memory tools are enabled.

Enable saved-memory retrieval with `[p]aiuser memory enable`, and enable the memory tools with `[p]aiuser tools memory enable`.

You can combine this with tools for more advanced behavior.
For example: a memory could store “when asked for a photo of the [bot], use this description for the image request: [...]”, and the bot will automatically apply that description when generating the image. (dependent on the LLM's intelligence)

Admins can manage saved-memory retrieval and stored memories with:
```
[p]aiuser memory
```

## Random Messages 🎲

Have the bot sent random messages into a channel without external triggers.

Every 33 minutes, a RNG roll will determine if a random message will be sent using a list of topics as a prompt.

Enabled reply channels must have an hour pass without a message before a random message can be sent, and the last message must have been sent by a user.

Bot owners enable this setting per server here:
```
[p]aiuser random enable
```

Admins also manage topics here:
```
[p]aiuser random
```

---

## Prompt/Topics Dynamic Variables  📝

Prompts, topics,and image pre-prompt can include certain dynamic variables by including one of the following strings:

- `{botname}` - the bot's current nickname or username
- `{botowner}` - the bot owner(s) username(s)
- `{authorname}` - the author of the message the bot is activated on
- `{authortoprole}` - the author's highest role
- `{authormention}` - the author's mention in string format
- `{serverprompt}` - the configured server prompt, falling back to the global/default prompt
- `{channelprompt}` - the configured channel prompt, if one is set
- `{roleprompt}` - the author's highest configured role prompt, if one is set
- `{serveremojis}` - all of the server emojis, in a string format (eg. `<:emoji:12345> <:emoji2:78912>`)
- `{servername}` - the server name
- `{channelname}` - the current channel name
- `{channeltopic}` - the current channel description/topic
- `{currentdate}` - the current date eg. 2023/08/31 (based on host timezone)
- `{currentweekday}` - the current weekday eg. Monday (based on host timezone)
- `{currenttime}` - the current 24-hour time eg. 21:59 (based on host timezone)
- `{randomnumber}` - a random number between 0 - 100


Response filter regex patterns only support `{authorname}` (using authors of the last 10 messages) and `{botname}` placeholders.

---
