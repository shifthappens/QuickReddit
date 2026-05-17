#!/usr/bin/env python3
"""
QuickReddit - fetches top Reddit posts + nested comments, generates summaries via LLM, saves to JSON.
"""

import json
import datetime
import argparse
import time
import os
import threading
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

SUBREDDITS = ["dutchfire", "werkzaken", "askreddit", "komoot", "todayilearned", "youshouldknow", "zuinig"]
POSTS_PER_SUB = 10
TARGET_COMMENTS = 30
MIN_COMMENTS = 5
TOP_LEVEL_LIMIT = 100  # initieel ophalen, daarna bijladen indien nodig

USER_AGENT = "python:QuickReddit:v1.0 (personal daily digest; single user)"

# --- LLM configuratie (makkelijk te wisselen) ---
LLM_API_URL = "https://openrouter.ai/api/v1/chat/completions"
LLM_MODEL = "deepseek/deepseek-v4-flash"  # OpenRouter model ID
LLM_API_KEY_ENV = "OPENROUTER_API_KEY"
LLM_ENABLED = True   # zet op False om samenvattingen over te slaan
LLM_WORKERS = 5      # aantal parallelle samenvattingen


def _build_summary_request(post: dict, api_key: str) -> urllib.request.Request:
    top_comments = []
    for c in post.get("comments", [])[:10]:
        if c.get("body"):
            top_comments.append(f"- {c['body'][:400]}")
    prompt = (
        f"Subreddit: r/{post['subreddit']}\n"
        f"Titel: {post['title']}\n"
        f"Post: {post.get('selftext', '') or '(geen tekst)'}\n"
        f"Top comments:\n" + "\n".join(top_comments or ["(geen comments)"])
        + "\n\nGeef een samenvatting in het Nederlands van maximaal 100 woorden. Beschrijf waar de post over gaat en geef een genuanceerd beeld van de verschillende standpunten uit de reacties, inclusief afwijkende meningen. Eindig altijd met een volledige zin. Geen opsommingstekens."
    )
    payload = json.dumps({
        "model": LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 2000,
        "include_reasoning": False,
    }).encode()
    return urllib.request.Request(
        LLM_API_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://github.com/coen/quickreddit",
        },
    )


def llm_summarize(post: dict, index: int, total: int, attempt: int = 1) -> "tuple[str | None, list[str]]":
    """Returns (summary | None, log_lines)."""
    log = []
    api_key = os.environ.get(LLM_API_KEY_ENV, "")
    if not api_key:
        log.append(f"  samenvatting overgeslagen ({LLM_API_KEY_ENV} niet ingesteld)")
        return "", log

    label = f"[{index}/{total}]" + (f" poging {attempt}" if attempt > 1 else "")
    t0 = time.time()
    try:
        req = _build_summary_request(post, api_key)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            content = data["choices"][0]["message"].get("content") or data["choices"][0].get("text", "")
            elapsed = time.time() - t0
            if not content:
                log.append(f"  samenvatting {label}: leeg antwoord ({elapsed:.1f}s)")
                log.append(f"    debug: {json.dumps(data)[:200]}")
                return None, log
            words = len(content.split())
            log.append(f"  samenvatting {label}: klaar ({elapsed:.1f}s, {words} woorden)")
            return content.strip(), log
    except urllib.error.HTTPError as e:
        elapsed = time.time() - t0
        body = e.read().decode(errors="replace")[:200]
        log.append(f"  samenvatting {label}: HTTP {e.code} ({elapsed:.1f}s) — {body}")
        return None, log
    except Exception as e:
        elapsed = time.time() - t0
        log.append(f"  samenvatting {label}: fout ({elapsed:.1f}s): {e}")
        return None, log


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


def _parse_comment_children(children: list, level: int) -> tuple[list[dict], list[str]]:
    """Returns (parsed comments, more_ids for top-level 'more' objects)."""
    results = []
    more_ids = []
    for child in children:
        if child.get("kind") == "more":
            if level == 1:
                more_ids.extend(child.get("data", {}).get("children", []))
            continue
        if not child.get("data", {}).get("body"):
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
                comment["replies"], _ = _parse_comment_children(raw_replies["data"]["children"], level + 1)
        results.append(comment)
    return results, more_ids


def fetch_more_comments(post_id: str, more_ids: list[str]) -> list[dict]:
    ids = ",".join(more_ids[:100])
    url = (
        f"https://api.reddit.com/api/morechildren"
        f"?link_id=t3_{post_id}&children={ids}&api_type=json&limit_children=false&sort=top"
    )
    try:
        data = api_get(url)
        things = data.get("json", {}).get("data", {}).get("things", [])
        comments = []
        for t in things:
            if t.get("kind") != "t1":
                continue
            c = t["data"]
            if c.get("depth", 1) != 0:
                continue
            comments.append({
                "author": c.get("author", "[deleted]"),
                "score": c.get("score", 0),
                "body": c.get("body", "")[:600],
                "level": 1,
                "replies": [],
            })
        return comments
    except Exception:
        return []


