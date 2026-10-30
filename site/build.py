#!/usr/bin/env python3
"""
Generate the 2026 site into ../dist, with the untouched 1996 archive at
../dist/1996/.

  reads    ../krazykat/            (read-only: the archive is never written)
  reads    ./assets/style.css
  writes   ../dist/               (gitignored, and the deploy target)

URLs are extensionless (/placing), which is what Cloudflare Pages serves from
placing.html. The change to the poems is structural only: <MENU>/<BR> soup
becomes one <p> per stanza. Every word is asserted to survive.

Run:  python3 site/build.py
"""

from __future__ import annotations

import html
import re
import shutil
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent       # site/
ROOT = HERE.parent                                   # repo root
SRC = ROOT / "krazykat" / "writing"                  # the archive
OUT = ROOT / "dist"                                  # deploy tree
CSS = HERE / "assets" / "style.css"
SITE = "Splayed fingers, hidden rings."
CONTACT = "mailto:deafmetal@gmail.com"

FAVICON = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E"
    "%3Crect width='16' height='16' fill='%23000040'/%3E"
    "%3Cpath d='M4 3v10M4 8l5-5M4 8l5 5' stroke='%23ccff00' stroke-width='1.6' fill='none'/%3E%3C/svg%3E"
)


# ---------------------------------------------------------------- extraction

def read(name: str) -> str:
    return (SRC / name).read_bytes().decode("latin-1").replace("\r", "\n")


def nav_items() -> list[tuple[str, str]]:
    """The author's own order, taken from the original contents pane."""
    raw = read("contents.html")
    items = []
    for href, label in re.findall(r'<A HREF="([^"]+)"[^>]*>(.*?)</A>', raw, re.S):
        text = re.sub(r"<BR>", " ", label, flags=re.I)
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        items.append((href, text))
    return items


def slug(href: str) -> str:
    """contents.html points at placing.b.html; the clean URL is /placing."""
    return re.sub(r"\.b\.html$", "", href)


def body_inner(name: str) -> tuple[str, str]:
    """Inner HTML of the last <body> in the file, plus the <title>."""
    raw = read(name)
    title = ""
    m = re.search(r"(?is)<title>(.*?)</title>", raw)
    if m:
        title = html.unescape(re.sub(r"\s+", " ", m.group(1))).strip()
    raw = re.sub(r"(?is)<script.*?</script>", "", raw)
    starts = [m.end() for m in re.finditer(r"(?i)<body[^>]*>", raw)]
    if not starts:
        return "", title
    inner = raw[starts[-1]:]
    inner = re.split(r"(?i)</body>", inner)[0]
    return inner, title


def words(fragment: str) -> list[str]:
    text = html.unescape(re.sub(r"<[^>]+>", " ", fragment))
    return re.findall(r"[A-Za-z0-9]+", text)


def fix_ampersands(fragment: str) -> str:
    parts = re.split(r"(<[^>]+>)", fragment)
    out = []
    for part in parts:
        if part.startswith("<"):
            out.append(part)
        else:
            out.append(re.sub(r"&(?![a-zA-Z][a-zA-Z0-9]*;|#\d+;|#x[0-9a-fA-F]+;)", "&amp;", part))
    return "".join(out)


def split_boilerplate(content: str) -> tuple[str, str]:
    """
    Cut the trailing <HR> + copyright line that ends every page.

    Every poem in the archive carries exactly one <HR>, at the END, followed by
    <FONT SIZE="-2"><TT>&copy;1996 Noah Christy Brown.</TT></FONT>. It is page
    furniture, not verse, so it is dropped -- but only when the tail really is
    that: a copyright sign and a handful of words.
    """
    last = None
    for m in re.finditer(r"(?i)<hr[^>]*>", content):
        last = m
    if last is None:
        return content, ""
    head, tail = content[: last.start()], content[last.end():]
    plain = re.sub(r"<[^>]+>", "", tail)
    if ("\u00a9" in tail or "&copy;" in tail.lower()) and len(plain.split()) <= 8:
        return head, tail
    return content, ""


