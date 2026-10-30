"""Interface do app: editor com o vídeo, a transcrição clicável e os momentos por tema.

Roda em http://127.0.0.1:47615 (o app abre numa janela do Chrome).
  GET  /                       interface (interface.html)
  GET  /api/projetos           lista dos vídeos já enviados
  GET  /api/projeto/<id>       frases da transcrição, análise e andamento
  GET  /video/<id>             o vídeo original (com Range, para poder pular no tempo)
  POST /api/novo               abre a janela "escolher vídeo" e começa o processamento
  POST /api/localizar/<id>     aponta de novo um vídeo que mudou de lugar
  GET  /api/pdf/<id>           gera e baixa o PDF com os cortes sugeridos
  POST /api/drive              {"links": [...], "projeto"?} traz vídeos do Google Drive ou YouTube
  GET  /api/downloads          andamento dos downloads do Drive
  GET  /api/canais, /api/canal/<id>   análises de canal do YouTube
  POST /api/canal              {"youtube": link, "extra": texto} analisa o canal da igreja
  GET  /api/fonte/<id>         de onde dá para exportar cortes (original, Drive, YouTube ou só a versão leve)
  POST /api/exportar           exporta um corte já cortado (exportar.py); GET /api/exportacoes mostra o andamento
  POST /api/revelar            mostra o arquivo exportado no Finder
  GET/POST /api/ia             IA das análises: qual está conectada / conectar e testar outra
  GET  /api/pedido/<tipo>/<id>/<parte>  texto para levar a uma IA de conta grátis (copiar e colar)
  POST /api/colar              {"tipo": "pregacao"|"canal", "id", "parte", "texto"}: resposta colada pela pessoa
  GET  /api/atualizacao        versão atual e se há versão nova no GitHub (e se este Mac pode publicar)
  POST /api/atualizar          baixa e aplica a versão nova e reinicia o servidor
  POST /api/publicar           {"notas"} publica uma versão nova no GitHub (só no Mac de quem criou)
  POST /api/pacote             monta o SermonCut.zip (instalador) na Mesa
  GET/POST /api/ajustes        preferências da pessoa (abas visíveis, dados do "Sobre")
  POST /api/gerar/<id>/<parte> gera de novo "conteudo" (estudo, devocional, frases) ou "viral"
"""
import json, mimetypes, os, re, subprocess, sys, tempfile, time, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import comum

SIS = Path.home() / "CortesAutomacao" / ".sistema"
TRANS = SIS / "transcricoes"
DOWN = SIS / "downloads"
CANAIS = SIS / "canais"
EXPORT = SIS / "exportacoes"
AJUSTES = SIS / "ajustes.json"
PADRAO = {"abas": {"momentos": True, "transcricao": True, "estudo": True, "biblia": True, "frases": True, "viral": True},
          "recursos": {"canal": True, "pdf": True, "exportar": True},
          "desempenho": {"modo": "equilibrado"},
          "celular": {"ativo": False, "pin": ""},
          "sobre": {"nome": "", "texto": "", "instagram": "", "contato": "", "link": ""}}


def ajustes():
    salvo = json.loads(AJUSTES.read_text()) if AJUSTES.exists() else {}
    return {k: {**v, **salvo.get(k, {})} for k, v in PADRAO.items()}
PORTA = 47615
LINHA = re.compile(r"\[(\d+):(\d\d):(\d\d)\]\s*(.*)")


def ler(p, padrao=""):
    return p.read_text().strip() if p.exists() else padrao


def pasta_de(pid):
    p = (TRANS / pid).resolve()
    if p.parent != TRANS.resolve() or not p.is_dir():
        raise FileNotFoundError(pid)
    return p


escolher_video = comum.escolher_video


def resumo(p):
    analise = p / "analise.json"
    video = ler(p / "video.txt")
    titulo = p.name.replace("_", " ")
    if analise.exists():
        titulo = json.loads(analise.read_text()).get("titulo") or titulo
    return {"id": p.name, "titulo": titulo, "status": ler(p / "status", "na fila"),
            "video": video, "tem_video": bool(video) and Path(video).exists(),
            "quando": p.stat().st_mtime}


