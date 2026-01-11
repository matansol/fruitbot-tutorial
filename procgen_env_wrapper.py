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

    # Create the base procgen environment using the old gym API
    env = old_gym.make(
        "procgen-fruitbot-v0",
        num_levels=10,  # Use procedurally generated levels
        start_level=0,
        distribution_mode="easy",
        render_mode="rgb_array"
    )
    
    return env
