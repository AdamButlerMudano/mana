from typing import List, Dict
import copy
import random

from .state import Card, CardType, GameState, PlayerState, LandPermanent, CreaturePermanent, Phase, CombatState, CombatStep
from .errors import IllegalAction

OPENING_HAND = 7
HAND_LIMIT = 7

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
    
    gs.phase = Phase.DRAW
    gs.active = 0
    gs.turn = 1

    return gs


def start_turn(gs: GameState) -> None:
    """Untap, upkeep, draw."""

    if gs.terminal:
        return
    
    p = gs.active_player()
    
    # Untap
    for l in p.battlefield_lands:
        l.tapped = False
    for c in p.battlefield_creatures:
        c.tapped = False
        c.summoning_sick = False

    # TODO: Add upkeep in later version

    # Reset per turn state
    p.lands_played_this_turn = 0
    p.mana_pool = 0

    # Draw and move to main
    _draw(gs, gs.active)
    gs.phase = Phase.MAIN


# PLAY CARDS ==================================================================================================


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


# COMBAT ==================================================================================================


def begin_combat(gs: GameState) -> None:
    """Advance from MAIN to COMBAT phase. Simple state switch for now"""
    if gs.terminal:
        raise IllegalAction('Game already ended')
    if gs.phase != Phase.MAIN:
        raise IllegalAction('Must be in MAIN phase to begin COMBAT.')
    gs.phase = Phase.COMBAT
    gs.combat = CombatState(step=CombatStep.DECLARE_ATTACKERS, defending=gs.opp_idx())


def declare_attackers(
        gs: GameState, 
        attacker_idxs: list[int]
        ) -> None:
    """Declare attackers in COMBAT:
    - Only untapped non-summoning sick creatures you control may attack.
    - Attacking taps the create.
    - Moves to DECLARE_BLOCKERS
    """

    if gs.terminal:
        raise IllegalAction('Game already ended')
    if gs.phase != Phase.COMBAT:
        raise IllegalAction('Cannot declare attackers outside of combat')
    assert gs.combat is not None
    if gs.combat.step != CombatStep.DECLARE_ATTACKERS:
        raise IllegalAction('Not in DECLARE_ATTACKERS step')
    
    p = gs.active_player()
    opp = gs.opp_player()

    # No attackers so move to END
    if not attacker_idxs:
        gs.combat = None
        gs.phase = Phase.END
        return

    # Dedup attackers but preserve order
    seen = set()
    dedup_idxs: list[int] = []
    for i in attacker_idxs:
        if i in seen:
            # Ignore duplicates silently as all attackers will be picked at once. 
            # We can deduplicate when making the action so dont need to confuse things by raising an illegal action here.
            continue
        seen.add(i)
        dedup_idxs.append(i)

    # Validate attackers and tap
    for i in dedup_idxs:
        try:
            creature = p.battlefield_creatures[i]
        except IndexError as e:
            raise IllegalAction('Attacker index out of range.') from e
        if creature.tapped:
            raise IllegalAction('Tapped creature cannot attack.')
        if creature.summoning_sick:
            raise IllegalAction('Summoning sick creature cannot attack.')
        creature.tapped = True

    gs.combat.attackers = dedup_idxs
    gs.combat.blocks.clear()
    gs.combat.step = CombatStep.DECLARE_BLOCKERS


def declare_blockers(gs: GameState, assignments: Dict[int, List[int]]) -> None: 
    """
    Defending player declares blockers:
    - assignments maps attacker_idx-> [blocker_idx, ...]
    - Blocker can be summoning sick but not tapped
    - Each blocker can only be assigned to 1 attacker
    - Moves to DAMAGE
    """
    if gs.terminal:
        raise IllegalAction('Game already ended')
    if gs.phase != Phase.COMBAT:
        raise IllegalAction('Cannot declare attackers outside of combat')
    assert gs.combat is not None
    if gs.combat.step != CombatStep.DECLARE_BLOCKERS:
        raise IllegalAction('Not in DECLARE_BLOCKERS step')

    opp = gs.opp_player()

    # Validate blockers
    used_blockers: set[int] = set()
    valid_attackers = set(gs.combat.attackers)
    for a_idx, b_idxs in assignments.items():
        if a_idx not in valid_attackers:
            raise IllegalAction('Block assigned to non-declared attacker')
        for b_idx in b_idxs:
            if b_idx in used_blockers:
                raise IllegalAction('Blocker already declare against other attacker.')
            used_blockers.add(b_idx)
            try:
                blk = opp.battlefield_creatures[b_idx]
            except IndexError as e:
                raise IllegalAction('Blocker index out of range') from e
            if blk.tapped:
                raise IllegalAction('Tapped creature cannot block')
    
    gs.combat.blocks = assignments
    gs.combat.step = CombatStep.DAMAGE


