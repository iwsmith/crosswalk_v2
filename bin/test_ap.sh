#!/bin/bash
#
# Test that the crosswalk fallback Wi-Fi AP comes up correctly.
#
# wlan0 has a single radio, so bringing up the AP drops the corginia_slow
# client connection. If you are SSH'd in over Wi-Fi that will disconnect you,
# so by default this runs the whole test DETACHED (as a transient systemd unit)
# with an automatic revert back to the client — you can safely get kicked off
# and reconnect a few minutes later. The AP-mode checks are captured to a log
# file while the AP is up so you can read them afterwards.
#
# Usage:
#   sudo bin/test_ap.sh [start] [hold_seconds]   # detached test, default hold 180s
#   sudo bin/test_ap.sh check                     # run the checks inline (use over Ethernet)
#   sudo bin/test_ap.sh results                   # print the captured check log
#   sudo bin/test_ap.sh down                      # revert to the client now
#
# Env overrides: AP_CONN (default "crosswalk"), CLIENT_CONN (default "corginia_slow").

set -u

AP_CONN="${AP_CONN:-crosswalk}"
CLIENT_CONN="${CLIENT_CONN:-corginia_slow}"
WLAN="${WLAN:-wlan0}"
LOG="${AP_TEST_LOG:-/tmp/ap_test.log}"
UNIT="ap-test"

require_root() {
    if [[ "$(id -u)" -ne 0 ]]; then
        echo "This action needs root. Re-run with: sudo $0 $*" >&2
        exit 1
    fi
}

run_checks() {
    echo "===== crosswalk AP test — $(date) ====="
    echo
    echo "--- active connections (want: ${AP_CONN}:${WLAN}:activated) ---"
    nmcli -t -f NAME,DEVICE,STATE connection show --active
    echo
    echo "--- ${WLAN} mode (want: type AP) ---"
    iw dev "$WLAN" info | grep -E 'type|ssid|channel' || echo "iw: no info"
    echo
    echo "--- ${WLAN} IPv4 (shared mode → 10.42.0.1/24) ---"
    nmcli device show "$WLAN" | grep IP4.ADDRESS || echo "no IPv4 address"
    echo
    echo "--- dnsmasq (NM spawns one for DHCP in shared mode) ---"
    pgrep -a dnsmasq || echo "no dnsmasq running (clients won't get an IP)"
    echo
    echo "--- recent NetworkManager journal (AP / dnsmasq / shared) ---"
    journalctl -u NetworkManager -b --no-pager \
        | grep -iE "${AP_CONN}|AP-ENABLED|dnsmasq|shared|deauth" | tail -20
    echo
    echo "===== end of checks ====="
}

action="${1:-start}"

case "$action" in
    start)
        require_root "$@"
        hold="${2:-180}"
        # Clean up any leftover unit from a previous run.
        systemctl reset-failed "$UNIT.service" 2>/dev/null || true
        echo "Starting detached AP test: bring up '$AP_CONN', hold ${hold}s, revert to '$CLIENT_CONN'."
        echo "Check results will be written to: $LOG"
        systemd-run --unit="$UNIT" --collect \
            --setenv=AP_CONN="$AP_CONN" \
            --setenv=CLIENT_CONN="$CLIENT_CONN" \
            --setenv=WLAN="$WLAN" \
            --setenv=AP_TEST_LOG="$LOG" \
            /bin/bash "$(readlink -f "$0")" __worker "$hold" >/dev/null
        echo
        echo "AP is coming up now. If you are on Wi-Fi you will disconnect."
        echo "Reconnect in ~$((hold + 15))s, then run:  sudo $0 results"
        echo "To connect a phone during the window: SSID '$AP_CONN', then expect an IP in 10.42.0.x"
        ;;

    __worker)
        # Runs inside the detached systemd unit (as root), independent of SSH.
        hold="${2:-180}"
        {
            echo "[worker] bringing up AP '$AP_CONN'"
            nmcli connection up id "$AP_CONN"
            sleep 5
            run_checks
        } >"$LOG" 2>&1
        sleep "$hold"
        nmcli connection up id "$CLIENT_CONN" >>"$LOG" 2>&1
        echo "[worker] reverted to client '$CLIENT_CONN'" >>"$LOG" 2>&1
        ;;

    check)
        require_root "$@"
        run_checks
        ;;

    results)
        if [[ -f "$LOG" ]]; then
            cat "$LOG"
        else
            echo "No results yet at $LOG. Run: sudo $0 start"
        fi
        ;;

    down)
        require_root "$@"
        echo "Reverting to client '$CLIENT_CONN'..."
        nmcli connection up id "$CLIENT_CONN"
        ;;

    -h|--help|help)
        grep '^#' "$0" | sed 's/^# \{0,1\}//'
        ;;

    *)
        echo "Unknown action: $action" >&2
        echo "Try: sudo $0 --help" >&2
        exit 1
        ;;
esac
