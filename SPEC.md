# SPEC — Bot Discord "Khí Tuyệt Lục" (Giai đoạn 2)

> Trạng thái: bản chốt trước khi code (Draft v1.0)
> Vị trí code: `bot code\bot\` — tách hẳn khỏi tracker, mỗi thứ một thư mục.
> Hạ tầng: Render.com **Web Service (free)** + UptimeRobot ping để chống ngủ.

---

## 0. Thay đổi so với giai đoạn 1 (bắt buộc)

Tracker đang POST JSON có trường `screenshot` là **đường dẫn file trên máy bạn**. Bot chạy trên Render thì không thể đọc đường dẫn đó. Vì vậy giai đoạn 2 sửa hai chỗ ở tracker:

1. Khi gửi, đính thêm `screenshot_b64` (nội dung JPEG mã hoá base64) + `screenshot_mime`. File gốc trong `outbox/` vẫn không chứa base64 → không phình đĩa; base64 được tạo đúng lúc gửi.
2. `bot.timeout_s` tăng lên 10 s (Render free ngủ thì lần gọi đầu phải chờ khởi động), và `bot.endpoint` đổi sang `https://<app>.onrender.com/api/deaths`.

Chi phí: ảnh ~150 KB → payload ~200 KB. Không ảnh hưởng ngân sách tài nguyên của tracker.

---

## 1. Mục tiêu

1. Nhận sự kiện chết từ tracker qua 1 endpoint HTTP có xác thực.
2. Gửi thông báo vào **nhiều kênh** Discord đã cấu hình, tối đa 10 kênh.
3. Mỗi kênh có thể **bật/tắt ảnh riêng**, có mức mặc định chung.
4. **Ảnh nằm trên, embed nằm dưới** (ảnh gửi dạng attachment thường, không nhét vào `embed.image`).
5. Embed trang trí theo phong cách **kiếm hiệp / nhập ma**, tiếng Việt + Hán tự, bot tên **Khí Tuyệt Lục**.
6. Cấu hình **bền vững qua các lần deploy Render** (đĩa Render free là ephemeral).
7. Chạy ổn trên Render free: bind `0.0.0.0:$PORT`, có `/health` để UptimeRobot ping.

Ngoài phạm vi: đọc SQLite của tracker (không với tới được từ cloud), biểu đồ/thống kê nâng cao, đa ngôn ngữ.

---

## 2. Kiến trúc

```
   Máy bạn                                    Render (Docker/Python runtime)
┌──────────────────────┐   HTTPS POST      ┌──────────────────────────────────┐
│ pbz_tracker          │  /api/deaths      │ khi-tuyet-luc-bot                     │
│  · phát hiện DEAD    │ ────────────────► │  aiohttp  ──► Notifier           │
│  · outbox + retry    │  X-Tracker-Token  │    /health    │                  │
│  · ảnh JPEG          │  ── JSON + base64 │    /          │                  │
└──────────────────────┘                   │    /api/deaths│                  │
                                           │               ▼                  │
   UptimeRobot ── GET /health (5 phút) ──► │  discord.py ──► #kênh-1, #kênh-2 │
                                           │       ▲                          │
                                           │       └── ConfigStore (pin msg)  │
                                           └──────────────────────────────────┘
```

Một process duy nhất: `aiohttp` web server + `discord.py` client chạy chung event loop. Không cần Redis, không cần DB ngoài.

---

## 3. Hợp đồng API

### 3.1 `POST /api/deaths`

Header bắt buộc: `X-Tracker-Token: <API_TOKEN>` (so sánh bằng `hmac.compare_digest`).
Giới hạn body: 8 MB (`client_max_size`).

```json
{
  "id": "9f1c2b7e-...",
  "ts_utc": "2026-10-30T16:22:41.208Z",
  "ts_local": "2026-10-30 23:22:41",
  "session_id": "s_20261030_231500",
  "death_no": 3,
  "total_deaths": 47,
  "seconds_since_prev_death": 143.2,
  "session_elapsed_s": 902.4,
  "confidence": 1.0,
  "screenshot": "deaths/2026-10-30/232241_208_d003.jpg",
  "screenshot_b64": "/9j/4AAQSkZJRg...",
  "screenshot_mime": "image/jpeg",
  "screen": { "width": 1920, "height": 1080, "monitor": 0, "hdr": false },
  "capture_backend": "dxgi",
  "tracker_version": "0.1.0"
}
```

Trả về:

