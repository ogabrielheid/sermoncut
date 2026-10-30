"""Coisas usadas por vários scripts do app: o que muda entre Mac e Windows, modo de desempenho e yt-dlp."""
import json, os, shutil, subprocess, sys, time
from contextlib import contextmanager
from pathlib import Path

WINDOWS = os.name == "nt"
MAC = sys.platform == "darwin"
SIS = Path.home() / "CortesAutomacao" / ".sistema"
BIN = "Scripts" if WINDOWS else "bin"
EXE = ".exe" if WINDOWS else ""
PY = SIS / "venv" / BIN / f"python{EXE}"
LOCAL = Path.home() / ".local" / "bin"
YTDLP = SIS / "ytvenv" / BIN / f"yt-dlp{EXE}"
SEM_JANELA = 0x08000000 if WINDOWS else 0  # CREATE_NO_WINDOW: comandos do Windows sem abrir janela preta
# no Windows o Python lê e grava texto em cp1252 por padrão: os processos do app (e os filhos) usam UTF-8
os.environ["PYTHONUTF8"] = "1"


# ---------- caminhos ----------
def mesa():
    """A Mesa (Mac) ou a Área de Trabalho (Windows, inclusive quando está no OneDrive)."""
    if WINDOWS:
        import ctypes
        buf = ctypes.create_unicode_buffer(260)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 0x10, None, 0, buf) == 0:  # CSIDL_DESKTOPDIRECTORY
            return Path(buf.value)
    return Path.home() / "Desktop"


def ffmpeg():
    p = SIS / "bin" / f"ffmpeg{EXE}"
    if p.exists():
        return str(p)
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def claude():
    return str(LOCAL / f"claude{EXE}")


