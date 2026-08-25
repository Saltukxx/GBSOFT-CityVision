# Model upgrade plan: architecture, augmentation, labeling tooling

Written 2026-08-21, after the road_damage false-positive investigation (manholes/decorative
pavers misclassified as damage) and the finding that 168 new hand-labeled frames were too
small a slice of a 12,391-image training set to reliably shift an already-converged model
via continued fine-tuning (see training run `train_aerial_yolo11_with_own_v1`/`v2`).

## 1. Architecture: move off YOLO11, and specifically toward RF-DETR

### The core problem this needs to solve

Our actual bottleneck isn't inference speed — it's **small-labeled-data + domain transfer**.
We have a handful of public aerial-pavement datasets (China, different camera/altitude) plus
a slowly-growing hand-labeled set from your own footage (currently ~1,900 frames total,
~170 of them new). Every architecture question should be judged against "does this help with
too-little-data-for-the-target-domain," not raw FPS — we're nowhere near needing that.

### Recommendation: pilot RF-DETR alongside the current YOLO11 pipeline

Current research (2026) is specific and relevant to our exact situation:

- RF-DETR's backbone (DINOv2, pretrained on internet-scale self-supervised data) transfers
  to small custom datasets better than YOLO's COCO-pretrained CNN backbone — cited directly
  for the ~200-labeled-image regime, which is close to our own new-data slice size.
- RF-DETR leads Roboflow's RF100-VL benchmark, which specifically measures **domain
  transfer** — the exact axis we're weak on (public Chinese pavement data → your Turkish
  footage).
- It's NMS-free (deterministic one-to-one prediction, same direction Ultralytics took with
  YOLO26), and the training API is described as low-friction: point it at a YOLO- or
  COCO-format dataset directory and it auto-detects the format — should drop into our
  existing `data/datasets/model_b_aerial` export with minimal glue code, not a rewrite.
- Trade-off: needs a GPU for good inference throughput, unlike YOLO which stays fast on
  CPU/edge. **This doesn't cost us anything given the current plan** — we're already running
  training and (per the earlier hardware discussion) planning GPU-backed inference (the L4
  card for the DL380 server), not CPU/edge deployment.

### What I'd explicitly *not* do right now

- **Don't jump to YOLO26 as the primary fix.** It's real and current (already sitting on the
  pod as `yolo26n.pt`), faster on CPU, and has a small-object-aware label assigner (STAL) —
  but independent benchmarks show it's mixed at nano/small model scale specifically, with
  YOLO11 still ahead there in some studies. It solves speed, not our actual problem (data/
  domain transfer). Worth knowing it's there, not worth switching to as the headline fix.
- **Don't chase the specialized academic UAV-DETR/CF-YOLO papers.** They post strong numbers
  but aren't one-line-installable via Ultralytics-style tooling — real integration cost for
  benefit that's not clearly bigger than RF-DETR's for our case.

### Concrete next step

Run RF-DETR and the current YOLO11 pipeline side by side on the *same* data
(`combined_public_v2`'s dataset, or whatever the current best export is) and compare on the
same real-footage test we've been using (your own two videos) — not just val-split mAP,
since we already learned that metric can look fine while real-world false-positive rate
doesn't. This is a bounded experiment (a few hours of GPU time), not a full migration
commitment — decide after seeing both perform on your actual footage.

## 2. Data augmentation

### Copy-paste augmentation — the highest-leverage, lowest-cost option

We already have exactly what copy-paste augmentation needs: labeled defect crops (pothole,
crack, road_damage boxes) and plenty of clean/background frames. The technique: cut a
labeled defect out of one image, paste it (with some randomized scale/rotation/blend) onto a
different background frame, and the label follows automatically since we know exactly what
we pasted and where. This synthetically multiplies the *rare* classes (pothole, crack —
already flagged as rare in the existing labeling guide) without requiring a single additional
minute of manual labeling. This directly targets the exact problem we hit — not enough real
examples to move the needle — without waiting on more hand-labeling.

Practical notes:
- Keep pasted defects visually plausible: don't paste a pothole onto a sidewalk paver texture,
  match it to a plausible road-surface background so the model doesn't learn a giveaway
  artifact instead of the actual defect.
- Also copy-paste the *negative* examples we specifically need — manhole crops pasted onto
  varied backgrounds, explicitly *not* boxed as damage — since that's the exact confusion
  we're trying to eliminate and hand-labeling alone is deferred right now.
- This is a preprocessing step before training, not a training-time-only augmentation —
  worth writing as a standalone script (similar to `prepare_highrpd.py`) that expands
  `combined_with_own` into a larger synthetic set, kept separate from the real-labeled data
  so we can always tell which is which.

### What's already happening (no change needed)

The training script already runs Ultralytics' standard augmentation (mosaic, HSV jitter,
flips, rotation via `--degrees`/`--flipud` for the aerial profile) — this is fine as-is and
doesn't need reconfiguring.

