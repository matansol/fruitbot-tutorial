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
# from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean
# from sqlalchemy.orm import sessionmaker, declarative_base

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

# # SQLAlchemy setup
# DATABASE_URI = os.getenv("AZURE_DATABASE_URI", "sqlite:///tutorial.db")
# engine = create_engine(DATABASE_URI, echo=False)
# SessionLocal = sessionmaker(bind=engine)

# Base = declarative_base()


# class Users(Base):
#     __tablename__ = "users"
#     id = Column(Integer, primary_key=True, index=True)
#     user_id = Column(String(100))
#     timestamp = Column(String(30))
#     simillarity_level = Column(Integer)
#     final_score = Column(Float, default=0.0)  # Default to 0.0 if not set



# def create_database():
#     """Creates the database tables if they do not already exist."""
#     print("Ensuring database tables are created...")
#     Base.metadata.create_all(bind=engine)

# def clear_database():
#     """Clears the database tables."""
#     print("Clearing database tables...")
#     Base.metadata.drop_all(bind=engine)

action_mapping = {0: 1, # Left
                  1: 4, # Forward
                  2: 7, # Right
                  3: 9 # Throw
                  }

class FruitbotTutorialControl:
    def __init__(self, env):
        self.env = env
        self.episode_num = 0
        self.score = 0
        self.last_score = 0
        self.episode_actions = []
        self.episode_images = []
        self.current_obs = None
        self.episode_done = False
        self.step_count = 0
        self.last_action_time = time.time()
        self.pending_action = None

    def reset(self):
        obs = self.env.reset()
        self.score = 0
        self.step_count = 0
        self.episode_actions = []
        self.episode_images = []
        self.current_obs = obs
        self.episode_done = False
        self.last_action_time = time.time()
        self.pending_action = None
        return obs

    def step(self, action):
        if self.episode_done:
            return None
        
        observation, reward, done, info = self.env.step(action_mapping[action])
        
        self.episode_actions.append(action)
        self.step_count += 1
        print(f"Step {self.step_count}: action={action}, reward={reward}, done={done}")
        
        reward = round(float(reward), 1)
        self.score += reward
        self.score = round(self.score, 1)
        
        if done:
            last_episode_score = self.score
            self.last_score = self.score
            
            # Brief pause before resetting
            time.sleep(0.2)
            
            # Reset for next episode
            self.episode_num += 1
            obs = self.reset()
            
            # Return first frame of new episode (don't show done frame)
            img = obs
            return {
                'image': encode_image(img),
                'episode': int(self.episode_num),
                'reward': 0.0,
                'done': False,
                'score': float(self.score),
                'last_score': float(last_episode_score),
                'episode_finished': True,  # Signal that episode just finished and we auto-reset
                'step_count': int(self.step_count)
            }
        
        # In procgen with old gym, observation is the RGB image
        self.current_obs = observation
        img = info.get('rgb', observation)
        
        return {
            'image': encode_image(img),
            'episode': int(self.episode_num),
            'reward': float(reward),
            'done': bool(done),
            'score': float(self.score),
            'last_score': float(self.last_score),
            'episode_finished': bool(self.episode_done),
            'step_count': int(self.step_count)
        }

    def handle_action(self, action_str):
        """
        Map keyboard input to Fruitbot actions
        With ReducedActionWrapper mapping:
        0: left, 1: forward (default), 2: right, 3: throw
        """
        key_to_action = {
            "ArrowLeft": 0,   # left
            "ArrowRight": 2,  # right
            "Space": 3,       # throw
        }
        
        if action_str not in key_to_action:
            return None
        
        action = key_to_action[action_str]
        self.last_action_time = time.time()
        return self.step(action)

    def get_initial_observation(self):
        obs = self.reset()
        self.episode_num += 1
        return self.env.step(1)
        


# Global variables for multi-user support
game_controls = {}
sid_to_user = {}
game_controls_lock = asyncio.Lock()
sid_to_user_lock = asyncio.Lock()


# Background task to handle automatic "forward" actions (stay in place for fruitbot)
async def auto_action_handler():
    """Handle automatic actions when user doesn't press anything for 0.2 seconds"""
    while True:
        await asyncio.sleep(0.01)  # Check every 10ms for faster game speed
        
        current_time = time.time()
        async with game_controls_lock:
            for user_id, game in list(game_controls.items()):
                if game.episode_done:
                    continue
                
                # If minimal time has passed since last action, execute forward action
                if current_time - game.last_action_time >= 0.01:
                    # Use action 1 (forward) as default auto-action for continuous movement
                    result = game.step(1)  # forward
                    
                    if result:
                        game.last_action_time = current_time
                        
                        # Find all sids for this user
                        async with sid_to_user_lock:
                            user_sids = [sid for sid, uid in sid_to_user.items() if uid == user_id]
                        
                        # Emit to all sessions for this user
                        for sid in user_sids:
                            if result.get('episode_finished'):
                                await sio.emit("episode_finished", result, to=sid)
                            else:
                                await sio.emit("game_update", result, to=sid)


