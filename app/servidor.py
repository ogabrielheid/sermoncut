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

SIS = Path.home() / "CortesAutomacao" / ".sistema"
TRANS = SIS / "transcricoes"
DOWN = SIS / "downloads"
CANAIS = SIS / "canais"
EXPORT = SIS / "exportacoes"
AJUSTES = SIS / "ajustes.json"
PADRAO = {"abas": {"momentos": True, "transcricao": True, "estudo": True, "biblia": True, "frases": True, "viral": True},
          "recursos": {"canal": True, "pdf": True, "exportar": True},
          "desempenho": {"modo": "equilibrado"},
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


def rodar(*args):
    subprocess.Popen(["nohup", *map(str, args)], start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def escolher_video(prompt):
    r = subprocess.run(["osascript", "-e", "tell me to activate", "-e",
                        f'POSIX path of (choose file with prompt "{prompt}" of type {{"public.movie"}})'],
                       capture_output=True, text=True)
    return r.stdout.strip() or None


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


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        try:
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
                gh = Path.home() / ".local" / "bin" / "gh"
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
            if self.path == "/api/novo":
                v = escolher_video("Escolha o vídeo da pregação:")
                if v:
                    rodar(SIS / "processar.sh", v)
                self.json({"video": v})
            elif self.path == "/api/drive":
                corpo = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                links = [l.strip() for l in corpo.get("links", []) if l.strip()]
                projeto = [pasta_de(corpo["projeto"]).name] if corpo.get("projeto") else []
                for l in links:
                    rodar(sys.executable, SIS / "baixar_drive.py", l, *projeto)
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
                rodar(sys.executable, SIS / "exportar.py", arq)
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
                # abre o Terminal com o Claude para a pessoa entrar na conta (assinatura Pro)
                cmd = SIS / "login_claude.command"
                cmd.write_text(f'#!/bin/bash\ncd "{SIS}"\necho "Entre na sua conta Claude. Quando terminar, digite /exit e aperte Enter."\n'
                               f'"$HOME/.local/bin/claude"\n')
                cmd.chmod(0o755)
                subprocess.run(["open", str(cmd)])
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
                    subprocess.Popen(["bash", "-c", f"sleep 1; kill {os.getpid()}; sleep 1; "
                                      f"nohup '{sys.executable}' '{SIS / 'servidor.py'}' >> '{SIS / 'log.txt'}' 2>&1 &"],
                                     start_new_session=True)
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
                    subprocess.run(["open", "-R", zipf])
                self.json({"zip": zipf})
            elif self.path == "/api/revelar":
                corpo = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                arq = Path(corpo.get("arquivo", ""))
                if arq.is_file() and arq.parent.name == "CORTES EXPORTADOS":
                    subprocess.run(["open", "-R", str(arq)])
                self.json({"ok": True})
            elif self.path == "/api/canal":
                corpo = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                CANAIS.mkdir(parents=True, exist_ok=True)
                extra = CANAIS / f".extra_{int(time.time())}.txt"
                extra.write_text(corpo.get("extra", ""))
                if corpo.get("chave", "").strip():
                    (SIS / "youtube_chave.txt").write_text(corpo["chave"].strip())
                rodar(sys.executable, SIS / "canal.py", corpo.get("youtube", ""), extra)
                self.json({"ok": True})
            elif self.path.startswith("/api/gerar/") and len(partes) > 4 and partes[4] in ("conteudo", "viral", "biblia"):
                p = pasta_de(partes[3])
                (p / f"{partes[4]}_status").write_text("gerando")
                rodar(sys.executable, SIS / "gerar.py", p, partes[4])
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
    ThreadingHTTPServer(("127.0.0.1", PORTA), H).serve_forever()
