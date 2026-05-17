# QuickReddit

Dagelijks Reddit-digest: posts ophalen, samenvattingen genereren via LLM, resultaat bekijken als HTML.

## Workflow

```bash
# 1. API key instellen (eenmalig)
export OPENROUTER_API_KEY=sk-or-...

# 2. Data ophalen + samenvattingen genereren
python3 reddit_viewer.py

# 3. Open in browser (vereist een lokale server vanwege fetch())
python3 -m http.server 8765
# → http://localhost:8765/reddit_report.html
```

## Opties

```
python3 reddit_viewer.py [opties]

  --subreddits r/a r/b ...   Subreddits (default: zie SUBREDDITS in script)
  --posts N                  Posts per subreddit (default: 10)
  --output bestand.json      Uitvoerbestand (default: reddit_data.json)
  --no-summaries             Sla LLM-samenvattingen over
```

## LLM-configuratie

Bovenin `reddit_viewer.py`:

```python
LLM_API_URL = "https://openrouter.ai/api/v1/chat/completions"
LLM_MODEL   = "deepseek/deepseek-v4-flash"
LLM_API_KEY_ENV = "OPENROUTER_API_KEY"
LLM_ENABLED = True
```

Wisselen van provider: pas `LLM_API_URL`, `LLM_MODEL` en `LLM_API_KEY_ENV` aan. Elke OpenAI-compatibele API werkt.

## Vereisten

- Python 3.9+ (geen externe packages)
- OpenRouter-account met credits (of vervang door andere provider)
