"""Generate the restyled architecture diagram SVG."""
from __future__ import annotations

L = 40                            # left margin
FULL = 1100                       # a full-width box, sized to fit its widest row
COL_GAP = 40                      # between the two side-by-side boxes
COLW = (FULL - COL_GAP) // 2      # 530
RX = L + COLW + COL_GAP           # right column x
R = L + FULL
W = R + L                         # canvas

CX  = L + FULL // 2               # centre of a full-width box
CXL = L + COLW // 2               # centre of the left column
CXR = RX + COLW // 2              # centre of the right column

ICONS = {
    "api": '<path d="M6.5 18.5a4.5 4.5 0 0 1-.6-9 6 6 0 0 1 11.5-1.4 4.8 4.8 0 0 1 .6 9.5z"/><path d="M12 11v5m0 0 2-2m-2 2-2-2"/>',
    "cart": '<path d="M4 9h16l-1.5 9.2a2 2 0 0 1-2 1.8H7.5a2 2 0 0 1-2-1.8z"/><path d="m8.5 9 2.2-5M15.5 9l-2.2-5"/>',
    "cube": '<path d="M3 8.5 12 4l9 4.5v7L12 20l-9-4.5z"/><path d="M3 8.5 12 13l9-4.5M12 13v7"/>',
    "audit": '<rect x="5" y="5" width="14" height="16" rx="2"/><path d="M9 5V3.8A.8.8 0 0 1 9.8 3h4.4a.8.8 0 0 1 .8.8V5M8.5 11h7M8.5 15h4"/>',
    "download": '<path d="M12 3v11m0 0 4-4m-4 4-4-4M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/>',
    "shield": '<path d="M12 3 5 6v5.6c0 4 2.9 7.7 7 8.9 4.1-1.2 7-4.9 7-8.9V6z"/><path d="m9.2 12.2 2 2 3.7-4"/>',
    "spark": '<path d="M12 3.5 13.7 9l5.5 1.7-5.5 1.7L12 18l-1.7-5.6L4.8 10.7 10.3 9z"/><path d="M18.5 4v3M20 5.5h-3"/>',
    "x": '<circle cx="12" cy="12" r="8.5"/><path d="m9.4 9.4 5.2 5.2M14.6 9.4l-5.2 5.2"/>',
    "layers": '<path d="m12 3 8.5 4.4L12 11.8 3.5 7.4z"/><path d="m3.5 12 8.5 4.4 8.5-4.4M3.5 16.6 12 21l8.5-4.4"/>',
    "medal": '<circle cx="12" cy="14" r="5"/><path d="M9 9.3 7 3h10l-2 6.3M12 12v4M10.4 13.6h3.2"/>',
    "chart": '<path d="M4 20V4M4 20h16"/><path d="M8.5 20v-6M13 20V8.5M17.5 20v-9"/>',
    "clock": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.2V12l3.2 2"/>',
    "db": '<ellipse cx="12" cy="6.5" rx="7.5" ry="3"/>'
          '<path d="M4.5 6.5v11c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3v-11M4.5 12c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3"/>',
}


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def cyl(x, y, w, h, ry=8):
    """Cylinder silhouette + top rim, for storage boxes."""
    rx = w / 2
    x2 = x + w
    return (f'<path class="dg-band" d="M{x},{y+ry} A{rx},{ry} 0 0 1 {x2},{y+ry} '
            f'V{y+h-ry} A{rx},{ry} 0 0 1 {x},{y+h-ry} Z"/>'
            f'<path class="dg-rim" d="M{x},{y+ry} A{rx},{ry} 0 0 0 {x2},{y+ry}"/>')


BULL_STEP = 26    # every bullet list uses this rhythm
CHIP_STEP = 42

# Real text widths, measured in the browser (widths.json), so centring is exact rather
# than estimated. Regenerate by rendering the page and reading each text's getBBox().width.
import json
import pathlib

