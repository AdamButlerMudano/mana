import numpy as np
import gymnasium as gym
from gymnasium import spaces
from typing import List, Any

from .engine import rules as r
from .engine.state import GameState, Phase, CardType, Card
from .engine.errors import IllegalAction

H_MAX = 10 # Max hand size encoded
L_MAX = 12 # Max land count encoded
C_MAX = 10 # Max creature count encoded

# Action Index
# 0: pass
# 1 -> H_MAX: play_land(i)
# H_MAX+1 -> 2*H_MAX: cast_creature(i)
# 2*H_MAX+1 -> 2*H_MAX+L_MAX: tap_land(i)
# 2*H_MAX+L_MAX+1 -> 2*H_MAX+L_MAX+(2**C_MAX - 1): combinatoric bitmask of creature to attack with

A_PASS = 0
A_PLAY_BASE = 1
A_CAST_BASE = A_PLAY_BASE + H_MAX
A_TAP_BASE = A_CAST_BASE + H_MAX
A_ATTACK_BASE = A_TAP_BASE + L_MAX
N_ACTIONS = A_ATTACK_BASE + (2**C_MAX - 1) 

class MtgEnv(gym.Env):
    """Gym env for simple non-blocking mtg game"""

    metadata = {'render.modes': []}

    def __init__(self, deck0: List[Card], deck1: List[Card], seed: int=1) -> None:
        super().__init__()
        self._deck0 = deck0
        self._deck1 = deck1
        self._seed = seed
        self._gs: GameState | None = None

        self.obs_space = spaces.Dict(
            {
                'phase': spaces.Discrete(4),
                'life': spaces.Box(low=0, high=20, shape=(2,), dtype=np.int8), # increase when we enable life gain
                'mana_pool': spaces.Box(low=0, high=L_MAX, shape=(1,), dtype=np.int8),
                'lands_played_this_turn': spaces.Discrete(2),
                'hand_type': spaces.Box(low=0, high=2, shape=(H_MAX,), dtype=np.int8), # enum of card type for each card in hand
                'hand_cost': spaces.Box(low=0, high=20, shape=(H_MAX,), dtype=np.int8),
                'hand_pt': spaces.Box(low=0, high=20, shape=(H_MAX, 2), dtype=np.int8),
                'lands_tapped': spaces.MultiBinary(L_MAX),
                'creatures': spaces.Box(low=0, high=20, shape=(C_MAX, 4), dtype=np.int8) # power, toughness, summoning_sick, tapped
            }
        )
        self.action_space = spaces.Discrete(N_ACTIONS)

    # Action index helpers
    @staticmethod
    def idx_play_land(i: int) -> int: return A_PLAY_BASE + i

    @staticmethod
    def idx_cast_creature(i: int) -> int: return A_CAST_BASE + i

    @staticmethod
    def idx_tap_land(i: int) -> int: return A_TAP_BASE + i

    @staticmethod
    def idx_attack_mask(mask_num: int) -> int:
        assert 1<= mask_num < 2**C_MAX
        return A_ATTACK_BASE + (mask_num - 1)


    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None) -> tuple[Any, dict[str, Any]]:
        if seed is not None:
            self._seed = seed
        self._gs = r.new_game(self._deck0, self._deck1, seed=self._seed)

        # Begin at first players MAIN
        r.start_turn(self._gs)

        obs = self._encode(self._gs)
        info = {'action_mask': self._action_mask(self._gs)}

        return obs, info
    

    def step(self, action: int):
        assert self._gs is not None, 'GameState does not exists, call reset() first'
        gs = self._gs
        mask = self._action_mask(gs)
        
        if action < 0 or action >= N_ACTIONS or mask[action == 0]:
            raise IllegalAction('Illegal or masked action selected')
        
        # Map action -> rules
        if action == A_PASS:
            if gs.phase == Phase.MAIN:
                r.begin_combat(gs)
            elif gs.phase == Phase.COMBAT:
                r.declare_attackers(gs, [])
            elif gs.phase == Phase.END:
                r.end_turn(gs)
                
                # Auto pass opp back to our MAIN
                if not gs.terminal:
                    self._auto_pass_opponent(gs)
        elif A_PLAY_BASE <= action < A_CAST_BASE:
            idx = action - A_PLAY_BASE
            r.play_land(gs, idx)
        elif A_CAST_BASE <= action < A_ATTACK_BASE:
            idx = action - A_CAST_BASE
            r.cast_creature(gs, idx)
        elif A_TAP_BASE <= action <= A_ATTACK_BASE:
            idx = action - A_TAP_BASE
            r.tap_land_for_mana(gs, idx)
        else:
            m = (action - A_ATTACK_BASE) + 1
            attacker_indices = self._bitmask_to_indices(gs, m)
            if gs.phase == Phase.MAIN:
                r.begin_combat(gs)
            r.declare_attackers(gs, attacker_indices)

        terminated = bool(gs.terminal)
        truncated = False
        reward = 0.0
        if terminated:
            reward = 1.0 if gs.winner == 0 else -1.0
        
        obs = self._encode(gs)
        info = {'action_mask': self._action_mask(gs)}

        return obs, reward, terminated, truncated, info
    

    def _auto_pass_opponent(self, gs: GameState) -> None:
        # Assume this is envoked at the opponents MAIN
        if gs.active != 1 or gs.terminal:
            return
        
        r.begin_combat(gs)
        r.declare_attackers(gs, [])
        r.end_turn(gs)

    
    def _bitmask_to_indices(self, gs: GameState, mask_bits: int) -> List[int]:
        p = gs.active_player()
        n = min(C_MAX, len(p.battlefield_creatures))
        idxs: List[int] = []

        for i in range(n):
            # Check if creature idx is flagged by right bit shifting and selecting right most bit.
            if (mask_bits >> i) & 1:
                idxs.append(i)

        return idxs
    

    

