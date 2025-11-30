"""
Analyze kernel and node tuning state from a live OpenShift node or an extracted
Linux sosreport directory. The script inspects procfs/sysfs snapshots for
signals related to CPU isolation, IRQ affinity, huge pages, and networking
queues, then emits actionable tuning recommendations.

The implementation remains dependency-free so it can run anywhere Python 3.8+
is available (CI, developer workstations, or automation pipelines).
"""

from __future__ import annotations

import argparse
import atexit
import json
import os
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class EnvironmentPaths:
    base: Path
    proc: Path
    sys: Path
    sos_commands: Optional[Path]


DEFAULT_OC_BINARY = os.environ.get("OC_BIN", "oc")
DEFAULT_TOOLBOX_IMAGE = os.environ.get("TOOLBOX_IMAGE", "registry.redhat.io/rhel9/support-tools:latest")

DEFAULT_SOSREPORT_FLAGS: List[str] = [
    "-e",
    "openshift",
    "-e",
    "openshift_ovn",
    "-e",
    "openvswitch",
    "-e",
    "podman",
    "-e",
    "crio",
    "-k",
    "crio.all=on",
    "-k",
    "crio.logs=on",
    "-k",
    "podman.all=on",
    "-k",
    "podman.logs=on",
    "-k",
    "networking.ethtool-namespaces=off",
    "--all-logs",
    "--plugin-timeout=600",
]

SNAPSHOT_ITEMS = [
    "proc/cmdline",
    "proc/cpuinfo",
    "proc/meminfo",
    "proc/net",
    "proc/irq",
    "proc/sys",
    "proc/uptime",
    "proc/version",
    "proc/sys/kernel",
    "proc/sys/vm",
    "proc/sys/net",
    "proc/net/netstat",
    "proc/net/snmp",
    "proc/net/sockstat",
    "sys/devices/system/node",
    "sys/kernel/mm/transparent_hugepage",
]


def parse_arguments(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze kernel tuning signals from a live node (/proc, /sys) or an "
            "extracted sosreport directory."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--sosreport",
        help=(
            "Path to an extracted sosreport directory. The script will locate the "
            "embedded proc/ and sys/ trees automatically."
        ),
    )
    parser.add_argument(
        "--root",
        default="",
        help=(
            "Root path of a filesystem snapshot containing proc/ and sys/ "
            "(defaults to the live '/' filesystem when unset)."
        ),
    )
    parser.add_argument(
        "--proc-root",
        help="Explicit path to the procfs tree. Overrides auto-detection.",
    )
    parser.add_argument(
        "--sys-root",
        help="Explicit path to the sysfs tree. Overrides auto-detection.",
    )
    parser.add_argument(
        "--node",
        help=(
            "OpenShift node name to inspect via `oc debug node/<name>`. "
            "The script captures relevant /proc and /sys data using the provided KUBECONFIG."
        ),
    )
    parser.add_argument(
        "--kubeconfig",
        help="Path to the kubeconfig file used for oc debug commands (defaults to current oc context).",
    )
    parser.add_argument(
        "--oc-binary",
        default=DEFAULT_OC_BINARY,
        help="Path to the oc CLI binary.",
    )
    parser.add_argument(
        "--keep-snapshot",
        action="store_true",
        help="Keep temporary artifacts (oc-debug snapshots or sosreports) instead of deleting them on exit.",
    )
    parser.add_argument(
        "--collect-sosreport",
        dest="collect_sosreport",
        action="store_true",
        help=(
            "Use `oc debug node/<name>` to run sosreport on the target node, download the archive, "
            "and analyze it as an extracted sosreport."
        ),
    )
    parser.add_argument(
        "--no-collect-sosreport",
        dest="collect_sosreport",
        action="store_false",
        help="Disable automatic sosreport collection when targeting a live cluster via --node.",
    )
    parser.set_defaults(collect_sosreport=True)
    parser.add_argument(
        "--sosreport-output",
        help=(
            "Optional directory to store downloaded sosreport archives and their extraction. "
            "Defaults to a temporary directory when omitted."
        ),
    )
    parser.add_argument(
        "--toolbox-image",
        default=DEFAULT_TOOLBOX_IMAGE,
        help="Container image used by toolbox when collecting sosreport (default: %(default)s).",
    )
    parser.add_argument(
        "--sosreport-arg",
        action="append",
        default=[],
        metavar="ARG",
        help="Additional argument to pass to the sosreport command (repeatable).",
    )
    parser.add_argument(
        "--skip-default-sosreport-flags",
        action="store_true",
        help="Do not include the default OpenShift-focused sosreport flags; only use custom --sosreport-arg values.",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Output format.",
    )
    parser.add_argument(
        "--output",
        help="Optional path to write the report. Defaults to stdout when omitted.",
    )
    parser.add_argument(
        "--max-irq-samples",
        type=int,
        default=15,
        help="Limit how many IRQ affinity mismatches are included in the report.",
    )
    return parser.parse_args(argv)


