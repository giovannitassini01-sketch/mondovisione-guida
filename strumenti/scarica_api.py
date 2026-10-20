"""Scarica i dati pubblici di iptv-org (solo https) nella cartella indicata."""
import pathlib
import subprocess
import sys

FILE = ["channels", "streams", "logos", "countries", "categories", "guides", "blocklist", "feeds"]


def main():
    cartella = pathlib.Path(sys.argv[1])
    cartella.mkdir(parents=True, exist_ok=True)
    for nome in FILE:
        subprocess.run(["curl", "-sS", "-L", "--proto", "=https", "--proto-redir", "=https", "--retry", "3",
                        "--max-time", "300", "--fail", "-o", str(cartella / f"{nome}.json"),
                        f"https://iptv-org.github.io/api/{nome}.json"], check=True)
        print("ok", nome)
    # lista Free-TV Italia: non e' indispensabile, se non arriva si usa dati/freetv_italia.m3u8
    r = subprocess.run(["curl", "-sS", "-L", "--proto", "=https", "--proto-redir", "=https", "--retry", "3",
                        "--max-time", "120", "--fail", "-o", str(cartella / "freetv_italia.m3u8"),
                        "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_italy.m3u8"])
    print("ok freetv" if r.returncode == 0 else "freetv non scaricata: si usa l'ultima copia buona")


if __name__ == "__main__":
    main()
