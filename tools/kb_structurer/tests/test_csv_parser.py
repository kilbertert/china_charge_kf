"""单元测试:CSV → menu MD 解析器。"""
import sys
import tempfile
import csv
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parsers.csv_parser import csv_to_menu


SAMPLE_CSV = """name(菜单),id(菜单id),component,字段key,CN(中文对照),EN(英文对照),层级路径,顶级菜单名称
代码生成,f513,Layout,(No I18n Found),-,-,平台>平台设置>常用工具>代码生成,平台
管理员设置,abc,views/upms/user/index,user_1,账号：,Account:, >系统设置>管理员设置,
管理员设置,abc,views/upms/user/index,user_2,昵称：,Nickname:, >系统设置>管理员设置,系统
"""


def test_csv_to_menu():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8-sig") as f:
        f.write(SAMPLE_CSV)
        csv_path = f.name

    with tempfile.TemporaryDirectory() as out_dir:
        count = csv_to_menu(csv_path, out_dir, encoding="utf-8-sig")
        assert count == 2, f"Expected 2 MDs, got {count}"

        files = sorted(Path(out_dir).glob("*.md"))
        assert len(files) == 2

        f1 = files[0].read_text(encoding="utf-8")
        assert "# 代码生成" in f1
        assert "平台>平台设置>常用工具>代码生成" in f1
        assert "f513" in f1

        f2 = files[1].read_text(encoding="utf-8")
        assert "# 管理员设置" in f2
        assert "字段中英文对照" in f2
        assert "user_1" in f2
        assert "user_2" in f2

    print("✓ test_csv_to_menu passed")


if __name__ == "__main__":
    test_csv_to_menu()