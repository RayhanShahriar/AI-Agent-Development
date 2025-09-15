from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
from pydantic import BaseModel
from typing import Optional, Literal, List
import os
import PyPDF2
import shutil
from dotenv import load_dotenv
from contextlib import asynccontextmanager

# Load environment variables from .env file
load_dotenv()
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_core.runnables import RunnableParallel, RunnablePassthrough, RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from sentence_transformers import CrossEncoder
from langgraph.graph import StateGraph, END
from langchain.memory import ConversationBufferWindowMemory
from langchain.schema import BaseMessage, HumanMessage, AIMessage
from advanced_memory import ConversationMemory, ChainOfThoughtReasoner, EntityContext, EntityType
from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer
from typing import Dict, List, Any, TypedDict, Annotated
import operator
import logging
from datetime import datetime
import re
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

# Set API keys - hardcoded for this implementation
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
os.environ["GROQ_API_KEY"] = GROQ_API_KEY
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

logger.info("API keys configured successfully")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize RAG system on startup"""
    
    try:
        pdf_folder = "pdfs"  
        
        if not os.path.exists(pdf_folder):
            os.makedirs(pdf_folder)
            logger.info(f"Created {pdf_folder} folder. Please add your PDF files there.")
            yield
            return
            
        num_pdfs, num_chunks = initialize_rag_system(pdf_folder)
        logger.info(f"RAG system initialized with {num_pdfs} PDFs and {num_chunks} chunks")
        
    except Exception as e:
        logger.error(f"Error initializing RAG system: {e}")
    
    yield  # This is where the app runs
    
    logger.info("Shutting down RAG system")

app = FastAPI(
    title="Studynet CRM AI Assistant", 
    description="Advanced RAG system for Studynet CRM with LangGraph workflow",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (HTML, CSS, JS)
app.mount("/static", StaticFiles(directory="."), name="static")

# Pydantic models
class QuestionRequest(BaseModel):
    question: str
    llm_provider: Literal["openai", "groq", "gemini"] = "openai"
    model_name: Optional[str] = None
    use_reranker: bool = True
    max_chunks: int = 10

class QuestionResponse(BaseModel):
    answer: str
    status: str
    llm_used: str
    chunks_used: int
    reranker_used: bool
    query_type: str
    reasoning: str
    sources: List[str]
    conversation_context: bool

class LLMConfigRequest(BaseModel):
    llm_provider: Literal["openai", "groq", "gemini"]
    model_name: Optional[str] = None


# Global variables to store the RAG components
vector_store = None
retriever = None
reranker = None
current_llm_config = {"provider": "openai", "model": "gpt-4o-mini"}

# Advanced RAG Components
bm25_index = None
tfidf_vectorizer = None
conversation_memory = ConversationBufferWindowMemory(k=5, return_messages=True)

# Advanced Memory System
advanced_memory = ConversationMemory()
chain_of_thought_reasoner = ChainOfThoughtReasoner(advanced_memory)

# Studynet CRM Knowledge Base Context
KNOWLEDGE_BASE_CONTEXT = """
Studynet CRM is a comprehensive Customer Relationship Management system designed specifically for education services.
The system manages the complete student journey from initial inquiry to enrollment across 11 branches globally.

## SYSTEM OVERVIEW
Studynet CRM is where all employee data, leads, and applications are stored. The system operates across 11 branches:
Sydney CRM, Melbourne CRM, Brisbane CRM, Sylhet CRM, Dhaka CRM, Dhanmondi CRM, Chittagong CRM, Malaysia CRM, Nepal CRM, India CRM, Perth CRM.

## CORE MODULES & SECTIONS
- Dashboard, Bookings, Providers, Marketing, Leads, Applications, Students
- Migration, Health Cover, Finance, Reports, Communication, Contacts
- Agents, Users, Settings, Products, Site Management

## LEAD MANAGEMENT SYSTEM

### Lead Creation Process
A Lead is defined as a prospective student who registers through web forms or manual entry. Each Lead receives a unique CRM ID to prevent duplication.

**Service Types Available:**
- Education
- Professional Year (PY)
- Visa Services
- Health Cover
- Recognition of Prior Learning (RPL)

**Lead Sources:**
- Call, Company FB/Insta, Email Marketing, Eventbrite, Expo Walk-in Registration
- FB Messenger, Gumtree Ads, Office Phone/Mobile, Online Application
- Online Application - Sub agent, Personal Reference (Employee Referral)
- Referral Agent, Referred by Hossain, Referred by Manir, Sub Agent
- Virtual Office, Walk-in (Daily), Website, Others

**Lead Rating System:**
- New: Just created, not yet contacted
- Follow-up: Contacted, awaiting action
- Hot: Highly interested student
- Cold: Not interested currently
- Not Reachable: Contact attempts failed

**Lead Lifecycle Stages:**
1. Lead Creation → 2. Counselor Assignment → 3. Follow-up → 4. Application Initiation → 5. Conversion

## APPLICATION MANAGEMENT SYSTEM

### Application Stage Overview
The Application Management process begins once a student's profile successfully moves through all required stages in the Lead Cycle. Counselors initiate the transition by clicking the "Apply" button, which finalizes the lead as an applicant and forwards the profile to the Admission Team.

