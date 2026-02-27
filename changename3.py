#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Dict, Optional, Union


IMAGE_EXTS = {
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff",
    ".heic", ".heif", ".gif", ".avif", ".jfif"
}


def contains_cjk(s: str) -> bool:
    for ch in s:
        code = ord(ch)
        if (0x4E00 <= code <= 0x9FFF) or (0x3400 <= code <= 0x4DBF) or (0xF900 <= code <= 0xFAFF):
            return True
    return False


def is_image(p: Path) -> bool:
    return p.is_file() and p.suffix.lower() in IMAGE_EXTS


def parse_prefixes(raw: str) -> List[str]:
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


def match_any_prefix(stem: str, prefixes: List[str]) -> bool:
    if not prefixes:
        return True
    return any(stem.startswith(pref) for pref in prefixes)


def is_messy_name(stem: str) -> bool:
    if not stem:
        return False

    if len(stem) >= 24:
        return True

    weird_symbols = set("!*=+@#$%^&()[]{};,'`~<>|\\")
    if any(c in weird_symbols for c in stem):
        return True

    common_seps = set("_-. ")
    non_alnum = sum(1 for c in stem if (not c.isalnum()) and (c not in common_seps))
    if non_alnum >= 3:
        return True

    has_sep = any(c in stem for c in "_-. ")
    if (not has_sep) and len(stem) >= 18:
        has_digit = any(c.isdigit() for c in stem)
        has_alpha = any(c.isalpha() for c in stem)
        if has_digit and has_alpha:
            return True

    return False


# ---------------- Template tokenization & rendering ----------------
# Segment types:
# ("lit", text)           literal text
# ("x", width)            x-run counter (shared)
# ("d", width, start_val) digit-run counter (per-run)
Segment = Union[
    Tuple[str, str],
    Tuple[str, int],
    Tuple[str, int, int],
]


def tokenize_template(tpl: str) -> List[Segment]:
    """
    New rule:
      - Anything inside [ ... ] is forced literal ("lit", text), even if it contains digits or x.
      - Brackets are NOT kept in output (only inner text is output).
    Existing rules:
      - Runs of x/X -> ("x", width)
      - Runs of digits -> ("d", width, start_value)
      - Others -> ("lit", text)
    """
    segs: List[Segment] = []
    i = 0
    n = len(tpl)

    while i < n:
        ch = tpl[i]

        # [ ... ] forced literal
        if ch == "[":
            j = tpl.find("]", i + 1)
            if j == -1:
                raise SystemExit("错误：模板中出现 '[' 但没有匹配的 ']'。请检查 --name。")
            inner = tpl[i + 1: j]  # drop brackets
            segs.append(("lit", inner))
            i = j + 1
            continue

        # x-run
        if ch in ("x", "X"):
            j = i
            while j < n and tpl[j] in ("x", "X"):
                j += 1
            width = j - i
            segs.append(("x", width))
            i = j
            continue

        # digit-run
        if ch.isdigit():
            j = i
            while j < n and tpl[j].isdigit():
                j += 1
            run = tpl[i:j]
            width = j - i
            segs.append(("d", width, int(run)))
            i = j
            continue

        # literal (stop also on '[' now)
        j = i + 1
        while j < n and (not tpl[j].isdigit()) and (tpl[j] not in ("x", "X")) and (tpl[j] != "["):
            j += 1
        segs.append(("lit", tpl[i:j]))
        i = j

    return segs


def render_from_segments(segs: List[Segment], x_val: int, d_vals: List[int]) -> str:
    out: List[str] = []
    d_idx = 0
    for seg in segs:
        if seg[0] == "lit":
            out.append(seg[1])
        elif seg[0] == "x":
            width = seg[1]
            out.append(str(x_val).zfill(width) if width > 1 else str(x_val))
        elif seg[0] == "d":
            width = seg[1]
            cur = d_vals[d_idx]
            out.append(str(cur).zfill(width) if width > 1 else str(cur))
            d_idx += 1
        else:
            raise RuntimeError(f"Unknown segment: {seg}")
    return "".join(out)


def count_d_segments(segs: List[Segment]) -> int:
    return sum(1 for s in segs if s[0] == "d")


def has_x_segment(segs: List[Segment]) -> bool:
    return any(s[0] == "x" for s in segs)


