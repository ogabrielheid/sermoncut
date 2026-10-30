"""Pede à IA escolhida uma parte do material de uma pregação já transcrita.

Uso: gerar.py <pasta da transcrição> <parte> [vídeo]
  momentos   cortes + potencial viral          -> analise.json
  conteudo   estudo, devocional e frases        -> conteudo.json
  biblia     passagens bíblicas citadas na pregação  -> biblia.json
  viral      só o potencial viral de cortes já escolhidos (projetos antigos) -> entra no analise.json
O andamento fica em <pasta>/<parte>_status: gerando -> pronto | colar | erro
"colar": a IA é uma conta grátis; o pedido fica em <pasta>/pedido_<parte>.txt e a pessoa traz a resposta pelo app.
Saída: 0 pronto, 3 esperando colar, 1 erro.
"""
import json, re, subprocess, sys, time
from pathlib import Path

import comum
import ia

SIS = Path.home() / "CortesAutomacao" / ".sistema"


def seg(t):
    return sum(int(v) * 60 ** i for i, v in enumerate(reversed(str(t).split(":"))))


def montar(pasta, parte, nome=None):
    """O texto completo que vai para a IA."""
    nome = nome or pasta.name.replace("_", " ")
    transcricao = (pasta / "transcricao.txt").read_text()
    if parte == "momentos":
        return f"{(SIS / 'prompt_analise.md').read_text()}\n\nNome do arquivo: {nome}\n\nTRANSCRIÇÃO:\n{transcricao}"
    if parte in ("conteudo", "biblia"):
        return f"{(SIS / f'prompt_{parte}.md').read_text()}\n\nTRANSCRIÇÃO:\n{transcricao}"
    a = json.loads((pasta / "analise.json").read_text())
    linhas = [(seg(m.group(1)), m.group(2)) for m in re.finditer(r"\[(\d+:\d\d:\d\d)\]\s*(.*)", transcricao)]
    cortes = []
    for i, m in enumerate(a["momentos"], 1):
        fala = " ".join(t for s, t in linhas if seg(m["inicio"]) - 1 <= s < seg(m["fim"]))
        cortes.append(f"CORTE {i} ({m['inicio']} → {m['fim']}) — {m['titulo']}\n{fala}")
    return (SIS / "prompt_viral.md").read_text() + "\n\n" + "\n\n".join(cortes)


def aplicar(pasta, parte, resposta):
    """Confere a resposta da IA e grava. Levanta erro se não vier no formato certo."""
    (pasta / f"resposta_{parte}.txt").write_text(resposta)
    d = ia.json_da_resposta(resposta)
    if parte == "momentos":
        assert d["momentos"] and all("inicio" in m and "fim" in m for m in d["momentos"]), "faltam os momentos"
        (pasta / "analise.json").write_text(json.dumps(d, ensure_ascii=False, indent=1))
    elif parte == "conteudo":
        assert d["estudo"] and d["frases"], "faltam o estudo ou as frases"
        (pasta / "conteudo.json").write_text(json.dumps(d, ensure_ascii=False, indent=1))
    elif parte == "biblia":
        assert isinstance(d.get("passagens"), list), "falta a lista de passagens"
        (pasta / "biblia.json").write_text(json.dumps(d, ensure_ascii=False, indent=1))
    else:
        a = json.loads((pasta / "analise.json").read_text())
        assert len(d["viral"]) == len(a["momentos"]), "a quantidade de cortes não bate"
        for m, v in zip(a["momentos"], d["viral"]):
            v.pop("n", None)
            m["viral"] = v
        (pasta / "analise.json").write_text(json.dumps(a, ensure_ascii=False, indent=1))
    (pasta / f"pedido_{parte}.txt").unlink(missing_ok=True)


def gerar_pdf(pasta, destino):
    """PDF com os cortes sugeridos (feito na hora, quando a pessoa clica em Baixar PDF)."""
    video = (pasta / "video.txt").read_text().strip() if (pasta / "video.txt").exists() else pasta.name
    pdf = Path(destino) / f"{Path(video).stem.strip()} - cortes sugeridos.pdf"
    subprocess.run([sys.executable, str(SIS / "gerar_pdf.py"), str(pasta / "analise.json"), str(pdf)],
                   check=True, capture_output=True)
    return pdf


def main(pasta, parte, nome=None):
    texto = montar(pasta, parte, nome)
    for tentativa in (1, 2):
        try:
            aplicar(pasta, parte, ia.perguntar(texto, pasta))
            return "pronto"
        except ia.Colar:
            (pasta / f"pedido_{parte}.txt").write_text(texto)
            return "colar"
        except Exception as e:  # resposta fora do formato ou IA fora do ar: tenta mais uma vez
            with open(SIS / "log.txt", "a") as f:
                f.write(time.strftime("%d/%m %H:%M ") + f"{parte} {pasta.name} tentativa {tentativa}: {e}\n")
    return "erro"


if __name__ == "__main__":
    comum.aplicar_prioridade()
    pasta, parte = Path(sys.argv[1]), sys.argv[2]
    nome = Path(sys.argv[3]).stem.strip() if len(sys.argv) > 3 else None
    status = pasta / f"{parte}_status"
    status.write_text("gerando")
    r = main(pasta, parte, nome)
    status.write_text(r)
    sys.exit({"pronto": 0, "colar": 3}.get(r, 1))
