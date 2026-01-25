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
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base

# Import procgen environment
from procgen_env_wrapper import create_fruitbot_env

# Load environment variables
load_dotenv()

# FastAPI application
app = FastAPI(title="FruitBot Final Game")

# Socket.IO server
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")

# Wrap the FastAPI app with Socket.IO's ASGI application
app.mount("/static", StaticFiles(directory="static"), name="static")
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)

# Templates
templates = Jinja2Templates(directory="templates")

# Action mapping: simplified actions to procgen actions
# User inputs: 0=left, 1=forward, 2=right, 3=throw
ACTION_FORWARD = 1  # Default action when no key pressed

# SQLAlchemy setup
DATABASE_URI = os.getenv("AZURE_DATABASE_URI", "sqlite:///test.db")
engine = create_engine(DATABASE_URI, echo=False)
SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()
save_to_db = True  # Set to True to enable database saving (only final scores, not individual actions)


class Users(Base):
    __tablename__ = "users"  # Use the same table as the main app
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(100))
    timestamp = Column(String(30))
    similarity_level = Column(Integer)
    final_score = Column(Float, default=0.0)

# Action mapping for Fruitbot (reduced action space)
action_mapping = {0: 1,  # Left
                  1: 4,  # Forward
                  2: 7,  # Right
                  3: 9   # Throw
                  }

class FinalGameControl:
    """Controls the game state for a single user session."""
    
    def __init__(self, env):
        self.env = env
        self.episode_num = 0
        self.score = 0
        self.last_score = 0
        self.current_obs = None
        self.episode_finished = False
        self.step_count = 0
        self.start_flag = False # if the game has started
        self.start_time = None  # Track when game loop starts
        
        # New: Track currently pressed keys for continuous input
        self.keys_pressed = set()  # Track which keys are currently held down
        self.running = False  # Flag to control game loop
        
    def reset(self):
        """Reset the environment and return initial observation."""
        obs = self.env.reset()
        self.score = 0
        self.step_count = 0
        self.current_obs = obs
        self.episode_finished = False
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

    def step(self, action):
        """Execute one game step with the given action."""
        if self.episode_finished:
            return None
        
        observation, reward, done, info = self.env.step(action)
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
            self.episode_finished = True
        
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

# Global state for multi-user support
final_game_controls = {}
final_sid_to_user = {}
user_game_loops = {}  # Track game loop tasks per user
final_game_controls_lock = asyncio.Lock()
final_sid_to_user_lock = asyncio.Lock()


async def user_game_loop(user_id: str):
    """
    Continuous game loop for a specific user.
    Runs at fixed FPS, uses currently pressed keys to determine action.
    """
    TARGET_FPS = 15
    FRAME_TIME = 1.0 / TARGET_FPS
    
    print(f"[GameLoop] Started for user: {user_id}")
    
    # Set start time for initial delay
    async with final_game_controls_lock:
        if user_id in final_game_controls:
            final_game_controls[user_id].start_time = time.time()
    
    while True:
        loop_start = time.time()
        
        # Check if user still exists
        async with final_game_controls_lock:
            if user_id not in final_game_controls:
                print(f"[GameLoop] User {user_id} no longer exists, stopping loop")
                break
            game = final_game_controls[user_id]
            
            if not game.running:
                # Game paused, just wait
                await asyncio.sleep(0.1)
                continue
            
            if game.episode_finished or game.current_obs is None:
                await asyncio.sleep(0.1)
                continue
            
            # Check if 3-second initial delay has passed
            if game.start_time and (time.time() - game.start_time) < 3.0:
                # Still in initial delay, don't process actions yet
                await asyncio.sleep(0.1)
                continue
            
            # Get action based on currently pressed keys
            action = game.get_current_action()
            
            # Step the environment
            result = game.step(action)
        
        if result:
            # Find all sids for this user and emit frame
            async with final_sid_to_user_lock:
                user_sids = [sid for sid, uid in final_sid_to_user.items() if uid == user_id]
            
            for sid in user_sids:
                if result.get('episode_finished'):
                    # Save to database when episode finishes
                    if save_to_db:
                        try:
                            session = SessionLocal()
                            session.add(Users(
                                user_id=str(user_id),
                                timestamp=datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                                final_score=result["score"]
                            ))
                            session.commit()
                            print(f"Saved final score for user {user_id} to database with score {result['score']}")
                        except Exception as db_err:
                            session.rollback()
                            print(f"Database error: {db_err}")
                        finally:
                            session.close()
                    
                    await sio.emit("episode_finished", result, to=sid)
                else:
                    await sio.emit("frame", result, to=sid)
        
            if result.get('episode_finished'):
                break
        
        # Maintain fixed FPS
        elapsed = time.time() - loop_start
        sleep_time = FRAME_TIME - elapsed
        if sleep_time > 0:
            await asyncio.sleep(sleep_time)
        else:
            # Frame took too long, yield to other tasks
            await asyncio.sleep(0)
    
    print(f"[GameLoop] Ended for user: {user_id}")