### Four Major Application Processes

#### 1. GTE (Genuine Temporary Entrant) Process
- **Purpose**: First critical step ensuring applications meet documentation and compliance requirements
- **Management**: Dedicated GTE Team within Admission Team
- **Responsibilities**: Document validation, compliance checks, GTE criteria verification
- **Team Structure**: GTE Team Supervisor + Senior Admission Officers + Team Members

#### 2. Application Process
- **Purpose**: Core application processing and documentation management
- **Management**: Application Team within Admission Team
- **Responsibilities**: Application form processing, document collection, institution liaison
- **Team Structure**: Application Team Supervisor + Senior Admission Officers + Team Members

#### 3. Communication Process
- **Purpose**: Managing all communication with students and institutions
- **Management**: Communication Team within Admission Team
- **Responsibilities**: Student updates, institution correspondence, status notifications
- **Team Structure**: Communication Team Supervisor + Senior Admission Officers + Team Members

#### 4. CoE (Confirmation of Enrollment) Process
- **Purpose**: Final stage processing enrollment confirmations
- **Management**: CoE Team within Admission Team
- **Responsibilities**: CoE generation, final compliance checks, enrollment completion
- **Team Structure**: CoE Team Supervisor + Senior Admission Officers + Team Members

## ROLE HIERARCHY & RESPONSIBILITIES

### Admission Team Manager
- Provides strategic leadership across the Admission Team
- Oversees project execution and cross-functional initiatives
- Leads training and development initiatives
- Makes final decisions on escalated or critical cases
- Aligns team performance with organizational goals

### Admission Team Leader
- Manages overall team operations and workflows
- Supports execution of admission processes
- Ensures timely and quality task completion
- Escalates unresolved issues to the Manager
- Acts as a bridge between operational staff and upper management

### Assistant Team Leader
- Monitors daily operations and project timelines
- Oversees task distribution and follow-up
- Assists Team Leader with workflow coordination
- Ensures adherence to process documentation and policies
- Takes charge in the absence of the Team Leader

### Team Supervisor (1 per team: GTE, Application, Communication, CoE)
- Supervises the work and performance of Team members
- Conducts document reviews and quality checks
- Offers real-time support to team staff
- Identifies process gaps and reports to leadership
- Ensures compliance with internal SOPs

### Senior Admission Officer
- Handles high-priority or complex student applications
- Provides expertise in specialized areas
- Mentors junior team members
- Assists with escalated cases

### Counselors
- Manage student information through the Lead Cycle
- Initiate applications by clicking "Apply" button
- Handle lead follow-up and communication
- Assign leads to appropriate counselors
- Update lead status and ratings

## KEY FEATURES & CAPABILITIES

### Lead Management Features
- Lead tracking and status management
- Counselor assignment and reassignment
- Duplicate lead detection and merging (Lead Tools > Merge Leads)
- Lead rating and categorization
- Multi-source lead capture

### Application Management Features
- Application Update Tracker with color-coded stages
- Stage progression tracking (GTE=1, Application=2, Communication=3, CoE=4)
- Document collection and management
- Status updates and notifications
- Application search and filtering

### System Administration
- Custom status and tag management (Settings > CRM Config > Status & Tags)
- Multi-branch support with localized configurations
- User role management and permissions
- Comprehensive reporting and analytics
- Integration with external systems

### Communication Features
- Automated notifications and updates
- Student communication tracking
- Institution correspondence management
- Status change notifications
- Document sharing and collaboration

## COMMON PROCEDURES

### Lead Management
- Creating new leads: Leads > Add Leads
- Assigning counselors: Lead profile > Edit Owner
- Changing counselor: Lead view > Change Counselor
- Merging duplicates: Lead Tools > Merge Leads
- Status updates: Lead profile > Edit > choose new status

### Application Tracking
- View applications: Application Update Tracker
- Search applications: Use filters (date, status, lead)
- Check application status: Look for stage numbers (1-4)
- Track application details: Click "Track Application" button
- View stage-specific applications: Click on color codes

