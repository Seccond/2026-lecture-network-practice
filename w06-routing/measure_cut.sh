#!/usr/bin/env bash
# Week 6 - measure OSPF reconvergence on all three routers.
#
#   bash w06-routing/measure_cut.sh cut       cut r1 eth1, time each router's repair
#   bash w06-routing/measure_cut.sh restore   bring r1 eth1 back, time the return
#   bash w06-routing/measure_cut.sh cost      raise r1 eth0 cost 10 -> 100, time it
#   bash w06-routing/measure_cut.sh silent    optional: freeze r2 silently, time it
#
# Companion to scenario.sh (use it for up / routes / down). Two things
# differ from `scenario.sh cut`:
#   * the route table's uptime column (e.g. 00:01:19) changes every second, so
#     comparing raw text always reports a change after ~1 s. Here the uptime is
#     stripped and only prefixes, costs and next hops are compared.
#   * all three routers are saved and timed, not just r1, polling every 0.5 s.
#
# Docker does not keep interface order: r1's eth1 is net_b (to r2) on some
# runs and net_a (to r3) on others. Read which link moved from the subnets
# in route-before.txt, not from frr.conf's interface descriptions.
set -u
cd "$(dirname "$0")/.." || exit 1
OUT="${OUT:-w06-routing/out}"; mkdir -p "$OUT"
DC="docker compose --profile routing"
STATE="${TMPDIR:-/tmp}/w06-before"          # stripped tables before the cut
WINDOW=90                                    # seconds to watch at most
QUIET=10                                     # settled after this long unchanged

raw()   { $DC exec -T "$1" vtysh -c "show ip route ospf" 2>/dev/null; }
# routes only, uptime removed: "O>* 172.19.0.0/16 [110/20] via 172.18.0.2, eth0, weight 1"
paths() { raw "$1" | grep -E '^O|^ +\*' | sed -E 's/, [0-9]{2}:[0-9]{2}:[0-9]{2}$//'; }
now()   { python3 -c 'import time; print(f"{time.time():.3f}")'; }
since() { python3 -c "print(f'{$(now) - $1:.1f}')"; }

dump_all() {                                  # all three tables, as vtysh prints them
  for r in r1 r2 r3; do echo "===== $r ====="; raw $r; echo; done
}

# watch r1..r3 after an event; print "rN <seconds>" for each router's last change
watch_routers() {
  local start=$1 b1=$2 b2=$3 b3=$4
  local l1="$b1" l2="$b2" l3="$b3" t1="-" t2="-" t3="-" quiet_since
  quiet_since=$(now)
  for _ in $(seq 1 $((WINDOW * 2))); do
    sleep 0.5
    local c1 c2 c3; c1=$(paths r1); c2=$(paths r2); c3=$(paths r3)
    [ "$c1" != "$l1" ] && { l1="$c1"; t1=$(since "$start"); quiet_since=$(now); }
    [ "$c2" != "$l2" ] && { l2="$c2"; t2=$(since "$start"); quiet_since=$(now); }
    [ "$c3" != "$l3" ] && { l3="$c3"; t3=$(since "$start"); quiet_since=$(now); }
    if [ "$t1" != "-" ] && python3 -c "import sys; sys.exit($(now) - $quiet_since < $QUIET)"; then
      break                                   # r1 moved and nothing changed for QUIET s
    fi
  done
  echo "r1 $t1 s   r2 $t2 s   r3 $t3 s"
}

# OSPF is converged when every router has learned the one network it is not
# attached to (a route "via" a neighbour). `scenario.sh up` waits 30 s, but
# the DR election alone waits 40 s, so check instead of assuming.
wait_converged() {
  for _ in $(seq 1 $((WINDOW * 2))); do
    local ok=1
    for r in r1 r2 r3; do paths $r | grep -q " via " || ok=0; done
    [ $ok = 1 ] && return 0
    sleep 0.5
  done
  echo "OSPF did not converge within ${WINDOW} s - check 'bash scenario.sh up'"; exit 1
}

case "${1:-}" in
  cut)
    echo "waiting for OSPF to converge..."
    wait_converged
    sleep 5                                   # let the last LSAs settle
    dump_all | tee "$OUT/route-before.txt"
    for r in r1 r2 r3; do paths $r > "$STATE.$r"; done
    echo "cutting r1 eth1 (r2 or r3 side, depending on Docker's interface order)"
    START=$(now)
    $DC exec -T r1 ip link set eth1 down
    RESULT=$(watch_routers "$START" "$(cat "$STATE.r1")" "$(cat "$STATE.r2")" "$(cat "$STATE.r3")")
    echo "cut      $RESULT   (time of each router's last route change after the cut)" \
      | tee "$OUT/reconverge.txt"
    dump_all | tee "$OUT/route-after.txt"
    ;;

  restore)
    [ -f "$STATE.r1" ] || { echo "run 'cut' first"; exit 1; }
    B1=$(paths r1); B2=$(paths r2); B3=$(paths r3)
    START=$(now)
    $DC exec -T r1 ip link set eth1 up
    RESULT=$(watch_routers "$START" "$B1" "$B2" "$B3")
    same="no"
    [ "$(paths r1)" = "$(cat "$STATE.r1")" ] && [ "$(paths r2)" = "$(cat "$STATE.r2")" ] \
      && [ "$(paths r3)" = "$(cat "$STATE.r3")" ] && same="yes"
    echo "restore  $RESULT   (back to the pre-cut tables: $same)" | tee -a "$OUT/reconverge.txt"
    ;;

  cost)
    # Part C: same change as `scenario.sh cost` (r1 eth0 cost 10 -> 100),
    # but timed and with every router's table kept, before and after.
    wait_converged
    { echo "##### before #####"; dump_all; } > "$OUT/cost-change.txt"
    B1=$(paths r1); B2=$(paths r2); B3=$(paths r3)
    echo "raising r1 eth0 cost 10 -> 100 (r2 or r3 side, as above)"
    START=$(now)
    $DC exec -T r1 vtysh -c "configure terminal" -c "interface eth0" -c "ip ospf cost 100" 2>/dev/null
    RESULT=$(watch_routers "$START" "$B1" "$B2" "$B3")
    echo "cost     $RESULT   (r1 eth0 cost 10 -> 100, no link went down)" \
      | tee -a "$OUT/reconverge.txt"
    { echo "##### after #####"; dump_all; } >> "$OUT/cost-change.txt"
    ;;

  silent)
    # Optional: r2 freezes without a word (docker pause). No interface goes
    # down and no LSA announces it, so r1 and r3 can only notice when r2's
    # hellos stop for a whole dead interval.
    wait_converged
    B1=$(paths r1); B3=$(paths r3)
    R2=$($DC ps -q r2)
    echo "freezing r2 (docker pause) - expect up to the 40 s dead interval"
    START=$(now)
    docker pause "$R2" >/dev/null
    # a paused r2 cannot be read at all; baseline "" makes its empty reads count as no change
    RESULT=$(watch_routers "$START" "$B1" "" "$B3")
    docker unpause "$R2" >/dev/null
    echo "silent   $RESULT   (r2 frozen, so it is not measured)" \
      | tee -a "$OUT/reconverge.txt"
    ;;

  *)
    sed -n '2,7p' "$0"
    ;;
esac
