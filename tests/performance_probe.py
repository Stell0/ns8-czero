# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded disposable HTTPS measurements with real response/citation checks."""
import json
import math
import time


def measure(browser, page, *, clock=time.perf_counter):
    started = clock()
    def request(path):
        status, body, _ = browser.api(path)
        if clock() - started > 60:
            raise AssertionError('Installed latency sample deadline exceeded')
        if status != 200 or not isinstance(body, bytes) or len(body) > 1024**2:
            raise AssertionError('Installed benchmark response unavailable')
        try:
            value = json.loads(body)
        except (ValueError, TypeError):
            raise AssertionError('Installed benchmark response invalid') from None
        if not isinstance(value, dict):
            raise AssertionError('Installed benchmark response invalid')
        return value

    listing = request('/api/v1/wiki/pages?limit=100')
    pages = listing.get('pages')
    if not isinstance(pages, list) or not 0 < len(pages) < 100:
        raise AssertionError('Benchmark corpus exceeds disclosure bound')
    measurements = {'visible_wiki_pages': len(pages)}
    query = '/api/v1/knowledge/search?query=independent+authored&kind=wiki&mode=text&rerank=off&graph_depth=0&limit=10'
    for name, path, count, ceiling in [('health', '/api/v1/health', 50, .5),
                                       ('wiki_text_search', query, 20, 1.0)]:
        samples = []
        for index in range(count + 2):
            before = clock()
            value = request(path)
            elapsed = clock() - before
            if elapsed < 0:
                raise AssertionError('Installed benchmark clock invalid')
            if name == 'health':
                if value.get('status') != 'ok' or value.get('service') != 'czero':
                    raise AssertionError('Benchmark health is not ready')
            else:
                hits = value.get('hits')
                if (value.get('retrieval_method') != 'text' or value.get('fallback_reason') is not None
                        or not isinstance(hits, list) or not any(
                            h.get('id') == page['content']['id'] and h.get('resource_id') == page['id']
                            and h.get('wiki', {}).get('revision') == 2
                            for h in hits if isinstance(h, dict))):
                    raise AssertionError('Benchmark text evidence or revision missing')
            if index >= 2:
                samples.append(elapsed)
        p95 = sorted(samples)[math.ceil(.95 * count) - 1]
        if p95 > ceiling:
            raise AssertionError('Installed ' + name + ' p95 target exceeded')
        measurements[name] = {'requests': count, 'warmups': 2,
                             'p95_ms': round(p95 * 1000, 3),
                             'maximum_ms': round(max(samples) * 1000, 3),
                             'mean_ms': round(sum(samples) * 1000 / count, 3)}
    return measurements
