from app import app
import logging
import socket
import multiprocessing
from waitress import serve
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_local_ip():
    """Get the local IP address of this machine"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        hostname = socket.gethostname()
        return socket.gethostbyname(hostname)

def find_available_port(start_port=8080, max_attempts=10):
    """Find an available port starting from start_port"""
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', port))
                return port
        except OSError:
            continue
    raise RuntimeError(f"Could not find an available port after {max_attempts} attempts")

if __name__ == '__main__':
    try:
        # Try to get port from environment variable, otherwise find an available port
        port = int(os.environ.get("PORT", 0))
        if port == 0:
            port = find_available_port()
        
        # Calculate optimal number of workers based on CPU cores
        num_workers = multiprocessing.cpu_count()
        
        # Get the local IP address
        local_ip = get_local_ip()
        
        logger.info(f"Starting Waitress server with {num_workers} workers...")
        logger.info(f"Server is accessible at:")
        logger.info(f"  • Local:   http://localhost:{port}")
        logger.info(f"  • Network: http://{local_ip}:{port}")
        
        # Configure Waitress with workers
        serve(
            app,
            host='127.0.0.1',  # Changed from 0.0.0.0 to localhost only
            port=port,
            threads=4,  # Threads per worker
            url_scheme='http',
            channel_timeout=30,
            cleanup_interval=30,
            max_request_header_size=262144,  # 256KB
            max_request_body_size=1073741824,  # 1GB
            clear_untrusted_proxy_headers=True,
            ident='Katilo ERP'
        )
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        logger.info("Try running with a different port by setting the PORT environment variable")
        logger.info("Example: set PORT=5000 && python wsgi.py")
