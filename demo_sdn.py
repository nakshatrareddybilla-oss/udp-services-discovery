import time, subprocess
from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController
from mininet.log import setLogLevel

def log(t):
    print(f"\n===== {t} =====", flush=True)

def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout

def registry_log():
    print(open("logs/registry.log").read(), flush=True)

def start(host, cmd, logfile):
    return host.popen(cmd, stdout=open(logfile, "w"), stderr=subprocess.STDOUT)

open("blocked.txt", "w").close()
ryu = subprocess.Popen(["venv/bin/ryu-manager", "controller.py"],
                       stdout=open("logs/controller.log", "w"), stderr=subprocess.STDOUT)
time.sleep(4)

setLogLevel("warning")
net = Mininet(switch=OVSSwitch, controller=None)
net.addController("c0", controller=RemoteController, ip="127.0.0.1", port=6653)
s1 = net.addSwitch("s1", protocols="OpenFlow13")
h1, h2, h3, h4 = [net.addHost(f"h{i}") for i in range(1, 5)]
for h in (h1, h2, h3, h4):
    net.addLink(h, s1)
net.start()

if not net.waitConnected(timeout=20):
    print("Switch did not connect to Ryu. Controller log:")
    print(open("logs/controller.log").read())
    net.stop(); ryu.terminate(); raise SystemExit(1)

reg = start(h1, "python3 registry.py", "logs/registry.log")
srv2 = start(h2, "python3 server.py echo 6000", "logs/h2.log")
srv3 = start(h3, "python3 server.py echo 6001", "logs/h3.log")
time.sleep(5)

log("1. Discovery through the SDN switch (first query goes via controller)")
print(h4.cmd("python3 client.py echo 5"))

log("2. Latency with SDN (100 queries, about 50 s)")
h4.cmd("python3 client.py echo 100 > logs/latency_sdn.txt")
print(h4.cmd("tail -1 logs/latency_sdn.txt"))

log("3. SDN policy: UDP to a non-service port 7777 is dropped")
h4.cmd("python3 -c \"import socket;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.sendto(b'x',('10.0.0.2',7777))\"")
time.sleep(1)
print(sh("grep -E 'DROP' logs/controller.log | tail -5"))

log("4. SDN control: controller blocks h3 (10.0.0.3) live")
open("blocked.txt", "w").write("10.0.0.3\n")
time.sleep(10)
registry_log()
print(s1.cmd("ovs-ofctl -O OpenFlow13 dump-flows s1 | grep priority=10"))
print(h4.cmd("python3 client.py echo 3"))

log("5. Controller unblocks h3")
open("blocked.txt", "w").close()
time.sleep(10)
registry_log()
print(s1.cmd("ovs-ofctl -O OpenFlow13 dump-flows s1 | grep priority=10"))
print(h4.cmd("python3 client.py echo 3"))

log("6. Flow table on the switch")
print(s1.cmd("ovs-ofctl -O OpenFlow13 dump-flows s1"))

log("7. Controller decisions")
print(sh("grep -E 'BLOCK|DROP' logs/controller.log"))

for p in (reg, srv2, srv3):
    p.terminate()
net.stop()
ryu.terminate()
print("\nDONE. Evidence saved in logs/", flush=True)
