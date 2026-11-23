# Maria Spano · sito personale

Sito Quarto pubblicato su GitHub Pages: <https://mariaspano.github.io/homepage/>

## Come funziona

| Cosa | Dove |
|---|---|
| Pagine | `index.qmd`, `publications.qmd`, `projects.qmd`, `teaching.qmd`, `about.qmd`, `contacts.qmd` |
| Stile | `styles.css`, `site-scripts.html` |
| **Pubblicazioni** | `data/publications.yml`, unica fonte: la pagina Research e i numeri della home si generano da qui |
| Metriche (citazioni, h-index) | `data/metrics.yml` |
| Lavori ORCID da non mostrare | `data/orcid-ignore.yml` |

A ogni `quarto render` lo script `scripts/build_publications.py` rigenera `_publications.md` e `_home-stats.md`.
Non modificare questi due file: vengono sovrascritti.

## Pubblicazione

Ogni push su `main` avvia l'Action **Publish website**, che compila il sito e lo pubblica.
La cartella `_site/` serve solo per l'anteprima locale e non va nel repository.

Anteprima locale: `quarto preview` (oppure il pulsante Preview in Positron/RStudio).

## Aggiornamento automatico delle pubblicazioni

Ogni lunedì l'Action **Sync publications from ORCID** confronta il profilo ORCID
(0000-0002-3103-2342) con `data/publications.yml`. Se trova lavori nuovi:

1. li aggiunge al file con `review: true`, completando i dati da Crossref quando c'è un DOI;
2. apre una pull request **"New publications from ORCID"**.

Cosa fare quando arriva la PR:

- apri la PR su GitHub → *Files changed* → controlla le citazioni (autori, rivista, volume, pagine);
- correggi se serve (matita → *Edit file*) e cancella la riga `review: true`;
  finché c'è, sul sito compare un'etichetta **NEW** accanto alla voce;
- *Merge*: il sito si aggiorna da solo in un paio di minuti.

Per non mostrare un lavoro: cancella la voce e aggiungi il suo `orcid_put_code` a `data/orcid-ignore.yml`.
La sincronizzazione si può lanciare anche a mano da *Actions → Sync publications from ORCID → Run workflow*.

**Importante:** l'automazione vede solo quello che è su ORCID. Tieni ORCID aggiornato
(anche collegandolo a Scopus/Crossref), oppure aggiungi le voci a mano in `data/publications.yml`.

## Metriche di Google Scholar

Google Scholar blocca le richieste che arrivano dai server cloud, quindi questo passaggio va lanciato dal tuo computer:

```bash
python3 scripts/update_scholar_metrics.py
git commit -am "Update Scholar metrics" && git push
```

## Script

- `scripts/build_publications.py`: genera i frammenti del sito (eseguito automaticamente da Quarto)
- `scripts/sync_orcid.py`: cerca lavori nuovi su ORCID (`--dry-run` per vedere senza modificare)
- `scripts/update_scholar_metrics.py`: aggiorna le metriche di Scholar

Requisiti locali: Python 3 con `pyyaml` (`pip3 install pyyaml`) e Quarto.
