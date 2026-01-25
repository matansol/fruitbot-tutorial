import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import time
import datetime
import base64
import numpy as np
import asyncio
from io import BytesIO
from PIL import Image
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import socketio
from dotenv import load_dotenv

# Import procgen environment
from procgen_env_wrapper import create_fruitbot_env

# Load environment variables
load_dotenv()

app = FastAPI()

# Socket.IO server configuration
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*", ping_timeout=60, ping_interval=25)

# Wrap the FastAPI app with Socket.IO's ASGI application
app.mount("/static", StaticFiles(directory="static"), name="static")
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)

# Templates
templates = Jinja2Templates(directory="templates")

# Action mapping: simplified actions to procgen actions
# User inputs: 0=left, 1=forward, 2=right, 3=throw
ACTION_FORWARD = 1  # Default action when no key pressed


class FruitbotTutorialControl:
    def __init__(self, env):
        self.env = env
        self.episode_num = 0
        self.score = 0
        self.last_score = 0
        self.episode_actions = []
        self.current_obs = None
        self.episode_done = False
        self.step_count = 0
        
        # New: Track currently pressed keys for continuous input
        self.keys_pressed = set()  # Track which keys are currently held down
        self.game_loop_task = None  # Reference to the game loop task
        self.running = False  # Flag to control game loop

    def reset(self):
        obs = self.env.reset()
        self.score = 0
        self.step_count = 0
        self.episode_actions = []
        self.current_obs = obs
        self.episode_done = False
        self.keys_pressed = set()
        return obs

    def get_current_action(self):
        """Determine action based on currently pressed keys"""
        # Priority: Left > Right > Forward (default)
        if "ArrowLeft" in self.keys_pressed:
            return 0  # left
        elif "ArrowRight" in self.keys_pressed:
            return 2  # right
        elif "Space" in self.keys_pressed:
            return 3  # throw
        else:
            return ACTION_FORWARD  # forward (default)

    def step(self, raw_action):
        if self.episode_done:
            return None
        
        observation, reward, done, info = self.env.step(raw_action)
        
        self.episode_actions.append(raw_action)
        self.step_count += 1
        
        reward = round(float(reward), 1)
        self.score = round(self.score + reward, 1)
        
        self.current_obs = observation
        img = info.get('rgb', observation)

        result = {
            'image': encode_image_fast(img),
            'episode': int(self.episode_num),
            'reward': float(reward),
            'done': bool(done),
            'score': float(self.score),
            'last_score': float(self.last_score),
            'episode_finished': bool(done),
            'step_count': int(self.step_count)
        }

        if done:
            self.last_score = self.score
            self.episode_actions = []
            self.score = 0
            self.step_count = 0
        
        return result

    def get_initial_observation(self):
        """Reset environment and return initial observation dict"""
        self.episode_num += 1
        obs = self.reset()
        obs, _, _, info = self.env.step(ACTION_FORWARD)  # initial forward step to start the game
        img = info.get('rgb', obs)
        return {
            'image': encode_image_fast(img),
            'episode': int(self.episode_num),
            'reward': 0.0,
            'done': False,
            'score': float(self.score),
            'last_score': float(self.last_score),
            'episode_finished': False,
            'step_count': int(self.step_count)
        }


# Global variables for multi-user support
game_controls = {}
sid_to_user = {}
user_game_loops = {}  # Track game loop tasks per user
game_controls_lock = asyncio.Lock()
sid_to_user_lock = asyncio.Lock()


async def user_game_loop(user_id: str):
    """
    Continuous game loop for a specific user.
    Runs at fixed FPS, uses currently pressed keys to determine action.
    """
    TARGET_FPS = 15
    FRAME_TIME = 1.0 / TARGET_FPS
    
    print(f"[GameLoop] Started for user: {user_id}")
    
    while True:
        loop_start = time.time()
        
        # Check if user still exists
        async with game_controls_lock:
            if user_id not in game_controls:
                print(f"[GameLoop] User {user_id} no longer exists, stopping loop")
                break
            game = game_controls[user_id]
            
            if not game.running:
                # Game paused, just wait
                await asyncio.sleep(0.1)
                continue
            
            if game.episode_done or game.current_obs is None:
                await asyncio.sleep(0.1)
                continue
            
            # Get action based on currently pressed keys
            action = game.get_current_action()
            
            # Step the environment
            result = game.step(action)
        
        if result:
            # Find all sids for this user and emit frame
            async with sid_to_user_lock:
                user_sids = [sid for sid, uid in sid_to_user.items() if uid == user_id]
            
            for sid in user_sids:
                if result.get('episode_finished'):
                    await sio.emit("episode_finished", result, to=sid)
                else:
                    await sio.emit("frame", result, to=sid)
        
        # Maintain fixed FPS
        elapsed = time.time() - loop_start
        sleep_time = FRAME_TIME - elapsed
        if sleep_time > 0:
            await asyncio.sleep(sleep_time)
        else:
            # Frame took too long, yield to other tasks
            await asyncio.sleep(0)
    
    print(f"[GameLoop] Ended for user: {user_id}")


# Encode image to base64 - FAST version using JPEG
def encode_image_fast(img):
    """Convert numpy array to base64 string using JPEG (faster than PNG)"""
    pil_img = Image.fromarray(img)
    buffer = BytesIO()
    pil_img.save(buffer, format="JPEG", quality=85)
    buffer.seek(0)
    img_str = base64.b64encode(buffer.getvalue()).decode()
    return img_str


# FastAPI Routes
@app.get("/")
def index(request: Request):
    return templates.TemplateResponse("tutorial_index.html", {"request": request})

