# Week 3 · Observation

## Task 1 · Iterative resolver

- 루트 서버는 `.kr` 담당 서버 목록만 알고 `www.korea.ac.kr`의 주소는 모른다. 캡처 2번 패킷도 Answer 0개, Authority에 `.kr` NS 6개였다. 수억 개의 이름을 한 서버가 관리할 수 없으니, 각 단계는 다음 담당자에게 위임만 한다.
- glue 없는 위임(Netflix: `ftl.netflix.com` → `e.ns.nflxso.net`, 주소 없음)을 받으면, 원래 조회를 멈추고 그 NS 이름을 루트부터 따로 resolve한 뒤 이어갔다. 추가 조회는 2번(루트 → `.net`)이었고, 검증용 5개 이름에는 모두 glue가 있어 이런 일이 없었다.
- 이름 하나에 3번(korea.ac.kr)에서 10번(microsoft.com, CNAME 2번)까지 서버에 물었다. 노트북은 기본 DNS 서버에 1번만 묻고, 나머지 조회는 그 서버가 루트부터 대신 해 준다.

## Task 2 · On the wire, and steering

- 위임 응답(2번)과 정답 응답(6번)은 같은 DNS 응답 형식이고, 채워진 칸만 다르다. 위임은 Answer 0 · Authority에 NS 6개, 정답은 Answer에 A 1개였다.
- 규칙: CNAME 체인 출발과 도착의 등록 도메인(`co.uk` 같은 접미사 고려)이 다르면 제3자. 12개 중 `www.wikipedia.org`(→ `wikimedia.org`)만 틀렸다. 둘 다 Wikimedia 재단 소유인데, 규칙은 이름만 보고 소유자는 보지 못한다.
- CDN 사이트 10개 중 7개가 resolver나 네트워크(핫스팟 LG U+망 vs 카페 Wi-Fi KT망)에 따라 다른 주소를 받았다. 하지만 두 네트워크는 같은 자리에서 쟀고, 네트워크만 바꾸면 3/10, resolver만 바꾸면 7/10이었다. CDN은 사용자가 아니라 질문을 전달한 resolver를 보고 고르므로, claim (b)는 "사용자 근처"가 아니라 "resolver 근처"로만 뒷받침된다.

## Task 3 · Cache

- baseline은 TTL을 무시하고 모든 레코드를 60초 동안 보관한다. 그래서 TTL보다 짧은 레코드는 만료 뒤에도 답으로 주고(정확성, stale 266), 긴 레코드는 일찍 버려 다시 묻는다(성능, 루트 서버는 1번이면 될 것을 20번).
- floor는 275다. 한 번 받은 답은 TTL 동안만 쓸 수 있으니, 만료 뒤 들어온 질문은 어떤 올바른 캐시든 upstream에 물어야 한다. `YourCache`는 그 경우에만 물어 275에 도달했고(`out/bench.txt`), 미리 묻는 것도 호출 1번이라 줄지 않는다. 한계는 자료구조가 아니라 TTL이 정한다.
- 가장 못 다루는 레코드는 `www.microsoft.com`이다. TTL이 20초로 가장 짧은데 가장 자주(1000번 중 322번) 묻는 이름이라, stale 266개 중 189개가 여기서 나왔다. upstream은 52번으로 올바른 캐시(118번)보다 적은데, 빨라서가 아니라 물어야 할 때 안 물어서다.
