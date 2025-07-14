# keep_alive.py
import os
from flask import Flask
import logging
import threading # Used to run the Flask app in a separate thread

# Configure logging for this module
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/')
def home():
    """
    A simple home route for health checks.
    Render will hit this endpoint to confirm the service is alive.
    """
    return "Bot's keep-alive server is running!", 200

def run_keep_alive_server():
    """
    Starts the Flask web server.
    It binds to 0.0.0.0 and uses the PORT environment variable provided by Render.
    """
    # Get the port from the environment variable, default to 5000 if not set
    # Render will set the PORT environment variable for Web Services.
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting keep-alive web server on port {port}...")
    # Run the Flask app. debug=False for production.
    app.run(host='0.0.0.0', port=port, debug=False)

if __name__ == '__main__':
    # This block is for testing keep_alive.py independently
    # When integrated, run_keep_alive_server will be called from main.py in a thread
    run_keep_alive_server()
