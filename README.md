# 🧠 DocuMind

### Production-Grade RAG Document Intelligence Platform

**DocuMind** is a scalable Retrieval-Augmented Generation (RAG) platform that lets users upload PDF documents and interact with them through a real-time AI chat interface.

It combines **semantic vector search, asynchronous document processing, streaming LLM responses, and source-aware generation** to provide accurate, context-grounded answers from user-provided documents.

> **Upload → Process → Embed → Retrieve → Generate → Stream**

---

## ✨ Features

* 📄 **PDF Document Upload** — Upload and manage multiple documents.
* 🔍 **Semantic Search** — Retrieve relevant document content using vector embeddings.
* 🧠 **RAG-Based QA** — Generate answers grounded in retrieved document context.
* ⚡ **Real-Time Streaming** — Stream LLM responses token-by-token for a responsive experience.
* 📚 **Source-Aware Responses** — Responses can reference the source document and page.
* 🔄 **Asynchronous Processing** — PDF parsing, chunking, embedding, and indexing run in background workers.
* 📈 **Scalable Architecture** — Worker-based processing allows horizontal scaling.
* 🗃️ **Vector Database** — Qdrant stores and retrieves high-dimensional document embeddings.
* ☁️ **Cloud + Local LLM Support** — Pluggable architecture supporting Gemini/OpenAI APIs and Ollama.
* 🐳 **Dockerized Infrastructure** — Queue and vector infrastructure can be run using Docker Compose.
* 🔌 **Pluggable LLM Architecture** — Swap between cloud-hosted and self-hosted inference.
* 🚀 **Non-Blocking Upload API** — Heavy document processing is moved away from request/response execution.

---

# 🏗️ Architecture

```text
                         ┌──────────────────────┐
                         │       Frontend       │
                         │    Next.js + React   │
                         └──────────┬───────────┘
                                    │
                         Upload / Chat Request
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │      Backend API     │
                         │     FastAPI / API    │
                         └───────┬───────┬──────┘
                                 │       │
                     Upload Job  │       │  Query
                                 │       │
                                 ▼       ▼
                         ┌──────────┐  ┌──────────────┐
                         │  BullMQ  │  │   Retriever  │
                         │  + Valkey│  │   + Qdrant   │
                         └────┬─────┘  └──────┬───────┘
                              │               │
                              ▼               │
                     ┌────────────────┐      │
                     │ Background     │      │
                     │ Worker         │      │
                     │                │      │
                     │ PDF Parsing    │      │
                     │ Chunking       │      │
                     │ Embeddings     │      │
                     │ Vector Index   │      │
                     └───────┬────────┘      │
                             │               │
                             ▼               ▼
                       ┌────────────────────────┐
                       │    Qdrant Vector DB    │
                       │                        │
                       │ Document Embeddings    │
                       │ Metadata / Chunks      │
                       └───────────┬────────────┘
                                   │
                             Relevant Context
                                   │
                                   ▼
                         ┌──────────────────────┐
                         │     LLM Provider     │
                         │                      │
                         │ Gemini / OpenAI      │
                         │ Ollama (Local)       │
                         └──────────┬───────────┘
                                    │
                              Streaming Response
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │   React Chat UI      │
                         └──────────────────────┘
```

---

# 🔄 RAG Pipeline

DocuMind separates **document ingestion** from **question answering**.

### 1. Document Ingestion

```text
PDF Upload
    ↓
API receives document
    ↓
Create processing job
    ↓
BullMQ / Valkey Queue
    ↓
Background Worker
    ↓
PDF Text Extraction
    ↓
Text Chunking
    ↓
Embedding Generation
    ↓
Qdrant Vector Indexing
```

### 2. Question Answering

```text
User Question
      ↓
Generate Query Embedding
      ↓
Semantic Vector Search
      ↓
Retrieve Relevant Chunks
      ↓
MMR / Context Selection
      ↓
Construct Grounded Prompt
      ↓
LLM Generation
      ↓
Stream Response
      ↓
User
```

This architecture ensures that expensive document-processing operations do not block API requests.

---

# 🧩 Tech Stack

| Layer           | Technology          |
| --------------- | ------------------- |
| Frontend        | Next.js 16          |
| UI              | React 19            |
| AI / RAG        | LangChain           |
| LLM Interface   | Vercel AI SDK       |
| Vector Database | Qdrant              |
| Embeddings      | Gemini Embeddings   |
| Cloud LLM       | Gemini / OpenAI     |
| Local LLM       | Ollama              |
| Backend         | FastAPI             |
| Task Queue      | BullMQ              |
| Queue Backend   | Valkey / Redis      |
| Database        | PostgreSQL          |
| Infrastructure  | Docker Compose      |
| Deployment      | Render / Vercel     |
| Language        | TypeScript / Python |

