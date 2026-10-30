"""Transcreve os vídeos novos da pasta de entrada.

Roda sozinho (launchd) quando algo cai na pasta e de hora em hora. Para cada
vídeo sem transcrição gera, em .sistema/transcricoes/<nome>/:
  transcricao.txt   uma frase por linha com [h:mm:ss]
  transcricao.json  frases e palavras com tempo
  status            "transcrevendo" -> "transcrito" (a análise do Claude
                    depois grava "relatorio_pronto")
"""
import fcntl, json, re, subprocess, sys, time
from pathlib import Path

BASE = Path.home() / "CortesAutomacao"
ENTRADA = BASE / "1 - SOLTE O VIDEO AQUI"
SIS = BASE / ".sistema"
TRANS = SIS / "transcricoes"
FFMPEG = SIS / "bin" / "ffmpeg"
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".mxf", ".avi", ".mts"}
LOG = SIS / "log.txt"


def log(msg):
    with open(LOG, "a") as f:
        f.write(time.strftime("%d/%m %H:%M ") + msg + "\n")


def slug(name):
    return re.sub(r"[^\w\-]+", "_", name, flags=re.UNICODE).strip("_")[:80]


def estavel(p):
    """Evita pegar um vídeo que ainda está sendo copiado para a pasta."""
    a = p.stat().st_size
    time.sleep(20)
    return p.exists() and p.stat().st_size == a and a > 0


def transcrever(video, pasta):
    from faster_whisper import WhisperModel
    (pasta / "status").write_text("transcrevendo")
    (pasta / "video.txt").write_text(str(video))
    wav = pasta / "audio.wav"
    subprocess.run([str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y", "-i", str(video),
                    "-vn", "-ac", "1", "-ar", "16000", str(wav)], check=True)
    import comum
    model = WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=comum.threads())
    segs, info = model.transcribe(str(wav), language="pt", beam_size=5,
                                  word_timestamps=True, vad_filter=True)
    (pasta / "duracao").write_text(str(info.duration))  # a interface usa para o progresso
    frases = []
    with open(pasta / "transcricao.txt", "w") as f:
        for s in segs:
            words = [{"w": w.word, "s": round(w.start, 2), "e": round(w.end, 2)} for w in (s.words or [])]
            frases.append({"s": round(s.start, 2), "e": round(s.end, 2), "t": s.text.strip(), "words": words})
            m, sec = divmod(int(s.start), 60); h, m = divmod(m, 60)
            f.write(f"[{h}:{m:02d}:{sec:02d}] {s.text.strip()}\n"); f.flush()
    json.dump({"video": str(video), "duracao": info.duration, "frases": frases},
              open(pasta / "transcricao.json", "w"), ensure_ascii=False)
    wav.unlink(missing_ok=True)
    (pasta / "status").write_text("transcrito")


def main():
    TRANS.mkdir(parents=True, exist_ok=True)
    lock = open(SIS / ".lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return  # já tem uma transcrição rodando
    for video in sorted(ENTRADA.iterdir(), key=lambda p: p.stat().st_mtime):
        if video.suffix.lower() not in VIDEO_EXT or video.name.startswith("."):
            continue
        pasta = TRANS / slug(video.stem)
        st = (pasta / "status").read_text().strip() if (pasta / "status").exists() else ""
        if st in ("transcrito", "relatorio_pronto"):
            continue
        if not estavel(video):
            continue
        pasta.mkdir(parents=True, exist_ok=True)
        log(f"transcrevendo {video.name}")
        t0 = time.time()
        try:
            transcrever(video, pasta)
            log(f"pronto {video.name} em {(time.time() - t0) / 60:.0f} min")
        except Exception as e:  # registra e segue para o próximo vídeo
            (pasta / "status").write_text("erro")
            log(f"ERRO {video.name}: {e}")


def um_video(caminho):
    """Modo do app: transcreve só o vídeo arrastado. Imprime a pasta de trabalho."""
    video = Path(caminho)
    pasta = TRANS / slug(video.stem)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "video.txt").write_text(str(video.resolve()))
    st = (pasta / "status").read_text().strip() if (pasta / "status").exists() else ""
    if st not in ("transcrito", "relatorio_pronto"):
        log(f"transcrevendo {video.name}")
        t0 = time.time()
        try:
            transcrever(video, pasta)
        except Exception:
            (pasta / "status").write_text("erro")
            raise
        log(f"pronto {video.name} em {(time.time() - t0) / 60:.0f} min")
    print(pasta)


if __name__ == "__main__":
    um_video(sys.argv[1]) if len(sys.argv) > 1 else main()
