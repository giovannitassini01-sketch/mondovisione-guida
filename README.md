# Mondovisione · giro della notte

Ogni notte questo progetto prepara due file per l'app Mondovisione e li pubblica su GitHub Pages:

- `canali.tsv.gz`: l'elenco dei canali televisivi gratuiti raccolti da [iptv-org](https://github.com/iptv-org/iptv), solo con collegamenti https;
- `guida/<paese>.json.gz`: la guida TV dei prossimi due giorni, presa dai siti che il progetto [iptv-org/epg](https://github.com/iptv-org/epg) sa leggere.

Qui non passa nessun video: solo elenchi e orari. I dati dei canali sono di pubblico dominio (iptv-org); le guide sono informazioni pubbliche dei rispettivi siti.

Il programma che scarica le guide gira con le richieste in chiaro (http) bloccate: si usano solo collegamenti https.