def resolve_environment(args: argparse.Namespace) -> EnvironmentPaths:
    collect_pref = args.collect_sosreport
    if collect_pref and not args.node:
        # Cannot collect sosreport without a target node; defer to other sources.
        collect_pref = False

    if collect_pref:
        if args.sosreport:
            raise ValueError("Cannot combine --collect-sosreport with --sosreport.")
        if not args.node:
            raise ValueError("Sosreport collection requires --node.")
        sos_dir = collect_sosreport_via_oc_debug(
            node=args.node,
            oc_binary=args.oc_binary,
            kubeconfig=args.kubeconfig,
            keep_snapshot=args.keep_snapshot,
            output_base=args.sosreport_output,
            toolbox_image=args.toolbox_image,
            proxy_exports_script=_build_proxy_exports_script(),
            sosreport_flag_string=_build_sosreport_flag_string(
                use_defaults=not args.skip_default_sosreport_flags,
                extra_args=args.sosreport_arg,
            ),
        )
        return _resolve_sosreport_dir(sos_dir)

    if args.sosreport:
        return _resolve_sosreport_dir(Path(args.sosreport))

    if args.node:
        return capture_node_snapshot(
            node=args.node,
            oc_binary=args.oc_binary,
            kubeconfig=args.kubeconfig,
            keep_snapshot=args.keep_snapshot,
        )

    root = Path(args.root or "/").expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"root path '{root}' does not exist")
    proc_root = Path(args.proc_root).expanduser().resolve() if args.proc_root else root / "proc"
    sys_root = Path(args.sys_root).expanduser().resolve() if args.sys_root else root / "sys"
    if not proc_root.is_dir():
        raise FileNotFoundError(f"proc path '{proc_root}' does not exist or is not a directory")
    if not sys_root.is_dir():
        raise FileNotFoundError(f"sys path '{sys_root}' does not exist or is not a directory")
    return EnvironmentPaths(base=root, proc=proc_root, sys=sys_root, sos_commands=None)


def _safe_extract_tar(archive: Path, destination: Path) -> None:
    with tarfile.open(archive, "r:*") as tar:
        for member in tar.getmembers():
            member_path = destination / member.name
            if not _is_within_directory(destination, member_path):
                raise ValueError("Archive extraction attempted path traversal.")
        tar.extractall(destination)


def _is_within_directory(directory: Path, target: Path) -> bool:
    directory = directory.resolve()
    if not directory.exists():
        directory.mkdir(parents=True, exist_ok=True)
    try:
        target.resolve(strict=False).relative_to(directory)
        return True
    except ValueError:
        return False


def _create_artifact_dir(base_dir: Optional[str], prefix: str) -> Path:
    if base_dir:
        base = Path(base_dir).expanduser().resolve()
        base.mkdir(parents=True, exist_ok=True)
        path = Path(tempfile.mkdtemp(prefix=f"{prefix}-", dir=str(base)))
    else:
        path = Path(tempfile.mkdtemp(prefix=f"{prefix}-"))
    return path


def _resolve_sosreport_dir(path: Path) -> EnvironmentPaths:
    base = Path(path).expanduser().resolve()
    if not base.exists():
        raise FileNotFoundError(f"sosreport path '{base}' does not exist")
    if base.is_file():
        raise ValueError(f"sosreport path '{base}' is a file; provide an extracted directory")
    root_candidates = [base] + [child for child in base.iterdir() if child.is_dir()]
    proc_root: Optional[Path] = None
    sys_root: Optional[Path] = None
    sos_commands: Optional[Path] = None
    selected_base = base
    for candidate in root_candidates:
        candidate_proc = candidate / "proc"
        if candidate_proc.is_dir():
            proc_root = candidate_proc
        candidate_sys = candidate / "sys"
        if candidate_sys.is_dir():
            sys_root = candidate_sys
        if (candidate / "sos_commands").is_dir():
            sos_commands = candidate / "sos_commands"
        if proc_root and sys_root:
            selected_base = candidate
            break
    if proc_root is None:
        raise FileNotFoundError(f"Unable to locate a proc/ directory under '{base}'")
    if sys_root is None:
        possible_sys = proc_root.parent / "sys"
        if possible_sys.is_dir():
            sys_root = possible_sys
        else:
            raise FileNotFoundError(f"Unable to locate a sys/ directory under '{base}'")
    return EnvironmentPaths(base=selected_base, proc=proc_root, sys=sys_root, sos_commands=sos_commands)


def _build_proxy_exports_script() -> str:
    proxy_vars = [
        "HTTP_PROXY",
        "http_proxy",
        "HTTPS_PROXY",
        "https_proxy",
        "NO_PROXY",
        "no_proxy",
    ]
    lines = []
    for var in proxy_vars:
        value = os.environ.get(var)
        if value:
            lines.append(f"export {var}={shlex.quote(value)}")
    return "\n".join(lines)


def _build_sosreport_flag_string(*, use_defaults: bool, extra_args: Sequence[str]) -> str:
    flags: List[str] = []
    if use_defaults:
        flags.extend(DEFAULT_SOSREPORT_FLAGS)
    flags.extend(extra_args)
    if not flags:
        return ""
    return " ".join(shlex.quote(flag) for flag in flags)


