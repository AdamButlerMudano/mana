import numpy as np
from gymnasium.spaces import Discrete

from mana.engine.state import Phase
from mana.env import MtgEnv
from mana.engine.rules import new_game
from mana.tests.factories import make_lands, make_vanilla_creature

def _make_land_only_env(land_only_decks, seed=1):
    return MtgEnv(*land_only_decks(), seed=seed)


def test_reset_shapes_and_mask(land_only_decks):
    env = _make_land_only_env(land_only_decks)
    obs, info = env.reset()
    mask = info['action_mask']

    assert set(obs.keys()) >= {
        'phase', 
        'life', 
        'mana_pool', 
        'lands_played_this_turn', 
        'hand_type', 
        'hand_cost', 
        'hand_pt', 
        'lands_tapped', 
        'creatures'
    }
    assert isinstance(env.action_space, Discrete)
    assert mask.shape[0] == env.action_space.n
    assert mask[env.A_PASS] == 1


def test_triple_pass_cycles_back_to_main(land_only_decks):
    env = _make_land_only_env(land_only_decks)
    obs, info = env.reset()

    obs, r, term, trunc, info = env.step(env.A_PASS)
    assert not term
    obs, r, term, trunc, info = env.step(env.A_PASS)
    assert not term
    obs, r, term, trunc, info = env.step(env.A_PASS)
    assert int(obs['phase']) == int(Phase.MAIN)


def test_cast_simple_creature_flow(land_only_decks):
    env = _make_land_only_env(land_only_decks)
    obs, info = env.reset()
    
    # Add vanilla creature to hand
    env._gs.players[0].hand.append(make_vanilla_creature('C001', 1, 1, 1))

    play0 = env.idx_play_land(0)
    print(play0)

    print('here1')
    obs, r, term, trunc, info = env.step(play0)
    print('here2')
    tap0 = env.idx_tap_land(0)
    print(tap0)
    print(env._gs.players[0].battlefield_lands)

    obs, r, term, trunc, info = env.step(tap0)
    print('here3')
    print(len(env._gs.players[0].hand))
    cast_idx = env.idx_cast_creature(len(env._gs.players[0].hand) - 1)
    obs, r, term, trunc, info = env.step(cast_idx)

    creatures = obs['creatures']
    assert creatures.shape == (env.C_MAX, 4)
    assert creatures[0, 0] == 1
    assert creatures[0, 1] == 1
    assert creatures[0, 2] == 1
    assert creatures[0, 3] == 0


