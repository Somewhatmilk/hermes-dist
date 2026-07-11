# Image-Gen Prompting Techniques

**Source research:** July 2026 image-gen prompt-techniques deep research (10+ live sources + June 30 2026 ANIMA/Illustrious memory recall). Full 587-line deliverable lives at `C:\Users\somew\Documents\hermes-research\2026-07-02_model-architectures\image-gen-prompting-techniques.md` — this file is the condensed class-level reference for the cartographer gate.

## Why this matters for cartographer

The Five Principles (Direction → Format → Examples → Evaluate → Divide-Labor) **transfer to image-gen almost unchanged** because the diagnostic phase is identical. What changes is the implementation: "Format" means CLIP-token budgets + weighting syntax; "Examples" means seed-locked reference images + IPAdapter + ControlNet; "Evaluate" means ADetailer + LPIPS + the 5-sense manual QA; "Divide-Labor" means Regional Prompter + Attention Couple + multi-stage pipeline.

## The single biggest pitfall: model-family blindspots

Most "image-gen anti-patterns" come from **using CLIP-syntax on a Qwen-LLM-encoder model** (or vice versa). The encoder architecture changed between SD1.5/SDXL/Pony/Illustrious (CLIP) → Flux (CLIP+T5) → ANIMA/Qwen-Image (Qwen LLM). Forgetting which family you're on is the #1 cause of broken generations.

| Anti-pattern | CLIP-family (SD1.5/SDXL/Pony/Illustrious/Flux) | Qwen-family (ANIMA/Qwen-Image) |
|---|---|---|
| `(tag:1.2)` weighted syntax | ✓ use freely | ✗ Qwen reads as literal text → embedding collision → detail collapse |
| `BREAK` separator | ✓ use | ✓ use (this is the only separator ANIMA honors) |
| `// ---` comment separator | ✓ use in A1111 | ✗ Qwen reads as literal text → garbage in image |
| `masterpiece, best quality, hd` | SD1.5 ✓; SDXL ✓; Pony V6 XL ✗ (use `score_9, score_8_up`); Illustrious ✓; Flux ✗ (use natural-language) | ✗ minimal — let model infer |
| Standard CFG 7 | ✓ default | ✗ causes noise explosion — use CFG 1.0–2.0 (F4nta5IA) or CFG 5 for WAI-ANIMA on Forge Neo |
| `motion blur` tags | ✗ bleeds everywhere | ✗ same — use `blown`, `swaying`, `mid-air`, `trailing`, `swept` instead |
| `@@[artist1:4\|artist2:3]` style mixing | n/a (use LoRA block weights) | ✓ the only weighting-style operator ANIMA honors |

## Token weighting math (authoritative, from Diffusers docs)

| Format | Multiplier | Notes |
|---|---|---|
| `(cat)` | +1.1× | one paren pair |
| `((cat))` | +1.21× | compounded (NOT 1.2×) |
| `(cat:1.5)` | +1.5× exact | preferred for reproducibility |
| `[cat]` | -1.1× | square brackets decrease attention |
| `(cat:0.5)` | -2× effective | below baseline |

> Diffusers docs explicitly note: "Prompt weighting doesn't necessarily help for newer models like Flux which already has very good prompt adherence."

## BREAK / AND — when to use which

- **`BREAK`**: soft prompt-region separator. Each segment after BREAK gets its own attention region.
- **`AND`**: composable-diffusion per-region latent split (left/right halves).

In Regional Prompter, BREAK and AND are auto-converted based on mode (Attention mode uses BREAK; Latent mode uses AND). Either input works.

Beyond BREAK, Regional Prompter recognizes:
- `ADDCOL` — explicit column split
- `ADDROW` — explicit row split
- `ADDBASE` — first segment is base prompt applied everywhere
- `ADDCOMM` — common prefix applied to all regions

## Attention Couple vs Latent Couple

**Both solve the "two characters, one image, no genetic fusion" problem.**

