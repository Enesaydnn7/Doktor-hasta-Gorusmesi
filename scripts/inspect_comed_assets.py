#!/usr/bin/env python3
"""Search the public COMED SPA bundles without reading browser credentials."""

from __future__ import annotations

import concurrent.futures
import html.parser
import sys
import urllib.parse
import urllib.request


class Scripts(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.sources: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script":
            value = dict(attrs).get("src")
            if value:
                self.sources.append(value)


def fetch(url: str) -> tuple[str, str]:
    with urllib.request.urlopen(url, timeout=60) as response:
        return url, response.read().decode("utf-8", errors="replace")


def main() -> int:
    root = (sys.argv[1] if len(sys.argv) > 1 else
            "https://goztepetest.comed.mlpcare.com/tr-tr/medical/")
    needles = sys.argv[2:] or [
        "Sistem Sorgulama",
        "Sistem Sorgusu",
        "Komplikasyon Sonrası Ex",
        "saveDocumentProcesses",
    ]
    _, page = fetch(root)
    parser = Scripts()
    parser.feed(page)
    urls = [urllib.parse.urljoin(root, source) for source in parser.sources]
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        for url, source in pool.map(fetch, urls):
            for needle in needles:
                folded = source.casefold()
                start_at = 0
                for occurrence in range(1, 9):
                    index = folded.find(needle.casefold(), start_at)
                    if index < 0:
                        break
                    start = max(0, index - 700)
                    end = min(len(source), index + len(needle) + 1400)
                    print(
                        f"\n=== {needle} #{occurrence} @ {url} ({index}) ===\n"
                        f"{source[start:end]}"
                    )
                    start_at = index + len(needle)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
