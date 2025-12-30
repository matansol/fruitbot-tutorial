#!/usr/bin/env python3
"""
Setup script for Fruitbot Tutorial
Ensures procgen is properly built and ready to use
"""
import os
import sys
import subprocess

def main():
    print("=" * 60)
    print("Fruitbot Tutorial Setup")
    print("=" * 60)
    
    # Check if we're in the right directory
    if not os.path.exists("fruitbot_tutorial_app.py"):
        print("ERROR: Please run this script from the tutorial_game directory")
        sys.exit(1)
    
    # Check if requirements file exists
    if not os.path.exists("fruitbot_requirements.txt"):
        print("ERROR: fruitbot_requirements.txt not found!")
        sys.exit(1)
    
    print("\n✓ Requirements file found")
    
    # Install requirements
    print("\n" + "=" * 60)
    print("Installing Python requirements...")
    print("=" * 60)
    
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", "fruitbot_requirements.txt"
        ])
        print("\n✓ Requirements installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Failed to install requirements: {e}")
        sys.exit(1)
    
    # Try to import procgen to trigger build if needed
    print("\n" + "=" * 60)
    print("Checking procgen build...")
    print("=" * 60)
    
    try:
        # Add current directory to path so we can import local procgen
        sys.path.insert(0, os.getcwd())
        import procgen
        print("\n✓ Procgen module imported successfully")
        
        # Try to create an environment to verify everything works
        from procgen_env_wrapper import create_fruitbot_env
        print("\nTesting environment creation...")
        env = create_fruitbot_env()
        env.reset()
        print("✓ Fruitbot environment created successfully")
        env.close()
        
    except Exception as e:
        print(f"\n✗ Error with procgen: {e}")
        print("\nNote: If procgen needs to be built, it will happen automatically on first import.")
        print("This may take a few minutes...")
        return 1
    
    print("\n" + "=" * 60)
    print("Setup Complete!")
    print("=" * 60)
    print("\nYou can now run the tutorial app with:")
    print("  python fruitbot_tutorial_app.py")
    print("\nOr build the Docker container with:")
    print("  docker build -f Dockerfile.fruitbot -t fruitbot-tutorial .")
    print("\nThen access it at: http://localhost:8002")
    print("=" * 60)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
