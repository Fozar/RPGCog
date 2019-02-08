import asyncio
import datetime
import re
from pathlib import Path
from typing import Union

import aiosqlite
import discord
from redbot.core.bot import Red
from redbot.core.commands import commands
from redbot.core.utils.predicates import MessagePredicate

Cog = getattr(commands, "Cog", object)

MAIN_DB = Path('C:\\Users\\fozar\\AppData\\Local\\Red-DiscordBot\\Red-DiscordBot\\cogs\\CogManager\\cogs\\RPGCog\\db'
               '\\Main.db')


class Database:
    """ Класс базы данных """

    def __init__(self, file):
        self.file = file

    async def query(self, sql):
        async with aiosqlite.connect(self.file) as db:
            await db.execute(sql)
            await db.commit()

    async def fetch(self, sql):
        async with aiosqlite.connect(self.file) as db:
            cursor = await db.execute(sql)
            rows = await cursor.fetchall()
            await cursor.close()
            return rows


class Member:
    """ Класс персонажа """

    def __init__(self, name, race, sex, description, lvl, xp):
        self.name = name  # Имя персонажа
        self.race = race  # Раса персонажа
        self.sex = sex  # Пол персонажа
        self.description = description  # Описание персонажа
        self.lvl = lvl  # Уровень персонажа
        self.xp = xp  # Опыт персонажа


class Inventory:
    """ Класс инвентаря """

    def __init__(self, item, count, stolen, maker):
        self.item = item  # Предмет
        self.count = count  # Количество
        self.stolen = stolen  # Украден ли предмет
        self.maker = maker  # Создатель


class Item:
    """ Класс предмета """

    def __init__(self, name, price, rarity, loot):
        self.name = name  # Название предмета
        self.price = price  # Цена предмета
        self.rarity = rarity  # Редкость предмета
        self.loot = loot  # Может ли предмет найден в луте


class Armor(Item):
    """ Класс брони """

    def __init__(self, slot, kind, armor, name, price, rarity, loot):
        super().__init__(name, price, rarity, loot)
        self.slot = slot  # Слот брони (шлем/кираса/сапоги/перчатки)
        self.kind = kind  # Легкая/тяжелая/тряпки
        self.armor = armor  # Класс брони


class Weapon(Item):
    """ Класс оружия """

    def __init__(self, melee, hands, kind, damage, name, price, rarity, loot):
        super().__init__(name, price, rarity, loot)
        self.melee = melee  # Ближний или дальний бой
        self.hands = hands  # Сколько рук занимает
        self.kind = kind  # Тип оружия
        self.damage = damage  # Урон


