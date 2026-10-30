"""Traz um vídeo do Google Drive ou do YouTube e manda para o processamento.

Uso: baixar_drive.py <link do arquivo ou do YouTube> [id do projeto]
Com o id do projeto, o vídeo só é religado a uma pregação que já está no app (sem processar de novo).
O vídeo original (5 a 10 GB) não é salvo: o ffmpeg lê direto do Drive e grava uma versão leve
(540p, ~0,5 GB por hora) em CortesAutomacao/videos, que serve para assistir no app e transcrever.
Um de cada vez (fila). O andamento fica em .sistema/downloads/<id>.json (a interface mostra).
O link precisa estar compartilhado como "Qualquer pessoa com o link".
"""
import fcntl, html, json, os, re, shutil, subprocess, sys, time, urllib.error, urllib.request
from email.message import Message
from pathlib import Path

import comum

SIS = Path.home() / "CortesAutomacao" / ".sistema"
VIDEOS = Path.home() / "CortesAutomacao" / "videos"
DOWN = SIS / "downloads"
FFMPEG = SIS / "bin" / "ffmpeg"
TRANS = SIS / "transcricoes"
UA = "Mozilla/5.0"
VIDEO_EXT = (".mp4", ".mov", ".m4v", ".mkv", ".mxf", ".avi", ".mts")


def id_do_link(link):
    for padrao in (r"/folders/([\w-]{20,})", r"/file/d/([\w-]{20,})", r"[?&]id=([\w-]{20,})", r"/d/([\w-]{20,})",
                   r"^([\w-]{25,})$"):
        m = re.search(padrao, link.strip())
        if m:
            return m.group(1)
    return None


def listar_pasta(fid):
    """Vídeos e subpastas de uma pasta pública do Drive."""
    req = urllib.request.Request(f"https://drive.google.com/embeddedfolderview?id={fid}", headers={"User-Agent": UA})
    t = urllib.request.urlopen(req, timeout=30).read().decode()
    titulo = html.unescape((re.search(r"<title>(.*?)</title>", t) or [0, "Pasta do Drive"])[1])
    itens = []
    for m in re.finditer(r'<div class="flip-entry" id="entry-([\w-]+)".*?<div class="flip-entry-title">(.*?)</div>', t, re.S):
        nome = html.unescape(m.group(2))
        pasta = "/folders/" in m.group(0)
        if pasta or nome.lower().endswith(VIDEO_EXT):
            itens.append({"id": m.group(1), "nome": nome, "pasta": pasta})
    return {"id": fid, "titulo": titulo, "itens": sorted(itens, key=lambda i: (not i["pasta"], i["nome"]))}


def motivo_da_falha(url):
    """O Drive responde uma página em vez do vídeo quando bloqueia: descobre qual foi o motivo."""
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30) as r:
            if "text/html" not in r.headers.get("Content-Type", ""):
                return None
            pagina = r.read(4000).decode(errors="ignore")
    except Exception:
        return None
    if "Quota exceeded" in pagina:
        return ("o Google Drive atingiu o limite de downloads desse vídeo por hoje (regra do Google para arquivos "
                "compartilhados). Tente de novo amanhã")
    return "o Drive não liberou o vídeo: confira se o link está como \"Qualquer pessoa com o link\""


def salvar(fid, **kw):
    p = DOWN / f"{fid}.json"
    d = json.loads(p.read_text()) if p.exists() else {}
    d.update(kw, quando=time.time())
    p.write_text(json.dumps(d, ensure_ascii=False))


