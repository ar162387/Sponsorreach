# SponsorReach UK logo pack

Generated with the built-in ImageGen tool from the supplied SR rising-arrow logo. The brand spelling is **SponsorReach UK**. The primary identity retains navy SR lettering and a teal arrowhead.

## Files

All seven logo PNGs have genuine transparent alpha backgrounds:

- `logo-horizontal.png`: full lockup for light backgrounds.
- `logo-stacked.png`: stacked mark and wordmark for larger brand applications.
- `logo-reversed.png`: exact horizontal geometry recoloured white and teal for navy backgrounds.
- `sr-mark.png`: colour symbol for compact UI placements.
- `sr-mark-reversed.png`: exact colour-symbol geometry recoloured white and teal.
- `sr-mark-navy.png`: ImageGen monochrome navy symbol.
- `sr-mark-white.png`: exact colour-symbol geometry recoloured white.

Also supplied: 16/32/64 px favicons, 180 px Apple touch icon, and a 1200×630 social-sharing graphic. The source social graphic is retained at its generated resolution.

The live website uses the compact SR mark with accessible, live Manrope text for the wordmark. The navy footer uses the white-and-teal mark. This keeps lettering clear at small sizes and avoids scaling a complete raster lockup too far down.

Do not stretch a logo, add shadows, redraw the arrow independently, or put navy marks on a dark background. Leave space around the mark; use a symbol rather than a full wordmark where the text cannot be read comfortably.

## Theme

| Use | Colour |
| --- | --- |
| Brand navy / primary CTA | #0B3B5B |
| Teal accent | #14B8AC |
| Deep teal | #087F79 |
| Small teal text on pale teal | #076E69 (contrast adjustment) |
| Warm white | #FAFBF8 |
| Pale teal | #EAF7F5 |
| Muted text | #4A6373 |
| Footer navy | #062D45 |

Manrope supplies headings and the live wordmark; DM Sans supplies body text and controls. Existing locally hosted font files and their licences remain unchanged.

## Generation and export method

ImageGen created the stacked master, horizontal logo, compact colour mark, navy monochrome mark and social graphic. White-on-transparent requests repeatedly produced speckles or glow. The user explicitly authorised precise recolouring instead. `export-assets.cjs` creates the final white variants from the clean colour originals, keeps teal where appropriate, and preserves every alpha byte. Alpha equality is checked for each derived variant; see `ASSET_VERIFICATION.json`.

Generated logos were mechanically trimmed to remove excess transparent canvas. Favicon and social outputs were resized with Sharp for their consuming file formats. No generation failures are included in the delivered pack.

To reproduce exports after replacing an approved colour original, run:

```sh
node sponsormatch/brand/export-assets.cjs
node sponsormatch/brand/preview-assets.cjs
```

Final consumed assets live in `sponsormatch/web/public/brand/`; the app icon files live in `sponsormatch/web/app/`. The source image-tool outputs also remain at their original Codex generated-image paths.

## Final prompt set

**Stacked master:** Recreate the supplied exact SponsorReach UK identity as a crisp flat transparent logo. Preserve intertwined SR, rising zigzag arrow, negative-space divisions and teal arrowhead. Navy #0B3B5B and teal #14B8AC. Centre the symbol above the exact text “SponsorReach UK”; bold geometric sans for SponsorReach, lighter UK. No background, shadows, glow, extra slogan or mockup.

**Horizontal:** Edit the approved master into a horizontal lockup, unchanged compact SR arrow left and exact one-line “SponsorReach UK” right. Navy and teal, modest transparent margins, no gradients or shadows.

**Colour symbol:** Edit the approved master to keep only SR and the rising teal arrow, remove all text, centre the mark with transparent padding, no additional elements.

**Navy symbol:** Edit the approved master to keep SR and arrow without text, entirely navy #0B3B5B, transparent background, no shadows.

**Social sharing:** Use the approved identity on warm white with exact text “Find relevant UK sponsors.” and “Reach out directly.” Navy and deep-teal typography, pale-teal arrow detail, generous safe margins, no photos, UI cards, statistics or added claims.

**White variants:** Precise recolouring of approved colour originals, authorised by the user, with exact source geometry and transparency preserved.
