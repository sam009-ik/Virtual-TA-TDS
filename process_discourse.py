import json

def combine_discourse_data():
    # Load both datasets
    with open("data/raw/discourse_data_gpt.json", 'r', encoding='utf-8') as f:
        gpt_data = json.load(f)
    
    with open("data/raw/discourse_comprehensive.json", 'r', encoding='utf-8') as f:
        comp_data = json.load(f)

    # Create URL-based index of comprehensive data
    comp_index = {topic["url"]: topic for topic in comp_data["topics"]}

    # Merge GPT data where URLs don't exist in comprehensive
    for gpt_topic in gpt_data:
        if gpt_topic["url"] not in comp_index:
            comp_data["topics"].append({
                "url": gpt_topic["url"],
                "title": gpt_topic["title"],
                "posts": [{"content_text": post} for post in gpt_topic["posts"]],
                "source": "gpt_scraper"
            })

    # Save combined data
    with open("discourse_combined.json", "w") as f:
        json.dump(comp_data, f, indent=2)

if __name__ == "__main__":
    combine_discourse_data()
# This script combines the GPT-scraped Discourse data with the comprehensive data
# by checking URLs. If a URL from the GPT data doesn't exist in the comprehensive data, 