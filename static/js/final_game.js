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
const coverPage = document.getElementById('cover-page');
const coverStartButton = document.getElementById('cover-start-button');
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
let gameStarted = false;

// Get Prolific ID from URL or generate random
function getProlificId() {
    const params = new URLSearchParams(window.location.search);
    const id = params.get('prolificID');
    return (id && id.trim()) ? id : `user_${Date.now()}`;
}
const prolificID = getProlificId();

// Cover page -> Welcome page transition
coverStartButton.addEventListener('click', () => {
    coverPage.classList.remove('active');
    welcomePage.classList.add('active');
});

// Welcome page -> Game page transition
startTutorialButton.addEventListener('click', () => {
    showLoading();
    connectSocket();
    socket.emit('start_game', { playerName: prolificID });
});

// Green "Start Game" button -> activates the game
startGameButton.addEventListener('click', () => {
    gameStarted = true;
    startGameOverlay.style.display = 'none';
    if (roundHeader) roundHeader.style.display = 'block';
    socket.emit('activate_game');
});

// Keyboard controls
const KEY_ACTIONS = {
    'ArrowLeft': 'ArrowLeft',
    'ArrowRight': 'ArrowRight',
    ' ': 'Space'
};

document.addEventListener('keydown', (event) => {
    if (!gamePage.classList.contains('active') || !gameStarted) return;
    
    const action = KEY_ACTIONS[event.key];
    if (action) {
        event.preventDefault();
        socket.emit('send_action', action);
    }
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
        gameImage.src = `data:image/png;base64,${data.image}`;
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
        
        // Show start button overlay (game paused until clicked)
        if (!gameStarted && startGameOverlay) {
            startGameOverlay.style.display = 'flex';
        }
    }
}