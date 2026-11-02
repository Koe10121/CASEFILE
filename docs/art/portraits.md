# Portraits for CASE #001

The web game shows a portrait of each suspect in the interview, and changes it with their mood (D55). Every image is optional. Where one is missing, the game shows the neutral face, and if that is missing too it shows the person's initials. You can add portraits a few at a time.

## What to make

There are 25 images: six expressions for each of the four suspects, and one neutral portrait of Arthur for the cover.

| Expression | Shown when the suspect is… | Prompt line |
| --- | --- | --- |
| `neutral` | calm, formal, helpful (and any mood the game doesn't know) | calm, composed expression, looking at the viewer |
| `guarded` | cold, defensive, evasive, wary | guarded, wary expression, eyes slightly narrowed, mouth set |
| `angry` | hostile, irritated, bitter | angry expression, jaw clenched, glaring at the viewer |
| `afraid` | nervous, anxious, tense | anxious, frightened expression, eyes wide, breath held |
| `sad` | ashamed, broken, defeated | sad, ashamed expression, eyes downcast |
| `shaken` | just caught in a lie (always) | shocked, shaken expression, caught off guard, lips parted |

The full list of mood words is in `backend/src/casefile/expressions.py`.

## The free tool: Fooocus

[Fooocus](https://github.com/lllyasviel/Fooocus) is a free image generator that runs on your own GPU, and 8 GB is enough. It runs SDXL with good defaults, and it can keep a face the same across images.

1. Download the Windows package from the Fooocus GitHub page (a `.7z` file), unpack it, and run `run.bat`. The first start downloads the model (about 7 GB) and then opens in your browser.
2. Tick **Advanced**:
   - Set **Aspect Ratios** to `896×1152` (portrait).
   - Set **Image Number** to 4, so you get four to pick from.
   - If your version has an **Image Format** setting (under Advanced, in Developer Debug Mode), pick `webp`, which keeps the files small for git. If it doesn't, PNG works too.

## Keeping each face the same

1. **Make the neutral face first.** Use the character's prompt plus the `neutral` line and the style line. Generate until one image *is* that person, then save it. Every other expression is built from it.
2. **Make the other expressions from it.**
   - Tick **Input Image**, open the **Image Prompt** tab, and drop the neutral image into the first slot.
   - Open its advanced options and choose **FaceSwap**, with a weight of about 0.8.
   - Change only the expression line in the prompt and generate.
   - If the face drifts, raise the weight. If the expression won't change, lower it.
3. Keep the seed the same for one character's whole set if you can, since that helps the lighting match.

## Prompts

Each prompt is three parts joined with commas: the **character**, the **expression line** from the table above, and the **style line**.

**Style line (painted noir):**

> dark oil painting portrait, film noir lighting, single hard light from the side, muted desaturated colours, deep shadows, visible brushstrokes, head and shoulders, plain dark background, present day

**Negative prompt** (the box under Advanced):

> text, watermark, signature, frame, cartoon, anime, 3d render, extra fingers, deformed, blurry, bright colours

The character lines below are a starting point. Change them freely, because you are the art director here. Only the case file's facts are fixed: ages, Victoria's pinned-up hair, and Eleanor's short silver hair.

| Character | File folder | Character prompt |
| --- | --- | --- |
| Victoria Shaw, 34 | `S_VICTORIA` | a 34-year-old woman, executive assistant, dark hair pinned up neatly, slim, smart dark blazer, small earrings, tired eyes behind a polite face |
| Richard Okafor, 58 | `S_RICHARD` | a 58-year-old man, company finance director, broad shoulders, close-cropped greying hair, expensive open-collared shirt and dinner jacket, heavy watch |
| Eleanor Blackwood, 52 | `S_ELEANOR` | a 52-year-old woman, former concert cellist, short silver hair, elegant black evening dress, pearl earrings, upright posture |
| Thomas Reid, 63 | `S_THOMAS` | a 63-year-old butler, neat grey hair, clean-shaven, black tailcoat and white shirt, dignified, lined face |
| Arthur Blackwood, 61 (neutral only) | `S_ARTHUR` | a 61-year-old tech company founder, silver beard, sharp eyes, black turtleneck, confident, controlling |

## Where the files go

Save each image as `cases/blackwood_manor/portraits/<folder>/<expression>.webp`. For example:

```
cases/blackwood_manor/portraits/S_RICHARD/neutral.webp
cases/blackwood_manor/portraits/S_RICHARD/angry.webp
cases/blackwood_manor/portraits/S_ARTHUR/neutral.webp
```

`.png` and `.jpg` work too, but `.webp` keeps the repository small. Restart `casefile-api` afterwards, because it looks for portraits when it starts. The cover and the interview will then show them.

## How the CASE #001 set was made

The committed portraits were made with ComfyUI instead of Fooocus. Claude ran it on Kole's PC, with no custom nodes. To redo or extend the set, follow this recipe.

| Setting | Value |
| --- | --- |
| Tool | ComfyUI portable (NVIDIA), driven through its HTTP API |
| Model | SDXL base 1.0 (`sd_xl_base_1.0.safetensors`) |
| Neutral faces | txt2img, 896×1152, 30 steps, CFG 6, dpmpp_2m karras, 4 candidates per character, Kole picked one |
| Other expressions | img2img from the picked neutral, denoise 0.6, same prompt with only the expression line changed |
| Seeds | Neutrals: Victoria 1033, Richard 2044, Eleanor 3033, Thomas 4044, Arthur 5011. Expressions: neutral seed + 100, 200, 300, 400, 500 for guarded, angry, afraid, sad, shaken. Four replacements were needed to remove painted-in signatures: Eleanor shaken 3536, Richard guarded 2146, Richard shaken 2545, Victoria afraid 1335 |
| Output | WebP, 768×1024, quality 85 |
| Time | About 13–14 s per image on an RTX 5070 Laptop GPU (8 GB) |

Lessons from making the set:

- **Use a new seed for each img2img expression.** Reusing the neutral's seed gives near-identical, overcooked images.
- **Denoise 0.6 is the ceiling.** Below 0.6 the expression barely changes, and above it the face drifts. Guarded, angry and sad read clearly. Afraid and shaken are subtle. Stronger emotion would need face-aware tools (IP-Adapter, FaceSwap or an inpaint mask), which mean extra nodes or models.
- **Check the corners.** SDXL sometimes paints a fake artist's signature, so regenerate any image that has one.
