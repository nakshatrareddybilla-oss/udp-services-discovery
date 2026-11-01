import re, statistics
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def load(path):
    vals = []
    for line in open(path):
        m = re.match(r"\[(\d+)\] ([\d.]+) ms", line)
        if m:
            vals.append(float(m.group(2)))
    return vals

plain = load("logs_plain_final/latency_plain.txt")
sdn = load("logs_sdn_final/latency_sdn.txt")

for name, v in (("Without SDN", plain), ("With SDN", sdn)):
    s = sorted(v)
    p95 = s[int(0.95 * len(s)) - 1]
    print(f"{name}: n={len(v)} first={v[0]:.2f} avg={statistics.mean(v):.2f} "
          f"median={statistics.median(v):.2f} p95={p95:.2f} max={max(v):.2f} ms")

plt.figure(figsize=(9, 4.5))
plt.plot(range(1, len(plain) + 1), plain, label="Without SDN", marker="o", markersize=3)
plt.plot(range(1, len(sdn) + 1), sdn, label="With SDN (Ryu)", marker="s", markersize=3)
plt.xlabel("Query number")
plt.ylabel("Discovery latency (ms)")
plt.title("UDP service discovery latency")
plt.legend()
plt.grid(alpha=0.3)
plt.tight_layout()
plt.savefig("latency_compare.png", dpi=150)
print("Saved latency_compare.png")
