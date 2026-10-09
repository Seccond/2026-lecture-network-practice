#!/usr/bin/env python3
"""Week 5 · Task 3 — Make longest-prefix match fast.

Textbook §4.3.3.

`LinearTable` is correct and it is what you probably wrote in Task 1: keep the
prefixes in a list, check every one, remember the longest that matched. On six
entries that is fine. A real router holds close to a million, and it has to
answer while the packet is still in the buffer.

Beat it:

    python3 bench.py
    python3 bench.py --yours

Correctness first: `bench.py` checks every one of your answers against the
linear table. A fast router that forwards to the wrong next hop is not a
router, it is an outage.
"""


class LinearTable:
    """Correct, and slow in the obvious way."""

    def __init__(self):
        self.entries = []                     # (prefix_len, network, next_hop)

    def add(self, network, prefix_len, next_hop):
        self.entries.append((prefix_len, network, next_hop))

    def lookup(self, address):
        best = None
        for plen, net, hop in self.entries:
            mask = (0xFFFFFFFF << (32 - plen)) & 0xFFFFFFFF
            if address & mask == net and (best is None or plen > best[0]):
                best = (plen, hop)
        return best[1] if best else None


class YourTable:
    # Group by prefix length: one dict {network: next_hop} per length that
    # actually occurs. A lookup masks the address to each length, longest
    # first, and the first dict hit is the longest match by construction -
    # so it can stop there. Work is bounded by the number of distinct prefix
    # lengths (at most 33, 7 in the bench table), not by the number of routes.

    def __init__(self):
        self.by_len = {}          # prefix_len -> {network: next_hop}
        self.order = []           # (mask, dict), longest prefix first

    def add(self, network, prefix_len, next_hop):
        if prefix_len not in self.by_len:
            self.by_len[prefix_len] = {}
            # rebuilt only when a new length appears - at most 33 times
            self.order = [((0xFFFFFFFF << (32 - plen)) & 0xFFFFFFFF, self.by_len[plen])
                          for plen in sorted(self.by_len, reverse=True)]
        self.by_len[prefix_len][network] = next_hop

    def lookup(self, address):
        for mask, routes in self.order:
            hop = routes.get(address & mask)
            if hop is not None:
                return hop
        return None
