#!/usr/bin/env python3
"""
Kirishima News Scraper (Improved Version)

Scrapes information from:
- Kirishima City Hall (https://www.city.kirishima.lg.jp/)
- Kirinavi (https://kirinavi.com/)
- Myplace Kirishima (https://kirishima.mypl.net/)

Posts to WordPress via REST API.
"""

import os
import sys
import json
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin
import logging
import time

import requests
from bs4 import BeautifulSoup
import feedparser
from dateutil import parser as dateutil_parser

# ===== Logging Setup =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ===== Configuration =====
CONFIG = {
    'scrapers': {
        'kirishima_city': {
            'url': 'https://www.city.kirishima.lg.jp/',
            'rss': 'https://www.city.kirishima.lg.jp/index.xml',
            'enabled': True,
            'source': 'kirishima_city',
            'name': '霧島市役所',
        },
        'kirinavi': {
            'url': 'https://kirinavi.com/',
            'enabled': True,
            'source': 'kirinavi',
            'name': 'きりなび',
        },
        'myplace': {
            'url': 'https://kirishima.mypl.net/',
            'enabled': True,
            'source': 'myplace',
            'name': 'まいぷれ霧島',
        },
    },
    'timeout': 15,  # seconds
    'retries': 2,
}

# Better User-Agent
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

# ===== Scrapers =====

class NewsItem:
    """Represents a news item to be posted."""
    
    def __init__(self, title, url, source, source_name, date=None, description='', category='kirishima-news'):
        self.title = title
        self.url = url
        self.source = source
        self.source_name = source_name
        self.date = date or datetime.now()
        self.description = description
        self.category = category
        
    def to_dict(self):
        return {
            'title': self.title,
            'url': self.url,
            'source': self.source,
            'source_name': self.source_name,
            'date': self.date.isoformat() if isinstance(self.date, datetime) else self.date,
            'description': self.description,
            'category': self.category,
        }

class KirishimaCityScraper:
    """Scrapes news from Kirishima City Hall."""
    
    def __init__(self):
        self.config = CONFIG['scrapers']['kirishima_city']
        self.session = self._create_session()
    
    def _create_session(self):
        """Create a requests session with proper configuration."""
        session = requests.Session()
        session.headers.update({
            'User-Agent': USER_AGENT,
            'Accept': 'application/rss+xml, application/atom+xml, */*',
            'Accept-Language': 'ja-JP,ja;q=0.9',
        })
        return session
    
    def scrape(self):
        """Scrape news from Kirishima City Hall."""
        items = []
        try:
            logger.info(f"Scraping {self.config['name']}...")
            items.extend(self._scrape_rss())
            logger.info(f"✓ Scraped {len(items)} items from {self.config['name']}")
        except Exception as e:
            logger.error(f"✗ Error scraping {self.config['name']}: {e}", exc_info=True)
        return items
    
    def _scrape_rss(self):
        """Scrape RSS feed from Kirishima City Hall."""
        items = []
        try:
            logger.debug(f"Fetching RSS feed: {self.config['rss']}")
            # feedparser doesn't use requests, so we fetch manually
            response = self.session.get(
                self.config['rss'],
                timeout=CONFIG['timeout']
            )
            response.raise_for_status()
            
            feed = feedparser.parse(response.content)
            logger.debug(f"Feed contains {len(feed.entries)} entries")
            
            for entry in feed.entries[:10]:  # Get last 10 items
                try:
                    title = entry.get('title', '').strip()
                    link = entry.get('link', '').strip()
                    published = entry.get('published', '')
                    
                    if not title or not link:
                        continue
                    
                    # Parse date
                    date = self._parse_date(published)
                    
                    # Extract description
                    description = entry.get('summary', '')
                    if description:
                        # Remove HTML tags
                        description = BeautifulSoup(description, 'html.parser').get_text().strip()
                        description = description[:200]  # Limit to 200 chars
                    
                    item = NewsItem(
                        title=title,
                        url=link,
                        source=self.config['source'],
                        source_name=self.config['name'],
                        date=date,
                        description=description,
                    )
                    items.append(item)
                    logger.debug(f"Parsed: {title}")
                except Exception as e:
                    logger.warning(f"Error parsing RSS entry: {e}")
        
        except Exception as e:
            logger.error(f"✗ Error scraping RSS feed: {e}", exc_info=True)
        
        return items
    
    def _parse_date(self, date_str):
        """Parse date string."""
        if not date_str:
            return datetime.now()
        try:
            return dateutil_parser.parse(date_str)
        except:
            return datetime.now()

