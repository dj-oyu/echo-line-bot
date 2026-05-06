import os
import sys
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from markdown_to_line import (  # noqa: E402
    format_with_citations,
    merge_citations,
    render_to_line,
)


class TestRenderToLine(unittest.TestCase):
    def test_empty(self) -> None:
        self.assertEqual(render_to_line(""), ("", []))

    def test_plain_paragraph_unchanged(self) -> None:
        text, urls = render_to_line("こんにちは。元気ですか？")
        self.assertEqual(text, "こんにちは。元気ですか？")
        self.assertEqual(urls, [])

    def test_strong_stripped(self) -> None:
        text, _ = render_to_line("これは **重要** な点です。")
        self.assertEqual(text, "これは 重要 な点です。")

    def test_em_stripped(self) -> None:
        text, _ = render_to_line("これは *斜体* の例。")
        self.assertEqual(text, "これは 斜体 の例。")

    def test_strikethrough_passthrough(self) -> None:
        # commonmark preset does not parse ~~ as strikethrough; treat as text.
        text, _ = render_to_line("~~消去~~ もそのまま")
        self.assertIn("消去", text)

    def test_inline_code_wrapped(self) -> None:
        text, _ = render_to_line("ファイル名は `config.json` です。")
        self.assertEqual(text, "ファイル名は 〈config.json〉 です。")

    def test_heading_levels_flattened(self) -> None:
        text, _ = render_to_line("# 章タイトル\n## 節\n### 小見出し\n本文")
        self.assertIn("■ 章タイトル", text)
        self.assertIn("■ 節", text)
        self.assertIn("■ 小見出し", text)

    def test_bullet_list(self) -> None:
        text, _ = render_to_line("- 一つ目\n- 二つ目\n- 三つ目")
        lines = [line for line in text.split("\n") if line]
        self.assertEqual(lines, ["・一つ目", "・二つ目", "・三つ目"])

    def test_nested_bullet_list_indented(self) -> None:
        md = "- 親\n  - 子1\n  - 子2\n- 別の親"
        text, _ = render_to_line(md)
        self.assertIn("・親", text)
        self.assertIn("  ・子1", text)
        self.assertIn("  ・子2", text)
        self.assertIn("・別の親", text)

    def test_ordered_list_numbered(self) -> None:
        text, _ = render_to_line("1. 最初\n2. 次\n3. 最後")
        self.assertIn("1. 最初", text)
        self.assertIn("2. 次", text)
        self.assertIn("3. 最後", text)

    def test_link_extracts_url_keeps_text(self) -> None:
        text, urls = render_to_line("詳細は [公式サイト](https://example.com) を参照。")
        self.assertEqual(text, "詳細は 公式サイト を参照。")
        self.assertEqual(urls, ["https://example.com"])

    def test_multiple_links_dedup_and_order(self) -> None:
        md = "[A](https://a.example) と [B](https://b.example) と [A again](https://a.example)"
        text, urls = render_to_line(md)
        self.assertNotIn("https://a.example", text)
        self.assertNotIn("https://b.example", text)
        self.assertEqual(urls, ["https://a.example", "https://b.example"])

    def test_non_http_link_skipped(self) -> None:
        _, urls = render_to_line("[mailto](mailto:foo@example.com)")
        self.assertEqual(urls, [])

    def test_code_block_preserved(self) -> None:
        md = "```\nprint('hi')\n```"
        text, _ = render_to_line(md)
        self.assertIn("print('hi')", text)

    def test_blockquote_prefixed(self) -> None:
        text, _ = render_to_line("> 引用された一行\n> 二行目")
        for line in text.strip().split("\n"):
            if line:
                self.assertTrue(line.startswith("｜"), f"unexpected line: {line!r}")

    def test_hr_emitted(self) -> None:
        text, _ = render_to_line("前\n\n---\n\n後")
        self.assertIn("────", text)

    def test_no_excessive_blank_lines(self) -> None:
        md = "段落1\n\n\n\n\n段落2"
        text, _ = render_to_line(md)
        self.assertNotIn("\n\n\n", text)

    def test_strong_with_japanese_punctuation_inside(self) -> None:
        # CommonMark flanking rule rejects `」**` followed by CJK letter; ensure
        # our residual-emphasis sweep cleans it up regardless.
        text, _ = render_to_line("**「テスト」**です")
        self.assertEqual(text, "「テスト」です")

    def test_strong_with_punctuation_boundary_variants(self) -> None:
        cases = [
            ("**「テスト」**", "「テスト」"),
            ("**これは「テスト」**", "これは「テスト」"),
            ("**テスト「重要」**", "テスト「重要」"),
            ("**1. テスト**", "1. テスト"),
            ("「**強調**」", "「強調」"),
            ("日本語**bold**日本語", "日本語bold日本語"),
            ("文末を**強調**。", "文末を強調。"),
        ]
        for src, expected in cases:
            with self.subTest(src=src):
                text, _ = render_to_line(src)
                self.assertEqual(text, expected)

    def test_em_with_punctuation_boundary(self) -> None:
        text, _ = render_to_line("これは*斜体*です")
        self.assertEqual(text, "これは斜体です")

    def test_residual_sweep_does_not_touch_code_block(self) -> None:
        md = "```\nuse **literal** in code\n```"
        text, _ = render_to_line(md)
        self.assertIn("**literal**", text)

    def test_residual_sweep_does_not_touch_inline_code(self) -> None:
        text, _ = render_to_line("使い方: `**raw**` のように書く")
        self.assertIn("〈**raw**〉", text)

    def test_unpaired_asterisks_left_alone(self) -> None:
        text, _ = render_to_line("計算: 2 ** 3 = 8")
        self.assertIn("**", text)

    def test_complex_mixed_document(self) -> None:
        md = (
            "# まとめ\n\n"
            "**結論**: AはBより速い。\n\n"
            "## 根拠\n\n"
            "- 計測した結果が [ベンチマーク](https://bench.example) に記載\n"
            "- 公式 `documentation` でも触れられている\n\n"
            "> なお例外あり。\n"
        )
        text, urls = render_to_line(md)
        self.assertIn("■ まとめ", text)
        self.assertIn("■ 根拠", text)
        self.assertIn("結論: AはBより速い。", text)
        self.assertIn("・計測した結果が ベンチマーク に記載", text)
        self.assertIn("〈documentation〉", text)
        self.assertTrue(any("｜" in line for line in text.split("\n")))
        self.assertEqual(urls, ["https://bench.example"])


