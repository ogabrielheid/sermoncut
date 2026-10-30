#!/bin/bash
# Monta os instaladores para compartilhar, na Mesa:
#   SermonCut.zip          Mac (Instalar SermonCut.command)
#   SermonCut-Windows.zip  Windows (Instalar SermonCut.bat)
# Levam só os arquivos do app (arquivos.txt): nada de vídeos, transcrições, chaves ou log.
SIS="$HOME/CortesAutomacao/.sistema"
TMP="$(mktemp -d)"
cd "$SIS" || exit 1
for so in Mac Windows; do
  DEST="$TMP/$so/SermonCut/sermoncut"
  mkdir -p "$DEST"
  xargs -I{} cp {} "$DEST/" < arquivos.txt
  [ -f atualizacao.json ] && cp atualizacao.json "$DEST/"
  # só o "Sobre" de quem criou vai junto; as abas começam no padrão
  "$SIS/venv/bin/python" - "$DEST/ajustes.json" <<'PY'
import json, sys
from pathlib import Path
a = Path.home() / "CortesAutomacao" / ".sistema" / "ajustes.json"
sobre = json.loads(a.read_text()).get("sobre", {}) if a.exists() else {}
Path(sys.argv[1]).write_text(json.dumps({"sobre": sobre}, ensure_ascii=False, indent=1))
PY
done

cp instalador.command "$TMP/Mac/SermonCut/Instalar SermonCut.command"
chmod +x "$TMP/Mac/SermonCut/Instalar SermonCut.command"
cat > "$TMP/Mac/SermonCut/LEIA-ME.txt" <<'TXT'
SermonCut - cortes, estudos e conteúdo a partir da pregação

Como instalar no Mac:
1. Precisa de um Mac com chip Apple (M1 ou mais novo), o Google Chrome e uns 3 GB livres.
2. Clique com o botão direito em "Instalar SermonCut.command" e escolha Abrir
   (na primeira vez o Mac pede essa confirmação porque o app não vem da App Store).
3. Siga a janela do Terminal. Leva uns 5 minutos.
4. Ao abrir o app pela primeira vez, escolha a IA das análises: Gemini (grátis), conta grátis
   do ChatGPT/Gemini/Claude/DeepSeek (copiar e colar), Claude Pro, ou uma chave de API.
5. O ícone SermonCut aparece na Mesa. Arraste o vídeo de um culto em cima dele.
TXT

cp instalar.bat "$TMP/Windows/SermonCut/Instalar SermonCut.bat"
cp instalar.ps1 "$TMP/Windows/SermonCut/instalar.ps1"
printf '%s\r\n' "SermonCut - cortes, estudos e conteúdo a partir da pregação" "" \
  "Como instalar no Windows:" \
  "1. Precisa do Windows 10 ou 11 (64 bits) e uns 3 GB livres." \
  "2. Extraia o zip inteiro: botão direito no arquivo > Extrair tudo." \
  "3. Dentro da pasta extraída, dê dois cliques em \"Instalar SermonCut.bat\"." \
  "   Se aparecer \"O Windows protegeu o computador\", clique em Mais informações > Executar assim mesmo." \
  "4. Siga a janela que abrir. Leva uns 5 minutos." \
  "5. O atalho SermonCut aparece na Área de Trabalho e no menu Iniciar." \
  "   Na primeira vez, escolha a IA das análises (tem opções grátis)." \
  "6. Arraste o vídeo de um culto em cima do atalho, ou traga pelo Drive ou YouTube." \
  > "$TMP/Windows/SermonCut/LEIA-ME.txt"

rm -f "$HOME/Desktop/SermonCut.zip" "$HOME/Desktop/SermonCut-Windows.zip"
(cd "$TMP/Mac" && ditto -c -k --norsrc --noextattr --keepParent SermonCut "$HOME/Desktop/SermonCut.zip")
(cd "$TMP/Windows" && ditto -c -k --norsrc --noextattr --keepParent SermonCut "$HOME/Desktop/SermonCut-Windows.zip")
rm -rf "$TMP"
echo "$HOME/Desktop/SermonCut.zip"
echo "$HOME/Desktop/SermonCut-Windows.zip"