class RPGCog(Cog):
    """ RPG Cog """

    def __init__(self, bot: Red):
        self.main_db = Database(MAIN_DB)
        self.Red = bot
        self.MemberClass = Member
        self.members = {}
        self.CharSessions = []
        bot.loop.create_task(self.setup())

    async def setup(self):
        await self.Red.wait_until_ready()

        loaded_members = await self.main_db.fetch(f'SELECT * FROM members')
        for member_id, name, race, sex, description, lvl, xp in loaded_members:
            self.members[member_id] = self.MemberClass(name=name,
                                                       race=race,
                                                       sex=sex,
                                                       description=description,
                                                       lvl=lvl,
                                                       xp=xp)

        print("Участники загружены")

    async def delete_member(self, member_id):
        del self.members[member_id]
        await self.main_db.query(f'DELETE FROM members WHERE member_id={member_id}')

    @commands.group(invoke_without_command=True)
    async def char(self, ctx, member: Union[discord.Member, discord.User] = None):
        """ Информация о персонаже """

        author = ctx.author
        if member is None:
            member = author
        member_id = str(member.id)

        if member_id in self.members:
            name = self.members.get(member_id).name
            race = self.members.get(member_id).race
            sex = self.members.get(member_id).sex
            desc = self.members.get(member_id).description
            lvl = self.members.get(member_id).lvl
            xp = self.members.get(member_id).xp

            embed = discord.Embed(title="{}".format(name), colour=discord.Colour(0xd0021b),
                                  description="{}".format(desc),
                                  timestamp=datetime.datetime.utcfromtimestamp(1549457010))

            embed.set_footer(text="Информация о персонаже")

            embed.add_field(name="Характеристики",
                            value="**Раса:**           {}\n"
                                  "**Пол:**            {}\n"
                                  "**Уровень:**        {}\n"
                                  "**Опыт:**           {}".format(race, sex, lvl, xp))

            await ctx.send(embed=embed)
        else:
            await ctx.send("{}, персонаж не найден.".format(ctx.author.mention))
            await ctx.send_help()

    @char.command(name="new")
    async def char_new(self, ctx):
        """ Создать персонажа """

        member = ctx.author
        member_id = str(member.id)

        # Проверка открытой сессии регистрации
        if next((session for session in self.CharSessions if session.author.id == ctx.author.id), None):
            return

        # Проверка регистрации
        if member_id in self.members:
            await ctx.send("{}, у вас уже есть персонаж. "
                           "Введите {}char delete, чтобы удалить его.".format(member.mention, ctx.prefix))
            return

        self.CharSessions.append(ctx)

        # Выбор имени
        await ctx.send("{}, введите имя нового персонажа.\n"
                       "Для отмены введите \"отмена\".".format(member.mention))

        async def name_select():
            try:
                name = await self.Red.wait_for("message", timeout=60.0, check=MessagePredicate.same_context(ctx))
            except asyncio.TimeoutError:
                return "отмена"
            if len(name.content) < 3 or len(name.content) > 25:
                await ctx.send("{}, в имени персонажа должно быть не менее 3 и не более 20 символов. "
                               "Повторите попытку.\n"
                               "Для отмены введите \"отмена\".".format(member.mention))
                return await name_select()
            elif name.content.count(" ") > 2:
                await ctx.send("{}, имя персонажа не должно содержать больше 2 пробелов. "
                               "Повторите попытку.\n"
                               "Для отмены введите \"отмена\".".format(member.mention))
                return await name_select()
            elif re.match('^[a-zа-яA-ZА-ЯёЁ][a-zA-Zа-яА-Яё \'-]+$', name.content):
                await ctx.send("{}, введены недопустимые символы. Повторите попытку.\n"
                               "Для отмена введите \"отмена\".".format(member.mention))
                return await name_select()
            else:
                return name.content

        name_c = await name_select()
        if name_c.lower() == "отмена" in name_c.lower():
            await ctx.send("{}, создание персонажа отменено.".format(member.mention))
            if ctx in self.CharSessions:
                self.CharSessions.remove(ctx)
            return

        # Выбор расы
        await ctx.send("{}, выберите расу персонажа.\n"
                       "Возможные варианты:\n"
                       "\n"
                       "    Аргонианин\n"
                       "    Данмер\n"
                       "    Альтмер\n"
                       "    Имперец\n"
                       "    Каджит\n"
                       "    Норд\n"
                       "    Орк\n"
                       "    Редгард\n"
                       "    Босмер\n"
                       "\n"
                       "Для отмены введите \"отмена\".".format(member.mention))

        async def race_select():
            try:
                race = await self.Red.wait_for("message", timeout=60.0, check=MessagePredicate.same_context(ctx))
            except asyncio.TimeoutError:
                return "отмена"
            if race.content.lower() in ["аргонианин",
                                        "бретонец",
                                        "данмер",
                                        "альтмер",
                                        "имперец",
                                        "каджит",
                                        "норд",
                                        "орк",
                                        "редгард",
                                        "босмер",
                                        "отмена"]:
                return race.content.lower().title()
            else:
                await ctx.send("{}, не могу найти указанную расу. Повторите попытку.\n"
                               "Для отмены введите \"отмена\".".format(member.mention))
                return await race_select()

        race_c = await race_select()
        if race_c.lower() == "отмена":
            await ctx.send("{}, создание персонажа отменено.".format(member.mention))
            if ctx in self.CharSessions:
                self.CharSessions.remove(ctx)
            return

        # Выбор пола
        await ctx.send("{}, выберите пол персонажа (М/Ж).\n"
                       "\n"
                       "Для отмены введите \"отмена\".".format(member.mention))

        async def sex_select():
            try:
                sex = await self.Red.wait_for("message", timeout=600.0, check=MessagePredicate.same_context(ctx))
            except asyncio.TimeoutError:
                return "отмена"
            if sex.content.lower() in ["м", "муж", "мужской", "муж."]:
                return "Мужской"
            elif sex.content.lower() in ["ж", "жен", "женский", "жен."]:
                return "Женский"
            elif sex.content.lower() == "отмена":
                return sex.content
            else:
                await ctx.send("{}, не могу найти указанный пол. Повторите попытку.\n"
                               "Для отмены введите \"отмена\".".format(member.mention))
                return await sex_select()

        sex_c = await sex_select()
        if sex_c.lower() == "отмена":
            await ctx.send("{}, создание персонажа отменено.".format(member.mention))
            if ctx in self.CharSessions:
                self.CharSessions.remove(ctx)
            return

        # Описание персонажа
        try:
            await ctx.send("{}, опишите своего персонажа. Тут может быть описана внешность персонажа, его история, "
                           "привычки и другие особенности. Не стоит описывать снаряжение персонажа и другие "
                           "приобретаемые вещи. "
                           "\n\nВ описании персонажа должно быть не менее 50 и не более 1000 символов.\nДля отмены "
                           "введите \"отмена\".".format(member.mention))
        except asyncio.TimeoutError:
            return "отмена"

        async def desc_select():
            description = await self.Red.wait_for("message", check=MessagePredicate.same_context(ctx))
            if description.content.lower() == "отмена":
                return description.content
            elif len(description.content) < 50 or len(description.content) > 1000:
                await ctx.send("{}, в описании персонажа должно быть не менее 50 и не более 1000 символов. "
                               "Повторите попытку.\n"
                               "Для отмены введите \"отмена\".".format(member.mention))
                return await desc_select()
            else:
                return description.content

        description_c = await desc_select()
        if description_c.lower() == "отмена":
            await ctx.send("{}, создание персонажа отменено.".format(member.mention))
            if ctx in self.CharSessions:
                self.CharSessions.remove(ctx)
            return

        # Сохранение персонажа
        await self.main_db.query(
            f'INSERT INTO members (member_id, name, race, sex, description) VALUES '
            f'("{member_id}", "{name_c}", "{race_c}", "{sex_c}", "{description_c}")'
        )  # Занесение персонажа в базу данных
        self.members[member_id] = self.MemberClass(name=name_c,
                                                   race=race_c,
                                                   sex=sex_c,
                                                   description=description_c,
                                                   lvl=1,
                                                   xp=0)  # Занесение персонажа в словарь

        await ctx.send("{}, ваш персонаж {} создан!".format(member.mention, name_c))
        if ctx in self.CharSessions:
            self.CharSessions.remove(ctx)
        print("Создан новый персонаж: {}".format(name_c))

    @char.command(name="delete", aliases=["del"])
    async def char_delete(self, ctx):
        """ Удалить персонажа """

        member = ctx.author
        member_id = str(member.id)

        if member_id in self.members:
            await ctx.send("{}, вы уверены, что хотите удалить своего персонажа?\n"
                           "\n"
                           "ВНИМАНИЕ: Это действие нельзя отменить. Все ваши предметы, уровень и достижения будут "
                           "потеряны безвозвратно.".format(member.mention))

            try:
                msg = await self.Red.wait_for("message", timeout=30.0, check=MessagePredicate.same_context(ctx))
            except asyncio.TimeoutError:
                await ctx.send("{}, удаление персонажа отменено.".format(member.mention))
                return
            if msg.content.lower() in ["да", "д", "yes", "y"]:
                await self.delete_member(member_id)
                await ctx.send("{}, ваш персонаж удален. "
                               "Введите '{}char new', чтобы создать нового.".format(member.mention, ctx.prefix))
            else:
                await ctx.send("{}, удаление персонажа отменено.".format(member.mention))
        else:
            await ctx.send("{}, у вас нет персонажа. "
                           "Введите '{}char new', чтобы создать".format(member.mention, ctx.prefix))
