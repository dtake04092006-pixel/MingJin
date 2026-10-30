"""Chạy bot Khí Tuyệt Lục qua tên cũ: `python -m menh_tan`.

Chỉ dùng khi Start Command trên Render vẫn còn `python -m menh_tan`. Sau khi
đổi Start Command sang `python -m khi_tuyet_luc`, thư mục này xoá được.
"""

from __future__ import annotations

import os

from khi_tuyet_luc.__main__ import main

if __name__ == "__main__":
    os.environ.setdefault("PYTHONUTF8", "1")
    raise SystemExit(main())
