#!/usr/bin/env bash
set -euo pipefail
G="$1"; P="$2"; O="$3"
"$G" --path "$P" --audio-driver Dummy -- --observe-input --capture-path="$O/interaction.png" > "$O/interaction.log" 2>&1 &
PID=$!
trap 'kill "$PID" 2>/dev/null || true' EXIT
W=$(timeout 20 xdotool search --sync --onlyvisible --name '^Parcel Switchyard' | head -1)
xdotool windowfocus --sync "$W"
xdotool key --window "$W" 2 space
sleep 4
xdotool mousemove --window "$W" 1080 316 click 1
xdotool key --window "$W" space
sleep 4
xdotool key --window "$W" F12
sleep 1
xdotool key --window "$W" r r
xdotool mousemove --window "$W" 1130 124 click 1
sleep 0.2
xdotool mousemove --window "$W" 1130 124 click 1
xdotool mousemove --window "$W" 1080 448 click 1
sleep 0.3
python - "$O/interaction.log" "$O/interaction-result.json" <<'PY'
import json,sys
from pathlib import Path
s=[json.loads(l.split('PARCEL_RUNTIME_STATE ',1)[1]) for l in Path(sys.argv[1]).read_text().splitlines() if l.startswith('PARCEL_RUNTIME_STATE ')]
checks={
 'keyboard_dispatch':any(x['sent']==1 and x['selected']==1 for x in s),
 'mouse_route_dispatch':any(x['sent']==2 and x['selected']==0 for x in s),
 'two_real_time_deliveries':any(x['delivered']==2 and x['missed']==0 for x in s),
 'repeated_keyboard_reset':sum(x['sent']==0 and x['delivered']==0 and x['selected']==1 for x in s)>=2,
 'mouse_auto_toggle':any(x['auto'] for x in s) and not s[-1]['auto'],
 'mouse_market_route':s[-1]['selected']==2,
}
Path(sys.argv[2]).write_text(json.dumps({'checks':checks,'states':s,'passed':all(checks.values())},indent=2)+'\n')
assert all(checks.values()),checks
PY
