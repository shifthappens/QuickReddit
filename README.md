# QuickReddit

Dagelijks Reddit-overzicht: nieuwe posts + top comments als HTML-rapport.

## Setup (2 minuten)

### 1. Reddit app aanmaken

Ga naar [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps):
- Klik **"create another app"**
- Type: **script**
- Name: `QuickReddit` (of wat je wilt)
- Redirect URI: `http://localhost` (verplicht veld, wordt niet gebruikt)
- Klik **"create app"**

Noteer de **client ID** (onder de app-naam, 14 tekens) en het **secret**.

### 2. Credentials instellen

```bash
cp .env.example .env
# Vul je client ID en secret in het .env bestand
```

Of exporteer ze direct:

```bash
export REDDIT_CLIENT_ID="jouw_client_id"
export REDDIT_CLIENT_SECRET="jouw_secret"
```

### 3. Uitvoeren

```bash
python3 reddit_viewer.py
```

Opent een HTML-rapport (`reddit_report.html`) in de huidige map.

## Gebruik

```
python3 reddit_viewer.py [opties]

Opties:
  --subreddits r/a r/b ...   Welke subreddits (default: dutchfire freelance webdev)
  --posts N                  Posts per subreddit (default: 25)
  --output bestand.html      Uitvoerbestand (default: reddit_report.html)
  --no-comments              Sla comments over (sneller)
```

### Voorbeelden

```bash
# Standaard: dutchfire + freelance + webdev
python3 reddit_viewer.py

# Alleen dutchfire, 10 posts
python3 reddit_viewer.py --subreddits dutchfire --posts 10

# Extra subreddits toevoegen
python3 reddit_viewer.py --subreddits dutchfire freelance webdev python Netherlands

# Snelle run zonder comments
python3 reddit_viewer.py --no-comments
```

## Vereisten

- Python 3.9+ (geen externe packages nodig)
- Reddit OAuth2 "script" app credentials

## Limieten

Reddit free tier: 100 requests/minuut. Met 3 subreddits × 25 posts + comments zijn dat ca. 78 requests — ruim binnen de limiet.
