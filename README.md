# Lyric Motion

**Biến lời bài hát và lời nói thành video chữ chuyển động, ngay trên trình duyệt.**

Dán lời hoặc tải lên một bài hát, Lyric Motion tự chia câu, dựng từng cảnh chữ động khớp nhịp và xuất MP4 cho TikTok, Reels, YouTube. Hơn 700 hiệu ứng, 24 phong cách, bấm một nút là ra một phương án mới. Bản này bổ sung giao diện tiếng Việt, hỗ trợ font tiếng Việt đầy đủ và các công cụ AI: nhận dạng lời từ audio, xử lý lời, và chọn hiệu ứng theo nghĩa của từng câu.

**▶ Dùng ngay: <https://sonlovinbot.github.io/lyric-motion/>** (chạy trên trình duyệt, không cần cài đặt)

[English guide](README.en.md) · [日本語](README.ja.md)

> Lyric Motion được phát triển dựa trên mã nguồn mở [JIZURA](https://github.com/852wa/JIZURA) của 852wa (giấy phép MIT).

---

## Tính năng mới so với JIZURA

### 1. Giao diện tiếng Việt, mở mặc định
- Toàn bộ giao diện, 707 tên hiệu ứng, 24 phong cách và lời mẫu đã được dịch sang tiếng Việt.
- Bản tiếng Việt là trang chính (`index.html`). Bản tiếng Nhật ở `ja/`, tiếng Anh ở `en/`, chuyển qua lại bằng nút ngôn ngữ trên thanh tiêu đề.

### 2. Hiển thị tiếng Việt chuẩn dấu
Bản gốc dùng font tiếng Nhật. **12/23 font không có bộ ký tự tiếng Việt**, nên chữ bị mất dấu thanh ("ẤY" hiện thành "ÂY", "ỄNH" thành "ÊNH") hoặc lẫn hai kiểu chữ trong một từ.
- Khi lời có tiếng Việt, app tự dùng font thay thế cùng phong cách, tất cả đều đã được kiểm tra là có bộ tiếng Việt trên Google Fonts: Be Vietnam Pro, Playfair Display, Noto Serif Display, Baloo 2, VT323, Sriracha, Paytone One, Bungee Shade, Nunito, Patrick Hand, Lora, IBM Plex Sans.
- Nhận đúng chữ Latin có dấu ("ở", "ữ"…): không còn ghép nhầm "ở ơi" thành "ởơi", không xoay sai khi viết dọc.
- Chuẩn hoá Unicode (NFC) để dấu không bị tách rời khi dán chữ từ macOS.
- Nới vùng vẽ để dấu chồng (Ấ, Ể, Ỗ) không bị cắt khi có hiệu ứng blur, glow hay vỡ chữ.

### 3. Lời tự động từ audio (Groq + DeepSeek)
- Tải lên bài hát hoặc file ghi âm: **Groq Whisper** nhận dạng lời kèm mốc thời gian của từng từ, sau đó điền lời dạng LRC để chữ chạy khớp bài hát.
- Tuỳ chọn **DeepSeek** sửa chính tả, dấu, ngắt câu theo ý. Thời gian luôn lấy từ Whisper nên không bị lệch.
- Có ô *Lời chuẩn*: dán lời gốc vào thì chữ lấy từ lời gốc, thời gian lấy từ audio.

### 4. ✨ AI xử lý lời (DeepSeek)
Nút cạnh *Cú pháp*. AI đọc cả đoạn để hiểu ngữ cảnh, kể cả khi nội dung dán vào là một khối dài, viết liền không dấu cách, gõ không dấu hay lẫn emoji:
- thêm dấu cách, khôi phục dấu tiếng Việt, sửa lỗi chính tả rõ ràng;
- tách thành các dòng ngắn theo nghĩa, chia khổ bằng dòng trống;
- tự thêm cú pháp hiệu ứng: `/` cắt cảnh, `*nhấn mạnh*`, `!` ở cao trào, `# Điệp khúc`;
- giữ nguyên mốc thời gian nếu lời đã có LRC; có nút **Hoàn tác**.

### 5. AI chọn hiệu ứng theo nội dung (TypeSafe Jev)
Bản gốc chọn hiệu ứng ngẫu nhiên theo trọng số, không hiểu nghĩa câu. Khung **AI chọn hiệu ứng** hỏi model [Jev](https://docs.typesafe.ai) cho từng dòng:
- bố cục, hiệu ứng vào và ra nào khớp *hình ảnh* trong câu, ví dụ "mưa" ra *mưa chữ*, "xoay vòng" ra *quỹ đạo* + *xoay*, "vỡ tan" ra *vỡ như kính*, "thứ nhất" ra *đánh số*;
- từ nào nên nhấn mạnh, câu nào là cao trào.

Jev chỉ chọn trong danh sách hiệu ứng hợp lệ do code đưa ra và trả về xác suất. Planner làm theo gợi ý ở cảnh đầu của mỗi dòng với xác suất 85% × (1 − p(không khớp)), các cảnh sau vẫn ngẫu nhiên nên video không đơn điệu và nút *Tạo ngẫu nhiên* vẫn ra phương án mới. Tắt công tắc thì video ra đúng như bản ngẫu nhiên cũ. Phân tích 6 dòng mất khoảng 1,5 giây.

### 6. Server local giữ API key an toàn
`server.py` chỉ dùng thư viện chuẩn của Python, phục vụ app và làm trung gian gọi Groq, DeepSeek, TypeSafe. Key nằm trong `.env` (không commit) và không bao giờ gửi xuống trình duyệt. Server chỉ nghe trên `127.0.0.1` và chặn truy cập `.env`, `.git`.

---

## Chạy trên máy

Yêu cầu: Python 3.9+ và Chrome hoặc Edge (để xuất MP4 bằng WebCodecs).

```sh
git clone https://github.com/sonlovinbot/lyric-motion.git
cd lyric-motion
cp .env.example .env      # điền các key muốn dùng
python3 server.py         # mở http://localhost:8765/
```

| Biến trong `.env` | Dùng cho | Bắt buộc? |
|---|---|---|
| `GROQ_API_KEY` | Lời tự động từ audio | Chỉ khi dùng tính năng này |
| `DEEPSEEK_API_KEY` | Sửa lời sau khi nhận dạng, nút ✨ AI xử lý | Chỉ khi dùng tính năng này |
| `TYPESAFE_API_KEY` | AI chọn hiệu ứng (Jev) | Chỉ khi dùng tính năng này |
| `TRANSCRIBE_LANGUAGE` | Ngôn ngữ nhận dạng mặc định (`vi`) | Không |

Không có key nào thì app vẫn chạy đầy đủ các tính năng dựng và xuất video. Các khung AI chỉ hiện khi chạy qua `server.py`: bản trên GitHub Pages và file `index.html` mở trực tiếp dùng được mọi tính năng khác, trừ AI (vì cần server giữ API key).

## Cú pháp lời

| Cú pháp | Tác dụng |
|---|---|
| Mỗi dòng một câu | Mỗi dòng là một cụm chữ trên màn hình. Dòng trống thêm một khoảng nghỉ ngắn |
| `Anh vẫn nhớ/màu bình minh` | `/` đánh dấu điểm cắt cảnh |
| `*trong suốt*` | Nhấn mạnh: chữ to hơn, hiệu ứng mạnh hơn |
| `Đừng đi!` | `!` cuối dòng thêm nháy sáng và rung |
| `lời\|phiên âm` | Chữ nhỏ trong bố cục chú thích |
| `[01:23.45]Lời bài hát` | Dùng mốc thời gian LRC |
| `# Điệp khúc` | Dòng ghi chú, không hiển thị |

## Xuất video
- **MP4** có nhạc, 720p đến 4K, 24/30/60 fps, tỉ lệ 16:9, 9:16, 4:3, 3:4, 1:1, 4:5, 21:9.
- **PNG sequence** và **PNG trong suốt**; nền **xanh lá / đen** để ghép vào CapCut, Premiere.
- **Xuất cho After Effects** (JSON) để chỉnh tiếp trong panel AE.

## Build

```sh
python3 build.py                           # index.html (VI), ja/index.html, en/index.html
node tools/export_template_catalog.js      # sau khi thêm/đổi tên hiệu ứng: cập nhật tên cho Jev
```

| Thư mục / file | Nội dung |
|---|---|
| `src/` | Engine: phân tích lời, planner, render, xuất video, các gói hiệu ứng (`11p_*.js`) |
| `src/13_ai.js` | Giao diện các tính năng AI |
| `app/` | Giao diện, bản dịch (`vietnamese.py`, `vietnamese_labels.json`, `english.*`) |
| `server.py` | Server local và proxy API |
| `ae/`, `cep/` | Panel After Effects (từ JIZURA, chưa cập nhật font tiếng Việt) |
| `docs/EXPRESSION_PACKS.md` | Hướng dẫn viết gói hiệu ứng mới |

## Sắp tới
- Video talking head: tải video 1–2 phút lên, tự cắt khoảng lặng và câu nói lại (A-roll), chèn cảnh chữ hiệu ứng (B-roll) vào các ý chính, ghép bằng ffmpeg.

## Giấy phép
- Mã nguồn: MIT, giữ nguyên bản quyền gốc của JIZURA (© 2026 hakoniwa). Xem [LICENSE](LICENSE) và [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
- Video và hình ảnh bạn tạo ra thuộc về bạn. Quyền đối với lời bài hát và bản nhạc thuộc về chủ sở hữu tương ứng.
- Lời và nhạc được xử lý trong trình duyệt. Chỉ khi bạn bấm các nút AI thì nội dung mới được gửi tới Groq, DeepSeek hoặc TypeSafe qua server local của bạn.
