import pytest

from mana.tests.factories import make_lands

@pytest.fixture
def land_only_decks():
    # As we want to test determinism (via multiple calls to land_only_decks within the same test
    # we need to return a callable rather than the objects themselves.
    def _make():
        return make_lands(30, 'A'), make_lands(30, 'B')
    return _make