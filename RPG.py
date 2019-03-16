import asyncio
import inspect
import random
import re
from itertools import cycle
from operator import itemgetter
from typing import Union

import discord
from mongoengine import (
    Document,
    connect,
    IntField,
    StringField,
    EmbeddedDocument,
    DictField,
    EmbeddedDocumentField,
    ListField,
    FloatField,
    URLField,
)
from redbot.core import checks
from redbot.core.bot import Red
from redbot.core.commands import commands, Context
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS, close_menu
from redbot.core.utils.predicates import MessagePredicate

from .register_char_session import RegisterSession
from .config import config

Cog = getattr(commands, "Cog", object)


class Item(Document):
    """Item class

    Attributes:
        item_id (int): Item ID.
        name (str): Item name.
        desc (str): Item description.
        price (int): Item price.
        _rarity (str): Item rarity.

    """

    rarity_rates = {
        "legendary": "легендарн.",
        "epic": "эпическ.",
        "rare": "редк.",
        "common": "обычн.",
    }
    item_id = IntField(primary_key=True, required=True, min_value=0)
    name = StringField()
    desc = StringField()
    price = IntField(min_value=0)
    rarity = StringField(choices=rarity_rates.keys())

    def __init__(
        self,
        item_id: int,
        name: str,
        desc: str,
        price: int,
        rarity: str,
        *args,
        **values,
    ):
        """Item constructor

        Args:
            item_id (int): Unique item ID.
            name (str): Item name.
            desc (str): Item description.
            price (int): Item price.
            rarity (str): Item rarity.
        """
        super().__init__(*args, **values)
        self.item_id = item_id
        self.name = name
        self.desc = desc
        self.price = price
        self.rarity = rarity

    @property
    def rarity_text(self) -> str:
        """Returns item rarity in human form.

        Returns: Item rarity.

        """
        return self.rarity_rates[self.rarity].title()

    @classmethod
    def get_next_id(cls) -> int:
        """Returns the next free id.

        Returns:
            int: Next free id.

        """
        try:
            item_id = int(cls.objects.order_by("-_id").first().item_id) + 1
        except AttributeError:
            item_id = 0
        return item_id

    meta = {"allow_inheritance": True}


class Armor(Item):
    """Armor class

    Attributes:
        item_id (int): Unique armor ID.
        name (str): Armor name.
        desc (str): Armor description.
        price (int): Armor price.
        rarity (str): Armor rarity.
        slot (str): Armor slot.
        kind (str): Armor kind.
        material (str): Armor material.
        armor (int): Armor rating.

    """

    slots = {
        "helmet": "шлем",
        "cuirass": "броня",
        "boots": "сапоги",
        "gauntlets": "перчатки",
        "shield": "шит",
    }
    armor_kinds = {
        "heavy": "тяжелая броня",
        "light": "легкая броня",
        "clothing": "одежда",
    }
    materials = {
        "iron": "железн.",
        "steel": "стальн.",
        "orcish": "ороч.",
        "glass": "стеклянн.",
        "elven": "эльфийск.",
        "ebony": "эбонитов.",
        "dwarven": "двемерск.",
        "daedric": "даэдрическ.",
        "cloth": "ткань",
        "leather": "кожан.",
    }

    slot = StringField(choices=slots.keys())
    kind = StringField(choices=armor_kinds.keys())
    material = StringField(choices=materials.keys())
    armor = IntField(min_value=0)

    def __init__(
        self,
        item_id: int,
        name: str,
        desc: str,
        price: int,
        rarity: str,
        slot: str = None,
        kind: str = None,
        material: str = None,
        armor: int = 0,
        *args,
        **values,
    ):
        """Armor constructor

        Args:
            item_id (int): Unique armor ID.
            name (str): Armor name.
            desc (str): Armor description.
            price (int): Armor price.
            rarity (str): Armor rarity.
            slot (str): Armor slot. Possible values: helmet, cuirass, boots, gauntlets.
            kind (str): Armor kind. Possible values: heavy, light, clothing.
            material (str): Armor material.
            armor (int): Armor rating. It can not be negative.
        """
        super().__init__(item_id, name, desc, price, rarity, *args, **values)
        self.slot = slot
        self.kind = kind
        self.material = material
        self.armor = armor

    @property
    def slot_text(self):
        return self.slots[self.slot].title()

    @property
    def kind_text(self):
        return self.armor_kinds[self.kind].title()