def pre_block(content: str) -> tuple[str, str] | None:
    """
    Some poems are <PRE> pieces where the indentation is the poem: bombs, felt,
    timidity, until2. Those cannot be re-flowed into stanzas, so the text is
    returned verbatim (presentational tags removed, whitespace untouched).
    """
    m = re.search(r"(?is)<pre[^>]*>(.*?)</pre>", content)
    if not m:
        return None
    raw = m.group(1)
    inner = re.sub(r"(?i)</?(?:tt|pre|font[^>]*|u|center|nobr|b|i)\b[^>]*>", "", raw)
    inner = re.sub(r"(?i)<br\s*/?>", "\n", inner)
    body = inner.strip("\n").rstrip()
    text = html.escape(body, quote=False)
    assert html.unescape(text) == body          # exact, character for character
    return text, raw


def to_blocks(content: str) -> tuple[str, object, str]:
    """1996 tag soup -> ("pre", text, region) or ("verse", [stanzas], region)."""
    pre = pre_block(content)
    if pre is not None:
        text, region = pre
        return "pre", text, region

    poem, _tail = split_boilerplate(content)
    s = re.sub(r"(?is)<!--.*?-->", "", poem)

    # Mark breaks BEFORE touching line endings: the files are CR-only, so every
    # <BR> is followed by a real newline. Two or more <BR> in a row is a stanza
    # break; a single one is a line break.
    s = re.sub(r"(?is)(?:<br\s*/?>\s*){2,}", "\x01", s)
    s = re.sub(r"(?i)<br\s*/?>", "\x00", s)

    # An in-body heading only exists on the standalone .html copies; drop it.
    s = re.sub(r"(?is)^[\s<]*(?:<(?:blockquote|p|center|font[^>]*|b)>|\s)*?<b>[^<]*</b>",
               "", s, count=1)

    # Block-level junk that carries no text.
    s = re.sub(r"(?i)</?(?:blockquote|menu|center|p|font[^>]*|body|html|head|nobr|caption)\b[^>]*>",
               "", s)

    # Keep inline emphasis, normalise to 2026 elements.
    s = re.sub(r"(?i)<b\b[^>]*>", "<strong>", s)
    s = re.sub(r"(?i)</b\s*>", "</strong>", s)
    s = re.sub(r"(?i)<i\b[^>]*>", "<em>", s)
    s = re.sub(r"(?i)</i\s*>", "</em>", s)

    # Anything else is presentation-only.
    s = re.sub(r"<(?!/?(?:strong|em|a)\b)[^>]*>", "", s)
    s = fix_ampersands(s)
    s = re.sub(r"[ \t\r\n]+", " ", s).strip()

    stanzas = []
    for block in s.split("\x01"):
        lines = [line.strip() for line in block.split("\x00") if line.strip()]
        if lines:
            stanzas.append("<br>".join(lines))

    # Hard check, inside the converter: not one word may be lost.
    assert words("\n".join(stanzas)) == words(poem), "verse lost words in conversion"
    return "verse", stanzas, poem


# ---------------------------------------------------------------- rendering

def shell(*, doc_title: str, h1: str, body: str, active: str,
          nav: list[tuple[str, str]], subtitle: str = "", after: str = "") -> str:
    items = []
    for href, label in nav:
        target = slug(href)
        cur = ' aria-current="page"' if target == active else ""
        items.append(f'      <li><a href="{target}"{cur}>{html.escape(label)}</a></li>')
    nav_html = "\n".join(items)

    sub = f'\n        <p class="subtitle">{subtitle}</p>' if subtitle else ""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{doc_title}</title>
  <meta name="description" content="Poetry written 1995-1996 by Noah Christy Brown.">
  <meta name="color-scheme" content="light dark">
  <meta name="theme-color" content="#000040">
  <link rel="icon" href="{FAVICON}">
  <link rel="preload" href="assets/fonts/fandol-fang-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="assets/style.css">
