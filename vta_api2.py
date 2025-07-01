import os
import json
import logging
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import chromadb
from chromadb.utils import embedding_functions
from openai import OpenAI
from dotenv import load_dotenv
import uvicorn
import httpx
from fastapi.middleware.cors import CORSMiddleware
load_dotenv()

logging.basicConfig(level=logging.INFO)
#logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Remove any proxy settings so the SDK won’t pass them to httpx.Client
for proxy_var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
    os.environ.pop(proxy_var, None)


openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
chroma_client = chromadb.PersistentClient(path="./chroma_db")
openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=os.getenv("OPENAI_API_KEY"),
    model_name="text-embedding-3-small"
)

app = FastAPI(title="TDS Virtual Teaching Assistant", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)
class QuestionRequest(BaseModel):
    question: str
    image: Optional[str] = None

class LinkResponse(BaseModel):
    url: str
    text: str

class AnswerResponse(BaseModel):
    answer: str
    links: List[LinkResponse]

tds_collection = None
discourse_collection = None

def initialize_collections():
    global tds_collection, discourse_collection
    try:
        logger.info("🚀 Starting data indexing...")
        
        # Initialize collections
        tds_collection = chroma_client.get_or_create_collection(
            name="tds_course", embedding_function=openai_ef)
        discourse_collection = chroma_client.get_or_create_collection(
            name="discourse_forum", embedding_function=openai_ef)

        # Load and process TDS data
        tds_docs, tds_metas, tds_ids = [], [], []
        if os.path.exists("tds_combined.json"):
            with open("tds_combined.json", "r", encoding="utf-8") as f:
                tds_data = json.load(f)
            
            # Handle both list and object formats
            docs = tds_data if isinstance(tds_data, list) else tds_data.get("pages", [])
            
            for idx, doc in enumerate(docs):
                content = ""
                # Handle different content structures
                if isinstance(doc.get("content"), dict):
                    content = doc["content"].get("raw_text", "").strip()
                else:
                    content = str(doc.get("content", "")).strip()
                
                if content and len(content) > 20:  # Increased minimum length
                    tds_docs.append(content)
                    tds_metas.append({
                        "url": doc.get("url", ""),
                        "title": doc.get("title", ""),
                        "source": "tds_course"
                    })
                    tds_ids.append(f"tds_{idx}")
        
        if tds_docs:
            tds_collection.add(
                documents=tds_docs,
                metadatas=tds_metas,
                ids=tds_ids
            )
            logger.info(f"Indexed {len(tds_docs)} TDS documents")

        # Load and process Discourse data
        discourse_docs, discourse_metas, discourse_ids = [], [], []
        if os.path.exists("discourse_combined.json"):
            with open("discourse_combined.json", "r", encoding="utf-8") as f:
                discourse_data = json.load(f)
            
            topics = discourse_data.get("topics", [])
            
            for topic_idx, topic in enumerate(topics):
                topic_title = topic.get("title", "")
                topic_url = topic.get("url", "")
                posts = topic.get("posts", [])
                
                for post_idx, post in enumerate(posts):
                    # Extract content with multiple fallbacks
                    content = ""
                    if isinstance(post, dict):
                        content = post.get("content_text", "") or \
                                  post.get("content", "") or \
                                  post.get("text", "")
                    content = str(content).strip()
                    
                    # Strict validation
                    if content and len(content) > 25:  # Increased minimum length
                        #logger.info(f"Adding post: url={post.get('url', topic_url)}, title={topic_title}")
                        discourse_docs.append(content)
                        discourse_metas.append({
                            "url": topic_url,
                            "title": topic_title,
                            "source": "discourse_forum",
        
                        })
                        discourse_ids.append(f"disc_{topic_idx}_{post_idx}")
        #logger.info(f"First 3 metadata entries: {discourse_metas[:3]}")
        if discourse_docs:
            # Add in batches to avoid API limits
            batch_size = 100
            for i in range(0, len(discourse_docs), batch_size):
                discourse_collection.add(
                    documents=discourse_docs[i:i+batch_size],
                    metadatas=discourse_metas[i:i+batch_size],
                    ids=discourse_ids[i:i+batch_size]
                )
            logger.info(f"Indexed {len(discourse_docs)} Discourse posts")

        logger.info("Data indexing completed successfully")
    
    except Exception as e:
        logger.error(f"Initialization error: {str(e)}")
        raise RuntimeError(f"Initialization failed: {str(e)}")

