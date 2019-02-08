import asyncio
import re
from pathlib import Path
from typing import Union

import aiosqlite
import discord
from redbot.core.bot import Red
from redbot.core.commands import commands
from redbot.core.utils.predicates import MessagePredicate
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Cog = getattr(commands, "Cog", object)

MAIN_DB = Path('C:\\Users\\fozar\\AppData\\Local\\Red-DiscordBot\\Red-DiscordBot\\cogs\\CogManager\\cogs\\RPGCog\\db'
               '\\Main.db')
engine = create_engine('sqlite:///C:\\Users\\fozar\\AppData\\Local\\Red-DiscordBot\\Red-DiscordBot\\cogs\\CogManager'
                       '\\cogs\\RPGCog\\db\\Main.db')

Base = declarative_base()


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


class Member(Base):
    """ Класс персонажа """

    __tablename__ = 'members'
    id = Column(Integer, primary_key=True)
    member_id = Column(String)
    name = Column(String)
    race = Column(String)
    sex = Column(String)
    description = Column(String)
    lvl = Column(Integer)
    xp = Column(Integer)

    def __init__(self, member_id, name, race, sex, description, lvl, xp):
        self.member_id = member_id  # ID участника
        self.name = name  # Имя персонажа
        self.race = race  # Раса персонажа
        self.sex = sex  # Пол персонажа
        self.description = description  # Описание персонажа
        self.lvl = lvl  # Уровень персонажа
        self.xp = xp  # Опыт персонажа
        # self.inventory = Inventory  # Инвентарь персонажа


"""
class Inventory:
    

    def __init__(self):
        self.helmet = Armor  # Экипированный шлем
        self.cuirass = Armor  # Экипированная броня
        self.gauntlets = Armor  # Экипированные перчатки
        self.boots = Armor  # Экипированные сапоги
        self.weapon = Weapon  # Экипированное оружие
        self.shield = Armor  # Экипированный щит
        self.items = []  # Список предметов


class Item:
   

    def __init__(self, name, description, price, rarity, loot, count, stolen, maker):
        self.name = name  # Название предмета
        self.description = description  # Описание предмета
        self.price = price  # Цена предмета
        self.rarity = rarity  # Редкость предмета
        self.loot = loot  # Может ли предмет найден в луте
        self.count = count  # Количество
        self.stolen = stolen  # Украден ли предмет
        self.maker = maker  # Создатель


class Armor(Item):
    

    def __init__(self, slot, kind, armor, name, description, price, rarity, loot, count, stolen, maker):
        super().__init__(name, description, price, rarity, loot, count, stolen, maker)
        self.slot = slot  # Слот брони (шлем/кираса/сапоги/перчатки)
        self.kind = kind  # Легкая/тяжелая/тряпки
        self.armor = armor  # Класс брони


class Weapon(Item):
    

    def __init__(self, melee, hands, type, damage, name, description, price, rarity, loot, count, stolen, maker):
        super().__init__(name, description, price, rarity, loot, count, stolen, maker)
        self.melee = melee  # Ближний или дальний бой
        self.hands = hands  # Сколько рук занимает
        self.type = type  # Тип оружия
        self.damage = damage  # Урон
"""


class RPGCog(Cog):
    """ RPG Cog """

    def __init__(self, bot: Red):
        self.main_db = Database(MAIN_DB)
        self.Red = bot
        self.MemberClass = Member
        self.members = {}
        self.CharSessions = []
        session_m = sessionmaker(bind=engine)
        self.session = session_m()
        Base.metadata.create_all(engine)

    @commands.group(invoke_without_command=True)
    async def char(self, ctx, member: Union[discord.Member, discord.User] = None):
        """ Информация о персонаже """

        author = ctx.author
        if member is None:
            member = author
        member_id = str(member.id)
        char = self.session.query(Member).filter_by(member_id=member_id).first()
        if char:
            name = char.name
            race = char.race
            sex = char.sex
            desc = char.description
            lvl = char.lvl
            xp = char.xp

            embed = discord.Embed(title="{}".format(name), colour=discord.Colour(0xd0021b),
                                  description="{}".format(desc))

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
        char = self.session.query(Member).filter_by(member_id=member_id).first()
        if char:
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
            elif not re.match("^[a-zа-яA-ZА-ЯёЁ][a-zA-Zа-яА-ЯёЁ '-]+$", name.content):
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
            if race.content.lower() in ["аргонианин", "бретонец", "данмер", "альтмер", "имперец", "каджит", "норд",
                                        "орк", "редгард", "босмер", "отмена"]:
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
            elif not re.match("""^[a-zа-яA-ZА-ЯёЁ][a-zA-Zа-яА-ЯёЁ !?:;"'.,-]+$""", description.content):
                await ctx.send("{}, введены недопустимые символы. Повторите попытку.\n"
                               "Для отмена введите \"отмена\".".format(member.mention))
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
        member_c = self.MemberClass(member_id=member_id, name=name_c, race=race_c, sex=sex_c, description=description_c,
                                    lvl=1, xp=0)
        self.session.add(member_c)  # Занесение персонажа в базу данных
        self.session.commit()
        await ctx.send("{}, ваш персонаж {} создан!".format(member.mention, name_c))
        if ctx in self.CharSessions:
            self.CharSessions.remove(ctx)
        print("Создан новый персонаж: {}".format(name_c))

    @char.command(name="delete", aliases=["del"])
    async def char_delete(self, ctx):
        """ Удалить персонажа """

        member = ctx.author
        member_id = str(member.id)

        char = self.session.query(Member).filter_by(member_id=member_id).first()
        if char:
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
                self.session.query(Member).filter_by(member_id=member_id).delete()
                self.session.commit()
                await ctx.send("{}, ваш персонаж удален. "
                               "Введите '{}char new', чтобы создать нового.".format(member.mention, ctx.prefix))
            else:
                await ctx.send("{}, удаление персонажа отменено.".format(member.mention))
        else:
            await ctx.send("{}, у вас нет персонажа. "
                           "Введите '{}char new', чтобы создать".format(member.mention, ctx.prefix))