</head>
<body>
  <a class="skip" href="#poem">Skip to the poem</a>

  <header class="band">
    <p class="site"><a href="./">{SITE}</a></p>
    <p class="tag">Poetry 1995&ndash;96</p>
  </header>

  <div class="shell">
    <nav class="works" aria-label="Works">
      <details open>
        <summary>Works <span class="count">{len(nav)}</span></summary>
        <ol>
{nav_html}
        </ol>
      </details>
    </nav>

    <main id="poem">
      <article>
        <h1>{h1}</h1>{sub}
{body}
      </article>
{after}
    </main>
  </div>

  <footer class="band">
    <p><a href="{CONTACT}">communicate</a></p>
    <p class="tag"><a href="1996/">1996 version</a> &middot; &copy; Noah Christy Brown, 1995&ndash;1996</p>
  </footer>
</body>
</html>
"""


def verse_html(stanzas: list[str]) -> str:
    return "\n".join(f"        <p>{s}</p>" for s in stanzas)


def pager_html(nav, index: int) -> str:
    prev_ = nav[index - 1] if index > 0 else None
    next_ = nav[index + 1] if index + 1 < len(nav) else None
    bits = ['      <nav class="pager" aria-label="Poems">']
    bits.append(f'        <a class="prev" href="{slug(prev_[0])}">&larr; {html.escape(prev_[1])}</a>'
                if prev_ else "        <span></span>")
    bits.append(f'        <a class="next" href="{slug(next_[0])}">{html.escape(next_[1])} &rarr;</a>'
                if next_ else "        <span></span>")
    bits.append("      </nav>")
    return "\n".join(bits)


def until_page() -> str:
    """until.b.html is itself a frameset; rebuild it as one page, three parts."""
    idx = read("until.i.html")
    parts = []
    for href, label in re.findall(r'<A HREF="([^"]+)"[^>]*>(.*?)</A>', idx, re.S):
        if not href.startswith(("until1", "until2", "until3")):
            continue
        title = re.sub(r"<[^>]+>", "", label)
        title = re.sub(r"\s+", " ", title).strip()
        content, _ = body_inner(href)
        kind, payload, region = to_blocks(content)
        if kind == "pre":
            body = f'          <pre class="concrete">{payload}</pre>'
        else:
            assert words("\n".join(payload)) == words(region), f"{href}: content changed"
            body = "\n".join(f"          <p>{s}</p>" for s in payload)
        parts.append(f"        <section>\n          <h2>{html.escape(title)}</h2>\n"
                     + body
                     + "\n        </section>")
    return '        <div class="parts">\n' + "\n".join(parts) + "\n        </div>"


def write_specimen(stanza: str) -> None:
    """A page for judging the fangsong question on the reader's own screen."""
    samples = [
        ("A", "system serif verse + system sans UI", "", "the shipped default"),
        ("B", "fangsong verse, sans UI", "fangv", "poems only"),
        ("C", "fangsong everywhere", "fangall", "verse, headings, nav labels"),
        ("D", "fangsong UI, serif verse", "fangui", "the inverse"),
    ]
    blocks = []
    for letter, caption, cls, note in samples:
        blocks.append(f"""    <section class="{cls}">
      <p class="lbl">{letter} &mdash; {caption} <span>({note})</span></p>
      <p class="ui"><span>Works 25</span><span>Poetry 1995&ndash;96</span><span>communicate</span></p>
      <h2>Placing</h2>
      <p class="v">{stanza}</p>
      <p class="v"><strong>bold</strong> &middot; <em>italic</em> &middot; &ldquo;quotes&rdquo; &middot; 1,234</p>
    </section>""")

    (OUT / "type.html").write_text(f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Type specimen — {SITE}</title>
  <meta name="color-scheme" content="light dark">
  <link rel="icon" href="{FAVICON}">
  <link rel="stylesheet" href="assets/style.css">
  <style>
    .spec {{ display: grid; gap: 1rem; padding: var(--pad); max-width: 78rem; margin-inline: auto; }}
    .spec section {{ border: 1px solid var(--rule); border-radius: .6rem; padding: 1rem 1.25rem; }}
    .spec .lbl {{ margin: 0 0 .9rem; font-size: .72rem; letter-spacing: .09em; text-transform: uppercase; opacity: .75; }}
    .spec .lbl span {{ text-transform: none; letter-spacing: 0; opacity: .7; }}
    .spec .ui {{ display: flex; flex-wrap: wrap; gap: .5rem 1.25rem; margin: 0 0 .9rem;
                 font-size: .72rem; letter-spacing: .09em; text-transform: uppercase; opacity: .8; }}
    .spec h2 {{ font: 600 1.4rem/1.2 var(--ui); margin: 0 0 .8rem; }}
    .spec .v {{ font-size: 1.05rem; line-height: 1.75; margin: 0 0 .7rem; }}
    .spec .note {{ padding: 0 var(--pad) 2rem; max-width: 78rem; margin-inline: auto; font-size: .85rem; opacity: .8; }}
    .fangv .v                 {{ font-family: var(--fang); }}
    .fangall .v, .fangall h2,
    .fangall .ui, .fangall .lbl {{ font-family: var(--fang); }}
    .fangui .ui, .fangui h2   {{ font-family: var(--fang); }}
  </style>
</head>
<body>
  <header class="band">
    <p class="site"><a href="./">{SITE}</a></p>
    <p class="tag">Type specimen</p>
  </header>
  <main class="spec">
{chr(10).join(blocks)}
  </main>
  <p class="note">Next: <a href="sans">the seven sans options for the chrome &rarr;</a>
  &middot; <a href="fang">system fangsong vs the self-hosted subset &rarr;</a></p>
  <p class="note">Rendered by your browser, so this is the real answer for your
  machine. Stack under test: <code>--fang</code> = 
  <code>\"FangSong\", \"仿宋\", \"STFangsong\", \"FandolFang\", fangsong, serif</code>.
  If all four sections look alike, no fangsong is installed &mdash; which is what
  most Linux and Android readers would see.</p>
</body>
</html>
""", encoding="utf-8")


SANS_OPTIONS = [
    ("system-ui",
     'system-ui, -apple-system, "Segoe UI Variable Text", "Segoe UI", Roboto, sans-serif',
     "what ships today",
     "Win: Segoe UI Variable &middot; macOS: SF Pro &middot; Linux: distro default"),
    ("Helvetica / Arial",
     '"Helvetica Neue", Helvetica, Arial, "Liberation Sans", sans-serif',
     "the neo-grotesque default of the web",
     "Win + macOS native &middot; Linux: Liberation Sans, metrically identical to Arial"),
    ("Verdana",
     'Verdana, Geneva, "DejaVu Sans", sans-serif',
     "1996 period piece",
     "designed for screens, huge x-height, still legible at 11px &middot; Linux: DejaVu Sans"),
    ("Tahoma",
     'Tahoma, Verdana, Geneva, "DejaVu Sans", sans-serif',
     "1996 period piece, compact",
     "narrower than Verdana, tighter tracking &middot; Linux: DejaVu Sans"),
    ("Trebuchet MS",
     '"Trebuchet MS", "DejaVu Sans", sans-serif',
     "1996 period piece, humanist",
     "warm, slightly quirky lowercase &middot; no faithful Linux equivalent"),
    ("Bahnschrift",
     'Bahnschrift, "DIN 2014", "DIN Alternate", "DejaVu Sans Condensed", sans-serif',
     "technical grotesque, railway-signage DIN",
     "Win 10+ variable font &middot; macOS/Linux fall back"),
    ("ui-monospace",
     'ui-monospace, "Cascadia Mono", "SF Mono", Menlo, Consolas, monospace',
     "typed / archival",
     "pairs with the concrete poems &middot; Win: Cascadia Mono &middot; macOS: SF Mono"),
]


def write_sans_specimen(stanza: str) -> None:
    """The same chrome block seven ways, verse held at fangsong so the pairing shows."""
    cards = []
    for i, (name, stack, note, avail) in enumerate(SANS_OPTIONS, start=1):
        cards.append(f"""    <section class="card k{i}">
      <p class="meta">{i} &middot; <b>{name}</b> &mdash; <i>{note}</i></p>
      <div class="demo">
        <div class="band"><span class="site">Splayed fingers, hidden rings.</span><span class="tag">Poetry 1995&ndash;96</span></div>
        <div class="cols">
          <ul class="nav"><li>01&nbsp; Placing</li><li class="on">02&nbsp; Woodstock</li><li>03&nbsp; Fluxus</li><li>04&nbsp; Bombs</li></ul>
          <div>
            <h3>Woodstock</h3>
            <p class="v">{stanza}</p>
            <p class="pg"><span>&larr; Placing</span><span>Fluxus &rarr;</span></p>
          </div>
        </div>
        <div class="band foot"><span>communicate</span><span class="tag">1996 version</span></div>
      </div>
      <p class="avail">{avail}</p>
    </section>""")

    css_vars = "\n".join(f"    .k{i} {{ --ui: {stack}; }}"
                          for i, (_n, stack, _no, _a) in enumerate(SANS_OPTIONS, start=1))

    (OUT / "sans.html").write_text(f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Sans options &mdash; {SITE}</title>
  <meta name="color-scheme" content="light dark">
  <link rel="icon" href="{FAVICON}">
  <link rel="stylesheet" href="assets/style.css">
  <style>
{css_vars}
    .sans {{ display: grid; gap: 1.1rem; padding: var(--pad); max-width: 96rem; margin-inline: auto; }}
    @media (min-width: 72rem) {{ .sans {{ grid-template-columns: 1fr 1fr; }} }}
    .card {{ border: 1px solid var(--rule); border-radius: .6rem; padding: .85rem 1rem 1rem; }}
    .card .meta {{ margin: 0 0 .7rem; font-size: .72rem; letter-spacing: .08em; text-transform: uppercase; opacity: .8; }}
    .card .meta b {{ letter-spacing: 0; text-transform: none; font-size: .88rem; }}
    .card .meta i {{ font-style: normal; opacity: .7; }}
    .card .avail {{ margin: .6rem 0 0; font-size: .72rem; opacity: .65; font-family: var(--ui); }}
    .demo {{ border: 1px solid var(--rule); border-radius: .45rem; overflow: hidden; background: var(--paper); color: var(--ink); }}
    .demo > * {{ font-family: var(--ui); }}
    .demo .band {{ background: var(--band); color: var(--band-ink); padding: .5rem .7rem;
                   display: flex; justify-content: space-between; gap: 1rem; font-size: .82rem; }}
    .demo .band .site {{ font-weight: 600; }}
    .demo .band .tag {{ opacity: .75; }}
    .demo .cols {{ display: grid; grid-template-columns: 8.5rem 1fr; gap: 1rem; padding: .85rem .7rem .7rem; }}
    .demo .nav {{ list-style: none; margin: 0; padding: 0; font-size: .82rem; }}
    .demo .nav li {{ padding: .12rem .35rem; border-radius: .25rem; }}
    .demo .nav li.on {{ background: var(--accent); color: #000040; font-weight: 600; }}
    .demo h3 {{ margin: 0 0 .55rem; font: 600 1.15rem/1.2 var(--ui); }}
    .demo .v {{ margin: 0 0 .6rem; font-family: var(--fang); font-size: .92rem; line-height: 1.65; }}
    .demo .pg {{ display: flex; justify-content: space-between; margin: 0; padding-top: .5rem;
                 border-top: 1px solid var(--rule); font-size: .74rem; }}
    .legend {{ padding: 0 var(--pad) 2rem; max-width: 96rem; margin-inline: auto; font-size: .85rem; opacity: .8; }}
  </style>
</head>
<body>
  <header class="band">
    <p class="site"><a href="./">{SITE}</a></p>
    <p class="tag"><a href="type">&larr; verse specimen</a></p>
  </header>
  <main class="sans">
{chr(10).join(cards)}
  </main>
  <p class="legend">Verse is held at fangsong in every card, so you are judging only
  the chrome. Cards that look identical mean those fonts are absent on this
  machine. Three of these are 1996-vintage (Verdana, Tahoma, Trebuchet), which is
  the period-accurate answer; the rest are neutral or technical.</p>
</body>
</html>
""", encoding="utf-8")


