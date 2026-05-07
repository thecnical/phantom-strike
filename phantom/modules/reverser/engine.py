"""
PhantomStrike Reverser Module — Binary analysis, ROP gadget discovery, and disassembly.

Provides:
  - analyze_binary()    — file type detection, string extraction, import/export analysis
  - find_rop_gadgets()  — ROP gadget enumeration via ROPgadget
  - disassemble()       — disassembly via r2pipe (radare2) with objdump fallback

All methods degrade gracefully when optional tools (ROPgadget, radare2, objdump,
strings, file) are not installed.  No unhandled exceptions are ever propagated
from any public method.
"""
from __future__ import annotations

import asyncio
import logging
import re
import shutil
import subprocess
from datetime import datetime

from phantom.modules.base import BaseModule, ModuleResult

logger = logging.getLogger("phantom.reverser")

# ---------------------------------------------------------------------------
# Install-hint constants
# ---------------------------------------------------------------------------
_FILE_ERR = "file utility not found — install binutils/file: apt install file"
_STRINGS_ERR = "strings utility not found — install binutils: apt install binutils"
_OBJDUMP_ERR = "objdump not found — install binutils: apt install binutils"
_ROPGADGET_ERR = "ROPgadget not installed — run: pip install ROPgadget"
_R2_ERR = "radare2 not installed — run: apt install radare2  (or: brew install radare2)"

# Strings that often indicate interesting / security-relevant content
_INTERESTING_PATTERNS = [
    r"(?i)password",
    r"(?i)passwd",
    r"(?i)secret",
    r"(?i)token",
    r"(?i)api[_\-]?key",
    r"(?i)http[s]?://",
    r"(?i)/etc/passwd",
    r"(?i)/etc/shadow",
    r"(?i)cmd\.exe",
    r"(?i)powershell",
    r"(?i)exec\b",
    r"(?i)system\b",
    r"(?i)popen\b",
    r"(?i)shellcode",
    r"(?i)exploit",
    r"(?i)overflow",
    r"(?i)format.string",
    r"(?i)use.after.free",
    r"(?i)heap.spray",
    r"(?i)rop.chain",
    r"(?i)mprotect",
    r"(?i)mmap",
    r"(?i)VirtualAlloc",
    r"(?i)WriteProcessMemory",
    r"(?i)CreateRemoteThread",
    r"(?i)LoadLibrary",
    r"(?i)GetProcAddress",
]

_INTERESTING_RE = [re.compile(p) for p in _INTERESTING_PATTERNS]

# Imports that are commonly associated with vulnerabilities / exploitation
_VULN_IMPORTS = {
    "gets": "CWE-120: Buffer overflow — gets() has no bounds checking",
    "strcpy": "CWE-120: Buffer overflow — strcpy() has no bounds checking",
    "strcat": "CWE-120: Buffer overflow — strcat() has no bounds checking",
    "sprintf": "CWE-134: Use of externally-controlled format string",
    "scanf": "CWE-120: Buffer overflow — scanf() with %s has no bounds checking",
    "system": "CWE-78: OS command injection risk",
    "popen": "CWE-78: OS command injection risk",
    "exec": "CWE-78: OS command injection risk",
    "execve": "CWE-78: OS command injection risk",
    "execl": "CWE-78: OS command injection risk",
    "execlp": "CWE-78: OS command injection risk",
    "execvp": "CWE-78: OS command injection risk",
    "printf": "CWE-134: Potential format string vulnerability if user-controlled",
    "fprintf": "CWE-134: Potential format string vulnerability if user-controlled",
    "syslog": "CWE-134: Potential format string vulnerability if user-controlled",
    "alloca": "CWE-770: Stack allocation without bounds check",
    "malloc": "CWE-789: Uncontrolled memory allocation (check return value)",
    "realloc": "CWE-789: Uncontrolled memory allocation (check return value)",
    "memcpy": "CWE-120: Buffer overflow — verify destination size",
    "memmove": "CWE-120: Buffer overflow — verify destination size",
    "strncpy": "CWE-170: Improper null-termination if n == dest size",
    "strncat": "CWE-170: Improper null-termination risk",
    "rand": "CWE-338: Use of cryptographically weak PRNG",
    "srand": "CWE-338: Use of cryptographically weak PRNG",
    "setuid": "CWE-250: Execution with unnecessary privileges",
    "setgid": "CWE-250: Execution with unnecessary privileges",
}


