#!/usr/bin/python3
"CSC458 Fall 2025 Programming Assignment 2: Bufferbloat"

import math
import os
import subprocess
import sys
from argparse import ArgumentParser
from multiprocessing import Process
from time import sleep, time
from typing import List

import termcolor as T
from mininet.clean import cleanup
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import info, lg
from mininet.net import Mininet
from mininet.node import CPULimitedHost
from mininet.topo import Topo
from mininet.util import dumpNodeConnections

from monitor import monitor_qlen

# TODO: Don't just read the TODO sections in this code.  Remember that
# one of the goals of this assignment is for you to learn how to use
# Mininet.

parser = ArgumentParser(description="Bufferbloat tests")
parser.add_argument(
    "--bw-host", "-B", type=float, help="Bandwidth of host links (Mb/s)", default=1000
)

parser.add_argument(
    "--bw-net",
    "-b",
    type=float,
    help="Bandwidth of bottleneck (network) link (Mb/s)",
    required=True,
)

parser.add_argument(
    "--delay", type=float, help="Link propagation delay (ms)", required=True
)

parser.add_argument("--dir", "-d", help="Directory to store outputs", required=True)

parser.add_argument(
    "--time", "-t", help="Duration (sec) to run the experiment", type=int, default=10
)

parser.add_argument(
    "--maxq",
    type=int,
    help="Max buffer size of network interface in packets",
    default=100,
)

# Linux uses CUBIC-TCP by default that doesn't have the usual sawtooth
# behaviour.  For those who are curious, invoke this script with
# --cong cubic and see what happens...
# sysctl -a | grep cong should list some interesting parameters.
parser.add_argument(
    "--cong", help="Congestion control algorithm to use", default="reno"
)

# Expt parameters
args = parser.parse_args()


class BBTopo(Topo):
    "Simple topology for bufferbloat experiment."

    def build(self, n=2) -> None:
        # Here are two hosts
        hosts = [self.addHost(f"h{i}") for i in range(1, n + 1)]

        # Here I have created a switch.  If you change its name, its
        # interface names will change from s0-eth1 to newname-eth1.
        switch = self.addSwitch("s0")

        # Add links with appropriate characteristics:
        # h1 <-> s0 : high-bandwidth host link (default/large queue)
        # h2 <-> s0 : bottleneck link with args.bw_net and args.maxq queue (packets)
        # Note: interface ordering creates s0-eth1 for the first link and s0-eth2 for the second.
        self.addLink(hosts[0], switch, bw=args.bw_host, delay="%sms" % (args.delay))
        self.addLink(
            hosts[1],
            switch,
            bw=args.bw_net,
            delay="%sms" % (args.delay),
            max_queue_size=args.maxq,
        )


# Simple wrappers around monitoring utilities.  You are welcome to
# contribute neatly written (using classes) monitoring scripts for
# Mininet!


# tcp_probe kernel module was removed since it used jprobe which was deprecated.
# In Linux >= 4.16, it has been replaced by the tcp:tcp_probe kernel tracepoint.
def start_tcpprobe(outfile: str = "cwnd.txt") -> subprocess.Popen:
    """Enable tcp_probe tracepoint and log to a file."""
    subprocess.run(
        "mount -t debugfs none /sys/kernel/debug 2>/dev/null || true", shell=True
    )
    subprocess.run(
        "echo 1 > /sys/kernel/debug/tracing/events/tcp/tcp_probe/enable", shell=True
    )

    trace_file = os.path.join(args.dir, outfile)
    return subprocess.Popen(
        f"cat /sys/kernel/debug/tracing/trace_pipe > {trace_file}", shell=True
    )


def stop_tcpprobe() -> None:
    """Disable tcp_probe and stop reader."""
    subprocess.run(
        "echo 0 > /sys/kernel/debug/tracing/events/tcp/tcp_probe/enable", shell=True
    )
    subprocess.run(
        "pgrep -f 'cat /sys/kernel/debug/tracing/trace_pipe' | xargs kill -9 2>/dev/null || true",
        shell=True,
    )


def start_qmon(iface: str, interval_sec=0.1, outfile="q.txt") -> Process:
    monitor = Process(target=monitor_qlen, args=(iface, interval_sec, outfile))
    monitor.start()
    return monitor


def start_iperf(net: Mininet) -> None:
    """Start iperf server and client."""
    h2 = net.get("h2")
    h1 = net.get("h1")
    print("Starting iperf server...")
    server = h2.popen("iperf -s -w 16m", shell=True)
    # Start a long-lived iperf client from h1 to h2 for the duration of the experiment.
    iperf_out = os.path.join(args.dir, "iperf.txt")
    client_cmd = f"iperf -c {h2.IP()} -t {args.time} -p 5001 > {iperf_out} 2>&1"
    print("Starting iperf client...")
    h1.popen(client_cmd, shell=True)


def start_webserver(net: Mininet) -> List[subprocess.Popen]:
    """Start HTTP webserver on h1."""
    h1 = net.get("h1")
    proc = h1.popen("python3 http/webserver.py", shell=True)
    sleep(1)
    return [proc]