---

# 🚀 Getting Started

## Prerequisites

Make sure you have installed:

* Node.js 20+
* Python 3.11+
* Docker
* Docker Compose
* Git

You will also need API credentials for the LLM/embedding provider you choose.

---

## 📥 Clone the Repository

```bash
git clone https://github.com/<your-username>/documind.git

cd documind
```

---

# ⚙️ Backend Setup

Navigate to the backend:

```bash
cd backend
```

### Create Virtual Environment

### Windows

```powershell
python -m venv venv

.\venv\Scripts\Activate.ps1
```

### macOS / Linux

```bash
python3 -m venv venv

source venv/bin/activate
```

---

## Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Environment Variables

Create:

```text
backend/.env
```

Example:

```env
DATABASE_URL=your_postgresql_connection_string

QDRANT_URL=your_qdrant_url
QDRANT_API_KEY=your_qdrant_api_key

GEMINI_API_KEY=your_gemini_api_key

OPENAI_API_KEY=your_openai_api_key

REDIS_URL=redis://localhost:6379

CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

> Never commit `.env` files or API keys to GitHub.

---

# 🐳 Start Infrastructure

Start the local infrastructure:

```bash
docker compose up -d
```

This can start services such as:

```text
Qdrant
Valkey / Redis
```

Verify running containers:

```bash
docker ps
```

---

# ▶️ Start Backend

From the `backend` directory:

```bash
uvicorn app.main:app --reload
```

The API will be available at:

```text
http://localhost:8000
```

Interactive API documentation:

```text
http://localhost:8000/docs
```

---

# ⚙️ Start Background Worker

Open another terminal.

Activate the virtual environment:

```powershell
.\venv\Scripts\Activate.ps1
```

Start the worker:

```bash
celery -A app.celery_app worker --loglevel=info --pool=solo
```

On Windows, `--pool=solo` is recommended for local Celery development.

---

# 💻 Frontend Setup

Navigate to the frontend:

```bash
cd frontend
```

Install dependencies:

```bash
npm install
```

Create:

```text
.env.local
```

Example:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Start the development server:

```bash
npm run dev
```

Open:

```text
http://localhost:3000
```

---

# 📂 Project Structure

```text
documind/
│
├── frontend/
│   ├── app/
│   ├── components/
│   ├── lib/
│   ├── hooks/
│   └── ...
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   │
│   │   ├── core/
│   │   │   └── config.py
│   │   │
│   │   ├── models/
│   │   │
│   │   ├── services/
│   │   │   ├── qdrant_service.py
│   │   │   ├── embedding_service.py
│   │   │   └── document_service.py
│   │   │
│   │   ├── workers/
│   │   │
│   │   └── celery_app.py
│   │
│   ├── requirements.txt
│   └── .env
│
├── docker-compose.yml
├── README.md
└── .gitignore
```

---

# 🧠 Retrieval Strategy

DocuMind uses vector similarity to identify relevant document chunks.

For a user query:

```text
"What projects did I build?"
```

the query is converted into an embedding vector.

Qdrant then searches for semantically similar document chunks.

The retrieved context is passed to the LLM:

```text
User Query
    +
Retrieved Context
    ↓
Grounded Prompt
    ↓
LLM
    ↓
Answer
```

This reduces dependence on keyword matching and allows semantically related questions to retrieve relevant information.

---

# 🎯 Maximum Marginal Relevance

DocuMind also supports **MMR-based retrieval** to improve context diversity.

Instead of returning six nearly identical chunks:

```text
Chunk A ───── Similar
Chunk B ───── Similar
Chunk C ───── Similar
Chunk D ───── Similar
```

MMR balances:

```text
Relevance
      +
Diversity
```

Conceptually:

```text
MMR =
λ × Relevance
-
(1 − λ) × Redundancy
```

This helps provide the LLM with broader document coverage.

---

# ⚡ Asynchronous Document Processing

Large PDF processing can involve:

* PDF parsing
* Text extraction
* Chunk generation
* Embedding computation
* Vector insertion

Running these operations directly inside an upload request can make the API slow or timeout under load.

DocuMind moves this workload to background workers:

```text
POST /upload
     │
     ▼
Create Document
     │
     ▼
Create Queue Job
     │
     ▼
Return Immediately
     │
     ▼