class Weapon(Item):
    """Weapon Class

    Attributes:
        item_id (int): Unique weapon ID.
        name (str): Weapon name.
        desc (str): Weapon description.
        price (int): Weapon price.
        rarity (str): Weapon rarity.
        attack_type (str): Attack type.
        hands (int): The number of used hands.
        weapon_type (str): Weapon type.
        material (str): Weapon material.
        damage (int): Weapon damage.

    """

    attack_types = {"melee": "ближний бой", "range": "дальний бой"}
    weapon_types = {
        "crossbow": "арбалет",
        "bow": "лук",
        "greatsword": "двуручный меч",
        "battleaxe": "секира",
        "warhammer": "боевой молот",
        "sword": "меч",
        "war_axe": "боевой топор",
        "mace": "булава",
        "dagger": "кинжал",
    }
    materials = {
        "iron": "железн.",
        "steel": "стальн.",
        "wood": "деревянн.",
        "silver": "серебрянн.",
        "orcish": "ороч.",
        "glass": "стеклянн.",
        "elven": "эльфийск.",
        "ebony": "эбонитов.",
        "dwarven": "двемерск.",
        "daedric": "даэдрическ.",
    }

    attack_type = StringField(choices=attack_types.keys())
    hands = IntField(min_value=1, max_value=2)
    weapon_type = StringField(choices=weapon_types.keys())
    material = StringField(choices=materials.keys())
    damage = IntField(min_value=0)

    def __init__(
        self,
        item_id: int,
        name: str,
        desc: str,
        price: int,
        rarity: str,
        attack_type: str = None,
        hands: int = 0,
        weapon_type: str = None,
        material: str = None,
        damage: int = 0,
        *args,
        **values,
    ):
        """Weapon constructor

        Args:
            item_id (int): Unique weapon ID.
            name (str): Weapon name.
            desc (str): Weapon description.
            price (int): Weapon price.
            rarity (str): Weapon rarity.
            attack_type (str): Attack type. May be melee or range.
            hands (int): The number of used hands. May be 1 or 2.
            weapon_type (str): Weapon type. Possible values: crossbow, bow,
                greatsword, battleaxe, warhammer, sword, war_axe, mace, dagger.
            material (str): Weapon material.
            damage (int): Weapon damage. It can not be negative.
        """
        super().__init__(item_id, name, desc, price, rarity, *args, **values)
        self.attack_type = attack_type
        self.hands = hands
        self.weapon_type = weapon_type
        self.material = material
        self.damage = damage

    @property
    def weapon_type_text(self):
        return self.weapon_types[self.weapon_type].title()


