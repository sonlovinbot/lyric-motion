"""Local dev server: serves the app and proxies speech-to-text (Groq Whisper) and transcript clean-up (DeepSeek).
usage: cp .env.example .env   (fill in the keys)
       python3 server.py       -> http://localhost:8765/
API keys are read from .env and never reach the browser. Standard library only."""
import json, os, re, sys, time, uuid, urllib.request, urllib.error, urllib.parse
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

ROOT = os.path.dirname(os.path.abspath(__file__))


def load_env(path):
    env = {}
    if os.path.exists(path):
        for raw in open(path, encoding='utf-8'):
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line: continue
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


ENV = {**load_env(os.path.join(ROOT, '.env')), **{k: v for k, v in os.environ.items() if k in (
    'GROQ_API_KEY', 'GROQ_MODEL', 'DEEPSEEK_API_KEY', 'DEEPSEEK_MODEL', 'TYPESAFE_API_KEY', 'TYPESAFE_MODEL', 'TRANSCRIBE_LANGUAGE', 'PORT')}}
cfg = lambda k, d='': ENV.get(k) or d
GROQ_URL = 'https://api.groq.com/openai/v1/audio/transcriptions'
DEEPSEEK_URL = 'https://api.deepseek.com/chat/completions'
TYPESAFE_URL = 'https://api.typesafe.ai/v1/systemone'
MAX_AUDIO = 25 * 1024 * 1024        # Groq free-tier upload limit


class ApiError(Exception):
    def __init__(self, status, message): super().__init__(message); self.status = status


