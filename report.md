# CSC458 Programming Assignment 2: Bufferbloat

## Questions

### 1. Webpage Fetch Times and Buffer Size

Once a stable state is reached, a larger buffer allows more packets to be queued
during congestion, which can lead to increased RTTs and longer webpage fetch
times due to bufferbloat. This is seen in the RTT plots where the 100 packet
buffer results in an RTT that oscillated between 100 and 250 ms, while the 20
packet buffer resulted in an RTT that oscillated between 20 and 50 ms. The
smaller buffer allows packets to be dropped earlier, which forces the TCP sender
to reduce its congestion window (CWND) sooner, leading to lower RTTs and faster
webpage fetch times. This is also reflected in the CWND plots, where the larger
buffer holds significanly more packets in memory, leading to larger CWND
oscillations and longer delays.

### 2. Bloat in Network Interface Card

```
enp0s1: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500
    inet 10.0.2.15  netmask 255.255.255.0  broadcast 10.0.2.255
    inet6 fec0::1cda:aeff:fe10:e805  prefixlen 64  scopeid 0x40<site>
    inet6 fe80::1cda:aeff:fe10:e805  prefixlen 64  scopeid 0x20<link>
    ether 1e:da:ae:10:e8:05  txqueuelen 1000  (Ethernet)
    RX packets 182026  bytes 171761736 (171.7 MB)
    RX errors 0  dropped 0  overruns 0  frame 0
    TX packets 65435  bytes 65743994 (65.7 MB)
    TX errors 0  dropped 0 overruns 0  carrier 0  collisions 0
```

txqueuelen: 1000

Draining rate: 100 Mbps = 100,000,000 bits per second

MTU: 1500 bytes

$$\text{Max Delay} = \frac{\text{Queue Size} \times \text{MTU} \times 8 \text{ bits/byte}}{\text{Draining Rate}}$$

$$\text{Max Delay} = \frac{1000 \times 1500 \times 8}{100,000,000} = 0.12 \text{ seconds} = 120 \text{ ms}$$

### 3. Analysis of CWND, RTT, and Queue Size Plots

$$RTT = RTT_{base} + \frac{Q \times MTU \times 8}{B}$$

Where:

- \(RTT\_{base}\) is the base round-trip time without any queueing delay.
- \(Q\) is the queue size (in packets).
- \(MTU\) is the maximum transmission unit (in bytes).
- \(B\) is the bottleneck bandwidth (in bits per second).

_CWND Oscillations and RTT Spikes_

- As the TCP sender increases its context window (CWND), the rate of packets
  will exceed the capacity at thebottleneck (B).
- This will lead to a build-up packets eventually exceeding the queue size (Q),
  causing packet drops.
- The packet drop will trigger the sender to reduce CWND, therefore reducing RTT
  as the queue drains.
- This cycle creates the sawtooth pattern observed in the plots which is most
  noticable in q100.

_Buffer Size and Webpage Fetch Times_

- Larger buffer sizes allow more packets to be queued during congestion, leading
  to increased RTTs.
- Smaller buffer sizes lead to earlier packet drops, forcing the TCP sender to
  reduce its CWND sooner.
- The longer RTT will hinder performance for applications like webpage fetching,
  as they rely on timely delivery of packets.

### 4. Potential Bufferbloat Solutions

_Method 1: Smaller Buffer Sizes_

- Tune the router to use smaller buffer sizes
- This will greatly reduce latency as we have seen, but this could affect link
  throughput and utilization during high traffic periods.
- We can experiment with sizes smaller than 20 packets to investigate what a
  very small buffer would do to both latency and throughput.

_Method 2: Random Early Detection (RED)_

- Implement RED on the router to proactively drop packets before the buffer is
  full, which can help to signal congestion to the TCP sender earlier.
- This will require more complex configuration for the router such as tuning the
  minimum and maximum thresholds for queue lengths.
- Mininet supports RED queuing, so we can compare the performance of RED against
  our set buffer sizes with default tail drop queuing.

## Theoretical Analysis

### 1. Sent Packets per Cycle

CWND cycles between $W_{min} = \frac{W_{max}}{2}$ and $W_{max}$.

The number of packets sent in one cycle is the area under the CWND curve:

We can conclude that the cycle duration is approximately $W_{max} - \frac{W_{max}}{2} = \frac{W_{max}}{2}$ RTTs.

The total number of packets will be the area under the CWND curve during the
cycle.

$$N_{packets} = \text{Average CWND} \times \text{Cycle Duration}$$

$$\text{Average CWND} = \frac{W_{max} + W_{min}}{2} = \frac{W_{max} + \frac{W_{max}}{2}}{2} = \frac{3}{4} W_{max}$$

$$N_{packets} = \frac{3}{4} W_{max} \times \frac{W_{max}}{2} = \frac{3}{8} W_{max}^2$$

### 2. CWND and Throughput Modeling

Let $K$ be the compute constant.

$$T \approx \frac{K \times MSS}{RTT \sqrt{p}}$$

Where:

- \($T$\) is the throughput.
- \($MSS$\) is the maximum segment size.
- \($RTT$\) is the round-trip time.
- \($p$\) is the packet loss probability.

$$p = \frac{1}{N_{packets}} = \frac{8}{3 W_{max}^2}$$

$$W_{max} = \sqrt{\frac{8}{3p}}$$

$$T = \frac{W_{avg} \times MSS}{RTT}$$

$$W_{avg} = \frac{3}{4} W_{max} = \frac{3}{4} \sqrt{\frac{8}{3p}} = \sqrt{\frac{9 \times 8}{16 \times 3p}} = \sqrt{\frac{3}{2p}}$$

$$T = \frac{MSS}{RTT} \sqrt{\frac{3}{2p}}$$

$$T = \frac{\sqrt{1.5} \times MSS}{RTT \sqrt{p}}$$

We can compare our derived formula to the original formula to find \($K$\):

$$K = \sqrt{1.5} \approx 1.2247$$

### 3. Queueing Delay and RTT

The maximum queueing delay will happen when the buffer is at full capacity and
the link is fully utilized.

$$\text{Max Queueing Delay} = \frac{B}{C}$$

The measured RTT will be the sum of the base RTT and the queueing delay.

$$RTT = RTT_{0} + \frac{Q \times MSS}{C}$$

$RTT_{0}$ will account for propagation delay and transmission delay without any queueing.

$\frac{Q \times MSS}{C}$ will account for the additional delay caused by packets waiting in the queue.

### 4. Effect of Buffer Size on Web Fetch Times

Downloading a webpage if often a short flow that requires a few round trips to
complete. The main bottleneck for these short flows is the TCP handshake and
slow start phase for the transmission. Both of these exchanges are bound
directly by RTT. The previous question shows that larger buffers increase RTT
due to queueing delay.

With a large buffer size, a few things can happen.

- The long-lived background flows can fill the buffer causing Q to reach the
  size of B.
- $RTT$ can increase significantly reaching $RTT_{max}$
- The web fetch will take longer due to the larger queue size.
- Due to the increased RTT, each round trip will take longer, no matter the
  request or interaction.

Due to these observations, we can determine that increasing the size of buffer B
will increase the $RTT$ which is directly responsible for the time needed to
complete short transfers of data.
