import pytest
from copy import deepcopy

from mana.tests.factories import make_lands, make_vanilla_creatures

@pytest.fixture
def land_only_decks():
    # As we want to test determinism (via multiple calls to land_only_decks within the same test
    # we need to return a callable rather than the objects themselves.
    def _make():
        return make_lands(30, 'A'), make_lands(30, 'B')
    return _make


def vanilla_decks():
    lands = make_lands(17)
    creatures = make_vanilla_creatures([(1, 1, 1, 10), (2, 2, 2, 8), (3, 3, 3, 5)])

    deck0 = lands + creatures
    deck1 = deepcopy(deck0)

    return deck0, deck1

@pytest.fixture
def vanilla_decks_fx():
    deck0, deck1 = vanilla_decks()

    def _make():
        return deck0, deck1
    return _make
