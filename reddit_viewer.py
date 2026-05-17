#!/usr/bin/env python3
"""
QuickReddit - fetches top Reddit posts + nested comments, generates Claude summaries.
Requires: pip install anthropic
Requires: ANTHROPIC_API_KEY env var for summaries (skipped if absent)
"""

import json
import datetime
import argparse
import time
import urllib.request
import urllib.error
import os
import sys

SUBREDDITS = ["dutchfire", "freelance", "webdev"]
POSTS_PER_SUB = 10
TOP_LEVEL_LIMIT = 50
SUMMARY_MODEL = "claude-haiku-4-5-20251001"

USER_AGENT = "python:QuickReddit:v1.0 (personal daily digest; single user)"


def api_get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def fetch_posts(subreddit: str, limit: int, sort: str = "top", timeframe: str = "day") -> list[dict]:
    if sort == "top":
        url = f"https://www.reddit.com/r/{subreddit}/top.json?t={timeframe}&limit={limit}"
    else:
        url = f"https://www.reddit.com/r/{subreddit}/{sort}.json?limit={limit}"
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
            "selftext": p.get("selftext", "")[:500],
            "num_comments": p["num_comments"],
            "created_utc": p["created_utc"],
            "subreddit": subreddit,
        })
    return posts


def fetch_top_posts_24h(subreddit: str, limit: int) -> tuple[list[dict], str]:
    posts = fetch_posts(subreddit, limit, sort="top", timeframe="day")
    if posts:
        return posts, "top/dag"
    posts = fetch_posts(subreddit, limit, sort="hot")
    return posts, "hot"


def _parse_comment_children(children: list, level: int, per_level_limit: int) -> list[dict]:
    results = []
    for child in children:
        if len(results) >= per_level_limit:
            break
        if child.get("kind") == "more" or not child.get("data", {}).get("body"):
            continue
        c = child["data"]
        comment = {
            "author": c.get("author", "[deleted]"),
            "score": c.get("score", 0),
            "body": c.get("body", "")[:600],
            "level": level,
            "replies": [],
        }
        if level < 3:
            raw_replies = c.get("replies", "")
            if isinstance(raw_replies, dict):
                reply_children = raw_replies["data"]["children"]
                comment["replies"] = _parse_comment_children(reply_children, level + 1, per_level_limit)
        results.append(comment)
    return results


def fetch_comments(post_id: str, subreddit: str) -> list[dict]:
    url = (
        f"https://www.reddit.com/r/{subreddit}/comments/{post_id}.json"
        f"?limit={TOP_LEVEL_LIMIT}&sort=top&depth=3"
    )
    data = api_get(url)
    if len(data) < 2:
        return []
    return _parse_comment_children(data[1]["data"]["children"], level=1, per_level_limit=TOP_LEVEL_LIMIT)


def flatten_comments(comments: list[dict], max_chars: int = 8000) -> str:
    lines = []
    total = 0

    def walk(comments, indent=0):
        nonlocal total
        for c in comments:
            if total >= max_chars:
                return
            prefix = "  " * indent
            line = f"{prefix}[{c['score']} pts] u/{c['author']}: {c['body']}"
            lines.append(line)
            total += len(line)
            if c.get("replies"):
                walk(c["replies"], indent + 1)

    walk(comments)
    return "\n".join(lines)


def summarize(client, post: dict) -> str:
    comments_text = flatten_comments(post.get("comments", []))
    if not comments_text:
        return ""

    context = f"Post: {post['title']}"
    if post.get("selftext", "").strip():
        context += f"\n{post['selftext']}"

    msg = client.messages.create(
        model=SUMMARY_MODEL,
        max_tokens=400,
        messages=[{
            "role": "user",
            "content": (
                f"{context}\n\n"
                f"Discussie:\n{comments_text}\n\n"
                "Schrijf een scherpe samenvatting (4-6 zinnen) in het Nederlands. "
                "Belicht alle kanten: de consensus, de tegengeluiden, de scherpe of onverwachte standpunten, "
                "en wat er eventueel niet gezegd wordt. Good, bad, ugly — niets weglaten."
            )
        }]
    )
    return msg.content[0].text


def main():
    parser = argparse.ArgumentParser(description="QuickReddit")
    parser.add_argument("--subreddits", nargs="+", default=SUBREDDITS)
    parser.add_argument("--posts", type=int, default=POSTS_PER_SUB)
    parser.add_argument("--output", default="reddit_data.json")
    parser.add_argument("--no-summarize", action="store_true", help="Skip AI summaries")
    args = parser.parse_args()

    claude = None
    if not args.no_summarize:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            try:
                import anthropic
                claude = anthropic.Anthropic(api_key=api_key)
                print("Claude API beschikbaar, samenvattingen worden gegenereerd.")
            except ImportError:
                print("Waarschuwing: anthropic niet geinstalleerd, samenvattingen overgeslagen.", file=sys.stderr)
        else:
            print("Geen ANTHROPIC_API_KEY gevonden, samenvattingen overgeslagen.")

    result = {
        "fetched_at": datetime.datetime.utcnow().isoformat(),
        "subreddits": {}
    }

    for sub in args.subreddits:
        print(f"\nr/{sub} ophalen...", flush=True)
        try:
            posts, sort_used = fetch_top_posts_24h(sub, args.posts)
            if sort_used != "top/dag":
                print(f"  (fallback naar {sort_used})", flush=True)
        except urllib.error.HTTPError as e:
            print(f"  Overgeslagen (HTTP {e.code})", file=sys.stderr)
            result["subreddits"][sub] = []
            continue

        for i, post in enumerate(posts, 1):
            print(f"  [{i}/{len(posts)}] {post['title'][:55]}…", flush=True)
            try:
                post["comments"] = fetch_comments(post["id"], sub)
                time.sleep(0.5)
            except urllib.error.HTTPError:
                post["comments"] = []

            post["summary"] = ""
            if claude:
                try:
                    post["summary"] = summarize(claude, post)
                except Exception as e:
                    print(f"    Samenvatting mislukt: {e}", file=sys.stderr)

        result["subreddits"][sub] = posts

    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), args.output)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    total = sum(len(v) for v in result["subreddits"].values())
    print(f"\nKlaar! {total} posts → {output_path}")


if __name__ == "__main__":
    main()