class Inventory(EmbeddedDocument):
    """Inventory class

    All items are dictionaries that contain information about the item ID,
    maker of the item and its tempering. These dictionaries are stored in
    lists, which are the values of the keys of the `items` dictionary. The keys
    of this dictionary are categories of inventory items.
    """

    items = DictField(
        ListField(DictField()), default={"Weapon": [], "Armor": [], "Item": []}
    )

    @staticmethod
    def get_item_category(item: Item) -> str:
        """Returns the item category.

        The method deletes the substring "Item.", if present.

        Args:
            item (Item): The item to get category.

        Returns:
            str: Category name.

        """
        return re.sub(r"Item.", "", item["_cls"])

    def get_item(self, item: Item, maker: str = None, temper: int = None) -> dict:
        """Returns a dictionary of an item from the inventory, if it exists
        in it, otherwise it raises the exception ItemNotFoundInInventory.

        Args:
            item (Item): The item to get from inventory.
            maker (:obj:`str`, optional): Name of the maker of the item.
                Defaults to None.
            temper (:obj:`int`, optional): Item tempering. Defaults to None.

        Returns:
            dict: Inventory item dictionary.

        Raises:
            ItemNotFoundInInventory: If the item is not found in inventory.

        """
        category = self.get_item_category(item)
        found_item = next(
            (
                _item
                for _item in self.items[category]
                if _item["item_id"] == item.item_id
                and _item["maker"] == maker
                and _item["temper"] == temper
            ),
            False,
        )
        if not bool(found_item):
            raise ItemNotFoundInInventory
        return found_item

    def add_item(self, item: Item, count: int, maker: str = None, temper: int = None):
        """Adds item to inventory.

        The method tries to find an instance of the item in the inventory, if it
        succeeds, then it simply increases the number of items. Otherwise, it
        creates a new instance of the item in this inventory and cleans it from
        blank items.

        Args:
            item (Item): The item to add to inventory.
            count (int): The number of items to add.
            maker (:obj:`str`, optional): Name of the maker of the item. Defaults
                to None.
            temper (:obj:`int`, optional): Item tempering. Defaults to None.
        """
        try:
            _item = self.get_item(item)
            _item["count"] += count
        except ItemNotFoundInInventory:
            category = self.get_item_category(item)
            new_item = {
                "item_id": item.id,
                "count": count,
                "maker": maker,
                "temper": temper,
            }
            self.items[category].append(new_item)
            self.items[category][:] = [
                item for item in self.items[category] if item.get("count") > 0
            ]

    def remove_item(self, item: Item, count: int):
        """Removes item from inventory.
        
        The method reduces the number of items. If after this operation the
        number of items has become less than 1, then all items that are less
        than 1 are removed from the inventory.

        If there are no items left after deleting an item in this section of
        the inventory, an blank item will be created to prevent the list from
        being deleted, due to the characteristics of mongoengine.
        
        Args:
            item (Item): The item to remove from inventory.
            count (int): The number of items to remove.
        """
        _item = self.get_item(item)
        category = self.get_item_category(item)
        if _item:
            _item["count"] -= count
            if _item["count"] < 1:
                self.items[category][:] = [
                    item for item in self.items[category] if item.get("count") > 0
                ]
                if len(self.items[category]) < 1:
                    blank_item = {"item_id": "", "count": 0}
                    self.items[category].append(blank_item)

    def is_inventory_empty(self) -> bool:
        """Returns whether there are items in the inventory.

        Returns:
            bool: The inventory is empty or not.

        """
        inv = self.items
        for category, items in inv.items():
            try:
                if items[0]["count"] > 0:
                    return False
            except IndexError:
                pass
        else:
            return True


class Attributes(EmbeddedDocument):
    """Character Attribute Class

    Attributes:
        health (float): Character health. Equals 10 immediately after creating a character.
        stamina (float) Character stamina. Equals 10 immediately after creating a character.
        magicka (float) Character magicka. Equals 10 immediately after creating a character.
        main (dict): The main dynamic attributes of the character.
        resists (dict): Character resistance to magic, elements, poisons and diseases.
        skills (dict): The level of skills of the character.
        armor_rating (int): Total character armor.
        unarmed_damage (int): Unarmed character damage.

    """

    health = FloatField(default=10)
    stamina = FloatField(default=10)
    magicka = FloatField(default=10)
    main = DictField(FloatField())
    resists = DictField(FloatField(min_value=-90, max_value=90))
    skills = DictField(FloatField(min_value=0, max_value=100))
    armor_rating = IntField(default=0)
    unarmed_damage = IntField()

    def __init__(
        self,
        main: dict,
        resists: dict,
        skills: dict,
        unarmed_damage: int,
        *args,
        **kwargs,
    ):
        """Attributes constructor

        Args:
            main (dict): The main dynamic attributes of the character.
            resists (dict): Character resistance to magic, elements, poisons and diseases.
            skills (dict): The level of skills of the character.
            unarmed_damage (int): Unarmed character damage.
        """
        super().__init__(*args, **kwargs)
        self.main = main
        self.resists = resists
        self.skills = skills
        self.unarmed_damage = unarmed_damage

    def get_total_value(self, attribute: str) -> int:
        """Returns the maximum attribute value, including all bonuses.

        Args:
            attribute (str): Attribute name to get.

        Returns:
            int: Maximum attribute value.

        """
        return self.main[f"{attribute}_max"] + self.main[f"{attribute}_buff"]

    def mod_value(self, attribute: str, damage: int):
        """Modifies the attribute value.

        A positive value will increase the value of the attribute by this
        number, a negative value will decrease it.

        Args:
            attribute (str): Attribute name to modify.
            damage (int): The amount by which the attribute will be modified.

        Raises:
            AttributeNotFound: If the attribute is not found.
        """
        if hasattr(self, attribute):
            attr = getattr(self, attribute)
            try:
                total = self.get_total_value(attribute)
                if attr + damage <= total:
                    setattr(self, attribute, attr + damage)
                    attr = getattr(self, attribute)
                    if attr > total:
                        setattr(self, attribute, total)
                    elif attr < 1:
                        setattr(self, attribute, 0)
                else:
                    setattr(self, attribute, total)
            except KeyError:
                setattr(self, attribute, attr + damage)
        elif hasattr(self.main, attribute):
            setattr(self.main, attribute, getattr(self.main, attribute) + damage)
        elif hasattr(self.resists, attribute):
            setattr(self.resists, attribute, getattr(self.resists, attribute) + damage)
        elif hasattr(self.skills, attribute):
            attr = getattr(self.skills, attribute)
            if attr + damage <= 100:
                setattr(self.skills, attribute, attr + damage)
                attr = getattr(self.skills, attribute)
                if attr > 100:
                    setattr(self.skills, attribute, 100)
                elif attr < 1:
                    setattr(self.skills, attribute, 0)
            else:
                setattr(self.skills, attribute, 100)
        else:
            raise AttributeNotFound

    def restore_values(self):
        """ Restores Health, Stamina and Magicka """
        self.health = self.main["health_max"]
        self.stamina = self.main["stamina_max"]
        self.magicka = self.main["magicka_max"]


