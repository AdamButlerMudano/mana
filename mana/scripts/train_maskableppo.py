import numpy as np
from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker
from stable_baselines3.common.monitor import Monitor
import os

from mana.env import MtgEnv
from mana.tests.conftest import vanilla_decks

def mask_fn(env) -> np.ndarray:
    """sb3 ActionMasker will call this each step/reset"""
    return env.action_mask()

def main() -> None:
    d0, d1 = vanilla_decks()
    env = MtgEnv(d0, d1, seed=1, opp_type='simple')
    env = Monitor(env)
    env = ActionMasker(env, mask_fn)

    model = MaskablePPO('MultiInputPolicy', env, verbose=1, device='cuda', n_steps=1024, batch_size=256)
    model.learn(total_timesteps=10000)

    model.save(os.path.join(os.getcwd(), 'outputs', 'ppo_mtg_simple.zip'))


if __name__ == '__main__':
    main()
