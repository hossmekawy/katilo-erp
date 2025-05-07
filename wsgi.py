from app import app
import logging
import socket
import webbrowser

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_local_ip():
    """Get the local IP address of this machine"""
    try:
        # Create a socket to determine the outgoing IP address
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # This doesn't actually establish a connection
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        # Fallback method if the above fails
        hostname = socket.gethostname()
        return socket.gethostbyname(hostname)

if __name__ == '__main__':
    from waitress import serve
    import os
    import multiprocessing
    import threading
    import time
    
    # Get port from environment variable or use default 8080
    port = int(os.environ.get("PORT", 8080))
    
    # Try alternative ports if the default port is unavailable
    max_port_attempts = 10
    for attempt in range(max_port_attempts):
        try:
            # Test if we can bind to this port
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.bind(('0.0.0.0', port))
            test_socket.close()
            # If we get here, the port is available
            break
        except OSError as e:
            logger.warning(f"Port {port} is not available: {e}")
            if attempt < max_port_attempts - 1:
                port += 1
                logger.info(f"Trying port {port} instead...")
            else:
                logger.error(f"Could not find an available port after {max_port_attempts} attempts")
                raise
    
    # Calculate a reasonable number of threads based on CPU cores
    num_cores = multiprocessing.cpu_count()
    threads = (2 * num_cores) + 1
    
    # Get the local IP address
    local_ip = get_local_ip()
    
    logger.info(f"Starting Waitress server on port {port} with {threads} threads...")
    logger.info(f"Server is accessible at:")
    logger.info(f"  • Local:   http://localhost:{port}")
    logger.info(f"  • Network: http://{local_ip}:{port}")
    
    # Function to open browser after a short delay
    def open_browser():
        # Wait for server to start
        time.sleep(1.5)
        url = f"http://localhost:{port}"
        logger.info(f"Opening browser at {url}")
        webbrowser.open(url)
    
    # Start browser in a separate thread so it doesn't block server startup
    browser_thread = threading.Thread(target=open_browser)
    browser_thread.daemon = True
    browser_thread.start()
    
    # Start the server
    serve(app, host='0.0.0.0', port=port, threads=threads)
