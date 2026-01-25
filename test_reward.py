import gym
import procgen  # Must import to register environments

env = gym.make('procgen-fruitbot-v0', num_levels=1, distribution_mode='easy', fruitbot_reward_step=0)
obs = env.reset()

print("Testing different actions:")
for action in [0, 1, 2, 3]:
    obs = env.reset()
    total_reward = 0
    for i in range(10):
        obs, r, d, info = env.step(action)
        total_reward += r
        if d:
            break
    print(f"action={action} total_reward_over_10_steps={total_reward:.4f}")
