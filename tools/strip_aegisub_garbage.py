#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""清理 .ass 字幕里的两类「Aegisub 垃圾」。

一、[Aegisub Project Garbage] 段
    Aegisub 会把本机的工程状态写进字幕文件这一段里:音频/视频文件的本地路径、
    滚动/光标位置、缩放比例等等。这些对发布出去的字幕毫无用处,而且会泄露本地
    盘符、目录结构和原始文件名(隐私)。本脚本把这一段整段删掉,其余内容(包括
    UTF-8 BOM、CRLF/LF 换行)原封不动。

二、不可见字符
    Aegisub 合轴(join),或者从网页/文档/AI 输出里复制粘贴时,正文里会混进一批
    看不见的字符 —— 最常见的是 U+200E(LRM,左到右标记)。它们会引出两个很坑的
    故障:

      1. 字体检查报「'某某字体' 缺少下列字形：」,后面却一个字都列不出来。
         因为缺的就是印不出来的字符,那份列表看起来是空的 —— 极容易被误判成
         「字体没装全 / 字形覆盖不够」,然后白折腾半天换字体。
      2. 子集化 / 内嵌之后,那个字符照样缺。换字体救不了,只内嵌也救不了,
         因为字形根本不在字体里。

    实测案例:死亡游戏12(剧场版) 一份稿子里清出 460 个 U+200E。清完之后,
    字体检查界面里的「缺字形」告警自己就消失了。

    一个更省事的判据:
        「缺少下列字形：」后面列表为空  →  基本就是这一类,不是字体问题。

    默认清掉(视为垃圾):
        U+00AD        软连字符
        U+180E        蒙古文元音分隔符
        U+200B        零宽空格 ZWSP
        U+200E        左到右标记 LRM      ← 最常见的元凶
        U+200F        右到左标记 RLM
        U+202A-U+202E 双向嵌入/覆盖控制符 LRE RLE PDF LRO RLO
        U+2060-U+2064 词连接符、不可见运算符
        U+2066-U+2069 双向隔离符 LRI RLI FSI PDI
        U+FEFF        零宽不换行空格(残留在正文里的 BOM)

    要开关才清(默认保留,因为可能是有意为之):
        --zwj    U+200C / U+200D  ZWNJ / ZWJ
                 ZWJ 是 emoji 组合序列要用的,默认不动 —— 免得把彩虹旗那种
                 ZWJ 组合 emoji 拆成两个独立 emoji。
        --nbsp   U+00A0 / U+202F  不换行空格 / 窄不换行空格
                 有人用它防止断行,默认不动。

    明确不碰:
        U+3000          全角空格 —— 字幕排版的常用手段,动了会改变版面
        U+2000-U+200A   各种宽度的空格 —— 可能是有意的对齐
        U+2028 / U+2029 行、段分隔符 —— 本脚本不处理,遇到请手工看

三种模式:

  (默认) [--zwj] [--nbsp] [路径...]
                     就地改写给定文件;不给路径时,清理当前目录下所有 *.ass。
                     GitHub Action 用的就是这个模式;也可用于一次性清理存量文件。

  --check [同样的开关] [路径...]
                     只检查不改写。若仍有文件可清理(垃圾段或不可见字符),
                     打印它们并以非 0 退出。可用于 CI 卡点。

  --filter [同样的开关]
                     从 stdin 读入单个文件内容,把清理后的内容写到 stdout。
                     这是为 git "clean" filter 预留的(本仓库当前没用,留着备用)。
