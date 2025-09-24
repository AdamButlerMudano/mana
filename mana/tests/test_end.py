from mana.engine.rules import (
    new_game,
    start_turn,
    begin_combat,
    declare_attackers,
    end_turn
)
from mana.engine.state import Phase, CreaturePermanent
from mana.engine.errors import IllegalAction

from mana.tests.factories import make_vanilla_creature

def test_end_turn_only_from_end_phase(land_only_decks):
    gs = new_game(*land_only_decks(), seed=1)

    start_turn(gs)

    try:
        end_turn(gs)
        assert False, 'Should only be able to end turn from END phase.'
    except IllegalAction:
        pass


def test_end_turn_switches_and_starts_turn(land_only_decks):
    gs = new_game(*land_only_decks(), seed=1)

    start_turn(gs)
    begin_combat(gs)
    declare_attackers(gs, [])

    assert gs.phase == Phase.END

    end_turn(gs)

    assert gs.active == 1
    assert gs.turn == 2
    assert gs.phase == Phase.MAIN


def test_cleanup_discards_and_empties_mana_pool(land_only_decks):
    gs = new_game(*land_only_decks(), seed=1)
    p = gs.active_player() 
    opp = gs.opp_player()
    
    start_turn(gs)
    begin_combat(gs)
    declare_attackers(gs, [])

    gy_before = len(p.graveyard)
    
    # Add card to hand
    p.hand.append(p.hand[-1])
    hand_before = len(p.hand)

    p.mana_pool = 5
    opp.mana_pool = 5

    end_turn(gs)

    assert len(p.hand) == 7
    assert len(p.graveyard) == gy_before + (hand_before - 7)
    assert p.mana_pool == 0
    assert opp.mana_pool == 0



def test_cleanup_clears_damage_from_creatures(land_only_decks):
    gs = new_game(*land_only_decks(), seed=1)
    p = gs.active_player()
    opp = gs.opp_player()

    start_turn(gs)

    p.battlefield_creatures.append(
        CreaturePermanent(
            card=make_vanilla_creature('C100', 2, 2, 2),
            damage=2,
            summoning_sick=False
        )
    )
    opp.battlefield_creatures.append(
        CreaturePermanent(
            card=make_vanilla_creature('C200', 3, 3, 3),
            damage=3,
            summoning_sick=False
        )
    )

    begin_combat(gs)
    declare_attackers(gs, [])

    assert p.battlefield_creatures[0].damage == 2
    assert opp.battlefield_creatures[0].damage == 3

    end_turn(gs)

    assert p.battlefield_creatures[0].damage == 0
    assert opp.battlefield_creatures[0].damage == 0

