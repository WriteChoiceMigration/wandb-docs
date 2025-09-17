#!/usr/bin/env python3
"""
Script to find and fix broken links by visiting pages and detecting redirects.
"""

import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException


def parse_broken_links_file(file_path):
    """
    Parse the broken.mdx file to extract page and broken link pairs.

    Args:
        file_path (str): Path to the broken.mdx file

    Returns:
        list: List of dicts with 'page' and 'broken_links' keys
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    entries = []
    current_page = None
    current_links = []

    for line in content.strip().split('\n'):
        line = line.strip()
        if not line:
            continue

        if line.startswith('⎿'):
            # This is a broken link
            broken_link = line.replace('⎿', '').strip()
            if current_page:
                current_links.append(broken_link)
        else:
            # This is a new page
            if current_page and current_links:
                entries.append({
                    'page': current_page,
                    'broken_links': current_links.copy()
                })
            current_page = line
            current_links = []

    # Don't forget the last entry
    if current_page and current_links:
        entries.append({
            'page': current_page,
            'broken_links': current_links.copy()
        })

    return entries


def setup_webdriver():
    """Setup Chrome webdriver with appropriate options."""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')

    try:
        driver = webdriver.Chrome(options=chrome_options)
        return driver
    except Exception as e:
        print(f"Failed to setup Chrome webdriver: {e}")
        print("Please ensure Chrome and chromedriver are installed")
        sys.exit(1)


def find_correct_link(driver, base_url, page_path, broken_link):
    """
    Visit a page and try to find the correct link for a broken one.

    Args:
        driver: Selenium WebDriver instance
        base_url (str): Base URL of the site
        page_path (str): Path to the page containing the broken link
        broken_link (str): The broken link to find a fix for

    Returns:
        str or None: The correct link if found, None otherwise
    """
    try:
        # Construct the full URL for the page
        page_url = urljoin(base_url, page_path.replace('.mdx', ''))
        print(f"  Visiting: {page_url}")

        driver.get(page_url)
        time.sleep(2)  # Wait for page to load

        # Try to find a link that matches the broken link text or href
        broken_path = broken_link.split('#')[0] if '#' in broken_link else broken_link
        broken_anchor = broken_link.split('#')[1] if '#' in broken_link else None

        # Strategy 1: Look for links with similar href
        links = driver.find_elements(By.TAG_NAME, 'a')

        for link in links:
            href = link.get_attribute('href')
            if not href:
                continue

            # Check if this link might be the correct version of the broken link
            if broken_path in href or href.endswith(broken_path.split('/')[-1]):
                # Try clicking the link to see where it goes
                try:
                    original_url = driver.current_url
                    driver.execute_script("arguments[0].click();", link)
                    time.sleep(1)

                    new_url = driver.current_url
                    if new_url != original_url:
                        # Parse the new URL to get the path
                        parsed = urlparse(new_url)
                        correct_path = parsed.path
                        if parsed.fragment and broken_anchor:
                            correct_path += f"#{parsed.fragment}"
                        elif broken_anchor:
                            correct_path += f"#{broken_anchor}"

                        driver.back()
                        time.sleep(1)
                        return correct_path

                except Exception as e:
                    print(f"    Error clicking link: {e}")
                    continue

        # Strategy 2: Look for text that might indicate the correct section
        if broken_anchor:
            try:
                # Look for headers or elements with IDs that match the anchor
                possible_targets = driver.find_elements(By.XPATH, f"//*[@id='{broken_anchor}']")
                if possible_targets:
                    current_path = urlparse(driver.current_url).path
                    return f"{current_path}#{broken_anchor}"

                # Look for headers with text that might match
                headers = driver.find_elements(By.XPATH, "//h1|//h2|//h3|//h4|//h5|//h6")
                for header in headers:
                    header_id = header.get_attribute('id')
                    if header_id and broken_anchor.lower() in header_id.lower():
                        current_path = urlparse(driver.current_url).path
                        return f"{current_path}#{header_id}"

            except Exception as e:
                print(f"    Error looking for anchors: {e}")

        return None

    except Exception as e:
        print(f"    Error processing {page_path}: {e}")
        return None


def main():
    """Main function to process broken links and generate report."""
    # Parse command line arguments
    base_url = "https://docs.wandb.ai"  # Default base URL
    if len(sys.argv) > 1:
        base_url = sys.argv[1]

    broken_links_file = "broken.mdx"
    if len(sys.argv) > 2:
        broken_links_file = sys.argv[2]

    print(f"Processing broken links from: {broken_links_file}")
    print(f"Base URL: {base_url}")
    print("-" * 50)

    # Parse the broken links file
    try:
        entries = parse_broken_links_file(broken_links_file)
        print(f"Found {len(entries)} pages with broken links")
    except Exception as e:
        print(f"Error parsing broken links file: {e}")
        sys.exit(1)

    # Setup webdriver
    driver = setup_webdriver()

    try:
        report = []

        for entry in entries:
            page = entry['page']
            broken_links = entry['broken_links']

            print(f"\nProcessing page: {page}")

            page_report = {
                'page': page,
                'links': []
            }

            for broken_link in broken_links:
                print(f"  Checking broken link: {broken_link}")

                correct_link = find_correct_link(driver, base_url, page, broken_link)

                link_report = {
                    'broken': broken_link,
                    'fix': correct_link
                }

                page_report['links'].append(link_report)

                if correct_link:
                    print(f"    ✓ Found fix: {correct_link}")
                else:
                    print(f"    ✗ No fix found")

            report.append(page_report)

    finally:
        driver.quit()

    # Generate report
    report_file = "broken_links_report.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n" + "="*50)
    print(f"Report saved to: {report_file}")

    # Print summary
    total_broken = sum(len(entry['links']) for entry in report)
    total_fixed = sum(1 for entry in report for link in entry['links'] if link['fix'])

    print(f"Summary:")
    print(f"  Total broken links: {total_broken}")
    print(f"  Links fixed: {total_fixed}")
    print(f"  Success rate: {total_fixed/total_broken*100:.1f}%")


if __name__ == "__main__":
    main()