#!/usr/bin/env python3
"""Week 3 · Task 1 — Build your own iterative resolver.

Textbook §2.4.2 - §2.4.3.

`dig +trace` walks root -> TLD -> authoritative for you. In this task you do
that walk yourself: start at a root server, read the delegation it returns,
ask the next server, and keep going until somebody answers authoritatively.

You may shell out to `dig` for the transport, or use a DNS library
(`dnspython` is in the container). Either is fine - what matters is that
*you* follow the delegations rather than letting a tool do it.

    python3 task1_resolve.py www.korea.ac.kr
    python3 task1_resolve.py --verify        # check yourself against dig

Pass condition
--------------
`--verify` resolves five names with your resolver and with `dig`, and the
addresses must agree. A name behind a CDN may legitimately return a different
address each time; the harness compares the *set of authoritative nameservers*
you ended at for those, not the address.
"""
import argparse, subprocess, sys
from collections import namedtuple

# Root servers. Everything starts here; there is no earlier step.
ROOT_SERVERS = [
    "198.41.0.4",       # a.root-servers.net
    "199.9.14.201",     # b.root-servers.net
    "192.33.4.12",      # c.root-servers.net
]

# (name, kind).  "stable" names must match dig exactly.  "cdn" names are served
# from many replicas and may legitimately give you a different address than dig
# got a second earlier - for those we only require that you reached an answer.
VERIFY_NAMES = [
    ("www.korea.ac.kr", "stable"),
    ("dns.google", "stable"),
    ("en.wikipedia.org", "stable"),
    ("www.stanford.edu", "stable"),
    ("www.microsoft.com", "cdn"),
]


MAX_DEPTH = 20          # cap so a broken/looping zone can't hang the resolver

# one parsed RR line: "example.com. 300 IN A 1.2.3.4" -> name ttl cls rtype rdata
_Record = namedtuple("_Record", "name ttl rtype rdata")


def _normalize(name):
    # dig prints names with a trailing dot and mixed case - strip both
    # so name comparisons don't silently fail
    return name.rstrip(".").lower()


class Resolver:
    """resolve(name) -> (address, path). Walks root -> TLD -> authoritative
    by hand instead of letting a recursive resolver do it."""

    def _ask(self, server, name, qtype="A"):
        # query one server, no recursion. dig with +noall +answer +authority
        # +additional prints all three sections back to back with no
        # headers, so records are told apart by rtype in _classify, not by
        # section. empty list = no response or nothing useful either way
        # the caller just moves to the next server (R4)
        try:
            out = subprocess.run(
                ["dig", f"@{server}", name, qtype, "+norecurse",
                 "+noall", "+answer", "+authority", "+additional",
                 "+time=2", "+tries=1"],
                capture_output=True, text=True, timeout=5,
            ).stdout
        except subprocess.TimeoutExpired:
            return []

        records = []
        for line in out.splitlines():
            if line.startswith(";"):
                continue                      # dig comment, e.g. ";; connection timed out"
            parts = line.split()
            if len(parts) < 5:
                continue                      # blank line / not a record
            rname, ttl, _cls, rtype, rdata = parts[:5]
            records.append(_Record(_normalize(rname), ttl, rtype,
                                    rdata.rstrip(".")))
        return records

    def _classify(self, records, name, qtype):
        # answer   - what we asked for, if this server had it
        # cname    - different name, restart the walk with it (R5)
        # ns_names - delegation: next zone's nameservers, by name
        # glue     - {nameserver name: address} that came with the delegation
        name = _normalize(name)
        answer, cname = None, None
        ns_names, glue = [], {}
        for r in records:
            if r.name == name and r.rtype == qtype:
                answer = r.rdata
            elif r.name == name and r.rtype == "CNAME":
                cname = r.rdata
            elif r.rtype == "NS":
                ns_names.append(r.rdata)
            elif r.rtype == "A":
                glue[r.name] = r.rdata
        return answer, cname, ns_names, glue

    def resolve(self, name):
        path = []
        servers = list(ROOT_SERVERS)     # R2: everything starts at the root
        current = _normalize(name)

        for _step in range(MAX_DEPTH):
            records = []
            for server in servers:
                path.append(server)
                records = self._ask(server, current)
                if records:               # R4: got something - stop trying servers
                    break
            if not records:
                raise RuntimeError(
                    f"none of {servers} answered for {current!r}")

            answer, cname, ns_names, glue = self._classify(records, current, "A")

            if answer:
                return answer, path

            if cname:                     # R5: different name - start over at the root
                current = cname
                servers = list(ROOT_SERVERS)
                continue

            if not ns_names:
                raise RuntimeError(
                    f"{servers} gave neither an answer nor a delegation "
                    f"for {current!r}")

            # R3: use glue if any nameserver has it; only resolve a
            # nameserver's own name when none of them do
            next_servers = [glue[ns] for ns in ns_names if ns in glue]
            if not next_servers:
                ns_address, ns_path = self.resolve(ns_names[0])
                path.extend(ns_path)
                next_servers = [ns_address]
            servers = next_servers

        raise RuntimeError(f"gave up after {MAX_DEPTH} steps resolving {name!r}")


# ------------------------------------------------------------------- harness
def dig_answer(name):
    """What the system resolver says, for comparison."""
    out = subprocess.run(["dig", "+short", name, "A"],
                         capture_output=True, text=True).stdout
    return [l for l in out.split() if l and l[0].isdigit()]


def verify():
    r, failures = Resolver(), 0
    for name, kind in VERIFY_NAMES:
        try:
            addr, path = r.resolve(name)
        except NotImplementedError:
            print("Nothing implemented yet - write Resolver.resolve first.")
            return 1
        except Exception as e:
            print(f"  FAIL  {name:<22} your resolver raised {e!r}")
            failures += 1
            continue
        expected = dig_answer(name)
        if addr in expected:
            note = ""
        elif kind == "cdn":
            note = "  <- differs, but this name is CDN-hosted. Explain it."
        else:
            note = "  <- should have matched"
            failures += 1
        print(f"  {'FAIL' if note.endswith('matched') else 'ok  '}  {name:<22} "
              f"you={addr:<16} dig={','.join(expected) or '-'}   "
              f"hops={len(path)}{note}")
    print(f"\n  {len(VERIFY_NAMES) - failures}/{len(VERIFY_NAMES)} ok")
    return 1 if failures else 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("name", nargs="?", default="www.korea.ac.kr")
    p.add_argument("--verify", action="store_true")
    a = p.parse_args()

    if a.verify:
        sys.exit(verify())

    addr, path = Resolver().resolve(a.name)
    for i, server in enumerate(path, 1):
        print(f"  {i}. asked {server}")
    print(f"\n  {a.name} -> {addr}")


if __name__ == "__main__":
    main()
