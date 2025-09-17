"""
Script to apply broken link fixes from the broken_links_report.json file.
This script reads the fixes found by fix_broken_links.py and applies them to the actual MDX files.
"""

import json
import re
import sys
import shutil
from pathlib import Path
from datetime import datetime


def load_report(report_file):
    """
    Load the broken links report JSON file.

    Args:
        report_file (str): Path to the report JSON file

    Returns:
        dict: Report data or None if error
    """
    try:
        with open(report_file, "r", encoding="utf-8") as f:
            report = json.load(f)

        print(f"Loaded report: {report['metadata']['generated_at']}")
        print(f"Script version: {report['metadata']['script_version']}")
        print(f"Total pages: {report['metadata']['total_pages']}")
        print(f"Total links processed: {report['metadata']['total_links_processed']}")

        return report
    except Exception as e:
        print(f"Error loading report file: {e}")
        return None


def backup_file(file_path):
    """
    Create a backup of the file before modifying it.

    Args:
        file_path (str): Path to the file to backup

    Returns:
        str: Path to the backup file
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{file_path}.backup_{timestamp}"

    try:
        shutil.copy2(file_path, backup_path)
        print(f"    Created backup: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"    Warning: Could not create backup: {e}")
        return None


def apply_link_fix(file_path, broken_link, fixed_link, dry_run=False):
    """
    Apply a single link fix to a file.

    Args:
        file_path (str): Path to the MDX file
        broken_link (str): The broken link to replace
        fixed_link (str): The correct link to replace it with
        dry_run (bool): If True, only show what would be changed

    Returns:
        bool: True if changes were made, False otherwise
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Create regex pattern to find markdown links with the broken URL
        # Pattern: [text](broken_link) or just (broken_link) if it's a standalone link
        pattern = rf"\]\({re.escape(broken_link)}\)"
        replacement = f"]({fixed_link})"

        # Find all matches
        matches = list(re.finditer(pattern, content))

        if not matches:
            print(f"    No matches found for: {broken_link}")
            return False

        if dry_run:
            print(f"    [DRY RUN] Would replace {len(matches)} occurrence(s):")
            for i, match in enumerate(matches, 1):
                # Get some context around the match
                start = max(0, match.start() - 30)
                end = min(len(content), match.end() + 30)
                context = content[start:end].replace("\n", "\\n")
                print(f"      Match {i}: ...{context}...")
            return True

        # Apply the replacement
        new_content = re.sub(pattern, replacement, content)

        if new_content != content:
            # Create backup before making changes
            # backup_path = backup_file(file_path)

            # Write the updated content
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            print(
                f"    [SUCCESS] Replaced {len(matches)} occurrence(s) of {broken_link} -> {fixed_link}"
            )
            return True
        else:
            print(f"    No changes made to {file_path}")
            return False

    except Exception as e:
        print(f"    Error applying fix to {file_path}: {e}")
        return False


def apply_fixes_to_page(page_path, links, dry_run=False):
    """
    Apply all link fixes to a single page.

    Args:
        page_path (str): Path to the MDX file (relative)
        links (list): List of link fix dictionaries
        dry_run (bool): If True, only show what would be changed

    Returns:
        tuple: (total_fixes, successful_fixes)
    """
    # Convert relative path to absolute path
    if not page_path.startswith("/"):
        full_path = f"D:/writechoice/wandb-docs/{page_path}"
    else:
        full_path = f"D:/writechoice/wandb-docs{page_path}"

    print(f"\nProcessing page: {page_path}")
    print(f"Full path: {full_path}")

    # Check if file exists
    if not Path(full_path).exists():
        print(f"  Error: File not found: {full_path}")
        return 0, 0

    total_fixes = 0
    successful_fixes = 0

    for link in links:
        broken_link = link.get("broken")
        fixed_link = link.get("fix")
        confidence = link.get("confidence", "unknown")
        fix_method = link.get("fix_method", "unknown")

        if not fixed_link:
            print(f"  Skipping {broken_link}: No fix available")
            continue

        print(
            f"  Fixing: {broken_link} -> {fixed_link} (method: {fix_method}, confidence: {confidence})"
        )

        total_fixes += 1
        if apply_link_fix(full_path, broken_link, fixed_link, dry_run):
            successful_fixes += 1

    return total_fixes, successful_fixes


def main():
    """Main function to apply link fixes from report."""
    # Parse command line arguments
    report_file = "broken_links_report.json"
    dry_run = False

    # Simple argument parsing
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg in ["-h", "--help"]:
            print("Usage: python apply_link_fixes.py [REPORT_FILE] [--dry-run]")
            print("  REPORT_FILE: JSON report file (default: broken_links_report.json)")
            print("  --dry-run: Show what would be changed without making changes")
            sys.exit(0)
        elif arg == "--dry-run":
            dry_run = True
        elif i == 1 and not arg.startswith("--"):
            report_file = arg

    print(f"Link Fixer Script")
    print(f"Report file: {report_file}")
    print(f"Mode: {'DRY RUN' if dry_run else 'APPLY FIXES'}")
    print("-" * 50)

    # Load the report
    report = load_report(report_file)
    if not report:
        sys.exit(1)

    total_pages = 0
    total_fixes = 0
    total_successful = 0

    # Process each page in the report
    for result in report.get("results", []):
        page = result.get("page")
        links = result.get("links", [])

        if not page or not links:
            continue

        total_pages += 1
        page_fixes, page_successful = apply_fixes_to_page(page, links, dry_run)
        total_fixes += page_fixes
        total_successful += page_successful

    # Summary
    print(f"\n" + "=" * 50)
    print(f"Summary:")
    print(f"  Pages processed: {total_pages}")
    print(f"  Total fixes attempted: {total_fixes}")
    print(f"  Successful fixes: {total_successful}")
    print(
        f"  Success rate: {total_successful/total_fixes*100:.1f}%"
        if total_fixes > 0
        else "  Success rate: N/A"
    )

    if dry_run:
        print(f"\nThis was a DRY RUN. No files were modified.")
        print(f"Run without --dry-run to apply the fixes.")
    else:
        print(f"\nFixes have been applied! Backup files created for safety.")

    if total_successful > 0:
        print(
            f"\nRecommendation: Test the fixed links and commit the changes if they work correctly."
        )

    return total_successful, total_fixes


if __name__ == "__main__":
    main()
