import numpy as np
import gymnasium as gym
from gymnasium import spaces
from typing import List, Any, Dict

from .engine import rules as r
from .engine.state import GameState, Phase, CardType, Card
from .engine.errors import IllegalAction


class MtgEnv(gym.Env):
    '''Gym env for simple non-blocking mtg game'''

    metadata = {'render.modes': []}

    def __init__(self, deck0: List[Card], deck1: List[Card], seed: int=1) -> None:
        super().__init__()
        self._deck0 = deck0
        self._deck1 = deck1
        self._seed = seed
        self._gs: GameState = r.new_game(self._deck0, self._deck1, seed=self._seed)

        self.H_MAX = 10 # Max hand size encoded
        self.L_MAX = 12 # Max land count encoded
        self.C_MAX = 10 # Max creature count encoded

        # Action Index
        self.A_PASS = 0 # pass
        self.A_PLAY_BASE = 1 # play_land(i)
        self.A_CAST_BASE = self.A_PLAY_BASE + self.H_MAX # cast_creature(i)
        self.A_TAP_BASE = self.A_CAST_BASE + self.H_MAX # tap_land(i)
        self.A_ATTACK_BASE = self.A_TAP_BASE + self.L_MAX # attack with creature mask(n)
        self.N_ACTIONS = self.A_ATTACK_BASE + (2**self.C_MAX - 1) # combinatoric bitmask of creature to attack with

        self.obs_space = spaces.Dict(
            {
                'phase': spaces.Discrete(4),
                'life': spaces.Box(low=0, high=20, shape=(2,), dtype=np.int8), # increase when we enable life gain
                'mana_pool': spaces.Box(low=0, high=self.L_MAX, shape=(1,), dtype=np.int8),
                'lands_played_this_turn': spaces.Discrete(2),
                'hand_type': spaces.Box(low=0, high=2, shape=(self.H_MAX,), dtype=np.int8), # enum of card type for each card in hand
                'hand_cost': spaces.Box(low=0, high=20, shape=(self.H_MAX,), dtype=np.int8),
                'hand_pt': spaces.Box(low=0, high=20, shape=(self.H_MAX, 2), dtype=np.int8),
                'lands_tapped': spaces.MultiBinary(self.L_MAX),
                'creatures': spaces.Box(low=0, high=20, shape=(self.C_MAX, 4), dtype=np.int8) # power, toughness, summoning_sick, tapped
            }
        )
        self.action_space = spaces.Discrete(self.N_ACTIONS)

    # Action index helpers
    def idx_play_land(self, i: int) -> int: return self.A_PLAY_BASE + i

    def idx_cast_creature(self, i: int) -> int: return self.A_CAST_BASE + i

    def idx_tap_land(self, i: int) -> int: return self.A_TAP_BASE + i

    def idx_attack_mask(self, mask_num: int) -> int:
        assert 1<= mask_num < 2**self.C_MAX
        return self.A_ATTACK_BASE + (mask_num - 1)


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

        if action < 0 or action >= self.N_ACTIONS or mask[action] == 0:
            raise IllegalAction('Illegal or masked action selected')
        
        # Map action -> rules
        if action == self.A_PASS:
            if gs.phase == Phase.MAIN:
                r.begin_combat(gs)
            elif gs.phase == Phase.COMBAT:
                r.declare_attackers(gs, [])
            elif gs.phase == Phase.END:
                r.end_turn(gs)
                
                # Auto pass opp back to our MAIN
                if not gs.terminal:
                    self._auto_pass_opponent(gs)
        elif self.A_PLAY_BASE <= action < self.A_CAST_BASE:
            idx = action - self.A_PLAY_BASE
            r.play_land(gs, idx)
        elif self.A_CAST_BASE <= action < self.A_TAP_BASE:
            idx = action - self.A_CAST_BASE
            r.cast_creature(gs, idx)
        elif self.A_TAP_BASE <= action < self.A_ATTACK_BASE:
            idx = action - self.A_TAP_BASE
            r.tap_land_for_mana(gs, idx)
        else:
            m = (action - self.A_ATTACK_BASE) + 1
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
        n = min(self.C_MAX, len(p.battlefield_creatures))
        idxs: List[int] = []

        for i in range(n):
            # Check if creature idx is flagged by right bit shifting and selecting right most bit.
            if (mask_bits >> i) & 1:
                idxs.append(i)

        return idxs
    

    def _encode(self, gs: GameState) -> Dict[str, np.ndarray]:
        p = gs.active_player()
        opp = gs.opp_player()

        # Hand
        hand_type = np.zeros((self.H_MAX,), dtype=np.int8)
        hand_cost = np.zeros((self.H_MAX,), dtype=np.int8)
        hand_pt = np.zeros((self.H_MAX, 2), dtype=np.int8)

        for i in range(min(self.H_MAX, len(p.hand))):
            c = p.hand[i]
            if c.type is CardType.LAND:
                hand_type[i] = 0
            elif c.type is CardType.CREATURE:
                if c.creature is None:
                    raise ValueError('CREATURE CardType should have creature info.')
                hand_type[i] = 1
                hand_pt[i, 0] = c.creature.power
                hand_pt[i, 1] = c.creature.toughness
            else:
                hand_type[i] = 2
            
            hand_cost[i] = c.cost
        
        # Lands
        lands_tapped = [l.tapped for l in p.battlefield_lands]
        lands_tapped = np.pad(np.array(lands_tapped, dtype=np.int8), (0, self.L_MAX-len(lands_tapped)))
        
        # Creatures
        creatures = np.zeros((self.C_MAX, 4), dtype=np.int8)
        for i, c in enumerate(p.battlefield_creatures):
            if i >= self.C_MAX:
                raise ValueError('Trying to encode more creatures than self.C_MAX')
            creatures[i, 0] = c.power
            creatures[i, 1] = c.toughness
            creatures[i, 2] = 1 if c.summoning_sick else 0
            creatures[i, 3] = 1 if c.tapped else 0
        
        obs = {
            'phase': np.array(gs.phase, dtype=np.int8),
            'life': np.array([p.life, opp.life], dtype=np.int8),
            'mana_pool': np.array([p.mana_pool], dtype=np.int8),
            'lands_played_this_turn': np.array(p.lands_played_this_turn, dtype=np.int8),
            'hand_type': hand_type,
            'hand_cost': hand_cost,
            'hand_pt': hand_pt,
            'lands_tapped': lands_tapped,
            'creatures': creatures,
        }

        return obs
    

    def _action_mask(self, gs: GameState) -> np.ndarray:
        mask = np.zeros((self.N_ACTIONS,), dtype=np.int8)
        p = gs.active_player()

        # Pass always allowed
        mask[self.A_PASS] = 1

        if gs.phase == Phase.MAIN:
            # Play land if we haven't already
            if p.lands_played_this_turn == 0:
                for i in range(min(self.H_MAX, len(p.hand))):
                    if p.hand[i].type is CardType.LAND:
                        mask[self.A_PLAY_BASE + i] = 1
            # Cast creature
            for i in range(min(self.H_MAX, len(p.hand))):
                c = p.hand[i]
                if c.type is CardType.CREATURE and p.mana_pool >= c.cost:
                    mask[self.A_CAST_BASE + i] = 1
            # Tap land
            for i in range(min(self.L_MAX, len(p.battlefield_lands))):
                if not p.battlefield_lands[i].tapped:
                    mask[self.A_TAP_BASE + i] = 1
        elif gs.phase == Phase.COMBAT:
            # Build mask of all eligible attackers
            eligible_bits = 0
            for i in range(min(self.C_MAX, len(p.battlefield_creatures))):
                c = p.battlefield_creatures[i]
                if (not c.tapped) and (not c.summoning_sick):
                    eligible_bits |= (1 << i)
            # Enable all non-empty subsets of all attackers
            sub = eligible_bits
            while sub:
                idx = self.A_ATTACK_BASE + (sub - 1) # we sub 1 as the no-attacker mask is the same as a pass
                if idx < self.N_ACTIONS:
                    mask[idx] = 1
                sub = (sub - 1) & eligible_bits # Iterate down the mask, the & skips to the next legal combination
        elif gs.phase == Phase.END:
            # No actions to take at end step in current version
            pass
        else:
            # DRAW isnt accessible to the agent in current version
            pass
        
        return mask



