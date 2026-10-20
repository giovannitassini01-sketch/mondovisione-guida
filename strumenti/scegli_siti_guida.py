"""Per ogni canale con la guida sceglie UN sito da cui prenderla e scrive canali_guida.xml
per il programma di iptv-org/epg.

Regole: solo siti verdi in SITES.md e non rotti; nessun sito il cui programma usi indirizzi
http (mai traffico in chiaro); per l'Italia prima le fonti delle emittenti; i siti che
consumano gigabyte di memoria solo se non c'e' altro.

Uso: python strumenti/scegli_siti_guida.py <cartella api> <cartella epg> <uscita canali_guida.xml> [cartella dati]
"""
import collections
import json
import pathlib
import re
import sys
import xml.sax.saxutils as sx

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import freetv  # noqa: E402

SITI_PREFERITI = {
    "IT": ["raiplay.it", "mediasetinfinity.mediaset.it", "guidatv.sky.it", "tv.blue.ch", "guida.tv", "teleboy.ch"],
}
PESANTI = {"sky.com", "epg.iptvx.one"}
ROTTI = {"superguidatv.it"}  # verde in SITES.md, ma il 20/10/2026 dava 0 programmi
LINGUE_PAESE = {"IT": "it", "UK": "en", "US": "en", "FR": "fr", "DE": "de", "ES": "es", "PT": "pt", "NL": "nl",
                "BR": "pt", "MX": "es", "AR": "es", "RU": "ru", "TR": "tr", "PL": "pl", "RO": "ro", "IN": "hi"}


def main():
    api, epg, uscita = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3])
    J = lambda n: json.load(open(api / f"{n}.json", encoding="utf-8"))
    canali = {c["id"]: c for c in J("channels")}
    con_https = {s["channel"] for s in J("streams") if s.get("channel") and s["url"].lower().startswith("https://")}
    if len(sys.argv) > 4:
        # anche i canali italiani che arrivano da Free-TV (non i privati)
        dati = pathlib.Path(sys.argv[4])
        lista = api / "freetv_italia.m3u8" if (api / "freetv_italia.m3u8").exists() else dati / "freetv_italia.m3u8"
        if lista.exists():
            lcn = json.load(open(dati / "numeri_lcn.json", encoding="utf-8"))["numeri"]
            bloccati = {b["channel"] for b in J("blocklist")}
            canali_it = [c for c in canali.values() if c["country"] == "IT"]
            for v, cid, nuovo in freetv.abbina(freetv.leggi(lista.read_text(encoding="utf-8", errors="replace")),
                                               canali_it, lcn, set(canali)):
                if not nuovo and not freetv.privato(cid, v["url"], bloccati):
                    con_https.add(cid)
    sites_md = (epg / "SITES.md").read_text(encoding="utf-8")
    verdi = set(re.findall(r'<a href="sites/([^"]+)">[^<]+</a></td><td align="right">\d+</td><td align="center">🟢', sites_md))
    guide = [g for g in J("guides") if g.get("channel") in con_https and g.get("channel") in canali]
    usabili = {}
    for sito in {g["site"] for g in guide}:
        cfg = epg / "sites" / sito / f"{sito}.config.js"
        usabili[sito] = (sito in verdi and sito not in ROTTI and cfg.exists()
                         and re.search(r"http://(?!localhost)", cfg.read_text(encoding="utf-8", errors="replace")) is None)
    copertura = collections.Counter(g["site"] for g in guide if usabili[g["site"]])
    per_canale = collections.defaultdict(list)
    for g in guide:
        if usabili[g["site"]]:
            per_canale[g["channel"]].append(g)
    righe, scelti = [], collections.Counter()
    for cid, opzioni in per_canale.items():
        paese = canali[cid]["country"]
        preferiti = SITI_PREFERITI.get(paese, [])
        opzioni.sort(key=lambda g: (g["site"] in PESANTI,
                                    preferiti.index(g["site"]) if g["site"] in preferiti else len(preferiti),
                                    g.get("lang") != LINGUE_PAESE.get(paese), -copertura[g["site"]], g["site"]))
        g = opzioni[0]
        scelti[g["site"]] += 1
        xmltv = cid + (f"@{g['feed']}" if g.get("feed") else "")
        righe.append(f'  <channel site="{sx.escape(g["site"])}" lang="{sx.escape(g.get("lang") or "")}" '
                     f'xmltv_id="{sx.escape(xmltv)}" site_id="{sx.escape(g["site_id"])}">{sx.escape(g.get("site_name") or cid)}</channel>')
    uscita.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<channels>\n' + "\n".join(sorted(righe)) + "\n</channels>\n",
                      encoding="utf-8")
    print(f"canali con guida: {len(righe)} da {len(scelti)} siti; esclusi: "
          f"{sorted(s for s, ok in usabili.items() if not ok)}")


if __name__ == "__main__":
    main()
