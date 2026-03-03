#!/usr/bin/env python3
"""
Kirishima News Scraper

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
    }
}

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
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def scrape(self):
        """Scrape news from Kirishima City Hall."""
        items = []
        try:
            logger.info(f"Scraping {self.config['name']}...")
            items.extend(self._scrape_rss())
        except Exception as e:
            logger.error(f"Error scraping {self.config['name']}: {e}")
        return items
    
    def _scrape_rss(self):
        """Scrape RSS feed from Kirishima City Hall."""
        items = []
        try:
            feed = feedparser.parse(self.config['rss'])
            for entry in feed.entries[:10]:  # Get last 10 items
                try:
                    title = entry.get('title', '')
                    link = entry.get('link', '')
                    published = entry.get('published', '')
                    
                    if not title or not link:
                        continue
                    
                    # Parse date
                    date = self._parse_date(published)
                    
                    # Extract description
                    description = entry.get('summary', '')
                    if description:
                        # Remove HTML tags
                        description = BeautifulSoup(description, 'html.parser').get_text()
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
                except Exception as e:
                    logger.warning(f"Error parsing RSS entry: {e}")
            
            logger.info(f"Scraped {len(items)} items from {self.config['name']}")
        except Exception as e:
            logger.error(f"Error scraping RSS feed: {e}")
        
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
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def scrape(self):
        """Scrape events from Kirinavi."""
        items = []
        try:
            logger.info(f"Scraping {self.config['name']}...")
            # Kirinavi scraping - simplified for HTML structure
            items.extend(self._scrape_html())
        except Exception as e:
            logger.error(f"Error scraping {self.config['name']}: {e}")
        return items
    
    def _scrape_html(self):
        """Scrape HTML page."""
        items = []
        try:
            response = self.session.get(self.config['url'], timeout=10)
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Note: Actual selectors depend on Kirinavi's HTML structure
            # This is a placeholder - adjust selectors based on actual site structure
            articles = soup.find_all('article', class_='event-item', limit=10)
            
            for article in articles:
                try:
                    title_elem = article.find('h3', class_='event-title')
                    link_elem = article.find('a')
                    date_elem = article.find('span', class_='event-date')
                    
                    if not (title_elem and link_elem):
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    link = urljoin(self.config['url'], link_elem.get('href', ''))
                    date_str = date_elem.get_text(strip=True) if date_elem else ''
                    
                    item = NewsItem(
                        title=title,
                        url=link,
                        source=self.config['source'],
                        source_name=self.config['name'],
                        date=self._parse_date(date_str),
                        category='events',
                    )
                    items.append(item)
                except Exception as e:
                    logger.warning(f"Error parsing Kirinavi entry: {e}")
            
            logger.info(f"Scraped {len(items)} items from {self.config['name']}")
        except Exception as e:
            logger.error(f"Error scraping HTML: {e}")
        
        return items
    
    def _parse_date(self, date_str):
        """Parse date string."""
        if not date_str:
            return datetime.now()
        try:
            return dateutil_parser.parse(date_str)
        except:
            return datetime.now()

class MyplaceScraper:
    """Scrapes news from Myplace Kirishima."""
    
    def __init__(self):
        self.config = CONFIG['scrapers']['myplace']
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def scrape(self):
        """Scrape news from Myplace."""
        items = []
        try:
            logger.info(f"Scraping {self.config['name']}...")
            items.extend(self._scrape_html())
        except Exception as e:
            logger.error(f"Error scraping {self.config['name']}: {e}")
        return items
    
    def _scrape_html(self):
        """Scrape HTML page."""
        items = []
        try:
            response = self.session.get(self.config['url'], timeout=10)
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Note: Actual selectors depend on Myplace's HTML structure
            # This is a placeholder - adjust selectors based on actual site structure
            articles = soup.find_all('div', class_='news-item', limit=10)
            
            for article in articles:
                try:
                    title_elem = article.find('h4', class_='news-title')
                    link_elem = article.find('a')
                    
                    if not (title_elem and link_elem):
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    link = urljoin(self.config['url'], link_elem.get('href', ''))
                    
                    item = NewsItem(
                        title=title,
                        url=link,
                        source=self.config['source'],
                        source_name=self.config['name'],
                    )
                    items.append(item)
                except Exception as e:
                    logger.warning(f"Error parsing Myplace entry: {e}")
            
            logger.info(f"Scraped {len(items)} items from {self.config['name']}")
        except Exception as e:
            logger.error(f"Error scraping HTML: {e}")
        
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
        except Exception as e:
            logger.error(f"Error running scraper: {e}")
    
    logger.info(f"Total items scraped: {len(all_items)}")
    return all_items

def deduplicate(items):
    """Remove duplicate items based on URL."""
    seen_urls = set()
    unique_items = []
    
    for item in items:
        if item.url not in seen_urls:
            unique_items.append(item)
            seen_urls.add(item.url)
    
    logger.info(f"Deduplicated: {len(items)} -> {len(unique_items)}")
    return unique_items

def main():
    """Main function."""
    logger.info("Starting Kirishima News Scraper")
    
    # Scrape all sources
    items = scrape_all()
    
    # Deduplicate
    items = deduplicate(items)
    
    # Save to JSON
    output_file = os.path.join(os.path.dirname(__file__), 'scraped_items.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump([item.to_dict() for item in items], f, ensure_ascii=False, indent=2)
    
    logger.info(f"Saved {len(items)} items to {output_file}")
    
    return items

if __name__ == '__main__':
    try:
        items = main()
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
