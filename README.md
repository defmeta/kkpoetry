# kkpoetry

Archive of the *krazykat* poetry site, written 1995–96. Static HTML, no build
step, no server-side code — it runs on any web server as-is.

- `krazykat/index.html` — entry point; immediately redirects to
  `writing/scrawlz.html`
- `krazykat/writing/` — poems. Most are a trio: `<poem>.html` (frame
  contents), `<poem>.t.html` (title pane), `<poem>.b.html` (body pane)
- `krazykat/images/` — three GIFs

The layout is a nested `<FRAMESET>` with `TARGET="body"` links from the
contents pane. Everything is original 1996 HTML; it is intentionally not
modernised.

## Viewing it locally

```sh
python3 -m http.server --directory krazykat 8000
# then open http://localhost:8000/
```

Opening `index.html` from the filesystem works too, though `file://` breaks
nothing here it just looks the same.

## Notes

- All HTML is pure ASCII, so no charset declaration is needed anywhere.
- Line endings are CR-only (classic Mac). `.gitattributes` sets `* -text` so
  git stores the bytes untouched — do not let an editor "fix" them.
- Every internal link resolves, and all filenames are lowercase, so the tree is
  safe on case-sensitive hosts.

© Noah Christy Brown, 1995–1996.
