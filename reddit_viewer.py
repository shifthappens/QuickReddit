#!/usr/bin/env python3
"""
QuickReddit - fetches top Reddit posts + nested comments and saves to JSON.
Summaries are generated separately by Claude Code.
"""

import json
import datetime
import argparse
import time
import urllib.request
import urllib.error

SUBREDDITS = ["dutchfire", "werkzaken", "askreddit", "komoot", "todayilearned", "youshouldknow", "zuinig"]
POSTS_PER_SUB = 10
TOP_LEVEL_LIMIT = 50

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
            "summary": "",
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


def main():
    parser = argparse.ArgumentParser(description="QuickReddit — fetch only")
    parser.add_argument("--subreddits", nargs="+", default=SUBREDDITS)
    parser.add_argument("--posts", type=int, default=POSTS_PER_SUB)
    parser.add_argument("--output", default="reddit_data.json")
    args = parser.parse_args()

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
            print(f"  Overgeslagen (HTTP {e.code})")
            result["subreddits"][sub] = []
            continue

        for i, post in enumerate(posts, 1):
            print(f"  [{i}/{len(posts)}] {post['title'][:55]}…", flush=True)
            try:
                post["comments"] = fetch_comments(post["id"], sub)
                time.sleep(0.5)
            except urllib.error.HTTPError:
                post["comments"] = []

        result["subreddits"][sub] = posts

    import os
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), args.output)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    total = sum(len(v) for v in result["subreddits"].values())
    print(f"\nKlaar! {total} posts → {output_path}")
    print("Vraag Claude Code nu om samenvattingen te genereren.")


if __name__ == "__main__":
    main()
