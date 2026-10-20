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

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import freetv  # noqa: E402

ITALIA_SENZA_LCN = 300
# canali senza categoria in iptv-org a cui la categoria si sa (da Wikipedia, sezione «Contenuti»)
CATEGORIE_MANCANTI = {"RaiStoria.it": ["culture", "documentary"], "Rai5.it": ["culture", "documentary"],
                      "Rai4.it": ["entertainment"], "Rai4K.it": ["entertainment"], "RaiPremium.it": ["entertainment"],
                      "RealTime.it": ["entertainment", "lifestyle"], "RaiGulp.it": ["kids"],
                      "R101TV.it": ["music"], "RDSSocialTV.it": ["music"]}
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


def lista_freetv(api, dati, canali_api, lcn, bloccati):
    """La lista di stanotte se e' sana, altrimenti l'ultima copia buona (che si aggiorna qui,
    senza le voci private: il progetto e' pubblico)."""
    fresca, copia = api / "freetv_italia.m3u8", dati / "freetv_italia.m3u8"
    if fresca.exists():
        testo = fresca.read_text(encoding="utf-8", errors="replace")
        if len(freetv.leggi(testo)) >= 100:
            canali_it = [c for c in canali_api.values() if c["country"] == "IT"]
            copia.write_text(freetv.senza_privati(testo, canali_it, lcn, set(canali_api), bloccati), encoding="utf-8")
            return testo
        print("lista Free-TV di stanotte sospetta: uso l'ultima copia buona")
    return copia.read_text(encoding="utf-8") if copia.exists() else ""


def unisci_freetv(api, dati, canali, canali_api, bloccati, lcn, pacchetto, loghi, verificati, flussi_buoni, con_guida):
    """Canali italiani ufficiali da Free-TV: link di riserva per chi c'e', canali nuovi per chi manca.
    Mai i «privati» (Sky e canali tolti con DMCA): quelli stanno solo dentro l'app."""
    testo = lista_freetv(api, dati, canali_api, lcn, bloccati)
    if not testo:
        return
    dmca = {cid for cid in bloccati}
    tutti = set(canali_api)
    canali_it = [c for c in canali_api.values() if c["country"] == "IT"]
    per_id = {c["id"]: c for c in canali}
    usati = set(lcn.values())
    aggiunti = 0
    for v, cid, nuovo in freetv.abbina(freetv.leggi(testo), canali_it, lcn, tutti):
        if freetv.privato(cid, v["url"], dmca):
            continue
        tipo, browser = flussi_buoni.get(v["url"], ("h", "0"))
        flusso = {"url": v["url"], "user_agent": None, "referrer": None, "quality": None,
                  "labels": ["Geo-blocked"] if v["estero_no"] else [], "_tipo": tipo, "_browser": browser}
        if cid in per_id:
            if v["url"] not in {s["url"] for s in per_id[cid]["s"]}:
                per_id[cid]["s"].append(flusso)
        else:
            info = canali_api.get(cid, {})
            voce = {"id": cid, "n": v["nome"] if nuovo else info.get("name", v["nome"]), "p": "IT",
                    "c": freetv.categoria_ipotizzata(v["nome"]) if nuovo else (info.get("categories") or []),
                    "s": [flusso], "ok": 1 if cid in verificati else 0,
                    "a": [] if nuovo else [a for a in info.get("alt_names") or [] if a != info.get("name")],
                    "epg": 1 if cid in con_guida else 0}
            if cid in pacchetto:
                voce["logo"], (voce["pl"], voce["col"]) = cid + ".webp", pacchetto[cid]
            else:
                url_logo = next((l["url"] for l in loghi.get(cid, []) if l["url"].lower().startswith("https://")), None)
                url_logo = url_logo or (v["logo"] if (v["logo"] or "").lower().startswith("https://") else None)
                if url_logo:
                    voce["logo"] = url_logo
            canali.append(voce)
            per_id[cid] = voce
            aggiunti += 1
        regionale = v["num"] and (10 <= v["num"] <= 19 or 71 <= v["num"] <= 99)  # numeri locali, per regione
        if v["num"] and not regionale and cid not in lcn and v["num"] not in usati:
            lcn[cid] = v["num"]
            usati.add(v["num"])
    print(f"Free-TV: {aggiunti} canali aggiunti, link di riserva per gli altri")


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

    unisci_freetv(api, dati, canali, canali_api, bloccati, lcn, pacchetto, loghi, verificati, flussi_buoni, con_guida)
    for c in canali:
        if c["p"] == "IT" and not c["c"]:
            # iptv-org non da' nessuna categoria a Rai 1, Rete 4 e a tante locali: le radio in musica, il resto generalisti
            c["c"] = CATEGORIE_MANCANTI.get(c["id"]) or freetv.categoria_ipotizzata(c["n"])
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
            tipo, browser = flussi_buoni.get(s["url"], (s.get("_tipo") or ("d" if ".mpd" in s["url"].lower() else "h"),
                                                          s.get("_browser") or "0"))
            out.append("\t".join(["F", pulito(s["url"]), pulito(s.get("user_agent")), pulito(s.get("referrer")), browser,
                                  q if q.isdigit() else "", tipo, ",".join(s.get("labels") or [])]))
    uscita.parent.mkdir(parents=True, exist_ok=True)
    uscita.write_bytes(gzip.compress(("\n".join(out) + "\n").encode("utf-8"), 9))
    json.dump(nuovo_stato, open(stato_file, "w", encoding="utf-8"), ensure_ascii=False, indent=0, sort_keys=True)
    print(f"{len(canali)} canali ({sum(c['ok'] for c in canali)} verificati dall'Italia), "
          f"{sum(1 for c in canali if c['epg'])} con guida -> {uscita} ({uscita.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
