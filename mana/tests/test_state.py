from mana.engine.state import Phase

def test_phase_order():
    assert list(Phase) == [Phase.DRAW, Phase.MAIN, Phase.COMBAT, Phase.END]
    assert Phase.DRAW < Phase.MAIN < Phase.COMBAT < Phase.END
