# Week 4 · Observation

## Task 1 · Reliable delivery

- Selective Repeat(window 16, 패킷마다 타이머)를 골랐다. 결정적인 경우는 window 안의 패킷 하나만 사라진 경우다. Go-Back-N은 그 뒤에 도착한 패킷까지 버리고 window 전체를 다시 보내서 같은 seed에서 데이터 패킷 1050개를 썼다. stop-and-wait는 318개로 적었지만 931 step이 걸렸고, Selective Repeat는 311개 · 175 step이었다.
- 2,000바이트는 최소 250개면 되는데 채널은 데이터 패킷 311개를 실어 날랐다(seed 246, 1.24배). 늘어난 61개는 전부 재전송이고, 반대 방향 ACK도 286개 중 30개를 잃었다. ACK를 잃어도 데이터를 다시 보내야 하니, 비용(24%)은 손실률(10%)보다 크다.
- 가장 먼저 깨진 것은 중복이다. 수신 측 중복 제거를 빼자 중복만 켠 채널에서도 출력이 2048바이트로 오염됐고, 순서 섞기만 켠 채널에서는 그대로 통과했다. 이미 받은 패킷에 ACK를 다시 보내지 않자 152바이트에서 멈췄다. 중복 데이터는 대개 내 ACK가 사라졌다는 신호라서, 버리되 답은 해야 한다.

## Task 2 · Handshake, and two links

- 첫 연결의 SYN · SYN-ACK · ACK는 1 · 2 · 3번 패킷이고, ISN은 내 Mac `45761130`, Cloudflare `2181899760`이었다(Wireshark가 보여 주는 0은 상대값이다). 5개 연결 모두 ISN이 매번 달랐다. 0부터 세면 같은 포트를 다시 쓴 새 연결이 이전 연결에 남은 패킷을 자기 것으로 받을 수 있고, 남이 번호를 짐작해 가짜 세그먼트를 끼워 넣기도 쉽다.
- SYN 옵션은 MSS 1460 / 1250(Cloudflare), window scale ×64 / ×8192, SACK permitted는 양쪽 모두였다. 내 Mac이 광고한 window는 handshake 직후 2051×64 = 131,264바이트, 전송 중에는 최대 약 3.4~4.2MB까지 커졌다. 그런데 실제 in-flight는 최대 약 26~37만 바이트로 그 10%도 채우지 못했다. 막은 것은 수신 window가 아니라 송신 측 congestion window였다.
- 학교 Wi-Fi는 median 166.2 Mbps(121.7~191.0, spread 42%) · handshake 9.3 ms, 핫스팟(LG U+망)은 67.0 Mbps(8.8~76.2, spread 101%) · 43.7 ms였다. Wi-Fi는 공기를 다른 기기와 나눠 쓰고, 핫스팟 1회차(handshake 154.5 ms, 8.84 Mbps)는 휴대폰 무선 연결이 깨어나는 시간까지 포함한 것으로 보인다. handshake 시간이 곧 RTT이고 slow start는 RTT마다 window를 두 배로 키우므로, RTT가 4.7배 긴 핫스팟은 5MB처럼 짧은 전송에서 window를 키우는 데만 시간을 더 쓴다.

## Task 3 · Congestion control

- baseline은 goodput이 가장 높지만(986.8), pipe 20 + queue 10을 넘는 34개를 매번 버린다. 손실 37.4%, 재전송 2340번, 평균 queue 8.8은 같은 링크를 쓰는 모든 흐름이 항상 8.8칸 뒤에서 기다린다는 뜻이다. 혼자일 때만 빠른 sender이고, 모두가 이렇게 보내면 링크는 재전송으로 가득 찬다(1986년 혼잡 붕괴).
- window는 첫 손실 때 82 → 41로 줄고(손실이 3 RTT 늦게 보여 slow start가 크게 넘쳤다), 이후 약 22~32를 오간다(평균 24.9). 손실은 30(pipe 20 + queue 10)을 넘을 때 나고, ×0.7로 줄이면 약 21로 pipe 20 바로 위라 링크가 쉬지 않는다. 평균 queue는 평균 window − 20 ≈ 4.9로, 측정값 4.5와 맞는다(`out/bench.txt`: goodput 96%, 손실 2.0%, strong).
- backoff를 0.5 → 0.7 → 0.75 → 0.9로 완만하게 하자 goodput은 86% → 96% → 98.5% → 98.7%로 올랐지만, 평균 queue도 3.1 → 4.5 → 5.1 → 8.0으로 늘어 0.75부터 기준(5.0)을 넘었다. 덜 줄인 만큼의 이득은 남이 기다리는 시간으로 갚는다. 한 번의 넘침에 timeout이 몰려올 때마다 줄이면 90.7%로 떨어져서, 줄인 뒤 1 RTT 안의 손실은 한 번으로 셌다.