def init_d_counters(segs: List[Segment]) -> List[int]:
    return [s[2] for s in segs if s[0] == "d"]


# ---------------- Rename safety ----------------
def ensure_no_collisions(pairs: List[Tuple[Path, Path]]) -> None:
    targets = [dst.name for _, dst in pairs]
    if len(set(targets)) != len(targets):
        raise SystemExit("错误：目标文件名重复（collision）。请调整模板/补零位数/起始编号。")

    src_set = {src.resolve() for src, _ in pairs}
    for _, dst in pairs:
        if dst.exists() and dst.resolve() not in src_set:
            raise SystemExit(f"错误：目标文件已存在且不在本次重命名源列表中：{dst.name}")


def two_phase_rename(pairs: List[Tuple[Path, Path]], dry_run: bool) -> List[Dict[str, str]]:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_suffix = f".__tmp_rename__{stamp}__"

    mapping = [{"src": str(src), "dst": str(dst)} for src, dst in pairs]
    if dry_run:
        return mapping

    phase1 = [(src, src.with_name(src.name + temp_suffix)) for src, _ in pairs]
    phase2 = [(src.with_name(src.name + temp_suffix), dst) for src, dst in pairs]

    for src, tmp in phase1:
        src.rename(tmp)
    for tmp, dst in phase2:
        tmp.rename(dst)

    return mapping


def save_log(folder: Path, mapping: List[Dict[str, str]]) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = folder / f"rename_log_{ts}.json"
    payload = {"created_at": datetime.now().isoformat(timespec="seconds"), "pairs": mapping}
    log_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return log_path


def undo(log_file: Path, dry_run: bool) -> None:
    data = json.loads(log_file.read_text(encoding="utf-8"))
    pairs = data["pairs"]
    ops = [(Path(item["dst"]), Path(item["src"])) for item in reversed(pairs)]

    for frm, to in ops:
        if not frm.exists():
            raise SystemExit(f"撤销失败：找不到 {frm}")
        if to.exists() and to != frm:
            raise SystemExit(f"撤销失败：目标已存在 {to}")

    if dry_run:
        for frm, to in ops:
            print(f"[DRY] {frm.name} -> {to.name}")
        return

    for frm, to in ops:
        frm.rename(to)


# ---------------- Interactive prefix selection ----------------
def suggest_prefixes(stems: List[str], k: int, topn: int = 10) -> List[Tuple[str, int]]:
    pref_counts = Counter([s[:k] for s in stems if len(s) >= k])
    return pref_counts.most_common(topn)


