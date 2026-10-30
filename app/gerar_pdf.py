"""Gera o PDF com os cortes sugeridos de uma pregação.

Uso: gerar_pdf.py analise.json saida.pdf

analise.json (escrito pela tarefa do Claude):
{
  "titulo": "Culto de domingo – Alex Kendrick", "pregador": "...", "data": "25/10/2026",
  "duracao": "1:18:33", "resumo": "2-3 frases sobre a mensagem",
  "momentos": [{"inicio": "06:39", "fim": "07:22", "titulo": "...", "gancho": "...",
                "porque": "...", "tema": "...", "potencial": 1-5, "trecho": "..."}],
  "observacoes": "opcional"
}
"""
import html, json, subprocess, sys, tempfile
from pathlib import Path

import comum

CHROME = comum.navegador()
a = json.load(open(sys.argv[1]))
out = Path(sys.argv[2])
e = html.escape


def seg(t):
    p = [int(x) for x in t.split(":")]
    return sum(v * 60 ** i for i, v in enumerate(reversed(p)))


cards = []
for i, m in enumerate(a["momentos"], 1):
    dur = seg(m["fim"]) - seg(m["inicio"])
    estrelas = "★" * int(m.get("potencial", 3)) + "☆" * (5 - int(m.get("potencial", 3)))
    cards.append(f"""
    <section class="card">
      <div class="top">
        <span class="num">{i:02d}</span>
        <div class="head">
          <h2>{e(m['titulo'])}</h2>
          <div class="meta"><b>{e(m['inicio'])} → {e(m['fim'])}</b> · {dur // 60}min{dur % 60:02d}s no vídeo
            · <span class="tag">{e(m.get('tema', ''))}</span> · <span class="stars">{estrelas}</span></div>
        </div>
      </div>
      <p class="hook">“{e(m['gancho'])}”</p>
      <p class="why"><b>Por que funciona:</b> {e(m['porque'])}</p>
      {f'<p class="trecho">{e(m["trecho"])}</p>' if m.get('trecho') else ''}
    </section>""")

doc = f"""<!doctype html><html lang="pt-br"><head><meta charset="utf-8">
<style>
@page {{ size: A4; margin: 16mm 14mm; }}
* {{ box-sizing: border-box; }}
body {{ font-family: -apple-system, "Helvetica Neue", Arial, sans-serif; color: #1b1b1f; font-size: 10.5pt; margin: 0; }}
header {{ border-bottom: 3px solid #f26a12; padding-bottom: 10px; margin-bottom: 14px; }}
.kicker {{ color: #f26a12; font-weight: 800; letter-spacing: .08em; font-size: 8.5pt; text-transform: uppercase; }}
h1 {{ font-size: 21pt; margin: 4px 0 6px; letter-spacing: -.02em; }}
.info {{ color: #555; font-size: 9.5pt; }}
.resumo {{ background: #f4f4f6; border-radius: 8px; padding: 10px 12px; margin: 0 0 14px; line-height: 1.45; }}
.how {{ font-size: 9pt; color: #555; margin: 0 0 12px; }}
.card {{ border: 1px solid #ddd; border-radius: 10px; padding: 10px 12px; margin-bottom: 10px; break-inside: avoid; }}
.top {{ display: flex; gap: 10px; align-items: flex-start; }}
.num {{ font-size: 18pt; font-weight: 800; color: #f26a12; line-height: 1; min-width: 34px; }}
.head {{ flex: 1; }}
h2 {{ font-size: 12.5pt; margin: 0 0 3px; letter-spacing: -.01em; }}
.meta {{ color: #555; font-size: 9pt; }}
.tag {{ background: #fff0e3; color: #b8520c; border-radius: 4px; padding: 0 5px; }}
.stars {{ color: #f26a12; letter-spacing: 1px; }}
.check {{ font-size: 20pt; line-height: 1; color: #999; }}
.hook {{ font-size: 11.5pt; font-weight: 700; margin: 8px 0 4px; }}
.why {{ margin: 0 0 4px; line-height: 1.4; }}
.trecho {{ color: #666; font-size: 9pt; font-style: italic; margin: 0; line-height: 1.4; }}
footer {{ margin-top: 12px; font-size: 9pt; color: #555; border-top: 1px solid #ddd; padding-top: 8px; }}
</style></head><body>
<header>
  <div class="kicker">SermonCut · cortes sugeridos</div>
  <h1>{e(a['titulo'])}</h1>
  <div class="info">{e(a.get('pregador', ''))} · {e(a.get('data', ''))} · vídeo de {e(a.get('duracao', ''))}
   · {len(a['momentos'])} sugestões</div>
</header>
<p class="resumo"><b>A mensagem:</b> {e(a.get('resumo', ''))}</p>
{''.join(cards)}
{f'<footer><b>Observações:</b> {e(a["observacoes"])}</footer>' if a.get('observacoes') else ''}
</body></html>"""

with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
    f.write(doc)
subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                f"--print-to-pdf={out}", Path(f.name).as_uri()], check=True,
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
print(out)
