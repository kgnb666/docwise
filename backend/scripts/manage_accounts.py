"""在 DocWise 数据目录中创建账号或为旧快照指定归属。"""

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.storage.accounts import create_account
from app.storage.workspace import adopt_legacy_documents


def main() -> None:
    parser = argparse.ArgumentParser(description="DocWise 本地账号管理")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("add", help="创建账号").add_argument("username")
    commands.add_parser("adopt-legacy", help="复制旧快照到指定账号").add_argument("username")
    args = parser.parse_args()

    try:
        if args.command == "add":
            password = getpass.getpass("密码：")
            if password != getpass.getpass("再次输入密码："):
                parser.error("两次输入的密码不一致")
            account = create_account(args.username, password)
            print(f"已创建账号 {account.username}")
        else:
            count = adopt_legacy_documents(args.username)
            print(f"已复制 {count} 份文档，请重启 DocWise 后端加载快照。")
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