def resolve_damage(gs: GameState) -> None:
    """
    Apply combat damage to creatures and opp then cleanup:
    - Unblocked attackers deal damage direct to opp
    - Blocked attackers assign power across blockers in listed order
    - Lethal must be assigned before moving to next blocker
    - Resolve damage, sweep for destroyed creatures, mark terminal if opp life <= 0
    """
    if gs.terminal:
        raise IllegalAction('Game already ended')
    if gs.phase != Phase.COMBAT:
        raise IllegalAction('Cannot declare attackers outside of combat')
    assert gs.combat is not None
    if gs.combat.step != CombatStep.DAMAGE:
        raise IllegalAction('Not in DAMAGE step')

    p = gs.active_player()
    opp = gs.opp_player()

    attackers = gs.combat.attackers
    blocks = gs.combat.blocks

    # Assign attacker dmg to blockers
    for a_idx in attackers:
        a_c = p.battlefield_creatures[a_idx]
        assigned = 0
        if a_idx in blocks and blocks[a_idx]:
            for b_idx in blocks[a_idx]:
                b_c = opp.battlefield_creatures[b_idx]
                remaining_attack_power = a_c.power - assigned
                if remaining_attack_power <= 0:
                    break
                required_lethal = max(0, b_c.toughness - b_c.damage)
                dmg_to_assign = remaining_attack_power if remaining_attack_power <= required_lethal else required_lethal
                if dmg_to_assign == 0 and remaining_attack_power > 0:
                    pass
                else:
                    b_c.damage += dmg_to_assign
                    assigned += dmg_to_assign
    
    # Assign unblocked attacker dmg to opp
    player_dmg = 0
    for a_idx in attackers:
        if a_idx not in blocks.keys():
            player_dmg += p.battlefield_creatures[a_idx].damage

    # Assign blocker dmg to attacker
    for a_idx, b_idxs in blocks.items():
        a_c = p.battlefield_creatures[a_idx]
        for b_idx in b_idxs:
            b_c = opp.battlefield_creatures[b_idx]
            a_c.damage += b_c.power

    # Resolve dmg
    _sweep_creature_lethal(p.battlefield_creatures, p.graveyard)
    _sweep_creature_lethal(opp.battlefield_creatures, opp.graveyard)    
    opp.life -= player_dmg

    # Check for player lethal
    if opp.life <= 0:
        gs.terminal = True
        gs.winner = gs.active
        gs.loser = gs.opp_idx()

    gs.combat = None
    gs.phase = Phase.END


def _sweep_creature_lethal(creatures: list[CreaturePermanent], graveyard: list) -> None:
    """Move creatures dealt enough damage to destroy them to the graveyard."""
    survivors: List[CreaturePermanent] = []
    for c in creatures:
        if c.damage >= c.toughness:
            c.damage = 0
            graveyard.append(c.card)
        else:
            survivors.append(c)
    creatures[:] = survivors


# END TURN ========================================================================================
def cleanup(gs: GameState) -> None:
    """
    - Empty mana pool
    - Discard to hand limit
    - Clear damage from creatures
    """

    if gs.terminal:
        return
    p = gs.active_player()
    opp = gs.opp_player()

    # Empty mana pool
    p.mana_pool = 0

    # Discard to hand limit
    while len(p.hand) > HAND_LIMIT:
        # Discard the last card in hand for now.
        p.graveyard.append(p.hand.pop())

    # Clear damage
    for c in p.battlefield_creatures:
        c.damage = 0
    for c in opp.battlefield_creatures:
        c.damage = 0


def end_turn(gs: GameState) -> None:
    """
    - Run cleanup
    - Change active player
    - Start next turn - for convenience in v0
    """

    if gs.terminal:
        return
    if gs.phase != Phase.END:
        raise IllegalAction('Can only end turn during END.')
    
    # Clean up 
    cleanup(gs)

    # Pass turn
    gs.active = gs.opp_idx()
    gs.turn += 1
    gs.phase = Phase.DRAW

    # Start next turn
    start_turn(gs)
    