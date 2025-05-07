from app import app
from waitress import serve
import socket

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

if __name__ == "__main__":
    port = 8000
    ip = get_local_ip()
    print("🚀 Katilo ERP is now running with Waitress")
    print("==========================================")
    print(f" * Running on http://127.0.0.1:{port}")
    print(f" * Running on http://{ip}:{port}")
    print(" * Press CTRL+C to quit")
    print("==========================================")

    serve(app, host="0.0.0.0", port=port)
