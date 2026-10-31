"""让 `python -m era5x` 能跑起来。

Python 执行 `python -m era5x` 时会找包里的 __main__.py 并执行它，
所以这两行就是 CLI 的入口；真正的逻辑在 cli.py。
"""

from .cli import main

raise SystemExit(main())
