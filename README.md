# kkpoetry

Poetry written 1995–96 by Noah Christy Brown, published as two things at once:

- **`/`** — the same poems in 2026 markup: semantic landmarks instead of a
  frameset, fangsong verse, monospace chrome, fluid layout, no JavaScript and
  no webfonts.
- **`/1996/`** — the original site, byte-for-byte as it was, frameworks and all.

Live at <https://kkpoetry.pages.dev>.

## Layout

```
krazykat/          the 1996 archive: 93 HTML pages + 3 GIFs, never modified
site/build.py      generator: reads krazykat/, writes dist/
site/assets/       the stylesheet
site/serve.py      local server that mimics Cloudflare Pages' URL handling
dist/              build output = the deploy target (gitignored)
```

## Build and preview

```sh
python3 site/build.py     # krazykat/ -> dist/, archive copied to dist/1996/
python3 site/serve.py     # http://localhost:8000
```

`serve.py` reproduces Pages' behaviour so local matches production: `/placing`
serves `placing.html`, and `/placing.html` 308s back to `/placing`.

Every poem is asserted at build time to be **word-for-word** the original. The
build fails rather than silently dropping text.

Two specimen pages exist for typography decisions and are disposable:

- `/type` — fangsong vs serif verse
- `/sans` — seven chrome options

## Deploying

Cloudflare Pages, project `kkpoetry`, direct upload (not git-connected — the
Cloudflare GitHub App is not installed on the account, so pushing does not
deploy):

```sh
npx wrangler pages deploy dist --project-name kkpoetry --branch main
```

`dist/_redirects` forwards the old root-level 1996 URLs to the archive:

```
/writing/*  /1996/writing/:splat  301
/images/*   /1996/images/:splat   301
```

## Typography

| | |
|---|---|
| verse | `FangSong`, `仿宋`, `STFangsong`, `FandolFang`, `fangsong`, serif |
| chrome | `ui-monospace` → Cascadia Mono / SF Mono / Menlo / Consolas |
| concrete poems | kept in monospace — indentation is the poem |

Fangsong exists on Windows (`simfang.ttf`) and macOS (`STFangsong`); Linux and
Android have none and fall through to a serif. **Open item:** self-host a
subset (FandolFang's Latin, GPL + font exception) so every platform agrees.
`simfang.ttf` itself is Microsoft-licensed and cannot be redistributed.

## Archive notes

- All HTML is pure ASCII, so no charset declaration is needed.
- Line endings are CR-only (classic Mac). `krazykat/` is stored byte-for-byte
  and must stay that way — do not let an editor "fix" it.
- Three `mailto:` links now point at `deafmetal@gmail.com`; the 1996 address and
  a dead link to `mindvox.phantom.com/~reive/poetry.html` were removed in 2026.
- Two poems contain literal angle-bracket words — `<jerks>` in *Timidity*, `<EOF>`
  in *Until 2*. 1996 browsers ate them as unknown tags, so the words were
  invisible for thirty years. The 2026 pages escape them and show them.

© Noah Christy Brown, 1995–1996.