def navegador():
    """Chrome no Mac; Edge (vem com o Windows) ou Chrome no Windows."""
    if MAC:
        return "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    for base in (os.environ.get("PROGRAMFILES(X86)", ""), os.environ.get("PROGRAMFILES", ""), os.environ.get("LOCALAPPDATA", "")):
        for rel in (r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe"):
            p = Path(base) / rel
            if base and p.exists():
                return str(p)
    return shutil.which("msedge") or shutil.which("chrome") or "msedge"


# ---------- processos ----------
def rodar(*args):
    """Começa um processo em segundo plano que continua mesmo se o servidor fechar.
    No Windows ele ganha um console escondido, que os filhos (ffmpeg, IA...) herdam: nenhuma janela preta aparece."""
    if WINDOWS:
        subprocess.Popen([str(a) for a in args], creationflags=0x00000200 | SEM_JANELA,  # NEW_PROCESS_GROUP
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, close_fds=True)
    else:
        subprocess.Popen([str(a) for a in args], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)


def python_script(nome, *args):
    """Roda outro script do app em segundo plano com o Python do app."""
    rodar(PY if PY.exists() else sys.executable, SIS / nome, *args)


def args_h264(mbps):
    """Opções do codificador escolhido para uma taxa de bits (Mbps)."""
    enc = encoder_h264()
    a = ["-c:v", enc, "-b:v", f"{mbps}M", "-maxrate", f"{round(mbps * 1.3, 1)}M", "-bufsize", f"{round(mbps * 2, 1)}M"]
    if enc == "libx264":
        a += ["-preset", "veryfast"]
    if enc in ("libx264", "h264_videotoolbox"):
        a += ["-profile:v", "high"]
    return a + ["-pix_fmt", "yuv420p"]


@contextmanager
def trava(nome, velha_h=4):
    """Fila: um por vez entre processos (funciona igual no Mac e no Windows).
    Uma trava com mais de velha_h horas é de um processo que morreu no meio."""
    pasta = SIS / f".trava_{nome}"
    while True:
        try:
            pasta.mkdir()
            break
        except FileExistsError:
            try:
                if time.time() - pasta.stat().st_mtime > velha_h * 3600:
                    pasta.rmdir()
                    continue
            except FileNotFoundError:
                continue
            time.sleep(5)
    try:
        yield
    finally:
        try:
            pasta.rmdir()
        except OSError:
            pass


def ocupado(nome):
    return (SIS / f".trava_{nome}").exists()


# ---------- sistema ----------
def avisar(texto, titulo="SermonCut"):
    """Notificação do sistema."""
    try:
        if MAC:
            subprocess.run(["osascript", "-e", "on run a", "-e",
                            'display notification (item 1 of a) with title (item 2 of a) sound name "Glass"', "-e", "end run",
                            texto, titulo], capture_output=True, timeout=10)
        elif WINDOWS:
            ps = ("Add-Type -AssemblyName System.Windows.Forms; $n = New-Object System.Windows.Forms.NotifyIcon; "
                  "$n.Icon = [System.Drawing.SystemIcons]::Information; $n.Visible = $true; "
                  "$n.ShowBalloonTip(8000, $env:SC_TITULO, $env:SC_TEXTO, 'Info'); Start-Sleep 9; $n.Dispose()")
            subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
                             env=dict(os.environ, SC_TITULO=titulo, SC_TEXTO=texto), creationflags=SEM_JANELA,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def escolher_video(titulo):
    """Janela do sistema para escolher um vídeo. Devolve o caminho ou None."""
    if MAC:
        r = subprocess.run(["osascript", "-e", "tell me to activate", "-e",
                            f'POSIX path of (choose file with prompt "{titulo}" of type {{"public.movie"}})'],
                           capture_output=True, text=True)
        return r.stdout.strip() or None
    codigo = ("import tkinter as tk, tkinter.filedialog as fd, sys\n"
              "r = tk.Tk(); r.withdraw(); r.attributes('-topmost', True)\n"
              "p = fd.askopenfilename(title=sys.argv[1], filetypes=[('Vídeos', '*.mp4 *.mov *.m4v *.mkv *.mxf *.avi *.mts'), ('Todos', '*.*')])\n"
              "print(p)")
    r = subprocess.run([sys.executable, "-c", codigo, titulo], capture_output=True, text=True)
    return r.stdout.strip() or None


def abrir(caminho):
    if WINDOWS:
        os.startfile(str(caminho))
    else:
        subprocess.run(["open", str(caminho)])


def revelar(caminho):
    """Mostra o arquivo selecionado no Finder / Explorador de Arquivos."""
    if WINDOWS:
        subprocess.run(["explorer", f"/select,{caminho}"])
    else:
        subprocess.run(["open", "-R", str(caminho)])


def abrir_terminal(comando, pasta):
    """Abre uma janela de terminal rodando um comando (ex.: login do Claude)."""
    if WINDOWS:
        subprocess.Popen(["cmd", "/c", "start", "SermonCut", "cmd", "/k", comando], cwd=pasta)
    else:
        arq = SIS / "terminal.command"
        arq.write_text(f'#!/bin/bash\ncd "{pasta}"\n{comando}\n')
        arq.chmod(0o755)
        subprocess.run(["open", str(arq)])


# ---------- vídeo ----------
_encoder = None


def encoder_h264():
    """O codificador H.264 mais rápido que existir: Mac (VideoToolbox), placa NVIDIA, Intel ou AMD; senão o processador."""
    global _encoder
    if _encoder:
        return _encoder
    candidatos = ["h264_videotoolbox"] if MAC else ["h264_nvenc", "h264_qsv", "h264_amf"]
    for enc in candidatos:
        r = subprocess.run([ffmpeg(), "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.2",
                            "-c:v", enc, "-f", "null", "-"], capture_output=True, creationflags=SEM_JANELA)
        if r.returncode == 0:
            _encoder = enc
            return enc
    _encoder = "libx264"
    return _encoder


# ---------- desempenho ----------
# leve: quase não se nota (mais lento) · equilibrado: prioridade baixa · maximo: usa tudo
MODOS = ("leve", "equilibrado", "maximo")


def modo():
    try:
        m = json.loads((SIS / "ajustes.json").read_text()).get("desempenho", {}).get("modo")
    except Exception:
        m = None
    return m if m in MODOS else "equilibrado"


def aplicar_prioridade(pid=None):
    """Ajusta a prioridade do processo (os filhos herdam)."""
    m = modo()
    if m == "maximo":
        return
    if WINDOWS:
        import ctypes
        classe = 0x40 if m == "leve" else 0x4000  # IDLE / BELOW_NORMAL
        h = ctypes.windll.kernel32.OpenProcess(0x0200, False, pid or os.getpid())  # PROCESS_SET_INFORMATION
        if h:
            ctypes.windll.kernel32.SetPriorityClass(h, classe)
            ctypes.windll.kernel32.CloseHandle(h)
        return
    pid = pid or os.getpid()
    if m == "leve" and MAC:
        subprocess.run(["taskpolicy", "-b", "-p", str(pid)], capture_output=True)
    else:
        try:
            os.setpriority(os.PRIO_PROCESS, pid, 15 if m == "leve" else 10)
        except OSError:
            pass


def threads():
    nucleos = os.cpu_count() or 8
    return {"leve": 2, "equilibrado": max(2, nucleos // 2), "maximo": nucleos}[modo()]


# ---------- yt-dlp ----------
def ytdlp():
    """Comando base do yt-dlp e o ambiente (deno vem junto com o app; node só se existir)."""
    caminho = os.pathsep.join([str(YTDLP.parent), str(LOCAL), os.environ.get("PATH", "")])
    cmd = [str(YTDLP)]
    if shutil.which("node", path=caminho):
        cmd += ["--js-runtimes", "node"]
    return cmd, dict(os.environ, PATH=caminho)


if __name__ == "__main__":
    print(modo())
