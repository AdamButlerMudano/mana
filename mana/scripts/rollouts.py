"""
run masked-random episodes and print summary.

Usage:
    python -m mana.scripts.rollouts --episodes 10 --seed 1
"""

import argparse
import numpy as np

from mana.env import MtgEnv
from mana.tests.conftest import vanilla_decks


def run_episode(env: MtgEnv, max_steps: int = 500, seed: int | None = None):
    rng = np.random.default_rng(seed)
    obs, info = env.reset(seed=seed)
    total_r = 0.0
    steps = 0
    while True:
        mask = info['action_mask']
        #print('phase', env._gs.phase.name)
        #print(mask[:env.A_ATTACK_BASE])
        #print(mask[env.A_ATTACK_BASE: env.A_ATTACK_BASE+5])
        #print('lands: ', env._gs.active_player().battlefield_lands)
        #print('creatures: ', env._gs.active_player().battlefield_creatures)
        #print(len(mask[env.A_ATTACK_BASE:]), print(sum(mask[env.A_ATTACK_BASE:])))
        a = int(rng.choice(np.flatnonzero(mask)))
        #print(a)
        obs, r, term, trunc, info = env.step(a)
        total_r += r
        steps += 1
        #print('=====================')
        if term or trunc or steps >= max_steps:
            break
        
    return total_r, steps, term


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--episodes', type=int, default=10)
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('--max-steps', type=int, default=500)
    args = parser.parse_args()

    env = MtgEnv(*vanilla_decks(), seed=args.seed)

    rewards, steps, num_wins = [], [], 0
    for ep in range(args.episodes):
        reward, n, term = run_episode(env, args.max_steps, seed=args.seed + ep)
        rewards.append(reward)
        steps.append(n)
        if reward > 0 and term:
            num_wins += 1

    print({
        'episodes': args.episodes,
        'avg_reward': float(np.mean(rewards)) if rewards else 0.0,
        'win_rate': num_wins / args.episodes if args.episodes else 0.0,
        'avg_steps': float(np.mean(steps)) if steps else 0.0,
        'min_steps': int(np.min(steps)) if steps else 0,
        'max_steps': int(np.max(steps)) if steps else 0,
    })


if __name__ == '__main__':
    main()
