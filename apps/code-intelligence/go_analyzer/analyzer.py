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

PACKAGE_RE = re.compile(r'package\s+(\w+)', re.MULTILINE)
FUNC_RE = re.compile(r'func\s+(?:\(([^)]+)\)\s+)?(\w+)\s*\(([^)]*)\)\s*(.*?)\s*\{', re.MULTILINE)
STRUCT_RE = re.compile(r'type\s+(\w+)\s+struct\s*\{', re.MULTILINE)
INTERFACE_RE = re.compile(r'type\s+(\w+)\s+interface\s*\{', re.MULTILINE)
IMPORT_RE = re.compile(r'"([^"]+)"', re.MULTILINE)
HTTP_HANDLER_RE = re.compile(r'http\.Handle(?:Func)?\s*\(\s*["\']([^"\']+)["\']', re.MULTILINE)


class GoAnalyzer:
    """Go analyzer using regex-based parsing (Go AST helper placeholder)."""

    language = "go"

    def parse(self, files: list[SourceFile]) -> list[ParseResult]:
        return [self._parse_file(f) for f in files]

    def _parse_file(self, f: SourceFile) -> ParseResult:
        result = ParseResult(file_path=f.path, language="go", parse_confidence=0.75)
        content = f.content
        lines = content.splitlines()

        pkg_match = PACKAGE_RE.search(content)
        package = pkg_match.group(1) if pkg_match else Path(f.path).stem

        import_block = re.search(r'import\s*\(([^)]+)\)', content, re.DOTALL)
        imports: list[str] = []
        if import_block:
            imports = [m.group(1) for m in IMPORT_RE.finditer(import_block.group(1))]
        else:
            for m in re.finditer(r'import\s+"([^"]+)"', content):
                imports.append(m.group(1))
        result.imports = imports

        symbols: list[Symbol] = []

        for m in STRUCT_RE.finditer(content):
            name = m.group(1)
            line_num = content[:m.start()].count("\n") + 1
            end_line = self._find_end_brace(lines, line_num - 1)
            fqn = f"{package}.{name}"
            sym_id = hashlib.sha256(fqn.encode()).hexdigest()[:16]
            symbols.append(Symbol(
                id=sym_id, fully_qualified_name=fqn, visibility="public",
                file_path=f.path, start_line=line_num, end_line=end_line,
                parse_confidence=0.75, language="go", symbol_kind="struct",
            ))

        for m in INTERFACE_RE.finditer(content):
            name = m.group(1)
            line_num = content[:m.start()].count("\n") + 1
            end_line = self._find_end_brace(lines, line_num - 1)
            fqn = f"{package}.{name}"
            sym_id = hashlib.sha256(fqn.encode()).hexdigest()[:16]
            symbols.append(Symbol(
                id=sym_id, fully_qualified_name=fqn, visibility="public",
                file_path=f.path, start_line=line_num, end_line=end_line,
                parse_confidence=0.75, language="go", symbol_kind="interface",
            ))

        for m in FUNC_RE.finditer(content):
            receiver = m.group(1)
            name = m.group(2)
            params = m.group(3)
            ret = (m.group(4) or "").strip()
            line_num = content[:m.start()].count("\n") + 1
            end_line = self._find_end_brace(lines, line_num - 1)

            if receiver:
                recv_type = receiver.split()[0].strip("*").strip()
                fqn = f"{package}.{recv_type}.{name}"
            else:
                fqn = f"{package}.{name}"
            sym_id = hashlib.sha256(fqn.encode()).hexdigest()[:16]

            visibility = "public" if name[0].isupper() else "private"

            symbols.append(Symbol(
                id=sym_id, fully_qualified_name=fqn,
                signature=f"func {name}({params}) {ret}",
                visibility=visibility, file_path=f.path,
                start_line=line_num, end_line=end_line,
                is_test=name.startswith("Test") or "test" in f.path.lower(),
                parse_confidence=0.75, language="go", symbol_kind="function",
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

    def symbols(self, parse: ParseResult) -> list[Symbol]:
        return parse.symbols

    def edges(self, parse: ParseResult, symbols: list[Symbol]) -> list[CodeEdge]:
        edges: list[CodeEdge] = []
        sym_by_name = {s.fully_qualified_name.split(".")[-1]: s for s in symbols}
        for imp in parse.imports:
            short = imp.split("/")[-1]
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
                    symbol_id=sid, language="go", change_type=ChangeType.ADDED,
                    new_signature=sym.signature, file_path=sym.file_path,
                    start_line=sym.start_line, end_line=sym.end_line,
                    semantic_delta={"new_symbol": True}, analyzer_confidence=0.75,
                ))
            elif base_syms[sid].signature != sym.signature:
                changes.append(SymbolChange(
                    symbol_id=sid, language="go", change_type=ChangeType.MODIFIED,
                    old_signature=base_syms[sid].signature, new_signature=sym.signature,
                    file_path=sym.file_path, start_line=sym.start_line, end_line=sym.end_line,
                    semantic_delta={"signature_change": True}, analyzer_confidence=0.75,
                ))

        for sid, sym in base_syms.items():
            if sid not in head_syms:
                changes.append(SymbolChange(
                    symbol_id=sid, language="go", change_type=ChangeType.DELETED,
                    old_signature=sym.signature, file_path=sym.file_path,
                    start_line=sym.start_line, end_line=sym.end_line,
                    semantic_delta={"deleted_symbol": True}, analyzer_confidence=0.75,
                ))

        return changes
