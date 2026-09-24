#!/usr/bin/env python3
"""Week 3 · Task 2 — Does DNS actually steer you? Measure it.

Textbook §2.4.3 (records) and §2.5 (CDNs).

The lecture claims two things:

    (a) most large sites are served by a CDN, reached through a CNAME chain
    (b) DNS steers each user to a *nearby* replica

Both are testable from your laptop, and one of them is harder to prove than
the slide makes it look. Your job is to produce the evidence and a number.

    python3 task2_steering.py --collect        # gather the raw data
    python3 task2_steering.py --report         # your analysis

What you have to build
----------------------
1.  For each hostname in SITES, follow the CNAME chain to its end and record
    every hop. `--collect` should leave the raw data in out/chains.json.

2.  Decide, for each site, whether it is served by a **third party**.
    This is the hard part and there is no single right answer:

      - `www.microsoft.com` ends at `akamaiedge.net`     - clearly third party
      - `www.netflix.com`   stops inside `netflix.com`   - own CDN, not third party
      - some sites have no CNAME at all and still sit behind a CDN (anycast)
      - `foo.cloudfront.net` and `foo.s3.amazonaws.com` are both Amazon,
        but they are not the same service

    Write down the rule you used and **defend it in observation.md**. A rule
    that just compares the last two labels will be wrong on at least one of
    the sites below; find which, and say so.

3.  Ask **two different resolvers** for the same name and compare the
    addresses you get back. If DNS really steers by location, a CDN-hosted
    name should answer differently to resolvers sitting in different places.

        RESOLVERS below has your system resolver and two public ones.

    Report: of N CDN-hosted sites, how many returned a different address set
    from a different resolver? Claim (b) predicts most of them. Check it.

Pass condition
--------------
There is no fixed answer. You pass by producing, in out/report.md:

  - the table: site | chain length | final zone | third party? | your rule's verdict
  - the steering number: "X of N sites answered differently to a different resolver"
  - at least one site where your classification rule was wrong, and why
"""
import argparse, json, os, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

SITES = [
    "www.microsoft.com",     # Akamai, multi-hop
    "www.netflix.com",       # own CDN
    "www.adobe.com",
    "www.cnn.com",
    "www.apple.com",
    "www.korea.ac.kr",       # no CDN at all
    "www.stanford.edu",
    "www.bbc.co.uk",
    "www.spotify.com",
    "www.github.com",
    "www.wikipedia.org",
    "www.nytimes.com",
]

RESOLVERS = {
    "system": None,          # whatever is in your resolv.conf
    "google": "8.8.8.8",
    "quad9":  "9.9.9.9",
}


def dig(name, rtype="A", server=None):
    """Raw lookup. Transport only - the thinking is yours."""
    args = ["dig", "+short", name, rtype]
    if server:
        args.insert(1, f"@{server}")
    out = subprocess.run(args, capture_output=True, text=True).stdout
    return [l.strip() for l in out.splitlines() if l.strip()]


MAX_CHAIN = 10          # a CNAME loop must not hang the collector
CHAINS = os.path.join(OUT, "chains.json")


def _is_ipv4(s):
    parts = s.split(".")
    return len(parts) == 4 and all(p.isdigit() for p in parts)


def follow_chain(name):
    # B1: ask for the CNAME one hop at a time so every hop is recorded,
    # instead of trusting the resolver's flattened +short output
    chain = [name]
    for _ in range(MAX_CHAIN):
        target = dig(chain[-1], "CNAME")
        if not target:
            break                          # no CNAME - this is the end name
        chain.append(target[0].rstrip(".").lower())
    return chain


