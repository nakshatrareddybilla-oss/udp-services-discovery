import socket, json, time, sys

REGISTRY = ("10.0.0.1", 5000)
service = sys.argv[1] if len(sys.argv) > 1 else "echo"
N = int(sys.argv[2]) if len(sys.argv) > 2 else 20

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.settimeout(2)
latencies, lost = [], 0

for i in range(N):
    t0 = time.perf_counter()
    s.sendto(json.dumps({"type": "QUERY", "service": service, "ts": t0}).encode(), REGISTRY)
    try:
        data, _ = s.recvfrom(4096)
        rtt = (time.perf_counter() - t0) * 1000
        latencies.append(rtt)
        services = json.loads(data.decode())["services"]
        print(f"[{i+1}] {rtt:.2f} ms -> {services}")
    except socket.timeout:
        lost += 1
        print(f"[{i+1}] timeout (registry unreachable)")
    time.sleep(0.5)

if latencies:
    print(f"\nDiscovery latency: min={min(latencies):.2f} "
          f"avg={sum(latencies)/len(latencies):.2f} max={max(latencies):.2f} ms, lost={lost}")
