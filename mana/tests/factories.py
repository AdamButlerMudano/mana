from typing import List
from copy import deepcopy

from mana.engine.state import Card, CardType, CreatureInfo

def make_land(id: str) -> Card:
    return Card(id=id, name='Basic Land', type=CardType.LAND)


def make_lands(n: int, prefix: str = 'L') -> List[Card]:
    return [make_land(f'{prefix}{i:03d}') for i in range(n)]


def make_vanilla_creature(id: str, power: int, toughness: int, cost: int) -> Card:
    return Card(
        id=id,
        name=f'Vanilla {power}/{toughness}',
        type=CardType.CREATURE,
        cost=cost,
        creature=CreatureInfo(power=power, toughness=toughness)
    )


def make_vanilla_creatures(specs: List[tuple[int, int, int, int]], prefix='C') -> List[Card]:
    """Create list of creature cards with specs (power, toughness, cost, count)"""
    
    creatures = [deepcopy(make_vanilla_creature(f'{prefix}{i:03d}', p, t, c)) 
                     for i, (p, t, c, cnt) in enumerate(spec for spec in specs for _ in range(spec[3]))]

    return creatures



