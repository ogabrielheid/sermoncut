#!/bin/bash
# Publica uma nova versão do SermonCut no GitHub (só no Mac de quem criou o app).
# Uso: publicar.sh "o que mudou nesta versão"
# Na primeira vez cria o repositório público "sermoncut" na conta do GitHub conectada.
# Cada versão vira um "release" com:
#   SermonCut.zip          instalador do Mac
#   SermonCut-Windows.zip  instalador do Windows
#   atualizacao.zip   só os arquivos do app, que os apps já instalados baixam sozinhos
set -e
SIS="$HOME/CortesAutomacao/.sistema"
GH="$HOME/.local/bin/gh"
REPO_DIR="$HOME/CortesAutomacao/.repo"
NOTAS="${1:-Melhorias e correções.}"
ARQS=($(grep -v '^VERSAO$' "$SIS/arquivos.txt"))  # a lista de arquivos do app

"$GH" auth status >/dev/null 2>&1 || { echo "ERRO: entre na sua conta do GitHub primeiro"; exit 2; }
DONO=$("$GH" api user -q .login)
REPO="$DONO/sermoncut"
if ! "$GH" repo view "$REPO" >/dev/null 2>&1; then
  "$GH" repo create "$REPO" --public --add-readme \
    --description "Cortes, estudos e conteúdo a partir da pregação, para quem edita os vídeos da igreja local." >/dev/null
fi
echo "{\"repo\": \"$REPO\"}" > "$SIS/atualizacao.json"

# versão: se a atual já foi publicada, sobe o último número (1.0 -> 1.1)
ATUAL=$(cat "$SIS/VERSAO")
if "$GH" release view "v$ATUAL" --repo "$REPO" >/dev/null 2>&1; then
  NOVA=$(python3 -c "import sys; a=sys.argv[1].split('.'); a[-1]=str(int(a[-1])+1); print('.'.join(a))" "$ATUAL")
else
  NOVA="$ATUAL"
fi
echo "$NOVA" > "$SIS/VERSAO"

# o "Sobre" de quem baixar aponta para a página do projeto; criador.json leva o seu contato
# (nome, Instagram, WhatsApp) para todo mundo, inclusive para quem só recebe a atualização
"$SIS/venv/bin/python" - "$REPO" <<'PY'
import json, sys
from pathlib import Path
sis = Path.home() / "CortesAutomacao" / ".sistema"
a = sis / "ajustes.json"
d = json.loads(a.read_text()) if a.exists() else {}
s = d.setdefault("sobre", {})
s["link"] = f"https://github.com/{sys.argv[1]}"
a.write_text(json.dumps(d, ensure_ascii=False, indent=1))
c = json.loads((sis / "criador.json").read_text()) if (sis / "criador.json").exists() else {}
c.update({k: s.get(k, "") for k in ("nome", "instagram", "whatsapp", "texto")}, link=s["link"])
(sis / "criador.json").write_text(json.dumps(c, ensure_ascii=False, indent=1))
PY

TMP=$(mktemp -d)
cd "$SIS"
zip -q -j "$TMP/atualizacao.zip" "${ARQS[@]}" VERSAO atualizacao.json
"$SIS/gerar_pacote.sh" >/dev/null
cp "$HOME/Desktop/SermonCut.zip" "$HOME/Desktop/SermonCut-Windows.zip" "$TMP/"

# código e página do projeto
rm -rf "$REPO_DIR"
"$GH" repo clone "$REPO" "$REPO_DIR" -- -q
mkdir -p "$REPO_DIR/app" "$REPO_DIR/docs"
cp "${ARQS[@]}" VERSAO arquivos.txt instalador.command instalar.ps1 instalar.bat gerar_pacote.sh publicar.sh README_github.md "$REPO_DIR/app/"
[ -d "$SIS/docs" ] && cp "$SIS/docs/"* "$REPO_DIR/docs/"
sed -e "s#{{REPO}}#$REPO#g" -e "s#{{VERSAO}}#$NOVA#g" "$SIS/README_github.md" > "$REPO_DIR/README.md"
cd "$REPO_DIR"
git config user.name "$("$GH" api user -q '.name // .login')"
git config user.email "$("$GH" api user -q '.id')+$DONO@users.noreply.github.com"
git add -A
git commit -q -m "SermonCut $NOVA" -m "$NOTAS" ${COAUTOR:+-m "$COAUTOR"} || true
git -c credential.helper= -c "credential.helper=!$GH auth git-credential" push -q origin HEAD

"$GH" release create "v$NOVA" "$TMP/SermonCut.zip" "$TMP/SermonCut-Windows.zip" "$TMP/atualizacao.zip" --repo "$REPO" \
  --title "SermonCut $NOVA" --notes "$NOTAS" --latest >/dev/null
rm -rf "$TMP"
echo "https://github.com/$REPO"
