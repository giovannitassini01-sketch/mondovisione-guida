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


if __name__ == "__main__":
    main()
