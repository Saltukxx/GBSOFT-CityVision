# CityVision — English Instagram Reel (46.4 s, 1080×1920, 60 fps, 115 BPM beat-locked, loops seamlessly)

Composition: `CityVision-Promo-EN` (silent master: `CityVision-Promo-EN-Silent`)
Render: `npm run render:promo` → `out/CityVision-Promo-EN-Reel.mp4`
Motion blur: CameraMotionBlur (6 samples). Fast preview without blur: composition `CityVision-Promo-EN-QA`, `npm run qa:promo`.
Sound design: `npm run sfx:promo` (synthesised, frame-locked to `src/promo/timeline.json`)
Music: `public/muzik-lightbeats.mp3` from 63.147 s (Pixabay Content License, commercial use OK);
every scene starts on a beat (src/promo/timeline.json, lengths in beats); the drop lands on the CityVision logo at 0:20.87. The end card closes into orange = frame 1, so the reel loops without a seam.

Optional voiceover (each line starts at the given time):

| Time | Scene | On screen | VO line |
| --- | --- | --- | --- |
| 0:00 | map | Your complaint map says 12 | "Your complaint map says twelve." |
| 0:02.1 | wrong | WRONG. *by a lot.* | "Wrong. By a lot." |
| 0:04.2 | says | It says 12 → There are *actually* 147 | "There are actually a hundred and forty-seven." |
| 0:08.4 | where | where were they hiding? | "So where were they hiding?" |
| 0:09.9 | feed | potholes, cracks, bins, dumping | "Potholes nobody reported. Cracks spreading. Bins overflowing. Illegal dumping." |
| 0:16.2 | findout | Day 43 · *from a phone call.* | "And you find out forty-three days later. From a phone call." |
| 0:18.8 | km | 380 KM *of road to check.* | "Three hundred and eighty kilometres. By car. By eye." |
| 0:20.9 | logo | CityVision *by GBSoft* | "Meet CityVision." |
| 0:22.4 | every | Every flight. Every street. Every defect. One map. | "Every flight, every street, every defect. On one map." |
| 0:26.6 | real | 147 issues · The real number. | "The real number." |
| 0:29.2 | notify | When a new pothole opens up, it taps you on the shoulder. | (same) |
| 0:32.4 | onetap | One tap. *Crew sent.* | "One tap. Crew sent." |
| 0:35.0 | morning | Every morning, 06:30, before the first shift. | (same) "...you know exactly where to go." |
| 0:38.6 | fewer | Fewer complaints. (the 4 issues get fixed) *Safer streets.* | (same) |
| 0:42.8 | end | CityVision · Book a demo · gbsoftt.com | "CityVision. Book a demo." |

Suggested caption:
Your complaint map is lying to you. 🚧
CityVision flies the same routes by drone, finds every pothole, crack, overflowing bin
and illegal dump with AI, and puts them on one map, with photo + GPS. One tap sends the crew.
Book a demo → gbsoftt.com
#smartcity #drones #AI #roadsafety #govtech #municipality #infrastructure

## Voiceover (v3, ElevenLabs "Sarah")

Lines and their beat-locked positions live in `scripts/promo_vo.py` (`LINES`).
`npm run vo:promo` generates any missing clips (cached in `vo/clips/`, git-ignored), places them,
and writes `public/promo/vo.wav` + ducked music/SFX (music −7 dB, SFX −3 dB under speech).
Render: `npm run render:promo:vo` → composition `CityVision-Promo-EN-VO`.
Key: `ELEVENLABS_API_KEY` in `.env` (git-ignored). Commercial use needs a paid ElevenLabs plan.

---

# Series: "How it works in 30 seconds" (40.2 s, white first / navy second, accent per step)

Composition `CityVision-HowItWorks` · `npm run vo:howto` → `npm run sfx:howto` → `npm run vo:howto` (re-duck) → `npm run render:howto`
Engine shared by future reels: `src/series/engine.tsx` (beat grid, transitions, motion blur, dither, audio) + `src/series/ui.tsx`.
Music starts on the drop (84.018 s). Animations key off Sarah's word timings (`src/howto/vo_words.json`).

| Step | Look | Sarah |
| --- | --- | --- |
| Hook | white · orange | How does CityVision work? Thirty seconds. |
| 1 Fly | navy · teal | One. A drone flies a planned route. Same streets, every time. |
| 2 Spot | white · orange | Two. AI checks every frame for potholes, cracks, overflowing bins and dumping. |
| 3 Pin | white · yellow | Three. Each one gets a photo and a GPS pin. |
| 4 Merge | navy · pink | Four. Seen on three flights? Still one issue. One work order. |
| 5 Blur | white · purple | Five. Faces and number plates are blurred in every photo. |
| 6 Approve | white · green | Six. Someone on your team approves it. |
| 7 Fix | navy · orange | Seven. The crew drives straight there. |
| Recap | white · all | Fly. Spot. Pin. Fix. Repeat. |
| End | navy → white (loops) | CityVision. Book your demo. |

