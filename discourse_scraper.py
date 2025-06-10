import os
import time
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

DISCOURSE_URL = "https://discourse.onlinedegree.iitm.ac.in/c/courses/tds-kb/34"
OUTPUT_DIR = os.path.join(os.getcwd(), "data", "raw")
OUTFILE = os.path.join(OUTPUT_DIR, "discourse_data2.json")

def setup_driver():
    """Setup Chrome driver with correct path handling"""
    chrome_options = Options()
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    
    # Fix for WinError 193: Explicitly set path to chromedriver.exe
    driver_path = ChromeDriverManager().install()
    folder = os.path.dirname(driver_path)
    chromedriver_path = os.path.join(folder, "chromedriver.exe")
    service = ChromeService(chromedriver_path)
    
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def handle_login(driver):
    """Handle manual login process"""
    print("Navigating to:", DISCOURSE_URL)
    driver.get(DISCOURSE_URL)
    print("→ Please log in via Google SSO in the browser window, then press ENTER here")
    input()
    
    # Wait for actual forum content to load after SSO
    print("Waiting for forum content to load...")
    try:
        WebDriverWait(driver, 30).until(
            EC.any_of(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.topic-list-container")),
                EC.presence_of_element_located((By.CSS_SELECTOR, ".topic-list")),
                EC.presence_of_element_located((By.CSS_SELECTOR, "table.topic-list"))
            )
        )
        print("✅ Forum content loaded successfully")
    except Exception as e:
        print(f"⚠️ Warning: Could not detect forum content loading: {e}")
        time.sleep(5)  # Give it some extra time

def extract_topic_links(driver):
    """Extract all topic links from the forum page"""
    print("Scrolling to load all topics...")
    
    # Scroll to load all topics (with safer scrolling)
    last_height = driver.execute_script("return document.body.scrollHeight")
    scroll_attempts = 0
    max_scrolls = 10
    
    while scroll_attempts < max_scrolls:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height
        scroll_attempts += 1

    # Try multiple selectors to find topic links
    soup = BeautifulSoup(driver.page_source, "html.parser")
    topic_links = []
    
    # Multiple selector strategies for topic links
    selectors = [
        "tr.topic-list-item a.title",
        "a.title.raw-link.raw-topic-link", 
        ".topic-list-item a[href*='/t/']",
        "a[href*='/t/'].title",
        ".topic-list .main-link a.title"
    ]
    
    for selector in selectors:
        links = soup.select(selector)
        if links:
            print(f"Found {len(links)} topics using selector: {selector}")
            for a in links:
                href = a.get("href")
                if href and href.startswith("/t/"):
                    full_url = "https://discourse.onlinedegree.iitm.ac.in" + href
                    if full_url not in topic_links:
                        topic_links.append(full_url)
            break
    
    if not topic_links:
        # Save page source for debugging
        with open("debug_page_source.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print("⚠️ No topic links found. Debug page saved as 'debug_page_source.html'")
    
    return topic_links

def scrape_topic_page(driver, url):
    """Scrape individual topic page for posts, content, and images"""
    try:
        driver.get(url)
        WebDriverWait(driver, 15).until(
            EC.any_of(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.topic-post")),
                EC.presence_of_element_located((By.CSS_SELECTOR, ".post-stream"))
            )
        )
        last_height = driver.execute_script("return document.body.scrollHeight")
        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
        soup = BeautifulSoup(driver.page_source, "html.parser")
        title_selectors = ["h1.fancy-title", "h1.title", ".title h1", "h1"]
        title = "NO TITLE FOUND"
        for selector in title_selectors:
            title_el = soup.select_one(selector)
            if title_el:
                title = title_el.get_text(strip=True)
                break
        posts = []
        post_elements = soup.select("div.topic-post")
        for post in post_elements:
            author_selectors = ["span.username", ".creator .username", ".names .username", ".username a"]
            author = "Unknown"
            for selector in author_selectors:
                author_el = post.select_one(selector)
                if author_el:
                    author = author_el.get_text(strip=True)
                    break
            content_el = post.select_one("div.cooked")
            content_text = content_el.get_text("\n", strip=True) if content_el else ""
            content_html = str(content_el) if content_el else ""
            # Extract images
            images = []
            for img in post.select("div.cooked img"):
                src = img.get("src", "")
                alt = img.get("alt", "")
                images.append({"src": src, "alt": alt})
            post_number = post.get("data-post-number", "0")
            is_solution = bool(post.select_one(".accepted-answer, .solved, .solution"))
            code_blocks = []
            for code in post.select("pre code"):
                code_blocks.append(code.get_text("\n", strip=True))
            likes = 0
            like_el = post.select_one(".like-count")
            if like_el and like_el.get_text(strip=True).isdigit():
                likes = int(like_el.get_text(strip=True))
            posts.append({
                "post_number": post_number,
                "author": author,
                "content_text": content_text,
                "content_html": content_html,
                "is_solution": is_solution,
                "likes": likes,
                "code_blocks": code_blocks,
                "has_code": len(code_blocks) > 0,
                "images": images
            })
        return {
            "url": url,
            "title": title,
            "posts": posts,
            "total_posts": len(posts)
        }
    except Exception as e:
        print(f"⚠️ Error scraping topic {url}: {e}")
        return {
            "url": url,
            "title": "ERROR_SCRAPING",
            "posts": [],
            "error": str(e)
        }


def main():
    """Main scraping function"""
    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print("🚀 Starting Discourse forum scraping for Virtual Teaching Assistant...")
    
    driver = setup_driver()
    
    try:
        # Handle login
        handle_login(driver)
        
        # Save post-login page for debugging
        with open("post_login_page.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print("📝 Post-login page saved for debugging")
        
        # Extract topic links
        topic_links = extract_topic_links(driver)
        print(f"📋 Found {len(topic_links)} topics to scrape")
        
        if not topic_links:
            print("❌ No topics found. Check your login status and try again.")
            return
        
        # Scrape all topics
        all_data = []
        total_posts = 0
        
        for idx, link in enumerate(topic_links, 1):
            print(f"📖 Scraping topic {idx}/{len(topic_links)}: {link}")
            topic_data = scrape_topic_page(driver, link)
            all_data.append(topic_data)
            total_posts += topic_data.get("total_posts", 0)
            time.sleep(1)  # Be respectful to the server
        
        # Save data
        output_data = {
            "scraping_date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "forum_url": DISCOURSE_URL,
            "topics_found": len(topic_links),
            "total_posts": total_posts,
            "topics": all_data
        }
        
        with open(OUTFILE, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Scraping completed successfully!")
        print(f"📊 Topics scraped: {len(topic_links)}")
        print(f"📝 Total posts: {total_posts}")
        print(f"💾 Data saved to: {OUTFILE}")
        
    except Exception as e:
        print(f"❌ Error during scraping: {e}")
    
    finally:
        driver.quit()
        print("🔚 Browser closed")

if __name__ == "__main__":
    main()