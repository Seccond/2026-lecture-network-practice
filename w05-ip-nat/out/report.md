# Week 5 · Task 2 report

Networks: `cafe wifi` (café Wi-Fi, KT DNS `168.126.63.1`) and `hotspot` (iPhone Personal Hotspot on LG U+). Raw `ifconfig` / `route` / `scutil --dns` output and the outside-seen address for both are in `out/addresses.json`.

## Part A · Address by hand

### A1 · Interface address and mask (en0, read from raw `ifconfig`)

| network | inet | netmask (hex) | netmask | prefix |
|---|---|---|---|---|
| cafe wifi | 172.30.1.77 | `0xffffff00` | 255.255.255.0 | /24 |
| hotspot | 172.20.10.6 | `0xfffffff0` | 255.255.255.240 | /28 |

### A2 · Subnet range, by hand, then checked with Task 1

**cafe wifi** — `172.30.1.77/24`

```
address   172.30.1.77   = 10101100.00011110.00000001 | 01001101
mask      /24           = 11111111.11111111.11111111 | 00000000
network   (AND)         = 172.30.1.0      host bits all 0
broadcast (host all 1)  = 172.30.1.255
usable                  = 172.30.1.1 - 172.30.1.254   (256 - 2 = 254 hosts)
```

**hotspot** — `172.20.10.6/28`

```
last octet   6          = 0000 | 0110
mask /28 last octet     = 1111 | 0000      (240)
network   (AND)         = 172.20.10.0
broadcast (host all 1)  = 172.20.10.15     (0000 | 1111)
usable                  = 172.20.10.1 - 172.20.10.14   (16 - 2 = 14 hosts)
```

`network_range` from Task 1 agrees with both:

```
network_range('172.30.1.0/24')  -> ('172.30.1.1', '172.30.1.254', '172.30.1.255')
network_range('172.20.10.0/28') -> ('172.20.10.1', '172.20.10.14', '172.20.10.15')
```

### A3 · Default gateway

| network | gateway | inside the range? |
|---|---|---|
| cafe wifi | 172.30.1.254 | yes — the last usable address |
| hotspot | 172.20.10.1 | yes — the first usable address |

It has to be inside. A host can only hand a frame directly to a neighbour on its own link; anything outside the subnet goes *through* the gateway, so the gateway itself must be reachable without a gateway. A gateway outside the range would be a door the host cannot walk up to.

### A4 · Address seen from outside (`api.ipify.org`)

| network | public address |
|---|---|
| cafe wifi | 121.168.41.174 |
| hotspot | 106.101.128.230 |

### A5 · Private vs public, and layers of NAT

Both interface addresses are private: `172.30.1.77` and `172.20.10.6` are both inside `172.16.0.0/12` (RFC 1918). Both outside-seen addresses are public. So on both networks there is **at least one NAT** between the laptop and the internet.

- **cafe wifi — at least one.** The café router translates `172.30.1.77` to `121.168.41.174`. Whether the router's own WAN side is that public address (one NAT) or another private address (two) cannot be told from the laptop alone; it needs the router's WAN address or a traceroute from the café, which was not taken.
- **hotspot — two, most likely.** The iPhone is the first NAT (`172.20.10.0/28` is the iPhone's own hotspot subnet, gateway `172.20.10.1` is the phone). A traceroute from the hotspot showed the carrier's network next, all on private addresses:

  ```
  1  172.20.10.1    5.9 ms   (iPhone)
  2  *
  3  10.2.212.211  46.9 ms   (LG U+ internal)
  4  10.2.240.2    23.4 ms
  5  10.2.240.41   29.9 ms
  6  10.2.197.14   31.0 ms
  ```

  The carrier is still routing on `10.x` several hops past the phone, and the outside sees `106.101.128.230`. That points to a second, carrier-grade NAT. The weakness: private router addresses in a traceroute show private *addressing* inside the carrier, not translation itself. The direct proof would be the iPhone's cellular address — a private or `100.64.0.0/10` address there means two NATs; a public one equal to `106.101.128.230` means one.

**One vs two, in general:** compare the address the outside sees with the address of the NAT box's outside interface. If they are equal there is one NAT; if the NAT box's outside is itself private or `100.64.x`, there is another NAT beyond it.

## Part B · Two networks

### B2 · Side by side

| | cafe wifi | hotspot |
|---|---|---|
| private address | 172.30.1.77 | 172.20.10.6 |
| mask | /24 (254 hosts) | /28 (14 hosts) |
| gateway | 172.30.1.254 | 172.20.10.1 |
| DNS | 168.126.63.1, .2 (KT) | 172.20.10.1 (the phone) |
| public address | 121.168.41.174 | 106.101.128.230 |
| en0 MAC | `5a:b5:14:be:54:bd` | `0a:e5:74:b2:94:ea` |

### B3 · What changed and why

- **The public address changed** — it belongs to whoever runs the outermost NAT: the café's ISP line in one case, LG U+'s mobile network in the other. Moving networks moves you behind a different NAT.
- **The private address changed too** — each network runs its own DHCP server with its own private plan. The café hands out a /24 for a room of customers; the iPhone hands out a /28 because a hotspot expects a handful of devices.
- **Even the MAC changed** — macOS uses a private Wi-Fi address per network, so the two networks never see the same hardware identity. The hardware Wi-Fi address does not appear in `out/addresses.json`; every MAC in it is locally administered.

## Part C · DHCP in the act

Capture: `out/dhcp.pcapng`, taken on `cafe wifi` with capture filter `port 67 or port 68`, trimmed to the four DORA messages. The original also had a DHCP **Release** before the Discover (the old address being handed back, which is why the client started again from Discover) and one more Request/ACK 36 s later (the OS re-confirming the address); both were removed.

| # | message | src → dst (IP) | dst (Ethernet) |
|---|---|---|---|
| 1 | Discover | `0.0.0.0` → `255.255.255.255` | `ff:ff:ff:ff:ff:ff` |
| 2 | Offer | `172.30.1.254` → `172.30.1.77` | client MAC |
| 3 | Request | `0.0.0.0` → `255.255.255.255` | `ff:ff:ff:ff:ff:ff` |
| 4 | ACK | `172.30.1.254` → `172.30.1.77` | client MAC |

### C2 · Discover's addresses

Source `0.0.0.0`, destination `255.255.255.255`. The source is the strange one: the client is asking for an address, so it has none to put there, and `0.0.0.0` means "this host, no address yet". That forces the destination: with no address it cannot be answered by unicast in the usual way, and it does not know the server's address either, so the only thing it can do is shout to everyone on the link.

### C3 · Lease time

The server (`172.30.1.254`) offered **3600 s (1 hour)**, with renewal (T1) at **1800 s** and rebinding (T2) at **3150 s** — exactly 50% and 87.5% of the lease. At T1 the client asks the same server to extend; only if that fails does it broadcast again at T2.

### C4 · Why Discover is broadcast but ACK is not

Between Discover and ACK the server learned two things: which address it is giving (`yiaddr` = `172.30.1.77`) and the client's MAC (`chaddr`, carried in the Discover). With both, it can address the frame straight to the client's MAC and the IP it is about to own. The client did not set the broadcast flag, so the server sent Offer and ACK as unicast. Request stays broadcast on purpose — it also tells any other server that offered an address that it was not chosen.
