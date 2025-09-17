#!/usr/bin/env python3
"""
Script to change 'url' to 'slug' in MDX file frontmatter and cascade items.
"""
import re
import sys
from pathlib import Path


def process_mdx_file(file_path):
    """Process a single MDX file to change url to slug in frontmatter and cascade items."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check if file has frontmatter
        if not content.startswith("---"):
            return False

        # Split content into frontmatter and body
        parts = content.split("---", 2)
        if len(parts) < 3:
            return False

        frontmatter = parts[1]
        body = parts[2]

        # Change url field to slug field
        frontmatter = re.sub(r"^url:", "slug:", frontmatter, flags=re.MULTILINE)

        # Change cascade field name from cascade to cascade (keep the same)
        # and change url: to slug: inside cascade items
        frontmatter = re.sub(r"^- url:", "- slug:", frontmatter, flags=re.MULTILINE)

        # Clean up extra blank lines
        frontmatter = re.sub(r"\n\n+", "\n\n", frontmatter)
        frontmatter = frontmatter.strip()

        # Reconstruct the file
        if frontmatter:
            new_content = f"---\n{frontmatter}\n---{body}"
        else:
            # If frontmatter is empty, remove it entirely
            new_content = body.lstrip()

        # Write back to file
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        return True

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def main():
    """Main function to process all MDX files."""
    if len(sys.argv) > 1:
        # Process specific files/directories passed as arguments
        paths = sys.argv[1:]
    else:
        # Process current directory recursively
        paths = ["."]

    processed_count = 0

    for path_arg in paths:
        path = Path(path_arg)

        if path.is_file() and path.suffix == ".mdx":
            if process_mdx_file(path):
                print(f"Processed: {path}")
                processed_count += 1
        elif path.is_dir():
            # Recursively find all .mdx files
            for mdx_file in path.rglob("*.mdx"):
                if process_mdx_file(mdx_file):
                    print(f"Processed: {mdx_file}")
                    processed_count += 1
        else:
            print(f"Skipping: {path} (not an MDX file or directory)")

    print(f"\nTotal files processed: {processed_count}")


if __name__ == "__main__":
    main()
