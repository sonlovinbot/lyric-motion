"""Build the Japanese, English and Vietnamese single-file browser editions from src/, app/ and vendor/.
usage: python3 build.py            -> index.html, en/index.html and vi/index.html (GitHub Pages)
       python3 build.py --dev      -> also dev/www/jizura.js + dev/www/test.html for the test tools"""
import glob, os, sys
from app.english import localize_body, localize_js, replace_copy
from app import vietnamese
ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
read = lambda p: open(p, encoding='utf-8').read()
sources = sorted(glob.glob('src/*.js'))
js = '\n'.join(read(f) for f in sources)
mux = '/*! mp4-muxer v5.2.2 | MIT License | (c) 2023 Vanilagy | see THIRD_PARTY_NOTICES.md */\n' + read('vendor/mp4-muxer.min.js')
LANGS = {   # lang: (folder, nav label, title, description, nav aria-label)
    'ja': ('', '日本語', 'Lyric Motion', '歌詞を入れると文字PV（リリックモーション）を自動で組み立てて MP4 に書き出すブラウザアプリ', '言語'),
    'en': ('en/', 'English', 'Lyric Motion — Kinetic Lyric Video Maker', 'Turn lyrics into animated lyric videos in your browser and export MP4.', 'Language'),
    'vi': ('vi/', 'Tiếng Việt', 'Lyric Motion — Tạo video chữ chuyển động', 'Nhập lời bài hát, tự động dựng video chữ chuyển động và xuất MP4 ngay trên trình duyệt.', 'Ngôn ngữ'),
}
def vi_js(source, filename):
    if filename.endswith('12_ui.js'): return replace_copy(source, vietnamese.UI)
    if filename.endswith('11_export.js'): return replace_copy(source, vietnamese.EXPORT)
    return source
def build(lang):
    english, viet = lang == 'en', lang == 'vi'
    folder, _, title, description, nav_label = LANGS[lang]
    canonical = 'https://sonlovinbot.github.io/lyric-motion/' + folder
    up = '../' if folder else ''
    links = ''.join(f'<span aria-current="page">{name}</span>' if code == lang else f'<a href="{up}{dir_}index.html" lang="{code}">{name}</a>'
                    for code, (dir_, name, *_rest) in LANGS.items())
    language_nav = f'<nav class="lang-switch" aria-label="{nav_label}">{links}</nav>'
    body = read('app/body.html').replace('    <div class="acts">', '    ' + language_nav + '\n    <div class="acts">', 1)
    if english: body = localize_body(body)
    if viet: body = replace_copy(body, vietnamese.BODY)
    script = '\n'.join(localize_js(read(f), f) for f in sources) if english else '\n'.join(vi_js(read(f), f) for f in sources) if viet else js
    if english or viet:
        marker = '/* ============================================================\n   JIZURA — editor UI'
        if marker not in script: raise ValueError('Could not find browser UI entry point')
        labels = read('app/english.js') if english else read('app/vietnamese.js').replace('/*VI_LABELS*/null', read('app/vietnamese_labels.json').strip(), 1)
        script = script.replace(marker, labels + '\n' + marker, 1)
    # IBM Plex Sans JP (UI) and Zen Old Mincho (brand) have no Vietnamese glyphs: the Vietnamese edition swaps in IBM Plex Sans / Noto Serif
    vi_head = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=Noto+Serif:wght@500;700&display=swap">\n' if viet else ''
    vi_css = '\n:root { --ui: "IBM Plex Sans", "Noto Sans", system-ui, sans-serif; --brand: "Noto Serif", "Noto Serif JP", serif; }' if viet else ''
    html = f'''<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{title}</title>
<meta name="description" content="{description}">
<link rel="canonical" href="{canonical}">
<link rel="alternate" hreflang="ja" href="https://sonlovinbot.github.io/lyric-motion/">
<link rel="alternate" hreflang="en" href="https://sonlovinbot.github.io/lyric-motion/en/">
<link rel="alternate" hreflang="vi" href="https://sonlovinbot.github.io/lyric-motion/vi/">
<meta property="og:type" content="website">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{canonical}">
<meta name="twitter:card" content="summary">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
{vi_head}<style>
{read('app/style.css')}{vi_css}
</style>
</head>
<body>
{body}
<script>
{mux}
</script>
<script>
{script}
</script>
</body>
</html>
'''
    target = folder + 'index.html'
    os.makedirs(os.path.dirname(target) or '.', exist_ok=True)
    open(target, 'w', encoding='utf-8').write(html)
    print(target, len(html), 'bytes')
build('ja')
build('en')
build('vi')
if '--dev' in sys.argv:
    os.makedirs('dev/www', exist_ok=True)
    open('dev/www/jizura.js', 'w', encoding='utf-8').write(js)
    open('dev/www/test.html', 'w', encoding='utf-8').write(read('dev/test.html'))
    print('dev/www ready: cd dev/www && python3 -m http.server 8765')
