"""Analisa o canal do YouTube de uma igreja: o que mais performou, por quê e como reaproveitar em cada rede.

Uso: canal.py <link do canal> [arquivo com dados de outras redes]
De onde vêm os números:
  - com a chave da API do YouTube (.sistema/youtube_chave.txt): API oficial, até 150 vídeos com views,
    likes, comentários, data e duração;
  - sem a chave: páginas públicas do canal (títulos e views dos shorts) e o feed RSS oficial
    (views e data dos 15 vídeos mais recentes). Os números ficam parciais.
Grava em .sistema/canais/<id>/: status, canal.json, analise.json (resposta do Claude com prompt_canal.md)
"""
import json, os, re, subprocess, sys, time, urllib.error, urllib.parse, urllib.request
from statistics import median
from pathlib import Path

import yt_dlp

import comum
import ia

SIS = Path.home() / "CortesAutomacao" / ".sistema"
CANAIS = SIS / "canais"
CHAVE = SIS / "youtube_chave.txt"
API = "https://www.googleapis.com/youtube/v3/"


def base_do_link(link):
    link = link.strip()
    if not link.startswith("http"):
        link = "https://www.youtube.com/" + (link if link.startswith("@") else "@" + link)
    m = re.match(r"(https?://(?:www\.|m\.)?youtube\.com/(?:@[^/?#]+|channel/[^/?#]+|c/[^/?#]+|user/[^/?#]+))", link)
    if not m:
        raise ValueError("isso não parece um link de canal do YouTube (ex.: youtube.com/@suaigreja)")
    return m.group(1).replace("m.youtube", "www.youtube")


def segundos(iso):
    h, m, s = (re.search(r"(\d+)" + u, iso or "") for u in "HMS")
    return sum(int(x.group(1)) * k for x, k in ((h, 3600), (m, 60), (s, 1)) if x)


def api(recurso, chave, **params):
    url = API + recurso + "?" + urllib.parse.urlencode({**params, "key": chave})
    try:
        return json.loads(urllib.request.urlopen(url, timeout=30).read())
    except urllib.error.HTTPError as e:
        motivo = json.loads(e.read() or b"{}").get("error", {}).get("message", str(e))
        raise RuntimeError("a chave da API do YouTube não funcionou: " + re.sub("<[^>]+>", "", motivo))


def via_api(base, chave, status):
    ident = base.rsplit("/", 1)[1]
    filtro = {"id": ident} if "/channel/" in base else {"forUsername": ident} if "/user/" in base else \
        {"forHandle": ident if ident.startswith("@") else "@" + ident}
    ch = api("channels", chave, part="snippet,statistics,contentDetails", **filtro).get("items")
    if not ch:
        raise RuntimeError("não encontrei esse canal no YouTube")
    ch = ch[0]
    uploads, ids, pagina = ch["contentDetails"]["relatedPlaylists"]["uploads"], [], None
    while len(ids) < 150:
        r = api("playlistItems", chave, part="contentDetails", playlistId=uploads, maxResults=50,
                **({"pageToken": pagina} if pagina else {}))
        ids += [i["contentDetails"]["videoId"] for i in r.get("items", [])]
        pagina = r.get("nextPageToken")
        status.write_text(f"buscando {len(ids)} vídeos")
        if not pagina:
            break
    videos = []
    for i in range(0, len(ids), 50):
        r = api("videos", chave, part="snippet,statistics,contentDetails,liveStreamingDetails", id=",".join(ids[i:i + 50]))
        for e in r.get("items", []):
            st, sn, dur = e.get("statistics", {}), e["snippet"], segundos(e["contentDetails"].get("duration"))
            videos.append({"id": e["id"], "titulo": sn["title"], "descricao": sn.get("description", "")[:280],
                           "tipo": "live" if "liveStreamingDetails" in e else "short" if 0 < dur <= 180 else "vídeo",
                           "views": int(st.get("viewCount", 0)), "likes": int(st.get("likeCount", 0)),
                           "comentarios": int(st.get("commentCount", 0)),
                           "data": sn["publishedAt"][:10].replace("-", ""), "duracao": dur})
    return {"nome": ch["snippet"]["title"], "inscritos": int(ch["statistics"].get("subscriberCount", 0)) or None,
            "fonte": "api", "videos": videos}