def encode_image_fast(img):
    """Encode numpy image to base64 JPEG string"""
    img_pil = Image.fromarray(img)
    buffered = BytesIO()
    img_pil.save(buffered, format="JPEG", quality=85)
    img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
    return f"data:image/jpeg;base64,{img_str}"


def create_new_env():
    """Create a Fruitbot environment for the final game"""
    env_instance = create_fruitbot_env()
    return env_instance

# FastAPI Routes for Final App
@app.get("/")
def index(request: Request):
    return templates.TemplateResponse("final_index.html", {"request": request})

@app.get("/final")
def final_route(request: Request):
    return templates.TemplateResponse("final_index.html", {"request": request})

# Serve a no-content favicon to avoid browser 404s during local dev
@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)

@app.get("/health")
def health_check():
    """Health check endpoint for Azure Container Apps"""
    return {
        "status": "healthy",
        "app_type": "final",
        "active_connections": len(final_sid_to_user),
        "active_games": len(final_game_controls),
        "timestamp": datetime.datetime.utcnow().isoformat()
    }

# Socket.IO Events with enhanced error handling for WebSocket-only mode
@sio.event
async def connect(sid, environ):
    print(f"Final App - WebSocket client connected: {sid}")
    # Store connection info for better debugging
    user_agent = environ.get('HTTP_USER_AGENT', 'Unknown')
    transport = environ.get('transport', 'Unknown')
    print(f"User agent: {user_agent[:100]}...")
    print(f"Transport: {transport}")
    # Send immediate acknowledgment to confirm connection
    await sio.emit("connection_confirmed", {"status": "connected", "transport": "websocket", "app": "final"}, to=sid)

@sio.event
async def disconnect(sid):
    print(f"Client disconnected: {sid}")
    async with final_sid_to_user_lock:
        if sid in final_sid_to_user:
            user_id = final_sid_to_user[sid]
            del final_sid_to_user[sid]

            # Check if other sockets still connected for this user
            other_sids_for_user = [s for s, uid in final_sid_to_user.items() if uid == user_id]
            if other_sids_for_user:
                print(f"Not cleaning game for user {user_id}; other active sockets: {len(other_sids_for_user)}")
                return

            # Clean up game instance
            async with final_game_controls_lock:
                if user_id in final_game_controls:
                    game_instance = final_game_controls[user_id]
                    game_instance.running = False  # Stop the game loop
                    if hasattr(game_instance.env, 'close'):
                        try:
                            game_instance.env.close()
                        except:
                            pass
                    del final_game_controls[user_id]
                    print(f"Cleaned up resources for user: {user_id}")
                
                # Cancel game loop task
                if user_id in user_game_loops:
                    user_game_loops[user_id].cancel()
                    del user_game_loops[user_id]


