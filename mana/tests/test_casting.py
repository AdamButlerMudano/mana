from mana.engine.rules import new_game, start_turn, play_land, tap_land_for_mana, cast_creature
from mana.engine.errors import IllegalAction

from mana.tests.factories import make_vanilla_creature

def test_tap_land_adds_mana(land_only_decks):
    gs = new_game(*land_only_decks(), seed=1)
    start_turn(gs)

    p = gs.active_player()
    play_land(gs, 0)
    
    assert len(p.battlefield_lands) == 1
    assert not p.battlefield_lands[0].tapped

    tap_land_for_mana(gs, 0)

    assert p.mana_pool == 1
    assert p.battlefield_lands[0].tapped


def test_cannot_tap_tapped_land(land_only_decks):
    gs = new_game(*land_only_decks(), seed=1)
    start_turn(gs)

    p = gs.active_player()
    play_land(gs, 0)

    tap_land_for_mana(gs, 0)

    try:
        tap_land_for_mana(gs, 0)
        assert False, 'Should not be able to tap a tapped land'
    except IllegalAction:
        pass


def test_cast_creature_correctly(land_only_decks):
    gs = new_game(*land_only_decks(), seed=1)
    start_turn(gs)

    p = gs.active_player()
    play_land(gs, 0)
    tap_land_for_mana(gs, 0)

    c = make_vanilla_creature('C001', power=1, toughness=1, cost=1)
    p.hand.append(c)

    cast_creature(gs, len(p.hand) - 1)
    creature = p.battlefield_creatures[0]

    assert p.mana_pool == 0
    assert len(p.battlefield_creatures) == 1

    assert creature.tapped is False
    assert creature.summoning_sick is True
    assert creature.power == 1
    assert creature.toughness == 1


def test_cast_creature_illegal_phase_type_and_mana(land_only_decks):
    gs = new_game(*land_only_decks(), seed=1)

    try:
        cast_creature(gs, 0)
        assert False, 'Should only be able to cast a creature in MAIN'
    except IllegalAction:
        pass

    start_turn(gs)

    p = gs.active_player()

    try:
        cast_creature(gs, 0)
        assert False, 'Should not be able to cast a land as a creature'
    except IllegalAction:
        pass

    c = make_vanilla_creature('C001', power=1, toughness=1, cost=2)
    p.hand.append(c)

    try:
        cast_creature(gs, len(p.hand)-1)
        assert False, 'Should not be able to cast a creature without sufficient mana pool'
    except IllegalAction:
        pass


