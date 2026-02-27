# batch-image-renamer
Batch rename image files in a folder with flexible templates (digits + x counters), interactive messy-name filtering, safe two-phase renaming, and undo support — works on Windows/Linux/macOS.

---
````markdown
# Image Batch Renamer (Template + Messy Detection + Undo)

A small, cross-platform Python CLI tool to batch rename image files in a folder **safely**.

It supports:
- **Mainstream image formats** (jpg/jpeg/png/webp/bmp/tif/tiff/heic/heif/gif/avif/jfif)
- **Non-recursive** renaming (only the specified folder)
- **Sort by filename** (stable ordering)
- **Powerful rename templates**:
  - `x` / `xxx` placeholders (shared counter, optional zero-padding)
  - **numeric counters** inside the template (each digit-run increments independently)
  - **mixed digits + x** in one template
  - **fixed blocks** using `[ ... ]` to keep text unchanged (digits inside brackets do NOT increment)
- **Two selection modes**:
  1. Interactive “messy filename” detection + **y/n** prefix confirmation
  2. Explicit `--src-prefix` filtering (rename only files with certain original prefixes)
- **Dry-run preview** (`--dry-run`)
- **Undo** via auto-generated rename logs (`--undo`)

---

## Why this tool?

Some folders contain a mix of:
- clean, meaningful names (often in Chinese) that you do NOT want to touch, and
- messy downloaded names like random tokens, long strings, special symbols, etc.

This tool renames only the files you intend to rename, with:
- safe filtering,
- preview-first workflow,
- collision protection,
- and an undo log.

---

## Requirements

- Python **3.8+**
- No external dependencies (standard library only)

---

## Install

Clone the repo or download `changename.py`, then run in a terminal:

```bash
python changename.py --help
````

---

## Usage

### 1) Preview first (recommended)

```bash
python changename.py --dir "D:/pics" --name "Imagex-FAQx" --dry-run
```

This prints the planned rename mapping without changing anything.

### 2) Apply rename

```bash
python changename.py --dir "D:/pics" --name "Imagex-FAQx"
```

---

## Selection Modes

### Mode A: Interactive “messy name” detection (default)

If you do NOT provide `--src-prefix`, the script will:

1. detect “messy” image names (heuristics),
2. find the most common prefix among them,
3. ask you to confirm with **y/n**,
4. only rename the confirmed group.

```bash
python changename.py --dir "D:/pics" --name "Imagex-FAQx"
```

> By default, filenames containing Chinese characters are **skipped** in this mode (to avoid accidentally renaming clean, meaningful names).
> If you want to include Chinese filenames, add `--include-cjk`.

---

### Mode B: Explicit prefix filtering (non-interactive)

Rename only images whose original filename **starts with** a specific prefix:

```bash
python changename.py --dir "D:/pics" --name "Imagex-FAQx" --src-prefix "NR8"
```

Multiple prefixes (comma-separated):

```bash
python changename.py --dir "D:/pics" --name "Imagex-FAQx" --src-prefix "NR8,IMG_,DSC"
```

If your prefix is Chinese (e.g. `图片9`), add `--include-cjk`:

```bash
python changename.py --dir "D:/pics" --name "图片9-宣传答疑x" --src-prefix "图片9" --include-cjk
```

---

## Template Rules

### A) `x` placeholders (shared counter)

* `x` means a sequence number: 1,2,3...
* `xxx` means zero padded: 001,002,003...
* **All x-runs share the same counter**.

Examples:

```bash
python changename.py --dir "D:/pics" --name "Imagex"
python changename.py --dir "D:/pics" --name "Imagexxx"
python changename.py --dir "D:/pics" --name "Qxx-Axxx"
```

Set the starting value (default is 1):

```bash
python changename.py --dir "D:/pics" --name "Imagex" --start 9
```

---

### B) Numeric counters (digit runs increment independently)

Any digit sequence in the template becomes a counter.

Example:

```bash
python changename.py --dir "D:/pics" --name "Photo3-Reply5"
```

Output:

* Photo3-Reply5
* Photo4-Reply6
* Photo5-Reply7
* ...

Padding is preserved by width:

```bash
python changename.py --dir "D:/pics" --name "Photo003-Reply05"
```

---

### C) Mixed digits + x (supported)

Digits increment independently, `x` increments from `--start`.

Example:

```bash
python changename.py --dir "D:/pics" --name "图片9-宣传答疑x"
```

Output:

* 图片9-宣传答疑1
* 图片10-宣传答疑2
* 图片11-宣传答疑3
* ...

Also works in reverse order:

```bash
python changename.py --dir "D:/pics" --name "图片x-宣传答疑9"
```

---

### D) Fixed blocks `[ ... ]` (do NOT increment inside)

Anything inside brackets is treated as literal text.
Digits inside `[...]` will **not** be parsed as counters, and `x` inside `[...]` is not a placeholder.

Examples:

Fix a year:

```bash
python changename.py --dir "D:/pics" --name "Report[2026]-Imagex"
```

Fix a constant digit group:

```bash
python changename.py --dir "D:/pics" --name "[图片9]-宣传答疑x"
```

Note:

* Brackets are not included in the output name; only the inner text is emitted.

---

## File Extensions

Do **not** include extensions in `--name`.
The script preserves each file’s original extension automatically.

Example:

* input: `something.png`
* output base name: `图片9-宣传答疑1`
* final: `图片9-宣传答疑1.png`

---

## Undo

After a successful rename, the script creates a JSON log in the folder:

`rename_log_YYYYMMDD_HHMMSS.json`

Undo using:

```bash
python changename.py --undo "D:/pics/rename_log_20260227_235959.json"
```

Preview undo (dry-run):

```bash
python changename.py --undo "D:/pics/rename_log_20260227_235959.json" --dry-run
```

---

## Safety Notes

* The script uses a **two-phase rename** (src → temp → dst) to avoid in-place conflicts.
* It will stop if a target filename already exists **outside** the current rename set (to prevent accidental overwrite).
* Always run with `--dry-run` first for important folders.

---

## Supported Platforms

* Windows (PowerShell / CMD)
* macOS (Terminal)
* Linux (Terminal)

---
