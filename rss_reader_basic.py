# rss_reader_basic.py

import feedparser
import requests
import sys
import textwrap  # For nice description formatting

# --- Configuration ---
# How wide should the description text be wrapped?
DESCRIPTION_WRAP_WIDTH = 80

# --- Core Functions ---

def fetch_feed_content(url):
    """Fetches the content from the given URL."""
    try:
        # Add a user-agent to be polite to servers
        headers = {'User-Agent': 'SimplePythonRssReader/1.0'}
        response = requests.get(url, headers=headers, timeout=10) # 10-second timeout
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
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

        # Check for parsing errors indicated by feedparser
        if feed_data.bozo:
            bozo_exception = feed_data.get('bozo_exception', 'Unknown parsing error')
            print(f"Warning: Feed may be malformed. Parser message: {bozo_exception}", file=sys.stderr)
            # Decide if you want to proceed despite errors. Often, data is still usable.
            # if not feed_data.entries: # If there are absolutely no entries, maybe stop
            #    return None

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

    # Display Feed Title and Description (if available)
    feed_title = feed_data.feed.get('title', 'No Title Found')
    feed_description = feed_data.feed.get('description') or feed_data.feed.get('subtitle', 'No Description Found') # Handle Atom feeds too

    print(f"\n--- Feed: {feed_title} ---")
    if feed_description:
        print(f"Description: {feed_description}\n")

    if not feed_data.entries:
        print("No entries found in this feed.")
        print("-" * (DESCRIPTION_WRAP_WIDTH + 4)) # Separator
        return

    print("--- Entries ---")
    for entry in feed_data.entries:
        title = entry.get('title', 'No Title')
        link = entry.get('link', 'No Link')
        description = entry.get('description') or entry.get('summary', 'No Description') # Handle Atom

        print(f"\n* Title: {title}")
        print(f"  Link: {link}")

        # Clean up and wrap description (often contains HTML)
        # A more robust solution would use BeautifulSoup to strip HTML,
        # but for plain text display, this is a basic approach.
        if description:
            # Basic HTML tag removal (replace with space)
            import re
            cleaned_description = re.sub('<[^<]+?>', ' ', description).strip()
            # Decode HTML entities (like &)
            import html
            cleaned_description = html.unescape(cleaned_description)
            # Wrap text
            wrapped_description = textwrap.fill(cleaned_description, width=DESCRIPTION_WRAP_WIDTH, initial_indent='  Desc: ', subsequent_indent='        ')
            print(wrapped_description)
        else:
            print("  Desc: Not Available")

    print("-" * (DESCRIPTION_WRAP_WIDTH + 4)) # Footer Separator

# --- Main Execution ---

def main():
    """Main function to run the RSS reader."""
    if len(sys.argv) > 1:
        # Use URL from command line argument
        feed_url = sys.argv[1]
        print(f"Fetching feed from command line argument: {feed_url}")
    else:
        # Get URL from user input
        feed_url = input("Enter the RSS feed URL: ").strip()
        if not feed_url:
            print("No URL entered. Exiting.")
            sys.exit(1)

    print(f"Fetching content from {feed_url}...")
    feed_content = fetch_feed_content(feed_url)

    if feed_content:
        print("Parsing feed...")
        parsed_data = parse_feed(feed_content)
        if parsed_data:
            print("Displaying feed:")
            display_feed_data(parsed_data, feed_url)
        else:
            print("Failed to parse the feed content.")
    else:
        print("Failed to fetch the feed content.")

if __name__ == "__main__":
    main()