_W = {}
_wf = pathlib.Path(__file__).with_name("widths.json")
if _wf.exists():
    _W = json.loads(_wf.read_text())

# fallbacks, only used for strings not present in the measured table
W_TITLE = 9.30    # .dg-t   17px bold
W_DESC  = 6.55    # .dg-s   13px
W_BULL  = 6.75    # .dg-b   13.5px

GAP_COL = 46      # space between the blocks that make up a row
BADGE_W = 28      # the numbered badge
PLATE_W = 52


def _rail(box_w, text_w, chip_w_max, bull_w_max):
    """One shared set of x offsets for a family of boxes.

    Badges, icons and titles then line up down the whole diagram instead of drifting
    per box, while the rail as a whole still sits centred in the box.
    """
    widths = [BADGE_W, PLATE_W, text_w]
    if chip_w_max:
        widths.append(chip_w_max)
    if bull_w_max:
        widths.append(14 + bull_w_max)
    total = sum(widths) + GAP_COL * (len(widths) - 1)
    start = (box_w - total) / 2
    offs, cur = [], start
    for wd in widths:
        offs.append(cur)
        cur += wd + GAP_COL
    while len(offs) < 5:
        offs.append(cur)
    offs[0] += BADGE_W / 2          # the badge is drawn from its centre
    return offs


# widest content in each family, measured, so the rails are exact
RAIL_ROW = _rail(FULL, 249.48, 201, 273.54)     # full-width boxes
# one rail for every box in the diagram, wide or narrow: badge, icon and title all land
# on the same offsets, so the spacing reads identically everywhere
RAIL_COL = RAIL_ROW


def tw(s, factor, cls=None):
    if cls is not None:
        hit = _W.get(f"{cls}|{s}")
        if hit is not None:
            return hit
    return len(s) * factor


def chip_w(c):
    return max(96, 9 * len(c) + 30)


