"""把 CDS 的 API key 写进 %USERPROFILE%\\.cdsapirc。

用法（在仓库根目录）：
    python 2_程序/0_设置CDS密钥.py

然后从 https://cds.climate.copernicus.eu/profile 的 "API key" 处
复制整串（形如 1a2b3c4d-5e6f-7890-abcd-ef1234567890），粘贴、回车。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

URL = "https://cds.climate.copernicus.eu/api"
RC = Path(os.path.expanduser("~/.cdsapirc"))


def main() -> int:
    print("=" * 58)
    print("CDS API key 设置")
    print("=" * 58)
    print()
    print("1. 浏览器打开：https://cds.climate.copernicus.eu/profile")
    print("2. 找到「API key」那一块")
    print("3. 复制整串（一整串，中间没有空格）")
    print()
    try:
        raw = input("把 key 粘贴到这里，然后回车：")
    except (EOFError, KeyboardInterrupt):
        print("\n已取消。")
        return 1

    key = raw.strip().strip('"').strip("'").strip()

    if not key:
        print("\n没读到内容，已取消。")
        return 1
    if any(c.isspace() for c in key):
        print()
        print("这串中间有空格，像是粘贴不全或带了多余内容。")
        print("请只复制 key 那一行冒号后面的整串，重新运行。")
        return 1

    RC.write_text(f"url: {URL}\nkey: {key}\n", encoding="ascii")
    print()
    print(f"已写入：{RC}")
    print(f"key 长度：{len(key)} 字符")
    print()
    print("下一步，验证一下：")
    print("    python 2_程序/1_下载ERA5.py --check")
    return 0


if __name__ == "__main__":
    sys.exit(main())
