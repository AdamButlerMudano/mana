import numpy as np
from gymnasium.spaces import Discrete
import pytest

from mana.engine.state import Phase
from mana.env import MtgEnv
from mana.engine.errors import IllegalAction
from mana.tests.factories import make_land, make_vanilla_creature

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
    obs, r, term, trunc, info = env.step(play0)

    tap0 = env.idx_tap_land(0)
    obs, r, term, trunc, info = env.step(tap0)

    cast_idx = env.idx_cast_creature(len(env._gs.players[0].hand) - 1)
    obs, r, term, trunc, info = env.step(cast_idx)

    creatures = obs['creatures']
    assert creatures.shape == (env.C_MAX, 4)
    assert creatures[0, 0] == 1
    assert creatures[0, 1] == 1
    assert creatures[0, 2] == 1
    assert creatures[0, 3] == 0


def test_mask_main_phase_play_tap_cast(land_only_decks):
    env = _make_land_only_env(land_only_decks)
    obs, info = env.reset()

    # Force hand to [land, creature]
    p = env._gs.active_player()
    p.hand.clear()
    p.hand.append(make_land('L001'))
    p.hand.append(make_vanilla_creature('C001', 1, 1, 1))

    m = env._action_mask(env._gs)
    assert m[env.A_PASS] == 1
    assert m[env.A_PLAY_BASE] == 1
    print(m[env.A_CAST_BASE: env.A_CAST_BASE+3])
    assert m[env.A_CAST_BASE] == 0
    assert m[env.A_TAP_BASE] == 0
    
    env.step(env.A_PLAY_BASE)
    m = env._action_mask(env._gs)
    assert m[env.A_PLAY_BASE] == 0
    assert m[env.A_CAST_BASE] == 0
    assert m[env.A_TAP_BASE] == 1

    env.step(env.A_TAP_BASE)
    m = env._action_mask(env._gs)
    assert m[env.A_CAST_BASE] == 1
    assert m[env.A_TAP_BASE] == 0
    

def test_mask_combat_phase_attack_subsets(land_only_decks):
    env = _make_land_only_env(land_only_decks)
    obs, info = env.reset()
    gs = env._gs
    p = gs.active_player()

    # Force hand and play a 1/1
    p.hand.clear()
    p.hand.append(make_land('L001'))
    p.hand.append(make_vanilla_creature('C001', 1, 1, 1))
    env.step(env.A_PLAY_BASE)
    env.step(env.A_TAP_BASE)
    env.step(env.A_CAST_BASE)

    # Pass combat, declare attackers and end (which will auto pass through opp turn to our MAIN)
    env.step(env.A_PASS)
    env.step(env.A_PASS)
    env.step(env.A_PASS)
    
    # Play another creature and clear summoning sickness
    p.hand.clear()
    p.hand.append(make_land('L001'))
    p.hand.append(make_vanilla_creature('C001', 1, 1, 1))
    env.step(env.A_PLAY_BASE)
    env.step(env.A_TAP_BASE)
    env.step(env.A_CAST_BASE)
    p.battlefield_creatures[1].summoning_sick = False

    # Move to combat
    env.step(env.A_PASS)
    
    # Multiple attackers
    m = env._action_mask(env._gs)
    enabled = np.flatnonzero(m)
    attack_enabled = [i for i in enabled if i >= env.A_ATTACK_BASE]
    
    assert len(attack_enabled) == 3
    
    # Single attacker
    p.battlefield_creatures[0].tapped = True
    m = env._action_mask(env._gs)
    enabled = np.flatnonzero(m)
    attack_enabled = [i for i in enabled if i >= env.A_ATTACK_BASE]
    
    assert len(attack_enabled) == 1
    assert attack_enabled[0] - env.A_ATTACK_BASE == 1

    # No attackers
    p.battlefield_creatures[1].tapped = True
    m = env._action_mask(env._gs)
    enabled = np.flatnonzero(m)
    attack_enabled = [i for i in enabled if i >= env.A_ATTACK_BASE]
    
    assert len(attack_enabled) == 0


def test_mask_end_phase_only_pass(land_only_decks):
    env = _make_land_only_env(land_only_decks)
    obs, info = env.reset()
    env.step(env.A_PASS)
    env.step(env.A_PASS)
    m = env._action_mask(env._gs)

    assert m[env.A_PASS] == 1
    assert m.sum() == 1


def test_masked_action_raises(land_only_decks):
    env = _make_land_only_env(land_only_decks)
    obs, info = env.reset()

    m = info['action_mask']
    illegal = int(np.flatnonzero(m == 0)[0])
    with pytest.raises(IllegalAction):
        env.step(illegal)