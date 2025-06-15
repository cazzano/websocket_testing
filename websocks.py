from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit, send
import os
import time
import threading
from datetime import datetime
import json
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
socketio = SocketIO(app, cors_allowed_origins="*")

# Global variables to store file content and last modified time
file_content = ""
last_modified = None
file_path = "file.txt"
connected_clients = set()

class FileChangeHandler(FileSystemEventHandler):
    def on_modified(self, event):
        global file_content, last_modified
        if not event.is_directory and event.src_path.endswith('file.txt'):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    new_content = f.read()
                    file_content = new_content
                last_modified = datetime.now().isoformat()
                
                # Broadcast to all connected WebSocket clients
                update_data = {
                    'content': file_content,
                    'last_modified': last_modified,
                    'timestamp': datetime.now().isoformat(),
                    'type': 'file_update'
                }
                
                socketio.emit('file_changed', update_data)
                print(f"File updated at {last_modified} - Broadcasted to {len(connected_clients)} clients")
                
            except Exception as e:
                print(f"Error reading file: {e}")
                socketio.emit('error', {'message': f'Error reading file: {e}'})

def initialize_file_watcher():
    """Initialize file watcher in background thread"""
    global file_content, last_modified
    
    # Create file.txt if it doesn't exist
    if not os.path.exists(file_path):
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("Hello WebSocket World! This is initial content.")
    
    # Load initial content
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            file_content = f.read()
        last_modified = datetime.now().isoformat()
    except Exception as e:
        print(f"Error reading initial file: {e}")
        file_content = "Error reading file"
        last_modified = datetime.now().isoformat()
    
    # Start file watcher
    event_handler = FileChangeHandler()
    observer = Observer()
    observer.schedule(event_handler, path='.', recursive=False)
    observer.start()
    
    return observer

# WebSocket Event Handlers
@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    client_id = f"client_{len(connected_clients) + 1}"
    connected_clients.add(client_id)
    
    print(f"Client connected: {client_id} (Total: {len(connected_clients)})")
    
    # Send current file content to newly connected client
    emit('connected', {
        'message': f'Connected as {client_id}',
        'client_id': client_id,
        'timestamp': datetime.now().isoformat()
    })
    
    # Send current file content
    emit('file_content', {
        'content': file_content,
        'last_modified': last_modified,
        'timestamp': datetime.now().isoformat(),
        'type': 'initial_content'
    })

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print(f"Client disconnected (Remaining: {len(connected_clients) - 1})")
    if connected_clients:
        connected_clients.pop()

@socketio.on('get_file_content')
def handle_get_file_content():
    """Handle request for current file content"""
    emit('file_content', {
        'content': file_content,
        'last_modified': last_modified,
        'timestamp': datetime.now().isoformat(),
        'type': 'requested_content'
    })

@socketio.on('get_status')
def handle_get_status():
    """Handle status request"""
    emit('status', {
        'file_exists': os.path.exists(file_path),
        'file_size': os.path.getsize(file_path) if os.path.exists(file_path) else 0,
        'last_modified': last_modified,
        'connected_clients': len(connected_clients),
        'current_content_preview': file_content[:100] + "..." if len(file_content) > 100 else file_content,
        'server_time': datetime.now().isoformat()
    })

@socketio.on('message')
def handle_message(data):
    """Handle generic messages from clients"""
    print(f"Received message: {data}")
    emit('message_received', {
        'message': f"Server received: {data}",
        'timestamp': datetime.now().isoformat()
    })

@socketio.on('broadcast_test')
def handle_broadcast_test():
    """Test broadcast to all clients"""
    socketio.emit('broadcast_message', {
        'message': 'This is a test broadcast to all connected clients',
        'timestamp': datetime.now().isoformat(),
        'sender': 'server'
    })

