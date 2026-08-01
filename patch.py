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

    if "JSON" in content and "TXTP" in content and "TranscribeOutputFormatEnum" in content:
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


def patch_asr_data(root: Path) -> bool:
    """添加 to_word_json()、to_plain_text()，更新 save()"""
    f = root / "videocaptioner" / "core" / "asr" / "asr_data.py"
    content = f.read_text(encoding="utf-8")

    if "def to_word_json" in content:
        print(f"  [SKIP] {f.name} - already patched")
        return False

    old_save = (
        '        elif save_path.endswith(".json"):\n'
        '            with open(save_path, "w", encoding="utf-8") as f:\n'
        '                json.dump(self.to_json(), f, ensure_ascii=False, indent=2)\n'
        '        elif save_path.endswith(".ass"):'
    )
    new_save = (
        '        elif save_path.endswith(".json"):\n'
        '            with open(save_path, "w", encoding="utf-8") as f:\n'
        '                json.dump(self.to_word_json(), f, ensure_ascii=False, indent=2)\n'
        '        elif save_path.endswith(".txtp"):\n'
        '            with open(save_path, "w", encoding="utf-8") as f:\n'
        '                f.write(self.to_plain_text())\n'
        '        elif save_path.endswith(".ass"):'
    )
    content = content.replace(old_save, new_save)

    insert_after = (
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

    content = content.replace(insert_after, new_methods)

    f.write_text(content, encoding="utf-8")
    print(f"  [OK] {f.name} - added to_word_json(), to_plain_text(), updated save()")
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
    changed |= patch_asr_data(root)

    print()
    if changed:
        print("Done! Restart VideoCaptioner GUI to see JSON and TXTP options.")
    else:
        print("All patches already applied. No changes needed.")


if __name__ == "__main__":
    main()