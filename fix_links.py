#!/usr/bin/env python3
"""
Script to fix internal links in MDX files by removing file extensions.
Processes all .mdx files in the current directory and subdirectories.
"""

import os
import re
import sys
from pathlib import Path


def fix_internal_links(text):
    """
    Remove .md/.mdx extensions from internal markdown links.

    Args:
        text (str): The markdown content to process

    Returns:
        str: The processed text with .md/.mdx extensions removed from internal links
    """
    # Pattern to match internal links: [text](path) where path starts with ./ or /
    # Only match .md or .mdx extensions
    pattern = r"\[([^\]]+)\]\(((?:\.)?/[^)]*?)(\.mdx?)(#[^)]*?)?\)"

    def replace_link(match):
        link_text = match.group(1)
        path = match.group(2)
        anchor = match.group(4) or ""

        # Remove the .md/.mdx extension and keep the anchor if present
        return f"[{link_text}]({path}{anchor})"

    return re.sub(pattern, replace_link, text)


def find_mdx_files(directory):
    """
    Find all .mdx files in the directory and subdirectories.

    Args:
        directory (str): The root directory to search

    Returns:
        list: List of Path objects for .mdx files
    """
    directory_path = Path(directory)
    return list(directory_path.rglob("*.mdx"))


def process_file(file_path, dry_run=False):
    """
    Process a single MDX file to fix internal links.

    Args:
        file_path (Path): Path to the MDX file
        dry_run (bool): If True, don't write changes, just show what would be changed

    Returns:
        tuple: (bool, int) - (changed, num_changes)
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            original_content = f.read()

        fixed_content = fix_internal_links(original_content)

        if original_content != fixed_content:
            if not dry_run:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(fixed_content)

            # Count the number of changes (only .md/.mdx extensions)
            original_links = re.findall(
                r"\[([^\]]+)\]\(((?:\.)?/[^)]*?)(\.mdx?)(#[^)]*?)?\)",
                original_content,
            )
            num_changes = len(original_links)

            return True, num_changes
        else:
            return False, 0

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False, 0


def main():
    """Main function to process all MDX files."""
    # Parse command line arguments
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv

    if dry_run:
        print("DRY RUN MODE - No files will be modified")
        print("-" * 50)

    # Find all MDX files
    current_dir = os.getcwd()
    mdx_files = find_mdx_files(current_dir)

    if not mdx_files:
        print("No .mdx files found in the current directory and subdirectories.")
        return

    print(f"Found {len(mdx_files)} .mdx files")
    print()

    total_files_changed = 0
    total_links_fixed = 0

    # Process each file
    for file_path in mdx_files:
        changed, num_changes = process_file(file_path, dry_run)

        if changed:
            relative_path = file_path.relative_to(current_dir)
            status = "WOULD FIX" if dry_run else "FIXED"
            print(f"{status}: {relative_path} ({num_changes} links)")
            total_files_changed += 1
            total_links_fixed += num_changes

    # Summary
    print()
    print("-" * 50)
    action = "would be fixed" if dry_run else "fixed"
    print(f"Summary: {total_links_fixed} links {action} in {total_files_changed} files")

    if dry_run:
        print()
        print("Run without --dry-run to apply changes")


if __name__ == "__main__":
    main()