"""
import os
import sys
from collections import Counter

SECTION = "[Aegisub Project Garbage]"
BOM = b"\xef\xbb\xbf"

# 默认视为垃圾、直接清掉的不可见/格式控制字符。写成区间,便于阅读和往后追加。
DEFAULT_RANGES = (
    (0x00AD, 0x00AD),  # 软连字符
    (0x180E, 0x180E),  # 蒙古文元音分隔符
    (0x200B, 0x200B),  # 零宽空格 ZWSP
    (0x200E, 0x200F),  # LRM / RLM  ← 最常见的元凶
    (0x202A, 0x202E),  # LRE RLE PDF LRO RLO
    (0x2060, 0x2064),  # 词连接符、不可见运算符
    (0x2066, 0x2069),  # LRI RLI FSI PDI
    (0xFEFF, 0xFEFF),  # 残留在正文里的 BOM
)

# 需要开关才清的字符
OPT_IN_RANGES = (
    ("--zwj", ((0x200C, 0x200D),), "ZWNJ / ZWJ(emoji 组合序列要用)"),
    ("--nbsp", ((0x00A0, 0x00A0), (0x202F, 0x202F)), "不换行空格 / 窄不换行空格"),
)

OPT_IN_FLAGS = tuple(f for f, _ranges, _why in OPT_IN_RANGES)

CHAR_NAMES = {
    0x00A0: "NBSP 不换行空格",
    0x00AD: "软连字符",
    0x180E: "蒙古文元音分隔符",
    0x200B: "ZWSP 零宽空格",
    0x200C: "ZWNJ 零宽不连字",
    0x200D: "ZWJ 零宽连字",
    0x200E: "LRM 左到右标记",
    0x200F: "RLM 右到左标记",
    0x202A: "LRE 左到右嵌入",
    0x202B: "RLE 右到左嵌入",
    0x202C: "PDF 嵌入结束",
    0x202D: "LRO 左到右覆盖",
    0x202E: "RLO 右到左覆盖",
    0x202F: "NNBSP 窄不换行空格",
    0x2060: "词连接符",
    0x2061: "不可见函数应用符",
    0x2062: "不可见乘号",
    0x2063: "不可见分隔符",
    0x2064: "不可见加号",
    0x2066: "LRI 左到右隔离",
    0x2067: "RLI 右到左隔离",
    0x2068: "FSI 首强隔离",
    0x2069: "PDI 隔离结束",
    0xFEFF: "零宽不换行空格(BOM 残留)",
}


def chars_in_ranges(ranges):
    """把若干码点区间展开成一个字符集合。"""
    out = set()
    for lo, hi in ranges:
        for cp in range(lo, hi + 1):
            out.add(chr(cp))
    return frozenset(out)


DEFAULT_CHARS = chars_in_ranges(DEFAULT_RANGES)


def extra_chars(argv):
    """按命令行开关收集「额外要清」的字符集合。不给开关就是空集。"""
    extra = set()
    for flag, ranges, _why in OPT_IN_RANGES:
        if flag in argv:
            extra |= chars_in_ranges(ranges)
    return frozenset(extra)


def scan(text, extra=frozenset()):
    """统计文本里出现的不可见字符。返回 Counter{字符: 次数}。"""
    bag = DEFAULT_CHARS | extra
    return Counter(ch for ch in text if ch in bag)


def strip_invisible(text, extra=frozenset()):
    """删掉文本里所有不可见字符。

    换行符(\\r \\n)不在名单里,所以 CRLF / LF 不会被改动。
    """
    bag = DEFAULT_CHARS | extra
    return "".join(ch for ch in text if ch not in bag)


def decode(raw):
    """拆掉可能存在的 UTF-8 BOM,返回 (text, had_bom)。

    不是 UTF-8 时返回 (None, None) —— 调用方据此放弃处理,避免破坏文件。
    """
    had_bom = raw.startswith(BOM)
    body = raw[len(BOM):] if had_bom else raw
    try:
        return body.decode("utf-8"), had_bom
    except UnicodeDecodeError:
        return None, None


def strip_text(text):
    """删除文本里所有 [Aegisub Project Garbage] 段。

    从该段标题行开始,删到下一个段标题(以 '[' 开头的行)之前为止 —— 这样
    顺带吃掉该段与下一段之间的那一行空行,不会留下多余空行。其余每一行(连同
    它原本的换行符)逐字保留,因此 CRLF / LF 不会被改动。
    """
    lines = text.splitlines(keepends=True)
    out = []
    i = 0
    n = len(lines)
    while i < n:
        if lines[i].strip() == SECTION:
            i += 1  # 跳过该段标题
            while i < n and not lines[i].lstrip().startswith("["):
                i += 1  # 跳过段内每一行,直到下一个段标题
        else:
            out.append(lines[i])
            i += 1
    return "".join(out)


def strip_bytes(raw):
    """对原始字节做清理,保留可能存在的 UTF-8 BOM。遇到非 UTF-8 内容时,
    为避免破坏文件,原样返回。

    注意:这里只清 [Aegisub Project Garbage] 段,不清不可见字符 ——
    has_section() 靠它来判断「是否存在垃圾段」,不能和字符清理混在一起。
    要连不可见字符一起清,用 scrub_bytes()。
    """
    text, had_bom = decode(raw)
    if text is None:
        return raw
    cleaned = strip_text(text).encode("utf-8")
    return (BOM + cleaned) if had_bom else cleaned


def scrub_bytes(raw, extra=frozenset()):
    """垃圾段 + 不可见字符,一起清。保留可能的 UTF-8 BOM,非 UTF-8 原样返回。"""
    text, had_bom = decode(raw)
    if text is None:
        return raw
    cleaned = strip_invisible(strip_text(text), extra).encode("utf-8")
    return (BOM + cleaned) if had_bom else cleaned


def iter_ass(paths):
    if paths:
        for p in paths:
            yield p
        return
    for root, dirs, files in os.walk("."):
        if ".git" in root.split(os.sep):
            dirs[:] = [d for d in dirs if d != ".git"]
            continue
        for name in files:
            if name.lower().endswith(".ass"):
                yield os.path.join(root, name)


def fix_in_place(path, extra=frozenset()):
    """就地清理一个文件。

    返回 (是否改动过, 不可见字符统计, 是否含垃圾段)。
    非 UTF-8 文件原样跳过,返回 (False, 空统计, False)。
    """
    with open(path, "rb") as f:
        raw = f.read()
    text, _had_bom = decode(raw)
    if text is None:
        return False, Counter(), False
    counts = scan(text, extra)
    had_section = strip_text(text) != text
    cleaned = scrub_bytes(raw, extra)
    if cleaned == raw:
        return False, counts, had_section
    with open(path, "wb") as f:
        f.write(cleaned)
    return True, counts, had_section


def has_section(path):
    with open(path, "rb") as f:
        raw = f.read()
    return strip_bytes(raw) != raw


def scan_file(path, extra=frozenset()):
    """读一个文件,统计里面的不可见字符。非 UTF-8 返回空 Counter。"""
    with open(path, "rb") as f:
        raw = f.read()
    text, _had_bom = decode(raw)
    return scan(text, extra) if text is not None else Counter()


def format_report(counts, had_section):
    """把一次检查的结果排成几行,给人看也方便贴 CI 日志。"""
    lines = []
    if had_section:
        lines.append("  " + SECTION)
    for ch in sorted(counts, key=ord):
        cp = ord(ch)
        lines.append("  U+%04X  %s  x%d" % (cp, CHAR_NAMES.get(cp, "未知"), counts[ch]))
    return lines


def main(argv):
    args = argv[1:]

    if "-h" in args or "--help" in args:
        sys.stdout.write(__doc__)
        return 0

    extra = extra_chars(args)

    if args and args[0] == "--filter":
        sys.stdout.buffer.write(scrub_bytes(sys.stdin.buffer.read(), extra))
        return 0

    # 开关本身不是路径,别拿去当文件找
    paths = [a for a in args if a != "--check" and a not in OPT_IN_FLAGS]

    if "--check" in args:
        bad = []
        for p in iter_ass(paths):
            had_section = has_section(p)
            counts = scan_file(p, extra)
            if had_section or counts:
                bad.append(p)
                print(p)
                for line in format_report(counts, had_section):
                    print(line)
        if bad:
            sys.stderr.write(
                "%d 个文件仍可清理（%s 段 / 不可见字符）\n" % (len(bad), SECTION)
            )
            return 1
        return 0

    changed = 0
    for p in iter_ass(paths):
        ok, counts, had_section = fix_in_place(p, extra)
        if not ok:
            continue
        changed += 1
        print("cleaned: " + p)
        for line in format_report(counts, had_section):
            print(line)
    print("共清理 %d 个文件。" % changed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
