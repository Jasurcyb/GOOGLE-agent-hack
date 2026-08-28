from __future__ import annotations

import hashlib
import re
from pathlib import Path

from contracts.models.enums import ChangeType, EdgeType, Resolution

from code_intelligence.analyzer_protocol import (
    CodeEdge,
    Entrypoint,
    LanguageAnalyzer,
    ParseResult,
    SourceFile,
    Symbol,
    SymbolChange,
)
from code_intelligence.entrypoints import detect_entrypoints


FUNCTION_RE = re.compile(
    r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*(<[^>]+>)?\s*\(([^)]*)\)\s*(?::\s*([^{]+?))?\s*\{',
    re.MULTILINE,
)
ARROW_RE = re.compile(
    r'(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*(?::\s*([^{]+?))?\s*=>',
    re.MULTILINE,
)
CLASS_RE = re.compile(
    r'(?:export\s+)?(?:abstract\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([\w,\s]+))?\s*\{',
    re.MULTILINE,
)
METHOD_RE = re.compile(
    r'(?:public|private|protected|static|async|override|readonly|\s)*\s+(\w+)\s*\(([^)]*)\)\s*(?::\s*([^{]+?))?\s*\{',
    re.MULTILINE,
)
IMPORT_RE = re.compile(
    r'import\s+(?:\{([^}]+)\}|(\w+))\s+from\s+["\']([^"\']+)["\']',
    re.MULTILINE,
)
EXPORT_RE = re.compile(r'export\s+\{([^}]+)\}', re.MULTILINE)
DECORATOR_RE = re.compile(r'@(\w+(?:\.\w+)*)\s*\(')
ROUTE_RE = re.compile(
    r'@(?:Get|Post|Put|Delete|Patch|All)\(\s*["\']([^"\']+)["\']',
    re.MULTILINE,
)
EXPRESS_RE = re.compile(
    r'\b(?:app|router)\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']',
    re.MULTILINE,
)


