#!/usr/bin/env python3
"""
QuickReddit - daily Reddit subreddit viewer.
Uses Reddit's public JSON API — no credentials needed.
"""

import json
import html
import datetime
import argparse
import time
import urllib.request
import urllib.error
import os
import sys

SUBREDDITS = ["dutchfire", "freelance", "webdev"]
POSTS_PER_SUB = 25
TOP_COMMENTS = 5
# Reddit requires a descriptive User-Agent for API requests
USER_AGENT = "python:QuickReddit:v1.0 (personal daily digest; single user)"


def api_get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def fetch_posts(subreddit: str, limit: int) -> list[dict]:
    url = f"https://www.reddit.com/r/{subreddit}/new.json?limit={limit}"
    data = api_get(url)
    posts = []
    for child in data["data"]["children"]:
        p = child["data"]
        posts.append({
            "id": p["id"],
            "title": p["title"],
            "author": p.get("author", "[deleted]"),
            "score": p["score"],
            "url": f"https://www.reddit.com{p['permalink']}",
            "selftext": p.get("selftext", "")[:300],
            "num_comments": p["num_comments"],
            "created_utc": p["created_utc"],
            "subreddit": subreddit,
        })
    return posts


def fetch_top_comments(post_id: str, subreddit: str) -> list[dict]:
    url = f"https://www.reddit.com/r/{subreddit}/comments/{post_id}.json?limit=10&sort=top&depth=1"
    data = api_get(url)
    comments = []
    if len(data) < 2:
        return comments
    for child in data[1]["data"]["children"]:
        c = child["data"]
        if c.get("kind") == "more" or not c.get("body"):
            continue
        comments.append({
            "author": c.get("author", "[deleted]"),
            "score": c.get("score", 0),
            "body": c.get("body", "")[:500],
        })
        if len(comments) >= TOP_COMMENTS:
            break
    return comments


def render_html(subreddit_data: dict, posts_per_sub: int) -> str:
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = []
    for subreddit, posts in subreddit_data.items():
        rows.append(f'<section><h2>r/{html.escape(subreddit)}</h2>')
        if not posts:
            rows.append('<p class="empty">Geen posts gevonden.</p>')
        for post in posts:
            created = datetime.datetime.utcfromtimestamp(post["created_utc"]).strftime("%Y-%m-%d %H:%M UTC")

            comments_html = ""
            for c in post.get("comments", []):
                body = html.escape(c["body"]).replace("\n", "<br>")
                comments_html += (
                    f'<div class="comment">'
                    f'<span class="cmeta">u/{html.escape(c["author"])} · {c["score"]} pts</span>'
                    f'<p>{body}</p>'
                    f'</div>'
                )
            if not comments_html:
                comments_html = '<p class="empty">Geen comments geladen.</p>'

            selftext = ""
            if post["selftext"].strip():
                excerpt = html.escape(post["selftext"])
                ellipsis = "…" if len(post["selftext"]) == 300 else ""
                selftext = f'<p class="selftext">{excerpt}{ellipsis}</p>'

            rows.append(f"""
<article>
  <h3><a href="{html.escape(post['url'])}" target="_blank">{html.escape(post['title'])}</a></h3>
  <div class="meta">
    u/{html.escape(post['author'])} · {post['score']} pts · {post['num_comments']} comments · {created}
  </div>
  {selftext}
  <details>
    <summary>Top comments</summary>
    <div class="comments">{comments_html}</div>
  </details>
</article>""")
        rows.append('</section>')

    body = "\n".join(rows)
    return f"""<!DOCTYPE html>
<html lang="nl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>QuickReddit – {now}</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{
      font-family: system-ui, sans-serif;
      max-width: 860px;
      margin: 0 auto;
      padding: 1.5rem 1rem;
      background: #f6f7f8;
      color: #1c1c1c;
    }}
    h1 {{ font-size: 1.4rem; margin-bottom: 0.25rem; }}
    h2 {{
      font-size: 1.1rem;
      background: #ff4500;
      color: #fff;
      padding: 0.4rem 0.75rem;
      border-radius: 4px;
      margin: 2rem 0 0.75rem;
    }}
    article {{
      background: #fff;
      border: 1px solid #e0e0e0;
      border-radius: 6px;
      padding: 1rem;
      margin-bottom: 0.75rem;
    }}
    h3 {{ margin: 0 0 0.35rem; font-size: 1rem; }}
    h3 a {{ color: #0079d3; text-decoration: none; }}
    h3 a:hover {{ text-decoration: underline; }}
    .meta {{ font-size: 0.8rem; color: #666; margin-bottom: 0.5rem; }}
    .selftext {{
      font-size: 0.88rem; color: #333; margin: 0.5rem 0;
      border-left: 3px solid #e0e0e0; padding-left: 0.75rem;
    }}
    details {{ margin-top: 0.5rem; }}
    summary {{ cursor: pointer; font-size: 0.85rem; color: #555; user-select: none; }}
    .comments {{ margin-top: 0.5rem; }}
    .comment {{
      border-left: 3px solid #ff4500;
      padding: 0.4rem 0.6rem;
      margin-bottom: 0.5rem;
      background: #fafafa;
      border-radius: 0 4px 4px 0;
    }}
    .cmeta {{ font-size: 0.75rem; color: #888; display: block; margin-bottom: 0.2rem; }}
    .comment p {{ margin: 0; font-size: 0.85rem; line-height: 1.4; }}
    .empty {{ color: #999; font-size: 0.85rem; }}
    footer {{ margin-top: 2rem; font-size: 0.75rem; color: #aaa; text-align: center; }}
  </style>
</head>
<body>
  <h1>QuickReddit</h1>
  <p style="font-size:0.85rem;color:#666">Gegenereerd op {now} · {posts_per_sub} nieuwste posts per subreddit</p>
  {body}
  <footer>QuickReddit – alleen voor persoonlijk gebruik</footer>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="QuickReddit – dagelijks Reddit overzicht")
    parser.add_argument("--subreddits", nargs="+", default=SUBREDDITS,
                        help="Subreddits (default: dutchfire freelance webdev)")
    parser.add_argument("--posts", type=int, default=POSTS_PER_SUB,
                        help="Posts per subreddit (default: 25)")
    parser.add_argument("--output", default="reddit_report.html",
                        help="Output HTML bestand (default: reddit_report.html)")
    parser.add_argument("--no-comments", action="store_true",
                        help="Sla comments over (sneller)")
    args = parser.parse_args()

    subreddit_data = {}
    for sub in args.subreddits:
        print(f"  r/{sub} ophalen...", flush=True)
        try:
            posts = fetch_posts(sub, args.posts)
        except urllib.error.HTTPError as e:
            print(f"  Waarschuwing: r/{sub} overgeslagen (HTTP {e.code})", file=sys.stderr)
            subreddit_data[sub] = []
            continue

        if not args.no_comments:
            for post in posts:
                try:
                    post["comments"] = fetch_top_comments(post["id"], sub)
                    time.sleep(0.5)  # vriendelijk voor Reddit's servers
                except urllib.error.HTTPError:
                    post["comments"] = []

        subreddit_data[sub] = posts

    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), args.output)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(render_html(subreddit_data, args.posts))

    total = sum(len(v) for v in subreddit_data.values())
    print(f"\nKlaar! {total} posts → {output_path}")
    print(f"Open in browser: file://{output_path}")


if __name__ == "__main__":
    main()