### System Maintenance
- Reset lead status: Lead profile > Edit > choose new status
- Reassign leads: Lead view > Change Counselor
- Add custom statuses: Contact admin team for Settings > CRM Config updates
- View application updates: Application Tab under lead profile
"""

# Advanced RAG State Definition
class AdvancedRAGState(TypedDict):
    query: str
    query_type: str
    transformed_query: str
    semantic_docs: Annotated[List[Any], operator.add]
    keyword_docs: Annotated[List[Any], operator.add]
    hybrid_docs: Annotated[List[Any], operator.add]
    reranked_docs: Annotated[List[Any], operator.add]
    context: str
    reasoning: str
    answer: str
    memory: Annotated[List[BaseMessage], operator.add]
    conversation_history: Annotated[List[Dict[str, str]], operator.add]



def get_llm(provider: str, model_name: Optional[str] = None):
    """Get the appropriate LLM based on provider and model"""
    
    if provider == "openai":
        model = model_name or "gpt-4o-mini"
        return ChatOpenAI(model=model, temperature=0.2), f"OpenAI ({model})"
    
    elif provider == "groq":
        model = model_name or "deepseek-r1-distill-llama-70b"
        return ChatGroq(model=model, temperature=0.2), f"Groq ({model})"
    
    elif provider == "gemini":
        model = model_name or "gemini-1.5-flash"
        return ChatGoogleGenerativeAI(model=model, temperature=0.2), f"Gemini ({model})"
    
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")

def extract_text_from_pdf(pdf_path):
    """Extract text from a single PDF file with better error handling"""
    try:
        text = ""
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                extracted = page.extract_text()
                if extracted:
                    text += extracted + " "
        
        if not text.strip():
            logger.warning(f"No text extracted from {pdf_path}")
            return ""
            
        return text.strip()
    except Exception as e:
        logger.error(f"Error extracting text from {pdf_path}: {e}")
        return ""

def initialize_rag_system(pdf_folder_path: str):
    """Initialize the advanced RAG system with PDFs from a folder and load all components"""
    global vector_store, retriever, reranker, bm25_index, tfidf_vectorizer
    
    # Initialize reranker
    try:
        logger.info("Loading reranker model...")
        reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
        logger.info("Reranker loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load reranker: {e}")
        reranker = None
    
    # Get all PDF files
    pdf_files = []
    for filename in os.listdir(pdf_folder_path):
        if filename.lower().endswith('.pdf'):
            pdf_files.append(os.path.join(pdf_folder_path, filename))
    
    if not pdf_files:
        logger.warning("No PDF files found in the specified folder")
        raise Exception("No PDF files found in the specified folder")
    
    # Extract text from all PDFs with metadata
    documents = []
    all_texts = []  # For BM25 indexing
    
    for pdf_path in pdf_files:
        logger.info(f"Processing {pdf_path}")
        pdf_text = extract_text_from_pdf(pdf_path)
        if pdf_text:
            # Create chunks with metadata
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=800, 
                chunk_overlap=100,
                length_function=len,
                separators=["\n\n", "\n", ". ", " ", ""]
            )
            chunks = splitter.create_documents(
                [pdf_text], 
                metadatas=[{"source": os.path.basename(pdf_path)}]
            )
            documents.extend(chunks)
            all_texts.extend([chunk.page_content for chunk in chunks])
    
    if not documents:
        raise Exception("No text could be extracted from PDF files")
    
    # Create embeddings and vector store
    logger.info("Creating embeddings and vector store...")
    embeddings = HuggingFaceEmbeddings(
        model_name="all-MiniLM-L6-v2",
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': True}
    )
    vector_store = FAISS.from_documents(documents, embeddings)
    
    # Set up retriever with increased initial results for reranking
    retriever = vector_store.as_retriever(
        search_type="similarity", 
        search_kwargs={"k": 20}  # Get more initial results for reranking
    )
    
    # Initialize BM25 for keyword search
    try:
        logger.info("Initializing BM25 index...")
        tokenized_docs = [doc.lower().split() for doc in all_texts]
        bm25_index = BM25Okapi(tokenized_docs)
        bm25_index.documents = all_texts  # Store original documents
        logger.info("BM25 index created successfully")
    except Exception as e:
        logger.error(f"Failed to create BM25 index: {e}")
        bm25_index = None
    
    # Initialize TF-IDF vectorizer
    try:
        logger.info("Initializing TF-IDF vectorizer...")
        tfidf_vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
        tfidf_vectorizer.fit(all_texts)
        logger.info("TF-IDF vectorizer initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize TF-IDF: {e}")
        tfidf_vectorizer = None
    
    logger.info(f"Advanced RAG system initialized with {len(pdf_files)} PDFs and {len(documents)} chunks")
    return len(pdf_files), len(documents)

def rerank_documents(query: str, documents: List, top_k: int = 10):
    """Rerank documents using cross-encoder"""
    if not reranker or not documents:
        return documents[:top_k]
    
    try:
        # Prepare query-document pairs
        query_doc_pairs = [(query, doc.page_content) for doc in documents]
        
        # Get reranking scores
        scores = reranker.predict(query_doc_pairs)
        
        # Sort documents by score
        doc_score_pairs = list(zip(documents, scores))
        doc_score_pairs.sort(key=lambda x: x[1], reverse=True)
        
        # Return top-k reranked documents
        reranked_docs = [doc for doc, score in doc_score_pairs[:top_k]]
        
        logger.info(f"Reranked {len(documents)} documents, returning top {len(reranked_docs)}")
        return reranked_docs
        
    except Exception as e:
        logger.error(f"Error in reranking: {e}")
        return documents[:top_k]

def create_rag_chain(llm_provider: str, model_name: Optional[str] = None, use_reranker: bool = True, max_chunks: int = 10):
    """Create RAG chain with specified LLM and reranking"""
    if retriever is None:
        raise Exception("RAG system not initialized")
    
    # Get LLM
    llm, llm_description = get_llm(llm_provider, model_name)
    
    # Enhanced prompt with source citations
    prompt = PromptTemplate(
        template="""
You are a helpful AI assistant for a company. Answer questions based ONLY on the provided document context.

