# rss_reader_multi.py

import feedparser
import requests
import sys
import textwrap
import html
import re

# --- Configuration ---
DESCRIPTION_WRAP_WIDTH = 80

# --- Core Functions (fetch_feed_content, parse_feed, display_feed_data are the same as above) ---

def fetch_feed_content(url):
    """Fetches the content from the given URL."""
    try:
        headers = {'User-Agent': 'SimplePythonRssReader/1.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching URL '{url}': {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"An unexpected error occurred during fetch: {e}", file=sys.stderr)
        return None

def parse_feed(feed_content):
    """Parses the feed content using feedparser."""
    if not feed_content:
        return None
    try:
        feed_data = feedparser.parse(feed_content)
        if feed_data.bozo:
            bozo_exception = feed_data.get('bozo_exception', 'Unknown parsing error')
            print(f"Warning: Feed may be malformed. Parser message: {bozo_exception}", file=sys.stderr)
        return feed_data
    except Exception as e:
        print(f"An unexpected error occurred during parsing: {e}", file=sys.stderr)
        return None

def display_feed_data(feed_data, url):
    """Displays the parsed feed data in a readable format."""
    if not feed_data:
        print(f"Could not parse or display data for {url}.", file=sys.stderr)
        return

    print("-" * (DESCRIPTION_WRAP_WIDTH + 4)) # Separator
    print(f"Feed Source: {url}")

    feed_title = feed_data.feed.get('title', 'No Title Found')
    feed_description = feed_data.feed.get('description') or feed_data.feed.get('subtitle', 'No Description Found')

    print(f"\n--- Feed: {feed_title} ---")
    if feed_description:
        print(f"Description: {feed_description}\n")

    if not feed_data.entries:
        print("No entries found in this feed.")
        print("-" * (DESCRIPTION_WRAP_WIDTH + 4))
        return

    print("--- Entries ---")
    for entry in feed_data.entries:
        title = entry.get('title', 'No Title')
        link = entry.get('link', 'No Link')
        description = entry.get('description') or entry.get('summary', 'No Description')

        print(f"\n* Title: {title}")
        print(f"  Link: {link}")

        if description:
            cleaned_description = re.sub('<[^<]+?>', ' ', description).strip()
            cleaned_description = html.unescape(cleaned_description)
            wrapped_description = textwrap.fill(cleaned_description, width=DESCRIPTION_WRAP_WIDTH, initial_indent='  Desc: ', subsequent_indent='        ')
            print(wrapped_description)
        else:
            print("  Desc: Not Available")

    print("-" * (DESCRIPTION_WRAP_WIDTH + 4)) # Footer Separator


def get_feed_urls_from_args_or_input():
    """Gets feed URLs from command line args or prompts the user."""
    if len(sys.argv) > 1:
        # Use URLs from command line arguments
        urls = sys.argv[1:]
        print(f"Processing {len(urls)} feed(s) from command line arguments.")
        return urls
    else:
        # Get URLs from user input
        urls = []
        print("Enter RSS feed URLs one by one. Press Enter on an empty line to finish.")
        while True:
            url = input(f"URL #{len(urls) + 1}: ").strip()
            if not url:
                break
            urls.append(url)
        if not urls:
            print("No URLs entered. Exiting.")
            sys.exit(1)
        return urls

# --- Main Execution ---

def main():
    """Main function to run the RSS reader for multiple URLs."""
    feed_urls = get_feed_urls_from_args_or_input()

    for feed_url in feed_urls:
        print(f"\n>>> Processing feed: {feed_url}")
        print("Fetching content...")
        feed_content = fetch_feed_content(feed_url)

        if feed_content:
            print("Parsing feed...")
            parsed_data = parse_feed(feed_content)
            if parsed_data:
                print("Displaying feed:")
                display_feed_data(parsed_data, feed_url)
            else:
                print(f"Failed to parse the feed content for {feed_url}.")
        else:
            print(f"Failed to fetch the feed content for {feed_url}.")
        print("<<< Finished processing feed.") # Indicate end of processing for one feed

if __name__ == "__main__":
    main()

