#!/usr/bin/env python3
"""
Script to convert Hugo shortcodes to Mintlify components.

Converts patterns like:
{{< img src="/images/reports/clone_reports.gif" alt="Cloning reports" >}}
To:
<Frame>
    <img src="/images/reports/clone_reports.gif" alt="Cloning reports"  />
</Frame>

{{< tabpane text=true >}}
{{% tab header="W&B App" value="app" %}}
Content here
{{% /tab %}}
{{< /tabpane >}}
To:
<Tabs>
<Tab title="W&B App">
Content here
</Tab>
</Tabs>

{{% pageinfo color="info" %}}
Content here
{{% /pageinfo %}}
To:
<Info>
Content here
</Info>

{{% alert %}}
Content here
{{% /alert %}}
To:
<Note>
Content here
</Note>

[W&B Runs]({{< relref "/ref/python/sdk/classes/run.md" >}})
To:
[W&B Runs](/ref/python/sdk/classes/run)

<!-- HTML comment -->
To:
{/* JSX comment */}

{{< cta-button productLink="https://wandb.ai/..." colabLink="https://colab.research.google.com/..." >}}
To:
<CardGroup cols={2}>
<Card title="Try in Colab" href="https://colab.research.google.com/..." icon="python">
</Card>
<Card title="Try in W&B" href="https://wandb.ai/..." icon="sliders-up">
</Card>
</CardGroup>
"""

import os
import re
import argparse
from pathlib import Path


def convert_image_shortcodes(content):
    """
    Convert Hugo img shortcodes to Mintlify Frame components.

    Args:
        content (str): File content to process

    Returns:
        tuple: (converted_content, count_of_replacements)
    """
    # Pattern to match Hugo img shortcodes
    # Matches: {{< img src="..." alt="..." >}} with optional additional attributes
    pattern = r'\{\{<\s*img\s+([^>]+)\s*>\}\}'

    def replace_shortcode(match):
        attributes = match.group(1).strip()

        # Extract src and alt attributes, preserve others
        src_match = re.search(r'src\s*=\s*["\']([^"\']+)["\']', attributes)
        alt_match = re.search(r'alt\s*=\s*["\']([^"\']*)["\']', attributes)

        if not src_match:
            # If no src found, return original
            return match.group(0)

        src = src_match.group(1)
        alt = alt_match.group(1) if alt_match else ""

        # Build the new Frame component
        img_attrs = f'src="{src}"'
        if alt:
            img_attrs += f' alt="{alt}"'

        # Add any other attributes (excluding src and alt)
        other_attrs = re.sub(r'(src\s*=\s*["\'][^"\']+["\']|alt\s*=\s*["\'][^"\']*["\'])\s*', '', attributes).strip()
        if other_attrs:
            img_attrs += f' {other_attrs}'

        return f'<Frame>\n    <img {img_attrs}  />\n</Frame>'

    converted_content = re.sub(pattern, replace_shortcode, content)
    count = len(re.findall(pattern, content))

    return converted_content, count


def convert_tab_shortcodes(content):
    """
    Convert Hugo tab shortcodes to Mintlify Tab components.

    Args:
        content (str): File content to process

    Returns:
        tuple: (converted_content, count_of_replacements)
    """
    count = 0

    # Pattern to match tabpane and tab blocks
    # This handles nested structure: {{< tabpane >}} ... {{% tab %}} ... {{% /tab %}} ... {{< /tabpane >}}
    tabpane_pattern = r'\{\{<\s*tabpane[^>]*>\}\}([\s\S]*?)\{\{<\s*/tabpane\s*>\}\}'

    def replace_tabpane(match):
        nonlocal count
        tabpane_content = match.group(1).strip()

        # Extract individual tabs
        tab_pattern = r'\{\{%\s*tab\s+([^%}]+)%\}\}([\s\S]*?)\{\{%\s*/tab\s*%\}\}'
        tabs = []

        for tab_match in re.finditer(tab_pattern, tabpane_content):
            tab_attrs = tab_match.group(1).strip()
            tab_content = tab_match.group(2).strip()

            # Extract header attribute for tab title
            header_match = re.search(r'header\s*=\s*["\']([^"\']*)["\']', tab_attrs)
            title = header_match.group(1) if header_match else "Tab"

            tabs.append(f'<Tab title="{title}">\n{tab_content}\n</Tab>')

        if tabs:
            count += 1
            return f'<Tabs>\n{"""\n""".join(tabs)}\n</Tabs>'
        else:
            return match.group(0)  # Return original if no tabs found

    converted_content = re.sub(tabpane_pattern, replace_tabpane, content)

    return converted_content, count