class TestMergeCitations(unittest.TestCase):
    def test_dedup_preserves_first_occurrence_order(self) -> None:
        merged = merge_citations(
            ["https://a", "https://b"], ["https://b", "https://c", "https://a"]
        )
        self.assertEqual(merged, ["https://a", "https://b", "https://c"])

    def test_skips_empty(self) -> None:
        merged = merge_citations(["", "https://a"], ["", None])  # type: ignore[list-item]
        self.assertEqual(merged, ["https://a"])

    def test_empty_input(self) -> None:
        self.assertEqual(merge_citations(), [])
        self.assertEqual(merge_citations([], []), [])


class TestFormatWithCitations(unittest.TestCase):
    def test_no_citations_unchanged(self) -> None:
        self.assertEqual(format_with_citations("body", []), "body")

    def test_citations_appended_with_header(self) -> None:
        out = format_with_citations("body", ["https://a", "https://b"])
        self.assertEqual(out, "body\n\n🔗 参考\n(1) https://a\n(2) https://b")

    def test_caps_at_max(self) -> None:
        urls = [f"https://x{i}" for i in range(10)]
        out = format_with_citations("body", urls, max_citations=3)
        self.assertIn("(1) https://x0", out)
        self.assertIn("(3) https://x2", out)
        self.assertNotIn("(4)", out)
        self.assertNotIn("https://x3", out)


if __name__ == "__main__":
    unittest.main()
