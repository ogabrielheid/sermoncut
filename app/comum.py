"""Coisas usadas por vários scripts do app: modo de desempenho e como chamar o yt-dlp."""
import json, os, shutil, subprocess
from pathlib import Path

SIS = Path.home() / "CortesAutomacao" / ".sistema"
YTDLP = SIS / "ytvenv" / "bin" / "yt-dlp"

# leve: só os núcleos de economia do Mac, quase não se nota (mais lento)
# equilibrado: prioridade baixa, deixa o Mac livre para editar enquanto processa
# maximo: usa todos os núcleos, termina o mais rápido possível
MODOS = ("leve", "equilibrado", "maximo")


def modo():
    try:
        m = json.loads((SIS / "ajustes.json").read_text()).get("desempenho", {}).get("modo")
    except Exception:
        m = None
    return m if m in MODOS else "equilibrado"


def aplicar_prioridade(pid=None):
    """Ajusta a prioridade do processo (os filhos herdam)."""
    pid = pid or os.getpid()
    m = modo()
    if m == "leve":
        subprocess.run(["taskpolicy", "-b", "-p", str(pid)], capture_output=True)
    elif m == "equilibrado":
        try:
            os.setpriority(os.PRIO_PROCESS, pid, 10)
        except OSError:
            pass


def threads():
    nucleos = os.cpu_count() or 8
    return {"leve": 2, "equilibrado": max(2, nucleos // 2), "maximo": nucleos}[modo()]


def ytdlp():
    """Comando base do yt-dlp e o ambiente (deno vem junto com o app; node só se existir)."""
    caminho = f"{YTDLP.parent}:{Path.home() / '.local' / 'bin'}:{os.environ.get('PATH', '')}"
    cmd = [str(YTDLP)]
    if shutil.which("node", path=caminho):
        cmd += ["--js-runtimes", "node"]
    return cmd, dict(os.environ, PATH=caminho)


if __name__ == "__main__":
    print(modo())
