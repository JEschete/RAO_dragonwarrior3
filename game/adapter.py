from retroarch_overlay.core.contracts import GameContext


class Adapter:
    name = 'Dragon Warrior 3'

    def __init__(self, context: GameContext) -> None:
        self.context = context

    def snapshot(self, memory: object) -> object:
        raise NotImplementedError("Implement the dragonwarrior3 snapshot adapter")
