"""
Wrapper to create and configure Fruitbot environment for the tutorial
Uses the installed procgen package (not the local copy for Docker)
"""
try:
    import gymnasium as gym
    import gym as old_gym
    import procgen
    PROCGEN_AVAILABLE = True
except ImportError:
    PROCGEN_AVAILABLE = False
    print("Procgen not found, using Mock environment")

import numpy as np

class MockEnv:
    def __init__(self):
        self.action_space = type('obj', (object,), {'n': 15})
        self.observation_space = type('obj', (object,), {'shape': (64, 64, 3)})
    
    def reset(self):
        return np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)
    
    def step(self, action):
        obs = np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)
        reward = 0.5
        done = np.random.random() < 0.1  # 10% chance to finish
        info = {'rgb': obs}
        return obs, reward, done, info
    
    def close(self):
        pass

def create_fruitbot_env():
    """
    Create a Fruitbot environment optimized for human play with low latency
    
    Returns:
        env: Configured Fruitbot Gym environment
    """
    if not PROCGEN_AVAILABLE:
        return MockEnv()

    # Define environment parameters as requested
    env_kwargs = {
        "num_levels": 0,  # 0 means infinite levels
        "start_level": 0,
        "distribution_mode": "easy",
        "render_mode": "rgb_array",
        # Environment structuring
        "fruitbot_num_walls": 3,
        "fruitbot_num_good_min": 5,
        "fruitbot_num_good_range": 0,
        "fruitbot_num_bad_min": 5,
        "fruitbot_num_bad_range": 0,
        "food_diversity": 6,
        "fruitbot_reward_positive": 1,
        "fruitbot_reward_negative": -1,
        "fruitbot_reward_wall_hit": -3,
        "fruitbot_wall_gap_pct": 30,
        "fruitbot_door_prob_pct": 50,
        "fruitbot_reward_step": 0,
        "fruitbot_reward_completion": 5,
        }



    # Create the base procgen environment using the old gym API
    env = old_gym.make("procgen-fruitbot-v0", **env_kwargs)
    
    return env