| Tình huống | Status | Body |
|---|---|---|
| Gửi ít nhất 1 kênh thành công | 200 | `{"ok":true,"delivered":2,"failed":0}` |
| Có kênh lỗi, có kênh thành công | 200 | `{"ok":true,"delivered":1,"failed":1,"errors":["..."]}` |
| Chưa cấu hình kênh nào | 503 | `{"ok":false,"error":"no_channels"}` → tracker giữ lại và thử lại |
| Token sai / thiếu | 403 | `{"ok":false,"error":"forbidden"}` |
| JSON hỏng / thiếu `id` | 400 | `{"ok":false,"error":"bad_payload","detail":"..."}` |

Trả 503 khi chưa có kênh là cố ý: thà giữ event trong outbox (retry tối đa 5 phút/lần) còn hơn âm thầm mất lần chết.

### 3.2 `GET /health` → `200 text/plain "ok"` (dùng cho UptimeRobot, không cần token).

### 3.3 `GET /` → trang HTML tối giản: trạng thái bot, số kênh, số event đã nhận, lần chết gần nhất. Không lộ token.

---

## 4. Cấu hình

### 4.1 Biến môi trường (bí mật, đặt trên Render)

| Biến | Bắt buộc | Mặc định | Ý nghĩa |
|---|---|---|---|
| `DISCORD_TOKEN` | có | — | token bot, **không bao giờ ghi vào code hay gửi qua chat** |
| `API_TOKEN` | có | — | phải trùng `bot.token` trong `config.toml` của tracker |
| `PORT` | không | `8080` | Render tự set |
| `GUILD_ID` | nên có | — | sync slash command vào 1 server ngay lập tức (không có thì sync global, chờ tới 1 giờ) |
| `CHANNELS` | không | — | danh sách kênh mặc định, dạng `123456789,987654321` — thêm vào mỗi lần khởi động |
| `IMAGE_MODE` | không | `on` | `on`/`off` cho các kênh thêm từ `CHANNELS` |
| `LOG_LEVEL` | không | `INFO` | |

### 4.2 Cấu hình runtime (đặt bằng lệnh slash)

```json
{
  "version": 1,
  "default_image": true,
  "paused": false,
  "channels": { "123456789": { "image": null }, "987654321": { "image": false } },
  "stats": { "received": 12, "last_death_utc": "2026-10-30T16:22:41.208Z" }
}
```

`image: null` = theo `default_image`; `true`/`false` = ép riêng cho kênh đó.

### 4.3 Lưu bền vững trên Render free (đĩa ephemeral)

Thứ tự đọc khi khởi động:

1. **Cache cục bộ** `data/config.json` (nhanh, có thể bị xoá khi Render restart).
2. **Nguồn sự thật: một message ghim trong Discord.** Bot giữ 1 message chứa JSON (marker `KTL_CONFIG_V1`); đọc/ghi bằng `channel.pins()`. Discord là DB → sống sót qua mọi lần deploy, không cần đĩa.
3. **Env** (`CHANNELS`) làm nền tảng cuối, luôn được merge vào.

**Nơi ghim cấu hình (neo) — không bắt buộc phải có kênh riêng:**

- `/ktl setup channel:#kênh` → ghim vào đúng kênh đó (thường là kênh thông báo).
- `/ktl setup` không truyền kênh → dùng **kênh thông báo đầu tiên** nếu đã có.
- Chưa có kênh nào → mới tạo kênh riêng tư `khi-tuyet-luc-config` làm chỗ chứa duy nhất có thể.
- Khi nạp lại, bot quét các kênh đã cấu hình (từ cache) để tìm message marker; không thấy mới tìm kênh tên `khi-tuyet-luc-config` (đường lui cho cấu hình cũ).
- Không cho `/ktl remove` chính kênh đang neo cấu hình — phải `/ktl setup channel:#khác` trước, tránh mất cấu hình.

---

## 5. Lệnh slash

Đăng ký dưới tên `ktl`. Bắt buộc quyền **Quản lý máy chủ** với lệnh cấu hình.

**Mọi phản hồi của lệnh đều là embed** (không trả text trần): mỗi embed có tiêu đề ngắn, thân là các dòng `▸`, màu theo kết quả — thành công `0x4C7A6B`, cảnh báo/lỗi `0x8C3A22`, thông tin `0x7A6440`.

