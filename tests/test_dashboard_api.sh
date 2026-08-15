#!/usr/bin/env bash
# test_dashboard_api.sh — Full API test for weed robot dashboard
set -uo pipefail

BASE="http://localhost:5000"
PASS=0
FAIL=0

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

check() {
  local name="$1" expected="$2" actual="$3"
  if echo "$actual" | grep -qF "$expected"; then
    echo -e "  ${GREEN}PASS${NC}  $name"
    PASS=$((PASS+1))
  else
    echo -e "  ${RED}FAIL${NC}  $name"
    echo "        expected: $expected"
    echo "        got:      $actual"
    FAIL=$((FAIL+1))
  fi
}

post_json() {
  curl -s -X POST "$BASE$1" \
    -H "Content-Type: application/json" \
    --data-raw "$2"
}

echo "=== WEED ROBOT DASHBOARD API TEST SUITE ==="
echo ""

# ── 1. Existing endpoints ─────────────────────────────────────
echo "--- Existing endpoints ---"

r=$(curl -s "$BASE/health")
check "/health returns ok"            '"status":"ok"'            "$r"
check "/health has ts"                '"ts"'                     "$r"

r=$(curl -s "$BASE/stats")
check "/stats total_detections"       "total_detections"         "$r"
check "/stats uptime_formatted"       "uptime_formatted"         "$r"
check "/stats simulate field"         '"simulate"'               "$r"
check "/stats total_strikes"          "total_strikes"            "$r"
check "/stats weeds_in_zone"          "weeds_in_zone"            "$r"

code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 "$BASE/video_feed" || true)
check "/video_feed HTTP 200"          "200"                      "$code"

# ── 2. Control status initial state ──────────────────────────
echo ""
echo "--- Control status (initial) ---"

r=$(curl -s "$BASE/control/status")
check "has detection_paused"          "detection_paused"         "$r"
check "has capture_paused"            "capture_paused"           "$r"
check "has frame_delay"               "frame_delay"              "$r"
check "detection_paused starts false" '"detection_paused":false' "$r"
check "capture_paused starts false"   '"capture_paused":false'   "$r"
check "frame_delay starts 0"          '"frame_delay":0'         "$r"

# ── 3. Detection pause / resume ───────────────────────────────
echo ""
echo "--- Detection pause / resume ---"

r=$(post_json /control/detection '{"paused": true}')
check "pause detection response"      '"detection_paused":true' "$r"

r=$(curl -s "$BASE/control/status")
check "status shows detection paused" '"detection_paused":true' "$r"

r=$(post_json /control/detection '{"paused": false}')
check "resume detection response"     '"detection_paused":false' "$r"

r=$(curl -s "$BASE/control/status")
check "status shows detection running" '"detection_paused":false' "$r"

# ── 4. Capture pause / resume ─────────────────────────────────
echo ""
echo "--- Capture pause / resume ---"

r=$(post_json /control/capture '{"paused": true}')
check "pause capture response"        '"capture_paused":true'  "$r"

r=$(curl -s "$BASE/control/status")
check "status shows capture paused"   '"capture_paused":true'  "$r"

r=$(post_json /control/capture '{"paused": false}')
check "resume capture response"       '"capture_paused":false' "$r"

r=$(curl -s "$BASE/control/status")
check "status shows capture running"  '"capture_paused":false' "$r"

# ── 5. Frame delay ─────────────────────────────────────────────
echo ""
echo "--- Frame delay ---"

r=$(post_json /control/delay '{"seconds": 1.0}')
check "set delay 1.0s"                '"frame_delay":1.0'      "$r"

r=$(curl -s "$BASE/control/status")
check "status shows delay 1.0"        '"frame_delay":1.0'      "$r"

r=$(post_json /control/delay '{"seconds": 3.5}')
check "set delay 3.5s"                '"frame_delay":3.5'      "$r"

r=$(post_json /control/delay '{"seconds": 0.5}')
check "set delay 0.5s"                '"frame_delay":0.5'      "$r"

r=$(post_json /control/delay '{"seconds": 999}')
check "delay 999 clamped to 30"       '"frame_delay":30.0'     "$r"

r=$(post_json /control/delay '{"seconds": -5}')
check "negative delay clamped to 0"   '"frame_delay":0.0'      "$r"

code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/control/delay" \
  -H "Content-Type: application/json" --data-raw '{"seconds": "notanumber"}')
check "bad delay value -> HTTP 400"   "400"                      "$code"

r=$(post_json /control/delay '{"seconds": 0}')
check "reset delay to 0"              '"frame_delay":0.0'      "$r"

# ── 6. Simultaneous state changes ─────────────────────────────
echo ""
echo "--- Simultaneous state ---"

post_json /control/detection '{"paused": true}'  > /dev/null
post_json /control/capture   '{"paused": true}'  > /dev/null
post_json /control/delay     '{"seconds": 2.5}'  > /dev/null

r=$(curl -s "$BASE/control/status")
check "all three set: detection"      '"detection_paused":true' "$r"
check "all three set: capture"        '"capture_paused":true'   "$r"
check "all three set: delay"          '"frame_delay":2.5'       "$r"

post_json /control/detection '{"paused": false}' > /dev/null
post_json /control/capture   '{"paused": false}' > /dev/null
post_json /control/delay     '{"seconds": 0}'    > /dev/null

r=$(curl -s "$BASE/control/status")
check "all three reset: detection"    '"detection_paused":false' "$r"
check "all three reset: capture"      '"capture_paused":false'   "$r"
check "all three reset: delay"        '"frame_delay":0'          "$r"

