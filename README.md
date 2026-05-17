# QuickReddit

Dagelijks Reddit-digest: posts ophalen met Python, samenvattingen genereren via Claude Code, resultaat bekijken als HTML.

## Workflow

```bash
# 1. Data ophalen
python3 reddit_viewer.py

# 2. Vraag Claude Code om samenvattingen te genereren
# "lees reddit_data.json, schrijf een Nederlandse samenvatting per post en sla op"

# 3. Open in browser (vereist een lokale server vanwege fetch())
python3 -m http.server 8765
# → http://localhost:8765/reddit_report.html
```

## Opties

```
python3 reddit_viewer.py [opties]

  --subreddits r/a r/b ...   Subreddits (default: dutchfire freelance webdev)
  --posts N                  Posts per subreddit (default: 10)
  --output bestand.json      Uitvoerbestand (default: reddit_data.json)
```

## Hoe het werkt

1. `reddit_viewer.py` haalt posts + comments op via Reddit's publieke JSON API en slaat op als `reddit_data.json`.
2. Claude Code leest de JSON en schrijft per post een gebalanceerde samenvatting terug naar `summary`-veld.
3. `reddit_report.html` laadt de JSON en toont titel, meta en samenvatting per post.

## Automatisering via Claude Cowork

Periodieke taak: draai `python3 reddit_viewer.py`, lees daarna `reddit_data.json`, genereer voor elke post een Nederlandse samenvatting en schrijf die terug naar de `summary`-velden.

## Vereisten

- Python 3.9+ (geen externe packages)
- Internetverbinding
