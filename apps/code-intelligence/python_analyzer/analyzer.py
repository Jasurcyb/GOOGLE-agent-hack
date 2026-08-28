from __future__ import annotations

import ast
import hashlib
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


class PythonAnalyzer:
    """Python analyzer using ast for parsing and symbol extraction."""

    language = "python"

    def parse(self, files: list[SourceFile]) -> list[ParseResult]:
        results: list[ParseResult] = []
        for f in files:
            results.append(self._parse_file(f))
        return results

    def _parse_file(self, f: SourceFile) -> ParseResult:
        result = ParseResult(file_path=f.path, language="python", source_content=f.content)

        try:
            tree = ast.parse(f.content, filename=f.path)
        except SyntaxError as e:
            result.errors.append(f"SyntaxError: {e}")
            result.parse_confidence = 0.5
            return result

        module_name = self._module_name_from_path(f.path)
        imports: list[str] = []
        symbols: list[Symbol] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append(f"{module}.{alias.name}" if module else alias.name)

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                sym = self._make_symbol(node, f.path, module_name)
                symbols.append(sym)
            elif isinstance(node, ast.ClassDef):
                sym = self._make_symbol(node, f.path, module_name, kind="class")
                symbols.append(sym)
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        child_sym = self._make_symbol(
                            child, f.path, module_name,
                            parent=node.name,
                        )
                        symbols.append(child_sym)

        result.symbols = symbols
        result.imports = imports
        result.entrypoints = detect_entrypoints(result)
        return result

    def _make_symbol(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
        file_path: str,
        module_name: str,
        parent: str | None = None,
        kind: str = "function",
    ) -> Symbol:
        name = node.name
        fqn = f"{module_name}.{parent}.{name}" if parent else f"{module_name}.{name}"
        sym_id = hashlib.sha256(fqn.encode()).hexdigest()[:16]

        decorators: list[str] = []
        for d in node.decorator_list:
            try:
                decorators.append(ast.unparse(d))
            except Exception:
                decorators.append("<unknown>")

        visibility = "public"
        if name.startswith("_"):
            visibility = "private"
        elif name.startswith("__"):
            visibility = "private"

        is_test = name.startswith("test_") or "test" in file_path.lower()

        signature = self._extract_signature(node) if kind == "function" else None

        return Symbol(
            id=sym_id,
            fully_qualified_name=fqn,
            signature=signature,
            visibility=visibility,
            file_path=file_path,
            start_line=node.lineno,
            end_line=getattr(node, "end_lineno", node.lineno),
            decorators=decorators,
            is_test=is_test,
            parse_confidence=1.0,
            language="python",
            symbol_kind=kind,
        )

    def _extract_signature(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        try:
            return ast.unparse(node).split(":")[0].strip().rstrip(")")
        except Exception:
            return f"def {node.name}(...)"

    def _module_name_from_path(self, path: str) -> str:
        p = Path(path)
        parts = list(p.with_suffix("").parts)
        if parts and parts[0] == ".":
            parts = parts[1:]
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]
        return ".".join(parts) if parts else p.stem

    def symbols(self, parse: ParseResult) -> list[Symbol]:
        return parse.symbols

    def edges(self, parse: ParseResult, symbols: list[Symbol]) -> list[CodeEdge]:
        edges: list[CodeEdge] = []
        sym_by_id = {s.id: s for s in symbols}
        sym_by_name = {s.fully_qualified_name: s for s in symbols}

        try:
            tree = ast.parse(parse.source_content, filename=parse.file_path)
        except Exception:
            return edges

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                callee = self._get_callee_name(node)
                if callee:
                    target = self._resolve_symbol(callee, parse.imports, sym_by_name)
                    if target:
                        caller = self._find_containing_symbol(node, symbols)
                        if caller:
                            edges.append(CodeEdge(
                                run_id="",
                                from_symbol_id=caller.id,
                                to_symbol_id=target.id,
                                edge_type=EdgeType.CALLS,
                                resolution=Resolution.EXACT,
                                confidence=1.0,
                            ))

        for imp in parse.imports:
            target = sym_by_name.get(imp)
            if target:
                edges.append(CodeEdge(
                    run_id="",
                    from_symbol_id="",
                    to_symbol_id=target.id,
                    edge_type=EdgeType.IMPORTS,
                    resolution=Resolution.HEURISTIC,
                    confidence=0.8,
                ))

        return edges

    def _get_callee_name(self, node: ast.Call) -> str | None:
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            try:
                return ast.unparse(node.func)
            except Exception:
                return None
        return None

    def _resolve_symbol(
        self,
        name: str,
        imports: list[str],
        sym_by_name: dict[str, Symbol],
    ) -> Symbol | None:
        for fqn, sym in sym_by_name.items():
            if fqn.endswith(f".{name}") or fqn.endswith(name):
                return sym
        for imp in imports:
            if imp.endswith(name):
                return sym_by_name.get(imp)
        return None

    def _find_containing_symbol(self, node: ast.AST, symbols: list[Symbol]) -> Symbol | None:
        if hasattr(node, "lineno"):
            for sym in symbols:
                if sym.start_line <= node.lineno <= sym.end_line:
                    return sym
        return None

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
                    language="python",
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
                    delta = self._compute_semantic_delta(old, sym)
                    changes.append(SymbolChange(
                        symbol_id=sym_id,
                        language="python",
                        change_type=ChangeType.MODIFIED,
                        old_signature=old.signature,
                        new_signature=sym.signature,
                        file_path=sym.file_path,
                        start_line=sym.start_line,
                        end_line=sym.end_line,
                        semantic_delta=delta,
                    ))

        for sym_id, sym in base_syms.items():
            if sym_id not in head_syms:
                changes.append(SymbolChange(
                    symbol_id=sym_id,
                    language="python",
                    change_type=ChangeType.DELETED,
                    old_signature=sym.signature,
                    file_path=sym.file_path,
                    start_line=sym.start_line,
                    end_line=sym.end_line,
                    semantic_delta={"deleted_symbol": True},
                ))

        return changes

    def _compute_semantic_delta(self, old: Symbol, new: Symbol) -> dict:
        delta: dict = {}

        if old.signature and new.signature and old.signature != new.signature:
            delta["signature_change"] = True

        if old.symbol_kind != new.symbol_kind:
            delta["kind_change"] = True

        old_decorators = set(old.decorators)
        new_decorators = set(new.decorators)
        if old_decorators != new_decorators:
            delta["decorator_change"] = True
            delta["added_decorators"] = list(new_decorators - old_decorators)
            delta["removed_decorators"] = list(old_decorators - new_decorators)

        if old.visibility != new.visibility:
            delta["visibility_change"] = True

        if not delta:
            delta["body_change"] = True

        return delta