class Equipment(EmbeddedDocument):
    """Equipment Class

    Attributes:
        right_hand (dict): The right hand of the character. It can take any
            type of weapon. If the weapon uses two hands, it will occupy the
            right hand.
        left_hand (dict): The left hand of the character. A second one-handed
            weapon or shield can be taken in the left hand.
        helmet (dict): Head slot character. For hats.
        cuirass (dict): Body slot character.
        gauntlets (dict): Hands slot character.
        boots (dict): Foot slot character.

    """

    right_hand = DictField()
    left_hand = DictField()
    helmet = DictField()
    cuirass = DictField()
    gauntlets = DictField()
    boots = DictField()

    def __init__(
        self,
        right_hand=None,
        left_hand=None,
        helmet=None,
        cuirass=None,
        gauntlets=None,
        boots=None,
        *args,
        **kwargs,
    ):
        """Equipment constructor

        Args:
            right_hand (dict): The right hand of the character. It can take any
            type of weapon. If the weapon uses two hands, it will occupy the
            right hand.
            left_hand (dict): The left hand of the character. A second one-handed
                weapon or shield can be taken in the left hand.
            helmet (dict): Head slot character. For hats.
            cuirass (dict): Body slot character.
            gauntlets (dict): Hands slot character.
            boots (dict): Foot slot character.
        """
        super().__init__(*args, **kwargs)
        self.right_hand = right_hand
        self.left_hand = left_hand
        self.helmet = helmet
        self.cuirass = cuirass
        self.gauntlets = gauntlets
        self.boots = boots


class Character(Document):
    """Character class

    Attributes:
        member_id (str): Member ID.
        name (str): Character name.
        race (str): Character race.
        sex (str): Character sex.
        desc (str): Character description. Maximum length is 1500.
        lvl (int): The current level of the character. Defaults to 1. Minimum
            value is 1.
        xp (int): The current experience of the character. Defaults to 0.
            Minimum value is 0.
        xp_factor (float): Multiplier experience for the character. Defaults
            to 1.0.
        avatar (str): Link to character avatar. Defaults to None.
        inventory (Inventory): Character inventory.
        attributes (Attributes): Character attributes.
        equipment (Equipment): Character equipment.
    """

    member_id = StringField(primary_key=True)
    name = StringField(max_length=25)
    race = StringField(choices=config.humanize.races.keys())
    sex = StringField(choices=config.humanize.genders.keys())
    desc = StringField(max_length=1500)
    lvl = IntField(default=1, min_value=1)
    xp = IntField(default=0, min_value=0)
    xp_factor = FloatField(default=1.0)
    avatar = URLField(default=None)
    inventory = EmbeddedDocumentField(Inventory)
    attributes = EmbeddedDocumentField(Attributes)
    equipment = EmbeddedDocumentField(Equipment)

    def __init__(
        self,
        member_id: str,
        name: str,
        race: str,
        sex: str,
        desc: str,
        inventory: Inventory,
        attributes: Attributes,
        equipment: Equipment,
        *args,
        **values,
    ):
        """Character constructor

        Args:
            member_id: Member ID.
            name: Character name. Maximum length is 25.
            race: Character race.
            sex: Character sex.
            description: Character description. Maximum length is 1500.
            attributes: Character attributes.
            equipment: Character equipment.
        """
        super().__init__(*args, **values)
        self.member_id = member_id
        self.name = name
        self.race = race
        self.sex = sex
        self.desc = desc
        self.inventory = inventory
        self.attributes = attributes
        self.equipment = equipment

    @classmethod
    def is_member_registered(cls, member_id: str) -> bool:
        """Returns whether the member has a character.

        Args:
            member_id: Member ID to check.

        Returns:
            bool: Character registered or not.

        """
        if cls.objects(member_id=member_id):
            return True
        else:
            return False