# Encode image to base64
def encode_image(img):
    """Convert numpy array to base64 string (without data URI prefix)"""
    pil_img = Image.fromarray(img)
    buffer = BytesIO()
    pil_img.save(buffer, format="PNG")
    buffer.seek(0)
    img_str = base64.b64encode(buffer.getvalue()).decode()
    return img_str  # Return just the base64 string, frontend adds the data URI prefix


# FastAPI Routes
@app.get("/")
def index(request: Request):
    return templates.TemplateResponse("tutorial_index.html", {"request": request})

@app.get("/tutorial")
def tutorial(request: Request):
    return templates.TemplateResponse("tutorial_index.html", {"request": request})

# Serve a no-content favicon to avoid browser 404s during local dev
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
    # Clean up user mapping and game control with thread safety
    async with sid_to_user_lock:
        if sid in sid_to_user:
            user_id = sid_to_user[sid]
            # Remove the sid mapping first
            del sid_to_user[sid]

            # Only clean up the user's game if no other sockets are still mapped to this user
            other_sids_for_user = [s for s, uid in sid_to_user.items() if uid == user_id]
            if other_sids_for_user:
                print(f"Not cleaning game for user {user_id}; other active sockets: {len(other_sids_for_user)}")
                return

            # Critical: Clean up game instance to prevent memory leaks (last socket for this user disconnected)
            async with game_controls_lock:
                if user_id in game_controls:
                    game_instance = game_controls[user_id]
                    # Clear memory-intensive data
                    if hasattr(game_instance, 'episode_images'):
                        game_instance.episode_images.clear()
                    if hasattr(game_instance, 'episode_actions'):
                        game_instance.episode_actions.clear()
                    # Close environment if it has cleanup methods
                    if hasattr(game_instance.env, 'close'):
                        try:
                            game_instance.env.close()
                        except:
                            pass
                    del game_controls[user_id]
                    print(f"Cleaned up resources for user: {user_id}")


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
        else:
            new_game = game_controls[user_id]
    
    response = new_game.get_initial_observation()
    response['action'] = None
    await sio.emit("game_update", response, to=sid)

@sio.event
async def send_action(sid, action):
    async with sid_to_user_lock:
        user_id = sid_to_user.get(sid)
    
    if not user_id:
        await sio.emit("error", {"error": "User not found"}, to=sid)
        return
        
    async with game_controls_lock:
        if user_id not in game_controls:
            await sio.emit("error", {"error": "Game not found"}, to=sid)
            return
        user_game = game_controls[user_id]

    # Accept both string and dict payloads for action to be robust with different clients
    if isinstance(action, dict):
        action = action.get('action') or action.get('key') or action.get('code')

    if not isinstance(action, str):
        await sio.emit("error", {"error": "Invalid action payload"}, to=sid)
        return

    response = user_game.handle_action(action)
    if response is None:
        # await sio.emit("error", {"error": "Episode ended"}, to=sid)
        return
    response["action"] = action

    if response.get("episode_finished"):
        await sio.emit("episode_finished", response, to=sid)
    else:
        await sio.emit("game_update", response, to=sid)

@sio.event
async def finish_tutorial(sid, data):
    """Handle tutorial completion and cleanup resources"""
    user_id = data.get("playerName")
    print(f"Tutorial finished for user: {user_id}")
    
    # Clean up game resources
    async with game_controls_lock:
        if user_id in game_controls:
            game_instance = game_controls[user_id]
            # Clear memory-intensive data
            if hasattr(game_instance, 'episode_images'):
                game_instance.episode_images.clear()
            if hasattr(game_instance, 'episode_actions'):
                game_instance.episode_actions.clear()
            # Close environment
            if hasattr(game_instance.env, 'close'):
                try:
                    game_instance.env.close()
                except:
                    pass
            del game_controls[user_id]
            print(f"Cleaned up resources for finished tutorial: {user_id}")


if __name__ == "__main__":
    print("=== Starting Fruitbot Tutorial App ===", flush=True)
    
    # Start the auto-action handler in the background
    import uvicorn
    
    async def startup_event():
        asyncio.create_task(auto_action_handler())
    
    # Configure uvicorn to run the startup event
    config = uvicorn.Config(
        socket_app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8001)),
        log_level="info"
    )
    server = uvicorn.Server(config)
    
    # Run with startup
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(auto_action_handler())
    loop.run_until_complete(server.serve()) 