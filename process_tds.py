import json
from typing import List, Dict

# Load both datasets
tds_gpt = json.load(open("data/raw/tds_data_gpt.json", encoding="utf-8"))
tds_comp = json.load(open("data/raw/tds_comprehensive_data.json", encoding="utf-8"))

# 1. Use comprehensive data as your main source (keep all fields)
main_data = tds_comp

# 2. Optionally, add GPT-style data as extra "pages" (if not already present)
# This is a simple merge; for a robust solution, you might want to deduplicate by URL
for page in tds_gpt:
    # Check if this URL already exists in the comprehensive data
    url_exists = any(p["url"] == page["url"] for p in tds_comp.get("pages", []))
    if not url_exists:
        # Add as a new page with minimal structure
        new_page = {
            "url": page["url"],
            "title": page["title"],
            "content": {
                "raw_text": page["content"],
                "headings": [],  # No headings in GPT data
                "links": [],     # No links in GPT data
                # ... other fields can be empty
            }
        }
        if "pages" not in main_data:
            main_data["pages"] = []
        main_data["pages"].append(new_page)

# Save the combined data
with open("tds_combined.json", "w", encoding="utf-8") as f:
    json.dump(main_data, f, ensure_ascii=False, indent=2)
