from redbot.core.bot import Red

from .RPG import RPG


def setup(bot: Red):
    bot.add_cog(RPG(bot))
