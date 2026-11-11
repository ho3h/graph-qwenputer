# Round 7: design crit

Light mode, 1440x900 and 390x844. Measured live. Only item 1's palette, ribbons and dim were tried in the browser; everything else is untested.

## 1. Pixel defects

**Left edges.** Header 130, intro 150, step text 66, `.more` 360. Use one axis:
`:root{--axis:calc(max(20px,env(safe-area-inset-left,0px)) + 46px)}`, `.sign .wrap{max-width:none;margin:0;padding-left:46px}`, `.intro{max-width:none;margin:0;padding-left:var(--axis)}`, `.more{max-width:calc(var(--axis) + 720px);margin:0;padding-left:var(--axis)}`. Under 860px: `--axis:20px`, wrap padding-left 0.

**Clipped end of route.** `frame()` shifts the camera `W*.12`, pushing Mets-Willets Point off the map (d-journey). Delete both shifts (`.12`, `.05`).

**Dark panel.** It hides Roosevelt Island (d-build), jumps from 50 to 207px tall, and stays 380 wide for one line. See beat 1.

**False geography.** After Bowling Green closes, hop 483>220 draws straight across the harbour (d-close). Add `const VIA={"483-220":223}` and draw through it in `geoHop`.

**Circle and heading.** Circle centre is T+17, heading centre T+26. `.step::before{top:9px}`, phone `6px`. `.steps::before{top:calc(8vh + 26px)}`, phone `56px` (by calculation, the phone rail starts 12px below circle 1).

**Rail end.** It runs 748px past circle 19. `.step:last-child::after{content:"";position:absolute;left:-46px;top:43px;bottom:0;width:34px;background:var(--ground)}`.

**Tiny diagrams.** Step SVGs render 14 units at 10.2px. Redraw both step-column figures at `viewBox` width 380 with 13-unit text.

**Wrong colour.** FX is drawn in 4-5-6 green. Use `#FF6319` in the fix SVG and `fix()`. Make "11 added layers" ink, 3px.

**Panels.** `.ans div` 150px label column wastes a quarter of 348: use `grid-template-columns:1fr;gap:2px` everywhere. Trip 6 orphans: `#askb{display:grid;grid-template-columns:repeat(6,1fr)}`, `#askb .card{padding:8px 0;text-align:center}`. Tint breaks the axis: `.play{background:none;padding:0}`.

**Tables.** `td.n,th:last-child{text-align:right;padding-right:0}`.

**Type.** Fifteen sizes. Use 13/15/18/25/31/34/h1; 14 and 14.5 become 13, 16 and 17 become 15 or 18.

**Blacks.** Four: `#000`, `#141414`, `#0a1a24`, `rgba(4,12,17,.9)`. Add `--sign:#000` for header, stage and deck. Rail: `#000` in light; `var(--ink)` stays in dark, where it must flip.

**Radii.** Panels 0; controls and SVG rects 4.

**Focus.** Yellow on `#fafaf8` is about 1.4:1. `.btn,.card,summary` use `outline:3px solid var(--ink)`. `#nyc` keeps yellow, but has no tabindex, so "close anything" is pointer-only. Add `.card:hover{border-color:var(--ink)}`.

**White to dark.** The hard edge is right; leave it. `.ride{margin-top:56px}`.

**Start marks.** `memory()` and `reopen()` drop the start ring and the route ends blunt; add `mark(N[341])`.

**Phone.** `.stage{height:48dvh}` (58vh leaves 354px to read). `THE BRONX` hits `Pelham Bay Park`. "Qwen alone: Broadway-Lafay" clips: drop "Qwen " on narrow and clamp x to the frame in `label()`. Under 860px keep hubs Times Sq, Atlantic Av, Coney Island, Flushing, Tottenville, Wakefield; place labels `f*.72`; dots `r=.9*Z`, because white beads currently drown the colours.

## 2. The map

Tried live: it stops looking like a dashboard. The route must then be thickened.

- Water `#000`, land `#1c1d1f`, shoreline `#3f4246` at .5. Removes the navy cast; colours sit truer.
- Vignelli's ribbons: `gL` stroke-width `Math.max(1.2,Math.min(6,STEP/Z))`, so parallels touch. Now they overlap citywide (2px on 1.33px spacing) and gap when zoomed.
- Dim: stroke-opacity .34 turns yellow olive and orange rust. Use .6.
- Route over ribbons: white 7px on a 10px `#000` casing.
- Dots: `r` 1 city, 2 zoomed.
- `#0039A6` is 1.45:1 on land, 1.72 on proposed land. Keep the colour; add a white .45 casing, line width +1, for ACE only.
- Transfers are scribbled triangles: `#c7c9cc`, 3px, round caps, opacity 1, hidden citywide.
- Label halo `#1c1d1f`, 2.5px, weight 600.
- Places: MANHATTAN crosses 18 dots, BROOKLYN 4, BRONX 5. Move MANHATTAN to `-74.012,40.79`, BROOKLYN to `-73.916,40.628`; check by eye. Drop hubs Pelham Bay Park and Inwood. Keep only Atlantic Ocean among water names. Land names `#8e9195`, water `#7b8a94`.
- Queens and the Bronx end in straight cuts against void, and New Jersey is missing. Add neighbouring land at `#141516`, no stroke, outside `land.json`. This is what most separates a cartographer's map from a data plot.

## 3. Subway beats, ranked

**Take:**

1. **The sign, as the deck.** Black, full width, white band, Helvetica; the header already speaks this language.
   `.deck{inset:0 0 auto 0;width:auto;height:144px;border-radius:0;padding:23px 20px 12px;background:linear-gradient(#fff,#fff) 0 8px/100% 3px no-repeat #000;grid-template-columns:minmax(0,1fr) 320px;column-gap:24px;align-content:start}`, `.say{grid-row:1/3}`, meter and bits in column 2. Reset on phone. In `frame()`, with T=144 when not `bare`: multiply `s` by `h0/(h0-T)`, subtract `(T/h0)*s/2` from y. Header: delete `.rule`, `.sign{background:linear-gradient(#fff,#fff) 0 14px/100% 5px no-repeat #000}`, wrap `padding-top:46px`.
2. **Route bullets inline**, only where a sentence names a line: steps 2, 7, 13, 19, trip questions. `.b{display:inline-grid;place-items:center;width:1.3em;height:1.3em;border-radius:50%;background:var(--c);color:#fff;font:700 .8em/1 var(--sans);vertical-align:-.15em}`. N, Q, R, W get black numerals. Use a diamond only for FX, the one express here. T is `#00ADD0`.
3. **Vignelli's touching ribbons** (section 2). No added element.
4. **Station-name sign** at arrivals: answer, journey, build. Deck column 2 shows "Borough Hall" at 31px bold with its bullets. It earns its place because it's the payoff.

**Refuse:**

5. Coloured legs on `.strip`: good, but a fifth beat.
6. Countdown clock for the step counter: LED pastiche.
7. Service-change notice: reads as a real MTA document.
8. Tile: skeuomorphism.
9. Sign arrows, and coloured step circles: decoration that competes with the route colours.

Caution: the MTA treats route bullets as its marks. Have them checked before launch.

## 4. Remove

- `.draft`, at launch.
- Deck text in `ask` (repeats the step) and "Five stops, one name."
- ", then the line" from the meter.
- `type()` everywhere except `query`.
- "Hover or tap a bar for its count." Label the bars directly.
- `.step::before` transition.
- `.tr` and `.wrong`, if unused.

Move "Positions of the new stops are drawn by hand." into step 19's text. Don't delete it: it's a disclosure.
