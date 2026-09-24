# Week 3 · Task 2 report

## Rule (B4)

A site is **third party** if its CNAME chain ends in a different registrable domain than it started in. The registrable domain is the last two labels, or three when the last two are a public suffix like `co.uk`. The rule reads names only.

## Classification

| site | chain length | final zone | third party? | rule verdict | ok |
|---|---|---|---|---|---|
| www.microsoft.com | 2 | akamaiedge.net | yes (Akamai) | third party | ✓ |
| www.netflix.com | 1 | netflix.com | no (Netflix's own CDN (Open Connect)) | own | ✓ |
| www.adobe.com | 2 | akamai.net | yes (Akamai) | third party | ✓ |
| www.cnn.com | 1 | fastly.net | yes (Fastly) | third party | ✓ |
| www.apple.com | 3 | akamaiedge.net | yes (Akamai, via Apple's own aaplimg.com) | third party | ✓ |
| www.korea.ac.kr | 0 | korea.ac.kr | no (Korea University's own server) | own | ✓ |
| www.stanford.edu | 1 | netlifyglobalcdn.com | yes (Netlify) | third party | ✓ |
| www.bbc.co.uk | 2 | fastly.net | yes (Fastly) | third party | ✓ |
| www.spotify.com | 1 | fastly.net | yes (Fastly) | third party | ✓ |
| www.github.com | 1 | github.com | no (GitHub's own servers) | own | ✓ |
| www.wikipedia.org | 1 | wikimedia.org | no (Wikimedia's own CDN - same foundation) | third party | ✗ |
| www.nytimes.com | 3 | fastly.net | yes (Fastly) | third party | ✓ |

## Where the rule was wrong

- **www.wikipedia.org** → `dyna.wikimedia.org`: the rule sees `wikipedia.org` ≠ `wikimedia.org` and says third party, but it is Wikimedia's own CDN - same foundation. Two different names can have one owner, and nothing in a DNS name says who that is.

## Steering (B5)

Networks: `cafe-wifi`, `hotspot`. Resolvers: system (your OS resolver), google (8.8.8.8), quad9 (9.9.9.9).

| site | cafe-wifi · system | cafe-wifi · google | cafe-wifi · quad9 | hotspot · system | hotspot · google | hotspot · quad9 | differs? |
|---|---|---|---|---|---|---|---|
| www.microsoft.com | 104.94.218.45 | 104.94.218.45 | 23.199.22.71 | 104.74.176.230 | 104.74.176.230 | 23.15.142.75 | yes |
| www.netflix.com | 207.45.72.1, 207.45.73.1 | 207.45.72.1, 207.45.73.1 | 207.45.72.1, 207.45.73.1 | 207.45.72.1, 207.45.73.1 | 207.45.72.1, 207.45.73.1 | 207.45.72.1, 207.45.73.1 | no |
| www.adobe.com | 23.32.56.10, 23.32.56.11, 23.32.56.43, 23.32.56.57 | 23.32.56.19, 23.32.56.43, 23.32.56.57 | 23.46.228.10, 23.46.228.12 | 23.67.53.168, 23.67.53.176 | 222.231.51.11, 222.231.51.99 | 23.209.46.74, 23.209.46.90 | yes |
| www.cnn.com | 146.75.51.5 | 151.101.131.5, 151.101.195.5, 151.101.3.5, 151.101.67.5 | 151.101.131.5, 151.101.195.5, 151.101.3.5, 151.101.67.5 | 146.75.51.5 | 151.101.131.5, 151.101.195.5, 151.101.3.5, 151.101.67.5 | 151.101.131.5, 151.101.195.5, 151.101.3.5, 151.101.67.5 | yes |
| www.apple.com | 23.60.185.29 | 23.60.185.29 | 23.217.180.246 | 23.41.89.203 | 23.41.89.203 | 23.56.25.51 | yes |
| www.stanford.edu | 15.197.167.90, 3.33.186.135 | 15.197.167.90, 3.33.186.135 | 15.197.167.90, 3.33.186.135 | 15.197.167.90, 3.33.186.135 | 15.197.167.90, 3.33.186.135 | 15.197.167.90, 3.33.186.135 | no |
| www.bbc.co.uk | 146.75.48.81 | 151.101.0.81, 151.101.128.81, 151.101.192.81, 151.101.64.81 | 151.101.0.81, 151.101.128.81, 151.101.192.81, 151.101.64.81 | 146.75.48.81 | 151.101.0.81, 151.101.128.81, 151.101.192.81, 151.101.64.81 | 151.101.0.81, 151.101.128.81, 151.101.192.81, 151.101.64.81 | yes |
| www.spotify.com | 146.75.51.42 | 151.101.131.42, 151.101.195.42, 151.101.3.42, 151.101.67.42 | 151.101.131.42, 151.101.195.42, 151.101.3.42, 151.101.67.42 | 146.75.51.42 | 151.101.131.42, 151.101.195.42, 151.101.3.42, 151.101.67.42 | 151.101.131.42, 151.101.195.42, 151.101.3.42, 151.101.67.42 | yes |
| www.wikipedia.org | 103.102.166.224 | 103.102.166.224 | 103.102.166.224 | 103.102.166.224 | 103.102.166.224 | 103.102.166.224 | no |
| www.nytimes.com | 146.75.49.164 | 151.101.1.164, 151.101.129.164, 151.101.193.164, 151.101.65.164 | 151.101.1.164, 151.101.129.164, 151.101.193.164, 151.101.65.164 | 146.75.49.164 | 151.101.1.164, 151.101.129.164, 151.101.193.164, 151.101.65.164 | 151.101.1.164, 151.101.129.164, 151.101.193.164, 151.101.65.164 | yes |

**7 of 10 CDN-hosted sites answered differently to a different resolver or network** (networks: cafe-wifi, hotspot).

Split by what changed:

- network only (system resolver, cafe-wifi vs hotspot): **3 of 10**
- resolver only (system vs google vs quad9, on `cafe-wifi`): **7 of 10**
- resolver only (system vs google vs quad9, on `hotspot`): **7 of 10**

## Capture (Part A)

- A2 query / response: packet 1 / 2, transaction ID 0x15e4
- A3 delegation: packet 2 · answer: packet 6
- A4 largest response: 394 bytes - the root's referral for .kr carries 17 records - 6 NS in authority, 10 glue (A + AAAA for the .kr servers) and OPT in additional - vs 2 in the answer (packet 6)
- capture: `out/dns.pcapng`, trimmed to the resolver's 6 packets (background apps removed). Note: `test_tasks.py` counts `dns.flags.response` as 0/1, but tshark 4.6 prints False/True, so it reports 0 queries - the file holds 3 queries and 3 responses.