def box(x, y, w, h, cls, icon, title, desc, chips=(), bullets=(), store=False,
        delay=0, stack_body=False, step=None, rail=None):
    shape = f'<rect class="dg-band" x="{x}" y="{y}" width="{w}" height="{h}" rx="16"/>'
    o = [f'<g class="dg-item {cls}" data-delay="{delay}">', shape]

    # ---- vertical: measure the title block, centre it (stacked boxes measure the whole stack)
    ends = [52]
    if desc:
        ends.append(40 + (len(desc) - 1) * 18 + 4)
    if stack_body:
        rel = 40 + len(desc) * 18 + 16
        if chips:
            ends.append(rel + (len(chips) - 1) * CHIP_STEP + 32)
        if bullets:
            ends.append(rel + len(chips) * CHIP_STEP + 18 + (len(bullets) - 1) * BULL_STEP + 4)
    py = round(y + (h - max(ends)) / 2)

    # ---- horizontal: one shared rail per box family, so badges, icons and titles each
    #      line up down the whole diagram; the rail as a whole is centred in the box.
    rail = rail or RAIL_ROW
    bx, px, tx, cx_chip, cx_bull = (x + off for off in rail)

    if step is not None:                # left-aligned down the whole diagram
        o.append(f'<circle class="dg-stepdot" cx="{bx:.1f}" cy="{y+h/2}" r="14"/>')
        o.append(f'<text class="dg-stepn" x="{bx:.1f}" y="{y+h/2+4.5}" '
                 f'text-anchor="middle">{step}</text>')

    o.append(f'<rect class="dg-plate" x="{px:.1f}" y="{py}" width="52" height="52" rx="14"/>')
    o.append(f'<g class="dg-ico" transform="translate({px+13:.1f} {py+13}) scale(1.083)" '
             f'fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
             f'stroke-linejoin="round">{ICONS[icon]}</g>')

    o.append(f'<text class="dg-t" x="{tx:.1f}" y="{py+16}">{esc(title)}</text>')
    for i, line in enumerate(desc):
        o.append(f'<text class="dg-s" x="{tx:.1f}" y="{py+40+i*18}">{esc(line)}</text>')
    cur = cx_chip

    if stack_body:                      # narrow column: chips then bullets, stacked under the title
        cy0 = py + 40 + len(desc) * 18 + 16
        sx = tx                         # chips and bullets line up under the title
        for i, c in enumerate(chips):
            cw = chip_w(c)
            o.append(f'<rect class="dg-chip" x="{sx:.1f}" y="{cy0+i*CHIP_STEP}" width="{cw}" '
                     f'height="32" rx="9"/>')
            o.append(f'<text class="dg-chip-t" x="{sx+cw/2:.1f}" y="{cy0+i*CHIP_STEP+20}" '
                     f'text-anchor="middle">{esc(c)}</text>')
        by = cy0 + len(chips) * CHIP_STEP + 18
        for i, b in enumerate(bullets):
            o.append(f'<circle class="dg-dot" cx="{sx:.1f}" cy="{by+i*BULL_STEP-4}" r="2.6"/>')
            o.append(f'<text class="dg-b" x="{sx+14:.1f}" y="{by+i*BULL_STEP}">{esc(b)}</text>')
    else:
        if chips:
            ctop = round(y + (h - ((len(chips) - 1) * CHIP_STEP + 32)) / 2)
            for i, c in enumerate(chips):
                cw = chip_w(c)
                o.append(f'<rect class="dg-chip" x="{cur:.1f}" y="{ctop+i*CHIP_STEP}" width="{cw}" '
                         f'height="32" rx="9"/>')
                o.append(f'<text class="dg-chip-t" x="{cur+cw/2:.1f}" y="{ctop+i*CHIP_STEP+21}" '
                         f'text-anchor="middle">{esc(c)}</text>')
        if bullets:
            cur = cx_bull
            btop = round(y + (h - ((len(bullets) - 1) * BULL_STEP + 14)) / 2)
            for i, b in enumerate(bullets):
                base = btop + 11 + i * BULL_STEP
                o.append(f'<circle class="dg-dot" cx="{cur:.1f}" cy="{base-4}" r="2.6"/>')
                o.append(f'<text class="dg-b" x="{cur+14:.1f}" y="{base}">{esc(b)}</text>')
    o.append('</g>')
    return "".join(o)


def arrow(x, y1, y2, label="", cls="", anchor_x=None, label_dy=None):
    """label_dy offsets the label from y1; used where the arrow crosses the boundary."""
    a = [f'<polyline class="dg-arrow {cls}" points="{x},{y1} {x},{y2}" '
         f'marker-end="url(#{"arrow" if not cls else "arrow-"+cls.split("-")[-1]})"/>']
    if label:
        ly = y1 + label_dy if label_dy is not None else (y1 + y2) / 2 + 4
        a.append(f'<text class="dg-e {cls}" x="{(anchor_x or x)+12}" y="{ly}" '
                 f'text-anchor="start">{esc(label)}</text>')
    return "".join(a)


GAP  = 68     # the one and only vertical gap between boxes
PAD  = 36     # breathing room inside the boundary, and clear of its legend
HROW = 124    # every full-width box
HCOL = 340    # the two side-by-side boxes
HSRC = 100    # the two source boxes
HEND = 88     # Airflow

parts = []
y = 0

# ---- two sources, side by side
parts.append(box(L, y, COLW, HSRC, "dg-src-a", "api", "Open Food Facts",
                 ["Real, public product data:", "names, brands, nutrition"], delay=0, step=1))
parts.append(box(RX, y, COLW, HSRC, "dg-src-b", "cart", "Generated prices",
                 ["Five fictional stores,", "with faults injected on purpose"], delay=1))
mid = y + HSRC + GAP // 2
parts.append(f'<polyline class="dg-arrow" points="{CXL},{y+HSRC} {CXL},{mid} {CX},{mid}"/>')
parts.append(f'<polyline class="dg-arrow" points="{CXR},{y+HSRC} {CXR},{mid} {CX},{mid} '
             f'{CX},{y+HSRC+GAP}" marker-end="url(#arrow)"/>')
