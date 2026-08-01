"""
VideoCaptioner 字幕格式增强补丁
在输出格式下拉菜单中添加 JSON（词级时间戳）和 TXTP（纯文本）选项

用法: python patch.py
放在 VideoCaptioner 项目根目录下运行
"""
import re
from pathlib import Path


def patch_entities(root: Path) -> bool:
    """在 TranscribeOutputFormatEnum 中添加 JSON 和 TXTP"""
    f = root / "videocaptioner" / "core" / "entities.py"
    content = f.read_text(encoding="utf-8")

    if 'JSON = "JSON"' in content and 'TXTP = "TXTP"' in content:
        print(f"  [SKIP] {f.name} - already patched")
        return False

    content = content.replace(
        '    TXT = "TXT"\n    ALL = "All"',
        '    TXT = "TXT"\n    JSON = "JSON"\n    TXTP = "TXTP"\n    ALL = "All"',
    )
    f.write_text(content, encoding="utf-8")
    print(f"  [OK] {f.name} - added JSON, TXTP to TranscribeOutputFormatEnum")
    return True


def patch_task_factory(root: Path) -> bool:
    """JSON/TXTP 格式时强制开启词级时间戳"""
    f = root / "videocaptioner" / "ui" / "task_factory.py"
    content = f.read_text(encoding="utf-8")

    if "TranscribeOutputFormatEnum.JSON" in content:
        print(f"  [SKIP] {f.name} - already patched")
        return False

    content = content.replace(
        "    TranscribeConfig,\n    TranscribeTask,",
        "    TranscribeConfig,\n    TranscribeOutputFormatEnum,\n    TranscribeTask,",
    )

    old_block = (
        "        # 构建输出路径\n"
        "        if need_next_task:\n"
        "            need_word_time_stamp = cfg.need_split.value\n"
        "            output_path = str(\n"
        "                Path(cfg.work_dir.value)\n"
        "                / file_name\n"
        '                / "subtitle"\n'
        '                / f"【原始字幕】{file_name}-{cfg.transcribe_model.value.value}-{cfg.transcribe_language.value.value}.srt"\n'
        "            )\n"
        "        else:\n"
        "            need_word_time_stamp = False\n"
        '            output_path = str(Path(file_path).parent / f"{file_name}.srt")'
    )
    new_block = (
        "        # JSON/TXTP 格式需要词级时间戳\n"
        "        output_format = cfg.transcribe_output_format.value\n"
        "        if output_format in (TranscribeOutputFormatEnum.JSON, TranscribeOutputFormatEnum.TXTP):\n"
        "            need_word_time_stamp = True\n"
        "        elif need_next_task:\n"
        "            need_word_time_stamp = cfg.need_split.value\n"
        "        else:\n"
        "            need_word_time_stamp = False\n"
        "\n"
        "        # 构建输出路径\n"
        "        if need_next_task:\n"
        "            output_path = str(\n"
        "                Path(cfg.work_dir.value)\n"
        "                / file_name\n"
        '                / "subtitle"\n'
        '                / f"【原始字幕】{file_name}-{cfg.transcribe_model.value.value}-{cfg.transcribe_language.value.value}.srt"\n'
        "            )\n"
        "        else:\n"
        '            output_path = str(Path(file_path).parent / f"{file_name}.srt")'
    )
    content = content.replace(old_block, new_block)

    f.write_text(content, encoding="utf-8")
    print(f"  [OK] {f.name} - JSON/TXTP forces need_word_time_stamp=True")
    return True