def convert_callout_shortcodes(content):
    """
    Convert Hugo pageinfo and alert shortcodes to Mintlify callout components.

    Args:
        content (str): File content to process

    Returns:
        tuple: (converted_content, count_of_replacements)
    """
    count = 0
    
    # Pattern to match pageinfo blocks with optional attributes
    pageinfo_pattern = r'\{\{%\s*pageinfo\s*([^%}]*)\s*%\}\}([\s\S]*?)\{\{%\s*/pageinfo\s*%\}\}'
    
    def replace_pageinfo(match):
        nonlocal count
        attrs = match.group(1).strip()
        content_text = match.group(2).strip()
        
        # Extract color attribute
        color_match = re.search(r'color\s*=\s*["\']([^"\']*)["\']', attrs)
        color = color_match.group(1) if color_match else ""
        
        # Extract title attribute if present
        title_match = re.search(r'title\s*=\s*["\']([^"\']*)["\']', attrs)
        title = title_match.group(1) if title_match else ""
        
        # Determine callout type based on color
        if color == "info":
            callout_type = "Info"
        elif color == "secondary" or color == "warning":
            callout_type = "Warning"
        else:
            callout_type = "Note"
        
        # Build callout content
        if title:
            callout_content = f"**{title}**\n\n{content_text}"
        else:
            callout_content = content_text
        
        count += 1
        return f'<{callout_type}>\n{callout_content}\n</{callout_type}>'
    
    # Pattern to match alert blocks
    alert_pattern = r'\{\{%\s*alert\s*([^%}]*)\s*%\}\}([\s\S]*?)\{\{%\s*/alert\s*%\}\}'
    
    def replace_alert(match):
        nonlocal count
        attrs = match.group(1).strip() if match.group(1) else ""
        content_text = match.group(2).strip()
        
        # Extract title attribute if present
        title_match = re.search(r'title\s*=\s*["\']([^"\']*)["\']', attrs)
        title = title_match.group(1) if title_match else ""
        
        # Extract color attribute if present
        color_match = re.search(r'color\s*=\s*["\']([^"\']*)["\']', attrs)
        color = color_match.group(1) if color_match else ""
        
        # Determine callout type based on color (default to Note for alerts)
        if color == "info":
            callout_type = "Info"
        elif color == "secondary" or color == "warning":
            callout_type = "Warning"
        else:
            callout_type = "Note"
        
        # Build callout content
        if title:
            callout_content = f"**{title}**\n\n{content_text}"
        else:
            callout_content = content_text
        
        count += 1
        return f'<{callout_type}>\n{callout_content}\n</{callout_type}>'
    
    # Apply conversions
    converted_content = re.sub(pageinfo_pattern, replace_pageinfo, content)
    converted_content = re.sub(alert_pattern, replace_alert, converted_content)
    
    return converted_content, count


def convert_link_shortcodes(content):
    """
    Convert Hugo relref shortcodes to standard markdown links.

    Args:
        content (str): File content to process

    Returns:
        tuple: (converted_content, count_of_replacements)
    """
    # Pattern to match relref shortcodes within markdown links
    # Matches: [text]({{< relref "path" >}})
    pattern = r'\[([^\]]*)\]\(\{\{<\s*relref\s+["\']([^"\']+)["\']\s*>\}\}\)'
    
    def replace_relref(match):
        link_text = match.group(1)
        link_path = match.group(2)
        
        # Remove file extensions (.md, .mdx)
        clean_path = re.sub(r'\.(md|mdx)$', '', link_path)
        
        return f'[{link_text}]({clean_path})'
    
    converted_content = re.sub(pattern, replace_relref, content)
    count = len(re.findall(pattern, content))
    
    return converted_content, count