Background Worker
     │
     ├── Extract
     ├── Chunk
     ├── Embed
     └── Index
```

This allows the API to remain responsive while documents are processed asynchronously.

---

# 📈 Scalability

The worker architecture allows additional workers to be added independently.

```text
                 Valkey / Redis
                       │
             ┌─────────┼─────────┐
             ▼         ▼         ▼
          Worker 1  Worker 2  Worker 3
             │         │         │
             └─────────┼─────────┘
                       ▼
                    Qdrant
```

As document-processing demand increases, additional workers can be deployed without changing the API layer.

---

# 🤖 LLM Flexibility

DocuMind is designed around a pluggable LLM architecture.

### Cloud inference

```text
Gemini
OpenAI
```

### Local inference

```text
Ollama
```

This allows users to choose between:

| Mode  | Advantage                                               |
| ----- | ------------------------------------------------------- |
| Cloud | High-quality inference and easier scaling               |
| Local | Privacy, offline inference, and no per-request API cost |

---

# 🔐 Security Considerations

For production deployments:

* Store secrets in environment variables.
* Never commit API keys.
* Validate uploaded file types.
* Enforce upload-size limits.
* Sanitize extracted document content.
* Apply authentication and authorization.
* Restrict access to document IDs.
* Use HTTPS in production.
* Apply rate limiting to public APIs.
* Validate LLM-generated responses against retrieved context.

---

# 📊 Performance Goals

The architecture is designed around:

### API responsiveness

Heavy processing is moved to workers.

### Retrieval latency

Qdrant provides optimized vector similarity search.

### Streaming UX

LLM output is streamed to the frontend rather than waiting for the complete response.

### Horizontal scalability

Multiple workers can process independent ingestion jobs concurrently.

---

# 🛣️ Roadmap

### Completed

* [x] PDF upload
* [x] PDF text extraction
* [x] Text chunking
* [x] Embedding generation
* [x] Qdrant vector storage
* [x] Semantic retrieval
* [x] MMR retrieval
* [x] RAG-based generation
* [x] Streaming chat interface
* [x] PostgreSQL document metadata
* [x] Background document processing
* [x] BullMQ / Valkey integration
* [x] Gemini / OpenAI support
* [x] Ollama integration
* [x] Dockerized infrastructure

### Planned

* [ ] Parent-child document retrieval
* [ ] Hybrid BM25 + vector search
* [ ] Cross-encoder reranking
* [ ] Conversation memory
* [ ] Multi-document reasoning
* [ ] Authentication
* [ ] Document-level access control
* [ ] Advanced evaluation pipeline
* [ ] RAG observability with LangSmith
* [ ] Automated retrieval evaluation
* [ ] Document deletion and cleanup jobs

---

# 🧪 Example Queries

Once a document has been indexed, users can ask:

```text
What projects are mentioned in this resume?

What technologies were used in the RAG project?

Summarize the candidate's experience.

What was the candidate's role in the Web Development Society?

Which projects used Next.js?

What are the key technical skills mentioned in the document?
```

---

# 🔬 Why RAG?

Traditional LLM applications rely entirely on the model's pretrained knowledge.

DocuMind instead grounds responses in user-provided documents:

```text
Traditional LLM

Question
   ↓
LLM
   ↓
Answer


DocuMind

Question
   ↓
Embedding
   ↓
Vector Search
   ↓
Relevant Document Context
   ↓
LLM
   ↓
Grounded Answer
```

This enables the system to work with private or previously unseen documents without requiring model fine-tuning.

---

# 🌟 Key Engineering Highlights

This project demonstrates practical experience with:

* **Retrieval-Augmented Generation**
* **Vector databases**
* **Semantic embeddings**
* **LLM application architecture**
* **Asynchronous job processing**
* **Distributed workers**
* **Streaming AI interfaces**
* **Dockerized infrastructure**
* **Cloud and local inference**
* **Scalable backend architecture**
* **Production-oriented API design**

---

# 🤝 Contributing

Contributions are welcome.

```bash
git checkout -b feature/your-feature

git add .

git commit -m "feat: add your feature"

git push origin feature/your-feature
```

Then open a pull request.

---

# 📄 License

This project is licensed under the MIT License.

---

## 👨‍💻 Author

**Harshit Sahu**

Built with:

**Next.js · React · FastAPI · LangChain · Qdrant · BullMQ · Valkey · PostgreSQL · Gemini · OpenAI  · Docker**

---

<p align="center">

### ⭐ If you found this project interesting, consider starring the repository.

</p>
