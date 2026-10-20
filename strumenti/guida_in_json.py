"""Dai file XMLTV del programma di iptv-org ai file leggeri che legge la TV: uno per paese.

Formato d'uscita (guida/<paese>.json.gz):
  {"v": 1, "creato": "...", "canali": {"Rai1.it": [[inizio, fine, "titolo", "descrizione"], ...]}}
Tempi in secondi (epoch). Si tengono i programmi dalle ultime 3 ore alle prossime 36,
e la descrizione si taglia a 180 caratteri: la TV scarica poco e legge in fretta.
Un programma senza fine (l'XMLTV lo permette) finisce quando inizia il successivo.

Uso: python strumenti/guida_in_json.py <cartella con i .xml> <cartella d'uscita> [paesi validi.json]
"""
import bisect
import collections
import datetime
import gzip
import json
import pathlib
import sys
import time
import xml.etree.ElementTree as ET

PRIMA, DOPO = 3 * 3600, 36 * 3600
DURATA_MAX = 12 * 3600  # senza fine e col successivo troppo lontano: buco nei dati, si scarta


def tempo(s):
    # «20261020203000 +0200»
    return int(datetime.datetime.strptime(s.strip(), "%Y%m%d%H%M%S %z").timestamp())


def testo(el, nome, lingue=("it", "en")):
    candidati = el.findall(nome)
    if not candidati:
        return None
    for l in lingue:
        for c in candidati:
            if c.get("lang") == l and (c.text or "").strip():
                return c.text.strip()
    return next(((c.text or "").strip() for c in candidati if (c.text or "").strip()), None)


def main():
    sorgenti = pathlib.Path(sys.argv[1])
    uscita = pathlib.Path(sys.argv[2])
    adesso = int(time.time())
    per_canale = collections.defaultdict(dict)
    inizi = collections.defaultdict(set)
    for f in sorted(sorgenti.glob("*.xml")):
        for _, el in ET.iterparse(f, events=("end",)):
            if el.tag != "programme":
                continue
            canale = (el.get("channel") or "").split("@")[0]
            try:
                inizio = tempo(el.get("start"))
                fine = tempo(el.get("stop")) if el.get("stop") else None
            except (AttributeError, ValueError):
                el.clear()
                continue
            inizi[canale].add(inizio)
            if inizio > adesso + DOPO or (fine is not None and (fine < adesso - PRIMA or fine <= inizio)):
                el.clear()
                continue
            titolo = testo(el, "title")
            if canale and titolo:
                desc = testo(el, "desc")
                if desc and len(desc) > 180:
                    desc = desc[:177].rsplit(" ", 1)[0] + "…"
                # chiave per inizio: se due siti danno lo stesso canale, vince il primo
                per_canale[canale].setdefault(inizio, [inizio, fine, titolo] + ([desc] if desc else []))
            el.clear()
    for canale, programmi in per_canale.items():
        successivi = sorted(inizi[canale])
        for k in [k for k, p in programmi.items() if p[1] is None]:
            i = bisect.bisect_right(successivi, k)
            fine = successivi[i] if i < len(successivi) else None
            if fine is None or fine - k > DURATA_MAX or fine < adesso - PRIMA:
                del programmi[k]
            else:
                programmi[k][1] = fine
    per_paese = collections.defaultdict(dict)
    for canale, programmi in per_canale.items():
        if not programmi:
            continue
        paese = canale.rsplit(".", 1)[-1].upper()
        per_paese[paese][canale] = [programmi[k] for k in sorted(programmi)]
    uscita.mkdir(parents=True, exist_ok=True)
    creato = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for paese, canali in sorted(per_paese.items()):
        dati = json.dumps({"v": 1, "creato": creato, "canali": canali}, ensure_ascii=False, separators=(",", ":"))
        (uscita / f"{paese.lower()}.json.gz").write_bytes(gzip.compress(dati.encode("utf-8"), 9))
    totale = sum(len(v) for c in per_paese.values() for v in c.values())
    print(f"{sum(len(c) for c in per_paese.values())} canali, {totale} programmi, {len(per_paese)} paesi in {uscita}")


if __name__ == "__main__":
    main()