def collect_sosreport_via_oc_debug(
    *,
    node: str,
    oc_binary: str,
    kubeconfig: Optional[str],
    keep_snapshot: bool,
    output_base: Optional[str],
    toolbox_image: str,
    proxy_exports_script: str,
    sosreport_flag_string: str,
) -> Path:
    safe_node = node.replace("/", "-")
    artifact_dir = _create_artifact_dir(output_base, f"node-tuning-sosreport-{safe_node}")
    if not keep_snapshot:
        atexit.register(lambda: shutil.rmtree(artifact_dir, ignore_errors=True))

    archive_path = artifact_dir / "sosreport.tar"
    extract_dir = artifact_dir / "extracted"
    extract_dir.mkdir(parents=True, exist_ok=True)

    archive_host_path = "/tmp/node-tuning-sosreport.tar.xz"
    payload_host_path = "/tmp/node-tuning-toolbox.sh"
    proxy_block = ""
    if proxy_exports_script.strip():
        proxy_block = textwrap.dedent(
            f"""
            PROXY_EXPORTS=$(cat <<'__NTO_PROXY__'
            {proxy_exports_script}
            __NTO_PROXY__
            )
            eval "$PROXY_EXPORTS"
            """
        ).strip()

    sosreport_flag_string = sosreport_flag_string or ""
    remote_script = textwrap.dedent(
        f"""
        set -euo pipefail
        TOOLBOX_IMAGE={shlex.quote(toolbox_image)}
        ARCHIVE_PATH="{archive_host_path}"
        PAYLOAD="{payload_host_path}"
        TOOLBOX_LOG="/tmp/node-tuning-toolbox.log"
        {proxy_block}
        cat <<'__NTO_PAYLOAD__' > "$PAYLOAD"
        set -euo pipefail
        TMPDIR=$(mktemp -d /var/tmp/node-tuning-sos.XXXX)
        cleanup() {{ rm -rf "$TMPDIR"; }}
        trap cleanup EXIT
        SOSREPORT_FLAGS="{sosreport_flag_string}"
        sosreport --batch --quiet --tmp-dir "$TMPDIR" $SOSREPORT_FLAGS >/dev/null
        LATEST=$(ls -1tr "$TMPDIR"/sosreport-* 2>/dev/null | tail -1)
        if [ -z "$LATEST" ]; then
          echo "Unable to locate sosreport archive" >&2
          exit 1
        fi
        mkdir -p "$(dirname "/host{archive_host_path}")"
        cp "$LATEST" "/host{archive_host_path}"
        __NTO_PAYLOAD__

        remove_existing() {{
          podman rm -f toolbox- >/dev/null 2>&1 || true
          toolbox rm -f node-tuning-sos >/dev/null 2>&1 || true
        }}

        remove_existing

        run_toolbox() {{
          local status=0
          if command -v script >/dev/null 2>&1; then
            script -q -c "toolbox --container node-tuning-sos --image $TOOLBOX_IMAGE -- /bin/bash /host$PAYLOAD" /dev/null >> "$TOOLBOX_LOG" 2>&1 || status=$?
          else
            toolbox --container node-tuning-sos --image "$TOOLBOX_IMAGE" -- /bin/bash "/host$PAYLOAD" >> "$TOOLBOX_LOG" 2>&1 || status=$?
          fi
          return "$status"
        }}

        if ! run_toolbox; then
          echo "toolbox execution failed; falling back to host sosreport (inspect $TOOLBOX_LOG)" >&2
          if ! bash "/host$PAYLOAD" >> "$TOOLBOX_LOG" 2>&1; then
            echo "host sosreport fallback failed; inspect $TOOLBOX_LOG" >&2
            exit 1
          fi
        fi

        rm -f "$PAYLOAD"

        if [ ! -s "{archive_host_path}" ]; then
          echo "sosreport archive missing after execution; inspect $TOOLBOX_LOG" >&2
          exit 1
        fi

        cat "{archive_host_path}"
        rm -f "{archive_host_path}" "$TOOLBOX_LOG"
        """
    ).strip()

    cmd: List[str] = [oc_binary]
    if kubeconfig:
        cmd.extend(["--kubeconfig", kubeconfig])
    cmd.extend(
        [
            "debug",
            f"node/{node}",
            "--quiet",
            "--",
            "/bin/bash",
            "-c",
            f"chroot /host /bin/bash -c {shlex.quote(remote_script)}",
        ]
    )

    try:
        with archive_path.open("wb") as archive_handle:
            result = subprocess.run(
                cmd,
                check=False,
                stdout=archive_handle,
                stderr=subprocess.PIPE,
                text=True,
            )
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Unable to execute oc binary '{oc_binary}': {exc}") from exc

    if result.returncode != 0:
        stderr_output = result.stderr.strip() if result.stderr else "unknown error"
        raise RuntimeError(f"`oc debug node/{node}` sosreport capture failed: {stderr_output}")

    _safe_extract_tar(archive_path, extract_dir)

    # Choose the first directory that contains proc/.
    candidates = [p for p in extract_dir.rglob("proc") if p.is_dir()]
    if not candidates:
        raise FileNotFoundError("Downloaded sosreport archive did not contain a proc/ directory.")
    sos_base = candidates[0].parent
    return sos_base


def capture_node_snapshot(
    *,
    node: str,
    oc_binary: str,
    kubeconfig: Optional[str],
    keep_snapshot: bool,
) -> EnvironmentPaths:
    tmp_dir = Path(tempfile.mkdtemp(prefix="node-tuning-"))
    if not keep_snapshot:
        atexit.register(lambda: shutil.rmtree(tmp_dir, ignore_errors=True))

    tar_path = tmp_dir / "snapshot.tar"
    include_args = " ".join(shlex.quote(item) for item in SNAPSHOT_ITEMS)
    remote_cmd = (
        "chroot /host /bin/bash -c "
        f"'cd / && tar --ignore-failed-read --warning=no-file-changed -cf - {include_args}'"
    )

    cmd: List[str] = [oc_binary]
    if kubeconfig:
        cmd.extend(["--kubeconfig", kubeconfig])
    cmd.extend(["debug", f"node/{node}", "--quiet", "--", "/bin/bash", "-c", remote_cmd])

    try:
        with tar_path.open("wb") as tar_handle:
            result = subprocess.run(
                cmd,
                check=False,
                stdout=tar_handle,
                stderr=subprocess.PIPE,
                text=True,
            )
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"Unable to execute oc binary '{oc_binary}': {exc}"
        ) from exc

    if result.returncode != 0:
        stderr_output = result.stderr.strip() if result.stderr else "unknown error"
        raise RuntimeError(
            f"`oc debug node/{node}` failed (exit {result.returncode}): {stderr_output}"
        )

    _safe_extract_tar(tar_path, tmp_dir)
    if not keep_snapshot:
        tar_path.unlink(missing_ok=True)  # type: ignore[arg-type]

    proc_path = tmp_dir / "proc"
    sys_path = tmp_dir / "sys"
    if not proc_path.exists():
        raise FileNotFoundError("Captured snapshot is missing proc/ data from the node.")
    if not sys_path.exists():
        raise FileNotFoundError("Captured snapshot is missing sys/ data from the node.")
    return EnvironmentPaths(base=tmp_dir, proc=proc_path, sys=sys_path, sos_commands=None)


def _safe_read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except (FileNotFoundError, IsADirectoryError, PermissionError):
        return None


