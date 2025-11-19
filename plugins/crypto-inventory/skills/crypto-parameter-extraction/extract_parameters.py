#!/usr/bin/env python3
"""
Extract cryptographic parameters from semgrep results.

This script extracts parameter values from crypto function calls found by semgrep.
It prioritizes semgrep metavariables (which extract literals reliably), then falls
back to parsing code snippets for literals only.

Usage:
    python3 extract_parameters.py --semgrep-results semgrep-all.json --output parameters.json

    Or pipe semgrep JSON directly:
    cat semgrep-all.json | python3 extract_parameters.py --output parameters.json
"""

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Pattern


class Confidence(Enum):
    """Confidence levels for extracted parameters."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNEXTRACTABLE = "unextractable"


class ParameterType:
    """Parameter type constants."""

    KEY_SIZE = "key_size"
    ITERATIONS = "iterations"
    CIPHER_MODE = "cipher_mode"
    IV = "iv"
    NONCE = "nonce"
    SALT = "salt"
    SALT_SIZE = "salt_size"
    KEY = "key"
    PASSWORD = "password"
    ALGORITHM = "algorithm"
    HASH = "hash"
    DIGEST = "digest"
    UNKNOWN = "unknown"


@dataclass
class ExtractedParameter:
    """Represents an extracted parameter value."""

    file_path: str
    line: int
    column: int
    check_id: str
    parameter_name: str
    parameter_type: str
    value: Any
    confidence: str
    resolution_path: List[str]


class LiteralParser:
    """Parses literal values from expressions."""

    OPERATOR_CHARS: ClassVar[set[str]] = set("+-*/%=:?{}[],")
    NULL_VALUES: ClassVar[set[str]] = {"null", "none"}
    _NULL_SENTINEL: ClassVar[object] = object()
    UPPERCASE_IDENTIFIER_PATTERN: ClassVar[Pattern[str]] = re.compile(
        r"^[A-Z][A-Z0-9_]*$"
    )
    DECIMAL_NUMBER_PATTERN: ClassVar[Pattern[str]] = re.compile(r"\b(\d+)\b")
    HEX_NUMBER_PATTERN: ClassVar[Pattern[str]] = re.compile(r"\b0x([0-9a-fA-F]+)\b")
    STRING_LITERAL_PATTERN: ClassVar[Pattern[str]] = re.compile(r'["\']([^"\']+)["\']')
    SNIPPET_TRUNCATE_LENGTH: ClassVar[int] = 50

    @classmethod
    def parse(cls, expr: str) -> Optional[Any]:
        """
        Parse a literal value from an expression.

        Only extracts actual literals, rejecting:
        - Function calls
        - Variable references
        - Complex expressions
        - Struct field accesses

        Returns:
            Parsed literal value or None if not a literal
        """
        expr = expr.strip()
        if not expr:
            return None

        if cls._is_function_call(expr) or cls._has_operators(expr):
            return None

        result = (
            cls._parse_integer(expr)
            or cls._parse_hex(expr)
            or cls._parse_quoted_string(expr)
            or cls._parse_boolean(expr)
            or cls._parse_null(expr)
            or cls._parse_qualified_constant(expr)
            or cls._parse_uppercase_identifier(expr)
        )
        if result is cls._NULL_SENTINEL:
            return None
        return result

    @staticmethod
    def _is_function_call(expr: str) -> bool:
        """
        Check if expression contains a function call.

        Detects patterns like:
        - foo()
        - foo(bar)
        - foo.bar()
        """
        if "()" in expr:
            return True
        if expr.endswith(")") and "(" in expr:
            return True
        return False

    @classmethod
    def _has_operators(cls, expr: str) -> bool:
        """Check if expression contains operators."""
        return any(char in expr for char in cls.OPERATOR_CHARS)

    @staticmethod
    def _parse_integer(expr: str) -> Optional[int]:
        """Parse integer literal."""
        if expr.isdigit() or (expr.startswith("-") and expr[1:].isdigit()):
            return int(expr)
        return None

    @staticmethod
    def _parse_hex(expr: str) -> Optional[int]:
        """Parse hexadecimal literal."""
        HEX_PREFIXES = ("0x", "0X")
        if expr.startswith(HEX_PREFIXES):
            try:
                return int(expr, 16)
            except ValueError:
                pass
        return None

    @staticmethod
    def _parse_quoted_string(expr: str) -> Optional[str]:
        """Parse quoted string literal."""
        QUOTE_CHARS = ('"', "'")
        if (expr.startswith(QUOTE_CHARS[0]) and expr.endswith(QUOTE_CHARS[0])) or (
            expr.startswith(QUOTE_CHARS[1]) and expr.endswith(QUOTE_CHARS[1])
        ):
            return expr[1:-1]
        return None

    @staticmethod
    def _parse_boolean(expr: str) -> Optional[bool]:
        """Parse boolean literal."""
        lower = expr.lower()
        if lower == "true":
            return True
        if lower == "false":
            return False
        return None

    @classmethod
    def _parse_null(cls, expr: str) -> Optional[object]:
        """Parse null/none literal. Returns sentinel (not None) to stop or-chain."""
        if expr.lower() in cls.NULL_VALUES:
            return cls._NULL_SENTINEL
        return None

    @staticmethod
    def _parse_qualified_constant(expr: str) -> Optional[str]:
        """Parse qualified constant (e.g., tls.VersionTLS12)."""
        if "." in expr:
            parts = expr.split(".", 1)
            if len(parts) == 2:
                first, second = parts
                if first[0].islower() or second[0].islower():
                    return None
                return expr
        return None

    @classmethod
    def _parse_uppercase_identifier(cls, expr: str) -> Optional[str]:
        """Parse uppercase identifier constant (e.g., GCM, AES)."""
        if cls.UPPERCASE_IDENTIFIER_PATTERN.match(expr):
            return expr
        return None

    @classmethod
    def extract_from_snippet(cls, code_snippet: str) -> List[Any]:
        """
        Extract all literal values from a code snippet.

        Returns:
            List of extracted literals (numbers, strings)
        """
        extracted = []

        for pattern, parser in [
            (cls.DECIMAL_NUMBER_PATTERN, lambda m: int(m)),
            (cls.HEX_NUMBER_PATTERN, lambda m: int(m, 16)),
            (cls.STRING_LITERAL_PATTERN, lambda m: m if m else None),
        ]:
            matches = pattern.findall(code_snippet)
            for match in matches:
                try:
                    value = parser(match)
                    if value is not None:
                        extracted.append(value)
                except (ValueError, TypeError):
                    continue

        return extracted


class ParameterTypeMapper:
    """Maps metavar names to parameter types."""

    TYPE_MAPPING: ClassVar[Dict[str, str]] = {
        "key_size": ParameterType.KEY_SIZE,
        "keysize": ParameterType.KEY_SIZE,
        "iterations": ParameterType.ITERATIONS,
        "iteration": ParameterType.ITERATIONS,
        "mode": ParameterType.CIPHER_MODE,
        "cipher_mode": ParameterType.CIPHER_MODE,
        "iv": ParameterType.IV,
        "initialization_vector": ParameterType.IV,
        "nonce": ParameterType.NONCE,
        "number_once": ParameterType.NONCE,
        "salt": ParameterType.SALT,
        "salt_size": ParameterType.SALT_SIZE,
        "saltlength": ParameterType.SALT_SIZE,
        "key": ParameterType.KEY,
        "password": ParameterType.PASSWORD,
        "algorithm": ParameterType.ALGORITHM,
        "hash": ParameterType.HASH,
        "digest": ParameterType.DIGEST,
    }

    METAVAR_PREFIX: ClassVar[str] = "$"
    NAME_SEPARATOR: ClassVar[str] = "-"

    @classmethod
    def infer(cls, metavar_name: str) -> Dict[str, str]:
        """
        Infer parameter name and type from metavar name.

        Args:
            metavar_name: Metavar name (e.g., "$KEY_SIZE")

        Returns:
            Dictionary with "name" and "type" keys
        """
        clean_name = metavar_name.lstrip(cls.METAVAR_PREFIX).lower()
        param_type = cls.TYPE_MAPPING.get(clean_name, ParameterType.UNKNOWN)
        param_name = clean_name.replace(cls.NAME_SEPARATOR, "_")

        return {"name": param_name, "type": param_type}


class ParameterExtractor:
    """Extracts cryptographic parameters from semgrep results."""

    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root).resolve()

    def extract_from_semgrep_results(
        self, semgrep_results: Dict[str, Any]
    ) -> List[ExtractedParameter]:
        """
        Extract parameters from semgrep JSON results.

        Priority:
        1. Use semgrep metavariables (extra.metavars) - highest confidence
        2. Parse literals from code snippet (extra.lines) - medium confidence
        3. Mark as unextractable - requires manual review

        Args:
            semgrep_results: Parsed semgrep JSON output

        Returns:
            List of extracted parameters
        """
        if not isinstance(semgrep_results, dict):
            return []

        results = semgrep_results.get("results", [])
        if not isinstance(results, list):
            return []

        extracted = []

        for result in results:
            if not isinstance(result, dict):
                continue
            try:
                location = self._extract_location(result)
                extracted_params = self._extract_parameters_from_result(
                    result, location
                )
                extracted.extend(extracted_params)
            except (KeyError, TypeError, AttributeError):
                continue

        return extracted

    @staticmethod
    def _extract_location(result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract location information from semgrep result."""
        start = result.get("start", {})
        return {
            "file_path": result.get("path", ""),
            "line": start.get("line", 0),
            "column": start.get("col", 0),
            "check_id": result.get("check_id", ""),
        }

    def _extract_parameters_from_result(
        self, result: Dict[str, Any], location: Dict[str, Any]
    ) -> List[ExtractedParameter]:
        """Extract parameters from a single semgrep result."""
        extra = result.get("extra", {})
        metavars = extra.get("metavars", {})
        code_snippet = extra.get("lines", "")

        extracted = self._extract_from_metavars(metavars, location)
        if not extracted and code_snippet:
            extracted = self._extract_from_snippet(code_snippet, location)

        return extracted

    def _extract_from_metavars(
        self, metavars: Dict[str, Any], location: Dict[str, Any]
    ) -> List[ExtractedParameter]:
        """Extract parameters from semgrep metavariables."""
        extracted = []

        for metavar_name, metavar_data in metavars.items():
            abstract_content = metavar_data.get("abstract_content", "")
            if not abstract_content:
                continue

            parsed_value = LiteralParser.parse(abstract_content)
            if parsed_value is None:
                continue

            param_info = ParameterTypeMapper.infer(metavar_name)
            extracted.append(
                ExtractedParameter(
                    file_path=location["file_path"],
                    line=location["line"],
                    column=location["column"],
                    check_id=location["check_id"],
                    parameter_name=param_info["name"],
                    parameter_type=param_info["type"],
                    value=parsed_value,
                    confidence=Confidence.HIGH.value,
                    resolution_path=[
                        f"semgrep metavar {metavar_name}: {abstract_content}"
                    ],
                )
            )

        return extracted

    def _extract_from_snippet(
        self, code_snippet: str, location: Dict[str, Any]
    ) -> List[ExtractedParameter]:
        """Extract parameters from code snippet as fallback."""
        parsed_values = LiteralParser.extract_from_snippet(code_snippet)
        extracted = []

        for idx, value in enumerate(parsed_values, start=1):
            extracted.append(
                ExtractedParameter(
                    file_path=location["file_path"],
                    line=location["line"],
                    column=location["column"],
                    check_id=location["check_id"],
                    parameter_name=f"param_{idx}",
                    parameter_type=ParameterType.UNKNOWN,
                    value=value,
                    confidence=Confidence.MEDIUM.value,
                    resolution_path=[
                        f"parsed from code snippet: {code_snippet[: LiteralParser.SNIPPET_TRUNCATE_LENGTH]}..."
                    ],
                )
            )

        return extracted

    @staticmethod
    def _calculate_summary(
        extracted: List[ExtractedParameter],
    ) -> Dict[str, int]:
        """Calculate summary statistics for extracted parameters."""
        summary = {conf.value: 0 for conf in Confidence}
        for param in extracted:
            confidence = param.confidence
            if confidence in summary:
                summary[confidence] += 1
            else:
                summary[Confidence.UNEXTRACTABLE.value] += 1
        return summary


