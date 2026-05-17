# QuickReddit

Dagelijks Reddit-overzicht: nieuwe posts + top comments als HTML-rapport.  
**Geen API-key of registratie nodig** — werkt direct.

## Gebruik

```bash
python3 reddit_viewer.py
```

Genereert `reddit_report.html` in de huidige map. Open in je browser.

## Opties

```
python3 reddit_viewer.py [opties]

  --subreddits r/a r/b ...   Subreddits (default: dutchfire freelance webdev)
  --posts N                  Posts per subreddit (default: 25)
  --output bestand.html      Uitvoerbestand (default: reddit_report.html)
  --no-comments              Sla comments over (veel sneller)
```

### Voorbeelden

```bash
# Standaard: dutchfire + freelance + webdev, 25 posts, top 5 comments
python3 reddit_viewer.py

# Alleen dutchfire, 10 posts
python3 reddit_viewer.py --subreddits dutchfire --posts 10

# Extra subreddits
python3 reddit_viewer.py --subreddits dutchfire freelance webdev python Netherlands

# Snelle run zonder comments
python3 reddit_viewer.py --no-comments
```

## Vereisten

- Python 3.9+ (geen externe packages)
- Internetverbinding
