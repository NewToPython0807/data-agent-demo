"""辅助命令：生成账号密码的 bcrypt 哈希（T07）。

用法（二选一）：
    python -m app.password_tool 你的密码
    python -m app.password_tool            # 不传参时交互式输入

把打印出的 ACCOUNT_PASSWORD_HASH=... 复制到 .env 中即可。
"""
from __future__ import annotations

import sys

from app.auth import hash_password


def main() -> None:
    if len(sys.argv) > 1:
        plain = sys.argv[1]
    else:
        plain = input("请输入明文密码：")
    print("ACCOUNT_PASSWORD_HASH=" + hash_password(plain))


if __name__ == "__main__":
    main()