def via_publico(base, status):
    videos, canal = {}, {}
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "extract_flat": "in_playlist"}) as y:
        for aba, tipo in (("videos", "vídeo"), ("shorts", "short"), ("streams", "live")):
            status.write_text(f"lendo a aba {aba}")
            try:
                d = y.extract_info(f"{base}/{aba}", download=False) or {}
            except yt_dlp.utils.DownloadError:
                continue  # canal sem shorts ou sem lives
            canal = canal or d
            for e in (d.get("entries") or [])[:60]:
                videos[e["id"]] = {"id": e["id"], "titulo": e.get("title"), "tipo": tipo, "views": e.get("view_count") or 0,
                                   "likes": 0, "comentarios": 0, "data": "", "duracao": e.get("duration") or 0,
                                   "descricao": (e.get("description") or "")[:280]}
    if canal.get("channel_id"):
        xml = urllib.request.urlopen(f"https://www.youtube.com/feeds/videos.xml?channel_id={canal['channel_id']}",
                                     timeout=30).read().decode()
        for ent in xml.split("<entry>")[1:]:
            vid = re.search(r"<yt:videoId>([^<]+)", ent).group(1)
            v = videos.setdefault(vid, {"id": vid, "titulo": re.search(r"<title>([^<]*)", ent).group(1), "tipo": "vídeo",
                                        "likes": 0, "comentarios": 0, "duracao": 0, "descricao": ""})
            v["views"] = int((re.search(r'views="(\d+)"', ent) or [0, 0])[1]) or v.get("views", 0)
            v["likes"] = v["likes"] or int((re.search(r'starRating count="(\d+)"', ent) or [0, 0])[1])
            v["data"] = re.search(r"<published>(\d{4})-(\d\d)-(\d\d)", ent).expand(r"\1\2\3")
    com_views = [v for v in videos.values() if v["views"]]
    return {"nome": canal.get("channel") or base.rsplit("/", 1)[1], "inscritos": canal.get("channel_follower_count"),
            "fonte": "publico", "videos": com_views, "sem_numeros": len(videos) - len(com_views),
            "titulos_sem_numeros": [v["titulo"] for v in videos.values() if not v["views"]][:40]}


def aplicar(pasta, resposta):
    """Confere e grava a análise do canal (vinda da IA automática ou colada pela pessoa)."""
    (pasta / "resposta.txt").write_text(resposta)
    d = ia.json_da_resposta(resposta)
    assert d["redes"] and d["top"], "faltam as redes ou os destaques"
    (pasta / "analise.json").write_text(json.dumps(d, ensure_ascii=False, indent=1))
    (pasta / "pedido.txt").unlink(missing_ok=True)
    (pasta / "status").write_text("pronto")


def main(link, extra):
    base = base_do_link(link)
    pasta = CANAIS / re.sub(r"[^\w-]+", "_", base.rsplit("/", 1)[1]).strip("_")
    pasta.mkdir(parents=True, exist_ok=True)
    status = pasta / "status"
    status.write_text("buscando os vídeos")
    try:
        chave = CHAVE.read_text().strip() if CHAVE.exists() else ""
        info = via_api(base, chave, status) if chave else via_publico(base, status)
        videos = info["videos"]
        if not videos:
            raise RuntimeError(f"o canal “{info['nome']}” ({info['inscritos'] or 0} inscritos) não tem vídeos públicos. "
                               "Confira se é o canal principal da igreja")
        # força = quantas vezes o vídeo passou da mediana do próprio formato (short com short, live com live)
        for tipo in {v["tipo"] for v in videos}:
            med = median([v["views"] for v in videos if v["tipo"] == tipo]) or 1
            for v in videos:
                if v["tipo"] == tipo:
                    v["forca"] = round(v["views"] / med, 2)
                    v["engajamento"] = round((v["likes"] + v["comentarios"]) / v["views"] * 100, 2) if v["views"] else 0
        videos.sort(key=lambda v: -v["views"])
        info.update(link=base, quando=time.time())
        (pasta / "canal.json").write_text(json.dumps(info, ensure_ascii=False, indent=1))

        status.write_text("analisando")
        linhas = [f"{v['id']} | {v['tipo']} | {v['data'] or '?'} | {v['views']} views | {v['likes']} likes | "
                  f"{v['comentarios']} coment. | {v['duracao'] // 60}min{v['duracao'] % 60:02d}s | força {v.get('forca')}x | "
                  f"{v['titulo']} | {v['descricao'][:160].replace(chr(10), ' ')}" for v in videos]
        texto = (f"CANAL: {info['nome']} ({info['inscritos'] or '?'} inscritos)\n\n"
                 "VÍDEOS (id | formato | data | views | likes | comentários | duração | força | título | descrição):\n"
                 + "\n".join(linhas))
        if info["fonte"] == "publico":
            texto += ("\n\nATENÇÃO: números parciais (sem a API do YouTube). Só há views dos shorts e dos 15 vídeos mais "
                      "recentes; likes e comentários quase sempre zerados por falta de dado, não por falta de engajamento. "
                      "Outros títulos do canal, sem números:\n" + "\n".join(info.get("titulos_sem_numeros", [])))
        if extra:
            texto += "\n\nDADOS DE OUTRAS REDES ENVIADOS PELA IGREJA:\n" + extra
        texto = (SIS / "prompt_canal.md").read_text() + "\n\n" + texto
        for tentativa in (1, 2):
            try:
                aplicar(pasta, ia.perguntar(texto, pasta))
                break
            except ia.Colar:  # conta grátis: a pessoa leva o pedido para a IA e cola a resposta no app
                (pasta / "pedido.txt").write_text(texto)
                status.write_text("colar")
                return 0
            except Exception as e:
                if tentativa == 2:
                    raise RuntimeError(f"a IA não respondeu no formato esperado ({e})")
        status.write_text("pronto")
    except Exception as e:
        status.write_text(f"erro: {e}")
        with open(SIS / "log.txt", "a") as f:
            f.write(time.strftime("%d/%m %H:%M ") + f"ERRO canal {link}: {e!r}\n")
        return 1
    return 0


if __name__ == "__main__":
    comum.aplicar_prioridade()
    extra = Path(sys.argv[2]).read_text() if len(sys.argv) > 2 and Path(sys.argv[2]).exists() else ""
    sys.exit(main(sys.argv[1], extra))