def _safe_read_int(path: Path) -> Optional[int]:
    text = _safe_read_text(path)
    if text is None:
        return None
    text = text.strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _parse_kernel_cmdline(raw_cmdline: Optional[str]) -> Tuple[str, Dict[str, List[str]]]:
    if not raw_cmdline:
        return "", {}
    cmdline = raw_cmdline.replace("\x00", " ").strip()
    params: Dict[str, List[str]] = {}
    for token in cmdline.split():
        if "=" in token:
            key, value = token.split("=", 1)
        else:
            key, value = token, ""
        params.setdefault(key, []).append(value)
    return cmdline, params


def _parse_cpu_list(expression: str) -> List[int]:
    cpus: List[int] = []
    for part in expression.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_str, end_str = part.split("-", 1)
            try:
                start = int(start_str)
                end = int(end_str)
            except ValueError:
                continue
            cpus.extend(range(min(start, end), max(start, end) + 1))
        else:
            try:
                cpus.append(int(part))
            except ValueError:
                continue
    return sorted(set(cpus))


def _parse_cpu_mask(mask: str) -> List[int]:
    cleaned = mask.strip().replace(",", "")
    if not cleaned:
        return []
    try:
        value = int(cleaned, 16)
    except ValueError:
        return []
    cpus: List[int] = []
    bit = 0
    while value:
        if value & 1:
            cpus.append(bit)
        value >>= 1
        bit += 1
    return cpus


def gather_system_info(env: EnvironmentPaths) -> Dict[str, object]:
    hostname = _safe_read_text(env.proc / "sys/kernel/hostname")
    kernel_release = _safe_read_text(env.proc / "sys/kernel/osrelease")
    kernel_version = _safe_read_text(env.proc / "version")
    uptime_text = _safe_read_text(env.proc / "uptime")
    if uptime_text:
        try:
            uptime_seconds = float(uptime_text.split()[0])
        except (ValueError, IndexError):
            uptime_seconds = None
    else:
        uptime_seconds = None
    cmdline_raw = _safe_read_text(env.proc / "cmdline")
    cmdline, cmd_params = _parse_kernel_cmdline(cmdline_raw)
    num_nodes = 0
    nodes_path = env.sys / "devices/system/node"
    if nodes_path.is_dir():
        num_nodes = sum(1 for entry in nodes_path.iterdir() if entry.name.startswith("node"))
    return {
        "hostname": (hostname or "").strip(),
        "kernel_release": (kernel_release or "").strip(),
        "kernel_version": (kernel_version or "").strip(),
        "uptime_seconds": uptime_seconds,
        "kernel_cmdline": cmdline,
        "kernel_cmdline_params": cmd_params,
        "numa_nodes": num_nodes,
    }


def gather_cpu_info(env: EnvironmentPaths, cmd_params: Dict[str, List[str]]) -> Dict[str, object]:
    cpuinfo_text = _safe_read_text(env.proc / "cpuinfo")
    logical_cpus = 0
    sockets: List[str] = []
    cores: List[Tuple[str, str]] = []
    smt_possible = False
    if cpuinfo_text:
        block: Dict[str, str] = {}
        for line in cpuinfo_text.splitlines():
            if not line.strip():
                if block:
                    logical_cpus += 1
                    physical_id = block.get("physical id", str(block.get("processor", logical_cpus - 1)))
                    core_id = block.get("core id", str(block.get("processor", logical_cpus - 1)))
                    sockets.append(physical_id)
                    cores.append((physical_id, core_id))
                    siblings = block.get("siblings")
                    core_count = block.get("cpu cores")
                    if siblings and core_count:
                        try:
                            if int(siblings) > int(core_count):
                                smt_possible = True
                        except ValueError:
                            pass
                    block = {}
                continue
            if ":" in line:
                key, value = line.split(":", 1)
                block[key.strip()] = value.strip()
        if block:
            logical_cpus += 1
            physical_id = block.get("physical id", str(block.get("processor", logical_cpus - 1)))
            core_id = block.get("core id", str(block.get("processor", logical_cpus - 1)))
            sockets.append(physical_id)
            cores.append((physical_id, core_id))
            siblings = block.get("siblings")
            core_count = block.get("cpu cores")
            if siblings and core_count:
                try:
                    if int(siblings) > int(core_count):
                        smt_possible = True
                except ValueError:
                    pass

    unique_sockets = sorted(set(sockets))
    unique_cores = sorted(set(cores))
    isolated_params = cmd_params.get("isolcpus", []) + cmd_params.get("tuned.isolcpus", [])
    isolated_cpus: List[int] = []
    for value in isolated_params:
        isolated_cpus.extend(_parse_cpu_list(value))
    nohz_full = []
    for value in cmd_params.get("nohz_full", []):
        nohz_full.extend(_parse_cpu_list(value))
    tuned_non_isol = []
    for value in cmd_params.get("tuned.non_isolcpus", []):
        tuned_non_isol.extend(_parse_cpu_list(value))

    default_irq_affinity = _parse_cpu_mask(_safe_read_text(env.proc / "irq/default_smp_affinity") or "")

    recommendations: List[str] = []
    observations: List[str] = []
    if logical_cpus:
        observations.append(f"Detected {logical_cpus} logical CPUs across {len(unique_sockets)} socket(s).")
    if smt_possible:
        observations.append("Hyper-Threading/SMT appears to be enabled (siblings > cpu cores).")
    if isolated_cpus:
        observations.append(f"Kernel cmdline isolates CPUs: {','.join(str(cpu) for cpu in isolated_cpus)}.")
    else:
        if logical_cpus >= 8:
            recommendations.append(
                "Configure `isolcpus` (or `tuned.non_isolcpus`) to reserve dedicated cores for workload isolation."
            )
    if nohz_full and not isolated_cpus:
        recommendations.append(
            "`nohz_full` specified without matching `isolcpus`; verify scheduler isolation covers intended CPUs."
        )
    if tuned_non_isol:
        observations.append(f"Tuned non-isolated CPU mask: {','.join(str(cpu) for cpu in sorted(set(tuned_non_isol)))}.")
    if default_irq_affinity and isolated_cpus:
        overlap = sorted(set(default_irq_affinity) & set(isolated_cpus))
        if overlap:
            recommendations.append(
                f"Default IRQ affinity includes isolated CPUs ({','.join(map(str, overlap))}); adjust "
                "`/proc/irq/default_smp_affinity` and tuned profiles to keep interrupts off dedicated cores."
            )
    return {
        "logical_cpus": logical_cpus,
        "sockets": len(unique_sockets),
        "physical_cores": len(unique_cores),
        "smt_detected": smt_possible,
        "isolated_cpus": sorted(set(isolated_cpus)),
        "nohz_full": sorted(set(nohz_full)),
        "tuned_non_isolcpus": sorted(set(tuned_non_isol)),
        "default_irq_affinity": default_irq_affinity,
        "observations": observations,
        "recommendations": recommendations,
    }