def entregar(fid, destino, projeto, link):
    """Vídeo pronto: religa ao projeto pedido ou manda processar."""
    salvar(fid, status="baixado", progresso=100, video=str(destino))
    # de onde veio o original: a exportação de cortes busca a qualidade cheia lá
    destino.with_name(destino.stem + ".origem.txt").write_text(link)
    if projeto and (TRANS / projeto).is_dir():
        (TRANS / projeto / "video.txt").write_text(str(destino))
    else:
        subprocess.Popen(["nohup", str(SIS / "processar.sh"), str(destino)], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def baixar_youtube(link, projeto=None):
    m = re.search(r"(?:v=|youtu\.be/|shorts/|live/|embed/)([\w-]{11})", link)
    if not m:
        print("link do YouTube inválido")
        return 1
    fid = "yt_" + m.group(1)
    DOWN.mkdir(parents=True, exist_ok=True)
    VIDEOS.mkdir(parents=True, exist_ok=True)
    salvar(fid, link=link, nome="Vídeo do YouTube", status="na fila", progresso=0)
    try:
        with open(DOWN / ".fila", "w") as trava:
            fcntl.flock(trava, fcntl.LOCK_EX)  # um vídeo por vez
            if shutil.disk_usage(VIDEOS).free < 3 * 1024 ** 3:
                raise RuntimeError("o Mac está com menos de 3 GB livres")
            salvar(fid, status="baixando")
            base, env = comum.ytdlp()
            # versão leve (até 540p na horizontal), suficiente para assistir no app e transcrever
            p = subprocess.Popen([*base, "--no-playlist", "--ffmpeg-location", str(FFMPEG),
                                  "-f", "bv*[width<=960][height<=960][vcodec^=avc1]+ba[ext=m4a]/b[width<=960][height<=960]/b",
                                  "--merge-output-format", "mp4", "-o", str(VIDEOS / "%(title).80s.%(ext)s"),
                                  "--newline", "--progress-template", "download:PCT %(progress._percent_str)s",
                                  "--print", "before_dl:NOME %(title)s", "--print", "after_move:ARQ %(filepath)s", link],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
            destino, ultimo = None, 0
            for linha in p.stdout:
                if linha.startswith("NOME "):
                    salvar(fid, nome=linha[5:].strip())
                elif linha.startswith("ARQ "):
                    destino = Path(linha[4:].strip())
                elif linha.startswith("PCT ") and time.time() - ultimo > 1:
                    pct = re.search(r"([\d.]+)%", linha)
                    salvar(fid, progresso=min(99, round(float(pct.group(1)))) if pct else 0)
                    ultimo = time.time()
            if p.wait() != 0 or not destino:
                raise RuntimeError("o YouTube não liberou o vídeo (privado, removido ou com restrição de idade?)")
        entregar(fid, destino, projeto, link)
        return 0
    except Exception as e:
        salvar(fid, status="erro", erro=str(e))
        with open(SIS / "log.txt", "a") as f:
            f.write(time.strftime("%d/%m %H:%M ") + f"ERRO youtube {link}: {e}\n")
        return 1


def baixar(link, projeto=None):
    if "youtu" in link:
        return baixar_youtube(link, projeto)
    fid = id_do_link(link)
    if not fid:
        print("link inválido")
        return 1
    DOWN.mkdir(parents=True, exist_ok=True)
    VIDEOS.mkdir(parents=True, exist_ok=True)
    url = f"https://drive.usercontent.google.com/download?id={fid}&export=download&confirm=t"
    salvar(fid, link=link, nome="Link do Drive", status="na fila", progresso=0)
    try:
        # confere o acesso e descobre o nome sem baixar o arquivo
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Range": "bytes=0-0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            if "text/html" in r.headers.get("Content-Type", ""):
                raise RuntimeError("o Drive não liberou o arquivo: deixe o link como \"Qualquer pessoa com o link\"")
            msg = Message()
            msg["content-disposition"] = r.headers.get("Content-Disposition", "")
            nome = Path(msg.get_filename() or f"drive_{fid}.mp4").name
        # mesmo nome do original, para reaproveitar uma transcrição que já exista
        destino = VIDEOS / (Path(nome).stem + ".mp4")
        salvar(fid, nome=nome)

        with open(DOWN / ".fila", "w") as trava:
            fcntl.flock(trava, fcntl.LOCK_EX)  # um vídeo do Drive por vez
            if shutil.disk_usage(VIDEOS).free < 3 * 1024 ** 3:
                raise RuntimeError("o Mac está com menos de 3 GB livres")
            salvar(fid, status="baixando")
            info = subprocess.run([str(FFMPEG), "-hide_banner", "-user_agent", UA, "-i", url],
                                  capture_output=True, text=True).stderr
            m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", info)
            total = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0
            parcial = destino.with_name(destino.stem + ".baixando.mp4")
            p = subprocess.Popen([str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y", "-user_agent", UA,
                                  "-reconnect", "1", "-reconnect_delay_max", "30",
                                  "-i", url, "-vf", "scale=-2:540", "-c:v", "h264_videotoolbox", "-b:v", "1200k",
                                  "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", "-progress", "pipe:1",
                                  str(parcial)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            ultimo = 0
            for linha in p.stdout:
                if linha.startswith("out_time_us=") and total and time.time() - ultimo > 1:
                    feito = int(linha.split("=")[1].strip() or 0) / 1e6
                    salvar(fid, progresso=max(0, min(99, round(feito / total * 100))))
                    ultimo = time.time()
            if p.wait() != 0:
                parcial.unlink(missing_ok=True)
                raise RuntimeError(motivo_da_falha(url) or "a conexão com o Drive caiu no meio. Tente de novo")
            parcial.rename(destino)
        entregar(fid, destino, projeto, f"https://drive.google.com/file/d/{fid}")
        return 0
    except Exception as e:
        if isinstance(e, urllib.error.HTTPError) and e.code in (401, 403, 404):
            e = "não achei o vídeo: confira o link e deixe como \"Qualquer pessoa com o link\""
        salvar(fid, status="erro", erro=str(e))
        with open(SIS / "log.txt", "a") as f:
            f.write(time.strftime("%d/%m %H:%M ") + f"ERRO drive {link}: {e}\n")
        return 1


if __name__ == "__main__":
    comum.aplicar_prioridade()
    sys.exit(baixar(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None))
