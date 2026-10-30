"""Pipeline do app: vídeo -> transcrição -> melhores momentos -> estudo, frases e passagens (IA escolhida).

Uso: processar.py <vídeo>
Um vídeo por vez (fila). Funciona igual no Mac e no Windows.
"""
import subprocess, sys, time
from pathlib import Path

import comum

SIS = comum.SIS
LOG = SIS / "log.txt"


def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(time.strftime("%d/%m %H:%M ") + msg + "\n")


def rodar(*args):
    return subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True,
                          creationflags=comum.SEM_JANELA)


def main(video):
    nome = Path(video).stem.strip()
    pasta = None

    def falhar(motivo):
        if pasta and pasta.exists():
            (pasta / "status").write_text("erro")
        log(f"ERRO {nome}: {motivo}")
        comum.avisar(f"Deu erro em {nome}: {motivo}")
        sys.exit(1)

    comum.aplicar_prioridade()
    if comum.ocupado("fila"):
        comum.avisar(f"“{nome}” entrou na fila. Começo assim que o vídeo anterior terminar.")
    with comum.trava("fila"):  # um vídeo por vez, para não travar o computador
        comum.avisar(f"Transcrevendo “{nome}”. Isso leva uns 30 a 40 minutos para 1h de vídeo.")
        r = rodar(SIS / "transcrever.py", video)
        if r.stderr.strip():
            log(r.stderr.strip()[-2000:])
        saida = r.stdout.strip().splitlines()
        pasta = Path(saida[-1]) if saida else None
        if not pasta or not (pasta / "transcricao.txt").exists():
            falhar("a transcrição não terminou")
        if not (pasta / "transcricao.txt").read_text(encoding="utf-8").strip():
            falhar("não encontrei fala nesse vídeo (ele tem áudio?)")
        # já analisado antes (ex.: o mesmo culto trazido de novo do Drive): só religa o vídeo
        status = (pasta / "status").read_text().strip() if (pasta / "status").exists() else ""
        if status == "relatorio_pronto" and (pasta / "analise.json").exists():
            comum.avisar(f"“{nome}” já tinha sido analisado. O vídeo foi ligado de novo no app.")
            return

        comum.avisar("Transcrição pronta. Escolhendo os melhores momentos…")
        (pasta / "status").write_text("analisando")
        rc = rodar(SIS / "gerar.py", pasta, "momentos", video).returncode
        if rc == 3:  # conta grátis: a pessoa cola as respostas da IA pelo app
            (pasta / "status").write_text("aguardando_ia")
            rodar(SIS / "gerar.py", pasta, "conteudo", video)
            rodar(SIS / "gerar.py", pasta, "biblia", video)
            comum.avisar(f"Transcrição de “{nome}” pronta! Abra o SermonCut para levar o pedido à sua IA.")
            return
        if rc != 0:
            falhar("a IA não respondeu no formato esperado (veja o log)")
        (pasta / "status").write_text("relatorio_pronto")
        log(f"cortes prontos: {nome}")
        comum.avisar(f"Pronto! Os cortes de “{nome}” já estão no app.")

        # material extra: estudo, devocional, frases de efeito e passagens bíblicas
        if rodar(SIS / "gerar.py", pasta, "conteudo", video).returncode == 0:
            comum.avisar(f"Estudo, devocional e frases de “{nome}” prontos no app.")
        rodar(SIS / "gerar.py", pasta, "biblia", video)


if __name__ == "__main__":
    main(sys.argv[1])