Caption: How does a city find every pothole before the first complaint? 30 seconds. 🚁
Drone → AI → photo + GPS pin → one work order → crew. Faces and plates blurred automatically.
Book a demo → gbsoftt.com  #smartcity #drones #AI #govtech #roadsafety #municipality

## v2 — real map + own footage
- Map: real Kartal streets from OpenStreetMap (`public/maps/kartal.json`, ODbL; "© OpenStreetMap" shown on every map card),
  Apple-Maps-like light + navy styles: `python3 scripts/howto_map.py` → `node scripts/bake-maps.mjs`.
  Routes are shortest paths on the real road graph (survey flight 1.5 km, crew route 1.0 km).
- Footage: own DJI flights (16 Aug 2026, Kartal). `../../.venv/bin/python scripts/howto_footage.py` crops, runs
  CityVision's anonymiser on every frame, and takes boxes straight from the pipeline's detections.jsonl:
  pothole 0.98 (180530 f1560), crack 0.78 (181137 f10), road damage 0.94 (181137 f240).
- Spot line now says "potholes, cracks and road damage" (the models have no dumping class).
- Merge cards use three frames of the same real pothole as stand-ins for three flights (illustrative).

---

# Series: "Can you beat the drone?" (37.6 s, game format, real footage)

Composition `CityVision-BeatTheDrone` · `npm run vo:game` → `npm run sfx:game` → `npm run vo:game` → `npm run render:game`
Rounds use one visually verified real detection each (own DJI flights, anonymised):
pothole 0.98 (180530 f1560) · road damage 0.94 (181137 f240) · crack 0.78 (181137 f10).
Rejected during the frame check: 175412 f1364 (pothole + damage boxes are the same patch),
181137 f1430 (one box is the sidewalk — false positive), overflowing-container hits (one is a car bonnet).
Each round = title 5 beats → countdown 6 beats (3.1 s, real three seconds) → reveal 4 beats.

| Scene | Sarah |
| --- | --- |
| Hook (navy) | Can you spot it faster than a drone? You get three seconds. |
| Round 1 | Round one. Find the pothole. … Easy. |
| Round 2 | Round two. Find the road damage. … Got it? It did. |
| Round 3 | Round three. Find the crack. … Most people miss this one. |
| Score (navy) | Three for three. How did you do? |
| Map (Kartal, every street lights up) | Now picture that on every street in your city. |
| End (white → navy loop) | CityVision. Book your demo. |

Caption: Can you beat the drone? 3 rounds, 3 seconds each. 🚁
Real footage from our flight in Kartal — faces and plates blurred automatically.
Drop your score below 👇  ·  Book a demo → gbsoftt.com
#smartcity #drones #AI #roadsafety #govtech #istanbul #challenge

---

# Series: "Dear Mayor" (40.2 s, dramatised letters + real footage)

Composition `CityVision-DearMayor` · `npm run vo:mayor` → `npm run sfx:mayor` (also cuts the music with the breath) → `npm run vo:mayor` → `npm run render:mayor`
Voices (ElevenLabs): Bill (letter 1), Jessica (letter 2), Chris (letter 3), Sarah (narrator).
Music starts at 59.494 s so the drop (84.018 s) lands on "What if the city found it first?"; the beat before it is held silent (−45 dB).
End card states: "Letters dramatised · footage: our test flight in Kartal · faces & plates blurred".

| Scene | Voice | Line |
| --- | --- | --- |
| Letter 1 (handwritten) | Bill | Dear Mayor. There's been a hole outside my door since March. My wife tripped on it last week. |
| Answer (pothole 0.98) | — | "Meanwhile, overhead…" · FOUND ON THE FIRST FLIGHT |
| Letter 2 (message) | Jessica | Dear Mayor. The road on our street is cracking. I've called twice. Nobody came. |
| Answer (crack 0.78) | — | "Meanwhile, overhead…" |
| Letter 3 (typewriter) | Chris | Dear Mayor. That's my second tyre this year. Second. |
| Answer (road damage 0.94) | — | "Meanwhile, overhead…" |
| Pile → silence | — | letters pile up, murmur of "Dear Mayor…", one beat of silence |
| Turn (drop) | Sarah | What if the city found it first? |
| Map (Kartal) | Sarah | CityVision flies your streets on a schedule and puts every issue on the map. Before anyone has to write. |
| Reply letter | Sarah | Dear Mayor. We found it first. — CityVision |
| End | Sarah | Book your demo. |

