/* ============================================================
   Lyric Motion — AI helpers (local server only)
   1. auto lyrics: audio -> 16 kHz mono WAV -> server.py /api/transcribe (Groq Whisper)
                   -> /api/lines (raw segments, or DeepSeek clean-up) -> LRC in the lyrics box
   2. AI format:   lyrics box text -> /api/format (DeepSeek: spaces, diacritics, line breaks, app syntax) -> lyrics box
   3. AI direct:   J.aiCandidates -> /api/direct (TypeSafe Jev: per-line template / emphasis / climax judgments)
                   -> project.ai, which the planner mixes into its seeded random picks (see 08_planner.js)
   Appears only when the page is served by server.py (GET /api/status answers);
   on GitHub Pages / file:// nothing is added.
   ============================================================ */
(() => {
'use strict';
if (typeof document === 'undefined' || typeof document.getElementById !== 'function' || !document.getElementById('app')) return;   // Node tools (AE data export) load src/ with a stub document
if (typeof location === 'undefined' || location.protocol === 'file:') return;
const $ = id => document.getElementById(id);

/* AudioBuffer -> 16 kHz mono 16-bit WAV (what Whisper uses anyway; ~1.9 MB per minute) */
async function toWav16k(buffer) {
  const SR = 16000;
  const oc = new OfflineAudioContext(1, Math.ceil(buffer.duration * SR), SR);
  const src = oc.createBufferSource(); src.buffer = buffer; src.connect(oc.destination); src.start();
  const pcm = (await oc.startRendering()).getChannelData(0);
  const out = new DataView(new ArrayBuffer(44 + pcm.length * 2));
  const str = (o, s) => { for (let i = 0; i < s.length; i++) out.setUint8(o + i, s.charCodeAt(i)); };
  str(0, 'RIFF'); out.setUint32(4, 36 + pcm.length * 2, true); str(8, 'WAVE'); str(12, 'fmt ');
  out.setUint32(16, 16, true); out.setUint16(20, 1, true); out.setUint16(22, 1, true);
  out.setUint32(24, SR, true); out.setUint32(28, SR * 2, true); out.setUint16(32, 2, true); out.setUint16(34, 16, true);
  str(36, 'data'); out.setUint32(40, pcm.length * 2, true);
  for (let i = 0; i < pcm.length; i++) out.setInt16(44 + i * 2, Math.max(-1, Math.min(1, pcm[i])) * 0x7fff, true);
  return new Blob([out.buffer], { type: 'audio/wav' });
}

async function api(path, body, headers) {
  const r = await fetch(path, { method: 'POST', body, headers });
  let j = null; try { j = await r.json(); } catch (e) {}
  if (!r.ok) throw new Error((j && j.error) || `HTTP ${r.status}`);
  return j;
}

const lrcTime = t => { t = Math.max(0, t); const m = Math.floor(t / 60), s = t - m * 60; return `[${String(m).padStart(2, '0')}:${s.toFixed(2).padStart(5, '0')}]`; };

function mount(status) {
  const anchor = $('audioName') && $('audioName').closest('.sec');
  if (!anchor) return;
  const sec = document.createElement('div');
  sec.className = 'sec';
  sec.innerHTML = `
    <div class="sec-h"><h2>Lời tự động (Groq)</h2></div>
    <div class="muted" style="font-size:12px">Nhận dạng giọng hát/nói trong audio rồi điền lời có mốc thời gian (LRC) vào ô lời.</div>
    <div class="fields">
      <label class="field">Loại<select id="trKind"><option value="song">Bài hát</option><option value="talk">Nói chuyện</option></select></label>
      <label class="field">Ngôn ngữ<input id="trLang" type="text" maxlength="5" placeholder="tự nhận"></label>
    </div>
    <label class="row" style="gap:6px"><input id="trLlm" type="checkbox"> Sửa lỗi bằng DeepSeek</label>
    <details><summary class="muted" style="cursor:pointer;font-size:12px">Lời chuẩn (tuỳ chọn, giúp chính xác hơn)</summary>
      <textarea id="trRef" rows="5" spellcheck="false" placeholder="Dán lời gốc vào đây: chữ lấy từ lời gốc, thời gian lấy từ audio"></textarea>
    </details>
    <div class="row"><button id="trGo" class="accent">Tạo lời từ audio</button><input id="trFile" type="file" accept="audio/*,video/*" hidden></div>
    <div id="trMsg" class="muted" style="font-size:12px"></div>`;
  anchor.after(sec);
  $('trLang').value = status.language || '';
  $('trLlm').checked = status.deepseek; $('trLlm').disabled = !status.deepseek;
  if (!status.deepseek) $('trLlm').parentElement.title = 'Chưa có DEEPSEEK_API_KEY trong .env';
  if (!status.groq) { $('trGo').disabled = true; $('trMsg').textContent = 'Chưa có GROQ_API_KEY trong .env. Điền key rồi khởi động lại server.py.'; }
  $('trGo').addEventListener('click', () => { if (J.ui.audio) run(); else $('trFile').click(); });
  $('trFile').addEventListener('change', async e => {
    const f = e.target.files && e.target.files[0]; e.target.value = '';
    if (f && await J.uiApi.loadAudioFile(f)) run();
  });
}

let busy = false;
async function run() {
  if (busy) return;
  const msg = t => { $('trMsg').textContent = t; };
  const audio = J.ui.audio;
  if (!audio || !audio.buffer) { msg('Hãy tải audio trước.'); return; }
  busy = true; $('trGo').disabled = true;
  const t0 = performance.now();
  try {
    msg('Đang chuẩn bị audio…');
    const wav = await toWav16k(audio.buffer);
    if (wav.size > 25 * 1024 * 1024) throw new Error('Audio dài quá (giới hạn khoảng 13 phút).');
    const ref = $('trRef').value.trim();
    msg(`Đang nhận dạng bằng Groq (${(wav.size / 1048576).toFixed(1)} MB)…`);
    const tr = await api('/api/transcribe', wav, {
      'Content-Type': 'audio/wav', 'X-Filename': encodeURIComponent((audio.name || 'audio').replace(/\.[^.]+$/, '') + '.wav'),
      'X-Language': encodeURIComponent($('trLang').value.trim()), 'X-Prompt': encodeURIComponent(ref.slice(0, 800)),
    });
    const llm = $('trLlm').checked;
    msg(llm ? `Đã nhận ${tr.words.length} từ. DeepSeek đang sửa lời…` : `Đã nhận ${tr.words.length} từ. Đang tách dòng…`);
    const { lines } = await api('/api/lines', JSON.stringify({ transcript: tr, llm, kind: $('trKind').value, reference: ref }), { 'Content-Type': 'application/json' });
    if (!lines.length) throw new Error('Không nhận ra lời nào trong audio.');
    const box = $('lyrics');
    box.value = lines.map(l => lrcTime(l.start) + l.text.normalize('NFC')).join('\n');
    J.ui.project.timing.lineTimes = {};
    box.dispatchEvent(new Event('input'));
    msg(`Xong: ${lines.length} dòng (ngôn ngữ: ${tr.language || '?'}, ${((performance.now() - t0) / 1000).toFixed(1)} giây). Có thể sửa trực tiếp trong ô lời.`);
  } catch (err) {
    msg('Lỗi: ' + err.message);
  } finally { busy = false; $('trGo').disabled = false; }
}

/* ---------- AI format button in the lyrics header ---------- */
function mountFormat(status) {
  const syntaxBtn = $('btnSyntax'), box = $('lyrics');
  if (!syntaxBtn || !box) return;
  const btn = document.createElement('button');
  btn.id = 'btnAiFormat'; btn.className = 'accent small'; btn.textContent = '✨ AI xử lý';
  btn.title = status.deepseek ? 'DeepSeek tách dòng, thêm dấu cách, dấu tiếng Việt và cú pháp hiệu ứng theo ngữ cảnh' : 'Chưa có DEEPSEEK_API_KEY trong .env';
  btn.disabled = !status.deepseek;
  const wrap = document.createElement('div'); wrap.className = 'row'; wrap.style.gap = '6px';
  syntaxBtn.replaceWith(wrap); wrap.append(btn, syntaxBtn);
  const bar = document.createElement('div');
  bar.className = 'row muted'; bar.style.fontSize = '12px'; bar.hidden = true;
  bar.innerHTML = '<span id="aiFmtMsg"></span><button id="aiFmtUndo" class="ghost small" hidden>Hoàn tác</button>';
  box.after(bar);
  let before = null;
  const setText = t => { box.value = t; box.dispatchEvent(new Event('input')); };
  $('aiFmtUndo').addEventListener('click', () => {
    if (before == null) return;
    setText(before); before = null;
    $('aiFmtMsg').textContent = 'Đã khôi phục nội dung cũ.'; $('aiFmtUndo').hidden = true;
  });
  btn.addEventListener('click', async () => {
    const text = box.value.trim();
    bar.hidden = false; $('aiFmtUndo').hidden = true;
    if (!text) { $('aiFmtMsg').textContent = 'Hãy nhập hoặc dán nội dung trước.'; return; }
    btn.disabled = true; $('aiFmtMsg').textContent = 'DeepSeek đang đọc ngữ cảnh và tách dòng…';
    const t0 = performance.now();
    try {
      const kind = $('trKind') ? $('trKind').value : 'song';
      const r = await api('/api/format', JSON.stringify({ text: box.value, kind }), { 'Content-Type': 'application/json' });
      before = box.value;
      setText(r.text.normalize('NFC'));
      const n = r.text.split('\n').filter(l => l.trim() && !l.trim().startsWith('#')).length;
      $('aiFmtMsg').textContent = `Xong: ${n} dòng (${((performance.now() - t0) / 1000).toFixed(1)} giây).`;
      $('aiFmtUndo').hidden = false;
    } catch (err) {
      $('aiFmtMsg').textContent = 'Lỗi: ' + err.message;
    } finally { btn.disabled = !status.deepseek; }
  });
}

/* ---------- AI direction panel (TypeSafe Jev) ---------- */
const EMPH_MIN = 0.5, EMPH_SHARE = 0.4;     // emphasise confident picks only, on at most 40% of the lines
const CLIMAX_MIN = 0.7;                     // flash + shake on the clearest peaks, at most 3 (fewer on short texts)

function mountDirect(status, after) {
  const sec = document.createElement('div');
  sec.className = 'sec';
  sec.innerHTML = `
    <div class="sec-h"><h2>AI chọn hiệu ứng (Jev)</h2></div>
    <div class="muted" style="font-size:12px">Đọc nghĩa từng dòng để ưu tiên bố cục và chuyển động hợp hình ảnh (mưa, vỡ, xoay, đếm…), chọn từ nhấn mạnh và câu cao trào. Vẫn giữ ngẫu nhiên cho những dòng không có hình ảnh rõ.</div>
    <label class="row" style="gap:6px"><input id="aiOn" type="checkbox"> Dùng gợi ý AI khi dựng</label>
    <div class="row"><button id="aiGo" class="accent">Phân tích lời</button></div>
    <div id="aiMsg" class="muted" style="font-size:12px"></div>`;
  after.after(sec);
  const P = () => J.ui.project;
  const msg = t => { $('aiMsg').textContent = t; };
  const refresh = () => {
    const ai = P().ai;
    $('aiOn').checked = !!ai && P().aiOn !== false; $('aiOn').disabled = !ai;
    if (!status.typesafe) { $('aiGo').disabled = true; msg('Chưa có TYPESAFE_API_KEY trong .env.'); return; }
    if (!ai) { msg('Chưa phân tích.'); return; }
    const lines = J.parseLyrics(P().lyrics).lines;
    const live = lines.filter((l, i) => ai.lines[i] && ai.lines[i].text === l.text).length;
    msg(live === lines.length ? `Đang áp dụng cho ${live} dòng.` : `Còn hiệu lực ${live}/${lines.length} dòng (lời đã sửa). Bấm Phân tích lời để cập nhật.`);
  };
  $('aiOn').addEventListener('change', e => { P().aiOn = e.target.checked; J.uiApi.replan(); J.uiApi.flushSave(); refresh(); });
  let timer = 0;
  $('lyrics').addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(refresh, 400); });
  $('aiGo').addEventListener('click', async () => {
    const cands = J.aiCandidates(P());
    if (!cands.length) { msg('Hãy nhập lời trước.'); return; }
    $('aiGo').disabled = true; msg(`Jev đang đọc ${cands.length} dòng…`);
    const t0 = performance.now();
    try {
      const r = await api('/api/direct', JSON.stringify({ lines: cands, language: J.VI ? 'Vietnamese' : undefined }), { 'Content-Type': 'application/json' });
      // code keeps the policy: which emphasis / climax answers are strong enough to act on
      const emphOk = new Set(r.lines.map((a, i) => [i, a]).filter(([i, a]) => a.emph && a.emphP >= EMPH_MIN && !cands[i].userEmph)
        .sort((x, y) => y[1].emphP - x[1].emphP).slice(0, Math.ceil(cands.length * EMPH_SHARE)).map(([i]) => i));
      const nClimax = Math.max(1, Math.min(3, Math.ceil(cands.length / 8)));
      const climaxOk = new Set(r.lines.map((a, i) => [i, a.climax || 0]).filter(([i, p]) => p >= CLIMAX_MIN && !cands[i].userImpact)
        .sort((x, y) => y[1] - x[1]).slice(0, nClimax).map(([i]) => i));
      P().ai = { v: 1, model: r.model, at: Date.now(), lines: r.lines.map((a, i) => ({
        text: cands[i].text, layout: a.layout, enter: a.enter, exit: a.exit,
        emph: emphOk.has(i) ? a.emph : null, impact: climaxOk.has(i),
      })) };
      P().aiOn = true;
      J.uiApi.replan(); J.uiApi.flushSave(); refresh();
      const matched = r.lines.filter(a => a.layout && (a.layout.none || 0) < 0.5).length;
      msg(`Xong (${((performance.now() - t0) / 1000).toFixed(1)} giây, ${r.model}): ${matched}/${cands.length} dòng có bố cục hợp hình ảnh, ${emphOk.size} từ nhấn mạnh, ${climaxOk.size} câu cao trào.`);
    } catch (err) {
      msg('Lỗi: ' + err.message);
    } finally { $('aiGo').disabled = !status.typesafe; }
  });
  refresh();
}

fetch('/api/status').then(r => (r.ok ? r.json() : null)).then(s => {
  if (!s || !('groq' in s)) return;
  mountFormat(s); mount(s);
  const groqSec = $('trGo') && $('trGo').closest('.sec');
  if (groqSec) mountDirect(s, groqSec);
}).catch(() => {});
})();