# ── 7. Toggle cycle: pause → pause again (idempotent) ─────────
echo ""
echo "--- Idempotency ---"

post_json /control/detection '{"paused": true}'  > /dev/null
r=$(post_json /control/detection '{"paused": true}')
check "double-pause is idempotent"    '"detection_paused":true' "$r"
post_json /control/detection '{"paused": false}' > /dev/null

# ── 8. Dashboard HTML elements ────────────────────────────────
echo ""
echo "--- Dashboard HTML ---"

r=$(curl -s "$BASE/")
check "HTML: video-stream element"    "video-stream"             "$r"
check "HTML: btn-detection"           "btn-detection"            "$r"
check "HTML: btn-capture"             "btn-capture"              "$r"
check "HTML: delay-slider"            "delay-slider"             "$r"
check "HTML: info-icon tooltips"      "info-icon"                "$r"
check "HTML: tooltip text detection"  "detection"                "$r"
check "HTML: tooltip text capture"    "capture"                  "$r"
check "HTML: fetches /control/status" "control/status"           "$r"
check "HTML: toggleDetection()"       "toggleDetection"          "$r"
check "HTML: toggleCapture()"         "toggleCapture"            "$r"
check "HTML: applyDelay()"            "applyDelay"               "$r"
check "HTML: onDelayInput()"          "onDelayInput"             "$r"
check "HTML: stat-detections"         "stat-detections"          "$r"
check "HTML: uptime-display"          "uptime-display"           "$r"
check "HTML: strike-log"              "strike-log"               "$r"
check "HTML: arm-state"               "arm-state"                "$r"
check "HTML: btn-weed"                "btn-weed"                 "$r"
check "HTML: btn-pest"                "btn-pest"                 "$r"
check "HTML: btn-rat"                 "btn-rat"                  "$r"
check "HTML: toggleDetector()"        "toggleDetector"           "$r"
check "HTML: detectorState JS object" "detectorState"            "$r"
check "HTML: bird tooltip"            "bird"                     "$r"

# ── 9. Per-detector toggle endpoints ──────────────────────────
echo ""
echo "--- Per-detector toggles ---"

r=$(curl -s "$BASE/control/status")
check "status has weed_detect_enabled"  "weed_detect_enabled"          "$r"
check "status has pest_detect_enabled"  "pest_detect_enabled"          "$r"
check "status has rat_detect_enabled"   "rat_detect_enabled"           "$r"
check "weed starts enabled"             '"weed_detect_enabled":true'   "$r"
check "pest starts enabled"             '"pest_detect_enabled":true'   "$r"
check "rat starts enabled"              '"rat_detect_enabled":true'    "$r"

r=$(post_json /control/weed '{"enabled": false}')
check "disable weed response"           '"weed_detect_enabled":false'  "$r"
r=$(curl -s "$BASE/control/status")
check "status shows weed disabled"      '"weed_detect_enabled":false'  "$r"
r=$(post_json /control/weed '{"enabled": true}')
check "re-enable weed"                  '"weed_detect_enabled":true'   "$r"

r=$(post_json /control/pest '{"enabled": false}')
check "disable pest response"           '"pest_detect_enabled":false'  "$r"
r=$(curl -s "$BASE/control/status")
check "status shows pest disabled"      '"pest_detect_enabled":false'  "$r"
r=$(post_json /control/pest '{"enabled": true}')
check "re-enable pest"                  '"pest_detect_enabled":true'   "$r"

r=$(post_json /control/rat '{"enabled": false}')
check "disable rat response"            '"rat_detect_enabled":false'   "$r"
r=$(curl -s "$BASE/control/status")
check "status shows rat disabled"       '"rat_detect_enabled":false'   "$r"
r=$(post_json /control/rat '{"enabled": true}')
check "re-enable rat"                   '"rat_detect_enabled":true'    "$r"

# All three off simultaneously
post_json /control/weed '{"enabled": false}' > /dev/null
post_json /control/pest '{"enabled": false}' > /dev/null
post_json /control/rat  '{"enabled": false}' > /dev/null
r=$(curl -s "$BASE/control/status")
check "all three disabled: weed"        '"weed_detect_enabled":false'  "$r"
check "all three disabled: pest"        '"pest_detect_enabled":false'  "$r"
check "all three disabled: rat"         '"rat_detect_enabled":false'   "$r"

# Restore
post_json /control/weed '{"enabled": true}' > /dev/null
post_json /control/pest '{"enabled": true}' > /dev/null
post_json /control/rat  '{"enabled": true}' > /dev/null
r=$(curl -s "$BASE/control/status")
check "all three re-enabled: weed"      '"weed_detect_enabled":true'   "$r"
check "all three re-enabled: pest"      '"pest_detect_enabled":true'   "$r"
check "all three re-enabled: rat"       '"rat_detect_enabled":true'    "$r"

# ── 10. Unit tests (non-torch) ────────────────────────────────
echo ""
echo "--- Unit tests (arm/camera/zone) ---"

cd /home/rpi/weed-robot
.venv/bin/python -m pytest tests/ \
  --ignore=tests/test_detector_rpi.py \
  --ignore=tests/test_dashboard_api.sh \
  -v --tb=short 2>&1 | tail -10

# ── Summary ──────────────────────────────────────────────────
echo ""
echo "============================================="
echo "  API Tests: $PASS passed, $FAIL failed"
echo "============================================="
[ $FAIL -eq 0 ] && echo -e "${GREEN}ALL API TESTS PASSED${NC}" || echo -e "${RED}SOME TESTS FAILED${NC}"
exit $FAIL
