#!/usr/bin/env python3
"""Week 4 · Task 3 — Beat the fixed window.

Textbook §3.7.

`FixedWindow` is a sender that never adapts. It picks a window and keeps it,
forever, no matter what the network says back. It is not a strawman: it is what
you get if you skip congestion control entirely, and it was the internet's
actual failure mode in October 1986.

Write `YourControl` and beat it on the harness:

    python3 bench.py
    python3 bench.py --yours

The interface is two events and one number:

    .window        how many packets you are willing to have in flight
    .on_ack()      one packet made it there and back
    .on_loss()     a packet was dropped, or timed out waiting for its ACK

That is all the information a real TCP sender has. It cannot see the queue,
it cannot see the link rate, and neither can you. You infer them from these
two events, which is the entire idea of §3.7.
"""


class FixedWindow:
    """Send 64 packets at a time and never listen."""

    def __init__(self):
        self.window = 64

    def on_ack(self):
        pass

    def on_loss(self):
        pass


class YourControl:
    # Slow start until the first loss, then AIMD with a gentler cut (x0.7
    # instead of Reno's x0.5). The pipe holds ~20 packets and the queue 10,
    # so loss means window > ~30; cutting to 0.7 lands near 21, just above
    # the pipe, so the link never idles while the queue stays short.
    # Halving would drop to ~15, below the pipe, and waste slots regrowing.
    #
    # A loss is seen only at timeout (3 RTT late), and one overflow drops a
    # burst of packets. Reacting to each would cut the window many times for
    # one congestion event, so losses within one window's worth of ACKs of a
    # cut are treated as the same event.

    BACKOFF = 0.7

    def __init__(self):
        self.window = 1.0
        self.slow_start = True
        self.ignore = 0           # ACKs left before a new loss counts again

    def on_ack(self):
        if self.ignore > 0:
            self.ignore -= 1
        if self.slow_start:
            self.window += 1                  # doubles every RTT
        else:
            self.window += 1 / self.window    # +1 packet per RTT

    def on_loss(self):
        if self.ignore > 0:
            return
        if self.slow_start:
            # by the time the timeout fires, slow start has overshot badly
            self.window /= 2
            self.slow_start = False
        else:
            self.window *= self.BACKOFF
        self.window = max(2.0, self.window)
        self.ignore = int(self.window)
