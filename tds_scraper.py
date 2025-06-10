import os
import time
import json
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup

class TDSWebScraper:
    """
    Enhanced TDS course website scraper for Virtual Teaching Assistant
    Designed to extract comprehensive course content, assignments, and structure
    """

    def __init__(self, headless=True, timeout=10):
        """
        Initialize the scraper with improved configuration

        Args:
            headless (bool): Run browser in headless mode (no GUI)
            timeout (int): Maximum wait time for elements to load
        """
        self.headless = headless
        self.timeout = timeout
        self.wait = None
        self.driver = None

        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('tds_scraper.log', 'w'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

        # Data structure for extracted content
        self.scraped_data = {
            'scrape_timestamp': datetime.now().isoformat(),
            'course_info': {},
            'modules': [],
            'assignments': [],
            'instructors': [],
            'navigation_structure': [],
            'all_pages': []
        }

        # Base URL and output configuration
        self.base_url = "https://tds.s-anand.net/#/2025-01/"
        self.output_dir = os.path.join(os.path.dirname(__file__), "data", "raw")
        os.makedirs(self.output_dir, exist_ok=True)

    def setup_driver(self):
        """Setup Chrome driver with optimal configurations for scraping"""
        try:
            chrome_options = ChromeOptions()

            if self.headless:
                chrome_options.add_argument('--headless')

            # Performance and stability options
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-logging')
            chrome_options.add_argument('--disable-web-security')
            chrome_options.add_argument('--allow-running-insecure-content')

            # Initialize driver
            driver_path = ChromeDriverManager().install()
            folder = os.path.dirname(driver_path)
            chromedriver_path = os.path.join(folder, "chromedriver.exe")
            service = ChromeService(chromedriver_path)
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.wait = WebDriverWait(self.driver, self.timeout)

            self.logger.info("Chrome driver setup completed successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to setup Chrome driver: {e}")
            return False

    def wait_for_page_load(self, timeout=None):
        """Wait for page to fully load including JavaScript content"""
        if timeout is None:
            timeout = self.timeout

        try:
            # Wait for basic page load
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

            # Wait for any loading indicators to disappear
            try:
                self.wait.until_not(EC.presence_of_element_located((By.CLASS_NAME, "loading")))
            except TimeoutException:
                pass  # No loading indicator found, continue

            # Additional wait for dynamic content
            time.sleep(2)
            return True

        except TimeoutException:
            self.logger.warning(f"Page load timeout after {timeout} seconds")
            return False

    def extract_page_content(self, url):
        """Extract comprehensive content from a single page"""
        try:
            self.driver.get(url)
            if not self.wait_for_page_load():
                return None

            # Get page source and parse with BeautifulSoup
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')

            # Extract comprehensive page data
            page_data = {
                'url': url,
                'title': self.driver.title,
                'scraped_at': datetime.now().isoformat(),
                'content': {
                    'raw_text': self.driver.find_element(By.TAG_NAME, "body").text,
                    'headings': self.extract_headings(soup),
                    'links': self.extract_links(soup),
                    'videos': self.extract_videos(soup),
                    'tables': self.extract_tables(soup),
                    'assignments': self.extract_assignments(soup),
                    'deadlines': self.extract_deadlines(soup),
                    'contact_info': self.extract_contact_info(soup)
                },
                'meta_data': {
                    'page_length': len(page_source),
                    'word_count': len(self.driver.find_element(By.TAG_NAME, "body").text.split()),
                    'has_navigation': bool(soup.find_all(['nav', '[role="navigation"]'])),
                    'has_forms': bool(soup.find_all('form')),
                    'external_links_count': len([link for link in soup.find_all('a', href=True) 
                                                if 'http' in link['href'] and 'tds.s-anand.net' not in link['href']])
                }
            }

            return page_data

        except Exception as e:
            self.logger.error(f"Error extracting content from {url}: {e}")
            return None

    def extract_headings(self, soup):
        """Extract all headings and their hierarchy"""
        headings = []
        for level in range(1, 7):  # h1 through h6
            for heading in soup.find_all(f'h{level}'):
                headings.append({
                    'level': level,
                    'text': heading.get_text(strip=True),
                    'id': heading.get('id', ''),
                    'classes': heading.get('class', [])
                })
        return headings

    def extract_links(self, soup):
        """Extract all links with context"""
        links = []
        for link in soup.find_all('a', href=True):
            links.append({
                'url': link['href'],
                'text': link.get_text(strip=True),
                'title': link.get('title', ''),
                'is_external': 'http' in link['href'] and 'tds.s-anand.net' not in link['href'],
                'is_hash_route': link['href'].startswith('#/'),
                'classes': link.get('class', [])
            })
        return links

    def extract_videos(self, soup):
        """Extract video links and embeds"""
        videos = []

        # YouTube embeds
        for iframe in soup.find_all('iframe'):
            src = iframe.get('src', '')
            if 'youtube.com' in src or 'youtu.be' in src:
                videos.append({
                    'type': 'youtube_embed',
                    'url': src,
                    'title': iframe.get('title', ''),
                    'width': iframe.get('width', ''),
                    'height': iframe.get('height', '')
                })

        # Direct video links
        for link in soup.find_all('a', href=True):
            href = link['href']
            if any(ext in href.lower() for ext in ['.mp4', '.webm', '.avi', 'youtube.com', 'youtu.be']):
                videos.append({
                    'type': 'video_link',
                    'url': href,
                    'text': link.get_text(strip=True)
                })

        return videos

    def extract_tables(self, soup):
        """Extract table data"""
        tables = []
        for table in soup.find_all('table'):
            table_data = {
                'headers': [],
                'rows': [],
                'caption': table.find('caption').get_text(strip=True) if table.find('caption') else ''
            }

            # Extract headers
            header_row = table.find('tr')
            if header_row:
                table_data['headers'] = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]

            # Extract all rows
            for row in table.find_all('tr')[1:]:  # Skip header row
                row_data = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
                if row_data:
                    table_data['rows'].append(row_data)

            tables.append(table_data)

        return tables

    def extract_assignments(self, soup):
        """Extract assignment and evaluation information"""
        assignments = []
        text = soup.get_text().lower()

        # Look for assignment keywords
        assignment_keywords = ['graded assignment', 'project', 'ga:', 'p1:', 'p2:', 'roe:', 'final']

        for paragraph in soup.find_all(['p', 'div', 'li']):
            para_text = paragraph.get_text()
            if any(keyword in para_text.lower() for keyword in assignment_keywords):
                assignments.append({
                    'text': para_text.strip(),
                    'type': self.classify_assignment_type(para_text),
                    'contains_date': bool(self.extract_dates_from_text(para_text))
                })

        return assignments

    def extract_deadlines(self, soup):
        """Extract deadline and date information"""
        deadlines = []

        # Look for date patterns
        import re
        date_patterns = [
            r'\d{1,2}\s+\w+\s+\d{4}',  # "15 Jan 2025"
            r'\d{1,2}/\d{1,2}/\d{4}',     # "15/01/2025"
            r'\d{4}-\d{2}-\d{2}'          # "2025-01-15"
        ]

        for element in soup.find_all(['p', 'div', 'td', 'li']):
            text = element.get_text()
            for pattern in date_patterns:
                matches = re.findall(pattern, text)
                if matches:
                    deadlines.append({
                        'date_found': matches,
                        'context': text.strip(),
                        'element_type': element.name
                    })

        return deadlines

    def extract_contact_info(self, soup):
        """Extract instructor and contact information"""
        contacts = []

        # Look for email patterns
        import re
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

        for element in soup.find_all(['p', 'div', 'li']):
            text = element.get_text()
            emails = re.findall(email_pattern, text)
            if emails:
                contacts.append({
                    'emails': emails,
                    'context': text.strip(),
                    'element_type': element.name
                })

        return contacts

    def classify_assignment_type(self, text):
        """Classify the type of assignment"""
        text_lower = text.lower()
        if 'graded assignment' in text_lower or 'ga' in text_lower:
            return 'graded_assignment'
        elif 'project' in text_lower:
            return 'project'
        elif 'exam' in text_lower or 'roe' in text_lower:
            return 'exam'
        elif 'final' in text_lower:
            return 'final_exam'
        else:
            return 'other'

    def extract_dates_from_text(self, text):
        """Extract dates from text"""
        import re
        date_patterns = [
            r'\d{1,2}\s+\w+\s+\d{4}',
            r'\d{1,2}/\d{1,2}/\d{4}',
            r'\d{4}-\d{2}-\d{2}'
        ]

        dates = []
        for pattern in date_patterns:
            dates.extend(re.findall(pattern, text))
        return dates

    def discover_all_pages(self):
        """Discover all pages in the course website"""
        try:
            self.logger.info("Starting page discovery...")
            self.driver.get(self.base_url)
            self.wait_for_page_load()

            # Find all hash-route links
            discovered_links = set()

            # Get all links with href starting with #/
            hash_links = self.driver.find_elements(By.CSS_SELECTOR, "a[href^='#/']")

            for link in hash_links:
                href = link.get_attribute("href")
                if href and href not in discovered_links:
                    discovered_links.add(href)

            # Also look for any links in the page source
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            for link in soup.find_all('a', href=True):
                href = link['href']
                if href.startswith('#/'):
                    full_url = self.base_url.split('#/')[0] + href
                    discovered_links.add(full_url)

            self.logger.info(f"Discovered {len(discovered_links)} unique pages")
            return list(discovered_links)

        except Exception as e:
            self.logger.error(f"Error during page discovery: {e}")
            return []

    def scrape_all_content(self):
        """Main method to scrape all course content"""
        try:
            if not self.setup_driver():
                return False

            # Discover all pages
            all_urls = self.discover_all_pages()

            if not all_urls:
                self.logger.error("No pages discovered")
                return False

            self.logger.info(f"Starting scraping of {len(all_urls)} pages...")

            # Scrape each page
            for i, url in enumerate(all_urls, 1):
                self.logger.info(f"Scraping page {i}/{len(all_urls)}: {url}")

                page_data = self.extract_page_content(url)
                if page_data:
                    self.scraped_data['all_pages'].append(page_data)

                    # Categorize data
                    self.categorize_page_data(page_data)

                # Small delay to be respectful to the server
                time.sleep(1)

            # Save the data
            self.save_data()

            self.logger.info("Scraping completed successfully!")
            return True

        except Exception as e:
            self.logger.error(f"Error during scraping: {e}")
            return False
        finally:
            if self.driver:
                self.driver.quit()

    def categorize_page_data(self, page_data):
        """Categorize scraped data into structured sections"""
        url = page_data['url']
        content = page_data['content']

        # Extract course overview info
        if 'tools-in-data-science' in url.lower() or url.endswith('2025-01/'):
            self.scraped_data['course_info'].update({
                'overview': content['raw_text'][:1000],  # First 1000 chars
                'instructors': content['contact_info'],
                'schedule': content['deadlines']
            })

        # Extract module information
        if any(module in url.lower() for module in ['development', 'deployment', 'data-sourcing', 'data-preparation']):
            module_info = {
                'name': page_data['title'],
                'url': url,
                'content': content['raw_text'],
                'sub_topics': [link['text'] for link in content['links'] if link['is_hash_route']],
                'videos': content['videos']
            }
            self.scraped_data['modules'].append(module_info)

        # Extract assignments
        if content['assignments']:
            self.scraped_data['assignments'].extend(content['assignments'])

    def save_data(self):
        """Save scraped data to JSON file"""
        try:
            output_file = os.path.join(self.output_dir, "tds_comprehensive_data.json")

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(self.scraped_data, f, ensure_ascii=False, indent=2)

            self.logger.info(f"Data saved to {output_file}")

            # Also save a summary
            summary = {
                'scrape_summary': {
                    'total_pages': len(self.scraped_data['all_pages']),
                    'total_modules': len(self.scraped_data['modules']),
                    'total_assignments': len(self.scraped_data['assignments']),
                    'scrape_timestamp': self.scraped_data['scrape_timestamp']
                }
            }

            summary_file = os.path.join(self.output_dir, "tds_scrape_summary.json")
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)

            self.logger.info(f"Summary saved to {summary_file}")

        except Exception as e:
            self.logger.error(f"Error saving data: {e}")

# Main execution function
def main():
    """Main function to run the TDS scraper"""
    scraper = TDSWebScraper(headless=True, timeout=15)
    success = scraper.scrape_all_content()

    if success:
        print("\n✅ TDS course content scraped successfully!")
        print(f"📁 Data saved to: {scraper.output_dir}")
        print("📊 Check the following files:")
        print("   - tds_comprehensive_data.json (full data)")
        print("   - tds_scrape_summary.json (summary)")
        print("   - tds_scraper.log (scraping log)")
    else:
        print("❌ Scraping failed. Check the log file for details.")

if __name__ == "__main__":
    main()