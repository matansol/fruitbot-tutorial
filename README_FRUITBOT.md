# Fruitbot Tutorial Game

A web-based tutorial for the Procgen Fruitbot environment where users can play the game themselves using keyboard controls.

## Features

- **Interactive Gameplay**: Play Fruitbot using arrow keys and spacebar
- **Auto-action**: If no input for 0.2 seconds, the game automatically moves right
- **Low Latency**: Optimized for smooth, responsive gameplay
- **Multi-round System**: Play multiple rounds and see your scores
- **Real-time Updates**: WebSocket-based communication for instant feedback

## Controls

- **Left Arrow (←)**: Move left
- **Right Arrow (→)**: Move right
- **Space**: Throw key
- **Auto-action**: If idle for 0.2s, automatically moves forward

## Installation & Running

### Option 1: Run Locally

1. Install dependencies:
```bash
pip install -r fruitbot_requirements.txt
```

2. Run the app:
```bash
python fruitbot_tutorial_app.py
```

3. Open browser to: `http://localhost:8002`

### Option 2: Run with Docker

1. Build the Docker image:
```bash
docker build -f Dockerfile.fruitbot -t fruitbot-tutorial .
```

2. Run the container:
```bash
docker run -p 8002:8002 fruitbot-tutorial
```

3. Open browser to: `http://localhost:8002`

### Option 3: Run with Docker Compose

If you have a docker-compose setup, add this service:

```yaml
fruitbot-tutorial:
  build:
    context: ./tutorial_game
    dockerfile: Dockerfile.fruitbot
  ports:
    - "8002:8002"
  environment:
    - PORT=8002
    - PYTHONUNBUFFERED=1
```

## File Structure

```
tutorial_game/
├── fruitbot_tutorial_app.py       # Main Flask/SocketIO app
├── procgen_env_wrapper.py         # Procgen environment wrapper
├── fruitbot_requirements.txt      # Python dependencies (includes procgen)
├── Dockerfile.fruitbot            # Docker configuration
├── templates/
│   └── fruitbot_tutorial_index.html
├── static/
│   └── js/
│       └── fruitbot_tutorial_game.js
└── README_FRUITBOT.md             # This file
```

**Note:** Uses the installed `procgen==0.10.7` package, not a local copy.

## Game Mechanics

- Collect fruits for points
- Avoid enemies (or eliminate them with thrown keys)
- Each round has a time limit
- Score is cumulative across actions
- Complete 3+ rounds to finish the tutorial

## Technical Details

### Backend
- **Framework**: FastAPI + python-socketio
- **Environment**: Procgen Fruitbot (Gymnasium wrapper)
- **Actions**: Reduced action space [left, right, throw]
- **Auto-action Loop**: Background asyncio task handles auto-movement

### Frontend
- **WebSocket Communication**: Socket.IO for real-time updates
- **Key Throttling**: 50ms minimum between key presses
- **Responsive UI**: Optimized for smooth gameplay

## Performance Optimization

1. **Low-latency action handling**: Actions are processed immediately
2. **Throttled key presses**: Prevents input flooding
3. **Auto-action system**: Keeps game flowing even when idle
4. **WebSocket transport**: Fast bidirectional communication
5. **Image encoding**: Base64 encoding for efficient frame transfer

## Environment Variables

- `PORT`: Port to run the app (default: 8002)
- `AZURE_DATABASE_URI`: Database connection string (optional)

## Troubleshooting

### Issue: Slow response time
- Check network latency
- Ensure Docker container has sufficient resources
- Verify WebSocket connection is established

### Issue: Actions not registering
- Check browser console for errors
- Verify Socket.IO connection
- Try refreshing the page

### Issue: Auto-action not working
- This is handled server-side in the background task
- Check server logs for errors

## Development

To modify the game:

1. **Change action mappings**: Edit `handle_action()` in `fruitbot_tutorial_app.py`
2. **Adjust auto-action timing**: Modify the 0.2s threshold in `auto_action_handler()`
3. **Change UI**: Edit `fruitbot_tutorial_index.html` and `fruitbot_tutorial_game.js`
4. **Environment settings**: Modify `create_fruitbot_env()` in `procgen_env_wrapper.py`

## License

See parent project license.
