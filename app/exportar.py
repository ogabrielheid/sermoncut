"""Exporta um trecho (corte) de uma pregação, já cortado, para jogar no editor.

Uso: exportar.py <pedido.json>
  pedido: {"id", "projeto", "inicio", "fim" (segundos), "nome", "altura" (0 = original | 720 | 1080 | 2160),
           "fps" (0 = original | 24 | 30 | 60), "mbps" (0 = automático)}
Busca a melhor fonte que existir: o arquivo original no Mac, o original no Google Drive (só o trecho, sem baixar
tudo), o YouTube na resolução pedida ou, por último, a versão leve que o app guarda.
O andamento fica em .sistema/exportacoes/<id>.json. O arquivo vai para Mesa/CORTES EXPORTADOS.
"""
import json, os, re, subprocess, sys, tempfile, time
from pathlib import Path

import comum

SIS = Path.home() / "CortesAutomacao" / ".sistema"
TRANS = SIS / "transcricoes"
FFMPEG = SIS / "bin" / "ffmpeg"
SAIDA = Path.home() / "Desktop" / "CORTES EXPORTADOS"
UA = "Mozilla/5.0"
LIMITE = 179  # 2min59s


def fonte(projeto):
    """Lista as fontes possíveis, da melhor para a pior: [(tipo, endereço)]."""
    video = Path((TRANS / projeto / "video.txt").read_text().strip())
    origem = video.with_name(video.stem + ".origem.txt")
    link = origem.read_text().strip() if origem.exists() else ""
    fontes = []
    if "youtu" in link:
        fontes.append(("youtube", link))
    elif m := re.search(r"/file/d/([\w-]+)", link):
        fontes.append(("drive", f"https://drive.usercontent.google.com/download?id={m.group(1)}&export=download&confirm=t"))
    if video.exists():
        fontes.append(("leve" if link else "original", str(video)))
    return fontes


def web(endereco):
    """Opções de rede do ffmpeg (só valem para links)."""
    return ["-user_agent", UA] if endereco.startswith("http") else []


def sondar(endereco):
    """Largura, altura e fps de um vídeo (arquivo ou link)."""
    info = subprocess.run([str(FFMPEG), "-hide_banner", *web(endereco), "-i", endereco],
                          capture_output=True, text=True, timeout=120).stderr
    m = re.search(r"Video: .*?, (\d{2,5})x(\d{2,5})", info)
    f = re.search(r"([\d.]+) fps", info)
    if not m:
        raise RuntimeError("não consegui abrir o vídeo de origem")
    return int(m.group(1)), int(m.group(2)), float(f.group(1)) if f else 30.0


def main(pedido):
    job = SIS / "exportacoes" / f"{pedido['id']}.json"
    estado = dict(pedido, status="preparando", progresso=0)

    def salvar(**kw):
        estado.update(kw, quando=time.time())
        job.write_text(json.dumps(estado, ensure_ascii=False))

    salvar()
    tmp = None
    try:
        ini, fim = float(pedido["inicio"]), float(pedido["fim"])
        dur = fim - ini
        if dur <= 0:
            raise RuntimeError("a saída precisa ser depois da entrada")
        if dur > LIMITE + 0.5:
            raise RuntimeError("o corte pode ter no máximo 2min59s")

        entrada, tipo, desloc = None, None, ini
        for tipo, endereco in fonte(pedido["projeto"]):
            try:
                if tipo == "youtube":
                    salvar(status="baixando o trecho do YouTube", fonte=tipo)
                    tmp = Path(tempfile.mkdtemp(prefix="corte_"))
                    alt = pedido["altura"] or 4320
                    base, env = comum.ytdlp()
                    subprocess.run([*base, "--no-playlist", "--ffmpeg-location", str(FFMPEG),
                                    "-f", f"bv*[height<={alt}][width<={alt * 16 // 9 + 8}]+ba/b",
                                    "--download-sections", f"*{max(0, ini - 2)}-{fim + 2}", "--merge-output-format", "mkv",
                                    "-o", str(tmp / "trecho.%(ext)s"), endereco],
                                   check=True, capture_output=True, timeout=1800, env=env)
                    endereco, desloc = str(next(tmp.glob("trecho.*"))), ini - max(0, ini - 2)
                largura, altura, fps = sondar(endereco)
                entrada = endereco
                break
            except Exception:
                continue  # Drive com limite do dia, YouTube fora do ar...: tenta a próxima fonte
        if not entrada:
            raise RuntimeError("nenhuma fonte do vídeo está disponível")

        filtros = []
        if pedido["altura"]:
            alvo = pedido["altura"]  # 720p / 1080p / 4K valem para o lado menor (serve para vertical também)
            filtros.append(f"scale='if(gt(iw,ih),-2,{alvo})':'if(gt(iw,ih),{alvo},-2)':flags=lanczos")
            curto = alvo
        else:
            curto = min(largura, altura)
        if pedido["fps"]:
            filtros.append(f"fps={pedido['fps']}")
        mbps = pedido["mbps"] or (10 if curto <= 720 else 20 if curto <= 1080 else 50)
        if (pedido["fps"] or fps) > 40 and not pedido["mbps"]:
            mbps = round(mbps * 1.5)

        SAIDA.mkdir(parents=True, exist_ok=True)
        nome = re.sub(r'[\\/:*?"<>|]+', "", pedido["nome"]).strip()[:120] or "corte"
        out = SAIDA / f"{nome}.mp4"
        n = 2
        while out.exists():
            out = SAIDA / f"{nome} ({n}).mp4"
            n += 1
        salvar(status="exportando", fonte=tipo, arquivo=str(out),
               original=f"{largura}x{altura} {fps:g} fps", mbps=mbps)
        cmd = [str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y", *web(entrada),
               "-ss", f"{desloc:.3f}", "-i", entrada, "-t", f"{dur:.3f}"]
        if filtros:
            cmd += ["-vf", ",".join(filtros)]
        cmd += ["-c:v", "h264_videotoolbox", "-b:v", f"{mbps}M", "-maxrate", f"{round(mbps * 1.3)}M",
                "-bufsize", f"{mbps * 2}M", "-profile:v", "high", "-c:a", "aac", "-b:a", "320k",
                "-movflags", "+faststart", "-progress", "pipe:1", str(out)]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        ultimo = 0
        for linha in p.stdout:
            if linha.startswith("out_time_us=") and time.time() - ultimo > 0.5:
                feito = int(linha.split("=")[1].strip() or 0) / 1e6
                salvar(progresso=max(0, min(99, round(feito / dur * 100))))
                ultimo = time.time()
        if p.wait() != 0:
            out.unlink(missing_ok=True)
            raise RuntimeError("a exportação falhou: " + p.stderr.read()[-200:])
        salvar(status="pronto", progresso=100)
    except Exception as e:
        salvar(status="erro", erro=str(e))
        with open(SIS / "log.txt", "a") as f:
            f.write(time.strftime("%d/%m %H:%M ") + f"ERRO exportar {pedido.get('nome')}: {e}\n")
    finally:
        if tmp:
            for f in tmp.iterdir():
                f.unlink()
            tmp.rmdir()


if __name__ == "__main__":
    comum.aplicar_prioridade()
    main(json.loads(Path(sys.argv[1]).read_text()))
