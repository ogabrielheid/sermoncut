#!/bin/bash
# Liga o servidor da interface (sempre um novo, para pegar atualizações) e abre a janela do app.
SIS="$HOME/CortesAutomacao/.sistema"
URL="http://127.0.0.1:47615/"
pkill -f "$SIS/servidor.py"; sleep 0.3
nohup "$SIS/venv/bin/python" "$SIS/servidor.py" >>"$SIS/log.txt" 2>&1 &
for _ in $(seq 20); do curl -s -m 1 "$URL" >/dev/null && break; sleep 0.25; done
open -na "Google Chrome" --args --app="$URL" --window-size=1440,900