def collect(network):
    """Gather raw chains and per-resolver answers into out/chains.json.

    Runs are keyed by `network`, so running once on each network (B3)
    keeps both results side by side in the same file.
    """
    data = {}
    if os.path.exists(CHAINS):
        with open(CHAINS, encoding="utf-8") as f:
            data = json.load(f)

    for site in SITES:
        entry = data.setdefault(site, {"chain": [], "answers": {}})
        entry["chain"] = follow_chain(site)
        # B2: same name, each resolver - keep only addresses, +short also
        # prints the CNAME lines
        entry["answers"][network] = {
            label: sorted(a for a in dig(site, "A", server) if _is_ipv4(a))
            for label, server in RESOLVERS.items()
        }
        hops = len(entry["chain"]) - 1
        print(f"  {site:<20} cnames={hops}  end={entry['chain'][-1]}")

    with open(CHAINS, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n  saved {len(data)} sites for network {network!r} -> {CHAINS}")


# suffixes where the registrable domain is three labels, not two
# (a tiny slice of the Public Suffix List - enough for SITES)
MULTI_LABEL_SUFFIXES = {"co.uk", "ac.uk", "ac.kr", "co.kr", "or.kr", "go.kr"}

# the truth, checked by hand - the rule never sees this.
# site -> (served by a CDN?, third party?, who actually serves it)
GROUND_TRUTH = {
    "www.microsoft.com": (True,  True,  "Akamai"),
    "www.netflix.com":   (True,  False, "Netflix's own CDN (Open Connect)"),
    "www.adobe.com":     (True,  True,  "Akamai"),
    "www.cnn.com":       (True,  True,  "Fastly"),
    "www.apple.com":     (True,  True,  "Akamai, via Apple's own aaplimg.com"),
    "www.korea.ac.kr":   (False, False, "Korea University's own server"),
    "www.stanford.edu":  (True,  True,  "Netlify"),
    "www.bbc.co.uk":     (True,  True,  "Fastly"),
    "www.spotify.com":   (True,  True,  "Fastly"),
    "www.github.com":    (False, False, "GitHub's own servers"),
    "www.wikipedia.org": (True,  False, "Wikimedia's own CDN - same foundation"),
    "www.nytimes.com":   (True,  True,  "Fastly"),
}

# Part A - filled in by hand after reading out/dns.pcapng in Wireshark
PART_A = {
    "query_packet": 1,           # A2: a query ...
    "response_packet": 2,        # ... and its matching response
    "transaction_id": "0x15e4",  # A2: same ID on both (also 3/4, 5/6)
    "delegation_packet": 2,      # A3: answer count 0, NS in authority
    "answer_packet": 6,          # A3: A record in answer section
    "largest_bytes": 394,        # A4
    "largest_why": "the root's referral for .kr carries 17 records - "
                   "6 NS in authority, 10 glue (A + AAAA for the .kr "
                   "servers) and OPT in additional - vs 2 in the answer (packet 6)",
}


def registrable_domain(name):
    # "a.b.bbc.co.uk" -> "bbc.co.uk", "x.akamaiedge.net" -> "akamaiedge.net"
    labels = name.rstrip(".").lower().split(".")
    if ".".join(labels[-2:]) in MULTI_LABEL_SUFFIXES:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def rule_third_party(chain):
    # B4 rule: third party if the chain ends in a different registrable
    # domain than it started in. Looks at names only, never at owners.
    return registrable_domain(chain[0]) != registrable_domain(chain[-1])


def _steered(answers):
    # did any resolver, on any network, hand back a different address set?
    sets = {tuple(addrs) for per_net in answers.values()
            for addrs in per_net.values() if addrs}
    return len(sets) > 1


def report():
    """Read out/chains.json and produce out/report.md."""
    with open(CHAINS, encoding="utf-8") as f:
        data = json.load(f)
    networks = sorted({n for e in data.values() for n in e["answers"]})

    lines = [
        "# Week 3 · Task 2 report", "",
        "## Rule (B4)", "",
        "A site is **third party** if its CNAME chain ends in a different "
        "registrable domain than it started in. The registrable domain is the "
        "last two labels, or three when the last two are a public suffix like "
        "`co.uk`. The rule reads names only.", "",
        "## Classification", "",
        "| site | chain length | final zone | third party? | rule verdict | ok |",
        "|---|---|---|---|---|---|",
    ]
    wrong = []
    for site in SITES:
        chain = data[site]["chain"]
        _cdn, truth, who = GROUND_TRUTH[site]
        verdict = rule_third_party(chain)
        ok = verdict == truth
        if not ok:
            wrong.append((site, chain, who))
        lines.append(
            f"| {site} | {len(chain) - 1} | {registrable_domain(chain[-1])} | "
            f"{'yes' if truth else 'no'} ({who}) | "
            f"{'third party' if verdict else 'own'} | {'✓' if ok else '✗'} |")

    lines += ["", "## Where the rule was wrong", ""]
    for site, chain, who in wrong:
        lines.append(
            f"- **{site}** → `{chain[-1]}`: the rule sees "
            f"`{registrable_domain(chain[0])}` ≠ `{registrable_domain(chain[-1])}` "
            f"and says third party, but it is {who}. Two different names can "
            f"have one owner, and nothing in a DNS name says who that is.")
    if not wrong:
        lines.append("- none on this list")

    cdn_sites = [s for s in SITES if GROUND_TRUTH[s][0]]
    net_names = ", ".join(f"`{n}`" for n in networks)
    res_names = ", ".join(f"{k} ({v or 'your OS resolver'})" for k, v in RESOLVERS.items())
    lines += [
        "", "## Steering (B5)", "",
        f"Networks: {net_names}. Resolvers: {res_names}.",
        "",
        "| site | " + " | ".join(f"{n} · {r}" for n in networks for r in RESOLVERS)
        + " | differs? |",
        "|---|" + "---|" * (len(networks) * len(RESOLVERS) + 1),
    ]
    steered = 0
    for site in cdn_sites:
        ans = data[site]["answers"]
        diff = _steered(ans)
        steered += diff
        cells = [", ".join(ans.get(n, {}).get(r, [])) or "-"
                 for n in networks for r in RESOLVERS]
        lines.append(f"| {site} | " + " | ".join(cells)
                     + f" | {'yes' if diff else 'no'} |")
    # split the number: same resolver on two networks vs two resolvers
    # on one network - they are different claims about what DNS keys on
    by_network = sum(
        len({tuple(data[s]["answers"][n]["system"]) for n in networks}) > 1
        for s in cdn_sites) if len(networks) > 1 else None
    by_resolver = {
        n: sum(len({tuple(a) for a in data[s]["answers"][n].values()}) > 1
               for s in cdn_sites)
        for n in networks}
    lines += [
        "",
        f"**{steered} of {len(cdn_sites)} CDN-hosted sites answered differently "
        f"to a different resolver or network** "
        f"(networks: {', '.join(networks)}).",
        "",
        "Split by what changed:",
        "",
    ]
    if by_network is not None:
        lines.append(
            f"- network only (system resolver, {' vs '.join(networks)}): "
            f"**{by_network} of {len(cdn_sites)}**")
    for n, k in by_resolver.items():
        lines.append(f"- resolver only (system vs google vs quad9, on `{n}`): "
                     f"**{k} of {len(cdn_sites)}**")
    if len(networks) < 2:
        lines.append("\n> Only one network so far - B3 needs a second run.")

    a = PART_A
    lines += [
        "", "## Capture (Part A)", "",
        f"- A2 query / response: packet {a['query_packet']} / "
        f"{a['response_packet']}, transaction ID {a['transaction_id']}",
        f"- A3 delegation: packet {a['delegation_packet']} · "
        f"answer: packet {a['answer_packet']}",
        f"- A4 largest response: {a['largest_bytes']} bytes - {a['largest_why']}",
        "- capture: `out/dns.pcapng`, trimmed to the resolver's 6 packets "
        "(background apps removed). Note: `test_tasks.py` counts "
        "`dns.flags.response` as 0/1, but tshark 4.6 prints False/True, so "
        "it reports 0 queries - the file holds 3 queries and 3 responses.",
    ]

    path = os.path.join(OUT, "report.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  {steered}/{len(cdn_sites)} steered, {len(wrong)} misclassified"
          f" -> {path}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--collect", action="store_true")
    p.add_argument("--report", action="store_true")
    p.add_argument("--network", default="network1",
                   help="label for this vantage point, e.g. hotspot, campus-wifi")
    a = p.parse_args()
    os.makedirs(OUT, exist_ok=True)
    if a.collect:
        collect(a.network)
    elif a.report:
        report()
    else:
        p.print_help()
