# rss_reader_custom_parser.py

import requests
import sys
import textwrap
import html
import re
import xml.etree.ElementTree as ET # Standard library for XML parsing
import argparse # For command-line option parsing

# --- Configuration ---
DESCRIPTION_WRAP_WIDTH = 80

# --- Core Functions ---

def fetch_feed_content(url):
    """Fetches the content from the given URL."""
    try:
        headers = {'User-Agent': 'SimplePythonRssReader/1.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        # Ensure we decode correctly, try UTF-8 first
        try:
            content = response.content.decode('utf-8')
        except UnicodeDecodeError:
            # Fallback to apparent encoding if UTF-8 fails
            content = response.text
        return content
    except requests.exceptions.RequestException as e:
        print(f"Error fetching URL '{url}': {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"An unexpected error occurred during fetch: {e}", file=sys.stderr)
        return None

# --- Library Parser (feedparser) ---
def parse_feed_library(feed_content):
    """Parses the feed content using feedparser."""
    # Lazy import feedparser only if needed
    try:
        import feedparser
    except ImportError:
        print("Error: 'feedparser' library is required for standard parsing.", file=sys.stderr)
        print("Please install it using: pip install feedparser", file=sys.stderr)
        return None

    if not feed_content:
        return None
    try:
        feed_data = feedparser.parse(feed_content)
        if feed_data.bozo:
            bozo_exception = feed_data.get('bozo_exception', 'Unknown parsing error')
            print(f"Warning (feedparser): Feed may be malformed. Parser message: {bozo_exception}", file=sys.stderr)

        # Convert feedparser output to a common dictionary structure
        parsed = {
            'feed': {
                'title': feed_data.feed.get('title'),
                'description': feed_data.feed.get('description') or feed_data.feed.get('subtitle'),
                'link': feed_data.feed.get('link')
            },
            'entries': [
                {
                    'title': entry.get('title'),
                    'link': entry.get('link'),
                    'description': entry.get('description') or entry.get('summary')
                }
                for entry in feed_data.entries
            ]
        }
        return parsed
    except Exception as e:
        print(f"An unexpected error occurred during feedparser parsing: {e}", file=sys.stderr)
        return None

# --- Custom XML Parser ---
def find_element_text(parent_element, tag_name, namespaces=None):
    """Helper to find text content of a child element, handling namespaces."""
    element = parent_element.find(tag_name, namespaces)
    return element.text.strip() if element is not None and element.text else None

def find_element_link(parent_element, tag_name, namespaces=None):
    """Helper to find link href, handling namespaces and common link tags."""
    link_element = parent_element.find(tag_name, namespaces)
    if link_element is not None:
        # Atom uses <link href="...">
        href = link_element.get('href')
        if href:
            return href
        # RSS uses <link>...</link>
        if link_element.text:
            return link_element.text.strip()
    # Fallback for RSS <channel><link>
    if tag_name == 'link' and parent_element.tag.endswith('channel'):
        return find_element_text(parent_element, 'link', namespaces)
    return None


def parse_feed_custom(feed_content):
    """Parses the feed content using xml.etree.ElementTree (basic RSS/Atom)."""
    if not feed_content:
        return None
    try:
        # Remove potential whitespace/BOM at the beginning
        feed_content = feed_content.strip()
        root = ET.fromstring(feed_content)

        # --- Namespace detection (basic) ---
        # XML namespaces make parsing harder. Atom feeds *always* use them.
        # RSS 2.0 usually doesn't for core elements, but extensions might.
        namespaces = {}
        if '}' in root.tag: # If the root tag itself has a namespace URI
            ns_uri = root.tag.split('}')[0][1:] # Extract URI from {uri}tag
            namespaces['atom'] = ns_uri # Common prefix for Atom
            # Add more known prefixes if needed (e.g., 'content': 'http://purl.org/rss/1.0/modules/content/')

        # Determine if it looks like Atom or RSS
        is_atom = 'atom' in namespaces or root.tag.endswith('feed') # Check namespace or root tag
        is_rss = root.tag.endswith('rss')

        parsed = {'feed': {}, 'entries': []}

        if is_atom:
            # --- Atom Parsing ---
            feed_elem = root
            entry_tag = 'atom:entry'
            feed_title_tag = 'atom:title'
            feed_desc_tag = 'atom:subtitle' # Atom uses subtitle
            feed_link_tag = 'atom:link' # Need to find rel="alternate" ideally
            item_title_tag = 'atom:title'
            item_link_tag = 'atom:link' # Need to find rel="alternate"
            item_desc_tag = 'atom:summary' # Or 'atom:content'

            parsed['feed']['title'] = find_element_text(feed_elem, feed_title_tag, namespaces)
            parsed['feed']['description'] = find_element_text(feed_elem, feed_desc_tag, namespaces)
            # Find the primary feed link (often rel="alternate" or the first one)
            feed_link_elems = feed_elem.findall(feed_link_tag, namespaces)
            primary_feed_link = None
            for link in feed_link_elems:
                if link.get('rel') == 'alternate' or not link.get('rel'): # Prefer alternate or typeless
                    primary_feed_link = link.get('href')
                    if primary_feed_link: break
            if not primary_feed_link and feed_link_elems: # Fallback to first link href
                primary_feed_link = feed_link_elems[0].get('href')
            parsed['feed']['link'] = primary_feed_link


            for item in feed_elem.findall(entry_tag, namespaces):
                entry_data = {}
                entry_data['title'] = find_element_text(item, item_title_tag, namespaces)
                entry_data['description'] = find_element_text(item, item_desc_tag, namespaces)
                # If summary is empty, try content
                if not entry_data['description']:
                    entry_data['description'] = find_element_text(item, 'atom:content', namespaces)

                # Find the primary item link (rel="alternate" or first)
                item_link_elems = item.findall(item_link_tag, namespaces)
                primary_item_link = None
                for link in item_link_elems:
                    if link.get('rel') == 'alternate' or not link.get('rel'):
                        primary_item_link = link.get('href')
                        if primary_item_link: break
                if not primary_item_link and item_link_elems:
                    primary_item_link = item_link_elems[0].get('href')
                entry_data['link'] = primary_item_link

                if entry_data.get('title') or entry_data.get('link'): # Only add if it has some content
                    parsed['entries'].append(entry_data)

        elif is_rss:
            # --- RSS 2.0 Parsing (most common RSS) ---
            channel = root.find('channel')
            if channel is None:
                print("Error (Custom Parser): Could not find <channel> element in RSS feed.", file=sys.stderr)
                return None

            entry_tag = 'item'
            feed_title_tag = 'title'
            feed_desc_tag = 'description'
            feed_link_tag = 'link'
            item_title_tag = 'title'
            item_link_tag = 'link'
            item_desc_tag = 'description' # Could also be 'content:encoded' with namespace

            parsed['feed']['title'] = find_element_text(channel, feed_title_tag, namespaces)
            parsed['feed']['description'] = find_element_text(channel, feed_desc_tag, namespaces)
            parsed['feed']['link'] = find_element_text(channel, feed_link_tag, namespaces) # RSS link is text content

            for item in channel.findall(entry_tag, namespaces):
                entry_data = {}
                entry_data['title'] = find_element_text(item, item_title_tag, namespaces)
                entry_data['link'] = find_element_text(item, item_link_tag, namespaces)
                entry_data['description'] = find_element_text(item, item_desc_tag, namespaces)
                # Add more complex logic here if needed (e.g., check for 'content:encoded')

                if entry_data.get('title') or entry_data.get('link'): # Only add if useful
                    parsed['entries'].append(entry_data)

        else:
            print("Error (Custom Parser): Unknown feed type (neither RSS nor Atom detected).", file=sys.stderr)
            return None

        return parsed

    except ET.ParseError as e:
        print(f"Error (Custom Parser): Failed to parse XML: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"An unexpected error occurred during custom parsing: {e}", file=sys.stderr)
        return None


# --- Display Function (Works with the common dictionary structure) ---
def display_parsed_data(parsed_data, url):
    """Displays the parsed feed data (from either parser)"""
    if not parsed_data:
        print(f"No data to display for {url}.", file=sys.stderr)
        return

    print("-" * (DESCRIPTION_WRAP_WIDTH + 4))
    print(f"Feed Source: {url}")

    feed_info = parsed_data.get('feed', {})
    feed_title = feed_info.get('title', 'No Title Found')
    feed_description = feed_info.get('description', 'No Description Found')

    print(f"\n--- Feed: {feed_title} ---")
    if feed_description:
        print(f"Description: {feed_description}\n")

    entries = parsed_data.get('entries', [])
    if not entries:
        print("No entries found in this feed.")
        print("-" * (DESCRIPTION_WRAP_WIDTH + 4))
        return

    print("--- Entries ---")
    for entry in entries:
        title = entry.get('title', 'No Title')
        link = entry.get('link', 'No Link')
        description = entry.get('description', 'No Description')

        print(f"\n* Title: {title}")
        print(f"  Link: {link}")

        if description:
            # Basic HTML cleaning and wrapping
            cleaned_description = re.sub('<[^<]+?>', ' ', description).strip()
            cleaned_description = html.unescape(cleaned_description)
            wrapped_description = textwrap.fill(cleaned_description, width=DESCRIPTION_WRAP_WIDTH, initial_indent='  Desc: ', subsequent_indent='        ')
            print(wrapped_description)
        else:
            print("  Desc: Not Available")

    print("-" * (DESCRIPTION_WRAP_WIDTH + 4))


def get_feed_urls_from_args(args):
    """Gets feed URLs from command line args."""
    if not args.urls:
        print("Error: No feed URLs provided.", file=sys.stderr)
        sys.exit(1)
    return args.urls

# --- Main Execution ---

def main():
    """Main function to run the RSS reader with parser choice."""
    parser = argparse.ArgumentParser(description="Fetch and display RSS/Atom feeds.")
    parser.add_argument('urls', nargs='*', help="One or more RSS/Atom feed URLs.")
    parser.add_argument('--use-custom-parser', action='store_true',
                        help="Use the built-in basic XML parser instead of the 'feedparser' library.")
    parser.add_argument('--input', action='store_true',
                        help="Prompt for URLs interactively instead of using command-line arguments.")

    args = parser.parse_args()

    if args.input:
        feed_urls = []
        print("Enter RSS feed URLs one by one. Press Enter on an empty line to finish.")
        while True:
            url = input(f"URL #{len(feed_urls) + 1}: ").strip()
            if not url:
                break
            feed_urls.append(url)
        if not feed_urls:
            print("No URLs entered via input. Exiting.")
            sys.exit(1)
    else:
        feed_urls = get_feed_urls_from_args(args)


    if args.use_custom_parser:
        parse_function = parse_feed_custom
        print("Using CUSTOM XML parser.")
    else:
        parse_function = parse_feed_library
        print("Using 'feedparser' library.")


    for feed_url in feed_urls:
        print(f"\n>>> Processing feed: {feed_url}")
        print("Fetching content...")
        feed_content = fetch_feed_content(feed_url)

        if feed_content:
            print("Parsing feed...")
            parsed_data = parse_function(feed_content) # Use the selected parser
            if parsed_data:
                print("Displaying feed:")
                display_parsed_data(parsed_data, feed_url) # Use the unified display function
            else:
                print(f"Failed to parse the feed content for {feed_url}.")
        else:
            print(f"Failed to fetch the feed content for {feed_url}.")
        print("<<< Finished processing feed.")

if __name__ == "__main__":
    main()

