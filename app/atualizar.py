"""Atualização automática do SermonCut pelo GitHub Releases.

O endereço do projeto fica em .sistema/atualizacao.json ({"repo": "dono/sermoncut"}).
Cada versão publicada tem o arquivo atualizacao.zip: só os arquivos do app, sem vídeos, transcrições,
chaves ou configurações da pessoa.
"""
import json, os, shutil, subprocess, tempfile, time, urllib.request, zipfile
from pathlib import Path

SIS = Path.home() / "CortesAutomacao" / ".sistema"
CACHE = SIS / ".atualizacao_cache.json"
UV = Path.home() / ".local" / "bin" / "uv"
# o que uma atualização pode trocar (nunca ajustes.json, ia.json, chaves ou pastas de dados)
EXTENSOES = (".py", ".sh", ".html", ".md", ".txt", ".applescript", ".icns", ".command")
NOMES = ("VERSAO", "atualizacao.json")


def repo():
    try:
        return json.loads((SIS / "atualizacao.json").read_text())["repo"]
    except Exception:
        return ""


def versao_atual():
    return (SIS / "VERSAO").read_text().strip() if (SIS / "VERSAO").exists() else "0"


def _num(v):
    return tuple(int(x) for x in v.lstrip("v").split(".") if x.isdigit())


def verificar(forcar=False):
    atual = versao_atual()
    info = {"atual": atual, "nova": False, "repo": repo()}
    if not info["repo"]:
        return info
    if not forcar and CACHE.exists():
        c = json.loads(CACHE.read_text())
        if time.time() - c.get("quando", 0) < 6 * 3600 and c.get("atual") == atual:
            return c
    try:
        req = urllib.request.Request(f"https://api.github.com/repos/{info['repo']}/releases/latest",
                                     headers={"User-Agent": "SermonCut", "Accept": "application/vnd.github+json"})
        r = json.loads(urllib.request.urlopen(req, timeout=15).read())
        zip_url = next((a["browser_download_url"] for a in r.get("assets", []) if a["name"] == "atualizacao.zip"), "")
        versao = r.get("tag_name", "").lstrip("v")
        info.update(versao=versao, notas=r.get("body") or "", zip=zip_url,
                    nova=bool(zip_url) and _num(versao) > _num(atual))
    except Exception as e:
        info["erro"] = str(e)
    info["quando"] = time.time()
    CACHE.write_text(json.dumps(info, ensure_ascii=False))
    return info


def aplicar():
    info = verificar(forcar=True)
    if not info.get("nova"):
        return info
    with tempfile.TemporaryDirectory() as tmp:
        arq = Path(tmp) / "atualizacao.zip"
        req = urllib.request.Request(info["zip"], headers={"User-Agent": "SermonCut"})
        with urllib.request.urlopen(req, timeout=120) as r, open(arq, "wb") as f:
            shutil.copyfileobj(r, f)
        with zipfile.ZipFile(arq) as z:
            for nome in z.namelist():
                base = Path(nome).name
                # só arquivos soltos e conhecidos: nada de pastas, caminhos ou arquivos da pessoa
                if nome != base or not (base.endswith(EXTENSOES) or base in NOMES):
                    continue
                destino = SIS / base
                destino.write_bytes(z.read(nome))
                if base.endswith((".sh", ".command")):
                    os.chmod(destino, 0o755)
    req_txt = SIS / "requisitos.txt"
    if UV.exists() and req_txt.exists() and (SIS / "venv" / "bin" / "python").exists():
        subprocess.run([str(UV), "pip", "install", "-q", "--python", str(SIS / "venv" / "bin" / "python"),
                        "-r", str(req_txt)], capture_output=True, timeout=900)
    CACHE.unlink(missing_ok=True)
    return {"atualizado": True, "versao": versao_atual()}


if __name__ == "__main__":
    print(json.dumps(verificar(forcar=True), ensure_ascii=False, indent=1))