def gather_hugepage_info(env: EnvironmentPaths) -> Dict[str, object]:
    meminfo_text = _safe_read_text(env.proc / "meminfo")
    hugepages_total = None
    hugepages_free = None
    hugepages_rsvd = None
    hugepages_surp = None
    hugepage_size_kb = None
    mem_total_kb = None
    if meminfo_text:
        for line in meminfo_text.splitlines():
            if line.startswith("HugePages_Total:"):
                hugepages_total = int(line.split()[1])
            elif line.startswith("HugePages_Free:"):
                hugepages_free = int(line.split()[1])
            elif line.startswith("HugePages_Rsvd:"):
                hugepages_rsvd = int(line.split()[1])
            elif line.startswith("HugePages_Surp:"):
                hugepages_surp = int(line.split()[1])
            elif line.startswith("Hugepagesize:"):
                hugepage_size_kb = int(line.split()[1])
            elif line.startswith("MemTotal:"):
                mem_total_kb = int(line.split()[1])
    sysctl_nr_hugepages = _safe_read_int(env.proc / "sys/vm/nr_hugepages")
    sysctl_overcommit_huge = _safe_read_int(env.proc / "sys/vm/nr_overcommit_hugepages")

    per_node: Dict[str, Dict[str, int]] = {}
    nodes_dir = env.sys / "devices/system/node"
    if nodes_dir.is_dir():
        for node_dir in sorted(nodes_dir.iterdir()):
            if not node_dir.name.startswith("node"):
                continue
            node_info: Dict[str, int] = {}
            hugepages_dir = node_dir / "hugepages"
            if hugepages_dir.is_dir():
                for hp_dir in hugepages_dir.iterdir():
                    nr_path = hp_dir / "nr_hugepages"
                    free_path = hp_dir / "free_hugepages"
                    if nr_path.exists():
                        node_info["total"] = node_info.get("total", 0) + int(nr_path.read_text().strip())
                    if free_path.exists():
                        node_info["free"] = node_info.get("free", 0) + int(free_path.read_text().strip())
            if node_info:
                per_node[node_dir.name] = node_info

    recommendations: List[str] = []
    observations: List[str] = []
    if hugepages_total is not None:
        observations.append(f"HugePages_Total={hugepages_total} (size={hugepage_size_kb or 'unknown'} KB).")
        if hugepages_total == 0:
            recommendations.append(
                "Huge pages are disabled. Configure `vm.nr_hugepages` or MachineConfig/Tuned profiles if workloads require pinned memory."
            )
        elif hugepages_free is not None and hugepages_free / max(hugepages_total, 1) < 0.1:
            recommendations.append(
                "Huge pages are nearly exhausted (free <10%). Increase the allocation cap or investigate consumption."
            )
    if hugepages_rsvd:
        observations.append(f"HugePages_Rsvd={hugepages_rsvd}.")
    if mem_total_kb and hugepages_total and hugepage_size_kb:
        provisioned_percent = (hugepages_total * hugepage_size_kb) / mem_total_kb * 100
        if provisioned_percent < 1:
            recommendations.append(
                "Huge page pool is <1% of system memory. Verify sizing matches workload requirements."
            )
    if sysctl_nr_hugepages and hugepages_total and sysctl_nr_hugepages != hugepages_total:
        observations.append(
            f"Runtime HugePages_Total ({hugepages_total}) differs from sysctl target ({sysctl_nr_hugepages})."
        )

    return {
        "hugepages_total": hugepages_total,
        "hugepages_free": hugepages_free,
        "hugepages_reserved": hugepages_rsvd,
        "hugepages_surplus": hugepages_surp,
        "hugepage_size_kb": hugepage_size_kb,
        "sysctl_nr_hugepages": sysctl_nr_hugepages,
        "sysctl_nr_overcommit": sysctl_overcommit_huge,
        "per_node": per_node,
        "observations": observations,
        "recommendations": recommendations,
    }