Caption: Every city gets these letters. 📮
What if the city found it first? CityVision flies your streets on a schedule, finds potholes, cracks and road damage,
and puts them on one map — with photo + GPS. (Letters dramatised; footage from our test flight in Kartal.)
Book a demo → gbsoftt.com  #smartcity #govtech #drones #AI #roadsafety #municipality

## Dear Mayor v2
- Map: Kadıköy (OSM, `public/maps/kadikoy.json`). `python3 scripts/citymap.py kadikoy` → `node scripts/bake-maps.mjs kadikoy src/mayor/map.json`.
  `citymap.py` is the generic district tool (sea built from OSM coastline; add a district to DISTRICTS to use it).
- New real shots (`../../.venv/bin/python scripts/mayor_footage.py`, anonymised, cropped in):
  pothole 0.96 (181137 f814, approach clip) · road damage 0.88 (175412 f1728) · road damage 0.94 (175412 f258).
  Rejected on visual check: 182111 f1854–1968 (box on twigs), f870/f46 (too faint), 175412 f1362 (fresh repair patch).
- Labels: clips say "our test flight"; letters signed "a resident / a driver, Kadıköy" (dramatised).

---

# Series: "Same street. Different eyes." (24.0 s, split screen, real footage)

Composition `CityVision-DifferentEyes` · `npm run vo:eyes` → `npm run sfx:eyes` (also cuts music + silent beat) → `npm run vo:eyes` → `npm run render:eyes`
Top half = the same real footage as a passer-by glances at it (washed out, unsteady, defocused, phone notification);
bottom half = CityVision's view (sharp, real detection box, "logged · photo + GPS").
Moments: pothole 0.98 (walked past it) · road damage 0.88 (drove over it) · pothole 0.96 (stepped around it) · road damage 0.94 (didn't look down).
Tally "Noticed 0 / Logged 4" → silent beat → drop: halves split open onto the Kadıköy map (illustrative pin positions).
Sarah: "Same street. Different eyes." … "CityVision. Book your demo."

Caption: Same street. Different eyes. 👀
We walk past it, drive over it, step around it. CityVision logs it — with a photo and GPS.
(Footage: our own test flight; faces and plates blurred.)  Book a demo → gbsoftt.com
#smartcity #govtech #drones #AI #roadsafety #istanbul #kadıköy

## Different Eyes v2 — eye-level street clips
Top half now uses real eye-level footage from Pixabay (Pixabay Content License, commercial use OK):
#109674 POV street walk · #7713 legs crossing · #21782 footsteps on cobbles · #6590 man on his phone (face blurred).
Source files in `public/eyes/stock/` (git-ignored); cut/crop/face-blur: `../../.venv/bin/python scripts/eyes_stock.py` → `public/eyes/street/`.
Captions: walked past it · stepped right over it · stepped around it · didn't look down.
End card credits: drone footage = our test flight, street clips = Pixabay. Swap in own phone clips later via `eyes_stock.py`.

---

# Series: "CityVision Wrapped" (39.2 s, real pipeline numbers)

Composition `CityVision-Wrapped` · `npm run stats:wrapped` → `npm run vo:wrapped` → `npm run sfx:wrapped` → `npm run vo:wrapped` → `npm run render:wrapped`
Every number comes from `src/wrapped/stats.json`, generated from outputs/dji_175412, dji_180530, dji_181137, dji_182111_run
(own flights, 16 Aug 2026, Kartal, 17:54–18:24). Manholes excluded per labelling policy.
Cards: 6:03 in the air · 10,907 frames · 958 sightings (701 road damage / 194 pothole / 63 crack) · merged into 75 issues
(46 / 28 / 1) · top category road damage · strongest find pothole 0.98 · 365 maybes thrown out · 12 flagged for a human ·
1,059 person sightings, every face blurred · "All of that, in half an hour. Now imagine a year."
Mosaic: 24 frames sampled evenly from the 4 flights, anonymised (`scripts/wrapped_assets.py`).

Caption: Our test flights, Wrapped. 🎁 6 minutes in the air. 958 sightings. 75 real issues. 365 maybes thrown out.
Every face blurred. All real numbers from one evening in Kartal. Now imagine a year. → gbsoftt.com
#smartcity #govtech #drones #AI #wrapped #istanbul