def start_ping(net: Mininet) -> None:
    # Start a ping train from h1 to h2, 10 pings/sec (interval 0.1s).
    h1 = net.get("h1")
    h2 = net.get("h2")
    ping_file = os.path.join(args.dir, "ping.txt")
    # Ensure file exists/cleared on the controller filesystem (visible to host)
    open(ping_file, "w").close()
    # Start ping in the host; use popen so it runs asynchronously
    count = int(max(1, args.time * 10))
    h1.popen(f"ping -i 0.1 -c {count} {h2.IP()} > {ping_file} 2>&1", shell=True)


def cleanup_processes() -> None:
    """Ensure all spawned processes are terminated."""
    stop_tcpprobe()
    subprocess.run(
        "pgrep -f webserver.py | xargs kill -9 2>/dev/null || true", shell=True
    )
    subprocess.run("pgrep -f iperf | xargs kill -9 2>/dev/null || true", shell=True)


def bufferbloat() -> None:
    """Main: set up topology, start monitoring, run experiment."""
    os.makedirs(args.dir, exist_ok=True)
    subprocess.run(["sysctl", "-w", f"net.ipv4.tcp_congestion_control={args.cong}"])

    # Cleanup any leftovers from previous mininet runs
    cleanup()
    cleanup_processes()

    topo = BBTopo()
    net = Mininet(topo=topo, host=CPULimitedHost, link=TCLink)
    net.start()
    # This dumps the topology and how nodes are interconnected through
    # links.
    dumpNodeConnections(net.hosts)
    # This performs a basic all pairs ping test.
    net.pingAll()

    # Start all the monitoring processes
    start_tcpprobe("cwnd.txt")
    start_ping(net)

    # TODO: Start monitoring the queue sizes.  Since the switch I
    # created is "s0", I monitor one of the interfaces.  Which
    # interface?  The interface numbering starts with 1 and increases.
    # Depending on the order you add links to your network, this
    # number may be 1 or 2.  Ensure you use the correct number.
    #
    # Start queue monitoring on the switch interface connected to h2.
    # With the link order above, s0-eth2 is the interface toward h2.
    qmon = start_qmon(
        iface="s0-eth2", interval_sec=0.1, outfile=os.path.join(args.dir, "q.txt")
    )

    # Start iperf server/client
    start_iperf(net)

    # Start webserver on h1
    web_procs = start_webserver(net)

    # Start web fetches from h2 to h1:
    # Do 3 fetches then sleep 5s, repeat until timeout.
    h1 = net.get("h1")
    h2 = net.get("h2")
    www_file = os.path.join(args.dir, "www.txt")
    open(www_file, "w").close()
    # Use timeout so the process exits after args.time seconds.
    fetch_cmd = (
        f"timeout {args.time}s bash -c "
        + "'while true; do for i in 1 2 3; do "
        + f'curl -o /dev/null -s -w "%{{time_total}}\\n" http://{h1.IP()}:8000/index.html >> {www_file}; '
        + "done; sleep 5; done'"
    )
    h2.popen(fetch_cmd, shell=True)

    # Hint: The command below invokes a CLI which you can use to
    # debug.  It allows you to run arbitrary commands inside your
    # emulated hosts h1 and h2.
    #
    # CLI(net)

    # TODO: measure the time it takes to complete webpage transfer
    # from h1 to h2 (say) 3 times.  Hint: check what the following
    # command does: curl -o /dev/null -s -w %{time_total} google.com
    # Now use the curl command to fetch webpage from the webserver you
    # spawned on host h1 (not from google!)
    # Hint: have a separate function to do this and you may find the
    # loop below useful.
    start_time = time()
    while True:
        # do the measurement (say) 3 times.
        sleep(1)
        now = time()
        delta = now - start_time
        if delta > args.time:
            break
        print("%.1fs left..." % (args.time - delta))

    # Compute basic statistics for the webpage fetch times recorded in www.txt
    www_file = os.path.join(args.dir, "www.txt")
    fetch_times = []
    if os.path.exists(www_file):
        with open(www_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    fetch_times.append(float(line))
                except Exception:
                    continue
    if fetch_times:
        try:
            import statistics

            mean = statistics.mean(fetch_times)
            stdev = statistics.stdev(fetch_times) if len(fetch_times) > 1 else 0.0
            info(
                "Fetch times: n=%d mean=%.4fs stdev=%.4fs\n"
                % (len(fetch_times), mean, stdev)
            )
        except ImportError:
            n = len(fetch_times)
            mean = sum(fetch_times) / n
            variance = sum((x - mean) ** 2 for x in fetch_times) / (
                n - 1 if n > 1 else 1
            )
            stdev = math.sqrt(variance)
            info(
                "Fetch times: n=%d mean=%.4fs stdev=%.4fs\n"
                % (len(fetch_times), mean, stdev)
            )
    else:
        info("No fetch times recorded in %s\n" % (www_file))

    stop_tcpprobe()
    if qmon is not None:
        qmon.terminate()

    net.stop()

    # Ensure that all processes you create within Mininet are killed.
    # Sometimes they require manual killing.
    cleanup_processes()


if __name__ == "__main__":
    bufferbloat()