def projeto(p):
    frases = []
    for linha in ler(p / "transcricao.txt").splitlines():
        m = LINHA.match(linha)
        if m:
            h, mi, s, t = m.groups()
            frases.append({"s": int(h) * 3600 + int(mi) * 60 + int(s), "t": t})
    d = resumo(p)
    d["frases"] = frases
    d["duracao"] = float(ler(p / "duracao", "0") or 0)
    d["analise"] = json.loads((p / "analise.json").read_text()) if (p / "analise.json").exists() else None
    d["conteudo"] = json.loads((p / "conteudo.json").read_text()) if (p / "conteudo.json").exists() else None
    d["conteudo_status"] = ler(p / "conteudo_status")
    d["biblia"] = json.loads((p / "biblia.json").read_text()) if (p / "biblia.json").exists() else None
    d["biblia_status"] = ler(p / "biblia_status")
    d["viral_status"] = ler(p / "viral_status")
    d["momentos_status"] = ler(p / "momentos_status")
    d["tem_pdf"] = Path(ler(p / "pdf.txt")).is_file() if ler(p / "pdf.txt") else False
    return d


PORTAO = """<!doctype html><html lang="pt-br"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>SermonCut</title>
<link rel="manifest" href="/manifest.json"><link rel="apple-touch-icon" href="/icone.png"><meta name="theme-color" content="#111115">
<style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#111115;color:#ececf1;font:16px -apple-system,Segoe UI,Arial,sans-serif}
.c{width:min(340px,88vw);text-align:center}img{width:84px;border-radius:20px}h1{font-size:22px;margin:14px 0 6px}
p{color:#9a9aa8;font-size:14px;line-height:1.5}input{width:100%;box-sizing:border-box;font-size:28px;letter-spacing:.3em;text-align:center;
padding:12px;border-radius:12px;border:1px solid #2c2c36;background:#1a1a20;color:#fff;margin:10px 0}
button{width:100%;padding:14px;border:0;border-radius:12px;background:#ff6a13;color:#fff;font-size:16px;font-weight:700}
#e{color:#ff7b81;min-height:20px;font-size:14px}</style></head><body><div class="c"><img src="/icone.png" alt="">
<h1>SermonCut</h1><p>Digite o código de acesso que aparece no computador, em ⚙️ › Celular.</p>
<input id="pin" inputmode="numeric" maxlength="6" autocomplete="one-time-code" autofocus><div id="e"></div><button id="b">Entrar</button></div>
<script>const b=document.getElementById("b"),i=document.getElementById("pin");
async function entrar(){b.disabled=true;const r=await fetch("/api/entrar",{method:"POST",body:JSON.stringify({pin:i.value})}).then(r=>r.json());
if(r.ok)location.reload();else{document.getElementById("e").textContent="Código errado. Confira no computador.";b.disabled=false;i.select()}}
b.onclick=entrar;i.onkeydown=e=>e.key==="Enter"&&entrar();</script></body></html>"""
MANIFESTO = {"name": "SermonCut", "short_name": "SermonCut", "start_url": "/", "display": "standalone",
             "background_color": "#111115", "theme_color": "#111115",
             "icons": [{"src": "/icone.png", "sizes": "1024x1024", "type": "image/png"}]}
# o que só faz sentido no próprio computador (abre janelas lá, mexe na conta do GitHub...)
SO_NO_COMPUTADOR = ("/api/novo", "/api/localizar/", "/api/revelar", "/api/ia/login_claude", "/api/publicar",
                    "/api/pacote", "/api/celular", "/api/atualizar")


