# Fandol Fang (subset)

`fandol-fang-latin.woff2` is a Latin-and-punctuation subset of
`FandolFang-Regular.otf` from the Fandol fonts.

- **Copyright** © 2012–2013, the Fandol team (Clerk Ma & Jie Su)
- **License** GNU General Public License, version 3, with the font embedding
  exception — full text in `COPYING`
- **Source** https://ctan.org/pkg/fandol  (upstream: `fonts/fandol/FandolFang-Regular.otf`)

The subset keeps the font's name table, so the copyright and license URL travel
inside the file itself.

Reproduce it with fonttools:

```sh
pyftsubset FandolFang-Regular.otf \
  --unicodes="U+0020-007E,U+00A1-00FF,U+2010-2027,U+2030-205E,U+20AC" \
  --layout-features=kern --no-hinting --desubroutinize --name-IDs='*' \
  --flavor=woff2 --output-file=fandol-fang-latin.woff2
```

6.64 MB → 9.7 KB. The GPL is why the source URL and this build recipe are
recorded here: the subset is a GPL work being distributed to browsers.