class TypeScriptAnalyzer:
    """TypeScript analyzer using regex-based parsing as a fallback for ts-morph sidecar."""

    language = "typescript"

    def parse(self, files: list[SourceFile]) -> list[ParseResult]:
        return [self._parse_file(f) for f in files]

    def _parse_file(self, f: SourceFile) -> ParseResult:
        result = ParseResult(file_path=f.path, language="typescript")
        content = f.content
        lines = content.splitlines()

        module_name = self._module_name_from_path(f.path)

        imports: list[str] = []
        for m in IMPORT_RE.finditer(content):
            named, default, source = m.group(1), m.group(2), m.group(3)
            if named:
                for n in named.split(","):
                    n = n.strip()
                    if n:
                        imports.append(f"{source}.{n}")
            if default:
                imports.append(f"{source}.{default}")

        result.imports = imports

        symbols: list[Symbol] = []

        for m in FUNCTION_RE.finditer(content):
            name = m.group(1)
            params = m.group(3) or ""
            ret = m.group(4) or ""
            line_num = content[:m.start()].count("\n") + 1
            end_line = self._find_end_brace(lines, line_num - 1)
            fqn = f"{module_name}.{name}"
            sym_id = hashlib.sha256(fqn.encode()).hexdigest()[:16]

            decorators = self._extract_decorators(lines, line_num - 1)

            symbols.append(Symbol(
                id=sym_id,
                fully_qualified_name=fqn,
                signature=f"function {name}({params}): {ret.strip()}",
                visibility="public" if "export" in content[max(0, m.start()-20):m.start()] else "private",
                file_path=f.path,
                start_line=line_num,
                end_line=end_line,
                decorators=decorators,
                is_test=name.startswith("test") or "test" in f.path.lower() or "spec" in f.path.lower(),
                parse_confidence=0.9,
                language="typescript",
                symbol_kind="function",
            ))

        for m in ARROW_RE.finditer(content):
            name = m.group(1)
            params = m.group(2) or ""
            ret = m.group(3) or ""
            line_num = content[:m.start()].count("\n") + 1
            fqn = f"{module_name}.{name}"
            sym_id = hashlib.sha256(fqn.encode()).hexdigest()[:16]

            symbols.append(Symbol(
                id=sym_id,
                fully_qualified_name=fqn,
                signature=f"const {name} = ({params}): {ret.strip()}",
                visibility="public",
                file_path=f.path,
                start_line=line_num,
                end_line=line_num,
                is_test=name.startswith("test") or "spec" in f.path.lower(),
                parse_confidence=0.85,
                language="typescript",
                symbol_kind="function",
            ))

        for m in CLASS_RE.finditer(content):
            name = m.group(1)
            extends = m.group(2)
            implements = m.group(3)
            line_num = content[:m.start()].count("\n") + 1
            end_line = self._find_end_brace(lines, line_num - 1)
            fqn = f"{module_name}.{name}"
            sym_id = hashlib.sha256(fqn.encode()).hexdigest()[:16]

            decorators = self._extract_decorators(lines, line_num - 1)

            sym = Symbol(
                id=sym_id,
                fully_qualified_name=fqn,
                visibility="public",
                file_path=f.path,
                start_line=line_num,
                end_line=end_line,
                decorators=decorators,
                parse_confidence=0.9,
                language="typescript",
                symbol_kind="class",
            )
            if extends:
                sym.annotations.append(f"extends:{extends}")
            if implements:
                sym.annotations.append(f"implements:{implements.strip()}")
            symbols.append(sym)

            class_body = self._extract_class_body(lines, line_num - 1, end_line)
            for mm in METHOD_RE.finditer(class_body):
                mname = mm.group(1)
                mparams = mm.group(2) or ""
                mret = mm.group(3) or ""
                mline = line_num + class_body[:mm.start()].count("\n") + 1
                mfqn = f"{module_name}.{name}.{mname}"
                msym_id = hashlib.sha256(mfqn.encode()).hexdigest()[:16]

                if mname == "constructor":
                    continue

                mdecorators = self._extract_decorators(lines, mline - 2)

                symbols.append(Symbol(
                    id=msym_id,
                    fully_qualified_name=mfqn,
                    signature=f"{mname}({mparams}): {mret.strip()}",
                    visibility="public",
                    file_path=f.path,
                    start_line=mline,
                    end_line=mline,
                    decorators=mdecorators,
                    is_test=mname.startswith("test"),
                    parse_confidence=0.8,
                    language="typescript",
                    symbol_kind="method",
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

    def _extract_decorators(self, lines: list[str], line_idx: int) -> list[str]:
        decorators: list[str] = []
        i = line_idx - 1
        while i >= 0 and (lines[i].strip().startswith("@") or lines[i].strip() == ""):
            stripped = lines[i].strip()
            if stripped.startswith("@"):
                decorators.append(stripped)
            i -= 1
        return decorators

    def _module_name_from_path(self, path: str) -> str:
        p = Path(path)
        parts = list(p.with_suffix("").parts)
        if parts and parts[0] == ".":
            parts = parts[1:]
        return ".".join(parts) if parts else p.stem

    def symbols(self, parse: ParseResult) -> list[Symbol]:
        return parse.symbols

    def edges(self, parse: ParseResult, symbols: list[Symbol]) -> list[CodeEdge]:
        edges: list[CodeEdge] = []
        sym_by_name = {s.fully_qualified_name.split(".")[-1]: s for s in symbols}

        for imp in parse.imports:
            short_name = imp.split(".")[-1]
            target = sym_by_name.get(short_name)
            if target:
                edges.append(CodeEdge(
                    run_id="",
                    from_symbol_id="",
                    to_symbol_id=target.id,
                    edge_type=EdgeType.IMPORTS,
                    resolution=Resolution.HEURISTIC,
                    confidence=0.7,
                ))

        return edges

    def entrypoints(self, parse: ParseResult) -> list[Entrypoint]:
        return parse.entrypoints

    def classify_change(self, base: ParseResult, head: ParseResult) -> list[SymbolChange]:
        changes: list[SymbolChange] = []
        base_syms = {s.id: s for s in base.symbols}
        head_syms = {s.id: s for s in head.symbols}

        for sym_id, sym in head_syms.items():
            if sym_id not in base_syms:
                changes.append(SymbolChange(
                    symbol_id=sym_id,
                    language="typescript",
                    change_type=ChangeType.ADDED,
                    new_signature=sym.signature,
                    file_path=sym.file_path,
                    start_line=sym.start_line,
                    end_line=sym.end_line,
                    semantic_delta={"new_symbol": True},
                ))
            else:
                old = base_syms[sym_id]
                if old.signature != sym.signature:
                    changes.append(SymbolChange(
                        symbol_id=sym_id,
                        language="typescript",
                        change_type=ChangeType.MODIFIED,
                        old_signature=old.signature,
                        new_signature=sym.signature,
                        file_path=sym.file_path,
                        start_line=sym.start_line,
                        end_line=sym.end_line,
                        semantic_delta={"signature_change": True},
                    ))

        for sym_id, sym in base_syms.items():
            if sym_id not in head_syms:
                changes.append(SymbolChange(
                    symbol_id=sym_id,
                    language="typescript",
                    change_type=ChangeType.DELETED,
                    old_signature=sym.signature,
                    file_path=sym.file_path,
                    start_line=sym.start_line,
                    end_line=sym.end_line,
                    semantic_delta={"deleted_symbol": True},
                ))

        return changes
