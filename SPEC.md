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
2. **Nguồn sự thật: một message ghim trong Discord.** Bot giữ 1 message chứa JSON (marker `KTL_CONFIG_V1`) trong kênh tên `khi-tuyet-luc-config`; đọc/ghi bằng `channel.pins()`. Discord là DB → sống sót qua mọi lần deploy, không cần đĩa.
3. **Env** (`CHANNELS`) làm nền tảng cuối, luôn được merge vào.

`/ktl setup` tạo (hoặc tìm) kênh `khi-tuyet-luc-config`, ghim message cấu hình và trả lời hướng dẫn. Sau đó mọi lệnh khác đều ghi vào đó.

---

## 5. Lệnh slash

Đăng ký dưới tên `ktl`. Bắt buộc quyền **Quản lý máy chủ** với lệnh cấu hình.

| Lệnh | Tham số | Tác dụng |
|---|---|---|
| `/ktl setup` | — | tạo/tìm kênh `khi-tuyet-luc-config`, ghim cấu hình |
| `/ktl add` | `channel`, `image` (tuỳ chọn) | thêm kênh nhận thông báo |
| `/ktl remove` | `channel` | bỏ kênh |
| `/ktl list` | — | bảng các kênh + chế độ ảnh + trạng thái |
| `/ktl image` | `channel`, `mode` = `on`/`off`/`default` | ép chế độ ảnh cho 1 kênh |
| `/ktl default-image` | `mode` = `on`/`off` | mặc định chung |
| `/ktl test` | `channel` (tuỳ chọn) | gửi 1 thông báo mẫu để xem embed ngay |
| `/ktl status` | — | cấu hình hiện tại + số event đã nhận + lần chết gần nhất |
| `/ktl pause` | — | tạm ngưng thông báo (tracker vẫn được nhận) |
| `/ktl resume` | — | chạy tiếp |

Giới hạn 10 kênh (đủ dùng, tránh tự bắn rate limit của mình).

---

## 6. Thiết kế embed (kiếm hiệp / nhập ma)

Nguyên tắc thị giác:

- Không dùng emoji — chỉ Hán tự và ký tự trang trí (`氣絕錄`, `乂`, `血`, `煞`, `◈`, `︽`). Nhẹ, đúng chất, không bị Discord render lệch.
- Bảng màu theo "tầng ma khí" (theo tổng số lần chết): `0x7B0C0C` → `0x9B0F0F` → `0xB81313` → `0xD41A1A`.
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
│ 煞 · Ma khí     │ ◈ Phiên        │ 連 · Liên tử│
│ Tứ chuyển       │ 23:15 → nay    │ —           │
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
│  ├─ store.py              # cấu hình: cache + message ghim Discord + env
│  ├─ notify.py             # gửi tới nhiều kênh, chế độ ảnh
│  ├─ web.py                # aiohttp: /health, /, /api/deaths
│  └─ commands.py           # 9 lệnh slash
└─ tools/
   ├─ test_embed.py         # test thuần offline: giới hạn embed, nội dung
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
| `tools/test_embed.py` | Dựng embed cho 6 tình huống (mới/liên tử/tổng lớn/không ảnh/không có số liệu/số cực lớn) → assert không vượt giới hạn Discord, đúng thứ tự field, đúng bậc màu, đúng số chữ Hán |
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
