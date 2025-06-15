from flask import Flask, jsonify, Response
import os
import time
import threading
from datetime import datetime
import json
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

app = Flask(__name__)

# Global variables to store file content and last modified time
file_content = ""
last_modified = None
file_path = "file.txt"

class FileChangeHandler(FileSystemEventHandler):
    def on_modified(self, event):
        global file_content, last_modified
        if not event.is_directory and event.src_path.endswith('file.txt'):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    file_content = f.read()
                last_modified = datetime.now().isoformat()
                print(f"File updated at {last_modified}")
            except Exception as e:
                print(f"Error reading file: {e}")

def initialize_file_watcher():
    """Initialize file watcher in background thread"""
    global file_content, last_modified
    
    # Create file.txt if it doesn't exist
    if not os.path.exists(file_path):
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("Hello World! This is initial content.")
    
    # Load initial content
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            file_content = f.read()
        last_modified = datetime.now().isoformat()
    except Exception as e:
        print(f"Error reading initial file: {e}")
        file_content = "Error reading file"
    
    # Start file watcher
    event_handler = FileChangeHandler()
    observer = Observer()
    observer.schedule(event_handler, path='.', recursive=False)
    observer.start()
    
    return observer

# REST API endpoint - Standard approach
@app.route('/api/hello', methods=['GET'])
def get_file_content():
    """Standard REST API - returns current file content"""
    return jsonify({
        'content': file_content,
        'last_modified': last_modified,
        'timestamp': datetime.now().isoformat(),
        'type': 'standard_rest'
    })

# Server-Sent Events endpoint - XMPP-like persistent connection
@app.route('/api/hello/stream', methods=['GET'])
def stream_file_content():
    """XMPP-like persistent connection using Server-Sent Events"""
    def generate():
        last_sent_content = ""
        while True:
            if file_content != last_sent_content:
                data = {
                    'content': file_content,
                    'last_modified': last_modified,
                    'timestamp': datetime.now().isoformat(),
                    'type': 'live_stream'
                }
                yield f"data: {json.dumps(data)}\n\n"
                last_sent_content = file_content
            time.sleep(1)  # Check every second
    
    return Response(generate(), mimetype='text/plain')

# WebSocket-like endpoint using chunked response
@app.route('/api/hello/live', methods=['GET'])
def live_file_content():
    """Long-polling approach - keeps connection open"""
    def generate():
        last_sent_content = ""
        start_time = time.time()
        
        while time.time() - start_time < 60:  # Keep alive for 60 seconds
            if file_content != last_sent_content:
                data = {
                    'content': file_content,
                    'last_modified': last_modified,
                    'timestamp': datetime.now().isoformat(),
                    'type': 'long_polling',
                    'change_detected': True
                }
                yield json.dumps(data) + '\n'
                last_sent_content = file_content
            else:
                # Send heartbeat
                heartbeat = {
                    'type': 'heartbeat',
                    'timestamp': datetime.now().isoformat()
                }
                yield json.dumps(heartbeat) + '\n'
            
            time.sleep(2)  # Check every 2 seconds
        
        # Connection timeout
        yield json.dumps({
            'type': 'connection_timeout',
            'message': 'Connection closed after 60 seconds'
        }) + '\n'
    
    return Response(generate(), mimetype='application/json')

# Status endpoint
@app.route('/api/status', methods=['GET'])
def get_status():
    """Check if file monitoring is working"""
    return jsonify({
        'file_exists': os.path.exists(file_path),
        'file_size': os.path.getsize(file_path) if os.path.exists(file_path) else 0,
        'last_modified': last_modified,
        'current_content_preview': file_content[:100] + "..." if len(file_content) > 100 else file_content,
        'server_time': datetime.now().isoformat()
    })

if __name__ == '__main__':
    print("Starting Flask File Monitor API...")
    print("Creating file.txt for testing...")
    
    # Initialize file watcher
    observer = initialize_file_watcher()
    
    print(f"Monitoring file: {os.path.abspath(file_path)}")
    print("\nAvailable endpoints:")
    print("- GET /api/hello          -> Standard REST (current content)")
    print("- GET /api/hello/stream   -> Server-Sent Events (real-time)")
    print("- GET /api/hello/live     -> Long-polling (60s connection)")
    print("- GET /api/status         -> File monitoring status")
    print("\nTo test:")
    print("1. Start server: python app.py")
    print("2. Edit file.txt in another window")
    print("3. Call any endpoint to see live updates!")
    
    try:
        app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
