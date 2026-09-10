import re

from urllib.parse import urljoin, urlparse


FEED_EXTENSIONS = ['.rss', '.xml', '.atom', '.feed']
FEED_PATTERNS = [
    r'rss', r'atom', r'feed', r'xml',
    r'/news/', r'/feeds/', r'/syndication/'
]
# Extensions to exclude
EXCLUDE_EXTENSIONS = ['.html', '.htm', '.php', '.aspx', '.jsp']



def duplicate_feeds(feeds):
    seen_urls = set()
    unique_feeds = []
    original_count = len(feeds)
    
    for feed in feeds:
        url = feed.get('url', '')
        
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_feeds.append(feed)
    
    stats = {
        'original_count': original_count,
        'unique_count': len(unique_feeds),
        'duplicates_removed': original_count - len(unique_feeds)
    }
    
    return {
        'feeds': unique_feeds,
        'stats': stats
    }
def is_feed_url(url):
    """Check if URL looks like an RSS/Atom feed."""
    # url_lower = url.lower()
    url_lower = url.lower()
    parsed = urlparse(url)
    
    # Exclude HTML and other web pages
    for ext in EXCLUDE_EXTENSIONS:
        if url_lower.endswith(ext):
            return False
    # catches feeds.abcnews.com
    if 'feeds.' in parsed.netloc:
        return True
    
    if parsed.fragment:
        return False
    for ext in FEED_EXTENSIONS:
        if ext in url_lower:
            return True
    
    for pattern in FEED_PATTERNS:
        if re.search(pattern, url_lower):
            return True
    
    return False

def find_tags_type(soup, page_url):
    feeds = []
    try:

        for link in soup.find_all('link', type=True):
            print(f"Found {len(link)}")
            link_type = link.get('type', '').lower()
            if 'rss' in link_type or 'atom' in link_type or 'xml' in link_type:
                href = link.get('href')
                if is_feed_url(href):
                    full_url = urljoin(page_url, href)
                if href:
                    feeds.append({
                        'url': urljoin(page_url, href),
                        'title': link.get('title', ''),
                        'type': link_type,
                        'source': 'link_tag'
                    })
        return feeds
    except Exception as e:
        return e

def find_tags_url(soup, page_url):
    """Find feed URLs inside <a href> tags."""
    feeds = []

    for a in soup.find_all('a', href=True):
        href = a['href']

        if is_feed_url(href):
            full_url = urljoin(page_url, href)

            feeds.append({
                'url': full_url,
                'title': a.get_text(strip=True),
                'type': 'unknown',
                'source': 'a_tag'
            })

    return feeds

        