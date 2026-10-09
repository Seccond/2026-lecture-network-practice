#!/usr/bin/env python3
"""Week 6 · Task 3 — Reconverge without recomputing the world.

Textbook §5.2.1, §5.3.

A link flaps. Every router in the area has to decide what changed. `FullRecompute`
does the honest thing: throw the table away and run Dijkstra again, from scratch,
for every event. It is correct and it is what the first implementations did.

It is also why a single flapping link in a large area used to melt the CPU of
every router that could see it.

Beat it:

    python3 bench.py
    python3 bench.py --yours

Correctness first. `bench.py` compares your table against a full recompute after
**every single event**. A router that is fast and wrong black-holes traffic.
"""
import heapq

# The harness counts how many times you run a full SPF. This is the score:
# wall-clock time in Python says more about dictionary overhead than about
# routing, but "how many times did the CPU have to recompute the world" is
# exactly what melted real routers.
SPF_RUNS = 0


def dijkstra_table(graph, source):
    """Reference shortest-path-first. Returns {destination: first_hop}.

    Use THIS function whenever you need a full recompute. Rolling your own to
    dodge the counter is not an optimisation, it is cheating the meter.
    """
    global SPF_RUNS
    SPF_RUNS += 1
    best = {source: (0, None)}
    pq, done = [(0, source, None)], set()
    while pq:
        cost, node, first_hop = heapq.heappop(pq)
        if node in done:
            continue
        done.add(node)
        best[node] = (cost, first_hop)
        for nbr, w in sorted(graph[node].items()):
            if nbr in done:
                continue
            hop = nbr if node == source else first_hop
            if cost + w < best.get(nbr, (float("inf"), None))[0]:
                best[nbr] = (cost + w, hop)
                heapq.heappush(pq, (cost + w, nbr, hop))
    return {d: h for d, (_, h) in best.items() if d != source and h}


class FullRecompute:
    """On every event, forget everything and run SPF again."""

    def __init__(self, graph, source):
        self.graph = {n: dict(e) for n, e in graph.items()}
        self.source = source
        self.table = dijkstra_table(self.graph, source)

    def link_change(self, a, b, cost):
        """cost=None means the link went down."""
        if cost is None:
            self.graph[a].pop(b, None)
            self.graph[b].pop(a, None)
        else:
            self.graph[a][b] = cost
            self.graph[b][a] = cost
        self.table = dijkstra_table(self.graph, self.source)


class YourRouter:
    # Keeps, between events, the shortest-path tree that dijkstra_table built:
    # each node's distance and the neighbour it was first reached from
    # (`parent`). With that, one link change can be judged without SPF:
    #
    #   * down, or more expensive: matters only if the link is a tree edge.
    #     Off-tree links carried no chosen path, so nothing moves.
    #   * up, or cheaper: matters only if it makes some endpoint at least as
    #     close as it is now - dist[a] + cost <= dist[b] (or the other way).
    #     Equal counts too, because a new tie can change which first hop
    #     dijkstra_table's ordering picks.
    #
    # Anything else leaves both the table and the tree exactly as they were.
    # When an event does matter, the full recompute goes through
    # dijkstra_table() so the meter sees it; _tree() then rebuilds the
    # bookkeeping alongside it.

    def __init__(self, graph, source):
        self.graph = {n: dict(e) for n, e in graph.items()}
        self.source = source
        self._recompute()

    def link_change(self, a, b, cost):
        old = self.graph[a].get(b)            # None if the link was down
        if cost is None:
            self.graph[a].pop(b, None)
            self.graph[b].pop(a, None)
        else:
            self.graph[a][b] = cost
            self.graph[b][a] = cost
        if self._matters(a, b, old, cost):
            self._recompute()

    def _matters(self, a, b, old, new):
        if old == new:
            return False                      # no change at all
        if self.parent.get(a) == b:
            a, b = b, a                       # make a the parent, b the child
        on_tree = self.parent.get(b) == a
        if new is None:
            return on_tree                    # down: only if we used it
        if on_tree:
            # A tree edge got dearer or cheaper. Everything under b moves by
            # the same delta and keeps its first hop - unless that shift
            # makes some link across the subtree boundary a tie or a
            # shortcut. Only then does the tree change shape.
            return self._shift_subtree(a, b, new - old)
        if old is not None and new > old:
            return False                      # off-tree link got dearer
        inf = float("inf")
        da, db = self.dist.get(a, inf), self.dist.get(b, inf)
        return da + new <= db or db + new <= da   # up/cheaper: shorter or tie

    def _shift_subtree(self, a, b, delta):
        children = {}
        for node, p in self.parent.items():
            children.setdefault(p, []).append(node)
        subtree, stack = set(), [b]
        while stack:
            node = stack.pop()
            subtree.add(node)
            stack.extend(children.get(node, ()))
        shifted = {n: self.dist[n] + delta for n in subtree}
        for x in subtree:
            for y, w in self.graph[x].items():
                if y in subtree or (x == b and y == a):
                    continue                  # inside, or the changed edge itself
                if shifted[x] + w <= self.dist[y] or self.dist[y] + w <= shifted[x]:
                    return True               # boundary tie or shortcut
        self.dist.update(shifted)             # same tree, same table, new costs
        return False

    def _recompute(self):
        self.table = dijkstra_table(self.graph, self.source)
        self.dist, self.parent = self._tree()

    def _tree(self):
        # Same loop and same tie order as dijkstra_table, recording the
        # neighbour each node was first reached from instead of its first hop.
        # Run only right after a counted dijkstra_table() call, never on its
        # own, so it adds bookkeeping, not uncounted recomputes.
        src = self.source
        best = {src: (0, None)}
        pq, done = [(0, src, "")], set()
        while pq:
            cost, node, _ = heapq.heappop(pq)
            if node in done:
                continue
            done.add(node)
            for nbr, w in sorted(self.graph[node].items()):
                if nbr in done:
                    continue
                if cost + w < best.get(nbr, (float("inf"), None))[0]:
                    best[nbr] = (cost + w, node)
                    hop = nbr if node == src else self.table[node]
                    heapq.heappush(pq, (cost + w, nbr, hop))
        dist = {n: c for n, (c, _) in best.items()}
        parent = {n: p for n, (_, p) in best.items() if p is not None}
        return dist, parent