def patch_transcript_thread(root: Path) -> bool:
    """TXTP 格式导出时使用 .txt 后缀（Windows 兼容）"""
    f = root / "videocaptioner" / "ui" / "thread" / "transcript_thread.py"
    content = f.read_text(encoding="utf-8")

    if "FORMAT_EXT_MAP" in content:
        print(f"  [SKIP] {f.name} - already patched")
        return False

    old_import = (
        "from videocaptioner.core.entities import TranscribeOutputFormatEnum, TranscribeTask\n"
    )
    new_import = (
        "from videocaptioner.core.entities import TranscribeOutputFormatEnum, TranscribeTask\n"
        "\n"
        "# GUI 显示名 vs 实际文件扩展名\n"
        "# TXTP 在 GUI 中用于区分纯文本和带时间戳的 TXT，但导出时用 .txt 后缀\n"
        "FORMAT_EXT_MAP = {\n"
        '    "txtp": "txt",\n'
        "}\n"
    )
    content = content.replace(old_import, new_import)

    old_line = '                save_path = f"{base_path}.{fmt}"'
    new_line = '                ext = FORMAT_EXT_MAP.get(fmt, fmt)\n                save_path = f"{base_path}.{ext}"'
    content = content.replace(old_line, new_line)

    old_save_call = "                asr_data.save(save_path)"
    new_save_call = "                asr_data.save(save_path, output_format=output_format_enum)"
    content = content.replace(old_save_call, new_save_call)

    f.write_text(content, encoding="utf-8")
    print(f"  [OK] {f.name} - TXTP exports as .txt, passes format to save()")
    return True


