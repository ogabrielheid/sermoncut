#!/bin/bash
# Instalador do SermonCut: dois cliques e ele prepara tudo neste Mac.
# Vai no zip como "Instalar SermonCut.command", ao lado da pasta "sermoncut" com os arquivos do app.
cd "$(dirname "$0")" || exit 1
ORIGEM="$PWD/sermoncut"
BASE="$HOME/CortesAutomacao"
SIS="$BASE/.sistema"
LOCAL="$HOME/.local/bin"
MESA="$HOME/Desktop"

passo() { printf "\n\033[1;38;5;208m▶ %s\033[0m\n" "$1"; }
ok() { printf "\033[0;32m  ✓ %s\033[0m\n" "$1"; }
erro() {
  printf "\n\033[1;31m✖ %s\033[0m\n\n" "$1"
  read -r -n 1 -p "Aperte qualquer tecla para fechar."
  exit 1
}

clear
printf "\033[1;38;5;208m"
cat <<'EOF'
   ✂  S E R M O N C U T
   Cortes, estudos e conteúdo a partir da pregação
EOF
printf "\033[0m\nA instalação leva uns 5 minutos. Deixe esta janela aberta até o fim.\n"

passo "Conferindo o Mac"
[ -d "$ORIGEM" ] || erro "Não achei a pasta 'sermoncut'. Descompacte o zip inteiro e rode o instalador de dentro dele."
[ "$(uname -m)" = arm64 ] || erro "O SermonCut precisa de um Mac com chip Apple (M1 ou mais novo)."
if [ ! -d "/Applications/Google Chrome.app" ]; then
  open "https://www.google.com/chrome/"
  erro "Instale o Google Chrome (abri a página) e depois rode o instalador de novo."
fi
livre=$(df -g "$HOME" | awk 'NR==2 {print $4}')
[ "${livre:-0}" -ge 3 ] || erro "O Mac precisa de pelo menos 3 GB livres (tem ${livre} GB)."
ok "Mac com chip Apple, Chrome instalado e ${livre} GB livres"

passo "Copiando os arquivos do app"
mkdir -p "$SIS/bin" "$BASE/videos"
for f in "$ORIGEM"/*; do
  nome=$(basename "$f")
  # as preferências da pessoa não são apagadas numa reinstalação
  [ "$nome" = ajustes.json ] && [ -f "$SIS/ajustes.json" ] && continue
  cp -R "$f" "$SIS/"
done
chmod +x "$SIS"/*.sh "$SIS"/*.py 2>/dev/null
ok "Arquivos em $SIS"

passo "Instalando o Python e as ferramentas de vídeo (uns 3 minutos)"
UV="$LOCAL/uv"
if [ ! -x "$UV" ]; then
  curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh >/dev/null 2>&1 || erro "Não consegui baixar o instalador do Python. Confira a internet."
fi
"$UV" python install 3.12 >/dev/null 2>&1 || erro "Não consegui instalar o Python."
"$UV" venv -q --allow-existing --python 3.12 "$SIS/venv" || erro "Não consegui criar o ambiente do app."
"$UV" pip install -q --python "$SIS/venv/bin/python" -r "$SIS/requisitos.txt" \
  || erro "Não consegui instalar as ferramentas. Confira a internet e rode de novo."
ln -sfn "$SIS/venv" "$SIS/ytvenv"
ln -sf "$("$SIS/venv/bin/python" -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')" "$SIS/bin/ffmpeg"
ok "Python, transcrição, ffmpeg e YouTube prontos"

passo "Baixando o modelo de transcrição (uns 500 MB, só desta vez)"
"$SIS/venv/bin/python" -c 'from faster_whisper import WhisperModel; WhisperModel("small", device="cpu", compute_type="int8")' \
  >/dev/null 2>&1 || erro "Não consegui baixar o modelo de transcrição. Confira a internet."
ok "Modelo de transcrição pronto"

passo "Instalando o Claude (opcional, para quem tem assinatura Claude Pro)"
if [ ! -x "$LOCAL/claude" ]; then
  curl -fsSL https://claude.ai/install.sh | bash >/dev/null 2>&1
fi
[ -x "$LOCAL/claude" ] && ok "Claude instalado" || ok "Claude não instalado (dá para usar Gemini, ChatGPT, DeepSeek ou conta grátis)"

passo "Criando o app SermonCut na Mesa"
APP="$MESA/SermonCut.app"
rm -rf "$APP"
osacompile -o "$APP" "$SIS/app.applescript" || erro "Não consegui criar o app."
cp "$SIS/applet.icns" "$APP/Contents/Resources/applet.icns"
cp "$SIS/applet.icns" "$APP/Contents/Resources/droplet.icns"
rm -f "$APP/Contents/Resources/Assets.car"
/usr/libexec/PlistBuddy -c 'Delete :CFBundleIconName' "$APP/Contents/Info.plist" 2>/dev/null
/usr/libexec/PlistBuddy -c 'Set :CFBundleName SermonCut' "$APP/Contents/Info.plist" 2>/dev/null
codesign --force --sign - "$APP" >/dev/null 2>&1
touch "$APP"
ok "Ícone SermonCut criado na Mesa"

printf "\n\033[1;32m✓ Pronto! O SermonCut está na sua Mesa.\033[0m\n"
printf "  Na primeira vez, o app pede para você escolher a IA das análises (tem opções grátis).\n"
printf "  Depois é só arrastar o vídeo de um culto no ícone, ou trazer pelo Drive ou YouTube.\n\n"
open "$APP"
read -r -n 1 -p "Aperte qualquer tecla para fechar esta janela."
