# How to use 🛠️

The bot will generate responses in whitelisted channels. Bot owners can add a channel to a server's whitelist using:
```
[p]aiuser add <CHANNEL>
```

Bot owners can change the percentage of eligible messages to reply to:
```
[p]aiuser percent <PERCENT>
```

Bot owners can change the LLM provider used for generating responses (eg. switching to OpenRouter, Codex sub or a custom URL endpoint - *Compatibility may vary*) using:
```
[p]aiuserowner endpoint <ENDPOINT>
```

Users will also have to opt-in (bot-wide) into having their messages used:
```
[p]aiuser optin
```

Admins can modify prompt settings in:
```
[p]aiuser prompt
```

Bot owners can also manage/enable function calling (eg. generating images or performing Google searches) using:
```
[p]aiuser functions
```

Some additional settings are restricted to bot owner only.
See other settings using:
```
[p]aiuserowner
[p]aiuser
```

### Have fun. 🎉
![repetition](https://user-images.githubusercontent.com/46238123/227853613-1a524915-ed46-45f7-a154-94e90daf0cd7.jpg)

---

## Custom LLM Providers
Bot owners can globally change the AI backend provider using:
`[p]aiuserowner endpoint <endpoint>`

* OpenRouter is supported via API key authentication, set up with:
  - `[p]aiuserowner endpoint openrouter`
  - `[p]set api openrouter api_key,INSERT_API_KEY`
  - More details: [OpenRouter Docs](https://openrouter.ai/docs#models)
* Codex subscription is supported via device code authentication for setup, start the process with:
  - `[p]aiuserowner endpoint codex`
* Other OpenAI-completions compatible endpoint support may vary and can be setup directly with:
  -`[p]aiuserowner endpoint <ENDPOINT_URL>`

### Disclaimers when using using custom providers:
* Models may need changing per server to have a valid model or match the provider's available models.
* Custom Parameters set via `[p]aiuser response parameters` per server may need changing to support different providers/models
* Performance varies by models; some third-party models may yield undesirable results.

---

## Image scanning 🖼️

![image_seeing](https://github.com/zhaobenny/bz-cogs/assets/46238123/8b0019f3-8b38-4578-b511-a350e10fce2d)

Enabling image scanning will allow the bot to incorporate images in the triggering message into the prompt. This requires the currently used LLM to have vision capabilities.

This will send image attachments to the specified endpoint for processing.

Bot owners can configure image scanning with the following commands:
- `[p]aiuser imagescan toggle`
  - Toggles scanning on or off.
- `[p]aiuser imagescan maxsize <size_in_mb>`
  - Sets the maximum size in Megabytes for an image to be scanned.
- `[p]aiuser imagescan model <model_name>`
  - Sets a specific model for image scanning. By default, the model used for chatting is used. Run without a model name to revert to using the chat model.

## Memory 🧠

Memory lets the bot recall stored information automatically without stuffing the prompt.
It works by including relevant (only manually saved memories currently) details when generating responses.

You can combine this with function calling for more advanced behavior.
For example: a memory could store “when asked for a photo of the [bot], use this description for the image request: [...]”, and the bot will automatically apply that description when generating the image. (dependent on the LLM's intelligence)

The command for bot owners is:
```
[p]aiuser memory
```

## Random Messages 🎲

Have the bot sent random messages into a channel without external triggers.

Every 33 minutes, a RNG roll will determine if a random message will be sent using a list of topics as a prompt.

Whitelisted channels must have a hour pass without a message sent in it for a random message to be sent, and the last sent message must be sent by a user.

Bot owners enable this setting per server here:
```
[p]aiuser randommessage toggle
```

Admins also manage topics here:
```
[p]aiuser randommessage
```
---

## Prompt/Topics Dynamic Variables  📝

Prompts, topics,and image pre-prompt can include certain dynamic variables by including one of the following strings:

- `{botname}` - the bot's current nickname or username
- `{botowner}` - the bot owner's username
- `{authorname}` - the author of the message the bot is activated on
- `{authortoprole}` - the author's highest role
- `{authormention}` - the author's mention in string format
- `{serveremojis}` - all of the server emojis, in a string format (eg. `<:emoji:12345> <:emoji2:78912>`)
- `{servername}` - the server name
- `{channelname}` - the current channel name
- `{channeltopic}` - the current channel description/topic
- `{currentdate}` - the current date eg. 2023/08/31 (based on host timezone)
- `{currentweekday}` - the current weekday eg. Monday (based on host timezone)
- `{currenttime}` - the current 24-hour time eg. 21:59 (based on host timezone)
- `{randomnumber}` - a random number between 0 - 100


Remove list regex patterns only support `{authorname}` (will use authors of last 10 messages) and `{botname}` placeholders.

---

