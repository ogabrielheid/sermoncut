"""Abre o SermonCut: liga o servidor (sempre um novo, para pegar atualizações) e abre a janela do app.

Uso: abrir.py [vídeos...]      os vídeos passados (arrastados no ícone) entram na fila de processamento
     abrir.py --so-servidor    só reinicia o servidor (usado depois de uma atualização)
"""
import os, signal, socket, subprocess, sys, time, urllib.request

import comum

SIS = comum.SIS
PORTA = 47615
URL = f"http://127.0.0.1:{PORTA}/"
PID = SIS / ".servidor.pid"


def no_ar():
    try:
        urllib.request.urlopen(URL + "api/ia", timeout=1)
        return True
    except Exception:
        return False


def porta_livre():
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", PORTA)) != 0


def parar_servidor():
    if PID.exists():
        try:
            os.kill(int(PID.read_text().strip()), signal.SIGTERM)
        except (OSError, ValueError):
            pass
    if not comum.WINDOWS:  # servidores ligados por versões antigas do app
        subprocess.run(["pkill", "-f", str(SIS / "servidor.py")], capture_output=True)
    for _ in range(40):
        if porta_livre():
            return
        time.sleep(0.25)


def ligar_servidor():
    comum.python_script("servidor.py")
    for _ in range(60):
        if no_ar():
            return True
        time.sleep(0.25)
    return False


def abrir_janela():
    if comum.MAC:
        subprocess.run(["open", "-na", "Google Chrome", "--args", f"--app={URL}", "--window-size=1440,900"])
    else:
        subprocess.Popen([comum.navegador(), f"--app={URL}", "--window-size=1440,900"])


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    for video in args:
        comum.python_script("processar.py", video)
    if "--so-servidor" in sys.argv:
        time.sleep(1)
    parar_servidor()
    ligar_servidor()
    if "--so-servidor" not in sys.argv:
        abrir_janela()