SYSCTL_CHECKS: List[Dict[str, object]] = [
    {
        "path": "kernel/sched_rt_runtime_us",
        "comparison": "eq",
        "value": -1,
        "message": "Set `kernel.sched_rt_runtime_us=-1` to allow realtime workloads full CPU bandwidth.",
    },
    {
        "path": "kernel/nmi_watchdog",
        "comparison": "eq",
        "value": 0,
        "message": "Disable NMI watchdog (`kernel.nmi_watchdog=0`) on isolated/latency-sensitive nodes.",
    },
    {
        "path": "vm/swappiness",
        "comparison": "lte",
        "value": 10,
        "message": "Lower `vm.swappiness` (<=10) to reduce swap pressure on performance nodes.",
    },
    {
        "path": "vm/zone_reclaim_mode",
        "comparison": "eq",
        "value": 0,
        "message": "Ensure `vm.zone_reclaim_mode=0` unless targeting NUMA-local reclaim.",
    },
    {
        "path": "net/core/netdev_max_backlog",
        "comparison": "gte",
        "value": 32768,
        "message": "Increase `net.core.netdev_max_backlog` (>=32768) to accommodate bursty NIC traffic.",
    },
    {
        "path": "net/core/somaxconn",
        "comparison": "gte",
        "value": 1024,
        "message": "Increase `net.core.somaxconn` (>=1024) to avoid listen queue overflows.",
    },
    {
        "path": "net/ipv4/tcp_tw_reuse",
        "comparison": "eq",
        "value": 1,
        "message": "Enable `net.ipv4.tcp_tw_reuse=1` for faster TIME-WAIT socket reuse.",
    },
    {
        "path": "net/ipv4/tcp_fin_timeout",
        "comparison": "lte",
        "value": 30,
        "message": "Reduce `net.ipv4.tcp_fin_timeout` (<=30) to shorten FIN-WAIT-2 linger.",
    },
    {
        "path": "net/ipv4/tcp_rmem",
        "comparison": "triplet_min",
        "value": (4096, 87380, 16777216),
        "message": "Grow `net.ipv4.tcp_rmem` (recommended min/def/max >= 4096/87380/16777216).",
    },
    {
        "path": "net/ipv4/tcp_wmem",
        "comparison": "triplet_min",
        "value": (4096, 65536, 16777216),
        "message": "Grow `net.ipv4.tcp_wmem` (recommended min/def/max >= 4096/65536/16777216).",
    },
]


def gather_sysctl_info(env: EnvironmentPaths) -> Dict[str, object]:
    results: Dict[str, Dict[str, object]] = {}
    recommendations: List[str] = []
    observations: List[str] = []
    for check in SYSCTL_CHECKS:
        path = env.proc / "sys" / Path(str(check["path"]))
        value_text = _safe_read_text(path)
        if value_text is None:
            continue
        normalized = value_text.strip()
        results[str(check["path"])] = {"value": normalized}
        comparison = str(check["comparison"])
        target = check["value"]
        try:
            if comparison == "eq":
                actual_int = int(normalized)
                if actual_int != int(target):
                    recommendations.append(str(check["message"]))
            elif comparison == "lte":
                actual_int = int(normalized)
                if actual_int > int(target):
                    recommendations.append(str(check["message"]))
            elif comparison == "gte":
                actual_int = int(normalized)
                if actual_int < int(target):
                    recommendations.append(str(check["message"]))
            elif comparison == "triplet_min":
                actual_parts = [int(part) for part in normalized.split()]
                target_parts = list(target) if isinstance(target, (list, tuple)) else []
                if len(actual_parts) >= 3 and len(target_parts) >= 3:
                    for idx in range(3):
                        if actual_parts[idx] < target_parts[idx]:
                            recommendations.append(str(check["message"]))
                            break
            else:
                observations.append(f"Unhandled comparison type '{comparison}' for {check['path']}.")
        except ValueError:
            observations.append(f"Non-integer sysctl value for {check['path']}: '{normalized}'.")

    thp_enabled = _safe_read_text(env.sys / "kernel/mm/transparent_hugepage/enabled")
    if thp_enabled:
        results["sys.kernel.mm.transparent_hugepage.enabled"] = {"value": thp_enabled.strip()}
        if "[never]" not in thp_enabled:
            recommendations.append(
                "Transparent Hugepages are not disabled (`[never]` not selected). Consider setting to `never` for latency-sensitive workloads."
            )

    thp_defrag = _safe_read_text(env.sys / "kernel/mm/transparent_hugepage/defrag")
    if thp_defrag:
        results["sys.kernel.mm.transparent_hugepage.defrag"] = {"value": thp_defrag.strip()}
        if "[never]" not in thp_defrag and "[madvise]" not in thp_defrag:
            recommendations.append(
                "Transparent Hugepage defrag is aggressive. Set to `never` or `madvise` to reduce allocation jitter."
            )

    return {
        "values": results,
        "observations": observations,
        "recommendations": recommendations,
    }


def _parse_netstat_file(path: Path) -> Dict[str, Dict[str, int]]:
    text = _safe_read_text(path)
    if not text:
        return {}
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    parsed: Dict[str, Dict[str, int]] = {}
    idx = 0
    while idx + 1 < len(lines):
        header = lines[idx].split()
        values = lines[idx + 1].split()
        if not header or not values:
            idx += 2
            continue
        section = header[0].rstrip(":")
        metrics: Dict[str, int] = {}
        for key, value in zip(header[1:], values[1:]):
            try:
                metrics[key] = int(value)
            except ValueError:
                continue
        parsed[section] = metrics
        idx += 2
    return parsed


def _parse_sockstat(path: Path) -> Dict[str, Dict[str, int]]:
    text = _safe_read_text(path)
    if not text:
        return {}
    parsed: Dict[str, Dict[str, int]] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        section, rest = line.split(":", 1)
        metrics: Dict[str, int] = {}
        parts = rest.split()
        for idx in range(0, len(parts), 2):
            key = parts[idx]
            if idx + 1 >= len(parts):
                break
            value = parts[idx + 1]
            try:
                metrics[key] = int(value)
            except ValueError:
                continue
        parsed[section.strip()] = metrics
    return parsed


