# Raul Osifo · Portfolio

Portfolio in italiano e inglese: https://geekeronline.github.io/portfolio/
Link diretto alla versione inglese: https://geekeronline.github.io/portfolio/?lang=en

Sito statico: `index.html`, `styles.css`, `main.js`. Non c'è nessun build step.

## Modificare i testi

Ogni testo compare due volte, una per lingua, uno accanto all'altro:

```html
<p lang="it">Testo in italiano.</p>
<p lang="en">English text.</p>
```

Il CSS mostra solo la lingua attiva (`html[lang]`). La lingua iniziale si decide così: `?lang=` nell'URL, poi l'ultima scelta del visitatore, poi la lingua del browser. Titolo della pagina, meta description, testi alternativi delle immagini e link al case study cambiano con la lingua tramite `main.js` (attributi `data-alt-*`, `data-href-*`, `data-aria-*`).

## Pubblicazione

GitHub Pages dal branch `main`, cartella principale. Dopo ogni push su `main` il sito si aggiorna in circa un minuto.

## Immagini

- `assets/img/raul-osifo-*.jpg`: ritratto
- `assets/img/spirit-ink-banner-*.webp`: banner del [case study Spirit Ink](https://github.com/Geekeronline/spirit-ink-case-study)
- `assets/img/hoodie-*.webp`: foto del catalogo Spirit Ink con due modelli grafici generici
- `assets/img/og-image.jpg`: anteprima mostrata quando il link viene condiviso
