from __future__ import annotations

import re
from dataclasses import dataclass
from enum import IntEnum
from typing import Iterable

from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat


@dataclass(frozen=True, slots=True)
class _Span:
    start: int
    end: int  # exclusive


def _merge_spans(spans: list[_Span]) -> list[_Span]:
    if not spans:
        return []
    items = sorted(spans, key=lambda s: (s.start, s.end))
    out: list[_Span] = [items[0]]
    for sp in items[1:]:
        last = out[-1]
        if sp.start < last.end:
            out[-1] = _Span(last.start, max(last.end, sp.end))
        else:
            out.append(sp)
    return out


def _overlaps(spans: Iterable[_Span], start: int, end: int) -> bool:
    for sp in spans:
        if not (end <= sp.start or start >= sp.end):
            return True
    return False


class _State(IntEnum):
    NORMAL = 0
    FENCE = 1


class MarkdownHighlighter(QSyntaxHighlighter):
    """
    Live markdown styling for QPlainTextEdit (editing aid).

    Covers the common GFM-ish subset:
    - Block: fenced ```/~~~ code, setext-ish hr, ATX headings, blockquotes, lists (+ tasks), simple pipe tables
    - Inline: `code`, **bold**, *italic* / _italic_, ~~strike~~, [text](url), ![alt](url), <https://...>
    """

    _heading = re.compile(r"^(?P<ind>\s{0,3})(?P<hashes>#{1,6})(?P<sp>\s+)(?P<title>.*)$")
    _hr = re.compile(r"^\s*(\*{3,}|-{3,}|_{3,})\s*$")
    _fence = re.compile(r"^\s*(```|~~~)")

    # Emphasis (commonmark-ish, pragmatic)
    _bold_star = re.compile(r"(?<!\*)\*\*(?=\S)(.+?)(?<=\S)\*\*(?!\*)", re.DOTALL)
    _bold_us = re.compile(r"(?<!_)__(?=\S)(.+?)(?<=\S)__(?!_)", re.DOTALL)
    _italic_star = re.compile(r"(?<!\*)\*(?!\*)(?=\S)(.+?)(?<=\S)\*(?!\*)", re.DOTALL)
    _italic_us = re.compile(r"(?<!_)_(?!_)(?=\S)(.+?)(?<=\S)_(?!_)", re.DOTALL)
    _strike = re.compile(r"(?<!~)~~(?=\S)(.+?)(?<=\S)~~(?!~)", re.DOTALL)

    _inline_code = re.compile(r"(?<!`)`[^`]+`(?!`)")
    _image = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
    _link = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)")
    _autolink = re.compile(r"<(https?://[^>\s]+)>")

    def __init__(self, parent_document, *, dark_mode: bool, base_font_size: int) -> None:
        super().__init__(parent_document)
        self._dark_mode = dark_mode
        self._base_font_size = base_font_size
        self._rebuild_formats()

    def set_dark_mode(self, dark_mode: bool) -> None:
        if self._dark_mode == dark_mode:
            return
        self._dark_mode = dark_mode
        self._rebuild_formats()
        self.rehighlight()

    def set_base_font_size(self, base_font_size: int) -> None:
        if self._base_font_size == base_font_size:
            return
        self._base_font_size = base_font_size
        self._rebuild_formats()
        self.rehighlight()

    def _rebuild_formats(self) -> None:
        self._heading_fg = QColor("#6b4eff")
        self._muted = QColor("#8b8b8b" if self._dark_mode else "#6b6b6b")
        self._link_color = QColor("#2a7bde" if not self._dark_mode else "#6aa6ff")
        self._list_color = QColor("#2a7bde" if not self._dark_mode else "#6aa6ff")
        self._quote_color = QColor("#9a9a9a" if self._dark_mode else "#5f5f5f")
        self._code_fg = QColor("#d14" if not self._dark_mode else "#ff6b6b")
        self._code_bg = QColor("#1a1a1d" if self._dark_mode else "#f2f2f2")

        self._fenced = QTextCharFormat()
        self._fenced.setFontFamily("monospace")
        self._fenced.setForeground(self._code_fg)
        self._fenced.setBackground(self._code_bg)

        self._table = QTextCharFormat()
        self._table.setFontFamily("monospace")

        self._title_by_level: dict[int, QTextCharFormat] = {}
        self._hash_by_level: dict[int, QTextCharFormat] = {}
        scale = {1: 2.0, 2: 1.75, 3: 1.55, 4: 1.35, 5: 1.2, 6: 1.1}
        for level in range(1, 7):
            t = QTextCharFormat()
            t.setFontWeight(QFont.Weight.Bold)
            t.setForeground(self._heading_fg)
            t.setFontPointSize(max(1, int(self._base_font_size * scale[level])))
            self._title_by_level[level] = t

            h = QTextCharFormat(t)
            h.setFontPointSize(max(1, int(self._base_font_size * 0.95)))
            h.setForeground(self._heading_fg)
            self._hash_by_level[level] = h

        self._hr_fmt = QTextCharFormat()
        self._hr_fmt.setForeground(self._muted)

        self._quote_text = QTextCharFormat()
        self._quote_text.setForeground(self._quote_color)
        self._quote_gt = QTextCharFormat()
        self._quote_gt.setForeground(self._muted)

        self._list_mark = QTextCharFormat()
        self._list_mark.setForeground(self._list_color)
        self._list_mark.setFontWeight(QFont.Weight.DemiBold)

        self._code = QTextCharFormat()
        self._code.setFontFamily("monospace")
        self._code.setForeground(self._code_fg)
        self._code.setBackground(self._code_bg)

        self._a_text = QTextCharFormat()
        self._a_text.setForeground(self._link_color)
        self._a_text.setFontUnderline(True)

        self._a_url = QTextCharFormat()
        self._a_url.setForeground(self._link_color)
        self._a_url.setFontFamily("monospace")

        self._img_alt = QTextCharFormat()
        self._img_alt.setForeground(self._link_color)

        self._dim = QTextCharFormat()
        self._dim.setForeground(self._muted)

    @staticmethod
    def _strong() -> QTextCharFormat:
        f = QTextCharFormat()
        f.setFontWeight(QFont.Weight.Bold)
        return f

    @staticmethod
    def _emph() -> QTextCharFormat:
        f = QTextCharFormat()
        f.setFontItalic(True)
        return f

    @staticmethod
    def _strikefmt() -> QTextCharFormat:
        f = QTextCharFormat()
        f.setFontStrikeOut(True)
        return f

    def highlightBlock(self, text: str) -> None:
        prev = self.previousBlockState()
        if prev == int(_State.FENCE):
            if self._fence.match(text) is not None:
                self.setFormat(0, len(text), self._fenced)
                self.setCurrentBlockState(int(_State.NORMAL))
                return
            self.setFormat(0, len(text), self._fenced)
            self.setCurrentBlockState(int(_State.FENCE))
            return

        if self._fence.match(text) is not None:
            self.setFormat(0, len(text), self._fenced)
            self.setCurrentBlockState(int(_State.FENCE))
            return

        if self._hr.match(text) is not None:
            self.setFormat(0, len(text), self._hr_fmt)
            self.setCurrentBlockState(int(_State.NORMAL))
            return

        if re.match(r"^\s*\|.*\|\s*$", text) and "|" in text:
            self.setFormat(0, len(text), self._table)
            self.setCurrentBlockState(int(_State.NORMAL))
            return

        mh = self._heading.match(text)
        if mh is not None:
            level = min(len(mh.group("hashes")), 6)
            ind = mh.group("ind")
            hs = mh.group("hashes")
            sp = mh.group("sp")
            i0, hlen, slen = len(ind), len(hs), len(sp)
            t0 = i0 + hlen + slen
            self.setFormat(i0, hlen, self._hash_by_level[level])
            self.setFormat(t0, max(0, len(text) - t0), self._title_by_level[level])
            self._apply_inlines(text, _merge_spans([_Span(i0, i0 + hlen)]))
            self.setCurrentBlockState(int(_State.NORMAL))
            return

        mq = re.match(r"^(\s{0,3})(>\s?)(.*)$", text)
        if mq is not None:
            i = len(mq.group(1))
            g = len(mq.group(2))
            self.setFormat(i, g, self._quote_gt)
            self.setFormat(i + g, max(0, len(text) - (i + g)), self._quote_text)

        mlist = re.match(
            r"^(?P<ind>\s{0,3})(?P<mk>(?:(?:[-*+](?:\s+\[[ xX]\])?)|(?:\d+\.)))(?P<sp>\s+)",
            text,
        )
        if mlist is not None:
            self.setFormat(mlist.start("ind"), mlist.end("sp") - mlist.start("ind"), self._list_mark)

        self._apply_inlines(text, [])
        self.setCurrentBlockState(int(_State.NORMAL))

    def _apply_inlines(self, text: str, initial_protect: list[_Span]) -> None:
        protected = _merge_spans(list(initial_protect))

        def in_prot(s: int, e: int) -> bool:
            return _overlaps(protected, s, e)

        def add_prot(s: int, e: int) -> None:
            nonlocal protected
            if s >= e or in_prot(s, e):
                return
            protected = _merge_spans(protected + [_Span(s, e)])

        # Inline code first (highest priority)
        for m in self._inline_code.finditer(text):
            if in_prot(m.start(), m.end()):
                continue
            add_prot(m.start(), m.end())
            self.setFormat(m.start(), m.end() - m.start(), self._code)

        # Images
        for m in self._image.finditer(text):
            if in_prot(m.start(), m.end()):
                continue
            add_prot(m.start(), m.end())
            self.setFormat(m.start(), m.start() + 2, self._dim)  # ![
            self.setFormat(m.start() + 2, m.end(1) - (m.start() + 2), self._img_alt)
            self.setFormat(m.end(1), m.start(2) - m.end(1), self._dim)  # ](
            self.setFormat(m.start(2), m.end(2) - m.start(2), self._a_url)
            self.setFormat(m.end(2), m.end() - m.end(2), self._dim)  # )

        # Links
        for m in self._link.finditer(text):
            if in_prot(m.start(), m.end()):
                continue
            add_prot(m.start(), m.end())
            self.setFormat(m.start(), m.start() + 1, self._dim)  # [
            self.setFormat(m.start(1), m.end(1) - m.start(1), self._a_text)
            self.setFormat(m.end(1), m.start(2) - m.end(1), self._dim)  # ](
            self.setFormat(m.start(2), m.end(2) - m.start(2), self._a_url)
            self.setFormat(m.end(2), m.end() - m.end(2), self._dim)  # )

        # Autolinks
        for m in self._autolink.finditer(text):
            if in_prot(m.start(), m.end()):
                continue
            add_prot(m.start(), m.end())
            self.setFormat(m.start(), m.end() - m.start(), self._a_url)

        # Collect protected union after structural inlines
        protected = _merge_spans(protected)

        def blocked(s: int, e: int) -> bool:
            return _overlaps(protected, s, e)

        def paint_emphasis(pattern: re.Pattern[str], inner_fmt: QTextCharFormat, width: int) -> None:
            for m in pattern.finditer(text):
                a, b = m.start(), m.end()
                if blocked(a, b):
                    continue
                # Markers
                self.setFormat(a, a + width, self._dim)
                self.setFormat(b - width, b, self._dim)
                self.setFormat(a + width, b - width, inner_fmt)

        paint_emphasis(self._bold_star, self._strong(), 2)
        paint_emphasis(self._bold_us, self._strong(), 2)
        paint_emphasis(self._italic_star, self._emph(), 1)
        paint_emphasis(self._italic_us, self._emph(), 1)
        paint_emphasis(self._strike, self._strikefmt(), 2)