class KirinaviScraper:
    """Scrapes events from Kirinavi."""
    
    def __init__(self):
        self.config = CONFIG['scrapers']['kirinavi']
        self.session = self._create_session()
    
    def _create_session(self):
        """Create a requests session with proper configuration."""
        session = requests.Session()
        session.headers.update({
            'User-Agent': USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ja-JP,ja;q=0.9',
        })
        return session
    
    def scrape(self):
        """Scrape events from Kirinavi."""
        items = []
        try:
            logger.info(f"Scraping {self.config['name']}...")
            items.extend(self._scrape_html())
            logger.info(f"✓ Scraped {len(items)} items from {self.config['name']}")
        except Exception as e:
            logger.error(f"✗ Error scraping {self.config['name']}: {e}", exc_info=True)
        return items
    
    def _scrape_html(self):
        """Scrape HTML page."""
        items = []
        try:
            logger.debug(f"Fetching: {self.config['url']}")
            response = self.session.get(
                self.config['url'],
                timeout=CONFIG['timeout'],
                allow_redirects=True
            )
            response.raise_for_status()
            response.encoding = 'utf-8'
            
            soup = BeautifulSoup(response.content, 'html.parser')
            logger.debug(f"Page size: {len(response.content)} bytes")
            
            # Try multiple selectors for robustness
            articles = soup.find_all(['article', 'div'], class_=re.compile(r'event|news|item', re.I), limit=10)
            logger.debug(f"Found {len(articles)} elements")
            
            for article in articles:
                try:
                    # Extract title
                    title_elem = article.find(['h2', 'h3', 'h4', 'a'])
                    title = title_elem.get_text(strip=True) if title_elem else None
                    
                    # Extract link
                    link_elem = article.find('a', href=True)
                    link = link_elem.get('href') if link_elem else None
                    
                    if not title or not link:
                        continue
                    
                    # Make absolute URL
                    link = urljoin(self.config['url'], link)
                    
                    item = NewsItem(
                        title=title,
                        url=link,
                        source=self.config['source'],
                        source_name=self.config['name'],
                        category='events',
                    )
                    items.append(item)
                    logger.debug(f"Parsed: {title}")
                except Exception as e:
                    logger.warning(f"Error parsing article: {e}")
        
        except Exception as e:
            logger.error(f"✗ Error scraping HTML: {e}", exc_info=True)
        
        return items

class MyplaceScraper:
    """Scrapes news from Myplace Kirishima."""
    
    def __init__(self):
        self.config = CONFIG['scrapers']['myplace']
        self.session = self._create_session()
    
    def _create_session(self):
        """Create a requests session with proper configuration."""
        session = requests.Session()
        session.headers.update({
            'User-Agent': USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ja-JP,ja;q=0.9',
        })
        return session
    
    def scrape(self):
        """Scrape news from Myplace."""
        items = []
        try:
            logger.info(f"Scraping {self.config['name']}...")
            items.extend(self._scrape_html())
            logger.info(f"✓ Scraped {len(items)} items from {self.config['name']}")
        except Exception as e:
            logger.error(f"✗ Error scraping {self.config['name']}: {e}", exc_info=True)
        return items
    
    def _scrape_html(self):
        """Scrape HTML page."""
        items = []
        try:
            logger.debug(f"Fetching: {self.config['url']}")
            response = self.session.get(
                self.config['url'],
                timeout=CONFIG['timeout'],
                allow_redirects=True
            )
            response.raise_for_status()
            response.encoding = 'utf-8'
            
            soup = BeautifulSoup(response.content, 'html.parser')
            logger.debug(f"Page size: {len(response.content)} bytes")
            
            # Try multiple selectors for robustness
            articles = soup.find_all(['article', 'div'], class_=re.compile(r'news|item|event', re.I), limit=10)
            logger.debug(f"Found {len(articles)} elements")
            
            for article in articles:
                try:
                    # Extract title
                    title_elem = article.find(['h2', 'h3', 'h4', 'a'])
                    title = title_elem.get_text(strip=True) if title_elem else None
                    
                    # Extract link
                    link_elem = article.find('a', href=True)
                    link = link_elem.get('href') if link_elem else None
                    
                    if not title or not link:
                        continue
                    
                    # Make absolute URL
                    link = urljoin(self.config['url'], link)
                    
                    item = NewsItem(
                        title=title,
                        url=link,
                        source=self.config['source'],
                        source_name=self.config['name'],
                    )
                    items.append(item)
                    logger.debug(f"Parsed: {title}")
                except Exception as e:
                    logger.warning(f"Error parsing article: {e}")
        
        except Exception as e:
            logger.error(f"✗ Error scraping HTML: {e}", exc_info=True)
        
        return items

# ===== Main Scraper =====

def scrape_all():
    """Run all scrapers."""
    all_items = []
    
    scrapers = [
        KirishimaCityScraper(),
        KirinaviScraper(),
        MyplaceScraper(),
    ]
    
    for scraper in scrapers:
        try:
            items = scraper.scrape()
            all_items.extend(items)
            # Be polite to servers
            time.sleep(1)
        except Exception as e:
            logger.error(f"Error running scraper: {e}", exc_info=True)
    
    logger.info(f"=== Total items scraped: {len(all_items)} ===")
    return all_items

def deduplicate(items):
    """Remove duplicate items based on URL."""
    seen_urls = set()
    unique_items = []
    
    for item in items:
        if item.url not in seen_urls:
            unique_items.append(item)
            seen_urls.add(item.url)
    
    logger.info(f"Deduplicated: {len(items)} → {len(unique_items)}")
    return unique_items

def main():
    """Main function."""
    logger.info("=" * 50)
    logger.info("Starting Kirishima News Scraper")
    logger.info("=" * 50)
    
    # Scrape all sources
    items = scrape_all()
    
    # Deduplicate
    items = deduplicate(items)
    
    # Save to JSON
    output_file = os.path.join(os.path.dirname(__file__), 'scraped_items.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump([item.to_dict() for item in items], f, ensure_ascii=False, indent=2)
    
    logger.info(f"Saved {len(items)} items to {output_file}")
    logger.info("=" * 50)
    
    return items

if __name__ == '__main__':
    try:
        items = main()
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