class ReverserEngine(BaseModule):
    """
    Binary reverse-engineering module.

    Provides static analysis capabilities:
      - analyze_binary()   — file type, strings, imports/exports, potential vulns
      - find_rop_gadgets() — ROP gadget enumeration via ROPgadget
      - disassemble()      — disassembly via r2pipe (radare2) or objdump fallback

    Optional dependencies:
      - file, strings, objdump  (analyze_binary, disassemble)
      - ROPgadget               (find_rop_gadgets)
      - r2pipe / radare2        (disassemble — preferred)
    """

    # ------------------------------------------------------------------ #
    # BaseModule interface                                                 #
    # ------------------------------------------------------------------ #

    @property
    def name(self) -> str:
        return "phantom-reverser"

    @property
    def description(self) -> str:
        return "Binary analysis — file type detection, string extraction, ROP gadgets, disassembly"

    @property
    def category(self) -> str:
        return "reverse_engineering"

    async def _setup(self) -> None:
        """Probe optional tool availability and set flags."""
        self._file_available = shutil.which("file") is not None
        self._strings_available = shutil.which("strings") is not None
        self._objdump_available = shutil.which("objdump") is not None

        # ROPgadget — Python package with a CLI entry-point
        self._ropgadget_available = shutil.which("ROPgadget") is not None
        if not self._ropgadget_available:
            # Some installs expose it as ropgadget (lowercase)
            self._ropgadget_available = shutil.which("ropgadget") is not None

        # r2pipe — Python binding for radare2
        try:
            import r2pipe  # noqa: F401
            self._r2pipe_available = shutil.which("r2") is not None or \
                                     shutil.which("radare2") is not None
        except ImportError:
            self._r2pipe_available = False

        if not self._file_available:
            logger.warning("file utility not found — binary type detection disabled. %s", _FILE_ERR)
        if not self._strings_available:
            logger.warning("strings utility not found — string extraction disabled. %s", _STRINGS_ERR)
        if not self._objdump_available:
            logger.warning("objdump not found — import/export analysis disabled. %s", _OBJDUMP_ERR)
        if not self._ropgadget_available:
            logger.warning("ROPgadget not installed — ROP gadget search disabled. %s", _ROPGADGET_ERR)
        if not self._r2pipe_available:
            logger.warning("r2pipe/radare2 not available — disassembly will use objdump. %s", _R2_ERR)

    async def run(self, target: str, options: dict = None) -> ModuleResult:
        """
        Primary entry-point.  Dispatches to the appropriate sub-operation
        based on ``options["operation"]``.

        Supported operations: analyze, rop_gadgets, disassemble.
        Defaults to analyze when no operation is specified.
        """
        options = options or {}
        operation = options.get("operation", "analyze")

        try:
            if operation == "rop_gadgets":
                return await self.find_rop_gadgets(target)
            elif operation == "disassemble":
                return await self.disassemble(target)
            else:
                return await self.analyze_binary(target)
        except Exception as exc:  # pragma: no cover — safety net
            logger.exception("Unexpected error in ReverserEngine.run()")
            return ModuleResult(
                module_name=self.name,
                operation=operation,
                success=False,
                errors=[f"Unexpected error: {exc}"],
                start_time=datetime.now(),
                end_time=datetime.now(),
            )

    # ------------------------------------------------------------------ #
    # Public reverser methods                                              #
    # ------------------------------------------------------------------ #

    async def analyze_binary(self, binary_path: str) -> ModuleResult:
        """
        Perform static analysis on a binary file.

        Runs ``file``, ``strings``, and ``objdump`` on the binary to extract:
          - file_type        : output of the ``file`` command
          - imports          : list of imported symbols (from objdump -d / -T)
          - exports          : list of exported symbols
          - interesting_strings : strings matching security-relevant patterns
          - potential_vulns  : list of {symbol, description} dicts for dangerous imports

        Returns a ModuleResult with ``data`` containing the above keys.
        Missing tools are reported in ``errors`` with install instructions;
        the method still returns partial results from whichever tools are available.
        """
        start_time = datetime.now()
        operation = "analyze"
        errors: list[str] = []

        # Require at least one analysis tool
        if not self._file_available and not self._strings_available and not self._objdump_available:
            return ModuleResult(
                module_name=self.name,
                operation=operation,
                success=False,
                errors=[_FILE_ERR, _STRINGS_ERR, _OBJDUMP_ERR],
                start_time=start_time,
                end_time=datetime.now(),
            )

        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                self._analyze_binary_sync,
                binary_path,
            )
        except FileNotFoundError:
            return ModuleResult(
                module_name=self.name,
                operation=operation,
                success=False,
                errors=[f"Binary not found: {binary_path}"],
                start_time=start_time,
                end_time=datetime.now(),
            )
        except PermissionError:
            return ModuleResult(
                module_name=self.name,
                operation=operation,
                success=False,
                errors=[f"Permission denied reading binary: {binary_path}"],
                start_time=start_time,
                end_time=datetime.now(),
            )
        except Exception as exc:
            logger.error("analyze_binary error: %s", exc)
            return ModuleResult(
                module_name=self.name,
                operation=operation,
                success=False,
                errors=[str(exc)],
                start_time=start_time,
                end_time=datetime.now(),
            )

        # Merge tool-unavailability warnings into errors list
        errors.extend(result.pop("_tool_errors", []))

        findings_count = (
            len(result.get("imports", []))
            + len(result.get("exports", []))
            + len(result.get("interesting_strings", []))
            + len(result.get("potential_vulns", []))
        )

        logger.info(
            "[Reverser] analyze_binary: %s — %d imports, %d exports, "
            "%d interesting strings, %d potential vulns",
            binary_path,
            len(result.get("imports", [])),
            len(result.get("exports", [])),
            len(result.get("interesting_strings", [])),
            len(result.get("potential_vulns", [])),
        )

        return ModuleResult(
            module_name=self.name,
            operation=operation,
            success=True,
            data=result,
            errors=errors,
            findings_count=findings_count,
            start_time=start_time,
            end_time=datetime.now(),
        )

    async def find_rop_gadgets(self, binary_path: str) -> ModuleResult:
        """
        Enumerate ROP gadgets in a binary using ROPgadget.

        Returns a ModuleResult whose ``data["gadgets"]`` is a list of dicts:
          {"address": str, "gadget": str}

        Returns ModuleResult(success=False) when ROPgadget is not installed.
        """
        start_time = datetime.now()
        operation = "rop_gadgets"

        if not self._ropgadget_available:
            return ModuleResult(
                module_name=self.name,
                operation=operation,
                success=False,
                errors=[_ROPGADGET_ERR],
                start_time=start_time,
                end_time=datetime.now(),
            )

        try:
            gadgets = await asyncio.get_event_loop().run_in_executor(
                None,
                self._find_rop_gadgets_sync,
                binary_path,
            )
        except FileNotFoundError:
            return ModuleResult(
                module_name=self.name,
                operation=operation,
                success=False,
                errors=[f"Binary not found: {binary_path}"],
                start_time=start_time,
                end_time=datetime.now(),
            )
        except PermissionError:
            return ModuleResult(
                module_name=self.name,
                operation=operation,
                success=False,
                errors=[f"Permission denied reading binary: {binary_path}"],
                start_time=start_time,
                end_time=datetime.now(),
            )
        except Exception as exc:
            logger.error("find_rop_gadgets error: %s", exc)
            return ModuleResult(
                module_name=self.name,
                operation=operation,
                success=False,
                errors=[str(exc)],
                start_time=start_time,
                end_time=datetime.now(),
            )

        logger.info("[Reverser] find_rop_gadgets: found %d gadgets in %s", len(gadgets), binary_path)

        return ModuleResult(
            module_name=self.name,
            operation=operation,
            success=True,
            data={"gadgets": gadgets, "binary_path": binary_path, "count": len(gadgets)},
            findings_count=len(gadgets),
            start_time=start_time,
            end_time=datetime.now(),
        )

    async def disassemble(self, binary_path: str) -> ModuleResult:
        """
        Disassemble a binary using r2pipe (radare2) if available, falling back
        to objdump when radare2 is not installed.

        Returns a ModuleResult whose ``data["disassembly"]`` is a string
        containing the disassembly output.

        Returns ModuleResult(success=False) when neither tool is available.
        """
        start_time = datetime.now()
        operation = "disassemble"

        if not self._r2pipe_available and not self._objdump_available:
            return ModuleResult(
                module_name=self.name,
                operation=operation,
                success=False,
                errors=[_R2_ERR, _OBJDUMP_ERR],
                start_time=start_time,
                end_time=datetime.now(),
            )

        try:
            disassembly, tool_used = await asyncio.get_event_loop().run_in_executor(
                None,
                self._disassemble_sync,
                binary_path,
            )
        except FileNotFoundError:
            return ModuleResult(
                module_name=self.name,
                operation=operation,
                success=False,
                errors=[f"Binary not found: {binary_path}"],
                start_time=start_time,
                end_time=datetime.now(),
            )
        except PermissionError:
            return ModuleResult(
                module_name=self.name,
                operation=operation,
                success=False,
                errors=[f"Permission denied reading binary: {binary_path}"],
                start_time=start_time,
                end_time=datetime.now(),
            )
        except Exception as exc:
            logger.error("disassemble error: %s", exc)
            return ModuleResult(
                module_name=self.name,
                operation=operation,
                success=False,
                errors=[str(exc)],
                start_time=start_time,
                end_time=datetime.now(),
            )

        logger.info(
            "[Reverser] disassemble: %s — %d chars via %s",
            binary_path, len(disassembly), tool_used,
        )

        return ModuleResult(
            module_name=self.name,
            operation=operation,
            success=True,
            data={
                "disassembly": disassembly,
                "binary_path": binary_path,
                "tool_used": tool_used,
            },
            findings_count=1,
            start_time=start_time,
            end_time=datetime.now(),
        )

    # ------------------------------------------------------------------ #
    # Synchronous helpers (run in executor to avoid blocking the loop)    #
    # ------------------------------------------------------------------ #

    def _analyze_binary_sync(self, binary_path: str) -> dict:
        """
        Run file, strings, and objdump on the binary and return a dict with:
          file_type, imports, exports, interesting_strings, potential_vulns,
          _tool_errors (internal — stripped before returning to caller).

        Raises FileNotFoundError / PermissionError on I/O problems.
        """
        import os
        # Validate path exists and is readable
        if not os.path.exists(binary_path):
            raise FileNotFoundError(binary_path)
        if not os.access(binary_path, os.R_OK):
            raise PermissionError(binary_path)

        tool_errors: list[str] = []
        file_type = ""
        all_strings: list[str] = []
        imports: list[str] = []
        exports: list[str] = []

        # ---- file -------------------------------------------------------
        if self._file_available:
            try:
                proc = subprocess.run(
                    ["file", binary_path],
                    capture_output=True, text=True, timeout=30,
                )
                file_type = proc.stdout.strip()
                # Strip the path prefix: "binary_path: ELF 64-bit ..." → "ELF 64-bit ..."
                if ": " in file_type:
                    file_type = file_type.split(": ", 1)[1]
            except subprocess.TimeoutExpired:
                tool_errors.append("file command timed out")
            except Exception as exc:
                tool_errors.append(f"file command failed: {exc}")
        else:
            tool_errors.append(_FILE_ERR)

        # ---- strings ----------------------------------------------------
        if self._strings_available:
            try:
                proc = subprocess.run(
                    ["strings", "-n", "4", binary_path],
                    capture_output=True, text=True, timeout=60,
                )
                all_strings = [s.strip() for s in proc.stdout.splitlines() if s.strip()]
            except subprocess.TimeoutExpired:
                tool_errors.append("strings command timed out")
            except Exception as exc:
                tool_errors.append(f"strings command failed: {exc}")
        else:
            tool_errors.append(_STRINGS_ERR)

        # ---- objdump — imports / exports --------------------------------
        if self._objdump_available:
            imports, exports = self._parse_objdump_symbols(binary_path, tool_errors)
        else:
            tool_errors.append(_OBJDUMP_ERR)

        # ---- interesting strings ----------------------------------------
        interesting_strings = [
            s for s in all_strings
            if any(pattern.search(s) for pattern in _INTERESTING_RE)
        ]

        # ---- potential vulnerabilities from imports ---------------------
        potential_vulns = []
        all_symbols = set(imports + exports)
        for sym in all_symbols:
            # Strip common decorators: @plt, @GLIBC_2.17, leading underscores
            clean = re.sub(r"@.*$", "", sym).lstrip("_")
            if clean in _VULN_IMPORTS:
                potential_vulns.append({
                    "symbol": sym,
                    "description": _VULN_IMPORTS[clean],
                })

        return {
            "file_type": file_type,
            "imports": imports,
            "exports": exports,
            "interesting_strings": interesting_strings,
            "potential_vulns": potential_vulns,
            "binary_path": binary_path,
            "_tool_errors": tool_errors,
        }

    def _parse_objdump_symbols(
        self, binary_path: str, tool_errors: list[str]
    ) -> tuple[list[str], list[str]]:
        """
        Parse imports and exports from objdump output.

        Uses ``objdump -T`` (dynamic symbol table) for ELF binaries.
        Falls back to ``objdump -t`` (full symbol table) if -T fails.

        Returns (imports, exports) as lists of symbol name strings.
        """
        imports: list[str] = []
        exports: list[str] = []

        for flag, label in [("-T", "dynamic"), ("-t", "static")]:
            try:
                proc = subprocess.run(
                    ["objdump", flag, binary_path],
                    capture_output=True, text=True, timeout=60,
                )
                if proc.returncode != 0:
                    # -T fails on static binaries; try -t next iteration
                    continue

                for line in proc.stdout.splitlines():
                    parts = line.split()
                    if len(parts) < 2:
                        continue
                    # objdump -T format: addr bind type vis ndx name
                    # objdump -t format: addr flags section size name
                    # We look for lines with a symbol name in the last column
                    sym_name = parts[-1]
                    if not sym_name or sym_name.startswith("."):
                        continue

                    line_lower = line.lower()
                    # UND = undefined = imported from external library
                    if "*und*" in line_lower or " u " in line_lower or "\tUND\t" in line:
                        if sym_name not in imports:
                            imports.append(sym_name)
                    else:
                        if sym_name not in exports:
                            exports.append(sym_name)

                # If we got results, no need to try the fallback flag
                if imports or exports:
                    break

            except subprocess.TimeoutExpired:
                tool_errors.append(f"objdump {flag} timed out")
                break
            except Exception as exc:
                tool_errors.append(f"objdump {flag} failed: {exc}")
                break

        return imports, exports

    def _find_rop_gadgets_sync(self, binary_path: str) -> list[dict]:
        """
        Run ROPgadget on the binary and parse the output into a list of
        {"address": str, "gadget": str} dicts.

        Raises FileNotFoundError / PermissionError on I/O problems.
        """
        import os
        if not os.path.exists(binary_path):
            raise FileNotFoundError(binary_path)
        if not os.access(binary_path, os.R_OK):
            raise PermissionError(binary_path)

        # Prefer the capitalised entry-point; fall back to lowercase
        ropgadget_bin = shutil.which("ROPgadget") or shutil.which("ropgadget") or "ROPgadget"

        try:
            proc = subprocess.run(
                [ropgadget_bin, "--binary", binary_path],
                capture_output=True, text=True, timeout=120,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("ROPgadget timed out — binary may be very large")
        except FileNotFoundError:
            raise RuntimeError(_ROPGADGET_ERR)

        gadgets: list[dict] = []
        # ROPgadget output format:
        #   0x0000000000401234 : pop rdi ; ret
        gadget_re = re.compile(r"^(0x[0-9a-fA-F]+)\s*:\s*(.+)$")
        for line in proc.stdout.splitlines():
            m = gadget_re.match(line.strip())
            if m:
                gadgets.append({"address": m.group(1), "gadget": m.group(2).strip()})

        return gadgets

    def _disassemble_sync(self, binary_path: str) -> tuple[str, str]:
        """
        Disassemble the binary.  Tries r2pipe first; falls back to objdump.

        Returns (disassembly_text, tool_name).
        Raises FileNotFoundError / PermissionError on I/O problems.
        """
        import os
        if not os.path.exists(binary_path):
            raise FileNotFoundError(binary_path)
        if not os.access(binary_path, os.R_OK):
            raise PermissionError(binary_path)

        # ---- r2pipe (radare2) -------------------------------------------
        if self._r2pipe_available:
            try:
                import r2pipe
                r2 = r2pipe.open(binary_path, flags=["-2"])  # -2 suppresses stderr
                try:
                    # Analyse all functions, then print disassembly of main
                    r2.cmd("aaa")
                    disasm = r2.cmd("pdf @ main")
                    if not disasm or disasm.strip() == "":
                        # Fallback: disassemble from entry point
                        disasm = r2.cmd("pd 200 @ entry0")
                    if not disasm or disasm.strip() == "":
                        # Last resort: print first 200 instructions
                        disasm = r2.cmd("pd 200")
                finally:
                    r2.quit()
                if disasm and disasm.strip():
                    return disasm, "r2pipe"
            except Exception as exc:
                logger.warning("[Reverser] r2pipe disassembly failed (%s), falling back to objdump", exc)

        # ---- objdump fallback -------------------------------------------
        if self._objdump_available:
            try:
                proc = subprocess.run(
                    ["objdump", "-d", "-M", "intel", binary_path],
                    capture_output=True, text=True, timeout=120,
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    return proc.stdout, "objdump"
                # Some binaries need AT&T syntax (default) — retry without -M intel
                proc2 = subprocess.run(
                    ["objdump", "-d", binary_path],
                    capture_output=True, text=True, timeout=120,
                )
                if proc2.returncode == 0 and proc2.stdout.strip():
                    return proc2.stdout, "objdump"
                raise RuntimeError(
                    f"objdump failed (rc={proc.returncode}): {proc.stderr.strip()}"
                )
            except subprocess.TimeoutExpired:
                raise RuntimeError("objdump timed out — binary may be very large")

        raise RuntimeError("No disassembly tool available")
