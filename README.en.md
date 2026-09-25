# Lyric Motion — Kinetic Lyric Video Maker

*Lyric Motion is built on [JIZURA](https://github.com/852wa/JIZURA) by 852wa (MIT License). It adds a Vietnamese edition (`vi/`, served by default by `server.py`), Vietnamese font support and local auto-lyrics. The rest of this guide describes the upstream JIZURA features and panels.*

Turn lyrics into animated lyric videos in your browser. JIZURA combines layouts, entrances, holds, exits, decorations, text treatments, backgrounds, camera moves, effects and transitions. Change the seed or press **Create a variation** to explore another arrangement.

**[Open the English app](https://852wa.github.io/JIZURA/en/)** · [日本語版](https://852wa.github.io/JIZURA/) · [Japanese guide](README.ja.md) · [Hướng dẫn tiếng Việt](README.md)

The English and Japanese browser editions share the same project format and saved browser data. Use the language links at the top of the editor to switch editions without changing your lyrics or settings. English After Effects panels are available as [ScriptUI](https://852wa.github.io/JIZURA/JIZURA_AE_en.jsx) and [CEP](https://852wa.github.io/JIZURA/JIZURA_CEP_en.zip) downloads. The AE JSON format is the same in both languages.

## Quick start

1. Paste lyrics into the left panel, one phrase per line. The built-in English sample is shown on a fresh install.
2. Optionally import audio. JIZURA detects beats and can snap cut boundaries to them. Use **Tap to sync** to mark the start of each line by pressing Space during playback.
3. Press **Create a variation** (or `R`) to randomize the style, mood, motion, palette and arrangement. **Previous** and **Next** navigate variations; **Change one thing** rerolls just one part.
4. Set aspect ratio, resolution and frame rate, then export MP4. Advanced mode adds a PNG sequence, transparent PNGs, color key backgrounds and individual technique controls.

Lyric syntax: `I remember/the dawn` makes a manual cut; `*word*` emphasizes a word; a final `!` adds a flash and shake; `lyric|note` adds small annotation text; `[01:23.45]lyric` imports an LRC timestamp; `# comment` is ignored.

Use **Save** and **Open** for `.jizura.json` projects. **Export for AE** creates arrangement data to import into the After Effects panel. Generated videos and images belong to their creators; rights to music and lyrics remain with their respective rights holders. Project files, lyrics and audio are handled in the browser. Google Fonts are loaded as needed. The tool is MIT licensed; see [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Build and publish

Run `python3 build.py` at the repository root. It creates `index.html` and `en/index.html`, both standalone pages for GitHub Pages. Run `python3 build_ae.py --lang en` to rebuild `JIZURA_AE_en.jsx`, and `python3 build_cep.py --lang en --out dist` to build `dist/JIZURA_CEP_en.zip` (copy the ZIP to the repository root for Pages downloads). Commit the built pages, panels and translation sources together. Publish from the repository root on GitHub Pages; the English edition is then served at `/JIZURA/en/`. Open either HTML file locally for offline use, with installed fonts as a fallback.

Install `JIZURA_AE_en.jsx` in After Effects' `Scripts/ScriptUI Panels` folder, restart AE, then open it from the Window menu. The English CEP package has a distinct extension ID, so it can coexist with the Japanese CEP panel. Extract the ZIP and use its Windows or macOS installer. These panels require After Effects to verify motion and export behavior; automated checks use a mock AE environment.

## Local auto-lyrics (optional)

`server.py` serves the app locally and adds an **Auto lyrics** panel: speech-to-text with Groq Whisper, optional clean-up with DeepSeek, and the result is written into the lyrics box as timed LRC lines. The panel appears only when the page is served by `server.py`; GitHub Pages and `file://` are unchanged.

```sh
cp .env.example .env      # add GROQ_API_KEY (and DEEPSEEK_API_KEY for the clean-up step)
python3 server.py         # http://localhost:8765/
```

Keys are read from `.env` (git-ignored) and stay on the server side. Audio is downsampled to 16 kHz mono in the browser before upload (about 13 minutes fit in Groq's 25 MB limit). Paste the official lyrics into *Reference lyrics* for the most accurate text: the wording comes from the reference and the timing from the audio.

Two more AI helpers appear with the same server:

- **✨ AI xử lý** (next to *Syntax*, needs `DEEPSEEK_API_KEY`) rewrites the lyrics box into clean screen lines: restores spaces and Vietnamese diacritics, splits long text by meaning, and adds the app syntax (`/`, `*emphasis*`, `!`, blank lines, `# section`). LRC timestamps are kept line by line. *Undo* restores the previous text.
- **AI chọn hiệu ứng (Jev)** (needs `TYPESAFE_API_KEY`) asks TypeSafe's Jev model, per line, which layout / entrance / exit matches the line's imagery (rain, breaking, circling, counting…), which word to emphasise and whether it is a climax. The browser lists the options the planner could use (`J.aiCandidates`); the planner then follows the model's distribution on the first cut of a line with probability 0.85 × (1 − p(none)), less on later cuts, and otherwise keeps its seeded random pick. Results are stored per line text in the project, so edited lines fall back to random until re-analysed, and switching the panel off restores the exact random plan. After adding or renaming expression packs, run `node tools/export_template_catalog.js` to refresh the English option names in `app/template_catalog.json`.
