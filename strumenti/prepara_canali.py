"""Elenco canali per Mondovisione, rifatto ogni notte dai dati pubblici di iptv-org.

Solo link https. Un canale e' «verificato» se funzionava dall'Italia nell'ultima prova
(dati/verificati.txt): gli altri arrivano come nuovi e la TV li prova da sola prima di mostrarli.
I numeri restano stabili (dati/numeri_stato.json): i canali nuovi prendono il primo libero.

Uso: python strumenti/prepara_canali.py <cartella api> <cartella dati> <canali_guida.xml> <uscita canali.tsv.gz>
"""
import datetime
import gzip
import json
import pathlib
import re
import sys

ITALIA_SENZA_LCN = 300
CATEGORIE_MANCANTI = {"RaiStoria.it": ["culture", "documentary"]}
FORMATI = {"PNG": 0, "WebP": 1, "JPEG": 2, "SVG": 3}


def leggi_righe(p):
    return [r.strip() for r in open(p, encoding="utf-8") if r.strip() and not r.startswith("#")]


def pulito(s):
    return "" if s is None else str(s).replace("\t", " ").replace("\n", " ").replace("\r", " ")


def numera(canali, lcn, stato):
    per_paese = {}
    for c in canali:
        per_paese.setdefault(c["p"], []).append(c)
    nuovo = {}
    for paese, lista in per_paese.items():
        vecchi = stato.get(paese, {})
        usati = set(vecchi.values()) | (set(lcn.values()) if paese == "IT" else set())
        assegnati = {}
        for c in lista:
            if paese == "IT" and c["id"] in lcn:
                assegnati[c["id"]] = lcn[c["id"]]
            elif c["id"] in vecchi:
                assegnati[c["id"]] = vecchi[c["id"]]
        prossimo = ITALIA_SENZA_LCN if paese == "IT" else 1
        for c in sorted(lista, key=lambda c: c["n"].lower()):
            if c["id"] in assegnati:
                continue
            while prossimo in usati:
                prossimo += 1
            assegnati[c["id"]] = prossimo
            usati.add(prossimo)
        for c in lista:
            c["num"] = assegnati[c["id"]]
        nuovo[paese] = {**vecchi, **assegnati}
    return nuovo


def main():
    api, dati = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
    guida_xml, uscita = pathlib.Path(sys.argv[3]), pathlib.Path(sys.argv[4])
    J = lambda n: json.load(open(api / f"{n}.json", encoding="utf-8"))
    canali_api = {c["id"]: c for c in J("channels")}
    paesi = {p["code"]: p for p in J("countries")}
    bloccati = {b["channel"] for b in J("blocklist")}
    loghi = {}
    for l in J("logos"):
        loghi.setdefault(l["channel"], []).append(l)
    verificati = set(leggi_righe(dati / "verificati.txt"))
    flussi_buoni = {}  # url -> (tipo, browser) come li ha trovati la prova dall'Italia
    for r in leggi_righe(dati / "flussi_verificati.txt"):
        p = r.split("\t")
        flussi_buoni[p[0]] = (p[1] if len(p) > 1 else "h", p[2] if len(p) > 2 else "0")
    lcn = json.load(open(dati / "numeri_lcn.json", encoding="utf-8"))["numeri"]
    stato_file = dati / "numeri_stato.json"
    stato = json.load(open(stato_file, encoding="utf-8")) if stato_file.exists() else {}
    pacchetto = {}  # loghi gia' dentro l'app: id -> (piastra, colore)
    if (dati / "loghi_pacchetto.tsv").exists():
        for r in leggi_righe(dati / "loghi_pacchetto.tsv"):
            p = r.split("\t")
            pacchetto[p[0]] = (p[1], p[2] if len(p) > 2 else "")
    con_guida = set(re.findall(r'xmltv_id="([^"@]+)', guida_xml.read_text(encoding="utf-8"))) if guida_xml.exists() else set()

    flussi_per = {}
    for s in J("streams"):
        cid = s.get("channel")
        if not cid or not s["url"].lower().startswith("https://"):
            continue
        flussi_per.setdefault(cid, []).append(s)

    canali = []
    for cid, flussi in flussi_per.items():
        c = canali_api.get(cid)
        if not c or c.get("closed") or c.get("is_nsfw") or cid in bloccati:
            continue
        # prima i link provati dall'Italia, poi per qualita'
        def qualita(s):
            q = (s.get("quality") or "").rstrip("pi")
            return int(q) if q.isdigit() else 0
        flussi.sort(key=lambda s: (s["url"] not in flussi_buoni, -qualita(s)))
        categorie = c.get("categories") or CATEGORIE_MANCANTI.get(cid, [])
        if not categorie and c["country"] == "IT" and lcn.get(cid, 99) <= 9:
            categorie = ["general"]
        voce = {"id": cid, "n": c["name"], "p": c["country"], "c": categorie, "s": flussi,
                "ok": 1 if cid in verificati else 0, "a": [a for a in c.get("alt_names") or [] if a != c["name"]],
                "epg": 1 if cid in con_guida else 0}
        if cid in pacchetto:
            voce["logo"], (voce["pl"], voce["col"]) = cid + ".webp", pacchetto[cid]
        else:
            candidati = sorted([l for l in loghi.get(cid, []) if l["url"].lower().startswith("https://")],
                               key=lambda l: (not l.get("in_use", True), FORMATI.get(l.get("format"), 4)))
            if candidati:
                voce["logo"] = candidati[0]["url"]
        canali.append(voce)

    nuovo_stato = numera(canali, lcn, stato)
    canali.sort(key=lambda c: (c["p"] != "IT", c["p"], c["num"]))
    creato = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = ["\t".join(["#mondovisione", "1", creato, "iptv-org (pubblico dominio), giro notturno Mondovisione"])]
    for k in sorted({c["p"] for c in canali}):
        if k in paesi:
            out.append("\t".join(["P", k, pulito(paesi[k]["name"]), pulito(paesi[k].get("flag"))]))
    for c in canali:
        out.append("\t".join(["C", c["id"], pulito(c["n"]), c["p"], ",".join(c["c"]), str(c["num"]), str(c["ok"]),
                              pulito(c.get("logo")), pulito(c.get("pl")), pulito(c.get("col")), str(c["epg"]),
                              "|".join(pulito(a) for a in c["a"])]))
        for s in c["s"]:
            q = (s.get("quality") or "").rstrip("pi")
            tipo, browser = flussi_buoni.get(s["url"], ("d" if ".mpd" in s["url"].lower() else "h", "0"))
            out.append("\t".join(["F", pulito(s["url"]), pulito(s.get("user_agent")), pulito(s.get("referrer")), browser,
                                  q if q.isdigit() else "", tipo, ",".join(s.get("labels") or [])]))
    uscita.parent.mkdir(parents=True, exist_ok=True)
    uscita.write_bytes(gzip.compress(("\n".join(out) + "\n").encode("utf-8"), 9))
    json.dump(nuovo_stato, open(stato_file, "w", encoding="utf-8"), ensure_ascii=False, indent=0, sort_keys=True)
    print(f"{len(canali)} canali ({sum(c['ok'] for c in canali)} verificati dall'Italia), "
          f"{sum(1 for c in canali if c['epg'])} con guida -> {uscita} ({uscita.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
