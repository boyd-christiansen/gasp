# Gasp face mark

Generated with the built-in image generation tool, October 31, 2026. These are project assets, not third-party brand marks.

- `face-open.png`: primary black wireframe logo on transparent background.
- `face-partial.png`, `face-closed.png`: retained alternate artwork, unused by the animation.
- `app-icon.png`: white mark on black, used to package `macos/Resources/Gasp.icns`.

The capture screen and floating recording indicator sample the alpha mask of `face-open.png` to dissolve the logo into particles and reform it. The cycle is calm while ready and faster while recording. Reduced-motion settings keep the logo still. This indicates app activity, not a measurement of mouth movement. The web renderer is `../logo-particles.js`; its native counterpart is `macos/Sources/LogoParticles.swift`.

## Prompts

**Open:** A simple front-facing geometric wireframe human face with lips parted in a small vertical oval, as if softly gasping. Pure black linework on a transparent background. Calm and abstract. Minimal polygonal facial mesh, clean outer outline, broad cheek and forehead planes, simple nose, restrained eye lines, visible open mouth. Strokes readable at 32 pixels. Symmetric square composition with generous padding. No gradients, shading, text, shadows, dots, neck or shoulders.

**Partial (edit of open):** Change only the mouth opening: reduce its vertical height by half so the lips are slightly ajar. Preserve facial lines, silhouette, eyes, nose, cheeks, line weight, position, scale, canvas, black color and transparent background. No added elements; register with the original for animation.

**Closed (edit of open):** Change only the mouth opening: close the lips into a relaxed short horizontal seam. Preserve facial lines, silhouette, eyes, nose, cheeks, line weight, position, scale, canvas, black color and transparent background. No added elements; register with the original for animation.

**App icon (edit of open):** Convert the attached Gasp logo into a macOS application icon. Preserve the wireframe face and gasping mouth. White face linework on solid near-black (#151515), centered on a square canvas with even padding. Flat black and white, no text, letters, shadows, gradients, extra symbols, borders or mockup.

**Consistency repair:** Remove all pupils and iris marks from the open-frame eye interiors while preserving the wireframe face and transparent background. Derive the partial and closed frames from that corrected master, changing only the mouth and explicitly retaining pupil-free eyes. All three frames were compared on a white background before packaging.