def fetch_comments(post_id: str, subreddit: str) -> list[dict]:
    url = (
        f"https://www.reddit.com/r/{subreddit}/comments/{post_id}.json"
        f"?limit={TOP_LEVEL_LIMIT}&sort=top&depth=3"
    )
    data = api_get(url)
    if len(data) < 2:
        return []
    comments, more_ids = _parse_comment_children(data[1]["data"]["children"], level=1)

    if len(comments) < TARGET_COMMENTS and more_ids:
        extra = fetch_more_comments(post_id, more_ids)
        comments.extend(extra)

    return comments


def main():
    parser = argparse.ArgumentParser(description="QuickReddit — fetch + summarize")
    parser.add_argument("--subreddits", nargs="+", default=SUBREDDITS)
    parser.add_argument("--posts", type=int, default=POSTS_PER_SUB)
    parser.add_argument("--output", default="reddit_data.json")
    parser.add_argument("--no-summaries", action="store_true", help="Sla LLM-samenvattingen over")
    args = parser.parse_args()

    summarize = LLM_ENABLED and not args.no_summaries
    script_start = time.time()
    total_subs = len(args.subreddits)
    failed_posts: list[tuple[dict, int, int]] = []  # (post, index, total)

    print(f"QuickReddit — {total_subs} subreddits, max {args.posts} posts/sub", flush=True)
    if summarize:
        print(f"Samenvattingen: {LLM_MODEL} via {LLM_API_URL}", flush=True)
    else:
        print("Samenvattingen: uitgeschakeld", flush=True)

    result = {
        "fetched_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "subreddits": {}
    }

    for sub_i, sub in enumerate(args.subreddits, 1):
        sub_start = time.time()
        print(f"\n[{sub_i}/{total_subs}] r/{sub}", flush=True)
        try:
            print(f"  posts ophalen...", end=" ", flush=True)
            t0 = time.time()
            posts, sort_used = fetch_top_posts_24h(sub, args.posts)
            print(f"{len(posts)} posts ({time.time()-t0:.1f}s, {sort_used})", flush=True)
        except urllib.error.HTTPError as e:
            print(f"overgeslagen (HTTP {e.code})", flush=True)
            result["subreddits"][sub] = []
            continue

        for i, post in enumerate(posts, 1):
            print(f"  [{i}/{len(posts)}] {post['title'][:60]}", flush=True)
            try:
                print(f"    comments ophalen...", end=" ", flush=True)
                t0 = time.time()
                post["comments"] = fetch_comments(post["id"], sub)
                n = len(post['comments'])
                print(f"{n} comments ({time.time()-t0:.1f}s)", flush=True)
                time.sleep(0.5)
            except urllib.error.HTTPError as e:
                print(f"mislukt (HTTP {e.code})", flush=True)
                post["comments"] = []

            if len(post["comments"]) < MIN_COMMENTS:
                print(f"    overgeslagen (te weinig comments: {len(post['comments'])})", flush=True)

        posts = [p for p in posts if len(p.get("comments", [])) >= MIN_COMMENTS]

        if summarize and posts:
            n = len(posts)
            print(f"  samenvattingen genereren ({n} posts, {LLM_WORKERS} parallel)...", flush=True)
            t0 = time.time()
            print_lock = threading.Lock()
            done_count = 0

            def _progress_bar(done, total):
                filled = int(20 * done / total)
                bar = "=" * filled + "-" * (20 - filled)
                return f"  [{bar}] {done}/{total}"

            def _summarize_task(post, i, total):
                return post, i, *llm_summarize(post, i, total)

            with ThreadPoolExecutor(max_workers=LLM_WORKERS) as ex:
                futures = {ex.submit(_summarize_task, post, i, n): post
                           for i, post in enumerate(posts, 1)}
                for future in as_completed(futures):
                    post, i, summary, log_lines = future.result()
                    done_count += 1
                    with print_lock:
                        for line in log_lines:
                            print(line, flush=True)
                        print(_progress_bar(done_count, n), flush=True)
                    if summary is None:
                        failed_posts.append((post, i, n))
                    else:
                        post["summary"] = summary

            print(f"  samenvattingen klaar in {time.time()-t0:.1f}s", flush=True)

        sub_elapsed = time.time() - sub_start
        print(f"  r/{sub} klaar in {sub_elapsed:.1f}s ({len(posts)} posts opgeslagen)", flush=True)
        result["subreddits"][sub] = posts

    if failed_posts:
        print(f"\nHerpogingen ({len(failed_posts)} mislukte samenvattingen)...", flush=True)
        print_lock = threading.Lock()
        with ThreadPoolExecutor(max_workers=LLM_WORKERS) as ex:
            futures = {ex.submit(llm_summarize, post, i, total, 2): post
                       for post, i, total in failed_posts}
            for future in as_completed(futures):
                post = futures[future]
                summary, log_lines = future.result()
                with print_lock:
                    for line in log_lines:
                        print(line, flush=True)
                if summary is None:
                    print(f"  mislukt na 2 pogingen: {post['title'][:60]}", flush=True)
                    post["summary"] = "[Samenvatting niet beschikbaar]"
                else:
                    post["summary"] = summary

    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), args.output)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    total_posts = sum(len(v) for v in result["subreddits"].values())
    total_elapsed = time.time() - script_start
    print(f"\nKlaar! {total_posts} posts in {total_elapsed:.0f}s → {output_path}")


if __name__ == "__main__":
    main()
