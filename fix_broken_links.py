"""
Script to find and fix broken links by visiting pages and detecting redirects.
"""

import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse
from difflib import SequenceMatcher
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import queue
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    WebDriverException,
)

# Configuration
MAX_INSTANCES = 15  # Maximum number of parallel Selenium instances


def check_redirect(base_url, broken_link, timeout=10):
    """
    Check if a broken link redirects to a valid URL using HTTP requests.

    Args:
        base_url: Base URL for the site
        broken_link: The broken link path to check
        timeout: Request timeout in seconds

    Returns:
        str or None: The final redirected URL path if found, None otherwise
    """
    try:
        # Construct the full URL
        if broken_link.startswith("/"):
            full_url = base_url.rstrip("/") + broken_link
        else:
            full_url = urljoin(base_url.rstrip("/") + "/", broken_link)

        print(f"    Checking redirect for: {full_url}")

        # Make a HEAD request to follow redirects without downloading content
        response = requests.head(full_url, allow_redirects=True, timeout=timeout)

        # If we got a successful response and the URL changed, we found a redirect
        if response.status_code == 200 and response.url != full_url:
            # Extract the path from the final URL
            final_parsed = urlparse(response.url)
            final_path = final_parsed.path
            if final_parsed.fragment:
                final_path += f"#{final_parsed.fragment}"

            print(f"    Found redirect: {broken_link} -> {final_path}")
            return final_path

        # Also check if the original URL actually works (might not be broken)
        elif response.status_code == 200 and response.url == full_url:
            print(f"    URL is actually valid: {broken_link}")
            return broken_link

    except requests.exceptions.RequestException as e:
        print(f"    HTTP redirect check failed: {e}")
    except Exception as e:
        print(f"    Unexpected error in redirect check: {e}")

    return None


def extract_link_text_from_mdx(mdx_file_path, broken_link):
    """
    Extract the clickable text for a broken link from the MDX file.

    Args:
        mdx_file_path (str): Path to the MDX file
        broken_link (str): The broken link URL

    Returns:
        str or None: The text that should be clickable, or None if not found
    """
    try:
        with open(mdx_file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Look for markdown link pattern [text](broken_link)
        import re

        pattern = rf"\[([^\]]+)\]\({re.escape(broken_link)}\)"
        match = re.search(pattern, content)

        if match:
            link_text = match.group(1)
            print(f"    Found link text for {broken_link}: '{link_text}'")
            return link_text

        print(f"    No link text found for {broken_link} in MDX file")
        return None

    except Exception as e:
        print(f"    Error reading MDX file: {e}")
        return None


def parse_broken_links_file(file_path):
    """
    Parse the broken.mdx file to extract page and broken link pairs.

    Args:
        file_path (str): Path to the broken.mdx file

    Returns:
        list: List of dicts with 'page' and 'broken_links' keys
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    entries = []
    current_page = None
    current_links = []

    for line in content.strip().split("\n"):
        line = line.strip()
        if not line:
            continue

        if line.startswith("⎿"):
            # This is a broken link
            broken_link = line.replace("⎿", "").strip()
            if current_page:
                current_links.append(broken_link)
        else:
            # This is a new page
            if current_page and current_links:
                entries.append(
                    {"page": current_page, "broken_links": current_links.copy()}
                )
            current_page = line
            current_links = []

    # Don't forget the last entry
    if current_page and current_links:
        entries.append({"page": current_page, "broken_links": current_links.copy()})

    return entries


def setup_webdriver():
    """Setup Chrome webdriver with appropriate options."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--disable-features=VizDisplayCompositor")
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )

    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.implicitly_wait(10)
        return driver
    except Exception as e:
        print(f"Failed to setup Chrome webdriver: {e}")
        print("Please ensure Chrome and chromedriver are installed")
        sys.exit(1)


def wait_for_page_load(driver, timeout=10):
    """Wait for page to fully load."""
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        time.sleep(1)  # Additional buffer for dynamic content
        return True
    except TimeoutException:
        return False


