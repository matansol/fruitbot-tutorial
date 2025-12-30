"""
Wrapper to create and configure Fruitbot environment for the tutorial
Uses the installed procgen package (not the local copy for Docker)
"""
import gymnasium as gym
import gym as old_gym
import procgen


def create_fruitbot_env():
    """
    Create a Fruitbot environment optimized for human play with low latency
    
    Returns:
        env: Configured Fruitbot Gym environment
    """
    # Create the base procgen environment using the old gym API
    env = old_gym.make(
        "procgen-fruitbot-v0",
        num_levels=10,  # Use procedurally generated levels
        start_level=0,
        distribution_mode="easy",
        render_mode="rgb_array"
    )
    
    return env
