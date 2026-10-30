#!/usr/bin/env python3
"""
Local server that behaves like Cloudflare Pages, for previewing ../dist.

Pages serves /placing out of placing.html, and 308-redirects /placing.html back
to /placing. This does the same lookup so what you see locally is what ships.

  python3 site/serve.py [port]        # default 8000
"""

from __future__ import annotations

import functools
import http.server
import pathlib
import sys

DIST = pathlib.Path(__file__).resolve().parent.parent / "dist"


class PagesLike(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path: str) -> str:
        resolved = super().translate_path(path)
        if pathlib.Path(resolved).is_dir() or pathlib.Path(resolved).exists():
            return resolved
        # extensionless clean URL -> the .html file
        if pathlib.Path(resolved + ".html").exists():
            return resolved + ".html"
        return resolved

    def do_GET(self) -> None:
        raw = self.path.split("?")[0].split("#")[0]
        if raw.endswith(".html"):
            target = raw[: -len(".html")] or "/"
            if target.endswith("/index"):
                target = target[: -len("index")]
            self.send_response(308)
            self.send_header("Location", target + ("?" + self.path.split("?", 1)[1] if "?" in self.path else ""))
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        super().do_GET()

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("  %s\n" % (fmt % args))


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    if not DIST.is_dir():
        print(f"no {DIST} — run: python3 site/build.py", file=sys.stderr)
        return 1
    handler = functools.partial(PagesLike, directory=str(DIST))
    with http.server.ThreadingHTTPServer(("0.0.0.0", port), handler) as httpd:
        print(f"serving {DIST} on http://localhost:{port}/")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
