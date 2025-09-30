import numpy as np
from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker
from stable_baselines3.common.vec_env import SubprocVecEnv
from stable_baselines3.common.monitor import Monitor
import os
import torch

from mana.env import MtgEnv
from mana.engine.state import Card
from mana.tests.conftest import vanilla_decks

def mask_fn(env) -> np.ndarray:
    """sb3 ActionMasker will call this each step/reset"""
    return env.unwrapped.action_masks()


def make_env(rank: int, d0: list[Card], d1: list[Card], base_seed: int = 1):
    """Env factory for SubprocVecEnv"""
    def _init():
        e = MtgEnv(d0, d1, seed=base_seed+rank, opp_type='simple')
        e = Monitor(e)
        e = ActionMasker(e, mask_fn)
        return e
    return _init


def main() -> None:
    device = 'cuda' if torch.cuda.is_available() else 'cpu'

    n_envs = 8
    n_steps = 1024
    batch_size = 256
    total_timesteps = 200_000

    d0, d1 = vanilla_decks()

    vec_env = SubprocVecEnv([make_env(i, d0, d1, base_seed=1) for i in range(n_envs)])

    model = MaskablePPO(
        'MultiInputPolicy', 
        vec_env, 
        verbose=1, 
        device=device, 
        n_steps=n_steps, 
        batch_size=batch_size
    )
    model.learn(total_timesteps=total_timesteps)

    model.save(os.path.join(os.getcwd(), 'mana', 'scripts', 'outputs', 'ppo_mtg_simple.zip'))

    vec_env.close()

if __name__ == '__main__':
    main()
