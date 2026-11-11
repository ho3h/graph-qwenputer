# Round 13: pixel review of subway.outofcontext.io

Fixes 1-10 were tested on a scratch copy of the live page, except the Van Siclen edit in 8 and the 180px in 1.

## Must fix before announcing

1. **Phone deck clips the story.** `.say` hides 50px on query and 16px on answer, losing the `legs` line and "Qwen: 425". In the 860px block, replace `.say{font-size:12px;max-height:4.3em;overflow:hidden}` with `.say{font-size:12px}`, then add `.stage{grid-template-rows:minmax(0,1fr) 144px}.stage:not(.nomem){grid-template-rows:minmax(0,1fr) 180px}.stage.bare{grid-template-rows:minmax(0,1fr) auto}`. This also stops the map rescaling each step.
2. **Phone hides the grid the copy describes.** In that block, change `#bits{display:none}` to `#bits{max-width:none}`.
3. **Build's last frame reads "ottenville", with new stops' rings covered.** In `buildT`'s ride callback, first add `pt(P1,"Gannet Sq");pt(P2,"Bracken Rd");mark(d,T,5);mark(s1,"#FCCC0A",6);label(s1,s1.n,{dx:11});`.
4. **Favicon 404.** Add `<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Ccircle cx='16' cy='16' r='12' fill='%23000' stroke='%23FCCC0A' stroke-width='7'/%3E%3C/svg%3E">`.

## Should fix

5. **Deck title floats mid-panel, left half empty** (ask, test, fulton, trips, game). Add `.deck:has(.say:empty) .side{grid-column:1/-1}`.
6. **Empty 144px band** on score and onestop. In `enter`: `stage.classList.toggle("bare",["map","score","onestop"].includes(k))`.
7. **"Saratoga Av" collides with the route.** In `close()`, `dy:-8` becomes `dy:22`.
8. **Labels collide on phone.** Pennsylvania Av and Van Siclen Av flip onto the route. Add `dy:wide()?4:-12` to the `N[A1]` labels and the `N[A2]` label.
9. **"no FX" labels cover their own rings.** In `fix()`, `dx:12` becomes `dx:on?12:-12`.
10. **Three-column table: middle header left, values right.** Replace `td.n,th:last-child{...}` with `td.n,th:not(:first-child){text-align:right;padding:6px 0 6px 12px}td.n{padding-block:9px}`.

## Owner's call

11. **First screen.** The headline and dek are strong, but a page about a map shows none: it first appears 3,253px down on desktop, 4,348px on phone. Moving `.built` and `.tech` to the top of `main.more` puts it about 870px down. It changes reading order, so check back-references.

## After launch (untested)

12. Phone diagram text renders about 8.8px: `.built figure{overflow-x:auto}.built figure svg{min-width:460px}`.
13. Landscape phone leaves about 60px of map: `@media (max-width:860px) and (max-height:500px){.say,#bits{display:none}}`.
14. Phone can show an empty text pane: `.step{min-height:56vh}`.
15. Step 15's heading runs four lines; every other step's runs at most two.

## Clean

Dark mode, CTA, footer, technical box, no horizontal overflow, no deck clipping at 1024 or 1440.