def gather_network_info(env: EnvironmentPaths) -> Dict[str, object]:
    netstat_data = _parse_netstat_file(env.proc / "net/netstat")
    snmp_data = _parse_netstat_file(env.proc / "net/snmp")
    sockstat_data = _parse_sockstat(env.proc / "net/sockstat")
    recommendations: List[str] = []
    observations: List[str] = []

    tcp_ext = netstat_data.get("TcpExt", {})
    listen_drops = tcp_ext.get("ListenDrops")
    backlog_drops = tcp_ext.get("TCPBacklogDrop")
    aborted_listens = tcp_ext.get("TCPAbortOnListen")
    syncookies_failed = tcp_ext.get("SyncookiesFailed")
    if listen_drops and listen_drops > 0:
        recommendations.append(
            f"Detected {listen_drops} TCP listen drops. Increase `net.core.somaxconn` and review application accept loops."
        )
    if backlog_drops and backlog_drops > 0:
        recommendations.append(
            f"Detected {backlog_drops} TCP backlog drops. Increase `net.core.netdev_max_backlog` / `somaxconn` and tune application backlog."
        )
    if aborted_listens and aborted_listens > 0:
        observations.append(f"{aborted_listens} connections aborted on listen; investigate SYN flood or backlog exhaustion.")
    if syncookies_failed and syncookies_failed > 0:
        recommendations.append(
            f"Syncookies failures observed ({syncookies_failed}); validate NIC offload settings and SYN cookie limits."
        )

    tcp_sockstat = sockstat_data.get("TCP", {})
    if tcp_sockstat:
        in_use = tcp_sockstat.get("inuse")
        orphan = tcp_sockstat.get("orphan")
        if orphan and in_use and orphan > max(1, in_use // 10):
            recommendations.append(
                f"High orphaned TCP socket count ({orphan}) relative to in-use sockets ({in_use}). Tune FIN timeout and monitor retransmits."
            )

    return {
        "netstat": netstat_data,
        "snmp": snmp_data,
        "sockstat": sockstat_data,
        "observations": observations,
        "recommendations": recommendations,
    }


def gather_irq_affinity_info(
    env: EnvironmentPaths,
    isolated_cpus: Sequence[int],
    *,
    max_samples: int,
) -> Dict[str, object]:
    isolated_set = set(isolated_cpus)
    irq_dir = env.proc / "irq"
    mismatches: List[Dict[str, object]] = []
    total_irqs_checked = 0
    if irq_dir.is_dir():
        for entry in sorted(irq_dir.iterdir(), key=lambda p: p.name):
            if not entry.name.isdigit():
                continue
            total_irqs_checked += 1
            effective = _safe_read_text(entry / "effective_affinity_list")
            if effective is None:
                effective = _safe_read_text(entry / "smp_affinity_list")
            if effective is None:
                continue
            effective_cpus = _parse_cpu_list(effective.strip())
            if isolated_set and any(cpu in isolated_set for cpu in effective_cpus):
                desc = _safe_read_text(entry / "actions") or _safe_read_text(entry / "spurious")
                if desc:
                    desc = desc.strip().splitlines()[0]
                mismatches.append(
                    {
                        "irq": entry.name,
                        "cpus": effective_cpus,
                        "detail": desc,
                    }
                )
    recommendations: List[str] = []
    if mismatches:
        sample_count = min(len(mismatches), max_samples)
        recommendations.append(
            f"{len(mismatches)} IRQs overlap isolated CPUs. Relocate interrupt affinities using tuned profiles or `irqbalance` (showing {sample_count})."
        )
    return {
        "total_irqs_checked": total_irqs_checked,
        "isolated_cpu_overlaps": mismatches[:max_samples],
        "recommendations": recommendations,
    }


def gather_process_summary(env: EnvironmentPaths) -> Dict[str, object]:
    # Prefer sosreport process snapshot for richer context.
    ps_snapshot: Optional[Path] = None
    if env.sos_commands:
        candidates = [
            env.sos_commands / "process/ps_auxwww",
            env.sos_commands / "process" / "ps_auxwww",
            env.sos_commands / "process" / "ps_auxwww_-www",
        ]
        for candidate in candidates:
            if candidate.exists():
                ps_snapshot = candidate
                break
    if ps_snapshot is None:
        return {"top_processes": [], "recommendations": []}
    text = _safe_read_text(ps_snapshot)
    if not text:
        return {"top_processes": [], "recommendations": []}
    lines = [line for line in text.splitlines() if line.strip()]
    _header = lines[0]  # Header row, not needed for parsing
    processes: List[Dict[str, str]] = []
    for line in lines[1:]:
        parts = line.split(None, 10)
        if len(parts) < 11:
            continue
        _user, pid, cpu, mem, _vsz, _rss, _tty, _stat, _start, _time, command = parts
        processes.append(
            {
                "pid": pid,
                "cpu_percent": cpu,
                "mem_percent": mem,
                "command": command.strip(),
            }
        )
    processes.sort(key=lambda entry: float(entry.get("cpu_percent", "0") or "0"), reverse=True)
    top_processes = processes[:10]
    recommendations: List[str] = []
    for proc in top_processes:
        if "irqbalance" in proc["command"]:
            recommendations.append(
                "Verify irqbalance configuration excludes isolated CPUs (saw irqbalance among top processes)."
            )
            break
    return {
        "top_processes": top_processes,
        "recommendations": recommendations,
    }


def assemble_report(env: EnvironmentPaths, max_irq_samples: int) -> Dict[str, object]:
    system_info = gather_system_info(env)
    cpu_info = gather_cpu_info(env, system_info.get("kernel_cmdline_params", {}))
    hugepage_info = gather_hugepage_info(env)
    sysctl_info = gather_sysctl_info(env)
    network_info = gather_network_info(env)
    irq_info = gather_irq_affinity_info(
        env,
        cpu_info.get("isolated_cpus", []),
        max_samples=max_irq_samples,
    )
    process_info = gather_process_summary(env)

    recommendations: List[str] = []
    sections = [cpu_info, hugepage_info, sysctl_info, network_info, irq_info, process_info]
    for section in sections:
        recommendations.extend(section.get("recommendations", []))  # type: ignore[arg-type]
    unique_recommendations = sorted(set(rec.strip() for rec in recommendations if rec.strip()))

    return {
        "system": system_info,
        "cpu": cpu_info,
        "hugepages": hugepage_info,
        "sysctl": sysctl_info,
        "network": network_info,
        "irq_affinity": irq_info,
        "processes": process_info,
        "recommendations": unique_recommendations,
    }


def format_markdown(report: Dict[str, object]) -> str:
    lines: List[str] = []
    system = report["system"]  # type: ignore[assignment]
    cpu = report["cpu"]  # type: ignore[assignment]
    hugepages = report["hugepages"]  # type: ignore[assignment]
    sysctl = report["sysctl"]  # type: ignore[assignment]
    network = report["network"]  # type: ignore[assignment]
    irq = report["irq_affinity"]  # type: ignore[assignment]
    processes = report["processes"]  # type: ignore[assignment]

    lines.append("# Node Tuning Analysis")
    lines.append("")
    lines.append("## System Overview")
    lines.append(f"- Hostname: {system.get('hostname') or 'unknown'}")
    lines.append(f"- Kernel: {system.get('kernel_release') or 'unknown'}")
    lines.append(f"- NUMA nodes: {system.get('numa_nodes')}")
    cmdline = system.get("kernel_cmdline") or ""
    if cmdline:
        lines.append(f"- Kernel cmdline: `{cmdline}`")
    uptime = system.get("uptime_seconds")
    if uptime is not None:
        lines.append(f"- Uptime: {uptime:.0f} seconds")

    lines.append("")
    lines.append("## CPU & Isolation")
    lines.append(f"- Logical CPUs: {cpu.get('logical_cpus')}")
    lines.append(f"- Physical cores: {cpu.get('physical_cores')} across {cpu.get('sockets')} socket(s)")
    lines.append(f"- SMT detected: {'yes' if cpu.get('smt_detected') else 'no'}")
    if cpu.get("isolated_cpus"):
        lines.append(f"- Isolated CPUs: {','.join(str(v) for v in cpu['isolated_cpus'])}")  # type: ignore[index]
    if cpu.get("nohz_full"):
        lines.append(f"- nohz_full CPUs: {','.join(str(v) for v in cpu['nohz_full'])}")  # type: ignore[index]
    if cpu.get("tuned_non_isolcpus"):
        lines.append(
            f"- tuned.non_isolcpus: {','.join(str(v) for v in cpu['tuned_non_isolcpus'])}"  # type: ignore[index]
        )
    for obs in cpu.get("observations", []):
        lines.append(f"- {obs}")

    lines.append("")
    lines.append("## Huge Pages")
    lines.append(f"- Total: {hugepages.get('hugepages_total')} (size={hugepages.get('hugepage_size_kb')} KB)")
    lines.append(f"- Free: {hugepages.get('hugepages_free')}, Reserved: {hugepages.get('hugepages_reserved')}")
    if hugepages.get("per_node"):
        per_node = hugepages["per_node"]  # type: ignore[assignment]
        node_summaries = []
        for node, values in per_node.items():
            node_summaries.append(f"{node}:total={values.get('total',0)}/free={values.get('free',0)}")
        lines.append(f"- Per NUMA node: {', '.join(node_summaries)}")
    for obs in hugepages.get("observations", []):
        lines.append(f"- {obs}")

    lines.append("")
    lines.append("## Sysctl Highlights")
    for key, info in sorted(sysctl.get("values", {}).items()):  # type: ignore[call-arg]
        lines.append(f"- {key}: {info.get('value')}")
    for obs in sysctl.get("observations", []):
        lines.append(f"- {obs}")

    lines.append("")
    lines.append("## Network Signals")
    tcp_ext = network.get("netstat", {}).get("TcpExt", {})  # type: ignore[index]
    if tcp_ext:
        lines.append(
            "- TcpExt counters: "
            + ", ".join(f"{key}={value}" for key, value in list(tcp_ext.items())[:8])
        )
    tcp_sock = network.get("sockstat", {}).get("TCP", {})  # type: ignore[index]
    if tcp_sock:
        lines.append("- Sockstat TCP: " + ", ".join(f"{k}={v}" for k, v in tcp_sock.items()))
    for obs in network.get("observations", []):
        lines.append(f"- {obs}")

    lines.append("")
    lines.append("## IRQ Affinity")
    lines.append(f"- IRQs inspected: {irq.get('total_irqs_checked')}")
    overlaps = irq.get("isolated_cpu_overlaps", [])
    if overlaps:
        lines.append(f"- IRQs overlapping isolated CPUs: {len(overlaps)}")
        for entry in overlaps:
            lines.append(
                f"  - IRQ {entry.get('irq')}: CPUs {','.join(str(cpu) for cpu in entry.get('cpus', []))}"
            )
    else:
        lines.append("- No IRQ affinity overlaps with isolated CPUs detected.")

    process_list = processes.get("top_processes", [])
    if process_list:
        lines.append("")
        lines.append("## Process Snapshot (top by %CPU)")
        for proc in process_list[:5]:
            lines.append(
                f"- PID {proc['pid']}: {proc['cpu_percent']}% CPU, {proc['mem_percent']}% MEM, cmd='{proc['command']}'"
            )

    recommendations = report.get("recommendations", [])
    if recommendations:
        lines.append("")
        lines.append("## Recommended Actions")
        for rec in recommendations:
            lines.append(f"- {rec}")

    return "\n".join(lines) + "\n"


def main(argv: Sequence[str]) -> int:
    args = parse_arguments(argv)
    try:
        env = resolve_environment(args)
        report = assemble_report(env, max_irq_samples=args.max_irq_samples)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.format == "json":
        output = json.dumps(report, indent=2)
    else:
        output = format_markdown(report)

    if args.output:
        output_path = Path(args.output).expanduser()
        if output_path.parent and not output_path.parent.exists():
            output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output, encoding="utf-8")
        print(f"Wrote analysis report to {output_path}")
    else:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