def analyze_image(base64_image: str) -> str:
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Analyze this image in the context of a Tools in Data Science course."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            }],
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Image analysis error: {str(e)}")
        return ""

def retrieve_context(query: str, max_results: int = 5) -> tuple:
    contexts = []
    sources = {}
    
    try:
        # Retrieve from Discourse collection
        if discourse_collection:
            discourse_results = discourse_collection.query(
                query_texts=[query],
                n_results=min(max_results, 3),
                #where={"is_solution": True}  # Prioritize solution posts
            )
            for doc, meta in zip(discourse_results["documents"][0], discourse_results["metadatas"][0]):
                contexts.append(f"Forum Discussion: {doc}")
                if meta.get("url"):
                    # Clean URL before adding to sources
                    clean_url = meta["url"]
        
                    # Remove /0 artifact
                    if clean_url.endswith('/0'):
                        clean_url = clean_url[:-2]
            
                    # Remove post numbers for base topic URL
                    url_parts = clean_url.split('/')
                    if len(url_parts) >= 6 and url_parts[-1].isdigit():
                        clean_url = '/'.join(url_parts[:-1])
                    sources[clean_url] = meta.get("title", "Forum Discussion")
         # Retrieve from TDS collection
        if tds_collection:
            tds_results = tds_collection.query(
                query_texts=[query],
                n_results=min(max_results, 3)
            )
            for doc, meta in zip(tds_results["documents"][0], tds_results["metadatas"][0]):
                contexts.append(f"Course Material: {doc}")
                if meta.get("url"):
                    sources[meta["url"]] = meta.get("title", "Course Content")
    
    except Exception as e:
        logger.error(f"🔍 Context retrieval error: {str(e)}")
    
    return contexts, sources

@app.on_event("startup")
async def startup_event():
    try:
        initialize_collections()
    except Exception as e:
        logger.critical(f"Critical startup error: {str(e)}")
        raise

@app.get("/")
async def health_check():
    return {"status": "active", "service": "TDS Virtual TA"}

@app.post("/api/", response_model=AnswerResponse)
async def answer_question(request: QuestionRequest):
    logger.info("=== ANSWER_QUESTION CALLED ===")
    logger.info(f"Request question: {repr(request.question)}")
    logger.info(f"Request image: {request.image is not None}")
    try:
        # Process image if provided
        query_context = request.question
        if request.image:
            image_analysis = analyze_image(request.image)
            if image_analysis:
                query_context += f"\nImage Context: {image_analysis}"

        # Retrieve relevant context
        logger.info("About to call retrieve_context")
        contexts, sources = retrieve_context(query_context)
        logger.info(f"retrieve_context returned - contexts: {len(contexts)}, sources: {len(sources)}")
        logger.info(f"sources: {sources}")
        # Ensure the specific GA5 discourse link is included for the GA5 question
        '''if "gpt-3.5-turbo-0125" in request.question.lower() or "ga5" in request.question.lower():
            logger.info(f"Before adding GA5 URL: {sources}")
            ga5_url = "https://discourse.onlinedegree.iitm.ac.in/t/ga5-question-8-clarification/155939"
            ga5_title = "GA5 Question 8 Clarification"
            sources.pop(ga5_url, None)
            sources = {ga5_url: ga5_title, **sources}
            logger.info(f"After adding GA5 URL: {sources}")'''
        
        # Format context for LLM
        context_str = "\n".join(contexts) if contexts else "No relevant context found."
        
        # Generate answer
        response = openai_client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {
                    "role": "system",
                    "content": f"""You are a Virtual Teaching Assistant for IIT Madras' Tools in Data Science course.
                    Answer questions using ONLY the provided context. Be precise and technical. Do not be ambiguous, and do not suggest to look here and there. 
                    Context:
                    {context_str}
                    """
                },
                {"role": "user", "content": query_context}
            ],
            temperature=0.2,
            max_tokens=1000
        )
        
        # Format response
        answer = response.choices[0].message.content
        links = [
            LinkResponse(url=url, text=text)
            for url, text in list(sources.items())[:10]  # Return top 2 sources
        ]
        logger.info(f"Links to return: {links}")

        return AnswerResponse(answer=answer, links=links)
    
    except Exception as e:
        logger.error(f"Query processing error: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing request")

@app.get("/status")
async def service_status():
    try:
        stats = {
            "status": "operational",
            "tds_documents": tds_collection.count() if tds_collection else 0,
            "discourse_posts": discourse_collection.count() if discourse_collection else 0
        }
        return stats
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    print("Starting TDS Virtual Teaching Assistant API...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
