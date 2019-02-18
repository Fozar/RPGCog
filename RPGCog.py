import asyncio
import re
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


class Inventory(EmbeddedDocument):
    """ Класс инвентаря """

    items = ListField(DictField())

    def __init__(self, items, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.items = items  # Список предметов

    # Добавление предмета в инвентарь
    def add_item(self, item, item_type, count):
        existing_item = next((_item for _item in self.items if _item["item_id"] == item.item_id), False)
        if existing_item:
            existing_item["count"] += count
        else:
            _item = {'item_id': item.id, 'item_type': item_type, 'count': count}
            self.items.append(_item)
        self.items[:] = [item for item in self.items if item.get('count') > 0]

    # Удаление предмета из инвентаря
    def remove_item(self, item, count):
        existing_item = next((_item for _item in self.items if _item["item_id"] == item.item_id), False)
        if existing_item:
            existing_item["count"] -= count
            self.items[:] = [item for item in self.items if item.get('count') > 0]
            if len(self.items) < 1:
                _item = {'item_id': "", 'count': 0}
                self.items.append(_item)


class Member(Document):
    """ Класс персонажа """

    member_id = StringField(primary_key=True)
    name = StringField(max_length=25)
    race = StringField()
    sex = StringField()
    description = StringField(max_length=1000)
    lvl = IntField(default=1)
    xp = IntField(default=0)
    inventory = EmbeddedDocumentField(Inventory)

    def __init__(self, member_id, name, race, sex, description, lvl, xp, inventory, *args, **values):
        super().__init__(*args, **values)
        self.member_id = member_id  # ID участника
        self.name = name  # Имя персонажа
        self.race = race  # Раса персонажа
        self.sex = sex  # Пол персонажа
        self.description = description  # Описание персонажа
        self.lvl = lvl  # Уровень персонажа
        self.xp = xp  # Опыт персонажа
        self.inventory = inventory  # Инвентарь персонажа


class Item(Document):
    """ Класс предмета """

    item_id = IntField(primary_key=True)
    name = StringField()
    description = StringField()
    price = IntField()
    rarity = StringField()
    loot = BooleanField()

    def __init__(self, item_id, name, description, price, rarity, loot, *args, **values):
        super().__init__(*args, **values)
        self.item_id = item_id  # ID предмета
        self.name = name  # Название предмета
        self.description = description  # Описание предмета
        self.price = price  # Цена предмета
        self.rarity = rarity  # Редкость предмета
        self.loot = loot  # Может ли предмет найден в луте

    meta = {'allow_inheritance': True}


class Armor(Item):
    """ Класс брони """

    armor_kinds = (('heavy', 'Тяжелая броня'), ('light', 'Легкая броня'), ('clothing', 'Одежда'))
    slots = (('helmet', 'Шлем'), ('cuirass', 'Броня'), ('boots', 'сапоги'), ('gauntlets', 'перчатки'))

    slot = StringField()
    kind = StringField()
    armor = IntField()

    def __init__(self, slot, kind, armor, item_id, name, description, price, rarity, loot, *args, **values):
        super().__init__(item_id, name, description, price, rarity, loot, *args, **values)
        self.slot = slot  # Слот брони (шлем/кираса/сапоги/перчатки)
        self.kind = kind  # Легкая/тяжелая/тряпки
        self.armor = armor  # Класс брони


class Weapon(Item):
    """ Класс оружия """

    weapon_types = (('crossbow', 'Арбалет'), ('bow', 'Лук'), ('greatsword', 'Двуручный меч'), ('battleaxe', 'Секира'),
                    ('warhammer', 'Боевой молот'), ('sword', 'Меч'), ('war_axe', 'Боевой топор'), ('mace', 'Булава'),
                    ('dagger', 'Кинжал'))

    melee = BooleanField()
    hands = IntField()
    weapon_type = StringField(choices=weapon_types)
    damage = IntField()

    def __init__(self, melee, hands, weapon_type, damage, item_id, name, description, price, rarity, loot, *args,
                 **values):
        super().__init__(item_id, name, description, price, rarity, loot, *args, **values)
        self.melee = melee  # Ближний или дальний бой
        self.hands = hands  # Сколько рук занимает
        self.weapon_type = weapon_type  # Тип оружия
        self.damage = damage  # Урон


def is_item_type(items, type=None):
    if type:
        _type = f".{type}"
    else:
        _type = ""
    try:
        if items.get(_cls=f"Item{_type.title()}"):
            return True
    except DoesNotExist:
        return False


def get_item_type(items):
    if is_item_type(items, "weapon"):
        return "weapon"
    elif is_item_type(items, "armor"):
        return "armor"
    elif is_item_type(items):
        return "item"
    else:
        raise ItemTypeNotFound(Exception)


class RPGCog(Cog):
    """ RPG Cog """

    def __init__(self, bot: Red):
        self.Red = bot
        self.MemberClass = Member
        self.InventoryClass = Inventory
        self.ItemClass = Item
        self.ArmorClass = Armor
        self.WeaponClass = Weapon
        self.CharSessions = []
        bot.loop.create_task(self.setup())

    async def setup(self):
        await self.Red.wait_until_ready()

        connect(db=config.database.db, host=config.database.host,
                port=config.database.port,
                username=config.database.db,
                password=config.database.password)

        print("RPGCog загружен")

    @commands.command(name="inventory", aliases=["inv"])
    async def inventory(self, ctx, member: Union[discord.Member, discord.User] = None):
        """ Инвентарь персонажа """

        author = ctx.author
        if member is None:
            member = author
        member_id = str(member.id)

        char = self.MemberClass.objects(member_id=member_id).first()
        if not char:
            await ctx.send("{}, персонаж не найден.".format(author.mention))
            return

        embed = discord.Embed(title=f"Инвентарь персонажа {char.name}", colour=discord.Colour(0x8b572a))

        embed.set_author(name="Deep Requiem",
                         icon_url="https://cdn.discordapp.com/attachments/464105000554201088/544831961265471488"
                                  "/design-skyrim-icon-11.jpeg")
        embed.set_footer(text="Инвентарь персонажа")

        async def empty_inventory():
            embed.description = "Инвентарь пуст."
            await ctx.send(embed=embed)

        if not char.inventory.items:
            await empty_inventory()
            return

        weapon_values = []
        item_values = []
        for item in char.inventory.items:
            count = item["count"]
            if item and count > 0:
                _item = self.ItemClass.objects(item_id=item["item_id"]).first()
                _stat = {'name': _item.name, 'count': count, 'rarity': _item.rarity, 'price': _item.price}
                if item["item_type"] == "weapon":
                    _stat['damage'] = _item.damage
                    weapon_values.append(_stat)
                else:
                    item_values.append(_stat)
            else:
                await empty_inventory()
                return
        weapon_values[:] = sorted(weapon_values, key=itemgetter('name'))
        item_values[:] = sorted(item_values, key=itemgetter('name'))

        def add_category(_embed, _category_name, _values):
            if not _values:
                return
            _embed.add_field(name="==========================================================",
                             value=f"**```fix\n[{_category_name}] ({len(_values)})\n```**", inline=False)
            for _value in _values:
                text = "```autohotkey\n"
                if 'rarity' in _value:
                    text += f"Редкость: {_value['rarity']}\n"
                if 'damage' in _value:
                    text += f"Урон: {_value['damage']}\n"
                if 'price' in _value:
                    text += f"Цена: {_value['price']}\n"
                text += "```"
                embed.add_field(name=f"{_value['name']} ({_value['count']})", value=text, inline=True)

        add_category(embed, "ОРУЖИЕ", weapon_values)
        add_category(embed, "ДРУГОЕ", item_values)
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
            await ctx.send("{}, предмет не найден.".format(author.mention))
        elif len(_items) > 1:
            await ctx.send("{}, найдено больше одного предмета с указанным именем. "
                           "Сообщите об этом администратору.".format(author.mention))
        else:
            item_type = get_item_type(_items)
            _item = _items.first()
            if "редк" in _item.rarity.lower():
                color = discord.Colour(0xa56b6)  # Цвет редкого предмета (синий)
            elif "эпическ" in _item.rarity.lower():
                color = discord.Colour(0x9013fe)  # Цвет эпического предмета (фиолетовый)
            elif "леген" in _item.rarity.lower():
                color = discord.Colour(0xffd700)  # Цвет легендарного предмета (золотой)
            else:
                color = discord.Colour(0xffffff)  # Цвет обычных предметов (белый)
            embed = discord.Embed(title=f"{_item.name}", colour=color,
                                  description=f"*{_item.description}*")

            embed.set_author(name="Deep Requiem",
                             icon_url="https://cdn.discordapp.com/attachments/464105000554201088/544831961265471488"
                                      "/design-skyrim-icon-11.jpeg")
            embed.set_footer(text="Информация о предмете")
            embed.add_field(name="Редкость", value=f"{_item.rarity}", inline=True)
            if item_type == "weapon":
                embed.add_field(name="Урон", value=f"{_item.damage}", inline=True)
            embed.add_field(name="Стоимость", value=f"{_item.price}", inline=True)

            await ctx.send(embed=embed)

    @checks.admin_or_permissions()
    @item.group(name="new", invoke_without_command=True)
    async def item_new(self, ctx, item_name, description, price, rarity, loot):
        """ Добавить новый предмет """

        try:
            item_id = int(self.ItemClass.objects.order_by('-_id').first().item_id) + 1
        except AttributeError:
            item_id = 1
        if loot.lower() in ['true', '1', 't', 'yes']:
            _loot = True
        else:
            _loot = False
        new_item = self.ItemClass(item_id=item_id, name=item_name, description=description,
                                  price=price, rarity=rarity, loot=_loot)
        new_item.save()
        await ctx.send("{}, предмет создан!".format(ctx.author.mention))

    @item_new.command(name="weapon")
    async def item_new_weapon(self, ctx, item_name, description, price, rarity, loot, melee, hands, type, damage):
        """ Добавить новое оружие """

        def str_to_bool(s):
            if s.lower() in ['true', '1', 't', 'yes', 'да', 'истина']:
                return True
            elif s.lower() in ['false', '0', 'f', 'no', 'нет', 'ложь']:
                return False
            else:
                raise ValueError

        try:
            item_id = int(self.ItemClass.objects.order_by('-_id').first().item_id) + 1
        except AttributeError:
            item_id = 1
        _loot = str_to_bool(loot)
        _melee = str_to_bool(melee)

        new_item = self.WeaponClass(item_id=item_id, name=item_name, description=description, price=price,
                                    rarity=rarity, loot=_loot, melee=_melee, hands=hands, weapon_type=type,
                                    damage=damage)
        new_item.save()
        await ctx.send("{}, предмет создан!".format(ctx.author.mention))

    @checks.admin_or_permissions()
    @item.command(name="add", pass_context=True)
    async def item_add(self, ctx, member: Union[discord.Member, discord.User] = None, count=1, *, item_name):
        """ Выдать предмет персонажу """

        author = ctx.author
        if member is None:
            member = author
        member_id = str(member.id)
        char = self.MemberClass.objects(member_id=member_id).first()

        _items = self.ItemClass.objects(name=item_name)
        if not _items:
            await ctx.send("{}, предмет не найден.".format(author.mention))
        elif len(_items) > 1:
            await ctx.send("{}, найдено больше одного предмета с указанным именем. "
                           "Сообщите об этом администратору.".format(author.mention))
        else:
            item_type = get_item_type(_items)
            _item = _items.first()
            char.inventory.add_item(_item, item_type, count)
            char.save()
            await ctx.send("{}, предмет(ы) добавлен(ы).".format(author.mention))

    @checks.admin_or_permissions()
    @item.command(name="remove", pass_context=True)
    async def item_remove(self, ctx, member: Union[discord.Member, discord.User] = None, count=1, *, item_name):
        """ Удалить предмет у персонажа """

        author = ctx.author
        if member is None:
            member = author
        member_id = str(member.id)
        char = self.MemberClass.objects(member_id=member_id).first()

        _items = self.ItemClass.objects(name=item_name)

        if not _items:
            await ctx.send("{}, предмет не найден.".format(author.mention))
            return
        elif len(_items) > 1:
            await ctx.send("{}, найдено больше одного предмета с указанным именем. "
                           "Сообщите об этом администратору.".format(author.mention))
        else:
            _item = _items.first()
            char.inventory.remove_item(_item, count)
            char.save()
            if len(char.inventory.items) < 1:
                inv = self.InventoryClass(items=[])
                char.inventory = inv
                char.save()
            await ctx.send("{}, предмет(ы) удален(ы).".format(author.mention))

    @commands.group(invoke_without_command=True)
    async def char(self, ctx, member: Union[discord.Member, discord.User] = None):
        """ Информация о персонаже """

        author = ctx.author
        if member is None:
            member = author
        member_id = str(member.id)
        char = self.MemberClass.objects(member_id=member_id).first()

        if not char:
            await ctx.send("{}, персонаж не найден.".format(author.mention))
            await ctx.send_help()
        else:
            name = char.name
            race = char.race
            sex = char.sex
            desc = char.description
            lvl = char.lvl
            xp = char.xp

            embed = discord.Embed(title="{}".format(name), colour=discord.Colour(0xf5a623),
                                  description="{}".format(desc))
            embed.set_author(name="Deep Requiem",
                             icon_url="https://cdn.discordapp.com/attachments/464105000554201088/544831961265471488"
                                      "/design-skyrim-icon-11.jpeg")
            embed.set_footer(text="Информация о персонаже")

            embed.add_field(name="Характеристики",
                            value="**Раса:**           {}\n"
                                  "**Пол:**            {}\n"
                                  "**Уровень:**        {}\n"
                                  "**Опыт:**           {}".format(race, sex, lvl, xp))

            await ctx.send(embed=embed)

    @char.command(name="new")
    async def char_new(self, ctx):
        """ Создать персонажа """

        member = ctx.author
        member_id = str(member.id)

        # Проверка открытой сессии регистрации
        if next((session for session in self.CharSessions if session.author.id == ctx.author.id), None):
            return

        # Проверка регистрации
        if self.MemberClass.objects(member_id=member_id):
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
            if len(description.content) < 50 or len(description.content) > 1000:
                await ctx.send("{}, в описании персонажа должно быть не менее 50 и не более 1000 символов. "
                               "Повторите попытку.\n"
                               "Для отмены введите \"отмена\".".format(member.mention))
                return await desc_select()
            elif not re.match("""^[a-zа-яA-ZА-ЯёЁ\d][a-zA-Zа-яА-ЯёЁ\d !?:;"'.,-]+$""", description.content):
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
        inv = self.InventoryClass(items=[])
        char = self.MemberClass(member_id=member_id, name=name_c, race=race_c, sex=sex_c, description=description_c,
                                lvl=1, xp=0, inventory=inv)
        char.save()
        await ctx.send("{}, ваш персонаж {} создан!".format(member.mention, name_c))
        if ctx in self.CharSessions:
            self.CharSessions.remove(ctx)
        print("Создан новый персонаж: {}".format(name_c))

    @char.command(name="delete", aliases=["del"])
    async def char_delete(self, ctx):
        """ Удалить персонажа """

        member = ctx.author
        member_id = str(member.id)

        if not self.is_char_exists(member_id):
            await ctx.send("{}, у вас нет персонажа. "
                           "Введите '{}char new', чтобы создать".format(member.mention, ctx.prefix))
        else:
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
                self.MemberClass.objects(member_id=member_id).delete()
                await ctx.send("{}, ваш персонаж удален. "
                               "Введите '{}char new', чтобы создать нового.".format(member.mention, ctx.prefix))
            else:
                await ctx.send("{}, удаление персонажа отменено.".format(member.mention))

    def is_char_exists(self, member_id):
        if self.MemberClass.objects(member_id=member_id):
            return True
        else:
            return False


class ItemTypeNotFound(Exception):
    pass