| Lệnh | Tham số | Tác dụng |
|---|---|---|
| `/ktl setup` | `channel` (tuỳ chọn) | ghim cấu hình vào kênh thông báo (mặc định: kênh đầu tiên), không có kênh nào mới tạo kênh riêng |
| `/ktl add` | `channel`, `image` (tuỳ chọn) | thêm kênh nhận thông báo |
| `/ktl remove` | `channel` | bỏ kênh |
| `/ktl list` | — | bảng các kênh + chế độ ảnh + trạng thái |
| `/ktl image` | `channel`, `mode` = `on`/`off`/`default` | ép chế độ ảnh cho 1 kênh |
| `/ktl default-image` | `mode` = `on`/`off` | mặc định chung |
| `/ktl deaths` | `count` (0–100000) | đặt tổng kiếp đã có trước khi dùng tool |
| `/ktl player` | `member` (bỏ trống = xoá) | ghim người chơi: tên + avatar trong embed |
| `/ktl test` | `channel` (tuỳ chọn) | gửi 1 thông báo mẫu **thật** vào kênh để xem embed ngay |
| `/ktl preview` | `image` (tuỳ chọn) | xem **đúng embed sẽ hiện mỗi lần chết**, ngay trong câu trả lời riêng tư (không đăng lên kênh) |
| `/ktl status` | — | cấu hình hiện tại + cảnh giới + người chơi + số event đã nhận |
| `/ktl pause` | — | tạm ngưng thông báo (tracker vẫn được nhận) |
| `/ktl resume` | — | chạy tiếp |
| `/ktl help` | — | bảng tóm tắt mọi lệnh, gửi riêng tư |

Giới hạn 10 kênh (đủ dùng, tránh tự bắn rate limit của mình).

---

## 6. Thiết kế embed (kiếm hiệp / nhập ma)

Nguyên tắc thị giác:

- Không dùng emoji — chỉ Hán tự và ký tự trang trí (`氣絕錄`, `乂`, `血`, `煞`, `◈`, `︽`). Nhẹ, đúng chất, không bị Discord render lệch.
- Bảng màu theo cảnh giới (mỗi 50 mạng đổi một bậc, xem §12) — từ `0x4C7A6B` (未染) tới `0xD60000` (無間).
- Mỗi lần gửi chọn ngẫu nhiên 1 câu thơ trong bộ 12 câu, không lặp lại câu vừa dùng.
- Liên tử (chết trong vòng 90 s so với lần trước) → thêm dòng "ma khí nhập thể" và tiêu đề đổi hậu tố.

Mô phỏng bố cục:

```
[ ảnh 1920x1080 — khung hình ngay TRƯỚC khi chữ DEAD hiện ]
┌───────────────────────────────────────────────┐
│ Khí Tuyệt Lục                                      │  ← author
│ 氣絕錄 · Tứ Chuyển · Nhập Ma                    │  ← title
│ 乂乂乂乂乂乂乂乂乂乂乂                        │
│ Ma khí quấn thân, huyết vụ tản như khói nhang │  ← description
│ tàn. Ngươi ngã xuống — bia đá khắc thêm một   │
│ vết.                                          │
│ 乂乂乂乂乂乂乂乂乂乂乂                        │
│ 血 · Tử kỳ      │ 命 · Tổng kiếp │ 時 · Cách   │  ← fields inline
│ #3              │ #47            │ 2 phút 41 s │
│ 境 · Cảnh giới   │ ◈ Phiên        │ 連 · Liên tử│
│ 未染 · Vô Nhiễm  │ 23:15 → nay    │ —           │
│ 氣絕錄 · đã khắc vào huyết thư                  │  ← footer
└───────────────────────────────────────────────┘
```

Quy tắc kỹ thuật:

- Ảnh gửi bằng `discord.File` (attachment thường) **trước**, embed **sau** → Discord render ảnh ở trên, embed ở dưới. Không dùng `embed.set_image` (sẽ nhét ảnh xuống đáy embed).
- Nếu kênh tắt ảnh: chỉ gửi embed.
- Nếu event không có ảnh (tracker tắt screenshot): chỉ gửi embed, footer ghi chú "vô ảnh".
- Giới hạn cứng của Discord: title ≤ 256, description ≤ 4096, field value ≤ 1024, footer ≤ 2048, tổng ≤ 6000, ≤ 25 field. Bộ dựng embed phải tự cắt và có test.
- `embed.timestamp` = thời điểm chết (UTC) để Discord hiện giờ tương đối.

---

## 7. Cấu trúc code

