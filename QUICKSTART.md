# Fruitbot Tutorial - Quick Start Guide

## Prerequisites
- Python 3.10 or 3.11
- Conda (recommended) or pip
- Windows/Linux/Mac

## Installation

### Option 1: Using Conda (Recommended)

1. **Create environment with Python 3.10:**
   ```bash
   conda create -n procgen_tutorial python=3.10 pip -y
   ```

2. **Activate the environment:**
   ```bash
   conda activate procgen_tutorial
   ```

3. **Install dependencies:**
   ```bash
   cd tutorial_game
   pip install -r fruitbot_requirements.txt
   ```

4. **Test the setup:**
   ```bash
   python test_fruitbot_setup.py
   ```

5. **Run the app:**
   ```bash
   python fruitbot_tutorial_app.py
   ```

6. **Open browser:**
   Navigate to `http://localhost:8002`

### Option 2: Using pip (venv)

1. **Create virtual environment:**
   ```bash
   python -m venv venv_fruitbot
   source venv_fruitbot/bin/activate  # On Windows: venv_fruitbot\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   cd tutorial_game
   pip install -r fruitbot_requirements.txt
   ```

3. **Run the app:**
   ```bash
   python fruitbot_tutorial_app.py
   ```

## Game Controls

- **← (Left Arrow)**: Move left
- **→ (Right Arrow)**: Move right
- **Space**: Throw key
- **Auto-forward**: Game moves forward automatically if no input for 0.2s

## Action Mapping

The game uses a reduced action space:
- Action 0: Move left (Left Arrow)
- Action 1: Forward/Continue (auto-action)
- Action 2: Move right (Right Arrow)
- Action 3: Throw key (Space)

## Troubleshooting

### Import errors
- Make sure you're in the correct conda environment: `conda activate procgen_tutorial`
- Verify Python version: `python --version` (should be 3.10 or 3.11)

### "Cannot load library" errors
- This usually means procgen isn't installed properly
- Try: `pip install --force-reinstall procgen==0.10.7`

### Port already in use
- Change the port by setting environment variable:
  ```bash
  set PORT=8003  # Windows
  export PORT=8003  # Linux/Mac
  ```

## Docker Deployment

1. **Build the image:**
   ```bash
   docker build -f Dockerfile.fruitbot -t fruitbot-tutorial .
   ```

2. **Run the container:**
   ```bash
   docker run -p 8002:8002 fruitbot-tutorial
   ```

3. **Access:**
   Open `http://localhost:8002`

## Next Steps

- Play multiple rounds to practice
- After 3 rounds, a "Finish Tutorial" button will appear
- Try to maximize your score by collecting fruits and avoiding enemies

## Support

For issues or questions, check:
- [README_FRUITBOT.md](README_FRUITBOT.md) - Full documentation
- [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) - Technical details