parts.append(f'<text class="dg-e" x="{CX+14}" y="{mid-6}">fetch and generate</text>')
y += HSRC + GAP

parts.append(box(L, y, FULL, HROW, "dg-ingest", "download", "Ingestion",
                 ["Fetch and generate, then land the files.", "Nothing is judged yet."],
                 chips=["products.json", "prices.csv"],
                 bullets=["Timestamped filenames", "Newest file wins", "Written to data/bronze/"],
                 delay=2, step=2))
parts.append(arrow(CX, y + HROW, y + HROW + GAP, "lands raw files", label_dy=17))
y += HROW + GAP

VAULT_TOP = y - PAD
parts.append(box(L, y, FULL, HROW, "dg-bronze", "cube", "Bronze layer",
                 ["Every record exactly as it arrived,", "stored as JSONB."],
                 chips=["raw_products", "raw_prices"],
                 bullets=["No cleaning, no dropping", "Replayable history",
                          "Written before validation"], delay=3, step=3))
parts.append(arrow(CX, y + HROW, y + HROW + GAP, "reads every record"))
y += HROW + GAP

parts.append(box(L, y, FULL, HROW, "dg-check", "shield", "Validation and cleaning",
                 ["Deterministic rules decide pass or reject.",
                  "An optional local LLM adds judgement,", "never a reversal."],
                 bullets=["Barcode, name and price checks",
                          "Duplicate event IDs caught per file",
                          "Unknown store or barcode rejected",
                          "Failures are written to audit, with the reason"], delay=4, step=4))
split, branch = y + HROW, y + HROW + GAP
parts.append(f'<polyline class="dg-arrow dg-good" points="{CXL},{split} {CXL},{branch}" '
             f'marker-end="url(#arrow-good)"/>')
parts.append(f'<text class="dg-e dg-good" x="{CXL+12}" y="{(split+branch)/2+4}" '
             f'text-anchor="start">clean data</text>')
parts.append(f'<polyline class="dg-arrow dg-bad" points="{CXR},{split} {CXR},{branch}" '
             f'marker-end="url(#arrow-bad)"/>')
parts.append(f'<text class="dg-e dg-bad" x="{CXR+12}" y="{(split+branch)/2+4}" '
             f'text-anchor="start">bad data</text>')
y = branch

parts.append(box(L, y, COLW, HCOL, "dg-silver", "spark", "Silver layer",
                 ["The trustworthy copy.", "A price cannot exist", "without its product."],
                 chips=["products", "prices", "stores"],
                 bullets=["Typed and length-capped", "Upserted on barcode",
                          "Foreign keys enforced"], stack_body=True, delay=5, step=5))
parts.append(box(RX, y, COLW, HCOL, "dg-quar", "audit", "Audit",
                 ["The paper trail. Rejected records", "land in the quarantine table,",
                  "with the reason they failed."],
                 chips=["quarantine", "pipeline_runs", "ai_validation_results"],
                 bullets=["Every run, rejection and AI verdict",
                          "Each tied to the run that rejected it",
                          "Never reaches silver"], stack_body=True, delay=6))
parts.append(arrow(CXL, y + HCOL, y + HCOL + GAP, "reads as a source"))
y += HCOL + GAP

parts.append(box(L, y, FULL, HROW, "dg-dbtstep", "layers", "dbt transformations",
                 ["SQL models in version control,", "carrying their own tests."],
                 chips=["1 model", "4 tests"],
                 bullets=["Reads silver through sources.yml", "Materialised as views",
                          "dbt run && dbt test"], delay=7, step=6))
parts.append(arrow(CX, y + HROW, y + HROW + GAP, "builds"))
y += HROW + GAP

parts.append(box(L, y, FULL, HROW, "dg-gold", "medal", "Gold layer",
                 ["Aggregates shaped for reading,", "not for storage."],
                 chips=["daily_price_summary"],
                 bullets=["Per day, per product", "Average, minimum, maximum",
                          "Stores reporting"], delay=8, step=7))
