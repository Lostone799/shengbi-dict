#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VCF通讯录转声笔词库工具 v1.2.0
将手机导出的VCF通讯录文件转换为Rime输入法声笔方案词库

功能：
- 自动扫描手机存储中的VCF文件
- 自动读取Android通讯录数据库
- 智能编码生成与冲突处理
- 自动备份已有词库
- 一键复制到Rime配置目录
"""

import re
import os
import glob
import quopri
import shutil
import sqlite3
import argparse
import subprocess
from datetime import datetime
from pathlib import Path
from pypinyin import lazy_pinyin, Style


# ============================================================
# 常量配置
# ============================================================

# 手机存储中搜索VCF文件的目录列表
VCF_SEARCH_DIRS = [
    "/storage/emulated/0/Download/",
    "/storage/emulated/0/Documents/",
    "/storage/emulated/0/DCIM/",
    "/storage/emulated/0/Bluetooth/",
    "/storage/emulated/0/backup/",
    "/storage/emulated/0/",
]

# Android通讯录数据库路径
CONTACTS_DB_PATH = "/data/data/com.android.providers.contacts/databases/contacts2.db"

# 默认Rime配置目录
DEFAULT_RIME_DIR = "/storage/emulated/0/rime/"

# 默认词库文件名
DEFAULT_DICT_NAME = "sbzdy.txt"


# ============================================================
# VCF解析器
# ============================================================

class VCFParser:
    """VCF文件解析器"""

    @staticmethod
    def decode_quoted_printable(encoded_str):
        """解码QUOTED-PRINTABLE编码的字符串"""
        try:
            bytes_str = encoded_str.encode('latin-1')
            decoded_bytes = quopri.decodestring(bytes_str)
            return decoded_bytes.decode('utf-8')
        except Exception:
            return None

    @staticmethod
    def parse(vcf_path):
        """
        解析VCF文件，提取联系人姓名

        Args:
            vcf_path: VCF文件路径

        Returns:
            list: 联系人姓名列表（去重）
        """
        names = []

        with open(vcf_path, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                stripped = line.strip()

                # 跳过非FN行
                if not stripped.startswith('FN'):
                    continue

                # 尝试QUOTED-PRINTABLE编码的FN字段
                fn_match = re.search(
                    r'FN;CHARSET=UTF-8;ENCODING=QUOTED-PRINTABLE:([^\n\r]+)',
                    stripped
                )
                if fn_match:
                    name = VCFParser.decode_quoted_printable(fn_match.group(1).strip())
                else:
                    # 尝试普通FN格式
                    fn_match = re.search(r'FN[^:]*:(.+)', stripped)
                    if fn_match:
                        name = fn_match.group(1).strip()
                    else:
                        continue

                if name and len(name) >= 2:
                    names.append(name)

        return list(set(names))


# ============================================================
# 通讯录数据库读取器
# ============================================================

class ContactsDBReader:
    """Android通讯录数据库读取器"""

    @staticmethod
    def is_available():
        """检查通讯录数据库是否可访问"""
        return os.path.exists(CONTACTS_DB_PATH)

    @staticmethod
    def read():
        """
        从Android通讯录数据库读取联系人姓名

        Returns:
            list: 联系人姓名列表（去重）
        """
        names = []
        try:
            conn = sqlite3.connect(CONTACTS_DB_PATH)
            cursor = conn.cursor()

            # 查询联系人姓名（raw_contacts + data表关联）
            cursor.execute("""
                SELECT d.data1
                FROM data d
                JOIN raw_contacts r ON d.raw_contact_id = r._id
                WHERE d.mimetype_id IN (
                    SELECT _id FROM mimetypes WHERE mimetype = 'vnd.android.cursor.item/name'
                )
                AND d.data1 IS NOT NULL
                AND d.data1 != ''
            """)

            for row in cursor.fetchall():
                name = row[0].strip()
                if name and len(name) >= 2:
                    names.append(name)

            conn.close()
        except Exception as e:
            print(f"  ⚠️ 读取通讯录数据库失败: {e}")

        return list(set(names))


# ============================================================
# VCF文件扫描器
# ============================================================

class VCFScanner:
    """VCF文件扫描器"""

    @staticmethod
    def scan(search_dirs=None):
        """
        扫描指定目录中的VCF文件

        Args:
            search_dirs: 搜索目录列表（默认使用VCF_SEARCH_DIRS）

        Returns:
            list: 找到的VCF文件路径列表
        """
        if search_dirs is None:
            search_dirs = VCF_SEARCH_DIRS

        vcf_files = []
        for directory in search_dirs:
            if not os.path.isdir(directory):
                continue
            for pattern in ["**/*.vcf", "**/*.VCF"]:
                matches = glob.glob(
                    os.path.join(directory, pattern),
                    recursive=True
                )
                vcf_files.extend(matches)

        return list(set(vcf_files))


# ============================================================
# 自动通讯录获取器
# ============================================================

class AutoContactsFetcher:
    """自动获取通讯录（优先数据库，其次扫描VCF文件）"""

    @staticmethod
    def fetch(vcf_hint_path=None):
        """
        自动获取通讯录联系人

        Args:
            vcf_hint_path: 用户指定的VCF文件路径（可选）

        Returns:
            tuple: (names_list, source_description)
        """
        # 1. 如果用户指定了VCF文件，直接使用
        if vcf_hint_path and os.path.isfile(vcf_hint_path):
            names = VCFParser.parse(vcf_hint_path)
            return names, f"指定文件: {vcf_hint_path}"

        # 2. 尝试读取通讯录数据库
        if ContactsDBReader.is_available():
            print("  📱 检测到通讯录数据库，正在读取...")
            names = ContactsDBReader.read()
            if names:
                return names, f"通讯录数据库: {CONTACTS_DB_PATH}"

        # 3. 扫描VCF文件
        print("  🔍 正在扫描手机存储中的VCF文件...")
        vcf_files = VCFScanner.scan()

        if not vcf_files:
            return [], "未找到通讯录数据"

        # 选择最新的VCF文件
        vcf_files.sort(key=lambda f: os.path.getmtime(f), reverse=True)
        latest_vcf = vcf_files[0]

        print(f"  📄 找到 {len(vcf_files)} 个VCF文件，使用最新的: {latest_vcf}")
        names = VCFParser.parse(latest_vcf)

        return names, f"VCF文件: {latest_vcf}"


# ============================================================
# 声笔编码生成器
# ============================================================

class ShengbiEncoder:
    """声笔编码生成器"""

    @staticmethod
    def encode(name):
        """
        生成声笔编码：首字声母 + 后续各字首字母

        Args:
            name: 中文姓名

        Returns:
            str: 声笔编码（小写）
        """
        pinyins = lazy_pinyin(name, style=Style.NORMAL)
        shengmus = lazy_pinyin(name, style=Style.INITIALS, strict=False)

        if not pinyins:
            return None

        first_shengmu = shengmus[0] if shengmus[0] else pinyins[0][0]

        code = first_shengmu.lower()
        for py in pinyins[1:]:
            if py:
                code += py[0].lower()

        return code


# ============================================================
# 词库管理器
# ============================================================

class DictManager:
    """词库管理器"""

    @staticmethod
    def parse_dict(dict_path):
        """
        解析现有词库文件

        Args:
            dict_path: 词库文件路径

        Returns:
            tuple: (word_to_code, code_to_word)
        """
        word_to_code = {}
        code_to_word = {}

        if not Path(dict_path).exists():
            return word_to_code, code_to_word

        with open(dict_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split('\t')
                if len(parts) >= 2:
                    word = parts[0].strip()
                    code = parts[1].strip()
                    word_to_code[word] = code
                    code_to_word[code] = word

        return word_to_code, code_to_word

    @staticmethod
    def is_valid_chinese_name(name):
        """
        判断是否为有效的中文姓名（2-4个汉字）

        Args:
            name: 待检查的姓名

        Returns:
            bool: 是否有效
        """
        return bool(re.match(r'^[\u4e00-\u9fa5]{2,4}$', name))


# ============================================================
# 转换器
# ============================================================

class VCFToShengbiConverter:
    """VCF转声笔词库转换器"""

    def __init__(self, existing_dict_path=None):
        """
        初始化转换器

        Args:
            existing_dict_path: 现有词库文件路径（可选）
        """
        self.existing_dict_path = existing_dict_path

        if existing_dict_path:
            self.existing_words, self.existing_codes = DictManager.parse_dict(
                existing_dict_path
            )
        else:
            self.existing_words = {}
            self.existing_codes = {}

    def convert(self, names, output_path=None):
        """
        执行转换

        Args:
            names: 联系人姓名列表
            output_path: 输出文件路径（可选）

        Returns:
            dict: 转换结果统计
        """
        # 1. 筛选新联系人
        new_names = [
            name for name in names
            if DictManager.is_valid_chinese_name(name)
            and name not in self.existing_words
        ]

        # 2. 生成编码（处理冲突）
        used_codes = set(self.existing_codes.keys())
        new_entries = []

        for name in sorted(new_names):
            base_code = ShengbiEncoder.encode(name)
            if not base_code:
                continue

            code = base_code
            if code in used_codes:
                suffix = 1
                while f"{base_code}{suffix}" in used_codes:
                    suffix += 1
                code = f"{base_code}{suffix}"

            used_codes.add(code)
            new_entries.append((name, code))

        # 3. 生成输出内容
        lines = []

        if not self.existing_dict_path:
            lines.extend([
                "# Rime dict",
                "# encoding: utf-8",
                '# version: "1.0"',
                "# 声笔通用自定义用户词库",
                "# 编码格式：字词+Tab符+编码，首码必须为声母，后接小写字母",
                "",
            ])
        else:
            with open(self.existing_dict_path, 'r', encoding='utf-8') as f:
                lines.append(f.read().rstrip())
            lines.append("")
            lines.append(f"# 通讯录新增联系人 ({datetime.now().strftime('%Y-%m-%d %H:%M')})")

        for name, code in new_entries:
            lines.append(f"{name}\t{code}")

        # 4. 写入输出文件
        if not output_path:
            output_path = "/data/user/work/sbzdy_updated.txt"

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        return {
            'total_contacts': len(names),
            'existing_entries': len(self.existing_words),
            'new_entries': len(new_entries),
            'output_file': str(output_path)
        }


# ============================================================
# 文件操作（含自动备份）
# ============================================================

def copy_with_backup(source_file, target_dir, new_name=None):
    """
    复制文件到目标目录，自动备份已存在的文件

    Args:
        source_file: 源文件路径
        target_dir: 目标目录
        new_name: 新文件名（可选）

    Returns:
        str: 目标文件完整路径
    """
    source = Path(source_file)
    target = Path(target_dir)

    # 创建目标目录
    target.mkdir(parents=True, exist_ok=True)

    # 确定目标文件名
    if new_name:
        target_file = target / new_name
    else:
        target_file = target / source.name

    # 如果目标文件已存在，先备份
    if target_file.exists():
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"{target_file.stem}_backup_{timestamp}{target_file.suffix}"
        backup_path = target / backup_name
        shutil.copy2(target_file, backup_path)
        print(f"  📦 已备份原文件: {backup_path}")

    # 复制新文件
    shutil.copy2(source, target_file)

    return str(target_file)


# ============================================================
# 命令行入口
# ============================================================

def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description='将通讯录转换为声笔输入法词库（支持自动获取）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  # 自动模式（自动获取通讯录 + 合并词库 + 复制到手机）
  python3 convert.py --auto

  # 指定VCF文件
  python3 convert.py contacts.vcf

  # 合并到现有词库
  python3 convert.py contacts.vcf -d sbzdy.txt -o sbzdy_updated.txt

  # 完整工作流（转换+备份+复制到手机）
  python3 convert.py --auto -d /storage/emulated/0/rime/sbzdy.txt --copy-to /storage/emulated/0/rime/ --rename sbzdy.txt
        '''
    )

    # 位置参数（可选，用于向后兼容）
    parser.add_argument(
        'vcf_file',
        nargs='?',
        default=None,
        help='VCF通讯录文件路径（可选，使用 --auto 可自动获取）'
    )

    # 自动模式
    parser.add_argument(
        '--auto',
        action='store_true',
        help='自动获取通讯录（优先数据库，其次扫描VCF文件）'
    )

    # 词库参数
    parser.add_argument(
        '-d', '--dict',
        dest='dict_file',
        help='现有词库文件路径（用于合并）'
    )
    parser.add_argument(
        '-o', '--output',
        dest='output_file',
        help='输出词库文件路径'
    )

    # 复制参数
    parser.add_argument(
        '--copy-to',
        dest='copy_target',
        default=DEFAULT_RIME_DIR,
        help=f'复制到目标目录（默认: {DEFAULT_RIME_DIR}）'
    )
    parser.add_argument(
        '--rename',
        dest='new_name',
        default=DEFAULT_DICT_NAME,
        help=f'复制时重命名文件（默认: {DEFAULT_DICT_NAME}）'
    )
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='禁用自动备份'
    )
    parser.add_argument(
        '--no-copy',
        action='store_true',
        help='不复制到目标目录（仅生成文件）'
    )

    args = parser.parse_args()

    # ========================================
    # Step 1: 获取通讯录
    # ========================================
    print("=" * 50)
    print("  声笔词库生成工具 v1.2.0")
    print("=" * 50)

    if args.auto or args.vcf_file is None:
        print("\n📡 Step 1: 自动获取通讯录...")
        names, source = AutoContactsFetcher.fetch(args.vcf_file)
        if not names:
            print("  ❌ 未找到通讯录数据！请手动指定VCF文件。")
            print("  提示: python3 convert.py contacts.vcf")
            return 1
        print(f"  ✅ 数据来源: {source}")
        print(f"  ✅ 提取联系人: {len(names)} 个")
    else:
        print(f"\n📄 Step 1: 读取VCF文件: {args.vcf_file}")
        if not os.path.isfile(args.vcf_file):
            print(f"  ❌ 文件不存在: {args.vcf_file}")
            return 1
        names = VCFParser.parse(args.vcf_file)
        source = args.vcf_file
        print(f"  ✅ 提取联系人: {len(names)} 个")

    # ========================================
    # Step 2: 转换为词库
    # ========================================
    print(f"\n🔤 Step 2: 生成声笔编码...")
    converter = VCFToShengbiConverter(args.dict_file)
    result = converter.convert(names, args.output_file)

    print(f"  通讯录联系人: {result['total_contacts']}")
    print(f"  现有词库词条: {result['existing_entries']}")
    print(f"  新增词条: {result['new_entries']}")
    print(f"  输出文件: {result['output_file']}")

    if result['new_entries'] == 0:
        print("\n  ℹ️ 没有新增联系人，词库已是最新。")
        return 0

    # ========================================
    # Step 3: 复制到目标目录（含自动备份）
    # ========================================
    if not args.no_copy:
        print(f"\n📋 Step 3: 复制到目标目录...")
        try:
            if args.no_backup:
                target_file = copy_to_target(
                    result['output_file'],
                    args.copy_target,
                    args.new_name
                )
            else:
                target_file = copy_with_backup(
                    result['output_file'],
                    args.copy_target,
                    args.new_name
                )
            print(f"  ✅ 已复制到: {target_file}")
        except Exception as e:
            print(f"  ❌ 复制失败: {e}")
            return 1

    # ========================================
    # 完成
    # ========================================
    print(f"\n{'=' * 50}")
    print(f"  ✅ 全部完成！新增 {result['new_entries']} 个词条")
    print(f"{'=' * 50}")

    return 0


def copy_to_target(source_file, target_dir, new_name=None):
    """复制文件到目标目录（无备份）"""
    source = Path(source_file)
    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)

    if new_name:
        target_file = target / new_name
    else:
        target_file = target / source.name

    shutil.copy2(source, target_file)
    return str(target_file)


if __name__ == '__main__':
    exit(main())