def similarity_score(a, b):
    """Calculate similarity score between two strings."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def analyze_page_content(driver):
    """Analyze page content to understand navigation structure."""
    content_info = {
        "nav_links": [],
        "section_headers": [],
        "breadcrumbs": [],
        "page_structure": {},
    }

    try:
        # Extract navigation links
        nav_elements = driver.find_elements(
            By.CSS_SELECTOR, "nav a, .navigation a, .sidebar a, .menu a"
        )
        for nav in nav_elements:
            href = nav.get_attribute("href")
            text = nav.text.strip()
            if href and text:
                content_info["nav_links"].append({"href": href, "text": text})

        # Extract section headers with IDs
        headers = driver.find_elements(By.XPATH, "//h1|//h2|//h3|//h4|//h5|//h6")
        for header in headers:
            header_id = header.get_attribute("id")
            text = header.text.strip()
            if header_id or text:
                content_info["section_headers"].append(
                    {"id": header_id, "text": text, "tag": header.tag_name}
                )

        # Extract breadcrumbs
        breadcrumb_elements = driver.find_elements(
            By.CSS_SELECTOR, ".breadcrumb a, [aria-label*='breadcrumb'] a"
        )
        for bc in breadcrumb_elements:
            href = bc.get_attribute("href")
            text = bc.text.strip()
            if href and text:
                content_info["breadcrumbs"].append({"href": href, "text": text})

    except Exception as e:
        print(f"    Error analyzing page content: {e}")

    return content_info


def find_best_match_by_content(broken_link, content_info, current_url):
    """Find the best matching link based on content analysis."""
    broken_path = broken_link.split("#")[0] if "#" in broken_link else broken_link
    broken_anchor = broken_link.split("#")[1] if "#" in broken_link else None

    best_match = None
    best_score = 0

    # Clean the broken path for comparison
    broken_path_parts = [part for part in broken_path.split("/") if part]

    # Check navigation links
    for nav_link in content_info["nav_links"]:
        href_parts = [
            part for part in urlparse(nav_link["href"]).path.split("/") if part
        ]

        # Calculate similarity based on path parts
        common_parts = set(broken_path_parts) & set(href_parts)
        if common_parts:
            score = len(common_parts) / max(len(broken_path_parts), len(href_parts))

            # Boost score if text similarity is high
            text_similarity = similarity_score(broken_path, nav_link["text"])
            score += text_similarity * 0.3

            if score > best_score and score > 0.3:  # Minimum threshold
                best_score = score
                parsed_href = urlparse(nav_link["href"])
                best_match = parsed_href.path
                if broken_anchor:
                    best_match += f"#{broken_anchor}"

    # Check if we need to look for anchor matches on current page
    if broken_anchor and not best_match:
        for header in content_info["section_headers"]:
            if header["id"]:
                # Direct ID match
                if header["id"] == broken_anchor:
                    current_path = urlparse(current_url).path
                    return f"{current_path}#{header['id']}"

                # Fuzzy ID match
                if similarity_score(header["id"], broken_anchor) > 0.7:
                    current_path = urlparse(current_url).path
                    return f"{current_path}#{header['id']}"

            # Text-based matching for anchors
            if header["text"]:
                text_slug = re.sub(r"[^a-zA-Z0-9]+", "-", header["text"].lower()).strip(
                    "-"
                )
                if similarity_score(text_slug, broken_anchor) > 0.7:
                    current_path = urlparse(current_url).path
                    return f"{current_path}#{header['id'] or text_slug}"

    return best_match


def smart_link_navigation(driver, link_element, max_wait=5):
    """Smart navigation that handles different types of links."""
    try:
        original_url = driver.current_url

        # Check if it's a same-page anchor link
        href = link_element.get_attribute("href")
        if href and "#" in href:
            parsed = urlparse(href)
            current_parsed = urlparse(original_url)
            if (
                parsed.netloc == current_parsed.netloc
                and parsed.path == current_parsed.path
            ):
                # It's an anchor link on the same page
                driver.execute_script("arguments[0].click();", link_element)
                time.sleep(0.5)
                return driver.current_url

        # For regular links, click and wait for navigation
        driver.execute_script("arguments[0].click();", link_element)

        # Wait for URL to change or timeout
        start_time = time.time()
        while time.time() - start_time < max_wait:
            if driver.current_url != original_url:
                wait_for_page_load(driver)
                return driver.current_url
            time.sleep(0.1)

        return driver.current_url

    except Exception as e:
        print(f"    Error in smart navigation: {e}")
        return original_url


def find_link_by_text_and_click(driver, link_text, broken_link):
    """
    Find a link element by its text and click it to see where it goes.

    Args:
        driver: Selenium webdriver instance
        link_text: The exact text of the link to find
        broken_link: The original broken link for context

    Returns:
        tuple: (final_url_path, method_used) or (None, None) if not found
    """
    try:
        original_url = driver.current_url

        # Try to find the link by exact text
        try:
            link_element = driver.find_element(By.LINK_TEXT, link_text)
            print(f"    Found link with exact text: '{link_text}'")
        except NoSuchElementException:
            # Try partial text match
            try:
                link_element = driver.find_element(By.PARTIAL_LINK_TEXT, link_text)
                print(f"    Found link with partial text: '{link_text}'")
            except NoSuchElementException:
                print(f"    No link found with text: '{link_text}'")
                return None, None

        # Check the href attribute before clicking
        href = link_element.get_attribute("href")
        print(f"    Link href: {href}")

        # If the href is different from the broken link, we found our answer
        if href:
            parsed_href = urlparse(href)
            href_path = parsed_href.path
            if parsed_href.fragment:
                href_path += f"#{parsed_href.fragment}"

            # Compare with broken link
            if href_path != broken_link:
                print(f"    [TEXT SUCCESS] Found corrected href: {href_path}")
                return href_path, "text_href_match"

        # Click the link to see where it actually goes
        try:
            new_url = smart_link_navigation(driver, link_element)
            if new_url != original_url:
                # Parse the new URL to get the correct path
                parsed = urlparse(new_url)
                correct_path = parsed.path
                if parsed.fragment:
                    correct_path += f"#{parsed.fragment}"

                print(f"    [TEXT SUCCESS] Found via click navigation: {correct_path}")
                return correct_path, "text_click_navigation"

        except Exception as e:
            print(f"    Error clicking link: {e}")

        return None, None

    except Exception as e:
        print(f"    Error in text-based link finding: {e}")
        return None, None


def find_correct_link(driver, base_url, page_path, broken_link):
    """
    Visit a page and try to find the correct link for a broken one using enhanced strategies.
    First attempts HTTP redirect detection, then falls back to content-based matching.

    Returns:
        tuple: (correct_link, method_used) where method_used is one of:
               'http_redirect', 'content_matching', 'navigation', None
    """
    try:
        print(f"  Processing broken link: {broken_link}")

        # Strategy 1: Check for HTTP redirects first (faster and more accurate)
        redirect_result = check_redirect(base_url, broken_link)
        if redirect_result:
            print(f"    [REDIRECT SUCCESS] Found via HTTP redirect: {redirect_result}")
            return redirect_result, "http_redirect"

        print(f"    No HTTP redirect found, trying text-based matching...")

        # Strategy 2: Text-based matching using MDX file
        # Construct the full URL for the page
        clean_page_path = page_path.replace(".mdx", "").lstrip("/")
        page_url = urljoin(base_url.rstrip("/") + "/", clean_page_path)
        print(f"  Visiting: {page_url}")

        driver.get(page_url)
        if not wait_for_page_load(driver):
            print(f"    Warning: Page load timeout for {page_url}")
            return None, None

        # Try to find the link text from the MDX file
        mdx_file_path = page_path if page_path.endswith(".mdx") else f"{page_path}.mdx"
        if not mdx_file_path.startswith("/"):
            mdx_file_path = f"D:/writechoice/wandb-docs/{mdx_file_path}"

        link_text = extract_link_text_from_mdx(mdx_file_path, broken_link)
        if link_text:
            text_result = find_link_by_text_and_click(driver, link_text, broken_link)
            if text_result[0]:
                return text_result

        print(f"    No text-based match found, trying content-based matching...")

        # Strategy 3: Content-based matching (fallback)

        # Analyze page content
        content_info = analyze_page_content(driver)

        # Try content-based matching first
        content_match = find_best_match_by_content(
            broken_link, content_info, driver.current_url
        )
        if content_match:
            print(f"    [CONTENT SUCCESS] Found content-based match: {content_match}")
            return content_match, "content_matching"

        # Parse broken link components
        broken_path = broken_link.split("#")[0] if "#" in broken_link else broken_link
        broken_anchor = broken_link.split("#")[1] if "#" in broken_link else None
        broken_parts = [part for part in broken_path.split("/") if part]

        # Strategy 1: Enhanced link discovery with smart navigation
        links = driver.find_elements(By.TAG_NAME, "a")
        candidates = []

        for link in links:
            href = link.get_attribute("href")
            link_text = link.text.strip()

            if not href:
                continue

            # Skip external links
            if href.startswith("http") and base_url not in href:
                continue

            link_parts = [part for part in urlparse(href).path.split("/") if part]

            # Calculate similarity score
            score = 0

            # Path similarity
            common_parts = set(broken_parts) & set(link_parts)
            if common_parts and broken_parts:
                score += len(common_parts) / len(broken_parts) * 0.7

            # Text similarity
            if link_text and broken_parts:
                text_score = max(
                    [similarity_score(link_text, part) for part in broken_parts]
                )
                score += text_score * 0.3

            # Exact ending match gets bonus
            if broken_parts and link_parts and broken_parts[-1] == link_parts[-1]:
                score += 0.2

            if score > 0.3:  # Only consider reasonable matches
                candidates.append((link, score, href))

        # Sort by score and try the best candidates
        candidates.sort(key=lambda x: x[1], reverse=True)

        for link, score, href in candidates[:3]:  # Try top 3 candidates
            try:
                print(f"    Trying link (score: {score:.2f}): {href}")

                original_url = driver.current_url
                new_url = smart_link_navigation(driver, link)

                if new_url != original_url:
                    # Parse the new URL to get the correct path
                    parsed = urlparse(new_url)
                    correct_path = parsed.path

                    # Handle anchors
                    if parsed.fragment:
                        correct_path += f"#{parsed.fragment}"
                    elif broken_anchor:
                        # Try to find the anchor on the new page
                        anchor_element = None
                        try:
                            anchor_element = driver.find_element(By.ID, broken_anchor)
                        except NoSuchElementException:
                            # Look for similar anchors
                            headers = driver.find_elements(
                                By.XPATH, "//h1|//h2|//h3|//h4|//h5|//h6"
                            )
                            for header in headers:
                                header_id = header.get_attribute("id")
                                if (
                                    header_id
                                    and similarity_score(header_id, broken_anchor) > 0.7
                                ):
                                    correct_path += f"#{header_id}"
                                    break
                            else:
                                correct_path += f"#{broken_anchor}"

                        if anchor_element:
                            correct_path += f"#{broken_anchor}"

                    # Navigate back
                    driver.back()
                    wait_for_page_load(driver)

                    return correct_path, "navigation"

            except Exception as e:
                print(f"    Error testing candidate link: {e}")
                continue

        return None, None

    except Exception as e:
        print(f"    Error processing {page_path}: {e}")
        return None, None


def process_entry_worker(entry, base_url, worker_id, progress_queue):
    """
    Worker function to process a single entry (page with broken links) using its own driver.

    Args:
        entry: Dictionary with 'page' and 'broken_links' keys
        base_url: Base URL for the site
        worker_id: Unique identifier for this worker
        progress_queue: Queue to report progress updates

    Returns:
        Dictionary with processed entry results
    """
    driver = None
    try:
        # Setup webdriver for this worker
        driver = setup_webdriver()

        page = entry["page"]
        broken_links = entry["broken_links"]

        progress_queue.put(
            f"Worker {worker_id}: Processing page {page} with {len(broken_links)} broken links"
        )

        page_report = {
            "page": page,
            "links": [],
            "processing_time": time.time(),
            "worker_id": worker_id,
        }

        for link_idx, broken_link in enumerate(broken_links, 1):
            progress_queue.put(
                f"Worker {worker_id}: [{link_idx}/{len(broken_links)}] Checking: {broken_link}"
            )

            try:
                result = find_correct_link(driver, base_url, page, broken_link)
                correct_link = result[0] if result else None
                fix_method = result[1] if result else None

                link_report = {
                    "broken": broken_link,
                    "fix": correct_link,
                    "confidence": "high" if correct_link else "none",
                }

                # Add additional metadata for successful fixes
                if correct_link:
                    link_report["fix_method"] = fix_method or "unknown"
                    link_report["fix_type"] = (
                        "redirect" if correct_link != broken_link else "validation"
                    )

                page_report["links"].append(link_report)

                if correct_link:
                    progress_queue.put(
                        f"Worker {worker_id}: [SUCCESS] Found fix: {correct_link}"
                    )
                else:
                    progress_queue.put(f"Worker {worker_id}: [FAILED] No fix found")

            except Exception as e:
                progress_queue.put(
                    f"Worker {worker_id}: Warning: Error processing link: {e}"
                )
                link_report = {
                    "broken": broken_link,
                    "fix": None,
                    "error": str(e),
                    "confidence": "none",
                }
                page_report["links"].append(link_report)

        page_report["processing_time"] = time.time() - page_report["processing_time"]
        progress_queue.put(
            f"Worker {worker_id}: Completed page {page} in {page_report['processing_time']:.1f}s"
        )

        return page_report

    except Exception as e:
        error_msg = f"Worker {worker_id}: Error processing entry {entry.get('page', 'unknown')}: {e}"
        progress_queue.put(error_msg)
        return {
            "page": entry.get("page", "unknown"),
            "links": [],
            "error": str(e),
            "worker_id": worker_id,
            "processing_time": 0,
        }
    finally:
        if driver:
            try:
                driver.quit()
            except Exception as e:
                progress_queue.put(f"Worker {worker_id}: Error closing driver: {e}")


def process_entries_parallel(entries, base_url, max_workers=None):
    """
    Process multiple entries in parallel using ThreadPoolExecutor.

    Args:
        entries: List of entry dictionaries to process
        base_url: Base URL for the site
        max_workers: Maximum number of worker threads (defaults to MAX_INSTANCES)

    Returns:
        List of processed entry results
    """
    if max_workers is None:
        max_workers = min(MAX_INSTANCES, len(entries))

    progress_queue = queue.Queue()
    results = []

    print(f"Starting parallel processing with {max_workers} workers...")

    # Start a progress monitor thread
    def progress_monitor():
        while True:
            try:
                message = progress_queue.get(timeout=1)
                if message is None:  # Sentinel to stop
                    break
                print(f"  {message}")
                progress_queue.task_done()
            except queue.Empty:
                continue

    progress_thread = threading.Thread(target=progress_monitor, daemon=True)
    progress_thread.start()

    try:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_entry = {
                executor.submit(
                    process_entry_worker, entry, base_url, i + 1, progress_queue
                ): entry
                for i, entry in enumerate(entries)
            }

            # Collect results as they complete
            for future in as_completed(future_to_entry):
                entry = future_to_entry[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    print(
                        f"  Error processing entry {entry.get('page', 'unknown')}: {e}"
                    )
                    results.append(
                        {
                            "page": entry.get("page", "unknown"),
                            "links": [],
                            "error": str(e),
                            "processing_time": 0,
                        }
                    )

    finally:
        # Stop progress monitor
        progress_queue.put(None)
        progress_thread.join(timeout=2)

    return results


def main():
    """Main function to process broken links and generate report."""
    # Parse command line arguments
    base_url = "https://docs.wandb.ai"  # Default base URL
    broken_links_file = "broken.mdx"

    # Simple argument parsing
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg in ["-h", "--help"]:
            print("Usage: python fix_broken_links.py [BASE_URL] [BROKEN_LINKS_FILE]")
            print("  BASE_URL: Base URL for the site (default: https://docs.wandb.ai)")
            print(
                "  BROKEN_LINKS_FILE: File containing broken links (default: broken.mdx)"
            )
            sys.exit(0)
        elif i == 1:
            base_url = arg
        elif i == 2:
            broken_links_file = arg

    print(f"Enhanced Broken Links Fixer")
    print(f"Processing broken links from: {broken_links_file}")
    print(f"Base URL: {base_url}")
    print("-" * 50)

    # Parse the broken links file
    try:
        entries = parse_broken_links_file(broken_links_file)
        print(f"Found {len(entries)} pages with broken links")
        total_links = sum(len(entry["broken_links"]) for entry in entries)
        print(f"Total broken links to fix: {total_links}")
    except Exception as e:
        print(f"Error parsing broken links file: {e}")
        sys.exit(1)

    # Process entries in parallel
    print(f"\nStarting parallel processing with up to {MAX_INSTANCES} workers...")
    print(
        f"You can adjust MAX_INSTANCES at the top of the script to control parallelization"
    )

    try:
        start_time = time.time()
        report = process_entries_parallel(entries, base_url)
        total_time = time.time() - start_time

        print(f"\nParallel processing completed in {total_time:.1f} seconds")

    except KeyboardInterrupt:
        print("\n\nProcess interrupted by user")
        report = []
    except Exception as e:
        print(f"\nUnexpected error during parallel processing: {e}")
        report = []

    # Calculate processed links for metadata
    processed_links = sum(len(entry["links"]) for entry in report)

    # Generate enhanced report
    report_file = "broken_links_report.json"
    enhanced_report = {
        "metadata": {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "base_url": base_url,
            "total_pages": len(entries),
            "total_links_processed": processed_links,
            "max_instances": MAX_INSTANCES,
            "processing_time_seconds": total_time if "total_time" in locals() else 0,
            "script_version": "3.0_parallel",
        },
        "results": report,
    }

    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(enhanced_report, f, indent=2, ensure_ascii=False)

    print(f"\n" + "=" * 50)
    print(f"Parallel enhanced report saved to: {report_file}")

    # Print detailed summary
    total_broken = sum(len(entry["links"]) for entry in report)
    total_fixed = sum(
        1 for entry in report for link in entry["links"] if link.get("fix")
    )
    total_errors = sum(
        1 for entry in report for link in entry["links"] if link.get("error")
    )

    print(f"\nDetailed Summary:")
    print(f"  Total pages processed: {len(report)}")
    print(f"  Total broken links: {total_broken}")
    print(f"  Links successfully fixed: {total_fixed}")
    print(f"  Links with errors: {total_errors}")
    print(f"  Max parallel instances: {MAX_INSTANCES}")
    if "total_time" in locals():
        print(f"  Total processing time: {total_time:.1f} seconds")
        if total_broken > 0:
            print(f"  Average time per link: {total_time/total_broken:.2f} seconds")
    print(
        f"  Success rate: {total_fixed/total_broken*100:.1f}%"
        if total_broken > 0
        else "  Success rate: N/A"
    )

    # Show breakdown by page
    print(f"\nPer-page breakdown:")
    for entry in report:
        page_fixed = sum(1 for link in entry["links"] if link.get("fix"))
        page_total = len(entry["links"])
        print(f"  {entry['page']}: {page_fixed}/{page_total} fixed")

    print(f"\nParallel enhanced script completed!")
    print(f"Processed with up to {MAX_INSTANCES} parallel Selenium instances")
    return total_fixed, total_broken


if __name__ == "__main__":
    main()
