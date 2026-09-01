from retroarch_overlay.core.contracts import GameContext

from .game.adapter import Adapter


class Plugin:
    def create(self, context: GameContext) -> Adapter:
        return Adapter(context)


PLUGIN = Plugin()