def load_semgrep_results(input_path: Optional[str]) -> Dict[str, Any]:
    """
    Load semgrep results from file or stdin.

    Args:
        input_path: Path to semgrep JSON file, or None to read from stdin

    Returns:
        Parsed semgrep JSON data

    Raises:
        FileNotFoundError: If input file doesn't exist
        PermissionError: If file cannot be read
        json.JSONDecodeError: If JSON parsing fails
        SystemExit: If stdin read fails
    """
    try:
        if input_path:
            with open(input_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return json.load(sys.stdin)
    except FileNotFoundError:
        print(f"ERROR: File not found: {input_path}", file=sys.stderr)
        raise
    except PermissionError:
        print(f"ERROR: Permission denied: {input_path}", file=sys.stderr)
        raise
    except json.JSONDecodeError as e:
        source = input_path or "stdin"
        print(f"ERROR: Invalid JSON in {source}: {e}", file=sys.stderr)
        raise


def save_results(extracted: List[ExtractedParameter], output_path: str) -> None:
    """
    Save extracted parameters to JSON file.

    Args:
        extracted: List of extracted parameters
        output_path: Output file path

    Raises:
        PermissionError: If file cannot be written
        OSError: If file system error occurs
    """
    try:
        summary = ParameterExtractor._calculate_summary(extracted)
        output_data = {
            "extracted_parameters": [asdict(param) for param in extracted],
            "total_extracted": len(extracted),
            "summary": summary,
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2)
    except PermissionError:
        print(f"ERROR: Permission denied writing to: {output_path}", file=sys.stderr)
        raise
    except OSError as e:
        print(f"ERROR: Failed to write file {output_path}: {e}", file=sys.stderr)
        raise


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Extract cryptographic parameters from semgrep results"
    )
    parser.add_argument(
        "--semgrep-results",
        type=str,
        default=None,
        help="Path to semgrep JSON results file (or read from stdin)",
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Output file path for extracted parameters JSON",
    )
    parser.add_argument(
        "--workspace-root",
        type=str,
        default=".",
        help="Workspace root directory (default: current directory)",
    )

    args = parser.parse_args()

    try:
        semgrep_data = load_semgrep_results(args.semgrep_results)
        extractor = ParameterExtractor(workspace_root=args.workspace_root)
        extracted = extractor.extract_from_semgrep_results(semgrep_data)

        save_results(extracted, args.output)

        print(f"Extracted {len(extracted)} parameters", file=sys.stderr)
        print(f"Results saved to {args.output}", file=sys.stderr)
    except (
        FileNotFoundError,
        PermissionError,
        json.JSONDecodeError,
        OSError,
        argparse.ArgumentError,
    ):
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
