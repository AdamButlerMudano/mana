from typing import List, Optional
from dataclasses import dataclass, field
from enum import Enum, IntEnum
import random


class Phase(IntEnum):
    DRAW = 0
    MAIN = 1
    COMBAT = 2
    END = 3


class CardType(str, Enum):
    LAND = 'Land'
    CREATURE = 'Creature'
    SORCERY = 'Sorcery'


@dataclass(frozen=True, slots=True)
class CreatureInfo:
    power: int
    toughness: int


@dataclass(frozen=True, slots=True)
class Card:
    id: str
    name: str
    type: CardType
    cost: int = 0
    creature: CreatureInfo | None = None

    def __post_init__(self):
        if self.type is CardType.CREATURE and self.creature is None:
            raise ValueError('Creature card must have creature info.')
        if self.type is not CardType.CREATURE and self.creature is not None:
            raise ValueError('None creature card must not have creature info.')


@dataclass(slots=True)
class LandPermanent:
    card: Card
    tapped: bool = False

    def __post_init__(self):
        if self.card.type is not CardType.LAND:
            raise ValueError('LandPermanent must wrap a LAND card')


@dataclass(slots=True)
class CreaturePermanent:
    card: Card
    damage: int = 0
    tapped: bool = False
    summoning_sick: bool = True

    @property
    def power(self) -> int:
        return self.card.power
    
    @property
    def toughness(self) -> int:
        return self.card.toughness
    
    def __post_init__(self):
        if self.card.type is not CardType.LAND:
            raise ValueError('CreaturePermanent must wrap a CREATURE card')
    

@dataclass(slots=True)
class PlayerState:
    life: int = 20
    library: List[Card] = field(default_factory=list)
    hand: List[Card] = field(default_factory=list)
    battlefield_lands: List[LandPermanent] = field(default_factory=list)
    battlefield_creatures: List[CreaturePermanent] = field(default_factory=list)
    graveyard: List[Card] = field(default_factory=list)
    lands_played_this_turn: int = 0
    mana_pool: int = 0


@dataclass(slots=True)
class GameState:
    players: List[PlayerState]
    phase: Phase = Phase.DRAW
    active: int = 0 # active player index
    turn: int = 1
    rng: random.Random = field(default_factory=random.Random)
    terminal: bool = False
    winner: Optional[int] = None
    loser: Optional[int] = None

    def opponent(self, idx: Optional[int] = None) -> int:
        i = self.active if idx is None else idx
        return 1 - i
    
