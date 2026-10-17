"""대용량 업종 Silver를 메모리에 통째로 올리지 않고 순서대로 읽는다."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator, TextIO


class JsonStream:
    """정해진 Silver 구조의 문자열·객체 값을 엄격한 JSON 디코더로 읽는다."""

    def __init__(self, stream: TextIO, chunk_size: int = 1024 * 1024) -> None:
        self.stream, self.chunk_size = stream, chunk_size
        self.buffer, self.pos = '', 0
        self.decoder = json.JSONDecoder()

    def fill(self) -> bool:
        data = self.stream.read(self.chunk_size)
        if not data:
            return False
        self.buffer, self.pos = self.buffer[self.pos:] + data, 0
        return True

    def peek(self) -> str:
        while True:
            if self.pos == len(self.buffer) and not self.fill():
                return ''
            if not self.buffer[self.pos].isspace():
                return self.buffer[self.pos]
            self.pos += 1

    def expect(self, char: str) -> None:
        if self.peek() != char:
            raise ValueError(f'invalid_json_structure: expected {char}')
        self.pos += 1

    def value(self) -> Any:
        self.peek()
        while True:
            try:
                value, self.pos = self.decoder.raw_decode(self.buffer, self.pos)
                return value
            except json.JSONDecodeError:
                if not self.fill():
                    raise

    def keys(self) -> Iterator[str]:
        self.expect('{')
        seen = set()
        if self.peek() == '}':
            self.expect('}')
            return
        while True:
            key = self.value()
            if not isinstance(key, str) or key in seen:
                raise ValueError('invalid_or_duplicate_object_key')
            seen.add(key)
            self.expect(':')
            yield key
            if self.peek() == '}':
                self.expect('}')
                return
            self.expect(',')

    def rows(self) -> Iterator[dict]:
        self.expect('[')
        if self.peek() == ']':
            self.expect(']')
            return
        while True:
            row = self.value()
            if not isinstance(row, dict):
                raise ValueError('non_object_silver_row')
            yield row
            if self.peek() == ']':
                self.expect(']')
                return
            self.expect(',')


def silver_rows(path: Path, chunk_size: int = 1024 * 1024) -> Iterator[tuple[str, str, dict]]:
    """부분 상태를 확인하고 datasets·links를 읽는다. 잘린 파일은 실패한다."""
    with path.open(encoding='utf-8') as stream:
        reader = JsonStream(stream, chunk_size)
        sections = set()
        for section in reader.keys():
            sections.add(section)
            if section == 'status':
                if reader.value() != 'partial_quarantined':
                    raise ValueError('expected_partial_quarantined')
            elif section in ('datasets', 'links'):
                if 'status' not in sections:
                    raise ValueError('status_must_precede_rows')
                for source in reader.keys():
                    for row in reader.rows():
                        yield section, source, row
            else:
                raise ValueError(f'unknown_silver_section: {section}')
        if sections != {'status', 'datasets', 'links'} or reader.peek():
            raise ValueError('incomplete_or_trailing_silver_content')
