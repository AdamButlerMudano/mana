import pytest

from mana.engine.rules import (
    new_game, 
    start_turn, 
    play_land, 
    tap_land_for_mana, 
    cast_creature, 
    begin_combat, 
    declare_attackers
)
from mana.engine.errors import IllegalAction

from mana.tests.factories import make_vanilla_creature

@pytest.fixture
def _setup_play_creature(land_only_decks):
    gs = new_game(*land_only_decks(), seed=1)
    p = gs.active_player()

    start_turn(gs)
    play_land(gs, 0)
    tap_land_for_mana(gs, 0)
    
    p.hand.append(make_vanilla_creature('C001', 1, 1, 1))
    cast_creature(gs, len(p.hand)-1)

    return gs

@pytest.fixture
def _setup_ready_attacker(_setup_play_creature):
    gs = _setup_play_creature
    
    # Start turn twice to rollback to first player
    start_turn(gs)
    start_turn(gs)

    return gs


def test_begin_combat_only_from_main(land_only_decks):
    gs = new_game(*land_only_decks(), seed=1)

    try:
        begin_combat(gs)
        assert False, 'Should only be able to start combat from MAIN'
    except IllegalAction:
        pass

    start_turn(gs)
    begin_combat(gs)

    assert gs.phase.name == 'COMBAT'


def test_declare_attackers_taps_creature(_setup_ready_attacker):
    gs = _setup_ready_attacker

    p = gs.active_player()
    begin_combat(gs)
    declare_attackers(gs, [0])

    assert p.battlefield_creatures[0].tapped is True


def test_attacker_reduces_opp_life(_setup_ready_attacker):
    gs = _setup_ready_attacker

    p = gs.active_player()
    opp = gs.opp_player()
    start_life = opp.life

    begin_combat(gs)
    declare_attackers(gs, [0])

    assert opp.life == start_life - 1
    assert gs.phase.name == 'END'


def test_cannot_attack_with_tapped_or_sick(_setup_play_creature):
    gs = _setup_play_creature
    p = gs.active_player()
    begin_combat(gs)

    try: 
        declare_attackers(gs, [0])
        assert False, 'Should not be able to attack with summoning sick creature'
    except IllegalAction:
        pass

    # Start turn twice to rollback to first player
    start_turn(gs)
    start_turn(gs)

    # Manually tap creature
    p.battlefield_creatures[0].tapped = True

    try: 
        declare_attackers(gs, [0])
        assert False, 'Should not be able to attack with tapped creature'
    except IllegalAction:
        pass


def test_lethal_attack_ends_game(_setup_ready_attacker):
    gs = _setup_ready_attacker
    p = gs.active_player()
    opp = gs.opp_player()

    opp.life = 1

    begin_combat(gs)
    declare_attackers(gs, [0])

    assert gs.terminal is True
    assert gs.winner == 0
    assert gs.loser == 1
