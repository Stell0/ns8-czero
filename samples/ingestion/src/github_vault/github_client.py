# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Official REST reads with durable per-page caching and bounded retries."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from .state import atomic, digest, log, now, read
from c0_ingest.http import open_url


class GitHubError(RuntimeError):
    def __init__(self, message, status=None, retryable=True):
        super().__init__(message)
        self.status = status
        self.retryable = retryable


class BudgetExceeded(GitHubError):
    pass


def token():
    value = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not value and shutil.which("gh"):
        proc = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
        if proc.returncode == 0:
            value = proc.stdout.strip()
    return value


class GitHub:
    def __init__(self, cache, config, resume=True, opener=None, sleeper=time.sleep):
        self.cache = Path(cache)
        self.config = config
        self.resume = resume
        self.opener = opener or open_url
        self.sleep = sleeper
        self.token = token()
        self.requests = 0
        self.cached = 0

    def get(self, path, params=None):
        url = path if path.startswith("https://") else "https://api.github.com" + path
        if params:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc != "api.github.com" or parsed.username or parsed.fragment:
            raise GitHubError("refusing non-GitHub API URL")
        target = self.cache / (digest(url) + ".json")
        content_response = "/git/blobs/" in parsed.path or parsed.path.endswith("/readme")
        saved = read(target) if self.resume and parsed.path != "/user" and not content_response else None
        if saved and saved.get("excluded_private"):
            raise GitHubError("private repository excluded", retryable=False)
        if saved and isinstance(saved.get("body"), dict) and saved["body"].get("incomplete_results"):
            saved = None
        if saved is not None:
            self.cached += 1
            if parsed.path == "/user":
                return {k: saved["body"][k] for k in ("login", "id", "html_url", "type") if k in saved["body"]}, saved["next"]
            return saved["body"], saved["next"]
        if self.requests >= self.config["max_requests"]:
            raise BudgetExceeded("configured GitHub request budget reached; resume with a larger budget")
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "github-vault/0.1", "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        for attempt in range(self.config["max_retries"] + 1):
            if self.requests >= self.config["max_requests"]:
                raise BudgetExceeded("configured GitHub request budget reached")
            self.requests += 1
            try:
                with self.opener(urllib.request.Request(url, headers=headers), timeout=40) as response:
                    body = json.load(response)
                    following = None
                    for part in response.headers.get("Link", "").split(","):
                        if 'rel="next"' in part:
                            following = part.split("<")[1].split(">")[0]
                    if isinstance(body, dict) and body.get("private"):
                        atomic(target, {"excluded_private": True, "url": url, "retrieved_at": now()})
                        raise GitHubError("private repository excluded", retryable=False)
                    # Strip private commit identity details before persisting public API responses.
                    if parsed.path == "/user":
                        body = {k: body[k] for k in ("login", "id", "html_url", "type") if k in body}
                    body = public_data(body)
                    if not content_response and (not isinstance(body, dict) or not body.get("incomplete_results")):
                        atomic(target, {"body": body, "next": following, "url": url, "retrieved_at": now()})
                    log("github_page", url=url, requests=self.requests, remaining=response.headers.get("X-RateLimit-Remaining"))
                    return body, following
            except urllib.error.HTTPError as exc:
                retryable = exc.code in (429, 500, 502, 503, 504) or (exc.code == 403 and (exc.headers.get("X-RateLimit-Remaining") == "0" or exc.headers.get("Retry-After")))
                wait = float(exc.headers.get("Retry-After", 2 ** attempt))
                if exc.headers.get("X-RateLimit-Remaining") == "0":
                    wait = max(wait, float(exc.headers.get("X-RateLimit-Reset", 0)) - time.time() + 1)
                if not retryable or attempt == self.config["max_retries"] or wait > self.config["max_wait_seconds"]:
                    raise GitHubError(f"GitHub HTTP {exc.code}: {parsed.path}", status=exc.code, retryable=retryable) from None
                log("github_retry", status=exc.code, wait=wait)
                self.sleep(max(0, wait))
            except (urllib.error.URLError, TimeoutError):
                if attempt == self.config["max_retries"]:
                    raise GitHubError("GitHub network failure; retry later") from None
                self.sleep(min(2 ** attempt, self.config["max_wait_seconds"]))
        raise GitHubError("retry exhausted")

    def pages(self, path, params=None):
        params = {"per_page": 100, **(params or {})}
        while path:
            body, following = self.get(path, params)
            if not isinstance(body, list):
                raise GitHubError("expected paginated list")
            yield from body
            path, params = following, None

    def search(self, kind, query, since, until):
        """Split by second on 1000-result ceilings; reject indivisible/incomplete results."""
        from datetime import datetime, timedelta
        qualifier = "author-date" if kind == "commits" else "created"
        q = f"{query} {qualifier}:{since}..{until}"
        path = f"/search/{kind}"
        body, following = self.get(path, {"q": q, "per_page": 100})
        if body.get("incomplete_results") or body["total_count"] > 1000:
            start = datetime.fromisoformat(since.replace("Z", "+00:00"))
            end = datetime.fromisoformat(until.replace("Z", "+00:00"))
            if end <= start:
                raise GitHubError("search ceiling remains at one-second partition")
            middle = start + timedelta(seconds=int((end - start).total_seconds()) // 2)
            fmt = lambda d: d.isoformat(timespec="seconds").replace("+00:00", "Z")
            return self.search(kind, query, since, fmt(middle)) + self.search(kind, query, fmt(middle + timedelta(seconds=1)), until)
        result = body["items"]
        while following:
            body, following = self.get(following)
            if body.get("incomplete_results"):
                raise GitHubError("GitHub search returned incomplete_results")
            result.extend(body["items"])
        if len(result) != body.get("total_count", len(result)):
            raise GitHubError("search count changed during pagination")
        return result


def public_data(value):
    if isinstance(value, list):
        return [public_data(v) for v in value]
    if isinstance(value, dict):
        return {k: public_data(v) for k, v in value.items() if k not in {"email", "verification", "text_matches", "body"}}
    return value