def write_fang_specimen(stanza: str) -> None:
    """System fangsong vs the self-hosted Fandol subset, so the swap is visible."""
    pangram = ("The quick brown fox &mdash; jumps &lsquo;over&rsquo; &ldquo;lazy&rdquo; "
               "dogs 1,234.5 + 6% [x]")
    (OUT / "fang.html").write_text(f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Fangsong comparison &mdash; {SITE}</title>
  <meta name="color-scheme" content="light dark">
  <link rel="icon" href="{FAVICON}">
  <link rel="stylesheet" href="assets/style.css">
  <style>
    .cmp {{ margin: 0; padding: var(--pad); border-bottom: 1px solid var(--rule); }}
    .cmp .lbl {{ margin: 0 0 1rem; font: 400 .75rem/1.5 var(--ui); letter-spacing: .06em;
                 text-transform: uppercase; opacity: .75; }}
    .cmp .lbl b {{ color: inherit; }}
    .cmp .v {{ margin: 0 0 1rem; font-size: 1.15rem; line-height: 1.8; }}
    .cmp .pg {{ margin: 0; font-size: .8rem; opacity: .7; }}
    .sys .v {{ font-family: var(--fang-sys); }}
    .web .v {{ font-family: "Fandol Fang", var(--fang-sys); }}
    .web {{ background: color-mix(in oklab, var(--accent) 8%, transparent); }}
  </style>
</head>
<body>
  <header class="band">
    <p class="site"><a href="./">{SITE}</a></p>
    <p class="tag"><a href="type">&larr; verse</a> &middot; <a href="sans">sans</a></p>
  </header>

  <section class="cmp sys">
    <p class="lbl">A &mdash; system fangsong: SimFang on Windows, STFangsong on macOS,
    <b>nothing at all</b> on Linux and Android</p>
    <p class="v">{stanza}</p>
    <p class="v pg">{pangram}</p>
  </section>

  <section class="cmp web">
    <p class="lbl">B &mdash; Fandol Fang, self-hosted subset (9.7 KB) &mdash; the same file everywhere</p>
    <p class="v">{stanza}</p>
    <p class="v pg">{pangram}</p>
  </section>

  <p class="legend" style="padding: var(--pad); max-width: 72rem; margin-inline: auto; font: 400 .85rem/1.6 var(--ui); opacity: .8">
  Both sections are the same words. On Windows the two differ: SimFang's Latin is
  a lighter, slightly angled face; Fandol's is a Times-proportioned serif with
  real kerning. Shipping B is what makes Linux and Android see fangsong at all
  &mdash; the cost is that Windows stops seeing SimFang. If you prefer A on
  Windows, swap <code>--fang</code> to <code>var(--fang-sys), "Fandol Fang"</code>
  and every platform keeps its local face, at the price of platform drift.</p>
</body>
</html>
""", encoding="utf-8")


# ---------------------------------------------------------------- main

def main() -> int:
    nav = nav_items()
    report = []

    # fresh deploy tree
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "assets").mkdir(parents=True)
    shutil.copyfile(CSS, OUT / "assets" / "style.css")
    fonts = HERE / "assets" / "fonts"
    if fonts.is_dir():
        shutil.copytree(fonts, OUT / "assets" / "fonts")

    # Pages serves everything with max-age=0 by default; the font never changes.
    # Keep these two patterns disjoint: Pages concatenates every rule that
    # matches, and an overlapping pair produced two Cache-Control directives.
    (OUT / "_headers").write_text(
        "/assets/fonts/*\n  Cache-Control: public, max-age=31536000, immutable\n"
        "/assets/style.css\n  Cache-Control: public, max-age=3600\n",
        encoding="utf-8")
    # the archive is copied byte-for-byte to /1996/
    shutil.copytree(ROOT / "krazykat", OUT / "1996")

    # index / introduction
    content, _ = body_inner("intro.html")
    kind, stanzas, region = to_blocks(content)
    assert kind == "verse" and words("\n".join(stanzas)) == words(region)
    body = "        <div class=\"prose\">\n" + "\n".join(f"          <p>{s}</p>" for s in stanzas) + "\n        </div>"
    (OUT / "index.html").write_text(
        shell(doc_title=f"Introduction — {SITE}", h1="Introduction", body=body,
              active="", nav=nav), encoding="utf-8")
    report.append(("index", len(words(" ".join(stanzas))), 0))

    specimen = None
    for i, (href, label) in enumerate(nav):
        target = slug(href)
        raw = read(href)
        if re.search(r"(?i)<frameset", raw):
            body = until_page()
            out = shell(doc_title=f"{label} — {SITE}", h1=html.escape(label), body=body,
                        active=target, nav=nav, after=pager_html(nav, i))
            (OUT / f"{target}.html").write_text(out, encoding="utf-8")
            report.append((target, -1, -1))
            continue

        content, doc_title = body_inner(href)
        kind, payload, region = to_blocks(content)
        if kind == "pre":
            body = f'        <div class="verse">\n          <pre class="concrete">{payload}</pre>\n        </div>'
            final = words(payload)
        else:
            assert words("\n".join(payload)) == words(region), f"{href}: text changed"
            body = f'        <div class="verse">\n{verse_html(payload)}\n        </div>'
            final = words("\n".join(payload))
            if target == "placing" and specimen is None:
                specimen = payload[0]
        dropped = 0
        report.append((target, len(final), dropped))

        (OUT / f"{target}.html").write_text(
            shell(doc_title=f"{label} — {SITE}", h1=html.escape(label), body=body,
                  active=target, nav=nav, after=pager_html(nav, i)), encoding="utf-8")

    # side-by-side comparison against the untouched original
    (OUT / "compare.html").write_text(f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>1996 vs 2026 — {SITE}</title>
  <meta name="color-scheme" content="light dark">
  <link rel="icon" href="{FAVICON}">
  <style>
    :root {{ color-scheme: light dark; --ink: light-dark(#000040,#e6e6f2); --paper: light-dark(#fff,#08081a); }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font: 13px/1.5 ui-sans-serif, system-ui, sans-serif; background: var(--paper); color: var(--ink); }}
    header {{ display: flex; flex-wrap: wrap; gap: .5rem 1.5rem; align-items: baseline; padding: .6rem 1rem; border-bottom: 1px solid currentColor; }}
    header b {{ font-size: .8rem; letter-spacing: .08em; text-transform: uppercase; }}
    .wrap {{ display: grid; grid-template-columns: 1fr; height: calc(100dvh - 3rem); }}
    @media (min-width: 50rem) {{ .wrap {{ grid-template-columns: 1fr 1fr; }} }}
    section {{ display: grid; grid-template-rows: auto 1fr; min-height: 0; border-right: 1px solid currentColor; }}
    section h2 {{ margin: 0; padding: .35rem .75rem; font-size: .72rem; letter-spacing: .08em; text-transform: uppercase; opacity: .7; }}
    iframe {{ width: 100%; height: 100%; border: 0; background: #fff; }}
  </style>
</head>
<body>
  <header>
    <b>1996 frameset</b> <span>vs</span> <b>2026 layout</b>
    <span style="margin-left:auto"><a href="./">open the new version &rarr;</a></span>
  </header>
  <div class="wrap">
    <section>
      <h2>Original &mdash; /1996/writing/scrawlz</h2>
      <iframe src="1996/writing/scrawlz" title="The original 1996 frameset"></iframe>
    </section>
    <section>
      <h2>2026 &mdash; /placing</h2>
      <iframe src="placing" title="The 2026 layout"></iframe>
    </section>
  </div>
</body>
</html>
""", encoding="utf-8")

    # Cloudflare Pages routing: for a day the 1996 frameset owned the root.
    (OUT / "_redirects").write_text(
        "# For one day the 1996 frameset was the whole site; it now lives under /1996/.\n"
        "/writing/*  /1996/writing/:splat  301\n"
        "/images/*   /1996/images/:splat   301\n",
        encoding="utf-8")

    write_specimen(specimen or "girl in red lapel leather<br>and sweet sickly smell")
    write_sans_specimen(specimen or "girl in red lapel leather<br>and sweet sickly smell")
    write_fang_specimen(specimen or "girl in red lapel leather<br>and sweet sickly smell")

    print(f"{'page':22} {'words':>6}")
    total = 0
    for name, n, _dropped in report:
        print(f"{name:22} {n if n >= 0 else '-':>6}")
        total += max(n, 0)
    print(f"\n{len(report)} pages, {total} words of verse, all asserted identical to the originals")
    return 0


if __name__ == "__main__":
    sys.exit(main())