VAULT_BOT = y + HROW + PAD
parts.append(arrow(CX, y + HROW, y + HROW + GAP, "queries", label_dy=57))
y += HROW + GAP

parts.append(box(L, y, FULL, HROW, "dg-serve", "chart", "Metabase dashboard",
                 ["Two tabs over the same warehouse:", "is the pipeline healthy,",
                  "and what do the prices say."],
                 chips=["Pricing", "Data quality"],
                 bullets=["Run health and rejections", "Price spread and promotions",
                          "SQL kept in the repo"], delay=9, step=8))
y += HROW + GAP

parts.append(box(L, y, FULL, HEND, "dg-sched", "clock", "Airflow",
                 ["Runs steps 2 to 4 once a day, two retries."], delay=10))
HEIGHT = y + HEND + 20

# the boundary carries a legend sitting on its top edge, the way a fieldset does
LG_TEXT = "one PostgreSQL database"
LG_PAD, LG_ICO, LG_GAP = 11, 19, 10
LG_W = round(LG_PAD + LG_ICO + LG_GAP + tw(LG_TEXT, 8.0, "dg-vault-t") + LG_PAD + 3)
vault = (f'<g class="dg-item dg-vault" data-delay="11">'
         f'<rect class="dg-vault-box" x="{L-22}" y="{VAULT_TOP}" width="{FULL+44}" '
         f'height="{VAULT_BOT-VAULT_TOP}" rx="22"/>'
         f'<rect class="dg-vault-lg" x="{L+4}" y="{VAULT_TOP-16}" width="{LG_W}" height="32" rx="16"/>'
         f'<g class="dg-ico dg-vault-ico" transform="translate({L+4+LG_PAD} {VAULT_TOP-9.5}) '
         f'scale(0.8)" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
         f'stroke-linejoin="round">{ICONS["db"]}</g>'
         f'<text class="dg-vault-t" x="{L+4+LG_PAD+LG_ICO+LG_GAP}" y="{VAULT_TOP+5}">'
         f'{LG_TEXT}</text></g>')

defs = ('<defs>'
        '<marker id="arrow" viewBox="0 0 10 10" refX="8.6" refY="5" markerWidth="6.2" '
        'markerHeight="6.2" orient="auto"><path d="M0 1.2 L9 5 L0 8.8 z" fill="currentColor"/></marker>'
        '<marker id="arrow-good" viewBox="0 0 10 10" refX="8.6" refY="5" markerWidth="6.2" '
        'markerHeight="6.2" orient="auto"><path d="M0 1.2 L9 5 L0 8.8 z" class="mk-good"/></marker>'
        '<marker id="arrow-bad" viewBox="0 0 10 10" refX="8.6" refY="5" markerWidth="6.2" '
        'markerHeight="6.2" orient="auto"><path d="M0 1.2 L9 5 L0 8.8 z" class="mk-bad"/></marker>'
        '</defs>')

ARIA = ("Eight stages flowing top to bottom. Open Food Facts and a price generator feed ingestion, "
        "which lands timestamped files. The bronze layer stores every record verbatim. Validation "
        "and cleaning then splits the flow in two, side by side: clean data goes left into the silver "
        "layer, bad data goes right into the audit schema, whose quarantine table keeps the record "
        "along with the reason it failed. dbt reads silver and builds the gold layer, and Metabase "
        "serves two dashboard tabs. Bronze, silver, audit and gold are all schemas inside one "
        "PostgreSQL database, drawn as a dashed boundary, and Airflow runs the middle stages once a "
        "day. A second route for the same price data is drawn separately in section 07.")

print(f'<svg class="diagram" viewBox="-30 -14 {W+30} {HEIGHT}" role="img" aria-label="{ARIA}">'
      f'{defs}{vault}{"".join(parts)}</svg>')
