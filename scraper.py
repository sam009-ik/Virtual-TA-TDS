# src/scraper.py

import os
import time
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup

# === CONFIG ===
TDS_URL       = "https://tds.s-anand.net/#/2025-01/"
DISCOURSE_URL = "https://discourse.onlinedegree.iitm.ac.in/c/courses/tds-kb/34"

OUTPUT_DIR    = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
TDS_OUTFILE   = os.path.join(OUTPUT_DIR, "tds_site.json")
DISC_OUTFILE  = os.path.join(OUTPUT_DIR, "discourse.json")

# === SETUP ===
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Initialize Selenium Chrome driver
driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()))

def scrape_tds_site():
    driver.get(TDS_URL)
    time.sleep(3)  # let JS load

    # find all hash-route links
    links = driver.find_elements(By.CSS_SELECTOR, "a[href^='#/']")
    urls = []
    for a in links:
        href = a.get_attribute("href")
        if href not in urls:
            urls.append(href)

    data = []
    for url in urls:
        driver.get(url)
        time.sleep(2)
        # grab page title & full text
        title   = driver.title
        content = driver.find_element(By.TAG_NAME, "body").text
        data.append({
            "url":     url,
            "title":   title,
            "content": content
        })

    with open(TDS_OUTFILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[+] Saved TDS site data to {TDS_OUTFILE}")

def scrape_discourse():
    driver.get(DISCOURSE_URL)
    print("→ When the browser pops up, please log in via Google SSO, then return here and press ENTER")
    input()
    time.sleep(2)

    # parse page source to collect topic links
    soup = BeautifulSoup(driver.page_source, "lxml")
    topic_links = []
    for a in soup.select("a[href*='/t/']"):
        href = a["href"]
        if href.startswith("/t/") and href not in topic_links:
            topic_links.append("https://discourse.onlinedegree.iitm.ac.in" + href)

    topics = []
    for link in topic_links:
        driver.get(link)
        time.sleep(2)
        page = BeautifulSoup(driver.page_source, "lxml")

        # title
        title_el = page.select_one("h1.title") or page.find("h1")
        if title_el:
            title = title_el.get_text(strip=True)
        else:
            title = "NO TITLE FOUND"

        # all posts
        posts = []
        for post_div in page.select("div.cooked"):
            text = post_div.get_text("\n", strip=True)
            posts.append(text)

        topics.append({
            "url":   link,
            "title": title,
            "posts": posts
        })

    with open(DISC_OUTFILE, "w", encoding="utf-8") as f:
        json.dump(topics, f, ensure_ascii=False, indent=2)
    print(f"[+] Saved Discourse data to {DISC_OUTFILE}")

if __name__ == "__main__":
    scrape_tds_site()
    scrape_discourse()
    driver.quit()
