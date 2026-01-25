// Connect to the Socket.IO server with polling+WebSocket fallback for local testing
const socket = io({
    transports: ["polling", "websocket"],  // Allow polling fallback for local/dev
    timeout: 20000,
    reconnection: true,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 5000,
    maxReconnectionAttempts: 5,
    forceNew: false,  // Don't force new connection unless needed
    path: "/socket.io",  // Explicit path
    autoConnect: false  // Don't auto-connect, we'll connect manually
});

// Connection management
let connectionAttempts = 0;
let isConnecting = false;

// Connection management for WebSocket-only mode
function connectSocket() {
    if (isConnecting || socket.connected) {
        return;
    }
    
    isConnecting = true;
    connectionAttempts++;
    console.log(`Attempting WebSocket connection (attempt ${connectionAttempts})...`);
    
    socket.connect();
    
    // Set a timeout for connection attempt (shorter for WebSocket)
    setTimeout(() => {
        if (!socket.connected && isConnecting) {
            console.log('WebSocket connection attempt timed out');
            isConnecting = false;
            if (connectionAttempts < 5) {  // Fewer attempts since WebSocket fails faster
                setTimeout(() => connectSocket(), 1000 * connectionAttempts);
            } else {
                console.log('Max connection attempts reached');
                // Could show user an error message here
            }
        }
    }, 5000);  // 5 second timeout for WebSocket
}

// DOM Elements
const welcomePage = document.getElementById('welcome-page');
const gamePage = document.getElementById('game-page');
const finishPage = document.getElementById('finish-page');
const scoreList = document.getElementById('score-list');
const startTutorialButton = document.getElementById('start-tutorial');
const gameImage = document.getElementById('game-image');
const scoreElement = document.getElementById('score');
const stepsElement = document.getElementById('steps');
const loadingOverlay = document.getElementById('loading-overlay');
const roundNumberElement = document.getElementById('round-number');
const roundHeader = document.getElementById('round-header');
const startGameOverlay = document.getElementById('start-game-overlay');
const startGameButton = document.getElementById('start-game-button');

// Game state
let currentScore = 0;
let currentSteps = 0;
let gameReady = false;  // Flag to track if 3-second delay has passed

// Get Prolific ID from URL or generate random
function getProlificId() {
    const params = new URLSearchParams(window.location.search);
    const id = params.get('prolificID');
    return (id && id.trim()) ? id : `user_${Date.now()}`;
}
const prolificID = getProlificId();

// Welcome page -> Game page transition
startTutorialButton.addEventListener('click', () => {
    showLoading();
    
    // If already connected, start immediately
    if (socket.connected) {
        socket.emit('start_game', { playerName: prolificID });
    } else {
        // Connect and emit start_game once connected
        connectSocket();
        socket.once('connect', () => {
            socket.emit('start_game', { playerName: prolificID });
        });
    }
});

// Remove start game button overlay logic (game starts immediately)
// Green button functionality removed - game auto-starts

// Keyboard controls - NEW: Continuous key tracking
const keysCurrentlyPressed = new Set();

document.addEventListener('keydown', (event) => {
    if (!gamePage.classList.contains('active') || !socket.connected || !gameReady) return;
    
    let key = null;
    switch (event.key) {
        case 'ArrowLeft':
            key = 'ArrowLeft';
            break;
        case 'ArrowRight':
            key = 'ArrowRight';
            break;
        case ' ':  // Space key for throw
            key = 'Space';
            event.preventDefault();  // Prevent page scroll
            break;
    }
    
    // Only send if key is valid and not already pressed (avoid key repeat)
    if (key && !keysCurrentlyPressed.has(key)) {
        keysCurrentlyPressed.add(key);
        socket.emit('key_down', { key: key });
    }
});

document.addEventListener('keyup', (event) => {
    if (!gamePage.classList.contains('active') || !socket.connected || !gameReady) return;
    
    let key = null;
    switch (event.key) {
        case 'ArrowLeft':
            key = 'ArrowLeft';
            break;
        case 'ArrowRight':
            key = 'ArrowRight';
            break;
        case ' ':
            key = 'Space';
            break;
    }
    
    if (key && keysCurrentlyPressed.has(key)) {
        keysCurrentlyPressed.delete(key);
        socket.emit('key_up', { key: key });
    }
});

// Clear all keys when window loses focus (prevents stuck keys)
window.addEventListener('blur', () => {
    keysCurrentlyPressed.forEach(key => {
        socket.emit('key_up', { key: key });
    });
    keysCurrentlyPressed.clear();
});

// Socket.IO event handlers for polling+WebSocket fallback
socket.on('connect', () => {
    console.log('WebSocket connected to server with socket ID:', socket.id);
    isConnecting = false;
    connectionAttempts = 0;  // Reset connection attempts on successful connection
});

socket.on('connect_error', (error) => {
    console.log('WebSocket connection error:', error);
    isConnecting = false;
});

socket.on('disconnect', (reason) => {
    console.log('WebSocket disconnected from server. Reason:', reason);
    if (reason === 'transport error') {
        console.log('Attempting WebSocket reconnection...');
        setTimeout(() => connectSocket(), 1000);
    }
});

socket.on('game_update', (data) => {
    updateGameState(data);
});

// NEW: Listen for continuous frame updates from server
socket.on('frame', (data) => {
    // Frames come continuously at ~15 FPS from server
    updateGameState(data);
});

socket.on('episode_finished', (data) => {
    updateGameState(data);
    
    // Show finish page
    gamePage.classList.remove('active');
    finishPage.classList.add('active');
    
    // Calculate bonus level based on score
    const score = data.score || 0;
    const scoreLevel = score > 13 ? 3 : (score > 11 ? 2 : 1);
    
    // Update confirmation number
    const confirmationElement = document.getElementById('confirmation-number');
    if (confirmationElement) {
        confirmationElement.textContent = `232${scoreLevel}`;
    }
    
    // Show final score
    if (scoreList) {
        scoreList.innerHTML = `<li style="list-style-type: none;">Final Score: ${score}</li>`;
    }
});

socket.on('error', (data) => {
    alert(`Error: ${data.error}`);
});

// Helper functions
function showLoading() {
    loadingOverlay.style.display = 'flex';
}

function hideLoading() {
    loadingOverlay.style.display = 'none';
}

function updateGameState(data) {
    // Update game display
    if (data.image && gameImage) {
        // Check if image already has data URI prefix
        if (data.image.startsWith('data:image/')) {
            gameImage.src = data.image;
        } else {
            // Support both PNG and JPEG images
            const format = data.image.startsWith('/9j/') ? 'jpeg' : 'png';
            gameImage.src = `data:image/${format};base64,${data.image}`;
        }
    }
    if (data.score !== undefined && scoreElement) {
        scoreElement.textContent = data.score;
    }
    if (data.step_count !== undefined && stepsElement) {
        stepsElement.textContent = data.step_count;
    }

    // Transition to game page on first update
    if (gamePage && !gamePage.classList.contains('active')) {
        welcomePage?.classList.remove('active');
        gamePage.classList.add('active');
        hideLoading();
        if (roundHeader) roundHeader.style.display = 'block';
        
        // Start 1-second delay before enabling controls
        gameReady = false;
        console.log('Game starting in 1 seconds...');
        setTimeout(() => {
            gameReady = true;
            console.log('Game controls enabled!');
        }, 1000);
    }
}