```
bot code/bot/
├─ SPEC.md                  # tài liệu này
├─ README.md                # hướng dẫn deploy Render + UptimeRobot
├─ requirements.txt         # discord.py, aiohttp
├─ render.yaml              # blueprint deploy 1 click
├─ .env.example
├─ run_local.bat            # chạy thử trên máy
├─ khi_tuyet_luc/
│  ├─ __main__.py           # entrypoint: web server + bot, SIGTERM
│  ├─ settings.py           # đọc env, validate
│  ├─ texts.py              # kho câu thơ, Hán tự, bậc chuyển
│  ├─ event.py              # parse payload tracker + decode ảnh
│  ├─ embed.py              # dựng embed kiếm hiệp
│  ├─ store.py              # cấu hình: cache + message ghim Discord + env (neo linh hoạt)
│  ├─ notify.py             # gửi tới nhiều kênh, chế độ ảnh, dựng payload xem trước
│  ├─ web.py                # aiohttp: /health, /, /api/deaths
│  └─ commands.py           # 14 lệnh slash, mọi phản hồi là embed
└─ tools/
   ├─ test_embed.py         # test thuần offline: giới hạn embed, nội dung, cảnh giới
   ├─ test_notify.py        # nhiều kênh, chống trùng, liên tử, avatar, build_preview
   ├─ test_store.py         # neo cấu hình: ghim vào kênh thông báo, khôi phục sau mất cache
   └─ test_webhook.py       # test handler bằng aiohttp TestClient (không cần token)
```

---

## 8. Triển khai Render + UptimeRobot (tóm tắt, chi tiết ở README)

1. Discord Developer Portal → tạo Application "Khí Tuyệt Lục" → Bot → copy token.
2. Invite với scope `bot` + `applications.commands`; quyền: Send Messages, Embed Links, Attach Files, Read Message History, Manage Channels.
3. Push thư mục `bot code/bot` lên một repo GitHub.
4. Render → New → Web Service → repo đó, root `bot code/bot` (hoặc repo chỉ chứa bot), build `pip install -r requirements.txt`, start `python -m khi_tuyet_luc`.
5. Set env: `DISCORD_TOKEN`, `API_TOKEN`, `GUILD_ID`.
6. UptimeRobot: HTTP(s) monitor `https://<app>.onrender.com/health`, mỗi 5 phút.
7. Trong server: `/ktl setup` → `/ktl add`.
8. Sửa `config.toml` của tracker: `bot.endpoint = "https://<app>.onrender.com/api/deaths"`, `bot.token = "<API_TOKEN>"`.

---

## 9. Kiểm thử (không cần token Discord)

| Test | Nội dung |
|---|---|
| `tools/test_embed.py` | Dựng embed cho 6 tình huống (mới/liên tử/tổng lớn/không ảnh/không có số liệu/số cực lớn) → assert không vượt giới hạn Discord, đúng thứ tự field, đúng bậc màu, đúng số chữ Hán; kèm lưu/đọc cấu hình |
| `tools/test_notify.py` | Nhiều kênh, bật/tắt ảnh, chống trùng `id`, liên tử, lỗi quyền, avatar người chơi, và `build_preview()` (đúng embed, không gửi gì, không đổi số liệu) |
| `tools/test_store.py` | Neo cấu hình: ghim vào kênh thông báo, không tạo kênh riêng, không sinh message trùng, khôi phục sau khi mất cache (quét pin), kênh tên cũ vẫn đọc được |
| `tools/test_webhook.py` | aiohttp TestClient: token sai → 403; thiếu `id` → 400; chưa có kênh → 503; hợp lệ → 200 và ảnh base64 được decode đúng kích thước; body quá lớn → 413 |

Chạy được trên máy, không cần kết nối Discord, không cần Render.

---

## 10. Rủi ro

| Rủi ro | Ảnh hưởng | Xử lý |
|---|---|---|
| Render free ngủ sau 15 phút | POST đầu tiên chậm/timeout | UptimeRobot 5 phút + tracker timeout 10 s + outbox retry |
| Đĩa ephemeral xoá sạch khi deploy | mất cấu hình | cấu hình lưu trong message ghim của Discord |
| Token lộ | chiếm bot | chỉ đặt qua env Render, không commit, không gửi chat; repo công khai nên có `.gitignore` |
| Rate limit Discord khi nhiều kênh | mất thông báo | tối đa 10 kênh, mỗi kênh 1 request, lỗi được trả về trong `errors` |
| Ảnh > 8 MB | 413 | tracker gửi JPEG q80 ~150 KB; bot chặn cứng 8 MB |
| Kênh bị xoá / mất quyền | lỗi im lặng | bot trả lỗi 404/403 vào `errors`, ghi log |

