from __future__ import annotations

import discord
from aiuser.settings.utilities import build_prompt_pages, set_page_footers


class PromptEditModal(discord.ui.Modal, title="Edit prompt"):
    def __init__(self, view, max_length):
        super().__init__()
        self.view = view
        self.text = discord.ui.TextInput(
            label=f"Save to {view.scope_label}"[:45],
            style=discord.TextStyle.paragraph,
            default=view.prompt,
            max_length=max_length,
        )
        self.add_item(self.text)

    async def on_submit(self, interaction):
        if interaction.user.id != self.view.ctx.author.id:
            return await interaction.response.send_message(
                "This editor belongs to someone else.", ephemeral=True
            )
        prompt = str(self.text)
        cog = self.view.cog
        if len(
            prompt
        ) > await cog.config.max_prompt_length() and not await cog.bot.is_owner(
            interaction.user
        ):
            return await interaction.response.send_message(
                ":warning: Prompt too long. Max length is {max_prompt_length} characters.".format(
                    max_prompt_length=await cog.config.max_prompt_length()
                ),
                ephemeral=True,
            )
        await self.view.config_attr.custom_text_prompt.set(prompt)
        self.view.prompt = prompt
        cog.services.override_prompt_start_time[self.view.ctx.guild.id] = (
            interaction.created_at
        )
        await self.view.update_pages()
        await interaction.response.edit_message(
            embed=self.view.pages[0], view=self.view
        )


class PromptEditView(discord.ui.View):
    def __init__(self, cog, ctx, config_attr, prompt, scope_label, title):
        super().__init__(timeout=180)
        self.cog, self.ctx, self.config_attr = cog, ctx, config_attr
        self.prompt, self.scope_label = prompt, scope_label
        self.title = title
        self.pages = []
        self.page = 0
        self.message = None
        self.edit.label = f"Edit {scope_label}"[:80]

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass

    async def update_pages(self):
        self.pages = await build_prompt_pages(
            self.ctx, self.cog.services, self.title, self.prompt
        )
        if len(self.pages) > 1:
            set_page_footers(self.pages)
            if self.previous not in self.children:
                self.remove_item(self.edit)
                self.add_item(self.previous)
                self.add_item(self.next)
                self.add_item(self.edit)
        else:
            self.remove_item(self.previous)
            self.remove_item(self.next)
        self.page = 0
        self.previous.disabled = True
        self.next.disabled = len(self.pages) < 2
        if self.is_finished():
            for item in self.children:
                item.disabled = True

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction, button):
        self.page = max(0, self.page - 1)
        self.previous.disabled = self.page == 0
        self.next.disabled = self.page >= len(self.pages) - 1
        await interaction.response.edit_message(embed=self.pages[self.page], view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary)
    async def next(self, interaction, button):
        self.page = min(len(self.pages) - 1, self.page + 1)
        self.previous.disabled = self.page == 0
        self.next.disabled = self.page >= len(self.pages) - 1
        await interaction.response.edit_message(embed=self.pages[self.page], view=self)

    @discord.ui.button(label="Edit prompt", style=discord.ButtonStyle.secondary)
    async def edit(self, interaction, button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(
                "Only the person who opened this prompt can edit it.", ephemeral=True
            )
        if len(self.prompt) > 4000:
            return await interaction.response.send_message(
                "This prompt is too long for the editor. Use the prompt set command with a .txt file.",
                ephemeral=True,
            )
        is_owner = await self.cog.bot.is_owner(interaction.user)
        max_length = (
            4000 if is_owner else min(await self.cog.config.max_prompt_length(), 4000)
        )
        if len(self.prompt) > max_length:
            return await interaction.response.send_message(
                f"This prompt exceeds your {max_length}-character limit. Use the prompt set command to replace it with a shorter prompt.",
                ephemeral=True,
            )
        await interaction.response.send_modal(PromptEditModal(self, max_length))
