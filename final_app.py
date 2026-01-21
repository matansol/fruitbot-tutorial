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

# SQLAlchemy setup
DATABASE_URI = os.getenv("AZURE_DATABASE_URI", "sqlite:///test.db")
engine = create_engine(DATABASE_URI, echo=False)
SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()

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

def encode_image(img_array):
    """Convert numpy array to base64 encoded image"""
    if isinstance(img_array, np.ndarray):
        img = Image.fromarray(img_array)
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode()
    return None

class FinalGameControl:
    """Controls the game state for a single user session."""
    
    # Class-level constant for key mapping (created once, not per-call)
    KEY_TO_ACTION = {
        "ArrowLeft": 0,   # left
        "ArrowRight": 2,  # right
        "Space": 3,       # throw
    }
    
    def __init__(self, env):
        self.env = env
        self.episode_num = 0
        self.score = 0
        self.last_score = 0
        self.current_obs = None
        self.episode_finished = False
        self.step_count = 0
        self.last_action_time = time.time()
        self.ready_to_play = False
        
    def reset(self):
        """Reset the environment and return initial observation."""
        obs = self.env.reset()
        obs, _, _, info = self.env.step(1)  # Take initial forward step
        img = info.get('rgb', obs)
        
        self.score = 0
        self.step_count = 0
        self.current_obs = obs
        self.episode_finished = False
        self.last_action_time = time.time()
        return img

    def step(self, action):
        """Execute one game step with the given action."""
        if self.episode_finished:
            return None
            
        observation, reward, done, info = self.env.step(action_mapping[action])
        self.last_action_time = time.time()
        self.step_count += 1
        
        reward = round(float(reward), 1)
        self.score = round(self.score + reward, 1)
        
        if done:
            self.last_score = self.score
            self.episode_finished = True
        
        self.current_obs = observation
        img = info.get('rgb', observation)
        
        return self._build_response(img, reward, done)

    def _build_response(self, img, reward=0.0, done=False):
        """Build a standardized response dictionary."""
        return {
            'image': encode_image(img),
            'episode': int(self.episode_num),
            'reward': float(reward),
            'done': bool(done),
            'score': float(self.score),
            'last_score': float(self.last_score),
            'step_count': int(self.step_count)
        }

    def handle_action(self, action_str):
        """Handle a keyboard action from the user."""
        if self.episode_finished:
            return self._build_response(self.current_obs, done=True)
        
        if action_str not in self.KEY_TO_ACTION:
            return None
            
        return self.step(self.KEY_TO_ACTION[action_str])

    def get_initial_observation(self):
        """Get the first frame without starting auto-movement."""
        obs = self.reset()
        self.episode_num += 1
        response = self._build_response(obs)
        response['action'] = None
        return response

# Global state for multi-user support
final_game_controls = {}
final_sid_to_user = {}
final_game_controls_lock = asyncio.Lock()
final_sid_to_user_lock = asyncio.Lock()

async def auto_action_handler():
    # Continuously move forward when player is not pressing keys
    while True:
        await asyncio.sleep(0.02)  # 50 FPS check rate
        current_time = time.time()
        
        # Get snapshot of current games
        async with final_game_controls_lock:
            game_items = list(final_game_controls.items())
        
        for user_id, _ in game_items:
            result = None
            
            # Process game state with lock
            async with final_game_controls_lock:
                if user_id not in final_game_controls:
                    continue
                    
                game = final_game_controls[user_id]
                
                # Skip if not ready or already finished
                if game.episode_finished or not game.ready_to_play:
                    continue
                
                # Auto-move forward if enough time has passed
                if current_time - game.last_action_time >= 0.05:
                    result = game.step(1)  # forward action
            
            # Send update to client (outside lock for better performance)
            if result:
                async with final_sid_to_user_lock:
                    user_sids = [sid for sid, uid in final_sid_to_user.items() if uid == user_id]
                
                event_name = "episode_finished" if result.get('done') else "game_update"
                for sid in user_sids:
                    await sio.emit(event_name, result, to=sid)


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
    async with final_sid_to_user_lock:
        user_id = final_sid_to_user.pop(sid, None)
    print(f"Disconnected: {sid} (user: {user_id})")


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
            if user_id not in final_game_controls:
                final_game_controls[user_id] = FinalGameControl(create_new_env())
            response = final_game_controls[user_id].get_initial_observation()
        
        await sio.emit("game_update", response, to=sid)
        
    except Exception as e:
        print(f"Error in start_game: {e}")
        await sio.emit("error", {"error": f"Failed to start game: {str(e)}"}, to=sid)


@sio.event
async def send_action(sid, action):
    """Handle player keyboard input."""
    try:
        if not action:
            return
        
        async with final_sid_to_user_lock:
            user_id = final_sid_to_user.get(sid)
        
        if not user_id:
            await sio.emit("error", {"error": "Session not found - please refresh"}, to=sid)
            return
            
        async with final_game_controls_lock:
            if user_id not in final_game_controls:
                await sio.emit("error", {"error": "Game not initialized"}, to=sid)
                return
            response = final_game_controls[user_id].handle_action(action)
        
        if not response:
            return
            
        response["action"] = action

        if response["done"]:
            if save_to_db:
                try:
                    session = SessionLocal()
                    session.add(Users(
                        user_id=str(user_id),
                        timestamp=datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                        final_score=response["score"]
                    ))
                    session.commit()
                except Exception as db_err:
                    session.rollback()
                    print(f"Database error: {db_err}")
                finally:
                    session.close()
            await sio.emit("episode_finished", response, to=sid)
        else:
            await sio.emit("game_update", response, to=sid)
            
    except Exception as e:
        print(f"Error in send_action: {e}")
        await sio.emit("error", {"error": f"Action failed: {str(e)}"}, to=sid)


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

save_to_db = True  # Set to True to enable database saving (only final scores, not individual actions)

if __name__ == "__main__":
    # Start cleanup task
    async def run_app():
        # Start the cleanup task
        cleanup_task = asyncio.create_task(cleanup_stale_connections())
        # Start auto-action task
        auto_task = asyncio.create_task(auto_action_handler())
        
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




