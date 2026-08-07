#!/usr/bin/env python3
"""Build site/walkthrough.html: the whole page as one file, with no subresources.

``site/index.html`` references its screenshots as ``assets/*.jpg``. That is correct and it
works over HTTP, but it cannot work when the file is double-clicked on a Mac where the
browser has been handed access to *one file* rather than to the folder: the HTML opens and
every image beside it is denied. No path can fix that -- the page has to stop asking for
separate files at all.

So this writes a derived copy with the images inlined as ``data:`` URIs and the click-through
turned into an in-page lightbox. It requests nothing from disk or network, which makes it the
copy to double-click, email, or drop on a USB stick.

    python3 site/build_standalone.py            # write site/walkthrough.html
    python3 site/build_standalone.py --check    # exit 1 if it is missing or out of date

``site/index.html`` stays the editable source. Regenerate downstream of everything else:

    refresh_figures.py  ->  build_assets.py  ->  build_standalone.py

One trap worth naming, because the first cut of this hit it: each figure names its image
*twice*, once in ``<img src>`` and once in the wrapping ``<a href>`` click-through. Substituting
both embeds every screenshot twice and doubles the file. Only ``src`` is inlined here; the
anchor becomes a button that enlarges the image already in the DOM. ``verify()`` fails the
build if any payload appears more than once, so the mistake cannot come back quietly.
"""

from __future__ import annotations

import argparse
import base64
import re
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent
SOURCE = SITE / "index.html"
ASSETS = SITE / "assets"
OUTPUT = SITE / "walkthrough.html"

# Generous, but low enough that a doubled payload trips it rather than shipping silently.
# Ten captures, three of which ship a dark twin for the theme-aware dashboards.
SIZE_BUDGET = 6 * 1024 * 1024

ANCHOR = re.compile(
    r'<a href="assets/(?P<name>[^"]+)"[^>]*>\s*(?P<img><img [^>]*>)\s*</a>', re.S
)

EXTRA_CSS = """
/* ---------- standalone: zoom button replaces the click-through link ---------- */
.shot .shot-zoom {
  display:block; width:100%; padding:0; border:0; font:inherit; cursor:zoom-in;
  background:var(--card-2); color:var(--ink-3);
  border-radius:var(--r-sm); overflow:hidden; aspect-ratio:16 / 10;
}
.shot--tall .shot-zoom { aspect-ratio:3 / 4; }
.shot .shot-zoom img { width:100%; height:100%; object-fit:contain; display:block; }
.lb {
  position:fixed; inset:0; z-index:100; display:none; place-items:center;
  background:rgba(0,0,0,.84); padding:var(--sp-5);
}
.lb[data-on="true"] { display:grid; }
.lb img { max-width:100%; max-height:88vh; object-fit:contain; border-radius:var(--r-sm); }
.lb-close {
  position:fixed; top:16px; right:16px; width:40px; height:40px; display:grid;
  place-items:center; border-radius:50%; cursor:pointer; font:inherit; font-size:20px;
  background:var(--card); color:var(--ink); border:1px solid var(--line);
}
"""

EXTRA_JS = """
/* ---------- standalone lightbox ---------- */
(function () {
  const box = document.createElement("div");
  box.className = "lb"; box.setAttribute("role", "dialog");
  box.setAttribute("aria-modal", "true"); box.setAttribute("aria-label", "Enlarged screenshot");
  box.innerHTML = '<button class="lb-close" type="button" aria-label="Close">\\u2715</button><img alt="">';
  document.body.appendChild(box);
  const big = box.querySelector("img"), closer = box.querySelector(".lb-close");
  let opener = null;

  function open(button) {
    const source = button.querySelector("img");
    big.src = source.src; big.alt = source.alt;
    box.dataset.on = "true"; opener = button; closer.focus();
  }
  function close() {
    box.dataset.on = "false"; big.removeAttribute("src");
    if (opener) { opener.focus(); opener = null; }
  }
  document.querySelectorAll(".shot-zoom").forEach((button) =>
    button.addEventListener("click", () => open(button)));
  closer.addEventListener("click", close);
  box.addEventListener("click", (event) => { if (event.target === box) close(); });
  addEventListener("keydown", (event) => {
    if (event.key === "Escape" && box.dataset.on === "true") close();
  });
})();
"""


def data_uri(name: str) -> str:
    payload = (ASSETS / name).read_bytes()
    return "data:image/jpeg;base64," + base64.b64encode(payload).decode("ascii")


def render() -> str:
    """Inline every screenshot exactly once and swap the link for a zoom button."""
    html = SOURCE.read_text()

    def swap(match: re.Match[str]) -> str:
        img = match.group("img")
        inlined = re.sub(
            r'(src|data-light|data-dark)="assets/([^"]+)"',
            lambda m: f'{m.group(1)}="' + data_uri(m.group(2)) + '"',
            img,
        )
        return (
            '<button class="shot-zoom" type="button" aria-label="Enlarge this screenshot">'
            f"{inlined}</button>"
        )

    html = ANCHOR.sub(swap, html)
    html = html.replace("</style>", EXTRA_CSS + "</style>", 1)
    return html.rstrip() + "\n<script>" + EXTRA_JS + "</script>\n"


def verify(html: str) -> None:
    """Refuse to ship a build that still reaches for a file, or that doubled a payload."""
    leftovers = re.findall(r'(?:src|href)="(?:assets/|\.\./)[^"]*"', html)
    if leftovers:
        raise SystemExit(f"still references files on disk: {sorted(set(leftovers))}")

    source = SOURCE.read_text()
    for asset in sorted(ASSETS.glob("*.jpg")):
        # Count the whole payload, not a sample of it. Sampling looked cheaper but a
        # 512-character window is not unique: the dark captures have large flat areas,
        # so a slice of their base64 recurs both inside one image and across the set.
        encoded = data_uri(asset.name)
        # Every payload appears exactly once: the light capture as the img src, the dark
        # one as data-dark. The light source is recovered at runtime, not duplicated here.
        expected = 1
        count = html.count(encoded)
        if count != expected:
            raise SystemExit(
                f"{asset.name} is embedded {count} times, expected {expected} "
                "(check that <a href> is not being substituted alongside <img src>)"
            )

    size = len(html.encode())
    if size > SIZE_BUDGET:
        raise SystemExit(
            f"{size / 1_048_576:.1f} MB exceeds the {SIZE_BUDGET / 1_048_576:.0f} MB budget"
        )


def is_stale() -> bool:
    if not OUTPUT.exists():
        return True
    newest = max(p.stat().st_mtime for p in [SOURCE, *ASSETS.glob("*.jpg")])
    return OUTPUT.stat().st_mtime < newest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="exit 1 if walkthrough.html is missing or out of date")
    args = parser.parse_args()

    if args.check:
        if is_stale():
            print("site/walkthrough.html is missing or out of date; run build_standalone.py")
            sys.exit(1)
        print("site/walkthrough.html is current")
        return

    html = render()
    verify(html)
    OUTPUT.write_text(html)
    print(f"wrote {OUTPUT.relative_to(SITE.parent)} "
          f"({OUTPUT.stat().st_size / 1_048_576:.1f} MB, no external references)")


if __name__ == "__main__":
    main()