### Lower priority: generative/diffusion augmentation

Diffusion-based synthetic defect generation is a real 2026 research direction, but it's a
meaningfully bigger lift (needs its own model, own validation that generated defects are
realistic) for a benefit that's unproven for our specific narrow domain. Worth knowing about,
not worth building right now — copy-paste gets most of the value for a fraction of the effort.

## 3. Labeling tooling: use the CVAT install already sitting in this repo

**We don't need to adopt a new professional tool — CVAT is already installed and working**
(`tools/cvat`, `scripts/cvat_up.sh`/`cvat_down.sh`/`cvat_install.sh`, documented in
`docs/cvat-setup.md`). It's just configured for a different model's class list right now
(6 classes including `overflowing_container`/`street_waste`, ordered differently than our
4-class aerial scheme).

### Recommendation: adapt the existing CVAT install, don't shop for a new one

To use it for the aerial dataset:
1. Create a new CVAT project with labels in our exact order: `0 pothole, 1 road_crack,
   2 manhole, 3 road_damage` (must match `NAMES` in `label_aerial.py` / `configs/model_b_aerial.data.yaml`).
2. Upload `raw_frames/` (or the video directly — CVAT can extract frames itself, though we'd
   likely keep using our own 1fps extraction to stay consistent with the existing convention).
3. Annotate, export as YOLO 1.1 / Ultralytics format, drop into `labels_hand`-equivalent
   paths per the existing `docs/cvat-setup.md` workflow.

### Where CVAT actually helps vs. the custom browser tool

- **Multi-person labeling / review workflow.** If more than one person ends up labeling,
  CVAT has real user management and a review/QA pass built in — the custom tool has none of
  that (single local server, no accounts, no reviewer sign-off).
- **Richer QA tooling** — issue flagging, review status, inter-annotator comparison — that
  we'd otherwise have to hand-build (like the "revizyon" filter mode, which is a partial,
  DIY version of the same idea).

### Where it doesn't help, and what actually caused the labeling issue we found

Worth being direct about this: the mislabeled frame I found earlier (a tire-mark box labeled
`road_damage`) wasn't caused by tooling — the custom browser tool's keyboard-driven workflow
is fast and already well-matched to this specific task (1fps aerial frames, 4 fixed classes,
zoom-to-1:1 for thin cracks). That was a **judgment call under the existing guide**, not
something a fancier tool would have prevented. **Switching labeling tools doesn't fix label
quality by itself** — the "revizyon" review pass already planned is the actual fix for that.

CVAT is worth standing up in parallel specifically if labeling work is going to be shared
with someone else, or if formal reviewer sign-off becomes something you want as data volume
grows. It is not a prerequisite for continuing to make progress right now.

## Sequencing

1. **Now, in parallel with continued hand-labeling:** write the copy-paste augmentation
   script — cheapest, fastest lever, doesn't block on anything else.
2. **Once there's a stable current-best dataset export:** run the bounded RF-DETR vs. YOLO11
   side-by-side experiment on real footage, decide whether to switch based on that, not on
   benchmark papers alone.
3. **Only if/when labeling becomes a multi-person effort:** stand up the CVAT project for the
   aerial classes. Not urgent for solo labeling work.
