# Diagrams for "How the SDD harness works"

The pictures in [`how-it-works.md`](../../how-it-works.md) and the top-level README. Each file is
an SVG exported from [Excalidraw](https://excalidraw.com/) with the scene embedded, so it is both
the image and its own source.

## Editing a diagram

1. Open [excalidraw.com](https://excalidraw.com/) and drag the `.excalidraw.svg` file onto the
   canvas (or use **Open**). The drawing loads as editable shapes.
2. Make the change.
3. **Export image** → **SVG**, with **Embed scene** and **Background** turned on.
4. Save it over the old file with the same name, and check it in a Markdown preview.

## Colour key

| Colour | Meaning |
|---|---|
| Blue | Writing: spec, plan, code |
| Violet | Independent checks: critic, gates, QA, review |
| Green | Shipping and outputs |
| Yellow / orange | You, or the coding agent you run |
| Gray | Config files and neutral parts |
| Red | A stop: the run asks you |
