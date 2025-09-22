from mana.engine.rules import new_game, start_turn, play_land
from mana.engine.errors import IllegalAction
from mana.engine.state import Phase, LandPermanent, CreaturePermanent

from mana.tests.factories import make_land, make_vanilla_creature

def test_new_game_is_deterministic_with_seed(land_only_decks):
    d0, d1 = land_only_decks()
    g1 = new_game(d0, d1, seed=42)
    d2, d3 = land_only_decks()
    g2 = new_game(d2, d3, seed=42)

    assert [c.id for c in g1.players[0].hand] == [c.id for c in g2.players[0].hand]
    assert [c.id for c in g1.players[1].hand] == [c.id for c in g2.players[1].hand]

    d4, d5 = land_only_decks()
    g3 = new_game(d4, d5, seed=99)

    assert [c.id for c in g1.players[0].hand] != [c.id for c in g3.players[0].hand]


def test_upkeep_untaps_and_clears_sickness(land_only_decks):
    g = new_game(*land_only_decks(), seed=1)
    p0 = g.players[0]

    land = LandPermanent(make_land(id='L001'), tapped=True)
    p0.battlefield_lands = [land]

    creature = CreaturePermanent(make_vanilla_creature('C001', 1, 1, 1))
    p0.battlefield_creatures = [creature]

    start_turn(g)

    assert sum([l.tapped for l in p0.battlefield_lands]) == 0
    assert sum([c.tapped for c in p0.battlefield_creatures]) == 0
    assert sum([c.summoning_sick for c in p0.battlefield_creatures]) == 0


def test_draw_advances_to_main_draws_and_untaps(land_only_decks):
    g = new_game(*land_only_decks(), seed=1)
    p0 = g.players[0]
    starting = len(p0.hand)

    land = LandPermanent(make_land(id='L001'), tapped=True)
    p0.battlefield_lands = [land]
    
    start_turn(g)
    
    assert g.phase == Phase.MAIN
    assert len(p0.hand) == starting + 1
    assert sum([l.tapped for l in p0.battlefield_lands]) == 0


def test_play_one_land_per_turn_only_in_main(land_only_decks):
    g = new_game(*land_only_decks(), seed=1)

    try:
        play_land(g, 0)
        assert False
    except IllegalAction:
        pass

    start_turn(g)
    play_land(g, 0)

    try: 
        play_land(g, 0)
        assert False
    except IllegalAction:
        pass