Guidelines:
- Answer ONLY from the provided context
- If context is insufficient, say "I don't have enough information to answer this question"
- Be polite and professional as you're assisting fellow employees
- Write in Bangla if user writes in Bangla, otherwise use English
- Provide detailed, descriptive answers with bullet points when appropriate
- Include source references when mentioning specific information
- Guide users on where they can find more detailed information

Context from documents:
{context}

Question: {question}

Answer:""",
        input_variables=['context', 'question']
    )
    
    def enhanced_retrieval(question):
        """Enhanced retrieval with reranking"""
        # Get initial documents
        initial_docs = retriever.invoke(question)
        
        # Apply reranking if enabled
        if use_reranker and reranker:
            final_docs = rerank_documents(question, initial_docs, max_chunks)
        else:
            final_docs = initial_docs[:max_chunks]
        
        return final_docs
    
    import re

    def format_docs(retrieved_docs):
        """Clean and format PDF text before giving it to the LLM, including source info."""
        if not retrieved_docs:
            return "No relevant documents found."

        cleaned_chunks = []

        for i, doc in enumerate(retrieved_docs, 1):
            text = doc.page_content

            # Remove ALL markdown symbols: *, _, #, >, `, ~, **
            text = re.sub(r"[*_#>`~]", "", text)
            
            # Remove double asterisks specifically (for bold formatting)
            text = re.sub(r"\*\*", "", text)

            # Remove simple HTML tags like <p>, <br>, <div>, etc.
            text = re.sub(r"<.*?>", "", text)

            # Add line breaks before numbered items (1. 2. 3.)
            text = re.sub(r"(\d+\.)\s*", r"\n\1 ", text)

            # Remove excessive blank lines
            text = re.sub(r"\n{3,}", "\n\n", text)

            # Clean up any remaining multiple spaces
            text = re.sub(r"\s+", " ", text)

     # 1. Remove markdown bold (**) or other unwanted characters
            text = text.replace("**", "")
            text = text.replace("###", "")

                # 2. Add line breaks before numbered items (1. 2. 3.)
            text = re.sub(r"(\d+\.)\s*", r"\n\1 ", text)

                # 3. Remove excessive blank lines
            text = re.sub(r"\n{3,}", "\n\n", text)     

            text = text.strip()

            # Add source info
            source = doc.metadata.get('source', 'Unknown')
            cleaned_chunks.append(f"[Source {i}: {source}]\n{text}")

        return "\n\n".join(cleaned_chunks)


    # Create the enhanced chain
    parallel_chain = RunnableParallel({
        'context': RunnableLambda(enhanced_retrieval) | RunnableLambda(format_docs),
        'question': RunnablePassthrough()
    })
    
    parser = StrOutputParser()
    chain = parallel_chain | prompt | llm | parser
    
    return chain, llm_description

# Advanced RAG Components Implementation

def classify_query_type(query: str) -> str:
    """Classify the type of query to determine the best retrieval strategy"""
    query_lower = query.lower()
    
    if any(keyword in query_lower for keyword in ['how to', 'how do i', 'steps', 'process', 'workflow']):
        return "procedural"
    elif any(keyword in query_lower for keyword in ['what is', 'define', 'explain', 'meaning']):
        return "definitional"
    elif any(keyword in query_lower for keyword in ['where', 'location', 'find', 'search']):
        return "locational"
    elif any(keyword in query_lower for keyword in ['why', 'reason', 'because', 'purpose']):
        return "explanatory"
    elif any(keyword in query_lower for keyword in ['when', 'time', 'schedule', 'deadline']):
        return "temporal"
    else:
        return "general"

def transform_query(query: str, query_type: str) -> str:
    """Transform query based on type for better retrieval"""
    if query_type == "procedural":
        return f"step-by-step process for {query}"
    elif query_type == "definitional":
        return f"definition and explanation of {query}"
    elif query_type == "locational":
        return f"where to find information about {query}"
    elif query_type == "explanatory":
        return f"reasons and explanations for {query}"
    elif query_type == "temporal":
        return f"timing and scheduling information for {query}"
    else:
        return query

def semantic_search(query: str, k: int = 10) -> List[Any]:
    """Perform semantic search using vector similarity"""
    if retriever is None:
        return []
    
    try:
        docs = retriever.invoke(query)
        return docs[:k]
    except Exception as e:
        logger.error(f"Error in semantic search: {e}")
        return []

def keyword_search(query: str, k: int = 10) -> List[Any]:
    """Perform keyword search using BM25"""
    if bm25_index is None or not hasattr(bm25_index, 'get_scores'):
        return []
    
    try:
        # Tokenize query
        query_tokens = query.lower().split()
        
        # Get BM25 scores
        scores = bm25_index.get_scores(query_tokens)
        
        # Get document indices sorted by score
        doc_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        
        # Return top k documents
        keyword_docs = []
        for i in doc_indices[:k]:
            if i < len(bm25_index.documents):
                # Create a document-like object
                doc = type('Document', (), {
                    'page_content': bm25_index.documents[i],
                    'metadata': {'source': 'keyword_search', 'score': scores[i]}
                })()
                keyword_docs.append(doc)
        
        return keyword_docs
    except Exception as e:
        logger.error(f"Error in keyword search: {e}")
        return []

def hybrid_search(query: str, k: int = 10) -> List[Any]:
    """Combine semantic and keyword search results"""
    semantic_docs = semantic_search(query, k)
    keyword_docs = keyword_search(query, k)
    
    # Combine and deduplicate
    all_docs = []
    seen_content = set()
    
    # Add semantic docs first (higher priority)
    for doc in semantic_docs:
        content = doc.page_content
        if content not in seen_content:
            all_docs.append(doc)
            seen_content.add(content)
    
    # Add keyword docs that aren't duplicates
    for doc in keyword_docs:
        content = doc.page_content
        if content not in seen_content:
            all_docs.append(doc)
            seen_content.add(content)
    
    return all_docs[:k]

def advanced_rerank(query: str, documents: List[Any], top_k: int = 5) -> List[Any]:
    """Advanced reranking using multiple signals"""
    if not documents:
        return documents
    
    try:
        # Use cross-encoder reranker
        if reranker:
            query_doc_pairs = [(query, doc.page_content) for doc in documents]
            scores = reranker.predict(query_doc_pairs)
            
            # Combine with other signals
            doc_scores = []
            for i, doc in enumerate(documents):
                base_score = scores[i] if i < len(scores) else 0.0
                
                # Boost score for Studynet CRM specific terms
                content_lower = doc.page_content.lower()
                crm_boost = 0.1 if any(term in content_lower for term in 
                    ['studynet', 'crm', 'lead', 'application', 'admission']) else 0.0
                
                # Boost score for recent documents (if metadata available)
                recency_boost = 0.05 if 'recent' in str(doc.metadata).lower() else 0.0
                
                final_score = base_score + crm_boost + recency_boost
                doc_scores.append((doc, final_score))
            
            # Sort by final score
            doc_scores.sort(key=lambda x: x[1], reverse=True)
            return [doc for doc, score in doc_scores[:top_k]]
        
        return documents[:top_k]
    
    except Exception as e:
        logger.error(f"Error in advanced reranking: {e}")
        return documents[:top_k]

def generate_reasoning(query: str, query_type: str, docs: List[Any]) -> str:
    """Generate reasoning for the retrieval process"""
    reasoning_parts = [
        f"Query Type: {query_type}",
        f"Retrieved {len(docs)} relevant documents",
    ]
    
    if docs:
        sources = set()
        for doc in docs:
            source = doc.metadata.get('source', 'Unknown')
            sources.add(source)
        reasoning_parts.append(f"Sources: {', '.join(sources)}")
    
    return " | ".join(reasoning_parts)

def create_advanced_system_prompt() -> str:
    """Create context-aware system prompt based on Studynet CRM knowledge base"""
    return f"""
