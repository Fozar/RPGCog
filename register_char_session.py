import asyncio
import re

import discord
from discord import Embed
from discord.ext import commands
from redbot.core.utils.chat_formatting import italics
from redbot.core.utils.predicates import MessagePredicate, ReactionPredicate

from .config import config


class RegisterSession:
    """Class to run member character registration.

    Attributes:
        ctx (commands.Context): Context object from which this session will be run.
            This object assumes the session was started by `ctx.author`.
        char (dict): Dictionary to transfer information about the character in the
            database.
        complete (bool): This attribute indicates whether the registration is
            completed successfully or canceled.
        embed (Embed): Embedded message, which is a registration form.
        message (discord.Message): The message object that contains the registration
            form.

    """

    def __init__(self, ctx: commands.Context):
        self.ctx = ctx
        self.char = {}
        self.complete = False
        self._task = None
        self.embed = discord.Embed(
            title="Создание персонажа", colour=discord.Colour(0xF5A623)
        )
        self.embed.set_author(name=config.bot.name, icon_url=config.bot.icon_url)
        self.embed.set_footer(text="Создание персонажа")
        self.message = None

    @classmethod
    def start(cls, ctx: commands.Context):
        """Creates and starts registration session.

        This allows the session to manage the running and cancellation of its
        own tasks.

        Args:
            ctx (commands.Context): Same as `RegisterSession.ctx`

        Returns:
            RegisterSession: The new registration session being run.

        """
        session = cls(ctx)
        loop = ctx.bot.loop
        session._task = loop.create_task(session.run(ctx))
        return session

    async def run(self, ctx: commands.Context):
        """Runs the registration sessions.

        In order for the registration session to be stopped correctly, this
        should only be called internally by `RegisterSession.start`.

        Args:
            ctx (commands.Context): Same as `RegisterSession.ctx`
        """
        self.message = await ctx.send(embed=self.embed)
        self.char["member_id"] = str(ctx.author.id)
        for stage in [
            self.name_select,
            self.race_select,
            self.sex_select,
            self.desc_select,
        ]:
            continue_ = await stage(ctx, self.embed, self.message)
            if not continue_:
                break
        else:
            self.complete = True
            self.embed.title = "Персонаж создан!"
            await self.message.edit(embed=self.embed)
            self.stop()

    def stop(self):
        """Stops the registration session."""
        self.ctx.bot.dispatch("register_end", self)

    def force_stop(self):
        """Cancels whichever tasks this session is running."""
        self._task.cancel()

    async def cancel(self, embed: Embed = None, message: discord.Message = None):
        """Cancels registration and displays information about it.

        Args:
            embed (Embed): Same as `RegisterSession.embed`
            message (discord.Message): Same as `RegisterSession.message`
        """
        if not embed:
            embed = self.embed
        if not message:
            message = self.message
        embed.clear_fields()
        embed.description = "Создание персонажа отменено."
        await message.edit(embed=embed)
        self.stop()

    async def name_select(
        self,
        ctx: commands.Context,
        embed: Embed,
        message: discord.Message,
        do_once: bool = True,
    ) -> bool:
        """Requests information from the member about the name of the
        character being registered.

        Args:
            ctx (commands.Context): Same as `RegisterSession.ctx`
            embed (Embed): Same as `RegisterSession.embed`
            message (discord.Message): Same as `RegisterSession.message`
            do_once (bool): The parameter allows not to perform actions that
                are not needed during a recursive method call.

        Returns:
            bool: Whether the correct information is received or not.

        """
        if do_once:
            embed.description = (
                "**Выберите имя персонажа**\n\n"
                "В имени персонажа должно быть **не менее 3** и **не более 25 символов**.\n"
                "Имя персонажа должно состоять из символов **латинского алфавита** или **кириллицы.**"
            )
            await message.edit(embed=embed)
            do_once = False
        try:
            name = await self.ctx.bot.wait_for(
                "message", timeout=60.0, check=MessagePredicate.same_context(ctx)
            )
            name_content = name.content
            await name.delete()
            if not re.match("""^[a-zа-яA-ZА-ЯёЁ\s]{3,25}$""", name_content):
                incorrect = await ctx.send("Недопустимый ввод!")
                name_select = await self.name_select(ctx, embed, message, do_once)
                await incorrect.delete()
                if name_select:
                    return True
                else:
                    await self.cancel(embed, message)
                    return False
            self.char["name"] = name_content
            embed.add_field(name="Имя", value=name_content, inline=True)
            await message.edit(embed=embed)
            return True
        except asyncio.TimeoutError:
            await self.cancel(embed, message)
            return False

    async def race_select(
        self,
        ctx: commands.Context,
        embed: Embed,
        message: discord.Message,
        do_once: bool = True,
    ) -> bool:
        """Requests information from the member about the race of the
        character being registered.

        Args:
            ctx (commands.Context): Same as `RegisterSession.ctx`
            embed (Embed): Same as `RegisterSession.embed`
            message (discord.Message): Same as `RegisterSession.message`
            do_once (bool): The parameter allows not to perform actions that
                are not needed during a recursive method call.

        Returns:
            bool: Whether the correct information is received or not.

        """
        _config = config.humanize
        races = [race["name"] for race in _config.races.values()]
        if do_once:
            embed.description = (
                "**Выберите расу персонажа**\n\n"
                f"**Возможные варианты:** {', '.join(races)}."
            )
            await message.edit(embed=embed)
            do_once = False
        try:
            race = await self.ctx.bot.wait_for(
                "message", timeout=60.0, check=MessagePredicate.same_context(ctx)
            )
            race_content = race.content.lower()
            await race.delete()
            if race_content not in races:
                incorrect = await ctx.send("Недопустимый ввод!")
                race_select = await self.race_select(ctx, embed, message, do_once)
                await incorrect.delete()
                if race_select:
                    return True
                else:
                    await self.cancel(embed, message)
                    return False
            self.char["race"] = list(_config.races.keys())[
                list(_config.races.values()).index(race_content)
            ]
            embed.add_field(name="Раса", value=race_content.title(), inline=True)
            await message.edit(embed=embed)
            return True
        except asyncio.TimeoutError:
            await self.cancel(embed, message)
            return False

    async def sex_select(
        self, ctx: commands.Context, embed: Embed, message: discord.Message
    ) -> bool:
        """Requests information from the member about the sex of the
        character being registered.

        Args:
            ctx (commands.Context): Same as `RegisterSession.ctx`
            embed (Embed): Same as `RegisterSession.embed`
            message (discord.Message): Same as `RegisterSession.message`

        Returns:
            bool: Whether the correct information is received or not.

        """
        embed.description = "**Выберите пол персонажа**\n\n"
        await message.edit(embed=embed)
        genders = {"👨": "male", "👩": "female"}
        try:

            for gender in genders.keys():
                await message.add_reaction(gender)
            react, member = await self.ctx.bot.wait_for(
                "reaction_add",
                timeout=60.0,
                check=ReactionPredicate.with_emojis(
                    tuple(genders.keys()), message, ctx.author
                ),
            )
            await message.clear_reactions()
            self.char["sex"] = genders[react.emoji]
            embed.add_field(
                name="Пол",
                value=config.humanize.genders[genders[react.emoji]].title(),
                inline=True,
            )
            await message.edit(embed=embed)
            return True
        except asyncio.TimeoutError:
            try:
                await message.clear_reactions()
            except discord.Forbidden:  # cannot remove all reactions
                for gender in genders.keys():
                    await message.remove_reaction(gender, ctx.bot.user)
            except discord.NotFound:
                return False
            await self.cancel(embed, message)
            return False

    async def desc_select(
        self,
        ctx: commands.Context,
        embed: Embed,
        message: discord.Message,
        do_once: bool = True,
    ) -> bool:
        """Requests information from the member about the description of the
        character being registered.

        Args:
            ctx (commands.Context): Same as `RegisterSession.ctx`
            embed (Embed): Same as `RegisterSession.embed`
            message (discord.Message): Same as `RegisterSession.message`
            do_once (bool): The parameter allows not to perform actions that
                are not needed during a recursive method call.

        Returns:
            bool: Whether the correct information is received or not.

        """
        if do_once:
            embed.description = (
                "**Опишите своего персонажа**\n\n"
                "В описании персонажа должно быть **не менее 50** и **не более 2000 символов**.\n"
                "Описание персонажа должно состоять из символов **латинского алфавита** или **кириллицы.**"
            )
            await message.edit(embed=embed)
            do_once = False
        try:
            desc = await self.ctx.bot.wait_for(
                "message", timeout=600.0, check=MessagePredicate.same_context(ctx)
            )
            desc_content = desc.content
            await desc.delete()
            if not re.match(
                """[a-zа-яA-ZА-ЯёЁ\d\s!.,%*'";:()\[\]<>\-«»—]{50,2000}""", desc_content
            ):
                incorrect = await ctx.send("Недопустимый ввод!")
                desc_select = await self.desc_select(ctx, embed, message, do_once)
                await incorrect.delete()
                if desc_select:
                    return True
                else:
                    await self.cancel(embed, message)
                    return False
            self.char["desc"] = desc_content
            embed.description = italics(desc_content)
            await message.edit(embed=embed)
            return True
        except asyncio.TimeoutError:
            await self.cancel(embed, message)
            return False