def patch_asr_data(root: Path) -> bool:
    """添加 to_word_json()、to_plain_text()，更新 save() 支持 format 参数"""
    f = root / "videocaptioner" / "core" / "asr" / "asr_data.py"
    content = f.read_text(encoding="utf-8")

    if "def to_word_json" in content:
        print(f"  [SKIP] {f.name} - already patched (to_word_json exists)")
        return False

    # Step 1: 更新 save() 签名，添加 output_format 参数
    if "output_format" not in content.split("def save(")[1].split("\n    def ")[0]:
        old_sig = (
            "    def save(\n"
            "        self,\n"
            "        save_path: str,\n"
            "        ass_style: Optional[str] = None,\n"
            "        layout: SubtitleLayoutEnum = SubtitleLayoutEnum.ORIGINAL_ON_TOP,\n"
            "    ) -> None:"
        )
        new_sig = (
            "    def save(\n"
            "        self,\n"
            "        save_path: str,\n"
            "        ass_style: Optional[str] = None,\n"
            "        layout: SubtitleLayoutEnum = SubtitleLayoutEnum.ORIGINAL_ON_TOP,\n"
            '        output_format: Optional["TranscribeOutputFormatEnum"] = None,\n'
            "    ) -> None:"
        )
        content = content.replace(old_sig, new_sig)

    # Step 2: 在 save() 方法体开头插入 output_format 优先判断
    # 使用正则匹配 save() 方法中 handle_long_path 之前的区域
    if "output_format == TranscribeOutputFormatEnum" not in content:
        # 找到 save() 方法中的 "save_path = handle_long_path(save_path)" 这行
        # 在它前面插入 format 判断逻辑
        # 使用正则来确保精确匹配 save() 方法中的那行
        pattern = r'(    def save\(.*?\) -> None:.*?)(        save_path = handle_long_path\(save_path\))'
        replacement = (
            r'\1'
            "        # output_format 优先：TXTP -> 纯文本, JSON -> 词级JSON\n"
            "        if output_format is not None:\n"
            "            from videocaptioner.core.entities import TranscribeOutputFormatEnum\n"
            "            Path(save_path).parent.mkdir(parents=True, exist_ok=True)\n"
            "            save_path = handle_long_path(save_path)\n"
            "            if output_format == TranscribeOutputFormatEnum.TXTP:\n"
            '                with open(save_path, "w", encoding="utf-8") as f:\n'
            "                    f.write(self.to_plain_text())\n"
            "                return\n"
            "            elif output_format == TranscribeOutputFormatEnum.JSON:\n"
            '                with open(save_path, "w", encoding="utf-8") as f:\n'
            "                    json.dump(self.to_word_json(), f, ensure_ascii=False, indent=2)\n"
            "                return\n"
            "\n"
            r'\2'
        )
        content, n = re.subn(pattern, replacement, content, flags=re.DOTALL, count=1)
        if n == 0:
            print(f"  [WARN] {f.name} - could not find save() method body to patch")
            return False

    # Step 3: 添加 to_word_json() 和 to_plain_text() 方法
    insert_marker = (
        "            }\n"
        "        return result_json\n"
        "\n"
        "    def to_ass("
    )

    new_methods = (
        "            }\n"
        "        return result_json\n"
        "\n"
        "    def to_word_json(self) -> dict:\n"
        '        """Convert to word-level timestamp JSON format.\n'
        "\n"
        "        Each word/character has independent start/end times.\n"
        "        If data is sentence-level, splits into word-level first.\n"
        "\n"
        "        Returns:\n"
        "            dict with word-level segments\n"
        '        """\n'
        "        if not self.is_word_timestamp():\n"
        "            word_data = ASRData(\n"
        "                [ASRDataSeg(s.text, s.start_time, s.end_time, s.translated_text) for s in self.segments]\n"
        "            )\n"
        "            word_data.split_to_word_segments()\n"
        "        else:\n"
        "            word_data = self\n"
        "\n"
        "        segments = []\n"
        "        for seg in word_data.segments:\n"
        "            text = seg.text.strip()\n"
        "            if not text:\n"
        "                continue\n"
        "            segments.append({\n"
        '                "text": text,\n'
        '                "start": round(seg.start_time / 1000, 3),\n'
        '                "end": round(seg.end_time / 1000, 3),\n'
        '                "start_ms": seg.start_time,\n'
        '                "end_ms": seg.end_time,\n'
        "            })\n"
        "\n"
        "        return {\n"
        '            "mode": "word",\n'
        '            "total_duration_ms": segments[-1]["end_ms"] if segments else 0,\n'
        '            "segments": segments,\n'
        "        }\n"
        "\n"
        "    def to_plain_text(self) -> str:\n"
        '        """Convert to plain text (verbatim transcript without timestamps).\n'
        "\n"
        "        Groups word-level segments into sentences, then outputs clean text.\n"
        "\n"
        "        Returns:\n"
        "            str: plain text content\n"
        '        """\n'
        "        if not self.is_word_timestamp():\n"
        '            return "\\n".join(seg.text.strip() for seg in self.segments if seg.text.strip())\n'
        "\n"
        "        GAP_THRESHOLD = 500\n"
        "        sentences = []\n"
        '        current_text = ""\n'
        "        current_end = 0\n"
        "\n"
        "        for seg in self.segments:\n"
        "            text = seg.text.strip()\n"
        "            if not text:\n"
        "                continue\n"
        "            gap = seg.start_time - current_end\n"
        "            if gap > GAP_THRESHOLD and current_text:\n"
        "                sentences.append(current_text)\n"
        "                current_text = text\n"
        "            else:\n"
        "                current_text += text\n"
        "            current_end = seg.end_time\n"
        "\n"
        "        if current_text:\n"
        "            sentences.append(current_text)\n"
        "\n"
        '        return "\\n".join(sentences)\n'
        "\n"
        "    def to_ass("
    )

    if insert_marker in content:
        content = content.replace(insert_marker, new_methods)
    else:
        print(f"  [WARN] {f.name} - could not find insert point for to_word_json/to_plain_text")
        return False

    f.write_text(content, encoding="utf-8")
    print(f"  [OK] {f.name} - added to_word_json(), to_plain_text(), updated save() with format param")
    return True


def main():
    import sys

    root = Path(__file__).parent
    if not (root / "videocaptioner").exists():
        root = Path.cwd()
        if not (root / "videocaptioner").exists():
            print("ERROR: videocaptioner/ not found.")
            print("Place this script in the VideoCaptioner project root and run it there.")
            sys.exit(1)

    print(f"Project root: {root}")
    print()
    print("Applying patches...")
    print()

    changed = False
    changed |= patch_entities(root)
    changed |= patch_task_factory(root)
    changed |= patch_transcript_thread(root)
    changed |= patch_asr_data(root)

    print()
    if changed:
        print("Done! Restart VideoCaptioner GUI to see JSON and TXTP options.")
    else:
        print("All patches already applied. No changes needed.")


if __name__ == "__main__":
    main()