def convert_html_comments(content):
    """
    Convert HTML comments to JSX comments.

    Args:
        content (str): File content to process

    Returns:
        tuple: (converted_content, count_of_replacements)
    """
    # Pattern to match HTML comments
    # Matches: <!-- comment content -->
    pattern = r'<!--\s*(.*?)\s*-->'
    
    def replace_comment(match):
        comment_content = match.group(1).strip()
        return f'{{/* {comment_content} */}}'
    
    converted_content = re.sub(pattern, replace_comment, content, flags=re.DOTALL)
    count = len(re.findall(pattern, content, flags=re.DOTALL))
    
    return converted_content, count


def convert_shortcodes(content):
    """
    Convert all Hugo shortcodes to Mintlify components.

    Args:
        content (str): File content to process

    Returns:
        tuple: (converted_content, total_count_of_replacements)
    """
    total_count = 0

    # Convert images
    content, img_count = convert_image_shortcodes(content)
    total_count += img_count

    # Convert tabs
    content, tab_count = convert_tab_shortcodes(content)
    total_count += tab_count

    # Convert callouts
    content, callout_count = convert_callout_shortcodes(content)
    total_count += callout_count

    # Convert links
    content, link_count = convert_link_shortcodes(content)
    total_count += link_count

    # Convert comments
    content, comment_count = convert_html_comments(content)
    total_count += comment_count

    return content, total_count


def process_file(file_path, dry_run=False):
    """
    Process a single file to convert all Hugo shortcodes.

    Args:
        file_path (Path): Path to the file to process
        dry_run (bool): If True, don't write changes, just report what would be done

    Returns:
        int: Number of replacements made
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            original_content = f.read()

        converted_content, count = convert_shortcodes(original_content)

        if count > 0:
            if dry_run:
                print(f"Would convert {count} shortcode(s) in: {file_path}")
            else:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(converted_content)
                print(f"Converted {count} shortcode(s) in: {file_path}")

        return count

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return 0


def find_and_convert_files(directory, file_extensions=None, dry_run=False):
    """
    Find and convert Hugo shortcodes in all matching files.

    Args:
        directory (str): Directory to search
        file_extensions (list): List of file extensions to process (default: ['.md', '.mdx'])
        dry_run (bool): If True, don't write changes, just report what would be done

    Returns:
        tuple: (total_files_processed, total_replacements)
    """
    if file_extensions is None:
        file_extensions = ['.md', '.mdx']

    directory_path = Path(directory)
    total_files = 0
    total_replacements = 0

    # Find all matching files
    for ext in file_extensions:
        for file_path in directory_path.rglob(f'*{ext}'):
            if file_path.is_file():
                total_files += 1
                replacements = process_file(file_path, dry_run)
                total_replacements += replacements

    return total_files, total_replacements


def main():
    parser = argparse.ArgumentParser(
        description='Convert Hugo shortcodes to Mintlify components'
    )
    parser.add_argument(
        'directory',
        nargs='?',
        default='.',
        help='Directory to process (default: current directory)'
    )
    parser.add_argument(
        '--extensions',
        nargs='+',
        default=['.md', '.mdx'],
        help='File extensions to process (default: .md .mdx)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be changed without making actual changes'
    )
    parser.add_argument(
        '--file',
        help='Process a specific file instead of a directory'
    )

    args = parser.parse_args()

    if args.file:
        # Process single file
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"Error: File {file_path} does not exist")
            return 1

        replacements = process_file(file_path, args.dry_run)
        if replacements == 0:
            print(f"No Hugo shortcodes found in: {file_path}")
    else:
        # Process directory
        if not os.path.exists(args.directory):
            print(f"Error: Directory {args.directory} does not exist")
            return 1

        print(f"Searching for Hugo shortcodes in {args.directory}")
        print(f"File extensions: {args.extensions}")

        if args.dry_run:
            print("DRY RUN MODE - no files will be modified")

        total_files, total_replacements = find_and_convert_files(
            args.directory,
            args.extensions,
            args.dry_run
        )

        print(f"\nProcessed {total_files} files")
        print(f"Total replacements: {total_replacements}")

        if args.dry_run and total_replacements > 0:
            print("\nRe-run without --dry-run to apply changes")

    return 0


if __name__ == '__main__':
    exit(main())