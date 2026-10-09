#!/usr/bin/env python3
"""Week 4 · Task 1 — Build reliable delivery on top of an unreliable channel.

Textbook §3.4 (reliable data transfer) and §3.5 (TCP's sequence numbers).

`UnreliableChannel` below loses packets, reorders them, duplicates them, and
delays them. It is the network as §3.4 models it. Your job is to move a file
across it and have the bytes arrive intact and in order.

That is the whole of TCP's reliability story with the congestion control taken
out, and it is worth building once by hand before you ever trust a socket again.

    python3 task1_rdt.py --verify
"""
import argparse, hashlib, random

PAYLOAD = 8            # bytes per packet - small, so you see the sequencing


class UnreliableChannel:
    """Loses 10%, duplicates 3%, reorders, and delays. Deterministic by seed.

    You may not make it nicer. You may not read its internals. It is the only
    way your sender can reach your receiver.
    """

    def __init__(self, seed=246, loss=0.10, dup=0.03, reorder=0.10):
        self.rng = random.Random(seed)
        self.loss, self.dup, self.reorder = loss, dup, reorder
        self.wire = []          # packets in flight, in no particular order
        self.stats = {"sent": 0, "lost": 0, "duplicated": 0, "delivered": 0}

    def send(self, packet):
        """Hand a packet to the network. It may never come out."""
        self.stats["sent"] += 1
        if self.rng.random() < self.loss:
            self.stats["lost"] += 1
            return
        copies = 2 if self.rng.random() < self.dup else 1
        self.stats["duplicated"] += copies - 1
        for _ in range(copies):
            if self.rng.random() < self.reorder and self.wire:
                self.wire.insert(self.rng.randrange(len(self.wire)), packet)
            else:
                self.wire.append(packet)

    def receive(self):
        """Take the next packet out, or None if the network has nothing."""
        if not self.wire:
            return None
        self.stats["delivered"] += 1
        return self.wire.pop(0)


WINDOW = 16           # packets the sender may have unacked at once
TIMEOUT = 10          # steps before an unacked packet is sent again


class Sender:
    # Selective Repeat (§3.4.3): up to WINDOW numbered packets in flight,
    # each with its own timer. An ACK names one sequence number, so a lost
    # packet costs one retransmission instead of the whole window (Go-Back-N).
    # Packets on the wire: ("DATA", seq, payload) out, ("ACK", seq) back.

    def __init__(self, data_channel, ack_channel, data):
        self.out, self.back = data_channel, ack_channel
        self.chunks = [data[i:i + PAYLOAD] for i in range(0, len(data), PAYLOAD)]
        self.acked = [False] * len(self.chunks)
        self.base = 0             # oldest unacked seq
        self.next_seq = 0         # next seq never sent before
        self.sent_at = {}         # seq -> step it was last (re)sent
        self.clock = 0

    def step(self):
        """Do one unit of work. Return False when you believe you are done."""
        self.clock += 1

        # ACKs: a duplicate or stale ACK is harmless - marking True twice
        # changes nothing, and anything outside the window is ignored.
        while (packet := self.back.receive()) is not None:
            kind, seq = packet[0], packet[1]
            if kind == "ACK" and self.base <= seq < self.next_seq:
                self.acked[seq] = True
                self.sent_at.pop(seq, None)
        while self.base < len(self.chunks) and self.acked[self.base]:
            self.base += 1

        if self.base == len(self.chunks):
            return False

        # retransmit only the packets whose own timer ran out
        for seq, t in list(self.sent_at.items()):
            if self.clock - t >= TIMEOUT:
                self._send(seq)

        # fill the window with packets never sent before
        while self.next_seq < min(self.base + WINDOW, len(self.chunks)):
            self._send(self.next_seq)
            self.next_seq += 1
        return True

    def _send(self, seq):
        self.out.send(("DATA", seq, self.chunks[seq]))
        self.sent_at[seq] = self.clock


class Receiver:
    # Buffers out-of-order packets and hands bytes up only in order. Every
    # DATA packet is ACKed, duplicates included - a duplicate usually means
    # our earlier ACK was lost, so staying silent would stall the sender.

    def __init__(self, data_channel, ack_channel):
        self.inp, self.back = data_channel, ack_channel
        self.buffer = {}          # seq -> payload, not yet delivered
        self.expected = 0         # next seq to deliver in order
        self.delivered = bytearray()

    def step(self):
        while (packet := self.inp.receive()) is not None:
            kind, seq = packet[0], packet[1]
            if kind != "DATA":
                continue
            self.back.send(("ACK", seq))
            # already delivered or already buffered -> drop the copy
            if seq >= self.expected and seq not in self.buffer:
                self.buffer[seq] = packet[2]
        while self.expected in self.buffer:
            self.delivered += self.buffer.pop(self.expected)
            self.expected += 1

    def data(self):
        """The bytes reassembled so far."""
        return bytes(self.delivered)


# ------------------------------------------------------------------- harness
def verify(seed=246, size=2000, max_steps=200_000):
    original = bytes(random.Random(seed).getrandbits(8) for _ in range(size))
    up, down = UnreliableChannel(seed), UnreliableChannel(seed + 1)

    # Data goes out over `up`, ACKs come back over `down`. Both are unreliable.
    sender = Sender(up, down, original)
    receiver = Receiver(up, down)

    for _ in range(max_steps):
        alive = sender.step()
        receiver.step()
        if not alive and len(receiver.data() or b"") >= size:
            break

    got = receiver.data() or b""
    ok = hashlib.sha256(got).hexdigest() == hashlib.sha256(original).hexdigest()
    print(f"  bytes    sent {size}   received {len(got)}")
    print(f"  channel  {up.stats}")
    print(f"  result   {'IDENTICAL' if ok else 'CORRUPTED OR INCOMPLETE'}")
    return 0 if ok else 1


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--verify", action="store_true")
    p.add_argument("--seed", type=int, default=246)
    a = p.parse_args()
    raise SystemExit(verify(a.seed) if a.verify else p.print_help())
