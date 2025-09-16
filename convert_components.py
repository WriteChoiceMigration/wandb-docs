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
{{% /tabpane %}}
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

{{ %alert% }}
Content here
{{ /%alert% }}
To:
<Note>
Content here
</Note>

{{< alert title="Important" color="warning" >}}
Content here
{{< /alert >}}
To:
<Warning>
**Important**

Content here
</Warning>

{{< alert title="Tip" >}}
Content here
{{< /alert >}}
To:
<Tip>
Content here
</Tip>

[W&B Runs]({{< relref "/ref/python/sdk/classes/run.md" >}})
To:
[W&B Runs](/ref/python/sdk/classes/run)

[automation]({{< relref "/guides/core/automations/" >}}> )
To:
[automation](/guides/core/automations/)

[W&B Runs]({{< relref path="/guides/models/track/runs/" lang="ja" >}})
To:
[W&B Runs](/ja/guides/models/track/runs/)

[new Slack integration]({{ relref "#create-a-slack-automation" }})
To:
[new Slack integration](#create-a-slack-automation)

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

{{< cta-button githubLink="https://github.com/wandb/wandb/tree/main/wandb/sdk/launch/agent.py" >}}
To:
<Card title="View the source code" href="https://github.com/wandb/wandb/tree/main/wandb/sdk/launch/agent.py" icon="github">
</Card>

{{< cardpane >}}
{{< card >}}
<a href="/tutorials/experiments/">
<h2 className="card-title">Track experiments</h2>
</a>
<p className="card-content">Use W&B for machine learning experiment tracking...</p>
{{< /card >}}
{{< /cardpane >}}
To:
<Card title="Track experiments" href="/tutorials/experiments/">
Use W&B for machine learning experiment tracking...
</Card>

{{< readfile file="/_includes/enterprise-cloud-only.md" >}}
To:
import EnterpriseCloudOnly from "/snippets/en/_includes/enterprise-cloud-only.mdx";

<EnterpriseCloudOnly/>

![Screenshot of the Registry Automations tab](/images/automations/registry_tab.png)
To:
<Frame>
![Screenshot of the Registry Automations tab](/images/automations/registry_tab.png)
</Frame>
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
    pattern = r"\{\{<\s*img\s+([^>]+)\s*>\}\}"

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
        other_attrs = re.sub(
            r'(src\s*=\s*["\'][^"\']+["\']|alt\s*=\s*["\'][^"\']*["\'])\s*',
            "",
            attributes,
        ).strip()
        if other_attrs:
            img_attrs += f" {other_attrs}"

        return f"<Frame>\n    <img {img_attrs}  />\n</Frame>"

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

    # Pattern to match tabpane and tab blocks with mixed bracket types
    # This handles nested structure: {{< tabpane >}} ... {{% tab %}} ... {{% /tab %}} ... {{< /tabpane >}}
    # or {{< tabpane >}} ... {{% tab %}} ... {{% /tab %}} ... {{% /tabpane %}}
    tabpane_pattern = (
        r"\{\{<\s*tabpane[^>]*>\}\}([\s\S]*?)\{\{[%<]\s*/tabpane\s*[%>]\}\}"
    )

    def replace_tabpane(match):
        nonlocal count
        tabpane_content = match.group(1).strip()

        # Extract individual tabs
        tab_pattern = r"\{\{%\s*tab\s+([^%}]+)%\}\}([\s\S]*?)\{\{%\s*/tab\s*%\}\}"
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
    pageinfo_pattern = (
        r"\{\{%\s*pageinfo\s*([^%}]*)\s*%\}\}([\s\S]*?)\{\{%\s*/pageinfo\s*%\}\}"
    )

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

        # Determine callout type based on title first, then color
        if title and title.lower() == "tip":
            callout_type = "Tip"
        elif color == "info":
            callout_type = "Info"
        elif color == "secondary":
            callout_type = "Warning"
        elif color == "warning":
            callout_type = "Danger"
        else:
            callout_type = "Note"

        # Build callout content
        if title and title.lower() != "tip":
            callout_content = f"**{title}**\n\n{content_text}"
        else:
            callout_content = content_text

        count += 1
        return f"<{callout_type}>\n{callout_content}\n</{callout_type}>"

    # Pattern to match alert blocks with {% %} syntax
    alert_pattern = r"\{\{%\s*alert\s*([^%}]*)\s*%\}\}([\s\S]*?)\{\{%\s*/alert\s*%\}\}"

    # Pattern to match alert blocks with {{ %alert% }} syntax
    alert_percent_pattern = (
        r"\{\{\s*%\s*alert\s*%\s*\}\}([\s\S]*?)\{\{\s*/\s*%\s*alert\s*%\s*\}\}"
    )

    # Pattern to match alert blocks with {{< alert >}} syntax
    alert_angle_pattern = (
        r"\{\{<\s*alert\s*([^>]*)\s*>\}\}([\s\S]*?)\{\{<\s*/alert\s*>\}\}"
    )

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

        # Determine callout type based on title first, then color
        if title and title.lower() == "tip":
            callout_type = "Tip"
        elif color == "info":
            callout_type = "Info"
        elif color == "secondary" or color == "warning":
            callout_type = "Warning"
        else:
            callout_type = "Note"

        # Build callout content
        if title and title.lower() != "tip":
            callout_content = f"**{title}**\n\n{content_text}"
        else:
            callout_content = content_text

        count += 1
        return f"<{callout_type}>\n{callout_content}\n</{callout_type}>"

    def replace_alert_percent(match):
        nonlocal count
        content_text = match.group(1).strip()
        count += 1
        return f"<Note>\n{content_text}\n</Note>"

    # Apply conversions
    converted_content = re.sub(pageinfo_pattern, replace_pageinfo, content)
    converted_content = re.sub(alert_pattern, replace_alert, converted_content)
    converted_content = re.sub(
        alert_percent_pattern, replace_alert_percent, converted_content
    )
    converted_content = re.sub(alert_angle_pattern, replace_alert, converted_content)

    return converted_content, count


def convert_link_shortcodes(content):
    """
    Convert Hugo relref shortcodes to standard markdown links.
    Handles language-specific links with lang parameter.

    Args:
        content (str): File content to process

    Returns:
        tuple: (converted_content, count_of_replacements)
    """
    # Pattern to match relref shortcodes within markdown links with parameters
    # Matches: [text]({{< relref path="/path" lang="ja" >}})
    pattern1 = r"\[([^\]]*)\]\(\{\{<\s*relref\s+([^>]+)\s*>\}\}[^)]*\)"

    # Pattern to match simple relref shortcodes within markdown links
    # Matches: [text]({{ relref "path" }}) or [text]({{ relref "#anchor" }})
    pattern2 = r'\[([^\]]*)\]\(\{\{\s*relref\s+["\']([^"\']+)["\']\s*\}\}[^)]*\)'

    def replace_relref_with_params(match):
        link_text = match.group(1)
        params = match.group(2).strip()

        # Extract path parameter
        path_match = re.search(r'path\s*=\s*["\']([^"\']+)["\']', params)
        if path_match:
            link_path = path_match.group(1)
        else:
            # Fallback: try to extract a quoted string (old format)
            fallback_match = re.search(r'["\']([^"\']+)["\']', params)
            if fallback_match:
                link_path = fallback_match.group(1)
            else:
                return match.group(0)  # Return original if can't parse

        # Extract lang parameter
        lang_match = re.search(r'lang\s*=\s*["\']([^"\']+)["\']', params)
        lang = lang_match.group(1) if lang_match else ""

        # Handle anchor links (starting with #)
        if link_path.startswith("#"):
            return f"[{link_text}]({link_path})"

        # Remove file extensions (.md, .mdx)
        clean_path = re.sub(r"\.(md|mdx)$", "", link_path)

        # Add language prefix if specified
        if lang:
            # Ensure path starts with /
            if not clean_path.startswith("/"):
                clean_path = "/" + clean_path
            clean_path = f"/{lang}{clean_path}"

        return f"[{link_text}]({clean_path})"

    def replace_relref_simple(match):
        link_text = match.group(1)
        link_path = match.group(2)

        # Handle anchor links (starting with #)
        if link_path.startswith("#"):
            return f"[{link_text}]({link_path})"

        # Remove file extensions (.md, .mdx)
        clean_path = re.sub(r"\.(md|mdx)$", "", link_path)

        return f"[{link_text}]({clean_path})"

    # Apply patterns (pattern1 first to handle complex cases, then pattern2 for simple cases)
    converted_content = re.sub(pattern1, replace_relref_with_params, content)
    converted_content = re.sub(pattern2, replace_relref_simple, converted_content)

    count = len(re.findall(pattern1, content)) + len(re.findall(pattern2, content))

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
    pattern = r"<!--\s*(.*?)\s*-->"

    def replace_comment(match):
        comment_content = match.group(1).strip()
        return f"{{/* {comment_content} */}}"

    converted_content = re.sub(pattern, replace_comment, content, flags=re.DOTALL)
    count = len(re.findall(pattern, content, flags=re.DOTALL))

    return converted_content, count


def convert_cta_buttons(content):
    """
    Convert Hugo cta-button shortcodes to Mintlify Card components.

    Args:
        content (str): File content to process

    Returns:
        tuple: (converted_content, count_of_replacements)
    """
    # Pattern to match cta-button shortcodes
    # Matches: {{< cta-button productLink="..." colabLink="..." >}}
    pattern = r"\{\{<\s*cta-button\s+([^>]+)\s*>\}\}"

    def replace_cta_button(match):
        attributes = match.group(1).strip()

        # Extract productLink, colabLink, and githubLink attributes
        product_match = re.search(r'productLink\s*=\s*["\']([^"\']+)["\']', attributes)
        colab_match = re.search(r'colabLink\s*=\s*["\']([^"\']+)["\']', attributes)
        github_match = re.search(
            r'githubLink\s*=\s*["\']?([^"\'>\s]+)["\']?', attributes
        )

        product_link = product_match.group(1) if product_match else ""
        colab_link = colab_match.group(1) if colab_match else ""
        github_link = github_match.group(1) if github_match else ""

        cards = []

        # Add Colab card if link exists
        if colab_link:
            cards.append(
                f'<Card title="Try in Colab" href="{colab_link}" icon="python"/>'
            )

        # Add W&B card if link exists
        if product_link:
            cards.append(
                f'<Card title="Try in W&B" href="{product_link}" icon="sliders-up"/>'
            )

        # Add GitHub card if link exists
        if github_link:
            cards.append(
                f'<Card title="View the source code" href="{github_link}" icon="github"/>'
            )

        if not cards:
            return match.group(0)  # Return original if no valid links found

        if len(cards) == 1:
            # Single card, no CardGroup needed
            return cards[0]
        else:
            # Multiple cards, wrap in CardGroup
            card_content = "\n".join(cards)
            return f"<CardGroup cols={{2}}>\n{card_content}\n</CardGroup>"

    converted_content = re.sub(pattern, replace_cta_button, content)
    count = len(re.findall(pattern, content))

    return converted_content, count


def convert_cardpane_shortcodes(content):
    """
    Convert Hugo cardpane shortcodes to Mintlify Card components.

    Args:
        content (str): File content to process

    Returns:
        tuple: (converted_content, count_of_replacements)
    """
    count = 0

    # Pattern to match cardpane blocks
    # This handles nested structure: {{< cardpane >}} ... {{< card >}} ... {{< /card >}} ... {{< /cardpane >}}
    cardpane_pattern = r"\{\{<\s*cardpane[^>]*>\}\}([\s\S]*?)\{\{<\s*/cardpane\s*>\}\}"

    def replace_cardpane(match):
        nonlocal count
        cardpane_content = match.group(1).strip()

        # Extract individual cards
        card_pattern = r"\{\{<\s*card[^>]*>\}\}([\s\S]*?)\{\{<\s*/card\s*>\}\}"
        cards = []

        for card_match in re.finditer(card_pattern, cardpane_content):
            card_content = card_match.group(1).strip()

            # Extract title from h2 with card-title class
            title_match = re.search(
                r'<h2[^>]*className\s*=\s*["\'][^"\']*card-title[^"\']*["\'][^>]*>(.*?)</h2>',
                card_content,
                re.DOTALL,
            )
            title = title_match.group(1).strip() if title_match else ""

            # Extract href from anchor tag
            href_match = re.search(
                r'<a[^>]*href\s*=\s*["\']([^"\']+)["\'][^>]*>', card_content
            )
            href = href_match.group(1) if href_match else ""

            # Extract content from p with card-content class
            content_match = re.search(
                r'<p[^>]*className\s*=\s*["\'][^"\']*card-content[^"\']*["\'][^>]*>(.*?)</p>',
                card_content,
                re.DOTALL,
            )
            card_text = content_match.group(1).strip() if content_match else ""

            # If we couldn't extract structured content, use the raw content (minus HTML tags)
            if not title and not card_text:
                # Remove HTML tags and extract text
                clean_content = re.sub(r"<[^>]+>", "", card_content).strip()
                card_text = clean_content

            # Build the card
            card_attrs = []
            if title:
                card_attrs.append(f'title="{title}"')
            if href:
                card_attrs.append(f'href="{href}"')

            attrs_str = " ".join(card_attrs)
            if card_text:
                cards.append(f"<Card {attrs_str}>\n{card_text}\n</Card>")
            else:
                cards.append(f"<Card {attrs_str}/>")

        if cards:
            count += 1
            if len(cards) == 1:
                # Single card
                return cards[0]
            else:
                # Multiple cards, wrap in CardGroup or Columns
                card_content = "\n".join(cards)
                cols_count = len(cards) if len(cards) <= 4 else 2
                return (
                    f"<CardGroup cols={{{cols_count}}}>\n{card_content}\n</CardGroup>"
                )
        else:
            return match.group(0)  # Return original if no cards found

    converted_content = re.sub(cardpane_pattern, replace_cardpane, content)

    return converted_content, count


def convert_readfile_shortcodes(content):
    """
    Convert Hugo readfile shortcodes to Mintlify snippet imports.

    Args:
        content (str): File content to process

    Returns:
        tuple: (converted_content, count_of_replacements)
    """
    count = 0
    imports = []

    # Pattern to match readfile shortcodes
    # Matches: {{< readfile file="/_includes/enterprise-cloud-only.md" >}}
    pattern = r'\{\{<\s*readfile\s+file\s*=\s*["\']([^"\']+)["\']\s*>\}\}'

    def replace_readfile(match):
        nonlocal count, imports
        file_path = match.group(1)

        # Extract filename without extension and create component name
        # /_includes/enterprise-cloud-only.md -> enterprise-cloud-only
        filename = file_path.split("/")[-1]
        component_name = filename.replace(".md", "").replace(".mdx", "")

        # Convert to PascalCase for component name
        component_name = "".join(
            word.capitalize() for word in component_name.replace("-", "_").split("_")
        )

        # Create import statement
        snippet_path = f"/snippets/en{file_path.replace('.md', '.mdx')}"
        import_statement = f'import {component_name} from "{snippet_path}";'

        if import_statement not in imports:
            imports.append(import_statement)

        count += 1
        return f"<{component_name}/>"

    # Replace readfile shortcodes
    converted_content = re.sub(pattern, replace_readfile, content)

    # Add imports to the top of the file (after frontmatter)
    if imports:
        # Find the end of frontmatter
        frontmatter_end = content.find("---", 3)  # Find second occurrence of ---
        if frontmatter_end != -1:
            frontmatter_end += 3
            # Find the next non-empty line
            while frontmatter_end < len(content) and content[frontmatter_end] in [
                "\n",
                "\r",
            ]:
                frontmatter_end += 1

            # Insert imports after frontmatter
            import_block = "\n".join(imports) + "\n\n"
            converted_content = (
                converted_content[:frontmatter_end]
                + import_block
                + converted_content[frontmatter_end:]
            )
        else:
            # No frontmatter, add imports at the beginning
            import_block = "\n".join(imports) + "\n\n"
            converted_content = import_block + converted_content

    return converted_content, count


def convert_markdown_images(content):
    """
    Convert standalone markdown images to Frame-wrapped images.

    Args:
        content (str): File content to process

    Returns:
        tuple: (converted_content, count_of_replacements)
    """
    count = 0

    # Pattern to match standalone markdown images (not already in Frame)
    # Matches: ![alt text](image_path) on its own line, not already inside <Frame>
    pattern = r"^!\[([^\]]*)\]\(([^)]+)\)\s*$"

    def replace_markdown_image(match):
        nonlocal count
        alt_text = match.group(1)
        image_path = match.group(2)

        count += 1
        return f"<Frame>\n![{alt_text}]({image_path})\n</Frame>"

    # Split content into lines and process each line
    lines = content.split("\n")
    converted_lines = []
    in_frame = False
    frame_depth = 0

    for line in lines:
        # Track if we're inside a Frame component
        if "<Frame>" in line or "<Frame" in line:
            frame_depth += line.count("<Frame>") + line.count("<Frame ")
            in_frame = frame_depth > 0
        if "</Frame>" in line:
            frame_depth -= line.count("</Frame>")
            in_frame = frame_depth > 0

        # Only convert markdown images that are not inside Frame components
        if not in_frame and re.match(pattern, line.strip()):
            converted_lines.append(re.sub(pattern, replace_markdown_image, line))
        else:
            converted_lines.append(line)

    converted_content = "\n".join(converted_lines)
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

    # Convert CTA buttons
    content, cta_count = convert_cta_buttons(content)
    total_count += cta_count

    # Convert cardpanes
    content, cardpane_count = convert_cardpane_shortcodes(content)
    total_count += cardpane_count

    # Convert readfile shortcodes
    content, readfile_count = convert_readfile_shortcodes(content)
    total_count += readfile_count

    # Convert markdown images
    content, md_img_count = convert_markdown_images(content)
    total_count += md_img_count

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
        with open(file_path, "r", encoding="utf-8") as f:
            original_content = f.read()

        converted_content, count = convert_shortcodes(original_content)

        if count > 0:
            if dry_run:
                print(f"Would convert {count} shortcode(s) in: {file_path}")
            else:
                with open(file_path, "w", encoding="utf-8") as f:
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
        file_extensions = [".md", ".mdx"]

    directory_path = Path(directory)
    total_files = 0
    total_replacements = 0

    # Find all matching files
    for ext in file_extensions:
        for file_path in directory_path.rglob(f"*{ext}"):
            if file_path.is_file():
                total_files += 1
                replacements = process_file(file_path, dry_run)
                total_replacements += replacements

    return total_files, total_replacements


def main():
    parser = argparse.ArgumentParser(
        description="Convert Hugo shortcodes to Mintlify components"
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default="ja",
        help="Directory to process (default: current directory)",
    )
    parser.add_argument(
        "--extensions",
        nargs="+",
        default=[".md", ".mdx"],
        help="File extensions to process (default: .md .mdx)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without making actual changes",
    )
    parser.add_argument("--file", help="Process a specific file instead of a directory")

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
            args.directory, args.extensions, args.dry_run
        )

        print(f"\nProcessed {total_files} files")
        print(f"Total replacements: {total_replacements}")

        if args.dry_run and total_replacements > 0:
            print("\nRe-run without --dry-run to apply changes")

    return 0


if __name__ == "__main__":
    exit(main())
