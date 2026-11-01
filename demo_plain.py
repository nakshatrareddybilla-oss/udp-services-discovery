import time, subprocess
from mininet.net import Mininet
from mininet.node import OVSBridge
from mininet.log import setLogLevel

def log(title):
    print(f"\n===== {title} =====", flush=True)

def registry_log():
    print(open("logs/registry.log").read(), flush=True)

setLogLevel("warning")
net = Mininet(switch=OVSBridge, controller=None)
s1 = net.addSwitch("s1")
h1, h2, h3, h4 = [net.addHost(f"h{i}") for i in range(1, 5)]
for h in (h1, h2, h3, h4):
    net.addLink(h, s1)
net.start()

def start(host, cmd, logfile):
    f = open(logfile, "w")
    return host.popen(cmd, stdout=f, stderr=subprocess.STDOUT)

reg = start(h1, "python3 registry.py", "logs/registry.log")
srv2 = start(h2, "python3 server.py echo 6000", "logs/h2.log")
srv3 = start(h3, "python3 server.py echo 6001", "logs/h3.log")
time.sleep(4)

log("1. Discovery: both servers visible")
print(h4.cmd("python3 client.py echo 3"))

log("2. Baseline latency (100 queries, takes about 50 s)")
h4.cmd("python3 client.py echo 100 > logs/latency_plain.txt")
print(h4.cmd("tail -1 logs/latency_plain.txt"))

log("3. Timeout: stop server on h2, wait 8 s")
srv2.terminate()
time.sleep(8)
registry_log()
print(h4.cmd("python3 client.py echo 3"))

log("4. Dynamic registration: start h2 server again")
srv2 = start(h2, "python3 server.py echo 6000", "logs/h2.log")
time.sleep(3)
registry_log()
print(h4.cmd("python3 client.py echo 3"))

log("5. Link failure: h3 link down")
net.configLinkStatus("s1", "h3", "down")
time.sleep(8)
registry_log()
print(h4.cmd("python3 client.py echo 3"))

log("6. Link back up")
net.configLinkStatus("s1", "h3", "up")
time.sleep(7)
registry_log()
print(h4.cmd("python3 client.py echo 3"))

open("logs/registry_final.log", "w").write(open("logs/registry.log").read())
for p in (reg, srv2, srv3):
    p.terminate()
net.stop()
print("\nDONE. Evidence saved in logs/", flush=True)
