import socket, json, time, threading, sys

REGISTRY = ("10.0.0.1", 5000)
SERVICE = sys.argv[1]            # e.g. echo
PORT = int(sys.argv[2])          # e.g. 6000

def advertise():
    s = None
    while True:
        msg = {"type": "ADVERTISE", "service": SERVICE, "port": PORT}
        try:
            if s is None:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.sendto(json.dumps(msg).encode(), REGISTRY)
        except OSError:
            if s:
                s.close()
            s = None             # network down: rebuild the socket next round
        time.sleep(2)

threading.Thread(target=advertise, daemon=True).start()

# the actual service: a simple UDP echo
svc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
svc.bind(("0.0.0.0", PORT))
print(f"{SERVICE} service running on UDP {PORT}", flush=True)
while True:
    data, addr = svc.recvfrom(1024)
    try:
        svc.sendto(b"ECHO: " + data, addr)
    except OSError:
        pass
