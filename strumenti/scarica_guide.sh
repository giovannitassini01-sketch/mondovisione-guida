#!/usr/bin/env bash
# Scarica la guida sito per sito con il programma di iptv-org/epg.
# Un processo per sito: un sito lento, rotto o che chiede troppa memoria non ferma gli altri.
# Ogni richiesta in chiaro (http) viene mandata a un indirizzo morto: non esce mai dalla macchina.
# Uso: bash strumenti/scarica_guide.sh <cartella epg> <canali_guida.xml> <cartella uscita>
set -u
EPG="$(cd "$1" && pwd)"
CANALI="$2"
OUT="$(mkdir -p "$3" && cd "$3" && pwd)"
mkdir -p "$OUT/log" "$OUT/canali"
python3 - "$CANALI" "$OUT/canali" <<'PY'
import collections, pathlib, re, sys
righe = collections.defaultdict(list)
for r in open(sys.argv[1], encoding="utf-8"):
    m = re.search(r'site="([^"]+)"', r)
    if m:
        righe[m.group(1)].append(r.rstrip("\n"))
for sito, rr in righe.items():
    pathlib.Path(sys.argv[2], f"{sito}.channels.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<channels>\n' + "\n".join(rr) + "\n</channels>\n", encoding="utf-8")
print(len(righe), "siti")
PY

scarica() {  # sito, memoria in MB
  local f="$OUT/canali/$1.channels.xml"
  (cd "$EPG" && timeout 1500 env NODE_OPTIONS="--max-old-space-size=$2" HTTP_PROXY=http://127.0.0.1:9 http_proxy=http://127.0.0.1:9 \
    npm run grab --silent -- --channels="$f" --output="$OUT/$1.xml" --days=2 --maxConnections=3 --timeout=20000 \
    > "$OUT/log/$1.log" 2>&1)
  echo "$1: uscita $?, $(grep -c '<programme' "$OUT/$1.xml" 2>/dev/null || echo 0) programmi"
}
export -f scarica
export EPG OUT

PESANTI="sky.com epg.iptvx.one"
# prima tutti i siti normali, quattro alla volta
for f in "$OUT"/canali/*.channels.xml; do
  s="$(basename "$f" .channels.xml)"
  case " $PESANTI " in *" $s "*) continue;; esac
  echo "$s"
done | xargs -P 4 -I{} bash -c 'scarica {} 2048'
# poi quelli pesanti, uno alla volta e con tanta memoria
for s in $PESANTI; do
  [ -f "$OUT/canali/$s.channels.xml" ] && scarica "$s" 10240
done
true