@app.get("/tutorial")
def tutorial(request: Request):
    return templates.TemplateResponse("tutorial_index.html", {"request": request})

@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)


# Socket.IO Events
@sio.event
async def connect(sid, environ):
    print(f"Client connected: {sid}")
    
@sio.event
async def disconnect(sid):
    print(f"Client disconnected: {sid}")
    async with sid_to_user_lock:
        if sid in sid_to_user:
            user_id = sid_to_user[sid]
            del sid_to_user[sid]

            # Check if other sockets still connected for this user
            other_sids_for_user = [s for s, uid in sid_to_user.items() if uid == user_id]
            if other_sids_for_user:
                print(f"Not cleaning game for user {user_id}; other active sockets: {len(other_sids_for_user)}")
                return

            # Clean up game instance
            async with game_controls_lock:
                if user_id in game_controls:
                    game_instance = game_controls[user_id]
                    game_instance.running = False  # Stop the game loop
                    if hasattr(game_instance.env, 'close'):
                        try:
                            game_instance.env.close()
                        except:
                            pass
                    del game_controls[user_id]
                    print(f"Cleaned up resources for user: {user_id}")
                
                # Cancel game loop task
                if user_id in user_game_loops:
                    user_game_loops[user_id].cancel()
                    del user_game_loops[user_id]


@sio.event
async def start_game(sid, data):
    user_id = data["playerName"]
    
    async with sid_to_user_lock:
        sid_to_user[sid] = user_id
    
    async with game_controls_lock:
        if user_id not in game_controls:
            env_instance = create_fruitbot_env()
            new_game = FruitbotTutorialControl(env_instance)
            game_controls[user_id] = new_game
            
            # Start dedicated game loop for this user
            loop_task = asyncio.create_task(user_game_loop(user_id))
            user_game_loops[user_id] = loop_task
        else:
            new_game = game_controls[user_id]
        
        # Get initial observation and start running
        response = new_game.get_initial_observation()
        new_game.running = True
    
    response['action'] = None
    await sio.emit("game_update", response, to=sid)


@sio.event
async def key_down(sid, data):
    """Handle key press - just update the pressed keys set"""
    async with sid_to_user_lock:
        user_id = sid_to_user.get(sid)
    
    if not user_id:
        return
    
    key = data.get('key') if isinstance(data, dict) else data
    
    async with game_controls_lock:
        if user_id in game_controls:
            game_controls[user_id].keys_pressed.add(key)
            # print(f"[KeyDown] {user_id}: {key} -> keys: {game_controls[user_id].keys_pressed}")


@sio.event
async def key_up(sid, data):
    """Handle key release - remove from pressed keys set"""
    async with sid_to_user_lock:
        user_id = sid_to_user.get(sid)
    
    if not user_id:
        return
    
    key = data.get('key') if isinstance(data, dict) else data
    
    async with game_controls_lock:
        if user_id in game_controls:
            game_controls[user_id].keys_pressed.discard(key)
            # print(f"[KeyUp] {user_id}: {key} -> keys: {game_controls[user_id].keys_pressed}")


@sio.event
async def send_action(sid, action):
    """Legacy: Still support send_action for backwards compatibility"""
    async with sid_to_user_lock:
        user_id = sid_to_user.get(sid)
    
    if not user_id:
        return
    
    if isinstance(action, dict):
        action = action.get('action') or action.get('key') or action.get('code')
    
    if not isinstance(action, str):
        return
    
    # Simulate a quick key press
    async with game_controls_lock:
        if user_id in game_controls:
            game = game_controls[user_id]
            game.keys_pressed.add(action)
    
    # Release after a short delay
    await asyncio.sleep(0.1)
    
    async with game_controls_lock:
        if user_id in game_controls:
            game_controls[user_id].keys_pressed.discard(action)


@sio.event
async def next_episode(sid):
    """Reset game for another round."""
    try:
        async with sid_to_user_lock:
            user_id = sid_to_user.get(sid)
        if not user_id:
            await sio.emit("error", {"error": "Session not found - please refresh"}, to=sid)
            return
            
        async with game_controls_lock:
            if user_id not in game_controls:
                env_instance = create_fruitbot_env()
                new_game = FruitbotTutorialControl(env_instance)
                game_controls[user_id] = new_game
                
                # Start game loop if not running
                if user_id not in user_game_loops:
                    loop_task = asyncio.create_task(user_game_loop(user_id))
                    user_game_loops[user_id] = loop_task
            
            response = game_controls[user_id].get_initial_observation()
            game_controls[user_id].running = True
            
        await sio.emit("game_update", response, to=sid)
        
    except Exception as e:
        print(f"Error in next_episode: {e}")


@sio.event
async def finish_tutorial(sid, data):
    """Handle tutorial completion and cleanup resources"""
    user_id = data.get("playerName")
    print(f"Tutorial finished for user: {user_id}")
    
    async with game_controls_lock:
        if user_id in game_controls:
            game_instance = game_controls[user_id]
            game_instance.running = False
            if hasattr(game_instance.env, 'close'):
                try:
                    game_instance.env.close()
                except:
                    pass
            del game_controls[user_id]
            
        if user_id in user_game_loops:
            user_game_loops[user_id].cancel()
            del user_game_loops[user_id]
            
        print(f"Cleaned up resources for finished tutorial: {user_id}")


if __name__ == "__main__":
    print("=== Starting Fruitbot Tutorial App V2 (Continuous Frame Push) ===", flush=True)
    import uvicorn
    
    config = uvicorn.Config(
        socket_app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8001)),
        log_level="info"
    )
    server = uvicorn.Server(config)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(server.serve())
