#!/usr/bin/env python3
"""
Comprehensive script to fix all broken links in broken.mdx file.
"""


def fix_broken_links(filename):
    """Fix all broken links by joining split lines."""
    with open(filename, "r") as f:
        lines = f.readlines()

    fixed_lines = []
    i = 0

    while i < len(lines):
        current_line = lines[i].rstrip()

        # Look ahead to see if next line is a continuation
        if i + 1 < len(lines):
            next_line = lines[i + 1].strip()

            # Check if next line looks like a continuation:
            # - Doesn't start with ⎿, guides/, or empty
            # - Current line doesn't end with .mdx or /
            # - Next line doesn't look like a new entry
            if (
                next_line
                and not next_line.startswith(("⎿", "guides/"))
                and not current_line.endswith((".mdx", "/"))
                and not current_line.strip() == ""
            ):

                # Join the lines
                fixed_lines.append(current_line + next_line + "\n")
                i += 2  # Skip next line
                continue

        # Add current line as-is
        fixed_lines.append(lines[i])
        i += 1

    # Write back
    with open(filename, "w") as f:
        f.writelines(fixed_lines)

    print(f"Fixed all broken links in {filename}")


if __name__ == "__main__":
    fix_broken_links("/home/raeder/mintlify/wandb-docs/broken.mdx")