def http_json(url, data, headers, timeout=300):
    # Cloudflare in front of the APIs rejects the default "Python-urllib" agent (error 1010)
    req = urllib.request.Request(url, data=data, headers={'User-Agent': 'LyricMotion-local/1.0', 'Accept': 'application/json', **headers}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: return json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', 'replace')
        try: msg = json.loads(body).get('error', {}).get('message') or body
        except Exception: msg = body
        raise ApiError(e.code, f'{url.split("/")[2]}: {msg[:400]}')
    except urllib.error.URLError as e:
        raise ApiError(502, f'{url.split("/")[2]}: {e.reason}')


# ---------------- Groq Whisper ----------------
def transcribe(audio, filename, language, prompt):
    key = cfg('GROQ_API_KEY')
    if not key: raise ApiError(400, 'GROQ_API_KEY chưa được đặt trong .env')
    if len(audio) > MAX_AUDIO: raise ApiError(413, 'File audio quá 25MB')
    fields = [('model', cfg('GROQ_MODEL', 'whisper-large-v3')), ('response_format', 'verbose_json'),
              ('temperature', '0'), ('timestamp_granularities[]', 'word'), ('timestamp_granularities[]', 'segment')]
    if language: fields.append(('language', language))
    if prompt: fields.append(('prompt', prompt[:800]))
    b = uuid.uuid4().hex
    parts = [f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in fields]
    parts.append(f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: audio/wav\r\n\r\n'.encode() + audio + b'\r\n')
    parts.append(f'--{b}--\r\n'.encode())
    res = http_json(GROQ_URL, b''.join(parts), {'Authorization': f'Bearer {key}', 'Content-Type': f'multipart/form-data; boundary={b}'})
    words = [{'w': str(w.get('word', '')).strip(), 's': round(float(w.get('start', 0)), 3), 'e': round(float(w.get('end', 0)), 3)}
             for w in res.get('words') or [] if str(w.get('word', '')).strip()]
    segs = [{'s': round(float(s.get('start', 0)), 3), 'e': round(float(s.get('end', 0)), 3), 't': str(s.get('text', '')).strip(),
             'ns': float(s.get('no_speech_prob', 0) or 0)} for s in res.get('segments') or []]
    return {'language': res.get('language'), 'duration': res.get('duration'), 'text': res.get('text', ''), 'words': words, 'segments': segs}


# ---------------- lines ----------------
SYNTAX = re.compile(r'[\[\]|#]')
clean = lambda t: re.sub(r'\s+', ' ', SYNTAX.sub('', str(t))).strip()


def raw_lines(tr):
    """Whisper segments -> lines; long segments are split at the widest pause between words."""
    words, out = tr['words'], []
    for sg in tr['segments']:
        if sg['ns'] > 0.6 or not sg['t']: continue
        inside = [w for w in words if sg['s'] - 0.05 <= w['s'] < sg['e'] + 0.05]
        groups = [inside] if inside else []
        while any(len(g) > 9 for g in groups):
            g = max(groups, key=len); i = groups.index(g)
            # split after punctuation first, then at the longest pause, preferring balanced halves
            score = lambda k: (1.0 if re.search(r'[,.;:!?…]$', g[k - 1]['w']) else 0) + (g[k]['s'] - g[k - 1]['e']) - 0.03 * abs(k - len(g) / 2)
            cut = max(range(3, len(g) - 2), key=score)
            groups[i:i + 1] = [g[:cut], g[cut:]]
        if groups: out += [{'start': g[0]['s'], 'text': clean(' '.join(w['w'] for w in g))} for g in groups]
        else: out.append({'start': sg['s'], 'text': clean(sg['t'])})
    return [l for l in out if l['text']]


PROMPT = """You clean up an automatic speech-to-text transcript so it can be shown as on-screen text in a {kind}, line by line.
Language: {lang}.

INPUT: numbered words as "index|start_seconds|word".{ref_note}

OUTPUT: JSON only, shaped {{"lines":[{{"w":<index of the FIRST input word of this line>,"text":"<corrected line>"}}]}}

Rules:
- Lines cover the words in order. "w" must strictly increase. A line spans from its "w" up to the next line's "w" - 1.
- Fix spelling, missing or wrong diacritics / tone marks, wrong homophones and punctuation. Keep the speaker's wording; do not paraphrase or translate.
- Each line is one natural phrase for the screen: about 3-9 words ({unit}). Break at pauses and at phrase boundaries.
- Leave out Whisper hallucinations (e.g. "subscribe", "thanks for watching", "Ghiền Mì Gõ", channel names, repeated filler over silence): give them no line; their words may be skipped.
- Styling marks, use sparingly: wrap ONE key word in *asterisks* in at most one line of four; end a line with "!" only at a real climax (max 3 in total); put " / " inside a longer line to split it into two on-screen beats.
- Never use the characters [ ] | # in "text".
{ref_rules}"""


def deepseek_json(system, user):
    key = cfg('DEEPSEEK_API_KEY')
    if not key: raise ApiError(400, 'DEEPSEEK_API_KEY chưa được đặt trong .env')
    body = json.dumps({'model': cfg('DEEPSEEK_MODEL', 'deepseek-chat'), 'temperature': 0.2, 'max_tokens': 8000,
                       'response_format': {'type': 'json_object'},
                       'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]}).encode()
    res = http_json(DEEPSEEK_URL, body, {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'})
    try: return json.loads(res['choices'][0]['message']['content'])
    except Exception: raise ApiError(502, 'DeepSeek trả về JSON không hợp lệ')


def llm_lines(tr, kind, reference):
    if not cfg('DEEPSEEK_API_KEY'): raise ApiError(400, 'DEEPSEEK_API_KEY chưa được đặt trong .env')
    words = tr['words']
    if not words: return raw_lines(tr)
    lang = tr.get('language') or 'auto'
    ref = (reference or '').strip()
    out, CH = [], 700
    for c0 in range(0, len(words), CH):                     # long inputs go in chunks; indices stay global
        chunk = list(enumerate(words))[c0:c0 + CH]
        system = PROMPT.format(
            kind='song lyric video' if kind == 'song' else 'talking-head video with kinetic captions', lang=lang,
            unit='for Vietnamese, one word = one syllable' if str(lang).lower().startswith('vi') else 'words',
            ref_note='\nREFERENCE: the official text follows the words. Use its exact wording and spelling, aligned to the words by sound.' if ref else '',
            ref_rules='- The reference is authoritative for wording; the input words are authoritative for timing.' if ref else '')
        user = '\n'.join(f'{i}|{w["s"]:.2f}|{w["w"]}' for i, w in chunk) + (f'\n\nREFERENCE:\n{ref[:12000]}' if ref else '')
        lines = deepseek_json(system, user).get('lines')
        if not isinstance(lines, list): raise ApiError(502, 'DeepSeek trả về JSON không hợp lệ')
        last = out[-1]['w'] if out else -1
        lo, hi = chunk[0][0], chunk[-1][0]
        for l in lines:                                      # timing comes from Whisper only: validate every index
            try: w = int(l.get('w'))
            except Exception: continue
            text = clean(l.get('text', ''))
            if text and lo <= w <= hi and w > last:
                out.append({'w': w, 'text': text}); last = w
    if not out: raise ApiError(502, 'DeepSeek không trả về dòng hợp lệ')
    return [{'start': words[l['w']]['s'], 'text': l['text']} for l in out]


# ---------------- AI formatting of typed / pasted text ----------------
FORMAT_PROMPT = """You prepare raw text for an app that turns each line into an animated on-screen text scene ({kind}).
The input may be messy: one long paragraph, missing spaces between words, missing punctuation, Vietnamese typed without
tone marks, random symbols or emoji. Read it for meaning and context first, then return clean text in the app's syntax.

App syntax (one line = one on-screen phrase):
- Each line is one phrase shown together. An empty line inserts a short pause (use it between verses / paragraphs).
- "a/b" inside a line: manual cut, the two parts become separate beats of the same line.
- *word*: emphasis (bigger, stronger effect). Wrap single words or very short phrases only.
- A trailing "!" adds a flash and shake.
- "text|note": small annotation text (translation, romanisation). Only when the input clearly contains such a note.
- A line starting with "#" is a comment and is not shown: use it for section labels such as "# Điệp khúc".

Rules:
- Keep the author's words and their order. Do not paraphrase, summarise, translate or invent content.
- Restore missing spaces between words, missing Vietnamese tone marks / diacritics and obvious typos, judged from context.
- Split into short screen lines: about 3-8 words (for Vietnamese, 1 word = 1 syllable), breaking at natural phrase boundaries,
  never inside a compound word or a name. A line may use "/" once to split a slightly longer phrase into two beats.
- Punctuation: keep commas / question marks where they help reading; drop trailing periods. Remove emoji, hashtags, decorative
  symbols and characters outside normal text ([ ] | are reserved: never output them).
- Emphasis: at most one *word* in roughly one line of four, on the most meaningful word. Trailing "!" only for a real
  climax or exclamation, at most 3 in total.
- {kind_rules}
Return JSON only: {{"lines": ["line 1", "line 2", "", "# Section", ...]}} — empty strings are pauses."""
FORMAT_KIND = {
    'song': 'Lyrics: group lines into verses / chorus with an empty line between sections; add "# ..." section labels only if the structure is clear.',
    'talk': 'Speech / caption text: one idea per line, an empty line between paragraphs; no section labels.',
}
LRC_TAG = re.compile(r'^((?:\[\d+:\d+(?:[.:]\d+)?\])+)(.*)$')


def format_text(text, kind):
    text = str(text or '').replace('\r', '').strip()
    if not text: raise ApiError(400, 'Chưa có nội dung')
    if len(text) > 15000: raise ApiError(413, 'Nội dung quá dài (tối đa khoảng 15.000 ký tự)')
    kind = kind if kind in FORMAT_KIND else 'song'
    system = FORMAT_PROMPT.format(kind='song lyric video' if kind == 'song' else 'talking-head caption video', kind_rules=FORMAT_KIND[kind])
    src = text.split('\n')
    tags = [LRC_TAG.match(l.strip()) for l in src]
    if any(tags):
        # timed lyrics: keep every line and its timestamp, only clean the text inside each line
        timed = [(m.group(1), m.group(2).strip()) if m else ('', l.strip()) for l, m in zip(src, tags)]
        user = ('TIMED MODE: the input lines are numbered and carry timestamps elsewhere. Return EXACTLY one output line per input line, '
                'in the same order ("lines" has the same length). Do not merge, split across lines or add empty lines; "/" inside a line is allowed.\n\n'
                + '\n'.join(f'{i}: {t}' for i, (_, t) in enumerate(timed)))
        out = deepseek_json(system, user).get('lines')
        if not isinstance(out, list) or len(out) != len(timed): raise ApiError(502, 'AI trả về sai số dòng, thử lại hoặc bỏ mốc thời gian')
        out = [re.sub(r'^\d+:\s*', '', clean_line(o)) for o in out]
        return '\n'.join(tag + (o or t) for (tag, t), o in zip(timed, out))
    out = deepseek_json(system, text).get('lines')
    if not isinstance(out, list): raise ApiError(502, 'DeepSeek trả về JSON không hợp lệ')
    lines = [clean_line(o) for o in out]
    while lines and not lines[-1]: lines.pop()
    result = re.sub(r'\n{3,}', '\n\n', '\n'.join(lines)).strip()
    if not result: raise ApiError(502, 'AI không trả về nội dung')
    return result


def clean_line(line):
    """keep the app syntax valid whatever the model returned"""
    line = re.sub(r'\s+', ' ', str(line or '')).strip()
    if line.startswith('#'): return '# ' + re.sub(r'[\[\]|]', '', line.lstrip('#').strip())
    line = re.sub(r'[\[\]]', '', line)
    if line.count('|') > 1: line = line.replace('|', ' ')
    if line.count('*') % 2: line = line.replace('*', '')            # unbalanced emphasis would show literal stars
    line = re.sub(r'/{2,}', '/', line).strip(' /')
    return line


# ---------------- AI direction: TypeSafe Jev picks templates that match each line ----------------
# Code owns the workflow: the browser lists what the planner could use for every line (J.aiCandidates), Jev only
# answers narrow typed questions over those options, and the planner mixes the returned distributions into its
# seeded random picks. Option descriptions are the English template names (app/template_catalog.json).
CATALOG_PATH = os.path.join(ROOT, 'app', 'template_catalog.json')
NONE = 'No option has a visual idea that clearly matches the words or imagery of the line'
DIRECT_Q = {
    'layout': 'Which composition has a visual idea that literally or metaphorically matches the words or imagery of `lines[{i}]` '
              '(for example rain, falling, circling, breaking, darkness, counting)? Choose none if no option clearly matches.',
    'enter': 'Which entrance animation has a motion that literally or metaphorically matches the words or imagery of `lines[{i}]`? '
             'Choose none if no option clearly matches.',
    'exit': 'Which exit animation has a motion that literally or metaphorically matches the words or imagery of `lines[{i}]`? '
            'Choose none if no option clearly matches.',
}


def typesafe(state, questions):
    key = cfg('TYPESAFE_API_KEY')
    if not key: raise ApiError(400, 'TYPESAFE_API_KEY chưa được đặt trong .env')
    body = json.dumps({'state': state, 'model': cfg('TYPESAFE_MODEL', 'jev-latest'), 'questions': questions}).encode()
    for attempt in range(3):                                   # 429 / 529: back off and retry (docs: Handling rate limits)
        try: return http_json(TYPESAFE_URL, body, {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}, timeout=120)
        except ApiError as e:
            if e.status not in (429, 529) or attempt == 2: raise
            time.sleep(1.5 * 2 ** attempt)


def direct(req):
    lines = req.get('lines') or []
    if not lines: raise ApiError(400, 'Chưa có lời')
    if len(lines) > 200: raise ApiError(413, 'Quá nhiều dòng (tối đa 200)')
    cat = json.load(open(CATALOG_PATH, encoding='utf-8'))
    state = {'lines': [str(l.get('text', '')) for l in lines]}
    if req.get('language'): state['language'] = req['language']
    qs = {}
    for i, l in enumerate(lines):
        for g in ('layout', 'enter', 'exit'):
            opts = [k for k in l.get(g) or [] if k in cat[g]][:254]
            if opts:
                crit = {k: cat[g][k]['name'] for k in opts}
                crit['none'] = NONE
                qs[f'{g}_{i}'] = {'type': 'choice', 'instructions': DIRECT_Q[g].format(i=i), 'criteria': crit}
        words = [str(w) for w in l.get('words') or [] if str(w).strip() and str(w) != 'none'][:30]
        if words and not l.get('userEmph'):
            qs[f'emph_{i}'] = {'type': 'choice', 'criteria': {**{w: None for w in words}, 'none': 'No word stands out'},
                               'instructions': f'Which word or two-word phrase of `lines[{i}]` carries the most meaning or feeling and should be emphasised on screen?'}
        qs[f'climax_{i}'] = {'type': 'noul', 'instructions': f'Is `lines[{i}]` an emotional peak or exclamation — a line that should hit hardest visually?'}
    # ~5 lines per request keeps each call far below the 64k-token budget; requests run in parallel
    groups = [list(range(a, min(a + 5, len(lines)))) for a in range(0, len(lines), 5)]
    from concurrent.futures import ThreadPoolExecutor
    def run(idx):
        sub = {k: v for k, v in qs.items() if int(k.rsplit('_', 1)[1]) in idx}
        return typesafe(state, sub)
    with ThreadPoolExecutor(min(8, len(groups))) as ex: results = list(ex.map(run, groups))
    answers, usage, model = {}, 0, None
    for r in results:
        answers.update(r.get('answers') or {}); usage += (r.get('usage') or {}).get('input_tokens', 0); model = r.get('model') or model
    out = []
    for i in range(len(lines)):
        a = lambda k: answers.get(f'{k}_{i}') or {}
        e = a('emph')
        out.append({g: a(g).get('probabilities') for g in ('layout', 'enter', 'exit')} |
                   {'emph': e.get('choice') if e.get('choice') not in (None, 'none') else None,
                    'emphP': (e.get('probabilities') or {}).get(e.get('choice'), 0), 'climax': a('climax').get('noul')})
    return {'model': model, 'inputTokens': usage, 'lines': out}


# ---------------- HTTP ----------------
class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=ROOT, **k)

    def log_message(self, fmt, *args):
        if '/api/' in (self.path or ''): sys.stderr.write('%s\n' % (fmt % args))

    def send_json(self, status, obj):
        data = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers(); self.wfile.write(data)

    def do_GET(self):
        path = self.path.split('?')[0]
        if any(p.startswith('.') for p in path.split('/') if p):          # never serve .env / .git
            return self.send_error(404)
        if path == '/api/status':
            return self.send_json(200, {'groq': bool(cfg('GROQ_API_KEY')), 'deepseek': bool(cfg('DEEPSEEK_API_KEY')), 'typesafe': bool(cfg('TYPESAFE_API_KEY')),
                                        'language': cfg('TRANSCRIBE_LANGUAGE'), 'groqModel': cfg('GROQ_MODEL', 'whisper-large-v3'),
                                        'deepseekModel': cfg('DEEPSEEK_MODEL', 'deepseek-chat')})
        return super().do_GET()

    def do_POST(self):
        path = self.path.split('?')[0]
        n = int(self.headers.get('Content-Length') or 0)
        if n > MAX_AUDIO + 1024 * 1024: return self.send_json(413, {'error': 'Request quá lớn'})
        body = self.rfile.read(n)
        try:
            if path == '/api/transcribe':
                h = self.headers
                un = lambda k: urllib.parse.unquote(h.get(k) or '')
                return self.send_json(200, transcribe(body, un('X-Filename') or 'audio.wav', un('X-Language'), un('X-Prompt')))
            if path == '/api/lines':
                req = json.loads(body.decode('utf-8'))
                tr = req['transcript']
                lines = llm_lines(tr, req.get('kind', 'song'), req.get('reference')) if req.get('llm') else raw_lines(tr)
                return self.send_json(200, {'lines': lines})
            if path == '/api/direct':
                return self.send_json(200, direct(json.loads(body.decode('utf-8'))))
            if path == '/api/format':
                req = json.loads(body.decode('utf-8'))
                return self.send_json(200, {'text': format_text(req.get('text'), req.get('kind'))})
            return self.send_json(404, {'error': 'not found'})
        except ApiError as e:
            return self.send_json(e.status, {'error': str(e)})
        except Exception as e:
            return self.send_json(500, {'error': f'{type(e).__name__}: {e}'})


if __name__ == '__main__':
    port = int(cfg('PORT', '8765'))
    print(f'Lyric Motion local: http://localhost:{port}/   (Groq key: {"yes" if cfg("GROQ_API_KEY") else "NO"}, DeepSeek key: {"yes" if cfg("DEEPSEEK_API_KEY") else "NO"})')
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()
