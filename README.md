# Virtual TA for Tools in Data Science

An automated “virtual teaching assistant” API for IIT Madras’ **Tools in Data Science** course.  
It ingests course materials and forum discussions, then answers student questions on demand—so TAs can focus on the tough bits.

---

## 🔍 Overview

When a student asks a question, this API:
1. **Searches** across:
   - Lecture notes and slides from the Jan 2025 TDS module  
   - Discourse forum posts (Jan 1 – Apr 14, 2025)  
   - Any uploaded attachments (images/PDFs)  
2. **Retrieves** the most relevant snippets using a vector-search backend  
3. **Returns** a concise answer (with citations) via JSON  

---

## ⚙️ Features

- **Natural-language queries** over course docs & forum posts  
- **Optional file upload**: images or PDFs, encoded in Base64  
- **FastAPI**-powered REST endpoint  
- **Pluggable vector store** (e.g., Typesense / Elasticsearch)  
- **Extensible**: add new content sources by dropping files into `data/`

---

## 🚀 Getting Started

1. **Clone** this repo and install dependencies:
   ```bash
   git clone https://github.com/sam009-ik/Virtual-TA-TDS.git
   cd Virtual-TA-TDS
   pip install -r requirements.txt
