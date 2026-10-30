"""Fala com a IA que a pessoa escolheu para as análises.

Configuração em .sistema/ia.json (fica só neste Mac, nunca vai no pacote de instalação):
  {"provedor": "...", "chave": "...", "modelo": "...", "site": "..."}
Provedores:
  claude_pro   Claude Code com a assinatura (Pro ou maior), automático
  claude_api   API da Anthropic (chave paga por uso)
  gemini       Gemini pelo Google AI Studio (chave com nível gratuito)
  openai       ChatGPT pela API da OpenAI (chave paga por uso)
  deepseek     API da DeepSeek (chave paga por uso, barata)
  manual       conta grátis de qualquer chat (ChatGPT, Gemini, Claude, DeepSeek): copiar e colar
"""
import json, os, subprocess, urllib.error, urllib.request
from pathlib import Path

SIS = Path.home() / "CortesAutomacao" / ".sistema"
CONFIG = SIS / "ia.json"
CLAUDE = Path.home() / ".local" / "bin" / "claude"

PROVEDORES = {
    "claude_pro": {"nome": "Claude (assinatura Pro)", "chave": False, "modelo": ""},
    "claude_api": {"nome": "Claude (chave de API)", "chave": True, "modelo": "claude-sonnet-5-5"},
    "gemini": {"nome": "Gemini · Google AI Studio", "chave": True, "modelo": "gemini-2.5-flash"},
    "openai": {"nome": "ChatGPT (chave de API)", "chave": True, "modelo": "gpt-4.1-mini"},
    "deepseek": {"nome": "DeepSeek (chave de API)", "chave": True, "modelo": "deepseek-chat"},
    "manual": {"nome": "Conta grátis (copiar e colar)", "chave": False, "modelo": ""},
}
SITES = {"chatgpt": "https://chatgpt.com/", "gemini": "https://gemini.google.com/app",
         "claude": "https://claude.ai/new", "deepseek": "https://chat.deepseek.com/"}


class Colar(Exception):
    """A IA escolhida é uma conta grátis: a pessoa copia o pedido, cola no chat e traz a resposta."""


def config():
    try:
        return json.loads(CONFIG.read_text())
    except Exception:
        return {}


def salvar(cfg):
    CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=1))
    os.chmod(CONFIG, 0o600)


def publico(cfg=None):
    """O que a interface pode ver (a chave vai mascarada)."""
    cfg = cfg if cfg is not None else config()
    ch = cfg.get("chave", "")
    return {"configurada": cfg.get("provedor") in PROVEDORES, "provedor": cfg.get("provedor", ""),
            "modelo": cfg.get("modelo", ""), "site": cfg.get("site", "chatgpt"),
            "chave": (ch[:4] + "…" + ch[-4:]) if len(ch) > 10 else ("•••" if ch else ""),
            "provedores": PROVEDORES, "sites": SITES}


def _post(url, corpo, cabecalhos):
    req = urllib.request.Request(url, data=json.dumps(corpo).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **cabecalhos})
    try:
        with urllib.request.urlopen(req, timeout=900) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            d = json.loads(e.read())
            msg = d.get("error", {}).get("message") if isinstance(d.get("error"), dict) else d.get("error") or d
        except Exception:
            msg = str(e)
        if e.code == 400 and "key" in str(msg).lower():
            raise RuntimeError("a chave não é válida. Confira se copiou a chave inteira")
        if e.code in (401, 403):
            raise RuntimeError(f"a chave foi recusada ({msg})")
        if e.code == 429:
            raise RuntimeError(f"limite de uso atingido, tente mais tarde ({msg})")
        raise RuntimeError(f"erro {e.code}: {msg}")


def perguntar(texto, pasta=None, cfg=None):
    cfg = cfg or config()
    prov, chave = cfg.get("provedor"), cfg.get("chave", "")
    modelo = cfg.get("modelo") or PROVEDORES.get(prov, {}).get("modelo", "")
    if prov == "manual":
        raise Colar()
    if prov == "claude_pro":
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_BASE_URL"}
        r = subprocess.run([str(CLAUDE), "-p", "--output-format", "text"], input=texto, capture_output=True,
                           text=True, cwd=pasta or SIS, env=env, timeout=1800)
        if r.returncode != 0 or not r.stdout.strip():
            raise RuntimeError((r.stdout + r.stderr).strip()[-300:] or "o Claude não respondeu (está logado?)")
        return r.stdout
    if prov == "claude_api":
        d = _post("https://api.anthropic.com/v1/messages",
                  {"model": modelo, "max_tokens": 16000, "messages": [{"role": "user", "content": texto}]},
                  {"x-api-key": chave, "anthropic-version": "2023-06-01"})
        return "".join(b.get("text", "") for b in d.get("content", []))
    if prov == "gemini":
        d = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent",
                  {"contents": [{"role": "user", "parts": [{"text": texto}]}],
                   "generationConfig": {"maxOutputTokens": 16000}},
                  {"x-goog-api-key": chave})
        partes = (d.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in partes)
    if prov in ("openai", "deepseek"):
        url = "https://api.openai.com/v1/chat/completions" if prov == "openai" else "https://api.deepseek.com/chat/completions"
        d = _post(url, {"model": modelo, "messages": [{"role": "user", "content": texto}]},
                  {"Authorization": f"Bearer {chave}"})
        return d["choices"][0]["message"]["content"]
    raise RuntimeError("nenhuma IA conectada: escolha uma na engrenagem › IA das análises")


def json_da_resposta(t):
    """Tira o JSON do meio da resposta (as IAs às vezes escrevem algo antes ou usam ```json)."""
    return json.loads(t[t.index("{"):t.rindex("}") + 1])


def testar(cfg):
    if cfg.get("provedor") == "manual":
        return True, "ok"
    try:
        r = perguntar("Responda apenas a palavra: ok", cfg=cfg)
        return ("ok" in r.lower()), (r.strip()[:200] or "resposta vazia")
    except Exception as e:
        return False, str(e)
