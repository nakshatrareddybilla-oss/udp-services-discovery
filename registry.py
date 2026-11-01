import socket, json, time, threading

PORT, TTL = 5000, 6
registry = {}            # key -> {service, host, port, last_seen}
lock = threading.Lock()

def reaper():
    while True:
        time.sleep(1)
        now = time.time()
        with lock:
            for k in [k for k, v in registry.items() if now - v["last_seen"] > TTL]:
                print(f"[TIMEOUT] {k} removed (server unavailable)", flush=True)
                del registry[k]

threading.Thread(target=reaper, daemon=True).start()

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", PORT))
print("Registry listening on UDP", PORT, flush=True)

while True:
    data, addr = sock.recvfrom(4096)
    try:
        msg = json.loads(data.decode())
    except ValueError:
        continue

    if msg["type"] == "ADVERTISE":
        key = f'{msg["service"]}@{addr[0]}:{msg["port"]}'
        with lock:
            new = key not in registry
            registry[key] = {"service": msg["service"], "host": addr[0],
                             "port": msg["port"], "last_seen": time.time()}
        if new:
            print(f"[REGISTER] {key}", flush=True)

    elif msg["type"] == "QUERY":
        with lock:
            found = [{"host": v["host"], "port": v["port"], "service": v["service"]}
                     for v in registry.values()
                     if msg["service"] in ("*", v["service"])]
        reply = {"type": "RESPONSE", "ts": msg["ts"], "services": found}
        sock.sendto(json.dumps(reply).encode(), addr)

    elif msg["type"] == "BYE":      # graceful shutdown
        key = f'{msg["service"]}@{addr[0]}:{msg["port"]}'
        with lock:
            registry.pop(key, None)
        print(f"[DEREGISTER] {key}", flush=True)