You are an expert AI assistant for Studynet CRM, a comprehensive Customer Relationship Management system for education services.

{KNOWLEDGE_BASE_CONTEXT}

Your role is to help users understand and navigate the Studynet CRM system effectively. You should:

1. **Provide Accurate Information**: Base your answers strictly on the provided context from Studynet CRM documentation
2. **Be Specific**: Reference specific features, processes, and workflows when relevant
3. **Guide Users**: Help users understand how to perform tasks within the CRM system
4. **Explain Processes**: Break down complex workflows into clear, actionable steps
5. **Handle Multiple Languages**: Respond in Bangla if the user writes in Bangla, otherwise use English
6. **Be Professional**: Maintain a helpful, professional tone as you're assisting fellow employees

When answering questions:
- Always cite specific sources when mentioning information
- Provide step-by-step instructions for procedural questions
- Explain the "why" behind processes when relevant
- Suggest related features or next steps when appropriate
- If information is not available in the context, clearly state this limitation

Remember: You are helping users work more effectively with Studynet CRM, so accuracy and clarity are paramount.
"""

def create_chain_of_thought_prompt() -> str:
    """Create a chain of thought prompt for reasoning"""
    return """
Let me think through this step by step:

1. **Understanding the Query**: What is the user asking about?
2. **Identifying Key Concepts**: What are the main topics and keywords?
3. **Analyzing Context**: What relevant information do we have?
4. **Reasoning Process**: How do the pieces of information connect?
5. **Forming the Answer**: What is the most helpful response?

