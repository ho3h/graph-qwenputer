#!/bin/zsh
# The public bundle's contents, by allow list: no model weights, no sealed data. exam/bundle.sh DEST
cd "<repo>"
D=${1:?dest}; mkdir -p $D
copy() {
  for f in "$@"; do
    if [[ -e $f ]]; then
      mkdir -p $D/${f:h}
      cp -R $f $D/$f
    fi
  done
}
copy SPEC.md PATH.md DESIGN.md lib/reflib.py host/tools.py tools/memguard.py
copy data/heldout/nyc/nyc.graph.json data/heldout/nyc/nyc.questions.json
copy exam/REGISTRATION.md exam/R1.md exam/AFTER.md exam/FREEZE.json exam/FREEZE_r1.json exam/items/nyc.json
for f in exam/*.py exam/*.sh t8/fw/*.py t8/fw/*.sh t8/arms.py speed/fast.py speed/prove.py speed/proofs.json rvc/box.py rvc/decode.py rvc/graphlib.c ctrl/flows.py; do copy $f; done
copy t8/fw/build_writes/writes.elf t8/fw/build_r1/writes.elf
copy reviews/round4-critical.md reviews/round4-steelman.md reviews/round5-critical.md reviews/round5-steelman.md reviews/r1-prerun-critical.md
copy web/index.html
R=exam/results
for f in nyc_score.json nyc_r1_score.json nyc_r1_pairs.json nyc_d1m_score.json nyc_r1_d1m_score.json nyc_d1r_score.json nyc_r1_d1r_score.json nyc_d1r_replies.md nyc_r1_d1r_replies.md nyc_host.jsonl nyc_r1_host.jsonl nyc_window_check.json nyc_window_flip.json nyc_window_remainder.json nyc_r1_compare.json nyc_r1_stock_check.json nyc_d1m_ambig_posthoc.json nyc_edit_draw.json nyc_r1_edit_draw.json raw_hashes_r1.txt plan_nyc.json; do copy $R/$f; done
copy $R/nyc/*.json(N) $R/nyc/*.jsonl(N) $R/nyc_r1/*.json(N) $R/nyc_r1/*.jsonl(N) $R/nyc_d1m/all.jsonl $R/nyc_r1_d1m/all.jsonl $R/nyc_d1r/all.jsonl $R/nyc_r1_d1r/all.jsonl
copy $R/nyc_edit/all.jsonl $R/nyc_edit/score.json $R/nyc_edit/transcripts.md $R/nyc_r1_edit/all.jsonl $R/nyc_r1_edit/score.json $R/nyc_r1_edit/transcripts.md
copy $R/nyc_r1_edit_stock/all.jsonl $R/nyc_r1_edit_stock/score.json $R/nyc_r1_edit_stock/transcripts.md
A=$R/after
for f in alone.jsonl alone_score.json other/all.jsonl other_host.jsonl other_score.json other_r/all.jsonl other_r_score.json other_r_replies.md stops/all.jsonl stops_score.json stops_replies.md window_check.json window_flip.json remainder.json plan.json raw_hashes.txt demo_check.json mapped; do copy $A/$f; done
# Added for the public release: everything the post and README cite.
A=$R/after
copy $A/demo/all.jsonl $A/demo_draw.json $A/journeys/all.jsonl $A/journeys_draw.json $A/journeys_score.json $A/lines2/all.jsonl $A/lines2_draw.json $A/choice/all.jsonl $A/choice_draw.json
copy $A/control_plainc.jsonl $A/control_plaind.jsonl $A/control_plaine.jsonl $A/control_zeroed.jsonl $A/mapped/M1.jsonl
copy $R/mini/limits_score.json
copy exam/LIMITS.md exam/MINI.md exam/items/nyc_all.json t8/fw/build_r2/writes.elf t8/fw/build_r2/graphlib.c t8/fw/build_r1/graphlib.c
copy reviews/round6-critical.md reviews/round6-steelman.md reviews/round6-coldread.md reviews/round7-newreader.md reviews/round7-expert.md reviews/round7-design.md reviews/round8-figures.md reviews/round9-readme.md reviews/round10-critical.md reviews/round10-steelman.md
copy web/index.html web/template.html web/build.py web/check_figures.py web/geometry.py web/geometry.json web/land.py web/land.json web/near.py web/near.json web/OBJECTIONS.md
# Rows the README cites, and the firmware source.
copy $R/mini/score.json $R/mini/limits_edits.json $R/mini/r2_more_score.json $R/mini/cleanroom_walk.txt $R/mini/r2_fuzz $A/w $A/shared $A/shared_draw.json $A/control_map.json t8/fw/results/writes_fuzzfw.json
copy fw/graphlib.c fw/graphlib.diff tok/gen_fw.py tok/boot_tok.py tools/rt_mini.c t8/fw/build_writes/graphlib.c
copy $R/mini/r2 $A/gaslight/all.jsonl $A/gaslight_draw.json $A/gaslight_map.jsonl $A/gaslight_score.json
copy $A/lines3/all.jsonl $A/lines3_draw.json $A/recommend/all.jsonl $A/recommend_draw.json $A/v_score.json $A/stock_d1m0/all.jsonl $A/stock_d1m1/all.jsonl $A/stock_d1m2/all.jsonl $A/stock_d1m0/stock_sample.json $A/stock_d1m1/stock_sample.json $A/stock_d1m2/stock_sample.json
copy t8/fw/build_r4/writes.elf t8/fw/build_r4/graphlib.c t8/fw/build_r3/writes.elf t8/fw/build_r3/graphlib.c $R/mini/r4/r4_directed $R/mini/r4/r4_cost.jsonl $R/mini/r2/r3_cost_mac.jsonl $R/mini/r2/r4_cost_mac.jsonl $A/r4_stock/all.jsonl $A/r3_draw.json
# What release/run.py needs, without results, logs or builds.
for d in tok exec fw cop rvc host speed tools t8/fw; do
  mkdir -p $D/$d
  rsync -a --exclude results --exclude 'build' --exclude 'build_writes/results' --exclude '*.log' --exclude '__pycache__' --exclude '*.dylib' --exclude '*.npz' --exclude '*.jsonl' --exclude 'test' $d/ $D/$d/ 2>/dev/null
done
mkdir -p $D/vendor/qwenputer-riscv; rsync -a --exclude '__pycache__' vendor/qwenputer-riscv/chipformer vendor/qwenputer-riscv/LICENSE vendor/qwenputer-riscv/pyproject.toml $D/vendor/qwenputer-riscv/
mkdir -p $D/host/test $D/t8/fw/build_r5; cp host/test/tiny.graph.json $D/host/test/ 2>/dev/null; cp t8/fw/build_r5/writes.elf t8/fw/build_r5/graphlib.c t8/fw/build_r5/tok_lits.h t8/fw/build_r5/graphlib_bytes.c $D/t8/fw/build_r5/
copy exam/items/nyc_t.graph.json exam/lines_run.py t8/fw/worked.py
# r6: a closed stop blocks (exam/AFTER.md).
mkdir -p $D/t8/fw/build_r6; cp t8/fw/build_r6/writes.elf t8/fw/build_r6/graphlib.c t8/fw/build_r6/tok_lits.h t8/fw/build_r6/graphlib_bytes.c $D/t8/fw/build_r6/
copy exam/items/nyc_b.graph.json exam/journeys_run.py
copy exam/items/nyc_b_all.json $R/r6_all_score.json $R/r6_routes $R/r6_directed $A/r6_walk $A/r6_walk_a1 $A/r6_journeys $A/r6_alone.json $A/r6_walk_sim.json $A/r6_walk_draw.json $A/t1
# The rows behind the current build's machine exams, the opened maps and their builder, and the private commit list (round 16).
copy $R/r6_all $R/s1_nyc-cf $R/s1_nyc-relabelled $R/r6_limits data/MANIFEST.sha256 data/heldout/nyc-cf data/heldout/nyc-relabelled data/build/build_nyc_variants.py data/build/common.py exam/items/nyc_b_all.json
git log --format='%h %ad %s' --date=iso-strict -- . > $D/exam/HISTORY.txt
copy exam/t1_score.py exam/t2_score.py exam/s2_score.py exam/t2_run.py exam/draw_s5.py exam/draw_e6.py exam/edit_run_b.py exam/sealed_open.py exam/sealed_items.py exam/sealed_q.py
copy exam/items/sealed/nyc-cf_b.graph.json exam/items/sealed/nyc-relabelled_b.graph.json $R/s1_nyc-cf_score.json $R/s1_nyc-relabelled_score.json $R/r6_limits_score.json $R/r6_routes2 $A/t2 $A/t3 $A/f1 $A/e6 $A/e6_draw.json $A/s2_nyc-relabelled $A/s2_nyc-cf $A/s2_nyc-relabelled_draw.json $A/s2_nyc-cf_draw.json $A/s2_nyc-relabelled_score.json $A/s2_nyc-cf_score.json $A/s3_nyc-cf_draw.json $A/s3_nyc-relabelled_draw.json $A/s4_nyc-cf.jsonl $A/s4_nyc-relabelled.jsonl $A/s4_nyc-cf_score.json $A/s4_nyc-relabelled_score.json $A/s5_draw.json
copy reviews/round13-*.md(N) reviews/round14-*.md(N) reviews/round15-*.md(N)
cp release/run.py release/requirements.txt $D/
copy $R/mini/r5/r5_directed $R/mini/r5/r5_cost.jsonl $R/mini/r5/round11_r2_aimed.jsonl $A/z3b/all.jsonl $A/z3/all.jsonl $A/z3c/all.jsonl $A/z3_draw.json $A/round11 reviews/round11-critical.md reviews/round11-steelman.md reviews/round12-final.md exam/results/mini/r5/r5_score.json
# The release's front door, at the repo root.
cp release/README.md release/try.py release/gq.py release/THIRD-PARTY.md release/LICENSE $D/
cp release/gitignore.txt $D/.gitignore
cp -R release/docs release/toolkit $D/
mkdir -p $D/licenses; cp vendor/qwenputer-riscv/LICENSE $D/licenses/qwenputer-LICENSE
cp -R release/examples release/check $D/
# Local paths out of run scripts and logs, except anything a freeze file hashes.
python3 release/sanitize.py $D
echo bundled $(du -sh $D | cut -f1)