# Simple web interface for testing
@app.route('/')
def index():
    """Simple web interface for WebSocket testing"""
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>WebSocket File Monitor</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .container { max-width: 800px; margin: 0 auto; }
        .message { margin: 10px 0; padding: 10px; border-radius: 5px; }
        .connected { background-color: #d4edda; }
        .file-update { background-color: #fff3cd; }
        .status { background-color: #d1ecf1; }
        .error { background-color: #f8d7da; }
        textarea { width: 100%; height: 200px; }
        button { margin: 5px; padding: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>WebSocket File Monitor</h1>
        <p>This page connects to the WebSocket server and shows live file updates.</p>
        
        <div id="messages"></div>
        
        <h3>Controls:</h3>
        <button onclick="getFileContent()">Get File Content</button>
        <button onclick="getStatus()">Get Status</button>
        <button onclick="sendMessage()">Send Test Message</button>
        <button onclick="broadcastTest()">Test Broadcast</button>
        
        <h3>File Content:</h3>
        <textarea id="fileContent" readonly></textarea>
        
        <p><strong>Instructions:</strong> Edit file.txt while this page is open to see live updates!</p>
    </div>

    <script>
        const socket = io();
        
        function addMessage(message, className = '') {
            const div = document.createElement('div');
            div.className = `message ${className}`;
            div.innerHTML = `<strong>${new Date().toLocaleTimeString()}</strong>: ${message}`;
            document.getElementById('messages').appendChild(div);
            div.scrollIntoView();
        }
        
        socket.on('connect', function() {
            addMessage('Connected to WebSocket server!', 'connected');
        });
        
        socket.on('connected', function(data) {
            addMessage(`Server says: ${data.message}`, 'connected');
        });
        
        socket.on('file_content', function(data) {
            document.getElementById('fileContent').value = data.content;
            addMessage(`File content received (${data.type})`, 'status');
        });
        
        socket.on('file_changed', function(data) {
            document.getElementById('fileContent').value = data.content;
            addMessage(`🔄 FILE CHANGED! Updated at ${data.last_modified}`, 'file-update');
        });
        
        socket.on('status', function(data) {
            addMessage(`Status: ${data.connected_clients} clients, file size: ${data.file_size} bytes`, 'status');
        });
        
        socket.on('error', function(data) {
            addMessage(`Error: ${data.message}`, 'error');
        });
        
        socket.on('message_received', function(data) {
            addMessage(data.message, 'status');
        });
        
        socket.on('broadcast_message', function(data) {
            addMessage(`📢 Broadcast: ${data.message}`, 'file-update');
        });
        
        socket.on('disconnect', function() {
            addMessage('Disconnected from server', 'error');
        });
        
        function getFileContent() {
            socket.emit('get_file_content');
        }
        
        function getStatus() {
            socket.emit('get_status');
        }
        
        function sendMessage() {
            socket.emit('message', 'Hello from client!');
        }
        
        function broadcastTest() {
            socket.emit('broadcast_test');
        }
    </script>
</body>
</html>
    ''')

if __name__ == '__main__':
    print("🚀 Starting Flask WebSocket File Monitor...")
    print("\n📋 WebSocket Events:")
    print("- 'connect'           -> Client connects")
    print("- 'get_file_content'  -> Request current file content")
    print("- 'get_status'        -> Request server status")
    print("- 'message'           -> Send message to server")
    print("- 'broadcast_test'    -> Test broadcast to all clients")
    
    print("\n📡 WebSocket Responses:")
    print("- 'connected'         -> Connection confirmation")
    print("- 'file_content'      -> File content data")
    print("- 'file_changed'      -> Live file update")
    print("- 'status'            -> Server status")
    print("- 'error'             -> Error messages")
    
    print("\n🌐 Web Interface:")
    print("- http://localhost:5000  -> Test interface")
    
    print(f"\n📁 Monitoring file: {os.path.abspath(file_path)}")
    
    # Initialize file monitoring
    observer = initialize_file_watcher()
    
    print("\n✅ Server ready! Edit file.txt to see WebSocket updates in action!")
    print("💡 Open http://localhost:5000 in your browser for testing")
    
    try:
        socketio.run(app, debug=True, host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
