#!/usr/bin/env python3
"""
Deficiency to Experience Store Bridge

Automatically exports fixed deficiencies to the experience store
for future retrieval and learning.

Usage:
    python lib/deficiency_to_experience.py export <deficiency_id>
    python lib/deficiency_to_experience.py export-all-fixed
"""

import sys
import json
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent))

from deficiency_tracker import DeficiencyTracker
try:
    from experience_store import ExperienceStore, DomainContext
    HAS_EXPERIENCE_STORE = True
except ImportError:
    HAS_EXPERIENCE_STORE = False


def export_deficiency_to_experience(deficiency_id: str, tracker: DeficiencyTracker = None) -> bool:
    """
    Export a fixed deficiency to experience store

    Args:
        deficiency_id: ID of deficiency to export
        tracker: DeficiencyTracker instance (creates new if None)

    Returns:
        True if exported successfully, False otherwise
    """
    if not HAS_EXPERIENCE_STORE:
        return False

    if tracker is None:
        tracker = DeficiencyTracker()

    # Check if deficiency exists
    if deficiency_id not in tracker._deficiencies:
        return False

    deficiency = tracker._deficiencies[deficiency_id]

    # Only export if has solution
    if not deficiency.solution:
        return False

    # Export to format suitable for experience store
    export_data = tracker.export_for_experience_store(deficiency_id)

    # Create experience store and add entry
    try:
        store = ExperienceStore()

        # Determine domain from context
        domain_type = export_data['context'].get('domain', 'cli_tool')

        domain = DomainContext(
            project_type=domain_type,
            language=export_data['context'].get('language', 'bash'),
            frameworks=export_data['context'].get('frameworks', ['claude-loop']),
            tools_used=['claude-loop']
        )

        # Add to experience store
        experience_id = store.store_experience(
            problem=export_data['problem'],
            solution=export_data['solution'],
            domain=domain,
            context={
                'deficiency_type': export_data['deficiency_type'],
                'frequency': export_data['frequency'],
                'suggestions': export_data['improvement_suggestions'],
                'source': 'deficiency_tracker'
            }
        )

        return experience_id is not None
    except Exception:
        return False


def export_all_fixed_deficiencies(tracker: DeficiencyTracker = None) -> int:
    """
    Export all fixed deficiencies to experience store

    Args:
        tracker: DeficiencyTracker instance (creates new if None)

    Returns:
        Number of deficiencies exported
    """
    if tracker is None:
        tracker = DeficiencyTracker()

    exported = 0
    for deficiency_id, deficiency in tracker._deficiencies.items():
        # Only export fixed deficiencies with solutions
        if deficiency.remediation_status == 'fixed' and deficiency.solution:
            if export_deficiency_to_experience(deficiency_id, tracker):
                exported += 1

    return exported


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Export deficiencies to experience store')
    parser.add_argument('command', choices=['export', 'export-all-fixed'],
                        help='Command to execute')
    parser.add_argument('deficiency_id', nargs='?',
                        help='Deficiency ID to export (for export command)')

    args = parser.parse_args()

    if args.command == 'export':
        if not args.deficiency_id:
            print("Error: deficiency_id required for export command", file=sys.stderr)
            sys.exit(1)

        success = export_deficiency_to_experience(args.deficiency_id)
        if success:
            print(f"Exported deficiency {args.deficiency_id} to experience store")
            sys.exit(0)
        else:
            print(f"Failed to export deficiency {args.deficiency_id}", file=sys.stderr)
            sys.exit(1)

    elif args.command == 'export-all-fixed':
        count = export_all_fixed_deficiencies()
        print(f"Exported {count} fixed deficiencies to experience store")
        sys.exit(0)
