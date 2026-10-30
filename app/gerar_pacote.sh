#!/bin/bash
# Monta o SermonCut.zip para compartilhar: instalador + arquivos do app (sem vídeos, transcrições, chaves nem log).
SIS="$HOME/CortesAutomacao/.sistema"
TMP="$(mktemp -d)"
DEST="$TMP/SermonCut/sermoncut"
mkdir -p "$DEST"
cd "$SIS" || exit 1
cp app.applescript applet.icns abrir_interface.sh processar.sh interface.html servidor.py transcrever.py gerar.py \
   gerar_pdf.py baixar_drive.py exportar.py canal.py comum.py ia.py atualizar.py requisitos.txt VERSAO prompt_*.md "$DEST/"
[ -f atualizacao.json ] && cp atualizacao.json "$DEST/"
# só o "Sobre" de quem criou vai junto; as abas começam no padrão
"$SIS/venv/bin/python" - "$DEST/ajustes.json" <<'PY'
import json, sys
from pathlib import Path
a = Path.home() / "CortesAutomacao" / ".sistema" / "ajustes.json"
sobre = json.loads(a.read_text()).get("sobre", {}) if a.exists() else {}
Path(sys.argv[1]).write_text(json.dumps({"sobre": sobre}, ensure_ascii=False, indent=1))
PY
cp instalador.command "$TMP/SermonCut/Instalar SermonCut.command"
chmod +x "$TMP/SermonCut/Instalar SermonCut.command"
cat > "$TMP/SermonCut/LEIA-ME.txt" <<'TXT'
SermonCut - cortes, estudos e conteúdo a partir da pregação

Como instalar:
1. Precisa de um Mac com chip Apple (M1 ou mais novo), o Google Chrome e uns 3 GB livres.
2. Clique com o botão direito em "Instalar SermonCut.command" e escolha Abrir
   (na primeira vez o Mac pede essa confirmação porque o app não vem da App Store).
3. Siga a janela do Terminal. Leva uns 5 minutos.
4. Ao abrir o app pela primeira vez, escolha a IA das análises: Gemini (grátis), conta grátis
   do ChatGPT/Gemini/Claude/DeepSeek (copiar e colar), Claude Pro, ou uma chave de API.
5. O ícone SermonCut aparece na Mesa. Arraste o vídeo de um culto em cima dele.
TXT
rm -f "$HOME/Desktop/SermonCut.zip"
(cd "$TMP" && ditto -c -k --norsrc --noextattr --keepParent SermonCut "$HOME/Desktop/SermonCut.zip")
rm -rf "$TMP"
echo "$HOME/Desktop/SermonCut.zip"
