"""Canali italiani gratuiti e ufficiali dalla lista Free-TV (github.com/Free-TV/IPTV).

Free-TV accetta solo canali trasmessi gratis (digitale terrestre, satellite) e li elenca con il
numero del digitale terrestre. Qui la lista si legge e si abbina ai canali di iptv-org:
- i nazionali per numero (tabella LCN), ma solo se anche il nome corrisponde;
- gli altri per nome (o nome alternativo);
- quelli che iptv-org non ha diventano canali nuovi, con un identificativo nostro.

Si tengono solo link https, niente pagine YouTube, niente copie su server di terzi.
Lo stesso file serve all'elenco dentro l'app e al giro della notte.
"""
import difflib
import re
import unicodedata
from urllib.parse import urlsplit

URL = "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_italy.m3u8"
# copie dei canali su server che non sono delle emittenti: si scartano
NON_UFFICIALI = {"d3k8wzt41aflvx.cloudfront.net", "viamotionhsi.netplus.ch"}
VIETATI = re.compile(r"(^|\.)(worldsports\.[a-z0-9-]+|seckyes\.cc)\.?$", re.I)
PAROLE_VUOTE = r"\b(hd|tv|tivu|channel|television|televisione|canale|visual|radio)\b"


def pulisci(nome):
    nome = re.sub("[Ⓐ-ⓩ]", "", nome)  # lettere cerchiate: Ⓖ (bloccato all'estero), Ⓨ, Ⓢ
    return re.sub(r"\s+", " ", nome).strip()


def norma(s):
    s = unicodedata.normalize("NFKD", pulisci(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


def norma_corta(s):
    s = unicodedata.normalize("NFKD", pulisci(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", re.sub(PAROLE_VUOTE, " ", s))


def simili(a, b):
    x, y = norma_corta(a), norma_corta(b)
    if not x or not y:
        return norma(a) == norma(b)
    return x in y or y in x or difflib.SequenceMatcher(None, x, y).ratio() >= 0.6


def leggi(testo):
    voci, cur = [], None
    for riga in testo.splitlines():
        riga = riga.strip()
        if riga.startswith("#EXTINF"):
            a = dict(re.findall(r'([\w-]+)="([^"]*)"', riga.split(",", 1)[0] if '",' not in riga else riga.rsplit('",', 1)[0] + '"'))
            nome = riga.rsplit(",", 1)[-1].strip()
            num = a.get("tvg-chno", "").strip()
            cur = {"nome": pulisci(nome), "num": int(num) if num.isdigit() else None,
                   "logo": a.get("tvg-logo") or None, "estero_no": "Ⓖ" in nome}
        elif riga and not riga.startswith("#") and cur is not None:
            cur["url"] = riga
            voci.append(cur)
            cur = None
    return voci


def utilizzabile(v):
    p = urlsplit(v["url"])
    host = (p.hostname or "").lower()
    return (p.scheme == "https" and "youtube" not in host and "youtu.be" not in host
            and host not in NON_UFFICIALI and not VIETATI.search(host))


def nuovo_id(nome, esistenti):
    base = "".join(w[:1].upper() + w[1:] for w in re.findall(r"[A-Za-z0-9]+", unicodedata.normalize(
        "NFKD", nome).encode("ascii", "ignore").decode())) or "Canale"
    cid = f"{base}.it"
    return cid if cid not in esistenti else f"{base}FT.it"


# server di Sky Italia: Sky ha chiesto (DMCA) di togliere i suoi canali dalle liste pubbliche
SERVER_SKY = ("skycdn",)


def privato(cid, url, bloccati_dmca):
    """Canali da tenere solo dentro l'app, mai pubblicati su GitHub."""
    host = (urlsplit(url).hostname or "").lower()
    return cid in bloccati_dmca or any(s in host for s in SERVER_SKY)


def abbina(voci, canali_it, lcn, tutti_gli_id):
    """Ritorna [(voce, id_canale, nuovo)] per le voci utilizzabili.

    canali_it puo' contenere anche i canali che iptv-org segna come chiusi: servono a
    riconoscere per nome Sky TG24 o Mediaset Extra; a parita' vincono quelli aperti."""
    canali_it = sorted(canali_it, key=lambda c: bool(c.get("closed")))
    per_numero = {n: cid for cid, n in lcn.items()}
    nomi, corti, per_id = {}, {}, {}
    for c in canali_it:
        per_id[c["id"]] = c
        for n in [c["name"], *(c.get("alt_names") or [])]:
            nomi.setdefault(norma(n), c["id"])
            if norma_corta(n):
                corti.setdefault(norma_corta(n), c["id"])
    out, nuovi = [], {}
    for v in voci:
        if not utilizzabile(v):
            continue
        cid = None
        if v["num"] in per_numero and per_numero[v["num"]] in per_id:
            candidato = per_numero[v["num"]]
            c = per_id[candidato]
            if any(simili(v["nome"], n) for n in [c["name"], *(c.get("alt_names") or [])]):
                cid = candidato
        cid = cid or nomi.get(norma(v["nome"])) or corti.get(norma_corta(v["nome"]))
        nuovo = cid is None
        if nuovo:
            chiave = norma(v["nome"])
            cid = nuovi.setdefault(chiave, nuovo_id(v["nome"], tutti_gli_id | set(nuovi.values())))
        out.append((v, cid, nuovo))
    return out


def senza_privati(testo, canali_it, lcn, tutti_gli_id, bloccati):
    """La lista senza le voci private (Sky, DMCA): e' la copia che si puo' pubblicare."""
    voci = leggi(testo)
    privati = {v["url"] for v, cid, _ in abbina(voci, canali_it, lcn, tutti_gli_id) if privato(cid, v["url"], bloccati)}
    privati |= {v["url"] for v in voci if any(s in (urlsplit(v["url"]).hostname or "") for s in SERVER_SKY)}
    righe, attesa = [], []
    for riga in testo.splitlines():
        r = riga.strip()
        if r.startswith("#EXTINF"):
            attesa = [riga]
        elif r.startswith("#") or not r:
            (attesa if attesa else righe).append(riga)
        else:
            if r not in privati:
                righe.extend(attesa + [riga])
            attesa = []
    return "\n".join(righe) + "\n"


def categoria_ipotizzata(nome):
    """Per i canali che iptv-org non conosce: una categoria dal nome, se si capisce."""
    n = nome.lower()
    regole = [
        (("sport", "calcio", "tennis", "bianconera", "serie a", "motori"), "sports"),
        (("news", "tg ", "tg24", "notizie", "24"), "news"),
        (("radio",), "music"),
        (("boing", "cartoon", "yoyo", "gulp", "kids", "junior", "bimbi"), "kids"),
        (("shop", "shopping", "vendite"), "shop"),
        (("maria", "padre pio", "pace", "medjugorje", "tenda", "giovanni paolo", "vita"), "religious"),
        (("cinema", "movie", "film"), "movies"),
        (("travel", "viaggi"), "travel"),
    ]
    for parole, cat in regole:
        if any(p in n for p in parole):
            return [cat]
    return ["general"]