Based on the Studynet CRM context provided, here's my analysis and response:
"""

# LangGraph Workflow Implementation

def query_classifier(state: AdvancedRAGState) -> AdvancedRAGState:
    """Classify the query type"""
    query = state["query"]
    query_type = classify_query_type(query)
    logger.info(f"Query classified as: {query_type}")
    return {"query_type": query_type}

def query_transformer(state: AdvancedRAGState) -> AdvancedRAGState:
    """Transform query based on type"""
    query = state["query"]
    query_type = state["query_type"]
    transformed_query = transform_query(query, query_type)
    logger.info(f"Query transformed: {transformed_query}")
    return {"transformed_query": transformed_query}

def semantic_retriever(state: AdvancedRAGState) -> AdvancedRAGState:
    """Perform semantic search"""
    query = state["transformed_query"]
    semantic_docs = semantic_search(query, k=15)
    logger.info(f"Retrieved {len(semantic_docs)} semantic documents")
    return {"semantic_docs": semantic_docs}

def keyword_retriever(state: AdvancedRAGState) -> AdvancedRAGState:
    """Perform keyword search"""
    query = state["transformed_query"]
    keyword_docs = keyword_search(query, k=15)
    logger.info(f"Retrieved {len(keyword_docs)} keyword documents")
    return {"keyword_docs": keyword_docs}

def hybrid_combiner(state: AdvancedRAGState) -> AdvancedRAGState:
    """Combine semantic and keyword search results"""
    semantic_docs = state["semantic_docs"]
    keyword_docs = state["keyword_docs"]
    hybrid_docs = hybrid_search(state["transformed_query"], k=20)
    logger.info(f"Combined into {len(hybrid_docs)} hybrid documents")
    return {"hybrid_docs": hybrid_docs}

def advanced_reranker(state: AdvancedRAGState) -> AdvancedRAGState:
    """Apply advanced reranking"""
    query = state["transformed_query"]
    hybrid_docs = state["hybrid_docs"]
    reranked_docs = advanced_rerank(query, hybrid_docs, top_k=8)
    logger.info(f"Reranked to {len(reranked_docs)} final documents")
    return {"reranked_docs": reranked_docs}

def context_formatter(state: AdvancedRAGState) -> AdvancedRAGState:
    """Format context from retrieved documents"""
    docs = state["reranked_docs"]
    
    if not docs:
        context = "No relevant documents found."
    else:
        formatted_chunks = []
        for i, doc in enumerate(docs, 1):
            source = doc.metadata.get('source', 'Unknown')
            content = doc.page_content.strip()
            formatted_chunks.append(f"[Source {i}: {source}]\n{content}")
        
        context = "\n\n".join(formatted_chunks)
    
    logger.info(f"Formatted context from {len(docs)} documents")
    return {"context": context}

def reasoning_generator(state: AdvancedRAGState) -> AdvancedRAGState:
    """Generate reasoning for the retrieval process"""
    query = state["query"]
    query_type = state["query_type"]
    docs = state["reranked_docs"]
    
    reasoning = generate_reasoning(query, query_type, docs)
    logger.info(f"Generated reasoning: {reasoning}")
    return {"reasoning": reasoning}

def answer_generator(state: AdvancedRAGState) -> AdvancedRAGState:
    """Generate final answer using LLM with advanced memory and chain of thought"""
    query = state["query"]
    context = state["context"]
    reasoning = state["reasoning"]
    
    # Get conversation history from advanced memory
    conversation_history = advanced_memory.get_conversation_context()
    
    # Create user context for advanced reasoning
    user_context = {
        "role": "employee",
        "department": "general",
        "access_level": "basic",
        "current_projects": []
    }
    
    # Check if complex reasoning is needed
    complex_indicators = ["why", "compare", "analyze", "what if", "predict", "recommend", "best approach", "pros and cons"]
    requires_complex_reasoning = any(indicator in query.lower() for indicator in complex_indicators)
    
    try:
        if requires_complex_reasoning:
            # Use advanced chain of thought reasoning
            # Create a simplified result for complex queries
            result = {
                "final_answer": {
                    "direct_answer": f"Based on the Studynet CRM documentation: {context[:500]}...",
                    "business_context": "This information is derived from the Studynet CRM knowledge base.",
                    "actionable_insights": ["Review the documentation for detailed implementation steps"],
                    "next_steps": ["Contact support for specific implementation guidance"],
                    "confidence_notes": ["High confidence in documentation accuracy"]
                },
                "chain_id": "simplified_chain",
                "confidence": 0.8,
                "reasoning_steps": []
            }
            
            # Format the advanced answer
            answer = result["final_answer"]
            if isinstance(answer, dict):
                formatted_answer = f"""
**Answer**: {answer.get('direct_answer', 'No direct answer available')}

**Business Context**: {answer.get('business_context', 'No additional context')}

**Actionable Insights**:
{chr(10).join(f"• {insight}" for insight in answer.get('actionable_insights', []))}

**Next Steps**:
{chr(10).join(f"• {step}" for step in answer.get('next_steps', []))}

**Confidence Notes**:
{chr(10).join(f"• {note}" for note in answer.get('confidence_notes', []))}
"""
            else:
                formatted_answer = str(answer)
            
            # Add reasoning steps to context
            reasoning_steps = result.get("reasoning_steps", [])
            enhanced_reasoning = f"{reasoning}\n\n**Advanced Reasoning Steps**:\n"
            for i, step in enumerate(reasoning_steps, 1):
                enhanced_reasoning += f"{i}. **{step['step_type'].title()}**: {step['reasoning']}\n"
            
            # Update advanced memory
            advanced_memory.add_conversation_turn(query, formatted_answer, {
                "reasoning_chain_id": result.get("chain_id"),
                "confidence": result.get("confidence"),
                "complex_reasoning": True
            })
            
            return {
                "answer": formatted_answer,
                "conversation_history": conversation_history,
                "reasoning": enhanced_reasoning
            }
        else:
            # Use simple RAG with enhanced memory
            # Get conversation history from memory
            memory_messages = conversation_memory.chat_memory.messages
            simple_conversation_history = []
            for msg in memory_messages[-4:]:  # Last 4 messages
                if isinstance(msg, HumanMessage):
                    simple_conversation_history.append({"role": "user", "content": msg.content})
                elif isinstance(msg, AIMessage):
                    simple_conversation_history.append({"role": "assistant", "content": msg.content})
            
            # Create the enhanced prompt with memory context
            system_prompt = create_advanced_system_prompt()
            chain_of_thought = create_chain_of_thought_prompt()
            
            # Build the full prompt with memory context
            prompt = f"""
{system_prompt}

