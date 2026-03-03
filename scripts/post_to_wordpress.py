#!/usr/bin/env python3
"""
WordPress REST API Poster

Posts items scraped from Kirishima sources to WordPress.
Requires:
- WP_URL: WordPress site URL
- WP_USER: WordPress username
- WP_APP_PASS: Application Password
"""

import os
import sys
import json
import logging
from base64 import b64encode
from datetime import datetime

import requests

# ===== Logging Setup =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ===== Configuration =====
WP_URL = os.environ.get('WP_URL', '').rstrip('/')
WP_USER = os.environ.get('WP_USER', '')
WP_APP_PASS = os.environ.get('WP_APP_PASS', '')

if not all([WP_URL, WP_USER, WP_APP_PASS]):
    logger.error("Missing required environment variables: WP_URL, WP_USER, WP_APP_PASS")
    sys.exit(1)

class WordPressClient:
    """Client for WordPress REST API."""
    
    def __init__(self, url, username, password):
        self.url = url.rstrip('/')
        self.api_url = f"{self.url}/wp-json/wp/v2"
        self.username = username
        self.password = password
        self.session = requests.Session()
        
        # Setup authentication
        credentials = b64encode(f"{username}:{password}".encode()).decode()
        self.session.headers.update({
            'Authorization': f'Basic {credentials}',
            'User-Agent': 'Kirishima Auto Poster/1.0',
        })
    
    def test_connection(self):
        """Test WordPress connection."""
        try:
            response = self.session.get(f"{self.api_url}/posts?per_page=1")
            if response.status_code == 200:
                logger.info("✓ WordPress connection successful")
                return True
            else:
                logger.error(f"✗ WordPress connection failed: {response.status_code}")
                logger.error(response.text)
                return False
        except Exception as e:
            logger.error(f"✗ Connection error: {e}")
            return False
    
    def get_categories(self):
        """Get all categories."""
        try:
            response = self.session.get(f"{self.api_url}/categories?per_page=50")
            response.raise_for_status()
            categories = response.json()
            return {cat['slug']: cat['id'] for cat in categories}
        except Exception as e:
            logger.error(f"Error getting categories: {e}")
            return {}
    
    def get_category_id(self, slug):
        """Get category ID by slug."""
        try:
            response = self.session.get(
                f"{self.api_url}/categories",
                params={'slug': slug, 'per_page': 1}
            )
            response.raise_for_status()
            categories = response.json()
            if categories:
                return categories[0]['id']
            else:
                logger.warning(f"Category '{slug}' not found")
                return None
        except Exception as e:
            logger.error(f"Error getting category ID: {e}")
            return None
    
    def post_exists(self, source_url):
        """Check if post already exists (by source URL in meta)."""
        try:
            # Search by meta field (source_url)
            response = self.session.get(
                f"{self.api_url}/posts",
                params={'per_page': 100}
            )
            response.raise_for_status()
            posts = response.json()
            
            for post in posts:
                meta = post.get('meta', {})
                if meta.get('source_url') == source_url:
                    return True
            
            return False
        except Exception as e:
            logger.error(f"Error checking if post exists: {e}")
            return False
    
    def create_post(self, title, content, category_slug, source_url, source_name, date=None):
        """Create a new post."""
        try:
            # Get category ID
            category_id = self.get_category_id(category_slug)
            if not category_id:
                logger.error(f"Cannot create post: category '{category_slug}' not found")
                return None
            
            # Prepare post data
            post_data = {
                'title': title,
                'content': content,
                'status': 'publish',
                'categories': [category_id],
                'meta': {
                    'source_url': source_url,
                    'source_name': source_name,
                },
            }
            
            # Set date if provided
            if date:
                post_data['date'] = date
            
            # Create post
            response = self.session.post(
                f"{self.api_url}/posts",
                json=post_data,
            )
            response.raise_for_status()
            post = response.json()
            
            logger.info(f"✓ Created post: {post['title']} (ID: {post['id']})")
            return post
        except requests.exceptions.RequestException as e:
            logger.error(f"Error creating post: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return None
    
    def update_post(self, post_id, **kwargs):
        """Update an existing post."""
        try:
            response = self.session.post(
                f"{self.api_url}/posts/{post_id}",
                json=kwargs,
            )
            response.raise_for_status()
            post = response.json()
            logger.info(f"✓ Updated post: {post['title']} (ID: {post['id']})")
            return post
        except Exception as e:
            logger.error(f"Error updating post: {e}")
            return None

def load_scraped_items(filepath):
    """Load scraped items from JSON file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            items = json.load(f)
        logger.info(f"Loaded {len(items)} items from {filepath}")
        return items
    except FileNotFoundError:
        logger.error(f"Scraped items file not found: {filepath}")
        return []
    except Exception as e:
        logger.error(f"Error loading scraped items: {e}")
        return []

def post_items_to_wordpress(client, items):
    """Post scraped items to WordPress."""
    posted_count = 0
    skipped_count = 0
    
    for item in items:
        try:
            source_url = item.get('url')
            
            # Check if post already exists
            if client.post_exists(source_url):
                logger.info(f"⊘ Post already exists: {item.get('title')}")
                skipped_count += 1
                continue
            
            # Prepare content
            title = item.get('title', 'Untitled')
            description = item.get('description', '')
            
            # Build HTML content
            content = f"""
<p>{description}</p>
<p><strong>出典:</strong> <a href="{source_url}">{item.get('source_name', 'Unknown')}</a></p>
"""
            
            category = item.get('category', 'kirishima-news')
            source_name = item.get('source_name', 'Unknown')
            date = item.get('date')
            
            # Create post
            post = client.create_post(
                title=title,
                content=content,
                category_slug=category,
                source_url=source_url,
                source_name=source_name,
                date=date,
            )
            
            if post:
                posted_count += 1
        
        except Exception as e:
            logger.error(f"Error posting item: {e}")
            skipped_count += 1
    
    logger.info(f"Posted: {posted_count}, Skipped: {skipped_count}")
    return posted_count, skipped_count

def main():
    """Main function."""
    logger.info("Starting WordPress Poster")
    
    # Initialize client
    client = WordPressClient(WP_URL, WP_USER, WP_APP_PASS)
    
    # Test connection
    if not client.test_connection():
        logger.error("Failed to connect to WordPress")
        sys.exit(1)
    
    # Load scraped items
    script_dir = os.path.dirname(os.path.abspath(__file__))
    items_file = os.path.join(script_dir, 'scraped_items.json')
    items = load_scraped_items(items_file)
    
    if not items:
        logger.warning("No items to post")
        sys.exit(0)
    
    # Post items to WordPress
    posted_count, skipped_count = post_items_to_wordpress(client, items)
    
    logger.info(f"Completed: {posted_count} posted, {skipped_count} skipped")
    sys.exit(0)

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
