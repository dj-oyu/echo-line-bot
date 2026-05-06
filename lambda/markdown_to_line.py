"""Convert markdown text to LINE-friendly plain text.

LINE のテキストメッセージは markdown 装飾を表示できないため、
共通処理として AST ベースで装飾を除去し、リンクの URL を抽出する。

`render_to_line(text)` が中心の関数。装飾の除去ルールは LINE/日本語環境を想定:

- heading       → `■ {text}` （階層はフラット化）
- strong/em/del → 装飾のみ除去、本文はそのまま
- code inline   → `〈{text}〉`
- code block    → 改行を保ったままそのまま
- bullet list   → 行頭 `・`、ネストはインデント2スペース
- ordered list  → `{N}. `
- link          → 本文に表示テキストのみ残し、URL は呼び出し側に返す
- blockquote    → 各行を `｜ ` で前置
- hr            → `────`
"""

from __future__ import annotations

import re

from markdown_it import MarkdownIt
from markdown_it.token import Token


def render_to_line(text: str) -> tuple[str, list[str]]:
    """Render markdown text to LINE plain text.

    Args:
        text: Source markdown text.

    Returns:
        Tuple of `(plain_text, urls)` where `plain_text` has all semantic
        decorations stripped and markdown link URLs removed, and `urls` is the
        list of href values from markdown links in document order, deduplicated.
    """
    if not text:
        return "", []

    md = MarkdownIt("commonmark")
    tokens = md.parse(text)
    rendered, urls = _render_tokens(tokens)

    rendered = re.sub(r"\n{3,}", "\n\n", rendered).strip()

    seen: dict[str, None] = {}
    for u in urls:
        if u:
            seen.setdefault(u, None)
    return rendered, list(seen)


def merge_citations(*sources: list[str]) -> list[str]:
    """Merge citation URL lists preserving input order, deduplicated."""
    seen: dict[str, None] = {}
    for source in sources:
        for url in source:
            if url:
                seen.setdefault(url, None)
    return list(seen)


def format_with_citations(body: str, citations: list[str], max_citations: int = 5) -> str:
    """Append a numbered citation footer to body. No-op if citations empty."""
    if not citations:
        return body
    capped = citations[:max_citations]
    lines = ["🔗 参考"]
    for i, url in enumerate(capped, 1):
        lines.append(f"({i}) {url}")
    return body + "\n\n" + "\n".join(lines)


def _render_tokens(tokens: list[Token]) -> tuple[str, list[str]]:
    # buffer_stack[-1] is the active output buffer; blockquote pushes a new one
    # so its accumulated content can be prefixed at close time.
    buffer_stack: list[list[str]] = [[]]
    urls: list[str] = []
    list_stack: list[dict] = []

    def emit(s: str) -> None:
        buffer_stack[-1].append(s)

    for tok in tokens:
        t = tok.type
        if t == "heading_open":
            emit("\n■ ")
        elif t == "heading_close":
            emit("\n\n")
        elif t == "paragraph_open":
            pass
        elif t == "paragraph_close":
            emit("\n" if list_stack else "\n\n")
        elif t == "bullet_list_open":
            list_stack.append({"type": "ul", "counter": 0})
            emit("\n")
        elif t == "ordered_list_open":
            list_stack.append({"type": "ol", "counter": 1})
            emit("\n")
        elif t in ("bullet_list_close", "ordered_list_close"):
            if list_stack:
                list_stack.pop()
            emit("\n")
        elif t == "list_item_open":
            indent = "  " * max(0, len(list_stack) - 1)
            if list_stack and list_stack[-1]["type"] == "ol":
                n = list_stack[-1]["counter"]
                emit(f"{indent}{n}. ")
                list_stack[-1]["counter"] = n + 1
            else:
                emit(f"{indent}・")
        elif t == "list_item_close":
            pass
        elif t == "blockquote_open":
            buffer_stack.append([])
        elif t == "blockquote_close":
            inner = "".join(buffer_stack.pop()).strip("\n")
            quoted = "\n".join(f"｜ {line}" if line else "｜" for line in inner.split("\n"))
            emit("\n" + quoted + "\n\n")
        elif t == "hr":
            emit("\n────\n")
        elif t in ("code_block", "fence"):
            emit("\n" + tok.content.rstrip("\n") + "\n\n")
        elif t == "inline":
            inline_text, inline_urls = _render_inline(tok.children or [])
            emit(inline_text)
            urls.extend(inline_urls)

    return "".join(buffer_stack[0]), urls


def _render_inline(children: list[Token]) -> tuple[str, list[str]]:
    out: list[str] = []
    urls: list[str] = []
    href_stack: list[str] = []

    for c in children:
        t = c.type
        if t == "text":
            out.append(_strip_residual_emphasis(c.content))
        elif t in ("softbreak", "hardbreak"):
            out.append("\n")
        elif t == "code_inline":
            out.append(f"〈{c.content}〉")
        elif t in (
            "strong_open",
            "strong_close",
            "em_open",
            "em_close",
            "s_open",
            "s_close",
        ):
            pass
        elif t == "link_open":
            href = c.attrGet("href") or ""
            href_stack.append(str(href))
        elif t == "link_close":
            if href_stack:
                href = href_stack.pop()
                if href and href.startswith(("http://", "https://")):
                    urls.append(href)
        elif t == "image":
            alt = c.content or ""
            if alt:
                out.append(alt)

    return "".join(out), urls


# CommonMark left/right-flanking rules treat 」』】 etc. as punctuation, which
# can prevent ** from closing when the next character is a CJK letter (no space).
# Example: `**「テスト」**です` leaves literal `**...**` after AST. We sweep these
# orphans only at the inline level so code blocks (rendered from tok.content)
# stay intact.
_RE_RESIDUAL_STRONG = re.compile(r"\*\*([^*\n]+?)\*\*")
_RE_RESIDUAL_EM = re.compile(r"(?<!\*)\*([^*\n]+?)\*(?!\*)")
_RE_RESIDUAL_DEL = re.compile(r"~~([^\n]+?)~~")


def _strip_residual_emphasis(text: str) -> str:
    text = _RE_RESIDUAL_STRONG.sub(r"\1", text)
    text = _RE_RESIDUAL_EM.sub(r"\1", text)
    text = _RE_RESIDUAL_DEL.sub(r"\1", text)
    return text