---

## 11. Tiêu chí nghiệm thu

1. `POST /api/deaths` hợp lệ → đúng N kênh nhận được, ảnh trên + embed dưới, nội dung khớp số liệu event.
2. Đổi `image` của 1 kênh sang `off` → kênh đó chỉ nhận embed, kênh khác vẫn có ảnh.
3. Deploy lại Render → cấu hình kênh vẫn còn.
4. Tắt bot 10 phút rồi bật lại → tracker đẩy hết event tồn trong outbox, không mất lần chết nào.
5. `/ktl test` gửi được thông báo mẫu ngay.
6. `python tools\test_embed.py` và `python tools\test_webhook.py` PASS 100%.

---

## 12. Cảnh giới theo tổng kiếp + người chơi (v1.1)

### 12.1 Vì sao bot tự đếm

Người chơi đã chết **39 lần trước khi có tool**, tracker chỉ biết số của riêng nó. Nên
"tổng kiếp" là số của **bot**, không phải của tracker:

```
tổng kiếp = cfg.deaths_total          # admin đặt bằng /ktl deaths
          + 1 mỗi lần gửi thành công  # note_death(), chỉ khi delivered > 0
```

- `deaths_total` nằm trong `BotConfig` → chết cùng message ghim, sống qua mọi deploy.
- Admin đặt lại bằng `/ktl deaths count:39`; đặt xong mọi thứ (màu, cảnh giới) đổi ngay từ lần chết kế.
- Không dùng `event.total_deaths` của tracker để tính cảnh giới (tracker reset DB là về 0);
  con số đó vẫn hiện ở field `命 · Tổng kiếp` nếu bot chưa có số của mình.

### 12.2 Thang cảnh giới — 50 mạng một bậc, dừng ở 500

| Tổng kiếp | Hán | Việt | Trạng thái | Màu |
|---|---|---|---|---|
| 0–49 | 未染 | Vô Nhiễm | chưa vấy máu, tay còn sạch | `#4C7A6B` |
| 50–99 | 染血 | Nhiễm Huyết | vết máu đầu tiên đã khô trên áo | `#6E7448` |
| 100–149 | 傷痕 | Thương Ngân | thân đầy sẹo, bước chân đã chậm | `#7A6440` |
| 150–199 | 煞氣 | Sát Khí | sát khí bốc lên, quỷ thần tránh xa | `#84502F` |
| 200–249 | 血債 | Huyết Trái | nợ máu chồng lên nợ máu | `#8C3A22` |
| 250–299 | 入魔 | Nhập Ma | ma khí đã vào gân cốt | `#971E1E` |
| 300–349 | 業障 | Nghiệp Chướng | nghiệp cũ quấn lấy cổ chân | `#A21515` |
| 350–399 | 幽途 | U Đồ | đường âm đã mở, chỉ một lối | `#AD0D0D` |
| 400–449 | 輪迴 | Luân Hồi | chết rồi sống lại, quên cả tên mình | `#B80808` |
| 450–499 | 修羅 | Tu La | sa vào tu la đạo, sát nghiệp không dứt | `#C70404` |
| 500+ | 無間 | Vô Gián | vô gián địa ngục, không còn lối ra | `#D60000` |

Màu embed = màu cảnh giới (đây là thứ duy nhất đổi theo tổng kiếp). Chết liên tiếp ≥5 lần
vẫn ép màu đỏ tươi `#E01B1B` để báo "đang thua dồn dập" — ngoại lệ có chủ đích.

Hiển thị trong embed: tiêu đề thêm Hán tự cảnh giới (`氣絕錄 · 第三 · Tam Chuyển · 無間`),
field `境 · Cảnh giới` ghi `未染 · Vô Nhiễm` + trạng thái + `còn N mạng → 染血`.

### 12.3 Người chơi

- `/ktl player member:@ai` ghim người đang chơi; `/ktl player` (bỏ trống) để xoá.
- `/ktl setup` tự gán người chơi = người gọi lệnh — đúng ý "ai setup thì hiện người đó".
- Embed dùng **author** để hiện: tên hiển thị + avatar Discord của người chơi.
  Bot name/avatar chỉ dùng khi chưa gán ai.
- Lưu `{"id", "name", "avatar"}`; khi gửi thì lấy avatar tươi từ cache Discord
  (link CDN có chữ ký hết hạn), nếu không có cache mới dùng ảnh đã lưu.

