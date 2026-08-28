from __future__ import annotations

import hashlib
import re
from pathlib import Path

from contracts.models.enums import ChangeType, EdgeType, Resolution

from code_intelligence.analyzer_protocol import (
    CodeEdge, Entrypoint, LanguageAnalyzer,
    ParseResult, SourceFile, Symbol, SymbolChange,
)
from code_intelligence.entrypoints import detect_entrypoints

NAMESPACE_RE = re.compile(r'namespace\s+([\w.]+)', re.MULTILINE)
CLASS_RE = re.compile(
    r'(?:public|private|protected|internal|abstract|sealed|static|partial|\s)*\s*class\s+(\w+)(?:\s*:\s*([\w.,\s]+))?\s*\{',
    re.MULTILINE,
)
METHOD_RE = re.compile(
    r'(?:public|private|protected|internal|static|virtual|override|async|abstract|sealed|\s)*\s+([\w<>\[\],\?]+)\s+(\w+)\s*\(([^)]*)\)\s*\{',
    re.MULTILINE,
)
USING_RE = re.compile(r'using\s+([\w.]+);', re.MULTILINE)
HTTP_GET_RE = re.compile(r'\[Http(Get|Post|Put|Delete|Patch)\s*\(\s*["\']([^"\']+)["\']', re.MULTILINE)


class CSharpAnalyzer:
    """C# analyzer using regex-based parsing (Roslyn sidecar placeholder)."""

    language = "csharp"

    def parse(self, files: list[SourceFile]) -> list[ParseResult]:
        return [self._parse_file(f) for f in files]

    def _parse_file(self, f: SourceFile) -> ParseResult:
        result = ParseResult(file_path=f.path, language="csharp", parse_confidence=0.75)
        content = f.content
        lines = content.splitlines()

        ns_match = NAMESPACE_RE.search(content)
        ns = ns_match.group(1) if ns_match else Path(f.path).stem

        usings: list[str] = [m.group(1) for m in USING_RE.finditer(content)]
        result.imports = usings

        symbols: list[Symbol] = []

        for m in CLASS_RE.finditer(content):
            name = m.group(1)
            line_num = content[:m.start()].count("\n") + 1
            end_line = self._find_end_brace(lines, line_num - 1)
            fqn = f"{ns}.{name}"
            sym_id = hashlib.sha256(fqn.encode()).hexdigest()[:16]

            decorators = self._extract_attributes_before(lines, line_num - 1)

            sym = Symbol(
                id=sym_id, fully_qualified_name=fqn,
                visibility=self._extract_visibility(m.group(0)),
                file_path=f.path, start_line=line_num, end_line=end_line,
                decorators=decorators, parse_confidence=0.75,
                language="csharp", symbol_kind="class",
            )
            if m.group(2):
                sym.annotations.append(f"extends:{m.group(2).strip()}")
            symbols.append(sym)

            class_body = self._extract_class_body(lines, line_num - 1, end_line)
            for mm in METHOD_RE.finditer(class_body):
                ret_type = mm.group(1).strip()
                mname = mm.group(2)
                params = mm.group(3)
                mline = line_num + class_body[:mm.start()].count("\n") + 1
                mfqn = f"{ns}.{name}.{mname}"
                msym_id = hashlib.sha256(mfqn.encode()).hexdigest()[:16]

                if mname == name:
                    continue

                mdecorators = self._extract_attributes_before(lines, mline - 2)

                symbols.append(Symbol(
                    id=msym_id, fully_qualified_name=mfqn,
                    signature=f"{ret_type} {mname}({params})",
                    visibility=self._extract_visibility(mm.group(0)),
                    file_path=f.path, start_line=mline, end_line=mline,
                    decorators=mdecorators,
                    is_test=mname.startswith("Test") or "Test" in f.path,
                    parse_confidence=0.7, language="csharp", symbol_kind="method",
                ))

        result.symbols = symbols
        result.entrypoints = detect_entrypoints(result)
        return result

    def _find_end_brace(self, lines: list[str], start: int) -> int:
        depth = 0
        for i in range(start, len(lines)):
            for ch in lines[i]:
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        return i + 1
        return start + 1

    def _extract_class_body(self, lines: list[str], start: int, end: int) -> str:
        body_lines: list[str] = []
        depth = 0
        started = False
        for i in range(start, min(end, len(lines))):
            for ch in lines[i]:
                if ch == "{":
                    depth += 1
                    started = True
                elif ch == "}":
                    depth -= 1
            if started and depth > 0:
                body_lines.append(lines[i])
            elif started and depth == 0:
                break
        return "\n".join(body_lines)

    def _extract_attributes_before(self, lines: list[str], line_idx: int) -> list[str]:
        attrs: list[str] = []
        i = line_idx
        while i >= 0 and (lines[i].strip().startswith("[") or lines[i].strip() == ""):
            stripped = lines[i].strip()
            if stripped.startswith("["):
                attrs.append(stripped)
            i -= 1
        return attrs

    def _extract_visibility(self, text: str) -> str:
        for vis in ("public", "private", "protected", "internal"):
            if vis in text:
                return vis
        return "internal"

    def symbols(self, parse: ParseResult) -> list[Symbol]:
        return parse.symbols

    def edges(self, parse: ParseResult, symbols: list[Symbol]) -> list[CodeEdge]:
        edges: list[CodeEdge] = []
        sym_by_name = {s.fully_qualified_name.split(".")[-1]: s for s in symbols}
        for imp in parse.imports:
            short = imp.split(".")[-1]
            target = sym_by_name.get(short)
            if target:
                edges.append(CodeEdge(
                    run_id="", from_symbol_id="", to_symbol_id=target.id,
                    edge_type=EdgeType.IMPORTS, resolution=Resolution.HEURISTIC, confidence=0.6,
                ))
        return edges

    def entrypoints(self, parse: ParseResult) -> list[Entrypoint]:
        return parse.entrypoints

    def classify_change(self, base: ParseResult, head: ParseResult) -> list[SymbolChange]:
        changes: list[SymbolChange] = []
        base_syms = {s.id: s for s in base.symbols}
        head_syms = {s.id: s for s in head.symbols}

        for sid, sym in head_syms.items():
            if sid not in base_syms:
                changes.append(SymbolChange(
                    symbol_id=sid, language="csharp", change_type=ChangeType.ADDED,
                    new_signature=sym.signature, file_path=sym.file_path,
                    start_line=sym.start_line, end_line=sym.end_line,
                    semantic_delta={"new_symbol": True}, analyzer_confidence=0.75,
                ))
            elif base_syms[sid].signature != sym.signature:
                changes.append(SymbolChange(
                    symbol_id=sid, language="csharp", change_type=ChangeType.MODIFIED,
                    old_signature=base_syms[sid].signature, new_signature=sym.signature,
                    file_path=sym.file_path, start_line=sym.start_line, end_line=sym.end_line,
                    semantic_delta={"signature_change": True}, analyzer_confidence=0.75,
                ))

        for sid, sym in base_syms.items():
            if sid not in head_syms:
                changes.append(SymbolChange(
                    symbol_id=sid, language="csharp", change_type=ChangeType.DELETED,
                    old_signature=sym.signature, file_path=sym.file_path,
                    start_line=sym.start_line, end_line=sym.end_line,
                    semantic_delta={"deleted_symbol": True}, analyzer_confidence=0.75,
                ))

        return changes