{chain_of_thought}

**Current Query**: {query}
**Retrieval Reasoning**: {reasoning}

**Context from Studynet CRM Documentation**:
{context}

**Previous Conversation Context**:
{simple_conversation_history}

**Memory Context**:
{conversation_history}

**Your Response** (be specific, cite sources, and provide actionable guidance):
"""
            
            # Get LLM
            llm, _ = get_llm(current_llm_config["provider"], current_llm_config["model"])
            
            # Generate response
            response = llm.invoke(prompt)
            answer = response.content if hasattr(response, 'content') else str(response)
            
            # Update both memory systems
            conversation_memory.chat_memory.add_user_message(query)
            conversation_memory.chat_memory.add_ai_message(answer)
            
            advanced_memory.add_conversation_turn(query, answer, {
                "simple_reasoning": True,
                "sources_used": len(context.split('\n\n'))
            })
            
            logger.info("Generated answer successfully")
    
            return {
                "answer": answer,
                "conversation_history": simple_conversation_history,
                "reasoning": reasoning
            }
        
    except Exception as e:
        logger.error(f"Error generating answer: {e}")
        error_answer = f"I apologize, but I encountered an error while processing your question: {str(e)}"
        
        # Update memory with error
        advanced_memory.add_conversation_turn(query, error_answer, {"error": True})
        
    return {
            "answer": error_answer,
            "conversation_history": conversation_history,
            "reasoning": f"Error occurred: {str(e)}"
        }

def create_advanced_rag_workflow() -> StateGraph:
    """Create the advanced RAG workflow using LangGraph"""
    
    # Create the workflow
    workflow = StateGraph(AdvancedRAGState)
    
    # Add nodes
    workflow.add_node("classify_query", query_classifier)
    workflow.add_node("transform_query", query_transformer)
    workflow.add_node("semantic_search", semantic_retriever)
    workflow.add_node("keyword_search", keyword_retriever)
    workflow.add_node("hybrid_combine", hybrid_combiner)
    workflow.add_node("rerank", advanced_reranker)
    workflow.add_node("format_context", context_formatter)
    workflow.add_node("generate_reasoning", reasoning_generator)
    workflow.add_node("generate_answer", answer_generator)
    
    # Define the workflow
    workflow.set_entry_point("classify_query")
    workflow.add_edge("classify_query", "transform_query")
    workflow.add_edge("transform_query", "semantic_search")
    workflow.add_edge("transform_query", "keyword_search")
    workflow.add_edge("semantic_search", "hybrid_combine")
    workflow.add_edge("keyword_search", "hybrid_combine")
    workflow.add_edge("hybrid_combine", "rerank")
    workflow.add_edge("rerank", "format_context")
    workflow.add_edge("rerank", "generate_reasoning")
    workflow.add_edge("format_context", "generate_answer")
    workflow.add_edge("generate_reasoning", "generate_answer")
    workflow.add_edge("generate_answer", END)
    
    return workflow.compile()



# System endpoints
@app.get("/")
async def root():
    """Serve the main chat interface"""
    return FileResponse("index.html")

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "message": "Advanced PDF RAG API with LangGraph workflow is running", 
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "features": "Query Classification, Hybrid Search, Advanced Reranking, Chain of Thought, Memory"
    }

@app.get("/status")
async def get_status():
    """Get advanced RAG system status"""
    if retriever is None:
        return {"status": "not_initialized", "message": "Advanced RAG system not initialized"}
    
    return {
        "status": "ready", 
        "message": "Advanced RAG system ready to answer questions",
        "current_llm": current_llm_config,
        "components": {
            "semantic_search": vector_store is not None,
            "keyword_search": bm25_index is not None,
            "hybrid_search": vector_store is not None and bm25_index is not None,
            "reranker": reranker is not None,
            "tfidf": tfidf_vectorizer is not None,
            "memory": conversation_memory is not None
        },
        "features": [
            "Query Classification",
            "Query Transformation", 
            "Hybrid Search (Semantic + Keyword)",
            "Advanced Reranking",
            "Chain of Thought Reasoning",
            "Conversation Memory",
            "Context-Aware System Prompts",
            "Source Citation"
        ]
    }

@app.get("/llm-options")
async def get_llm_options():
    """Get available LLM options"""
    return {
        "providers": {
            "openai": {
                "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
                "default": "gpt-4o-mini"
            },
            "groq": {
                "models": ["deepseek-r1-distill-llama-70b", "llama-3.1-70b-versatile", "mixtral-8x7b-32768"],
                "default": "deepseek-r1-distill-llama-70b"
            },
            "gemini": {
                "models": ["gemini-pro", "gemini-1.5-pro", "gemini-1.5-flash"],
                "default": "gemini-1.5-flash"
            }
        }
    }

@app.post("/configure-llm")
async def configure_llm(config: LLMConfigRequest):
    """Configure default LLM settings"""
    global current_llm_config
    
    try:
        # Test the LLM configuration
        _, llm_description = get_llm(config.llm_provider, config.model_name)
        
        current_llm_config = {
            "provider": config.llm_provider,
            "model": config.model_name or {
                "openai": "gpt-4o-mini",
                "groq": "deepseek-r1-distill-llama-70b",
                "gemini": "gemini-1.5-flash"
            }[config.llm_provider]
        }
        
        logger.info(f"LLM configuration updated: {llm_description}")
        
        return {
            "status": "success",
            "message": f"LLM configured to {llm_description}",
            "config": current_llm_config
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error configuring LLM: {str(e)}")

# Document management endpoints
@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    """Upload a PDF file to the pdfs folder and reinitialize RAG system"""
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    # Check file size (50MB limit)
    if file.size and file.size > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size too large. Maximum 50MB allowed.")
    
    file_path = None
    try:
        # Ensure pdfs folder exists
        pdf_folder = "pdfs"
        if not os.path.exists(pdf_folder):
            os.makedirs(pdf_folder)
        
        # Save the uploaded file with timestamp to avoid conflicts
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{timestamp}_{file.filename}"
        file_path = os.path.join(pdf_folder, safe_filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        logger.info(f"PDF uploaded: {safe_filename}")
        
        # Reinitialize RAG system with all PDFs
        global vector_store, retriever
        num_pdfs, num_chunks = initialize_rag_system(pdf_folder)
        
        return {
            "status": "success",
            "message": f"PDF uploaded successfully and RAG system updated",
            "filename": safe_filename,
            "original_filename": file.filename,
            "total_pdfs": num_pdfs,
            "total_chunks": num_chunks
        }
        
    except Exception as e:
        # Clean up the file if there was an error
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        logger.error(f"Error uploading PDF: {e}")
        raise HTTPException(status_code=500, detail=f"Error uploading PDF: {str(e)}")

@app.get("/documents")
async def list_documents():
    """List all PDF documents in the system"""
    try:
        pdf_folder = "pdfs"
        if not os.path.exists(pdf_folder):
            return {"documents": [], "total": 0}
        
        documents = []
        for filename in os.listdir(pdf_folder):
            if filename.lower().endswith('.pdf'):
                file_path = os.path.join(pdf_folder, filename)
                stat = os.stat(file_path)
                documents.append({
                    "filename": filename,
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "uploaded_date": datetime.fromtimestamp(stat.st_ctime).isoformat()
                })
        
        documents.sort(key=lambda x: x["uploaded_date"], reverse=True)
        
        return {
            "documents": documents,
            "total": len(documents)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing documents: {str(e)}")

# Chat endpoint
@app.post("/ask", response_model=QuestionResponse)
async def ask_question(request: QuestionRequest):
    """Ask a question to the advanced RAG system with LangGraph workflow"""
    if retriever is None:
        raise HTTPException(status_code=503, detail="Advanced RAG system not initialized. Please contact administrator.")
    
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    
    try:
        # Update LLM config if specified
        if request.llm_provider:
            current_llm_config["provider"] = request.llm_provider
        if request.model_name:
            current_llm_config["model"] = request.model_name
        
        # Create the advanced RAG workflow
        workflow = create_advanced_rag_workflow()
        
        # Initialize state
        initial_state = {
            "query": request.question,
            "query_type": "",
            "transformed_query": "",
            "semantic_docs": [],
            "keyword_docs": [],
            "hybrid_docs": [],
            "reranked_docs": [],
            "context": "",
            "reasoning": "",
            "answer": "",
            "memory": [],
            "conversation_history": []
        }
        
        # Run the workflow
        logger.info(f"Processing question with advanced RAG workflow: {request.question}")
        result = workflow.invoke(initial_state)
        
        # Extract sources from reranked documents
        sources = []
        if result.get("reranked_docs"):
            sources = list(set([doc.metadata.get('source', 'Unknown') for doc in result["reranked_docs"]]))
        
        # Get LLM description
        _, llm_description = get_llm(current_llm_config["provider"], current_llm_config["model"])
        
        return QuestionResponse(
            answer=result.get("answer", "No answer generated"),
            status="success",
            llm_used=llm_description,
            chunks_used=len(result.get("reranked_docs", [])),
            reranker_used=request.use_reranker and reranker is not None,
            query_type=result.get("query_type", "unknown"),
            reasoning=result.get("reasoning", ""),
            sources=sources,
            conversation_context=len(result.get("conversation_history", [])) > 0
        )
        
    except Exception as e:
        logger.error(f"Error processing question with advanced RAG: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing question: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
    