def enderecos():
    """Endereços deste computador na rede Wi-Fi (para abrir no celular)."""
    import socket
    ips = set()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sk:
            sk.connect(("8.8.8.8", 80))  # não envia nada: só descobre qual placa de rede sai para a internet
            ips.add(sk.getsockname()[0])
    except OSError:
        pass
    return [f"http://{ip}:{PORTA}" for ip in sorted(ips) if not ip.startswith("127.")]


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def remoto(self):
        return self.client_address[0] not in ("127.0.0.1", "::1", "::ffff:127.0.0.1")

    def liberado(self):
        """No próprio computador sempre; no celular só com o código de acesso (guardado num cookie)."""
        if not self.remoto():
            return True
        cel = ajustes()["celular"]
        if not cel["ativo"] or not cel["pin"]:
            return False
        cookies = dict(c.strip().split("=", 1) for c in self.headers.get("Cookie", "").split(";") if "=" in c)
        return cookies.get("sc_pin") == cel["pin"]

    def portao(self):
        if self.path.startswith(("/api/", "/video/")):
            return self.json({"erro": "digite o código de acesso"}, 401)
        b = PORTAO.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        try:
            if self.path == "/manifest.json":
                return self.json(MANIFESTO)
            if self.path == "/icone.png":
                b = (SIS / "icone.png").read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(b)))
                self.send_header("Cache-Control", "max-age=86400")
                self.end_headers()
                return self.wfile.write(b)
            if not self.liberado():
                return self.portao()
            if self.path in ("/", "/index.html") or self.path.startswith("/?"):
                b = (SIS / "interface.html").read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)
            elif self.path == "/api/projetos":
                TRANS.mkdir(parents=True, exist_ok=True)
                ps = [resumo(p) for p in TRANS.iterdir() if p.is_dir()]
                self.json(sorted(ps, key=lambda x: -x["quando"]))
            elif self.path == "/api/downloads":
                DOWN.mkdir(parents=True, exist_ok=True)
                ds = [json.loads(p.read_text()) for p in DOWN.glob("*.json")]
                self.json([d for d in ds if time.time() - d.get("quando", 0) < 6 * 3600])
            elif self.path.startswith("/api/projeto/"):
                self.json(projeto(pasta_de(self.path.split("/")[3])))
            elif self.path.startswith("/api/drive_pasta?"):
                import baixar_drive
                link = urllib.parse.parse_qs(self.path.split("?", 1)[1]).get("link", [""])[0]
                try:
                    self.json(baixar_drive.listar_pasta(baixar_drive.id_do_link(link)))
                except Exception:
                    self.json({"erro": "não consegui abrir a pasta: deixe como \"Qualquer pessoa com o link\""})
            elif self.path.startswith("/api/fonte/"):
                import exportar
                tipos = [t for t, _ in exportar.fonte(pasta_de(self.path.split("/")[3]).name)]
                self.json({"fontes": tipos})
            elif self.path == "/api/exportacoes":
                EXPORT.mkdir(parents=True, exist_ok=True)
                js = [json.loads(p.read_text()) for p in EXPORT.glob("*.json")]
                self.json(sorted([j for j in js if time.time() - j.get("quando", 0) < 6 * 3600], key=lambda j: -j["quando"]))
            elif self.path == "/api/ajustes":
                self.json(ajustes())
            elif self.path.startswith("/api/atualizacao"):
                import atualizar
                info = atualizar.verificar(forcar="forcar" in self.path)
                gh = comum.LOCAL / f"gh{comum.EXE}"
                info["pode_publicar"] = (SIS / "publicar.sh").exists() and gh.exists() and \
                    subprocess.run([str(gh), "auth", "status"], capture_output=True).returncode == 0
                self.json(info)
            elif self.path == "/api/ia":
                import ia
                self.json(ia.publico())
            elif self.path.startswith("/api/pedido/"):
                _, _, _, tipo, pid, parte = self.path.split("/")[:6]
                arq = (CANAIS / pid / "pedido.txt") if tipo == "canal" else (pasta_de(pid) / f"pedido_{parte}.txt")
                if not arq.resolve().is_relative_to(SIS) or not arq.exists():
                    raise FileNotFoundError
                self.json({"texto": arq.read_text()})
            elif self.path == "/api/sistema":
                self.json({"so": "windows" if comum.WINDOWS else "mac", "remoto": self.remoto()})
            elif self.path == "/api/celular":
                if self.remoto():
                    return self.json({"erro": "só no computador"}, 403)
                cel = ajustes()["celular"]
                self.json({**cel, "enderecos": enderecos()})
            elif self.path.startswith("/api/exportado/"):
                # baixa um corte exportado (útil no celular)
                j = json.loads((EXPORT / f"{self.path.split('/')[3]}.json").read_text())
                arq = Path(j.get("arquivo", ""))
                if j.get("status") != "pronto" or arq.parent.name != "CORTES EXPORTADOS" or not arq.is_file():
                    raise FileNotFoundError
                self.send_response(200)
                self.send_header("Content-Type", "video/mp4")
                self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{urllib.parse.quote(arq.name)}")
                self.send_header("Content-Length", str(arq.stat().st_size))
                self.end_headers()
                with open(arq, "rb") as f:
                    while bloco := f.read(1 << 20):
                        self.wfile.write(bloco)
            elif self.path == "/api/config":
                self.json({"tem_chave": (SIS / "youtube_chave.txt").exists()})
            elif self.path == "/api/canais":
                CANAIS.mkdir(parents=True, exist_ok=True)
                cs = []
                for p in CANAIS.iterdir():
                    if p.is_dir():
                        info = json.loads((p / "canal.json").read_text()) if (p / "canal.json").exists() else {}
                        cs.append({"id": p.name, "nome": info.get("nome") or p.name, "status": ler(p / "status"),
                                   "quando": p.stat().st_mtime})
                self.json(sorted(cs, key=lambda x: -x["quando"]))
            elif self.path.startswith("/api/canal/"):
                p = (CANAIS / self.path.split("/")[3]).resolve()
                if p.parent != CANAIS.resolve() or not p.is_dir():
                    raise FileNotFoundError
                carregar = lambda n: json.loads((p / n).read_text()) if (p / n).exists() else None
                self.json({"id": p.name, "status": ler(p / "status"), "canal": carregar("canal.json"),
                           "analise": carregar("analise.json")})
            elif self.path.startswith("/api/pdf/"):
                # gera o PDF dos cortes na hora e entrega como download
                import gerar
                p = pasta_de(self.path.split("/")[3])
                with tempfile.TemporaryDirectory() as tmp:
                    pdf = gerar.gerar_pdf(p, destino=Path(tmp))
                    b = pdf.read_bytes()
                nome = urllib.parse.quote(pdf.name)
                self.send_response(200)
                self.send_header("Content-Type", "application/pdf")
                self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{nome}")
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)
            elif self.path.startswith("/video/"):
                self.video(Path(ler(pasta_de(self.path.split("/")[2]) / "video.txt")))
            else:
                self.send_error(404)
        except (FileNotFoundError, IsADirectoryError):
            self.send_error(404)
        except (BrokenPipeError, ConnectionResetError):
            pass  # o player cancelou o pedaço que tinha pedido

    def video(self, path):
        tam = path.stat().st_size
        ini, fim = 0, tam - 1
        m = re.match(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
        if m:
            if m.group(1):
                ini = int(m.group(1))
                fim = int(m.group(2)) if m.group(2) else tam - 1
            else:  # "bytes=-N": os últimos N bytes
                ini = tam - int(m.group(2))
        fim = min(fim, tam - 1)
        self.send_response(206 if m else 200)
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "video/mp4")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(fim - ini + 1))
        if m:
            self.send_header("Content-Range", f"bytes {ini}-{fim}/{tam}")
        self.end_headers()
        with open(path, "rb") as f:
            f.seek(ini)
            falta = fim - ini + 1
            while falta > 0:
                bloco = f.read(min(1 << 20, falta))
                if not bloco:
                    break
                self.wfile.write(bloco)
                falta -= len(bloco)

    def do_POST(self):
        try:
            partes = self.path.split("/")
            if self.path == "/api/entrar":
                corpo = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                cel = ajustes()["celular"]
                if cel["ativo"] and cel["pin"] and str(corpo.get("pin", "")).strip() == cel["pin"]:
                    b = b'{"ok": true}'
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Set-Cookie", f"sc_pin={cel['pin']}; Max-Age=31536000; Path=/; SameSite=Lax; HttpOnly")
                    self.send_header("Content-Length", str(len(b)))
                    self.end_headers()
                    return self.wfile.write(b)
                time.sleep(1.5)  # atrasa quem tenta adivinhar
                return self.json({"ok": False})
            if not self.liberado():
                return self.json({"erro": "digite o código de acesso"}, 401)
            if self.remoto() and self.path.startswith(SO_NO_COMPUTADOR):
                return self.json({"erro": "isso só dá para fazer no computador"}, 403)
            if self.path == "/api/celular":
                import random
                corpo = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                aj = ajustes()
                aj["celular"]["ativo"] = bool(corpo.get("ativo"))
                if corpo.get("novo_pin") or not aj["celular"]["pin"]:
                    aj["celular"]["pin"] = f"{random.SystemRandom().randrange(10 ** 6):06d}"
                AJUSTES.write_text(json.dumps(aj, ensure_ascii=False, indent=1))
                self.json({**aj["celular"], "enderecos": enderecos()})
                comum.python_script("abrir.py", "--so-servidor")  # religa ouvindo (ou não) a rede Wi-Fi
                return
            if self.path == "/api/novo":
                v = escolher_video("Escolha o vídeo da pregação:")
                if v:
                    comum.python_script("processar.py", v)
                self.json({"video": v})
            elif self.path == "/api/drive":
                corpo = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                links = [l.strip() for l in corpo.get("links", []) if l.strip()]
                projeto = [pasta_de(corpo["projeto"]).name] if corpo.get("projeto") else []
                for l in links:
                    comum.python_script("baixar_drive.py", l, *projeto)
                self.json({"links": len(links)})
            elif self.path == "/api/exportar":
                corpo = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                EXPORT.mkdir(parents=True, exist_ok=True)
                pedido = {"id": str(int(time.time() * 1000)), "projeto": pasta_de(corpo["projeto"]).name,
                          "inicio": float(corpo["inicio"]), "fim": float(corpo["fim"]), "nome": str(corpo.get("nome", "corte")),
                          "altura": int(corpo.get("altura") or 0), "fps": int(corpo.get("fps") or 0),
                          "mbps": float(corpo.get("mbps") or 0)}
                arq = EXPORT / f"{pedido['id']}.pedido"
                arq.write_text(json.dumps(pedido, ensure_ascii=False))
                (EXPORT / f"{pedido['id']}.json").write_text(json.dumps(dict(pedido, status="na fila", progresso=0,
                                                                              quando=time.time()), ensure_ascii=False))
                comum.python_script("exportar.py", arq)
                self.json({"id": pedido["id"]})
            elif self.path == "/api/ajustes":
                corpo = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                novo = {k: {c: corpo.get(k, {}).get(c, v) for c, v in PADRAO[k].items()} for k in PADRAO}
                AJUSTES.write_text(json.dumps(novo, ensure_ascii=False, indent=1))
                self.json(novo)
            elif self.path == "/api/ia":
                import ia
                corpo = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                atual = ia.config()
                cfg = {"provedor": corpo.get("provedor", ""), "modelo": corpo.get("modelo", "").strip(),
                       "site": corpo.get("site", "chatgpt"),
                       # chave em branco = manter a que já estava salva para o mesmo provedor
                       "chave": corpo.get("chave", "").strip() or (atual.get("chave", "") if atual.get("provedor") == corpo.get("provedor") else "")}
                if cfg["provedor"] not in ia.PROVEDORES:
                    return self.json({"ok": False, "msg": "escolha uma IA"})
                if ia.PROVEDORES[cfg["provedor"]]["chave"] and not cfg["chave"]:
                    return self.json({"ok": False, "msg": "cole a chave da IA"})
                ok, msg = ia.testar(cfg)
                if ok:
                    ia.salvar(cfg)
                self.json({"ok": ok, "msg": msg, "ia": ia.publico()})
            elif self.path == "/api/ia/login_claude":
                # abre um terminal com o Claude para a pessoa entrar na conta (assinatura Pro)
                comum.abrir_terminal(f'"{comum.claude()}"', SIS)
                self.json({"ok": True})
            elif self.path == "/api/colar":
                import gerar, canal
                corpo = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                try:
                    if corpo.get("tipo") == "canal":
                        p = (CANAIS / corpo["id"]).resolve()
                        if p.parent != CANAIS.resolve():
                            raise FileNotFoundError
                        canal.aplicar(p, corpo.get("texto", ""))
                    else:
                        p, parte = pasta_de(corpo["id"]), corpo.get("parte")
                        if parte not in ("momentos", "conteudo", "viral", "biblia"):
                            raise ValueError("parte inválida")
                        gerar.aplicar(p, parte, corpo.get("texto", ""))
                        (p / f"{parte}_status").write_text("pronto")
                        if parte == "momentos":
                            (p / "status").write_text("relatorio_pronto")
                    self.json({"ok": True})
                except (ValueError, KeyError, AssertionError, json.JSONDecodeError) as e:
                    self.json({"ok": False, "msg": "a resposta colada não está completa ou não é a da IA: "
                               "copie a resposta inteira (do primeiro { ao último })" + (f" — {e}" if isinstance(e, AssertionError) and str(e) else "")})
            elif self.path == "/api/atualizar":
                import atualizar
                r = atualizar.aplicar()
                self.json(r)
                if r.get("atualizado"):  # reinicia com o código novo (a página recarrega sozinha)
                    comum.python_script("abrir.py", "--so-servidor")
            elif self.path == "/api/publicar":
                corpo = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                r = subprocess.run([str(SIS / "publicar.sh"), corpo.get("notas", "").strip() or "Melhorias e correções."],
                                   capture_output=True, text=True, timeout=1800)
                saida = (r.stdout + r.stderr).strip()
                self.json({"ok": r.returncode == 0, "url": r.stdout.strip().splitlines()[-1] if r.returncode == 0 else "",
                           "msg": saida[-400:]})
            elif self.path == "/api/pacote":
                r = subprocess.run([str(SIS / "gerar_pacote.sh")], capture_output=True, text=True)
                zipf = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
                if zipf and Path(zipf).exists():
                    comum.revelar(zipf)
                self.json({"zip": zipf})
            elif self.path == "/api/revelar":
                corpo = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                arq = Path(corpo.get("arquivo", ""))
                if arq.is_file() and arq.parent.name == "CORTES EXPORTADOS":
                    comum.revelar(arq)
                self.json({"ok": True})
            elif self.path == "/api/canal":
                corpo = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                CANAIS.mkdir(parents=True, exist_ok=True)
                extra = CANAIS / f".extra_{int(time.time())}.txt"
                extra.write_text(corpo.get("extra", ""))
                if corpo.get("chave", "").strip():
                    (SIS / "youtube_chave.txt").write_text(corpo["chave"].strip())
                comum.python_script("canal.py", corpo.get("youtube", ""), extra)
                self.json({"ok": True})
            elif self.path.startswith("/api/gerar/") and len(partes) > 4 and partes[4] in ("conteudo", "viral", "biblia"):
                p = pasta_de(partes[3])
                (p / f"{partes[4]}_status").write_text("gerando")
                comum.python_script("gerar.py", p, partes[4])
                self.json({"ok": True})
            elif self.path.startswith("/api/localizar/"):
                p = pasta_de(partes[3])
                v = escolher_video("Onde está este vídeo agora?")
                if v:
                    (p / "video.txt").write_text(v)
                self.json({"video": v})
            else:
                self.send_error(404)
        except FileNotFoundError:
            self.send_error(404)


if __name__ == "__main__":
    (SIS / ".servidor.pid").write_text(str(os.getpid()))
    # com o acesso pelo celular ligado, também atende a rede Wi-Fi (protegido pelo código de acesso)
    ThreadingHTTPServer(("0.0.0.0" if ajustes()["celular"]["ativo"] else "127.0.0.1", PORTA), H).serve_forever()
