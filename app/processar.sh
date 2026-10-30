#!/bin/bash
# Pipeline do app: vídeo -> transcrição -> melhores momentos -> estudo e frases (IA escolhida).
# Uso: processar.sh /caminho/do/video.mp4
# Tudo fica dentro de main(): o bash lê o arquivo inteiro antes de rodar, então dá para atualizar
# o app enquanto um vídeo está sendo processado.
SIS="$HOME/CortesAutomacao/.sistema"
PY="$SIS/venv/bin/python"
LOG="$SIS/log.txt"

# o texto vai como argumento para não quebrar o AppleScript com aspas no nome do vídeo
avisar() {
  osascript -e 'on run a' -e 'display notification (item 1 of a) with title "SermonCut" sound name "Glass"' \
    -e 'end run' "$1" >/dev/null 2>&1
}
falhar() { [ -d "$PASTA" ] && echo erro > "$PASTA/status"; echo "$(date '+%d/%m %H:%M') ERRO $NOME: $1" >> "$LOG"; avisar "Deu erro em $NOME: $1"; exit 1; }

main() {
  VIDEO="$1"
  NOME="$(basename "${VIDEO%.*}" | sed 's/[[:space:]]*$//')"
  # modo de desempenho escolhido na engrenagem (o resto do processamento herda a prioridade)
  case "$("$PY" "$SIS/comum.py" 2>/dev/null)" in
    leve) taskpolicy -b -p $$ >/dev/null 2>&1 ;;
    equilibrado) renice -n 10 -p $$ >/dev/null 2>&1 ;;
  esac
  # fila: um vídeo por vez, para não travar o Mac de 8 GB
  # (uma trava com mais de 4 h é de um processamento que morreu no meio)
  find "$SIS/.fila" -maxdepth 0 -mmin +240 -exec rmdir {} \; 2>/dev/null
  if ! mkdir "$SIS/.fila" 2>/dev/null; then
    avisar "\"$NOME\" entrou na fila. Começo assim que o vídeo anterior terminar."
    until mkdir "$SIS/.fila" 2>/dev/null; do sleep 30; done
  fi
  trap 'rmdir "$SIS/.fila"' EXIT
  avisar "Transcrevendo \"$NOME\". Isso leva uns 30 a 40 minutos para 1h de vídeo."
  PASTA="$("$PY" "$SIS/transcrever.py" "$VIDEO" 2>>"$LOG" | tail -1)"
  [ -f "$PASTA/transcricao.txt" ] || falhar "a transcrição não terminou"
  [ -s "$PASTA/transcricao.txt" ] || falhar "não encontrei fala nesse vídeo (ele tem áudio?)"
  # já analisado antes (ex.: o mesmo culto trazido de novo do Drive): só religa o vídeo
  if [ "$(cat "$PASTA/status")" = relatorio_pronto ] && [ -f "$PASTA/analise.json" ]; then
    avisar "\"$NOME\" já tinha sido analisado. O vídeo foi ligado de novo no app."
    return 0
  fi

  avisar "Transcrição pronta. Escolhendo os melhores momentos…"
  echo analisando > "$PASTA/status"
  "$PY" "$SIS/gerar.py" "$PASTA" momentos "$VIDEO"
  case $? in
    0) ;;
    3)  # conta grátis: a pessoa cola as respostas da IA pelo app
      echo aguardando_ia > "$PASTA/status"
      "$PY" "$SIS/gerar.py" "$PASTA" conteudo "$VIDEO"
      "$PY" "$SIS/gerar.py" "$PASTA" biblia "$VIDEO"
      avisar "Transcrição de \"$NOME\" pronta! Abra o SermonCut para levar o pedido à sua IA."
      return 0 ;;
    *) falhar "a IA não respondeu no formato esperado (veja o log)" ;;
  esac
  echo relatorio_pronto > "$PASTA/status"
  echo "$(date '+%d/%m %H:%M') cortes prontos: $NOME" >> "$LOG"
  avisar "Pronto! Os cortes de \"$NOME\" já estão no app."

  # material extra: estudo, devocional, frases de efeito e passagens bíblicas
  "$PY" "$SIS/gerar.py" "$PASTA" conteudo "$VIDEO" && avisar "Estudo, devocional e frases de \"$NOME\" prontos no app."
  "$PY" "$SIS/gerar.py" "$PASTA" biblia "$VIDEO"
}

main "$@"
exit $?
