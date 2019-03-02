import asyncio
import inspect
import random

import re
from itertools import cycle
from operator import itemgetter
from typing import Union

from mongoengine import *
import discord
from redbot.core import checks
from redbot.core.bot import Red
from redbot.core.commands import commands
from redbot.core.utils.predicates import MessagePredicate

from .config import config

Cog = getattr(commands, "Cog", object)

INV_CATEGORIES = {"Item.Weapon": "ОРУЖИЕ", "Item.Armor": "БРОНЯ", "Item": "ДРУГОЕ"}
SHOWN_STATS = {
    "rarity": "Редкость",
    "damage": "Урон",
    "armor": "Броня",
    "price": "Цена",
}
RACES = {
    "Аргонианин": "argonian",
    "Бретонец": "breton",
    "Имперец": "imperial",
    "Каджит": "khajit",
    "Норд": "nord",
    "Орк": "orc",
    "Редгард": "redguard",
    "Данмер": "dunmer",
    "Альтмер": "altmer",
    "Босмер": "bosmer",
}
STATUS = [
    "Коллегии Бардов",
    "Гарцующей кобыле",
    "Пчеле и жале",
    "Смеющейся крысе",
    "Спящем великане",
    "Буйной фляге",
    "Замершем очаге",
    "Мертвецком меде",
    "Вайлмире",
    "Деревянном кружеве",
    "Мороденном фрукте",
    "Ночных воротах",
    "Очаге и свече",
    "Пике ветров",
    "Серебряной Крови",
    "Старом Хролдане",
    "Четырех щитах",
]


