from typing import List
import copy
import random

from .state import Card, CardType, CreatureInfo, GameState, PlayerState, LandPermanent, CreaturePermanent, Phase
from .errors import IllegalAction

OPENING_HAND = 7

def _shuffle(deck: List[Card], rng: random.Random) -> List[Card]:
    deck_copy = deck[:]
    rng.shuffle(deck_copy)

    return deck_copy


def _draw(gs: GameState, player_idx: int) -> None:
    # Note: not pure
    p = gs.players[player_idx]

    if not p.library:
        gs.terminal = True
        gs.loser = player_idx
        gs.winner = 1 - player_idx
        return
    card = p.library.pop()
    p.hand.append(card)


def new_game(deck_p0: List[Card], deck_p1: List[Card], seed: int) -> GameState:
    rng = random.Random(seed)
    p0 = PlayerState(library=_shuffle(deck_p0, rng))
    p1 = PlayerState(library=_shuffle(deck_p1, rng))
    gs = GameState(players=[p0, p1], rng=rng)

    for _ in range(OPENING_HAND):
        _draw(gs, 0)
        _draw(gs, 1)
    
    gs.phase = Phase.Draw
    gs.active = 0
    gs.turn = 1

    return gs


def start_turn(gs: GameState) -> None:
    """Untap, upkeep, draw."""

    if gs.terminal:
        return
    
    # Reset per turn state
    p = gs.active_player()
    p.lands_played_this_turn = 0
    p.mana_pool = 0

    _draw(gs, gs.active)
    gs.phase = Phase.MAIN


def play_land(gs: GameState, hand_index: int) -> None:
    # Check play is legal
    if gs.terminal:
        raise IllegalAction('Game already ended')
    
    if gs.phase != Phase.MAIN:
        raise IllegalAction('Only play lands during MAIN phase')
    
    p = gs.active_player()

    if p.lands_played_this_turn >= 1:
        raise IllegalAction('Only play 1 land a turn.')
    
    try:
        card = p.hand[hand_index]
    except IndexError as e:
        raise IllegalAction('Hand index out of range') from e

    if card.type is not CardType.LAND:
        raise IllegalAction('Selected card is not a land')
    
    # Play land to battlefield
    p.hand.pop(hand_index)
    p.battlefield_lands.append(LandPermanent(card=card, tapped=False))
    p.lands_played_this_turn += 1


def tap_land_for_mana(gs: GameState, land_index: int) -> None:
    """Tap an untapped land to add 1 generic mana to the pool"""
    # Check play is legal
    if gs.terminal:
        raise IllegalAction('Game already ended')

    p = gs.active_player()

    try:
        land = p.battlefield_lands[land_index]
    except IndexError as e:
        raise IllegalAction('Land index out of range') from e
    
    if land.tapped:
        raise IllegalAction('Land is already tapped')
    
    # Add mana to mana pool
    land.tapped = True
    p.mana_pool += 1


def cast_creature(gs: GameState, hand_index: int) -> None:
    """Cast a vanilla create"""

    # Check play is legal
    if gs.terminal:
        raise IllegalAction('Game already ended')
    
    if gs.phase != Phase.MAIN:
        raise IllegalAction('Creature can only be cast in MAIN phase.')
    
    p = gs.active_player()

    try:
        card = p.hand[hand_index]
    except IndexError as e:
        raise IllegalAction('Hand index out of range') from e
    
    if card.type is not CardType.CREATURE:
        raise IllegalAction('Selected card is not a creature')
    
    cost = card.cost

    if p.mana_pool < cost:
        raise IllegalAction('Insufficient floated mana to cast creature.')
    
    # Play creature to battlefield
    p.mana_pool -= cost
    p.hand.pop(hand_index)
    p.battlefield_creatures.append(CreaturePermanent(card=card))