class RPG(Cog):
    """RPG Cog"""

    def __init__(self, bot: Red):
        self.Red = bot
        self.ItemClass = Item
        self.CharacterClass = Character
        self.AttributesClass = Attributes
        self.EquipmentClass = Equipment
        self.register_sessions = []
        self.Red.loop.create_task(self.setup())
        self.Red.loop.create_task(self.change_status())

    async def setup(self):
        await self.Red.wait_until_ready()

        connect(
            db=config.database.db,
            host=config.database.host,
            port=config.database.port,
            username=config.database.user,
            password=config.database.password,
        )

    async def change_status(self):
        """Changes the bot status through random time.

        The time can be changed in the config in the `bot` section.
        status_change_min in minimum time. status_change_max - maximum.

        """
        await self.Red.wait_until_ready()
        _config = config.bot
        status = _config.statuses[:]
        random.shuffle(status)
        statuses = cycle(status)

        while not self.Red.is_closed():
            status = (
                self.Red.guilds[0].me.status
                if len(self.Red.guilds) > 0
                else discord.Status.online
            )
            activity = discord.Activity(
                name=next(statuses), type=discord.ActivityType.watching
            )
            await self.Red.change_presence(status=status, activity=activity)
            await asyncio.sleep(
                random.randint(_config.status_change_min, _config.status_change_max)
            )

    async def update_chars(self):
        await self.Red.wait_until_ready()
        timer = 5
        while not self.Red.is_closed():
            # Attributes regeneration
            chars = self.CharacterClass.objects
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

    @commands.group(invoke_without_command=True)
    async def char(self, ctx, member: Union[discord.Member, discord.User] = None):
        """Информация о персонаже"""

        author = ctx.author
        if member is None:
            member = author
        member_id = str(member.id)
        try:
            char = self.get_char_by_id(member_id)
        except CharacterNotFound:
            await ctx.send(f"{author.mention}, персонаж не найден.")
            await ctx.send_help()
            return

        embed = discord.Embed(
            title=f"{char.name}",
            colour=discord.Colour(0xF5A623),
            description=f"{char.desc}",
        )
        embed.set_author(name=config.bot.name, icon_url=config.bot.icon_url)
        if char.avatar:
            embed.set_thumbnail(url=char.avatar)
        embed.set_footer(text="Информация о персонаже")

        embed.add_field(
            name="Характеристики",
            value=f"**Раса:**           {config.humanize.races[char.race]}\n"
            f"**Пол:**            {config.humanize.genders[char.sex]}\n"
            f"**Уровень:**        {char.lvl}\n"
            f"**Опыт:**           {char.xp}",
        )

        await ctx.send(embed=embed)

    @char.command(name="new")
    async def char_new(self, ctx):
        """Создать персонажа"""

        author = ctx.author

        if self.CharacterClass.is_member_registered(str(author.id)):
            await ctx.send(
                f"{author.mention}, у вас уже есть персонаж. "
                f"Введите `{ctx.prefix}char delete`, чтобы удалить его."
            )
            return
        session = self._get_register_session(ctx.author)
        if session is not None:
            return
        session = RegisterSession.start(ctx)
        self.register_sessions.append(session)

    @char.command(name="cancel")
    async def char_cancel(self, ctx):
        """Отменить регистрацию персонажа"""
        session = self._get_register_session(ctx.author)
        if session is None:
            return
        author = ctx.author
        if author == session.ctx.author:
            await session.cancel()
            session.force_stop()

    @char.command(name="delete", aliases=["del"])
    async def char_delete(self, ctx):
        """Удалить персонажа"""

        author = ctx.author
        member_id = str(author.id)

        if not self.CharacterClass.is_member_registered(member_id):
            await ctx.send(
                f"{author.mention}, у вас нет персонажа. "
                f"Введите `{ctx.prefix}char new`, чтобы создать"
            )
            return

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
                f"Введите `{ctx.prefix}char new`, чтобы создать нового."
            )
        else:
            await ctx.send(f"{author.mention}, удаление персонажа отменено.")

    @commands.command()
    async def equip(self, ctx: Context, item_name: str):
        """Экипировать предмет"""

        author = ctx.author
        try:
            char = self.get_char_by_id(str(author.id))
        except CharacterNotFound:
            await ctx.send(f"{author.mention}, персонаж не найден.")
            return

        try:
            _item = self.get_item_by_name(item_name)
        except ItemNotFound:
            await ctx.send(f"{author.mention}, предмет не найден.")
            return

        try:
            item = char.inventory.get_item(_item)
            self.equip_item(char, item)
            char.save()
            await ctx.send(f"{author.mention}, предмет экипирован.")
        except ItemNotFoundInInventory:
            await ctx.send(f"{author.mention}, предмет не найден в инвентаре.")
        except ItemIsNotEquippable:
            await ctx.send(f"{author.mention}, предмет не может быть экипирован.")

    @commands.command(name="inventory", aliases=["inv"])
    async def inventory(self, ctx, member: Union[discord.Member, discord.User] = None):
        """Инвентарь персонажа"""

        author = ctx.author
        if member is None:
            member = author

        try:
            char = self.get_char_by_id(str(member.id))
        except CharacterNotFound:
            await ctx.send(f"{author.mention}, персонаж не найден.")
            return

        if char.inventory.is_inventory_empty():
            _embed = discord.Embed(
                title=f"Инвентарь персонажа {char.name}",
                colour=discord.Colour(0x8B572A),
                description=f"Инвентарь пуст.",
            )
            await ctx.send(embed=_embed)
            return

        pages = []
        for category, name in config.humanize.inventory.inv_categories.items():
            items = char.inventory.items[category]
            if not items:
                continue
            item_stats = []
            for item in items:
                count = item["count"]
                if item and count > 0:
                    try:
                        _item = self.get_item_by_id(item["item_id"])
                        stats = {**{"count": count}, **dict(_item.to_mongo())}
                        item_stats.append(stats)
                    except ItemNotFound:
                        print(
                            f"Item ID: {item['item_id']} not found. Member ID: {member.id}"
                        )
                else:
                    break
            else:
                item_stats[:] = sorted(item_stats, key=itemgetter("name"))
                embed = discord.Embed(
                    title=f"Инвентарь персонажа {char.name}",
                    colour=discord.Colour(0x8B572A),
                    description=f"**```fix\n[{name.upper()}] ({len(item_stats)})\n```**",
                )
                embed.set_author(name=config.bot.name, icon_url=config.bot.icon_url)
                embed.set_footer(text="Инвентарь персонажа")
                for stats in item_stats:
                    text = "```autohotkey\n"
                    for stat, _name in config.humanize.inventory.inv_stats.items():
                        if stat in stats:
                            text += f"{_name.title()}: {stats[stat]}\n"
                    text += "```"
                    embed.add_field(
                        name=f"{stats['name']} ({stats['count']})",
                        value=text,
                        inline=True,
                    )
                pages.append(embed)
        if len(pages) > 1:
            await menu(ctx, pages, DEFAULT_CONTROLS)
        elif len(pages) == 1:
            await menu(ctx, pages, {"❌": close_menu})

    @commands.group(invoke_without_command=True)
    async def item(self, ctx, item_name):
        """Информация о предмете"""

        author = ctx.author
        try:
            _item = self.get_item_by_name(item_name)
        except ItemNotFound:
            await ctx.send(f"{author.mention}, предмет не найден.")
            return

        color = discord.Colour(
            int(getattr(config.game.item_settings.colors, _item.rarity.lower()), 0)
        )
        embed = discord.Embed(
            title=f"{_item.name}", colour=color, description=f"*{_item.desc}*"
        )

        embed.set_author(name=config.bot.name, icon_url=config.bot.icon_url)
        embed.set_footer(text="Информация о предмете")
        for stat, name in config.humanize.inventory.inv_stats.items():
            if stat in _item:
                embed.add_field(
                    name=name.title(), value=f"{getattr(_item, stat)}", inline=True
                )

        await ctx.send(embed=embed)

    @checks.is_owner()
    @item.command(name="new", invoke_without_command=True)
    async def item_new(
        self, ctx, item_type, item_name, description, price, rarity, *args
    ):
        """Добавить новый предмет

        *- item_type:* Тип предмета. Возможные значения: item/weapon/armor
        *- item_name:* Название предмета
        *- description:* Описание предмета
        *- price:* Стоимость предмета
        *- rarity:* Редкость предмета
        *- args:* Дополнительные аргументы для разных типов предметов.
            *-- Оружие:*
                *--- attack_type:* Тип атаки
                *--- hands:* Количество рук
                *--- type:* Тип оружия
                *--- material:* Материал оружия
                *--- damage:* Наносимый урон
            *-- Броня:*
                *--- slot:* Слот брони
                *--- kind:* Тип брони
                *--- material:* Материал оружия
                *--- armor:* Класс брони
        """

        item_id = self.ItemClass.get_next_id()

        new_item = globals()[item_type.title()](
            item_id=item_id,
            name=item_name,
            desc=description,
            price=price,
            rarity=rarity,
        )
        signature = list(inspect.getfullargspec(new_item.__init__).args)
        if args:
            args_len = len(signature) - len(args)
            for arg, value in zip(signature[args_len:], list(args)):
                setattr(new_item, arg, value)

        new_item.save()
        await ctx.send(f"{ctx.author.mention}, предмет создан!")

    @checks.admin_or_permissions()
    @item.command(name="add", pass_context=True)
    async def item_add(
        self,
        ctx,
        member: Union[discord.Member, discord.User],
        count,
        item_name,
        maker=None,
        temper=None,
    ):
        """Выдать предмет персонажу"""

        author = ctx.author
        member_id = str(member.id)
        try:
            char = self.get_char_by_id(member_id)
        except CharacterNotFound:
            await ctx.send(f"{author.mention}, персонаж не найден.")
            return

        try:
            _item = self.get_item_by_name(item_name)
        except ItemNotFound:
            await ctx.send(f"{author.mention}, предмет не найден.")
            return

        if temper:
            temper = int(temper)
        char.inventory.add_item(_item, int(count), maker, temper)
        char.save()
        await ctx.send(f"{author.mention}, предмет(ы) добавлен(ы).")

    @checks.admin_or_permissions()
    @item.command(name="remove", pass_context=True)
    async def item_remove(
        self, ctx, member: Union[discord.Member, discord.User], count, item_name
    ):
        """Удалить предмет у персонажа"""

        author = ctx.author
        if member is None:
            member = author
        member_id = str(member.id)
        try:
            char = self.get_char_by_id(member_id)
        except CharacterNotFound:
            await ctx.send(f"{author.mention}, персонаж не найден.")
            return

        try:
            _item = self.get_item_by_name(item_name)
        except ItemNotFound:
            await ctx.send(f"{author.mention}, предмет не найден.")
            return

        try:
            char.inventory.remove_item(_item, count)
            char.save()
            await ctx.send(f"{author.mention}, предмет(ы) удален(ы).")
        except ItemNotFoundInInventory:
            await ctx.send(f"{author.mention}, предмет не найден в инвентаре.")

    async def on_register_end(self, session: RegisterSession):
        """Event for a registration session ending.

        This method removes the session from this cog's sessions, cancels
        any tasks which it was running, receives registration information
        and sends it to the database.

        Args:
            session (RegisterSession): The session which has just ended.
        """
        if session in self.register_sessions:
            self.register_sessions.remove(session)
        if session.complete:
            inventory = self.InventoryClass({"Weapon": [], "Armor": [], "Item": []})
            race_attrs = config.game.races[session.char["race"]]
            attributes = self.AttributesClass(
                race_attrs.main,
                race_attrs.resists,
                race_attrs.skills,
                race_attrs.unarmed_damage,
            )
            attributes.restore_values()
            equipment = self.EquipmentClass()
            char = self.CharacterClass(
                member_id=session.char["member_id"],
                name=session.char["name"],
                race=session.char["race"],
                sex=session.char["sex"],
                desc=session.char["desc"],
                inventory=inventory,
                attributes=attributes,
                equipment=equipment,
            )
            char.save()

    def _get_register_session(
        self, author: Union[discord.Member, discord.User]
    ) -> RegisterSession:
        """Returns the session registration of the member, if it exists.

        Args:
            author (Union[discord.Member, discord.User]): Member object

        Returns:
            RegisterSession: Registration session

        """
        return next(
            (
                session
                for session in self.register_sessions
                if session.ctx.author == author
            ),
            None,
        )

    def get_item_by_name(self, name: str) -> Item:
        """Returns the item by the given name.

        Args:
            name (str): Item name.

        Returns:
            Document: Item object.

        Raises:
            ItemNotFound: If the item is not found.

        """
        items = self.ItemClass.objects(name=name)
        if not items:
            raise ItemNotFound
        return items.first()

    def get_item_by_id(self, item_id: int) -> Item:
        """Returns the item by the given id.

        Args:
            item_id (int): Item ID.

        Returns:
            Document: Item object.

        Raises:
            ItemNotFound: If the item is not found.

        """
        items = self.ItemClass.objects(item_id=item_id)
        if not items:
            raise ItemNotFound
        return items.first()

    def get_char_by_id(self, member_id: str) -> Character:
        """Returns character object.

        Args:
            member_id: Member ID to get.

        Returns:
            Document: Character object.

        Raises:
            CharacterNotFound: If the member is not registered.

        """
        chars = self.CharacterClass.objects(member_id=member_id)
        if not chars:
            raise CharacterNotFound
        return chars.first()

    def unequip_item(self, char: Character, slot: str):
        """Unequips the item.

        The method removes the item from the equipment, adds it to the inventory
        and changes the attributes of the character, if necessary.

        Args:
            char (Character): Character on which the item is unequipped.
            slot (str): Item slot from which there is a need to remove the item.
        """
        equipment = char.equipment
        inventory = char.inventory
        attributes = char.attributes
        _item = getattr(equipment, slot)
        if _item:
            setattr(equipment, slot, None)
            item = self.get_item_by_id(_item["item_id"])
            inventory.add_item(item, 1, _item["maker"], _item["temper"])
            if hasattr(inventory.items, "armor"):
                attributes.armor_rating -= item["armor"]

    def equip_item(self, char: Character, item: dict):
        """Equips the item.

        Args:
            char (Character): Character on which the item is equipped.
            item (dict): Sample item from inventory.

        Raises:
            ItemNotFoundInInventory: If the item is not found in the inventory.
            ItemIsNotEquippable: If the item cannot be equipped.

        """
        equipment = char.equipment
        inventory = char.inventory
        attributes = char.attributes
        item_instance = item.copy()
        item_instance.pop("count")
        _item = self.get_item_by_id(item_instance["item_id"])
        category = inventory.get_item_category(_item)
        if item in inventory.items[category]:
            if category == "Weapon":
                right_hand = equipment.right_hand
                if right_hand:
                    weapon_right = self.get_item_by_id(right_hand["item_id"])
                    left_hand = equipment.left_hand
                    if left_hand:
                        self.unequip_item(char, "left_hand")
                    if _item["hands"] == 2:
                        self.unequip_item(char, "right_hand")
                    else:
                        if weapon_right["hands"] == 1:
                            equipment.left_hand = right_hand
                        else:
                            self.unequip_item(char, "right_hand")
                equipment.right_hand = item_instance
            elif category == "Armor":
                slot = _item["slot"]
                if getattr(equipment, slot):
                    self.unequip_item(char, slot)
                setattr(equipment, slot, item_instance)
                attributes.armor_rating += _item["armor"]
            else:
                raise ItemIsNotEquippable
            inventory.remove_item(_item, 1)
        else:
            raise ItemNotFoundInInventory


class ItemNotFound(Exception):
    """Raises if the file is not found in the database."""

    pass


class ItemNotFoundInInventory(Exception):
    """Raises if the file is not found in the inventory."""

    pass


class ItemIsNotEquippable(Exception):
    """Raises if the item is not equippable."""

    pass


class AttributeNotFound(Exception):
    """Raises if the attribute is not found."""

    pass


class CharacterNotFound(Exception):
    """Raises if the member is not registered."""

    pass
