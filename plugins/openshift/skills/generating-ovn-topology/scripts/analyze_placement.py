#!/usr/bin/env python3
"""
analyze_placement.py - Analyze OVN component placement from collected data

Usage: analyze_placement.py TMPDIR

This script analyzes UUID patterns from previously collected OVN data to determine
component placement (per-node vs cluster-wide).

Input files (read from TMPDIR):
  - ovn_switches_detail.txt - node|uuid|name|other_config
  - ovn_routers_detail.txt  - node|uuid|name|external_ids|options

Output files (written to TMPDIR):
  - ovn_switch_placement.txt  - name|placement (per-node|cluster-wide|cluster-wide-visual)
  - ovn_router_placement.txt  - name|placement (per-node|cluster-wide|cluster-wide-visual)

Exit codes:
  0 - Success
  1 - Missing input files or analysis failed

Requirements: Python 3.6+
"""

import os
import sys
from collections import defaultdict
from typing import Dict, List, Set, Tuple

# Import shared utilities (must be in same directory or in PYTHONPATH)
from ovn_utils import safe_write_file


class PlacementAnalyzer:
    """Analyze OVN component placement from collected data."""

    # File name constants
    SWITCHES_DETAIL_FILE = "ovn_switches_detail.txt"
    ROUTERS_DETAIL_FILE = "ovn_routers_detail.txt"
    SWITCH_PLACEMENT_FILE = "ovn_switch_placement.txt"
    ROUTER_PLACEMENT_FILE = "ovn_router_placement.txt"

    # Component names for visualization overrides
    TRANSIT_SWITCH_NAME = "transit_switch"
    JOIN_SWITCH_NAME = "join"

    # Placement types
    PLACEMENT_PER_NODE = "per-node"
    PLACEMENT_CLUSTER_WIDE = "cluster-wide"
    PLACEMENT_CLUSTER_WIDE_VISUAL = "cluster-wide-visual"

    def __init__(self, tmpdir: str):
        """Initialize PlacementAnalyzer with a private temporary directory.

        Args:
            tmpdir: Private temporary directory path.
        """

        # Input files (with UUIDs)
        self.switches_file = os.path.join(tmpdir, self.SWITCHES_DETAIL_FILE)
        self.routers_file = os.path.join(tmpdir, self.ROUTERS_DETAIL_FILE)

        # Output files (placement analysis only)
        self.switch_placement_file = os.path.join(tmpdir, self.SWITCH_PLACEMENT_FILE)
        self.router_placement_file = os.path.join(tmpdir, self.ROUTER_PLACEMENT_FILE)

        # In-memory data structures
        self.switch_data: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
        self.router_data: Dict[str, List[Tuple[str, str]]] = defaultdict(list)

    def verify_input_files(self) -> bool:
        """Verify that required input files exist.

        Returns:
            True if all required files exist, False otherwise.
        """
        if not os.path.exists(self.switches_file):
            print(
                f"❌ Error: Input file not found: {self.switches_file}",
                file=sys.stderr,
            )
            print(
                "   Run collect_ovn_data.py first to gather data.",
                file=sys.stderr,
            )
            return False

        if not os.path.exists(self.routers_file):
            print(
                f"❌ Error: Input file not found: {self.routers_file}",
                file=sys.stderr,
            )
            print(
                "   Run collect_ovn_data.py first to gather data.",
                file=sys.stderr,
            )
            return False

        return True

    def load_data(self):
        """Load switch and router data from files into memory."""
        print("=" * 50)
        print("LOADING COLLECTED DATA")
        print("=" * 50)

        # Load switches: node|uuid|name|other_config
        switch_count = 0
        with open(self.switches_file) as f:
            for line in f:
                if not line.strip():
                    continue
                parts = line.strip().split('|', 3)
                if len(parts) >= 3:
                    node, uuid, name = parts[0], parts[1], parts[2]
                    self.switch_data[name].append((node, uuid))
                    switch_count += 1

        print(f"  ✓ Loaded {switch_count} switch entries")

        # Load routers: node|uuid|name|external_ids|options
        router_count = 0
        with open(self.routers_file) as f:
            for line in f:
                if not line.strip():
                    continue
                parts = line.strip().split('|', 3)
                if len(parts) >= 3:
                    node, uuid, name = parts[0], parts[1], parts[2]
                    self.router_data[name].append((node, uuid))
                    router_count += 1

        print(f"  ✓ Loaded {router_count} router entries")

    def _analyze_component_placement(
        self,
        component_data: Dict[str, List[Tuple[str, str]]]
    ) -> Dict[str, str]:
        """Analyze placement for a component type (switch or router).

        Args:
            component_data: Dict mapping component names to (node, uuid) tuples

        Returns:
            Dict mapping component names to placement ("per-node" or "cluster-wide")
        """
        placement: Dict[str, str] = {}

        for name in sorted(component_data.keys()):
            entries = component_data[name]
            uuids: Set[str] = {uuid for _, uuid in entries}
            unique_count = len(uuids)
            total_count = len(entries)

            if unique_count == 1 and total_count > 1:
                # Same UUID across multiple nodes = truly cluster-wide
                placement[name] = self.PLACEMENT_CLUSTER_WIDE
                print(
                    f"  ✓ {name}: CLUSTER-WIDE "
                    f"(same UUID across {total_count} nodes)"
                )
            elif unique_count > 1:
                # Different UUIDs = per-node replicated component
                placement[name] = self.PLACEMENT_PER_NODE
                print(
                    f"  ✓ {name}: PER-NODE "
                    f"({unique_count} different UUIDs across {total_count} nodes)"
                )
            else:
                # Only exists on one node = per-node specific
                placement[name] = self.PLACEMENT_PER_NODE
                print(f"  ✓ {name}: PER-NODE (exists on 1 node only)")

        return placement


    def analyze_uuid_patterns(self):
        """Analyze UUID patterns to determine per-node vs cluster-wide placement."""
        print()
        print("=" * 50)
        print("ANALYZING UUID PATTERNS")
        print("=" * 50)

        # Analyze switches
        print()
        print("Switches:")
        switch_placement = self._analyze_component_placement(self.switch_data)

        # Analyze routers
        print()
        print("Routers:")
        router_placement = self._analyze_component_placement(self.router_data)

        # Apply visualization overrides
        print()
        print("Visualization Overrides:")

        # MANDATORY: Override transit_switch to cluster-wide-visual
        if self.TRANSIT_SWITCH_NAME in switch_placement:
            original = switch_placement[self.TRANSIT_SWITCH_NAME]
            if original == self.PLACEMENT_PER_NODE:
                switch_placement[self.TRANSIT_SWITCH_NAME] = self.PLACEMENT_CLUSTER_WIDE_VISUAL
                print(
                    "  → transit_switch: PER-NODE (detected) → "
                    "overriding to CLUSTER-WIDE-VISUAL"
                )
            else:
                print(
                    f"  → transit_switch: {original.upper()} (detected) → "
                    "keeping as-is"
                )

        # DO NOT override join switch - respect discovered data
        if self.JOIN_SWITCH_NAME in switch_placement:
            placement = switch_placement[self.JOIN_SWITCH_NAME]
            print(f"  → join: {placement.upper()} (detected) → keeping as-is")

        # Write placement files using safe write to prevent symlink attacks
        switch_content = "".join(
            f"{name}|{switch_placement[name]}\n"
            for name in sorted(switch_placement.keys())
        )
        safe_write_file(self.switch_placement_file, switch_content)

        router_content = "".join(
            f"{name}|{router_placement[name]}\n"
            for name in sorted(router_placement.keys())
        )
        safe_write_file(self.router_placement_file, router_content)

        print()
        print("✓ Placement analysis complete:")
        print(f"  Switch placements: {self.switch_placement_file}")
        print(f"  Router placements: {self.router_placement_file}")

    def print_summary(self):
        """Print analysis summary."""
        print()
        print("=" * 50)
        print("ANALYSIS SUMMARY")
        print("=" * 50)

        # Count from in-memory data
        unique_switches = len(self.switch_data)
        unique_routers = len(self.router_data)

        # Count entries
        total_switch_entries = sum(len(entries) for entries in self.switch_data.values())
        total_router_entries = sum(len(entries) for entries in self.router_data.values())

        print(f"Unique switches: {unique_switches} ({total_switch_entries} total entries)")
        print(f"Unique routers:  {unique_routers} ({total_router_entries} total entries)")

        # Count placement results
        def count_lines(filepath):
            try:
                with open(filepath) as f:
                    return sum(1 for _ in f)
            except Exception:
                return 0

        switch_placements = count_lines(self.switch_placement_file)
        router_placements = count_lines(self.router_placement_file)

        print()
        print("Output files:")
        print(
            f"  Switch placements: {switch_placements} → "
            f"{self.switch_placement_file}"
        )
        print(
            f"  Router placements: {router_placements} → "
            f"{self.router_placement_file}"
        )

    def run(self) -> int:
        """Run the placement analysis process.

        Returns:
            0 if successful
            1 if failed
        """
        # Verify input files exist
        if not self.verify_input_files():
            return 1

        # Load data from files
        self.load_data()

        # Analyze UUID patterns
        self.analyze_uuid_patterns()

        # Print summary
        self.print_summary()

        print()
        print("✅ Placement analysis complete")

        return 0


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print(
            "Usage: analyze_placement.py TMPDIR",
            file=sys.stderr,
        )
        return 1

    tmpdir = sys.argv[1]

    if not os.path.isdir(tmpdir):
        print(
            f"❌ Error: TMPDIR is not a directory or does not exist: {tmpdir}",
            file=sys.stderr,
        )
        return 1

    analyzer = PlacementAnalyzer(tmpdir)
    try:
        return analyzer.run()
    except OSError as exc:
        print(f"❌ Error reading/writing placement files: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