@sio.event
async def start_game(sid, data):
    """Initialize a new game session for the user."""
    try:
        if not data or "playerName" not in data:
            await sio.emit("error", {"error": "Missing playerName"}, to=sid)
            return
            
        user_id = str(data["playerName"]).strip()
        if not user_id:
            await sio.emit("error", {"error": "Invalid player name"}, to=sid)
            return
        
        print(f"Starting game for user: {user_id}")
        
        async with final_sid_to_user_lock:
            old_sid = next((s for s, u in final_sid_to_user.items() if u == user_id), None)
            if old_sid and old_sid != sid:
                del final_sid_to_user[old_sid]
                await sio.disconnect(old_sid)
            final_sid_to_user[sid] = user_id
        
        async with final_game_controls_lock:
            # Cancel existing game loop if present
            if user_id in user_game_loops:
                print(f"Cancelling existing game loop for user: {user_id}")
                user_game_loops[user_id].cancel()
                try:
                    await user_game_loops[user_id]
                except asyncio.CancelledError:
                    pass
                del user_game_loops[user_id]
            
            # Clean up old game instance if exists
            if user_id in final_game_controls:
                old_game = final_game_controls[user_id]
                old_game.running = False
                if hasattr(old_game.env, 'close'):
                    try:
                        old_game.env.close()
                    except:
                        pass
            
            # Create fresh game instance
            final_game_controls[user_id] = FinalGameControl(create_new_env())
            game = final_game_controls[user_id]
            response = game.get_initial_observation()
            
            # Start the game loop
            game.running = True
            user_game_loops[user_id] = asyncio.create_task(user_game_loop(user_id))
            print(f"Started fresh game loop for user: {user_id}")
        
        await sio.emit("game_update", response, to=sid)
        
    except Exception as e:
        print(f"Error in start_game: {e}")
        await sio.emit("error", {"error": f"Failed to start game: {str(e)}"}, to=sid)


@sio.event
async def key_down(sid, data):
    """Handle key press events."""
    try:
        key = data.get('key')
        if not key:
            return
        
        async with final_sid_to_user_lock:
            user_id = final_sid_to_user.get(sid)
        
        if not user_id:
            return
        
        async with final_game_controls_lock:
            if user_id in final_game_controls:
                final_game_controls[user_id].keys_pressed.add(key)
    except Exception as e:
        print(f"Error in key_down: {e}")


@sio.event
async def key_up(sid, data):
    """Handle key release events."""
    try:
        key = data.get('key')
        if not key:
            return
        
        async with final_sid_to_user_lock:
            user_id = final_sid_to_user.get(sid)
        
        if not user_id:
            return
        
        async with final_game_controls_lock:
            if user_id in final_game_controls:
                final_game_controls[user_id].keys_pressed.discard(key)
    except Exception as e:
        print(f"Error in key_up: {e}")

@sio.event
async def activate_game(sid):
    """Activate auto-actions when user clicks green start button."""
    async with final_sid_to_user_lock:
        user_id = final_sid_to_user.get(sid)
    if not user_id:
        return
        
    async with final_game_controls_lock:
        if user_id in final_game_controls:
            final_game_controls[user_id].ready_to_play = True


@sio.event
async def next_episode(sid):
    """Reset game for another round."""
    try:
        async with final_sid_to_user_lock:
            user_id = final_sid_to_user.get(sid)
        if not user_id:
            await sio.emit("error", {"error": "Session not found - please refresh"}, to=sid)
            return
            
        async with final_game_controls_lock:
            if user_id not in final_game_controls:
                await sio.emit("error", {"error": "Game not initialized"}, to=sid)
                return
            response = final_game_controls[user_id].get_initial_observation()
            
        await sio.emit("game_update", response, to=sid)
        
    except Exception as e:
        print(f"Error in next_episode: {e}")

async def cleanup_stale_connections():
    """Periodically clean up game controls for disconnected users."""
    while True:
        await asyncio.sleep(300)  # Every 5 minutes
        try:
            async with final_sid_to_user_lock:
                active_users = set(final_sid_to_user.values())
            
            async with final_game_controls_lock:
                stale = [uid for uid in final_game_controls if uid not in active_users]
                for uid in stale:
                    del final_game_controls[uid]
                if stale:
                    print(f"Cleaned up {len(stale)} stale games. Active: {len(final_game_controls)}")
        except Exception as e:
            print(f"Cleanup error: {e}")


if __name__ == "__main__":
    print("=== Starting Fruitbot Final App (Continuous Frame Push) ===", flush=True)
    async def run_app():
        # Start the cleanup task
        cleanup_task = asyncio.create_task(cleanup_stale_connections())
        
        # Import uvicorn here to avoid import order issues
        import uvicorn
        config = uvicorn.Config(
            socket_app,
            host="0.0.0.0",
            port=int(os.environ.get("PORT", 8002)),  # Different port for final app
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()
    
    asyncio.run(run_app())