def interactive_choose_prefix(messy_files: List[Path], k: int) -> Optional[str]:
    stems = [p.stem for p in messy_files]
    if not stems:
        return None

    suggestions = suggest_prefixes(stems, k=k, topn=10)
    if not suggestions:
        return None

    best_pref, best_cnt = suggestions[0]
    print(f"\n检测到 {len(messy_files)} 个“疑似乱名”的图片。")
    print(f"最常见前缀（取前 {k} 个字符）是：'{best_pref}'（{best_cnt} 个文件）")

    example = [p.name for p in messy_files if p.stem.startswith(best_pref)][:5]
    print("示例：")
    for e in example:
        print(f"  - {e}")

    while True:
        ans = input(f"\n是否只重命名前缀为 '{best_pref}' 的这些文件？[y/n] ").strip().lower()
        if ans == "y":
            return best_pref
        if ans == "n":
            print("\n不会改名。你可以：")
            print("1) 输入序号选一个前缀；2) 直接输入前缀字符串；3) 输入 q 退出。\n")
            for i, (pfx, cnt) in enumerate(suggestions, 1):
                print(f"  {i}. {pfx}  ({cnt})")
            choice = input("\n请输入序号/前缀/q： ").strip()
            if choice.lower() == "q":
                return None
            if choice.isdigit():
                idx = int(choice)
                if 1 <= idx <= len(suggestions):
                    cand = suggestions[idx - 1][0]
                    ex2 = [p.name for p in messy_files if p.stem.startswith(cand)][:5]
                    print(f"\n你选择了 '{cand}'，示例：")
                    for e in ex2:
                        print(f"  - {e}")
                    if input(f"确认使用前缀 '{cand}'？[y/n] ").strip().lower() == "y":
                        return cand
                    continue
                print("序号不合法。")
                continue
            else:
                cand = choice
                if not cand:
                    print("空输入无效。")
                    continue
                ex3 = [p.name for p in messy_files if p.stem.startswith(cand)][:5]
                if not ex3:
                    print(f"没有文件匹配前缀 '{cand}'。")
                    continue
                print(f"\n匹配示例：")
                for e in ex3:
                    print(f"  - {e}")
                if input(f"确认使用前缀 '{cand}'？[y/n] ").strip().lower() == "y":
                    return cand
                continue
        print("请输入 y 或 n。")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=".", help="要重命名的文件夹（默认当前目录）")
    ap.add_argument("--name", required=False, help="命名模板（支持数字段 + x 段 + [固定文本]；不要写后缀）")
    ap.add_argument("--start", type=int, default=1, help="x 段起始编号（不指定则默认 1）")
    ap.add_argument("--src-prefix", default="", help="（可选）只重命名原文件名以这些前缀开头的文件（逗号分隔）")
    ap.add_argument("--prefix-len", type=int, default=3, help="交互模式下用于统计候选前缀长度（默认3）")
    ap.add_argument("--include-cjk", action="store_true", help="默认跳过含中文文件名；加此参数则允许中文也参与筛选")
    ap.add_argument("--dry-run", action="store_true", help="只预览不改名")
    ap.add_argument("--undo", default="", help="用日志 json 撤销上一次改名")
    args = ap.parse_args()

    if args.undo:
        undo(Path(args.undo).expanduser().resolve(), dry_run=args.dry_run)
        print("Done." if not args.dry_run else "Dry-run done.")
        return

    if not args.name:
        raise SystemExit("错误：必须提供 --name 模板。")

    folder = Path(args.dir).expanduser().resolve()
    if not folder.exists() or not folder.is_dir():
        raise SystemExit(f"错误：文件夹不存在：{folder}")

    images = [p for p in folder.iterdir() if is_image(p)]
    images.sort(key=lambda p: p.name.lower())

    if not images:
        print("该文件夹下没有匹配的图片文件。")
        return

    prefixes = parse_prefixes(args.src_prefix)

    # candidate selection
    if prefixes:
        candidates = []
        for p in images:
            stem = p.stem
            if not match_any_prefix(stem, prefixes):
                continue
            if (not args.include_cjk) and contains_cjk(stem):
                continue
            candidates.append(p)
        if not candidates:
            print("没有匹配到需要重命名的图片（可能前缀不对/被中文跳过规则过滤）。")
            return
    else:
        messy = []
        for p in images:
            stem = p.stem
            if (not args.include_cjk) and contains_cjk(stem):
                continue
            if is_messy_name(stem):
                messy.append(p)

        if not messy:
            print("没有检测到“疑似乱名”的图片（或都被中文跳过规则排除了）。")
            print("如果你想强制只改某个前缀，请用 --src-prefix。")
            return

        chosen = interactive_choose_prefix(messy, k=max(1, args.prefix_len))
        if not chosen:
            print("未确认任何前缀，本次不会改名。")
            return
        candidates = [p for p in messy if p.stem.startswith(chosen)]

    # template parse (supports [fixed text])
    segs = tokenize_template(args.name)
    d_counters = init_d_counters(segs)      # per digit-run
    x_counter = args.start                  # shared x counter
    use_x = has_x_segment(segs)
    d_count = count_d_segments(segs)

    if (not use_x) and d_count == 0:
        raise SystemExit("错误：模板里既没有 x，也没有数字（或都被 [] 包裹了）。")

    pairs: List[Tuple[Path, Path]] = []
    for p in candidates:
        base = render_from_segments(segs, x_counter, d_counters)
        pairs.append((p, p.with_name(base + p.suffix)))

        if use_x:
            x_counter += 1
        if d_count > 0:
            d_counters = [v + 1 for v in d_counters]

    ensure_no_collisions(pairs)

    print("\n改名预览（前 30 个）：")
    for src, dst in pairs[:30]:
        print(f"{src.name} -> {dst.name}")
    if len(pairs) > 30:
        print(f"... ({len(pairs)} files total)")

    mapping = two_phase_rename(pairs, dry_run=args.dry_run)
    if args.dry_run:
        print("\nDry-run done. No files were renamed.")
        return

    log_path = save_log(folder, mapping)
    print(f"\nRenamed {len(pairs)} files.")
    print(f"Log saved: {log_path}")


if __name__ == "__main__":
    main()