from redbot.core.bot import Red

from .RPGCog import RPGCog


def setup(bot: Red):
    bot.add_cog(RPGCog(bot))