class Inventory(EmbeddedDocument):
    """ Inventory Class """

    items = ListField(DictField(), default=[])

    def __init__(self, items, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.items = items  # Items list

    def is_item_exists(self, item):
        return next(
            (_item for _item in self.items if _item["item_id"] == item.item_id), False
        )

    # Add item to inventory
    def add_item(self, item, count):
        item_exists = self.is_item_exists(item)
        if item_exists:
            item_exists["count"] += count
        else:
            new_item = {"item_id": item.id, "count": count}
            self.items.append(new_item)
        self.items[:] = [item for item in self.items if item.get("count") > 0]

    # Remove item from inventory
    def remove_item(self, item, count):
        item_exists = self.is_item_exists(item)
        if item_exists:
            item_exists["count"] -= count
            self.items[:] = [item for item in self.items if item.get("count") > 0]
            if len(self.items) < 1:
                blank_item = {"item_id": "", "count": 0}
                self.items.append(blank_item)


class Attributes(EmbeddedDocument):
    """ Character Attribute Class """

    health = FloatField(default=10)
    stamina = FloatField(default=10)
    magicka = FloatField(default=10)
    main = DictField(FloatField())
    armor_rating = IntField(default=0)

    def __init__(self, main, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.main = main

    def mod_value(self, value, damage):
        total = self.main[f"{value}_max"] + self.main[f"{value}_buff"]
        attr = getattr(self, value)
        if attr + damage <= total:
            setattr(self, value, attr + damage)
            attr = getattr(self, value)
            if attr > total:
                setattr(self, value, total)
            elif attr < 1:
                setattr(self, value, 0)
        else:
            setattr(self, value, total)

    def birth(self):
        self.health = self.main["health_max"]
        self.stamina = self.main["stamina_max"]
        self.magicka = self.main["magicka_max"]


class Character(Document):
    """ Character Class

        :param member_id: ID участника
        :param name: Character name
        :param race: Character race
        :param sex: Character sex
        :param description: Character description
        :param attributes: Character attributes

    """

    member_id = StringField(primary_key=True)
    name = StringField(max_length=25)
    race = StringField()
    sex = StringField()
    description = StringField(max_length=1000)
    lvl = IntField(default=1)
    xp = IntField(default=0)
    xp_factor = FloatField(default=1.0)
    inventory = EmbeddedDocumentField(Inventory)
    attributes = EmbeddedDocumentField(Attributes)

    def __init__(
        self,
        member_id,
        name,
        race,
        sex,
        description,
        inventory,
        attributes,
        *args,
        **values,
    ):
        super().__init__(*args, **values)
        self.member_id = member_id
        self.name = name
        self.race = race
        self.sex = sex
        self.description = description
        self.inventory = inventory
        self.attributes = attributes

    def lvl_up(self):
        self.lvl += 1
        self.xp = 0


class Item(Document):
    """ Item Class """

    item_id = IntField(primary_key=True)
    name = StringField()
    description = StringField()
    price = IntField()
    rarity = StringField()

    def __init__(self, item_id, name, description, price, rarity, *args, **values):
        super().__init__(*args, **values)
        self.item_id = item_id  # Item ID
        self.name = name  # Item name
        self.description = description  # Item description
        self.price = price  # Item price
        self.rarity = rarity  # Item rarity

    meta = {"allow_inheritance": True}


class Armor(Item):
    """ Armor Class """

    armor_kinds = (
        ("heavy", "Тяжелая броня"),
        ("light", "Легкая броня"),
        ("clothing", "Одежда"),
    )
    slots = (
        ("helmet", "Шлем"),
        ("cuirass", "Броня"),
        ("boots", "сапоги"),
        ("gauntlets", "перчатки"),
    )

    slot = StringField()
    kind = StringField()
    armor = IntField()

    def __init__(
        self,
        item_id,
        name,
        description,
        price,
        rarity,
        slot=None,
        kind=None,
        armor=0,
        *args,
        **values,
    ):
        super().__init__(item_id, name, description, price, rarity, *args, **values)
        self.slot = slot  # Armor slot
        self.kind = kind  # Light/Heavy/Clothing
        self.armor = armor  # Armor rating


class Weapon(Item):
    """ Weapon Class """

    attack_types = (("melee", "Ближний бой"), ("range", "Дальний бой"))
    weapon_types = (
        ("crossbow", "Арбалет"),
        ("bow", "Лук"),
        ("greatsword", "Двуручный меч"),
        ("battleaxe", "Секира"),
        ("warhammer", "Боевой молот"),
        ("sword", "Меч"),
        ("war_axe", "Боевой топор"),
        ("mace", "Булава"),
        ("dagger", "Кинжал"),
    )

    attack_type = StringField(choices=attack_types)
    hands = IntField()
    weapon_type = StringField(choices=weapon_types)
    damage = IntField()

    def __init__(
        self,
        item_id,
        name,
        description,
        price,
        rarity,
        attack_type=None,
        hands=0,
        weapon_type=None,
        damage=0,
        *args,
        **values,
    ):
        super().__init__(item_id, name, description, price, rarity, *args, **values)
        self.attack_type = attack_type  # Attack type
        self.hands = hands  # How many hands does it take
        self.weapon_type = weapon_type  # Weapon type
        self.damage = damage  # Weapon damage


class RPGCog(Cog):
    """ RPG Cog """

    def __init__(self, bot: Red):
        self.Red = bot
        self.CharacterClass = Character
        self.InventoryClass = Inventory
        self.AttributesClass = Attributes
        self.ItemClass = Item
        self.ArmorClass = Armor
        self.WeaponClass = Weapon
        self.CharSessions = []
        self.Red.loop.create_task(self.setup())
        self.Red.loop.create_task(self.change_status())
        self.Red.loop.create_task(self.update_chars())

    async def setup(self):
        await self.Red.wait_until_ready()

        connect(
            db=config.database.db,
            host=config.database.host,
            port=config.database.port,
            username=config.database.user,
            password=config.database.password,
        )

        print("RPGCog loaded")

    async def change_status(self):
        await self.Red.wait_until_ready()
        status = STATUS[:]
        random.shuffle(status)
        statuses = cycle(status)

        while not self.Red.is_closed():
            await self.Red.change_presence(activity=discord.Game(name=next(statuses)))
            await asyncio.sleep(random.randint(10800, 32400))

    async def update_chars(self):
        await self.Red.wait_until_ready()
        timer = 5
        while not self.Red.is_closed():
            # Attributes regeneration
            chars = self.CharacterClass.objects()
            for char in chars:
                char.attributes.mod_value(
                    "health",
                    char.attributes.main["health_max"]
                    * char.attributes.main["health_regen"]
                    * timer
                    / 100,
                )
                char.attributes.mod_value(
                    "stamina",
                    char.attributes.main["stamina_max"]
                    * char.attributes.main["stamina_regen"]
                    * timer
                    / 100,
                )
                char.attributes.mod_value(
                    "magicka",
                    char.attributes.main["magicka_max"]
                    * char.attributes.main["magicka_regen"]
                    * timer
                    / 100,
                )
                char.save()
            await asyncio.sleep(timer)

    @commands.command(name="inventory", aliases=["inv"])
    async def inventory(self, ctx, member: Union[discord.Member, discord.User] = None):
        """ Инвентарь персонажа """

        author = ctx.author
        if member is None:
            member = author
        member_id = str(member.id)

        char = self.CharacterClass.objects(member_id=member_id).first()
        if not char:
            await ctx.send(f"{author.mention}, персонаж не найден.")
            return

        embed = discord.Embed(
            title=f"Инвентарь персонажа {char.name}", colour=discord.Colour(0x8B572A)
        )
        embed.set_author(name=config.bot.name, icon_url=config.bot.icon_url)
        embed.set_footer(text="Инвентарь персонажа")

        async def empty_inventory():
            embed.description = "Инвентарь пуст."
            await ctx.send(embed=embed)

        if not char.inventory.items:
            await empty_inventory()
            return

        item_lists = {}  # Списки предметов по категориям
        for category in INV_CATEGORIES:
            item_lists[category] = []

        for item in char.inventory.items:
            count = item["count"]
            if item and count > 0:
                _item = self.ItemClass.objects(item_id=item["item_id"]).first()
                stats = {"count": count}
                for stat in _item:
                    stats[stat] = _item[stat]
                item_lists[_item["_cls"]].append(stats)
            else:
                await empty_inventory()
                return

        def add_category(_embed, _category_name, _items):
            _embed.add_field(
                name="=" * 58,
                value=f"**```fix\n[{_category_name}] ({len(_items)})\n```**",
                inline=False,
            )
            for _stats in _items:
                text = "```autohotkey\n"
                for _stat in SHOWN_STATS:
                    if _stat in _stats:
                        text += f"{SHOWN_STATS[_stat]}: {_stats[_stat]}\n"
                text += "```"
                embed.add_field(
                    name=f"{_stats['name']} ({_stats['count']})",
                    value=text,
                    inline=True,
                )

        for category in item_lists:
            if item_lists[category]:
                item_lists[category][:] = sorted(
                    item_lists[category], key=itemgetter("name")
                )
                add_category(embed, INV_CATEGORIES[category], item_lists[category])

        await ctx.send(embed=embed)

    @commands.group(invoke_without_command=True)
    async def item(self, ctx, *, item_name):
        """ Информация о предмете """

        if not item_name:
            await ctx.send_help()
            return

        author = ctx.author
        _items = self.ItemClass.objects(name=item_name)
        if not _items:
            await ctx.send(f"{author.mention}, предмет не найден.")
        elif len(_items) > 1:
            await ctx.send(
                f"{author.mention}, найдено больше одного предмета с указанным именем. "
                "Сообщите об этом администратору."
            )
        else:
            _item = _items.first()
            if "редк" in _item.rarity.lower():
                color = discord.Colour(0xA56B6)  # Цвет редкого предмета (синий)
            elif "эпическ" in _item.rarity.lower():
                color = discord.Colour(
                    0x9013FE
                )  # Цвет эпического предмета (фиолетовый)
            elif "леген" in _item.rarity.lower():
                color = discord.Colour(0xFFD700)  # Цвет легендарного предмета (золотой)
            else:
                color = discord.Colour(0xFFFFFF)  # Цвет обычных предметов (белый)
            embed = discord.Embed(
                title=f"{_item.name}",
                colour=color,
                description=f"*{_item.description}*",
            )

            embed.set_author(name=config.bot.name, icon_url=config.bot.icon_url)
            embed.set_footer(text="Информация о предмете")
            for stat in SHOWN_STATS:
                if stat in _item:
                    embed.add_field(
                        name=SHOWN_STATS[stat], value=f"{_item[stat]}", inline=True
                    )

            await ctx.send(embed=embed)

    @checks.admin_or_permissions()
    @item.command(name="new", invoke_without_command=True)
    async def item_new(
        self, ctx, item_type, item_name, description, price, rarity, *args
    ):
        """ Добавить новый предмет

        **- item_type:** Тип предмета. Возможные значения: item/weapon/armor
        **- item_name:** Название предмета
        **- description:** Описание предмета
        **- price:** Стоимость предмета
        **- rarity:** Редкость предмета
        **- args:** Дополнительные аргументы для разных типов предметов.
            **-- Оружие:**
                **--- attack_type:** Тип атаки
                **--- hands:** Количество рук
                **--- type:** Тип оружия
                **--- damage:** Наносимый урон
            **-- Броня:**
                **--- slot:** Слот брони
                **--- kind:** Тип брони
                **--- armor:** Класс брони
        """

        try:
            item_id = int(self.ItemClass.objects.order_by("-_id").first().item_id) + 1
        except AttributeError:
            item_id = 1

        new_item = globals()[item_type.title()](
            item_id=item_id,
            name=item_name,
            description=description,
            price=price,
            rarity=rarity,
        )
        signature = list(inspect.getfullargspec(new_item.__init__).args)
        if args:
            for arg, value in zip(signature[len(signature) - len(args):], list(args)):
                setattr(new_item, arg, value)

        new_item.save()
        await ctx.send(f"{ctx.author.mention}, предмет создан!")

    @checks.admin_or_permissions()
    @item.command(name="add", pass_context=True)
    async def item_add(
        self,
        ctx,
        member: Union[discord.Member, discord.User] = None,
        count=1,
        *,
        item_name,
    ):
        """ Выдать предмет персонажу """

        author = ctx.author
        if member is None:
            member = author
        member_id = str(member.id)
        char = self.CharacterClass.objects(member_id=member_id).first()

        _items = self.ItemClass.objects(name=item_name)
        if not _items:
            await ctx.send(f"{author.mention}, предмет не найден.")
        elif len(_items) > 1:
            await ctx.send(
                f"{author.mention}, найдено больше одного предмета с указанным именем. "
                "Сообщите об этом администратору."
            )
        else:
            _item = _items.first()
            char.inventory.add_item(_item, count)
            char.save()
            await ctx.send(f"{author.mention}, предмет(ы) добавлен(ы).")

    @checks.admin_or_permissions()
    @item.command(name="remove", pass_context=True)
    async def item_remove(
        self,
        ctx,
        member: Union[discord.Member, discord.User] = None,
        count=1,
        *,
        item_name,
    ):
        """ Удалить предмет у персонажа """

        author = ctx.author
        if member is None:
            member = author
        member_id = str(member.id)
        char = self.CharacterClass.objects(member_id=member_id).first()

        _items = self.ItemClass.objects(name=item_name)

        if not _items:
            await ctx.send(f"{author.mention}, предмет не найден.")
            return
        elif len(_items) > 1:
            await ctx.send(
                f"{author.mention}, найдено больше одного предмета с указанным именем. "
                "Сообщите об этом администратору."
            )
        else:
            _item = _items.first()
            char.inventory.remove_item(_item, count)
            char.save()
            if len(char.inventory.items) < 1:
                inv = self.InventoryClass([])
                char.inventory = inv
                char.save()
            await ctx.send(f"{author.mention}, предмет(ы) удален(ы).")

    @commands.command(aliases=["stats"])
    async def statistics(self, ctx, member: Union[discord.Member, discord.User] = None):
        """ Характеристики персонажа """

        author = ctx.author
        if member is None:
            member = author
        member_id = str(member.id)
        char = self.CharacterClass.objects(member_id=member_id).first()

        if not char:
            await ctx.send(f"{author.mention}, персонаж не найден.")
            return

        embed = discord.Embed(
            title=f"Характеристики персонажа {char.name}",
            colour=discord.Colour(0xC7C300),
        )

        embed.set_author(name=config.bot.name, icon_url=config.bot.icon_url)
        embed.set_footer(text="Характеристики персонажа")

        embed.add_field(
            name="Магия",
            value=f"{int(char.attributes.magicka)}/{int(char.attributes.magicka_max+char.attributes.magicka_buff)}",
            inline=True,
        )
        embed.add_field(
            name="Здоровье",
            value=f"{int(char.attributes.health)}/{int(char.attributes.health_max+char.attributes.health_buff)}",
            inline=True,
        )
        embed.add_field(
            name="Запас сил",
            value=f"{int(char.attributes.stamina)}/{int(char.attributes.stamina_max+char.attributes.stamina_buff)}",
            inline=True,
        )
        embed.add_field(
            name="Класс брони",
            value=f"{int(char.attributes.armor_rating)}",
            inline=True,
        )

        await ctx.send(embed=embed)

    @commands.group(invoke_without_command=True)
    async def char(self, ctx, member: Union[discord.Member, discord.User] = None):
        """ Информация о персонаже """

        author = ctx.author
        if member is None:
            member = author
        member_id = str(member.id)
        char = self.CharacterClass.objects(member_id=member_id).first()

        if not char:
            await ctx.send(f"{author.mention}, персонаж не найден.")
            await ctx.send_help()
        else:
            name = char.name
            race = char.race
            sex = char.sex
            desc = char.description
            lvl = char.lvl
            xp = char.xp

            embed = discord.Embed(
                title=f"{name}", colour=discord.Colour(0xF5A623), description=f"{desc}"
            )
            embed.set_author(name=config.bot.name, icon_url=config.bot.icon_url)
            embed.set_footer(text="Информация о персонаже")

            embed.add_field(
                name="Характеристики",
                value=f"**Раса:**           {race}\n"
                f"**Пол:**            {sex}\n"
                f"**Уровень:**        {lvl}\n"
                f"**Опыт:**           {xp}",
            )

            await ctx.send(embed=embed)

    @char.command(name="new")
    async def char_new(self, ctx):
        """ Создать персонажа """

        author = ctx.author
        member_id = str(author.id)

        async def cancel():
            await ctx.send(f"{author.mention}, создание персонажа отменено.")
            if ctx in self.CharSessions:
                self.CharSessions.remove(ctx)

        # Check open registration session
        if next(
            (
                session
                for session in self.CharSessions
                if session.author.id == ctx.author.id
            ),
            None,
        ):
            return

        # Registration check
        if self.CharacterClass.objects(member_id=member_id):
            await ctx.send(
                f"{author.mention}, у вас уже есть персонаж. "
                f"Введите {ctx.prefix}char delete, чтобы удалить его."
            )
            return

        self.CharSessions.append(ctx)

        # Name selection
        await ctx.send(
            f'{author.mention}, введите имя нового персонажа.\nДля отмены введите "отмена".'
        )

        async def name_select():
            try:
                name = await self.Red.wait_for(
                    "message", timeout=60.0, check=MessagePredicate.same_context(ctx)
                )
            except asyncio.TimeoutError:
                return "отмена"
            if len(name.content) < 3 or len(name.content) > 25:
                await ctx.send(
                    f"{author.mention}, в имени персонажа должно быть не менее 3 и не более 20 символов. "
                    "Повторите попытку.\n"
                    'Для отмены введите "отмена".'
                )
                return await name_select()
            elif name.content.count(" ") > 2:
                await ctx.send(
                    f"{author.mention}, имя персонажа не должно содержать больше 2 пробелов. "
                    "Повторите попытку.\n"
                    'Для отмены введите "отмена".'
                )
                return await name_select()
            elif not re.match("^[a-zа-яA-ZА-ЯёЁ][a-zA-Zа-яА-ЯёЁ '-]+$", name.content):
                await ctx.send(
                    f"{author.mention}, введены недопустимые символы. Повторите попытку.\n"
                    'Для отмена введите "отмена".'
                )
                return await name_select()
            else:
                return name.content

        name_c = await name_select()
        if name_c.lower() == "отмена" in name_c.lower():
            await cancel()
            return

        # Race selection
        await ctx.send(
            f"{author.mention}, выберите расу персонажа.\n"
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
            'Для отмены введите "отмена".'
        )

        async def race_select():
            try:
                race = await self.Red.wait_for(
                    "message", timeout=60.0, check=MessagePredicate.same_context(ctx)
                )
            except asyncio.TimeoutError:
                return "отмена"
            if race.content.lower() in [
                "аргонианин",
                "бретонец",
                "данмер",
                "альтмер",
                "имперец",
                "каджит",
                "норд",
                "орк",
                "редгард",
                "босмер",
                "отмена",
            ]:
                return race.content.lower().title()
            else:
                await ctx.send(
                    f"{author.mention}, не могу найти указанную расу. Повторите попытку.\n"
                    'Для отмены введите "отмена".'
                )
                return await race_select()

        race_c = await race_select()
        if race_c.lower() == "отмена":
            await cancel()
            return

        # Sex selection
        await ctx.send(
            f"{author.mention}, выберите пол персонажа (М/Ж).\n"
            "\n"
            'Для отмены введите "отмена".'
        )

        async def sex_select():
            try:
                sex = await self.Red.wait_for(
                    "message", timeout=600.0, check=MessagePredicate.same_context(ctx)
                )
            except asyncio.TimeoutError:
                return "отмена"
            if sex.content.lower() in ["м", "муж", "мужской", "муж."]:
                return "Мужской"
            elif sex.content.lower() in ["ж", "жен", "женский", "жен."]:
                return "Женский"
            elif sex.content.lower() == "отмена":
                return sex.content
            else:
                await ctx.send(
                    f"{author.mention}, не могу найти указанный пол. Повторите попытку.\n"
                    'Для отмены введите "отмена".'
                )
                return await sex_select()

        sex_c = await sex_select()
        if sex_c.lower() == "отмена":
            await cancel()
            return

        # Character description
        try:
            await ctx.send(
                f"{author.mention}, опишите своего персонажа. Тут может быть описана внешность персонажа, его история, "
                "привычки и другие особенности. Не стоит описывать снаряжение персонажа и другие "
                "приобретаемые вещи. "
                "\n\nВ описании персонажа должно быть не менее 50 и не более 1000 символов.\nДля отмены "
                'введите "отмена".'
            )
        except asyncio.TimeoutError:
            await cancel()
            return

        async def desc_select():
            description = await self.Red.wait_for(
                "message", check=MessagePredicate.same_context(ctx)
            )
            if description.content.lower() == "отмена":
                return description.content
            if len(description.content) < 50 or len(description.content) > 1000:
                await ctx.send(
                    f"{author.mention}, в описании персонажа должно быть не менее 50 и не более 1000 символов. "
                    "Повторите попытку.\n"
                    'Для отмены введите "отмена".'
                )
                return await desc_select()
            elif not re.match(
                """^[a-zа-яA-ZА-ЯёЁ\d][a-zA-Zа-яА-ЯёЁ\d !?:;"'.,-]+$""",
                description.content,
            ):
                await ctx.send(
                    f"{author.mention}, введены недопустимые символы. Повторите попытку.\n"
                    'Для отмена введите "отмена".'
                )
                return await desc_select()
            else:
                return description.content

        description_c = await desc_select()
        if description_c.lower() == "отмена":
            await cancel()
            return
        race_attrs = config.race_attrs[RACES[race_c]].main
        inventory = self.InventoryClass([])
        attributes = self.AttributesClass(main=race_attrs)
        attributes.birth()

        # Saving character
        char = self.CharacterClass(
            member_id=member_id,
            name=name_c,
            race=race_c,
            sex=sex_c,
            description=description_c,
            inventory=inventory,
            attributes=attributes,
        )
        char.save()
        await ctx.send(f"{author.mention}, ваш персонаж {name_c} создан!")
        if ctx in self.CharSessions:
            self.CharSessions.remove(ctx)
        print(f"Создан новый персонаж: {name_c}")

    @char.command(name="delete", aliases=["del"])
    async def char_delete(self, ctx):
        """ Удалить персонажа """

        author = ctx.author
        member_id = str(author.id)

        if not self.is_char_exists(member_id):
            await ctx.send(
                f"{author.mention}, у вас нет персонажа. "
                f"Введите '{ctx.prefix}char new', чтобы создать"
            )
        else:
            await ctx.send(
                f"{author.mention}, вы уверены, что хотите удалить своего персонажа?\n"
                "\n"
                "ВНИМАНИЕ: Это действие нельзя отменить. Все ваши предметы, уровень и достижения будут "
                "потеряны безвозвратно."
            )

            try:
                msg = await self.Red.wait_for(
                    "message", timeout=30.0, check=MessagePredicate.same_context(ctx)
                )
            except asyncio.TimeoutError:
                await ctx.send(f"{author.mention}, удаление персонажа отменено.")
                return
            if msg.content.lower() in ["да", "д", "yes", "y"]:
                self.CharacterClass.objects(member_id=member_id).delete()
                await ctx.send(
                    f"{author.mention}, ваш персонаж удален. "
                    f"Введите '{ctx.prefix}char new', чтобы создать нового."
                )
            else:
                await ctx.send(f"{author.mention}, удаление персонажа отменено.")

    def is_char_exists(self, member_id):
        if self.CharacterClass.objects(member_id=member_id):
            return True
        else:
            return False


def str_to_bool(s):
    if s.lower() in ["true", "1", "t", "yes", "да", "истина"]:
        return True
    elif s.lower() in ["false", "0", "f", "no", "нет", "ложь"]:
        return False
    else:
        return ValueError