- **Latent Couple** (opparco, Feb 2023): runs the U-Net **3× per generation**. 3 regions = 3 U-Net passes + 1 base pass. Composites latents at the end.
- **Attention Couple** (gcem156, March 10 2023 on [note.com](https://note.com/gcem156/n/nb3d516e376d7)): patches cross-attention k/v per region; the rest of the U-Net runs **once**. ~1.5× cost. Produces "more unified single image."

The **production implementation** of Attention Couple is hako-mikan's [sd-webui-regional-prompter](https://github.com/hako-mikan/sd-webui-regional-prompter) (1.8k★, AGPL-3.0). It supports both Attention mode (fast, single UNet pass) and Latent mode (3× cost, supports LoRA-per-region).

## Prompt Editing Schedule

A1111/Forge syntax: `[prompt_a:prompt_b:stop_step]`. Replaces the active concept mid-diffusion. Example: `[forest:trees:0.4] [sunlight:golden hour:0.7]` switches forest→trees at 40% steps, trees→sunlight at 70%.

**Orthogonal to Regional Prompter** — you can have per-region prompt schedules. Use cases:
- Pose → outfit evolution: pose early, refine clothing late
- Composition → detail: `[loose composition:tight detail:0.6]`
- Hand fix late-stage: `[masterpiece, detailed hands:0.7]`

## Prompt Travel (Deforum → video diffusion)

Deforum ([github](https://github.com/deforum-art/deforum-stable-diffusion)) was the canonical prompt-travel implementation — last meaningful commit Aug 30 2024, **now deprecated**. The community moved to video diffusion models (AnimateDiff, Wan 2.1, Hunyuan Video) for native temporal conditioning.

Wan 2.1 and Hunyuan Video use **Qwen-family text encoders** (not CLIP). The ANIMA anti-patterns above apply directly.

## Five-Principles implementation matrix for image-gen

| Principle | Text-LLM version | Image-gen implementation |
|---|---|---|
| **Direction** | Define role + persona + audience | **Subject-first order** + OpenArt's 5-question ritual (photo/painting? subject? details? art style? photo type?). Lead with subject; 95% vs 70% success rate (Tukanazo19666, 20-gen tests). |
| **Format** | Output structure + length | **CLIP token budget** (SD: 77; ANIMA: 200-300); weighting syntax appropriate to model family; separator choice (BREAK/AND/,/`// ---`); quality tag discipline (Pony uses `score_9` not `masterpiece`). Order matters: earlier = higher CLIP attention. |
| **Examples** | 2-5 few-shot examples | **Seed-locked reference images** via IPAdapter / ControlNet / LoRA / Textual Inversion. LoRA is the "example" of a character; IPAdapter is the example of a style. |
| **Evaluate** | Test cases + accuracy estimate | **Seed sweep (4-8 seeds) + CFG sweep (4/6/8/10)** + ADetailer pass + 5-sense manual QA (hands, eyes, background coherence, anatomy, semantic match). |
| **Divide-Labor** | Chain-of-thought / least-to-most | **Regional Prompter / Attention Couple** (text-side regional routing) OR **Latent Couple** (latent-space regional routing) OR **multi-stage pipeline** (layout→detail→upscale→post-process). |

## Universal anti-patterns (any diffusion model)

| # | Anti-pattern | Fix |
|---|---|---|
| 1 | **Keyword stuffing** — `masterpiece, best quality, ultra-detailed, 4k, 8k, hdr, RAW photo` | CLIP has 77-token budget; 1-3 quality tags at start, rest is subject |
| 2 | **Prompt items always missing** (a community-validated pain point) | Weight the missing items `(milk:1.3)` OR move to negative as `(no milk)` (use sparingly) |
| 3 | **Conflicting spatial cues** (`foreshortened staff` + `staff larger than character`) | Pick one spatial framing |
| 4 | **Repeating same concept 3+×** (e.g. `red hair, red locks, scarlet hair`) | Pick one canonical term |
| 5 | **Blur-inducing tags** (`motion blur`, `speed lines`) | Use `blown`, `swaying`, `mid-air`, `trailing`, `swept` |
| 6 | **Putting LoRA in negative prompt** | A1111 forbids it: "LoRA cannot be added to the negative prompt" |

## The Five-Principle image-gen workflow

**Goal:** "Generate an image of a Victorian woman reading in a library."

1. **Direction** — Subject-first: "A 30-year-old woman in 1880s Victorian dress, reading a leather-bound book, in a candlelit library, late afternoon golden light, oil painting by John Singer Sargent"
2. **Format** — Model = SDXL, A1111, CLIP, 77-token budget. Structure: `[quality], [subject], [clothing], [action], [environment], [lighting], [style]`. Final: `masterpiece, best quality, 30-year-old woman, Victorian dress, reading leather book, candlelit library, golden hour, oil painting, John Singer Sargent, (detailed face:1.2), (detailed hands:1.1), 8k` (≈ 35 tokens)
3. **Examples** — IPAdapter with Sargent's "Mrs. Carl Meyer" portrait for style; optionally a real reference of Victorian library
4. **Evaluate** — 4 seeds × 3 CFG (5/7/9) = 12 images. ADetailer on face. Manual 5-sense QA. Record (seed, prompt, params)
5. **Divide-Labor** — Multi-stage: txt2img 512×512 → img2img 768×768 (denoise 0.4) → hires fix 1536×1536 (4x-UltraSharp, denoise 0.3) → ADetailer pass

**Total time:** ~10 minutes for 12 generations + 1 final.

## Source inventory

- **HuggingFace Diffusers prompting docs** — authoritative weighting math (`(cat:1.5)` = +1.5×)
- **hako-mikan/sd-webui-regional-prompter** (1.8k★) — BREAK/AND syntax, ADDCOL/ADDROW/ADDBASE/ADDCOMM modifiers, Attention vs Latent mode
- **opparco/stable-diffusion-webui-two-shot** — original Latent Couple extension with the canonical 2-girl BREAK/AND example
- **gcem156 note.com (Mar 10 2023)** — original Attention Couple article; canonical "note.com ANIMA reference"
- **kohya-ss/sd-webui-additional-networks @ attention_couple branch** — experimental Attention-Couple-with-LoRAs impl
- **hako-mikan/sd-webui-lora-block-weight** (1.2k★) — block-weighted LoRA syntax `<lora:foo:1:lbw=IN02>` + `:start`/`:stop` step control
- **A1111 wiki Features** — LoRA syntax `<lora:filename:multiplier>`; "LoRA cannot be added to the negative prompt"
- **OpenArt Stable Diffusion Prompt Book (2022 PDF)** — 105 pages, full prompt engineering primer; the "earlier in prompt = higher attention" rule; 5-question ritual
- **June 30 2026 Civitai articles research** (memory) — ANIMA/Illustrious/Pony anti-patterns from F4nta5IA (31399), Boredafk (31037), Fasd800 (31241), elderagent (31885), Tukanazo19666 (30826), nur2asdASD901 (31760)
- **June 30 2026 Reddit r/PromptEngineering sweep** (memory) — Five Principles (Direction → Format → Examples → Evaluate → Divide-Labor)

For the **full 587-line deliverable** with worked examples, full citation URLs, and the Qwen-LLM / Pony V6 / Illustrious / Flux variant tables, see `C:\Users\somew\Documents\hermes-research\2026-07-02_model-architectures\image-gen-prompting-techniques.md`.