import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import "./App.css";

const API_URL = import.meta.env.VITE_API_URL;

interface Document {
  id: string;
  filename: string;
  status: string;
  pages: number;
  chunks: number;
  created_at: string;
}

interface Source {
  score: number;
  text: string;
  filename: string;
  page: number;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
}

function App() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [selectedDocument, setSelectedDocument] =
    useState<Document | null>(null);

  const [messages, setMessages] = useState<Message[]>([]);
  const [query, setQuery] = useState("");
  const [loadingDocuments, setLoadingDocuments] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [asking, setAsking] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Fetch all documents
  const fetchDocuments = async () => {
    try {
      setLoadingDocuments(true);

      const response = await fetch(`${API_URL}/documents`);
      const data = await response.json();

      setDocuments(data.documents || []);
    } catch (error) {
      console.error("Failed to fetch documents:", error);
    } finally {
      setLoadingDocuments(false);
    }
  };

  // Fetch documents when the app starts
  useEffect(() => {
    fetchDocuments();
  }, []);

  // Load saved chat when selected document changes
  useEffect(() => {
    if (!selectedDocument) {
      setMessages([]);
      return;
    }

    const savedMessages = localStorage.getItem(
      `chat-${selectedDocument.id}`
    );

    if (savedMessages) {
      try {
        setMessages(JSON.parse(savedMessages));
      } catch (error) {
        console.error("Failed to load chat history:", error);
        setMessages([]);
      }
    } else {
      setMessages([]);
    }
  }, [selectedDocument?.id]);

  // Save chat whenever messages change
  useEffect(() => {
    if (!selectedDocument) return;

    localStorage.setItem(
      `chat-${selectedDocument.id}`,
      JSON.stringify(messages)
    );
  }, [messages, selectedDocument?.id]);

  // Automatically check processing documents
  useEffect(() => {
    const processingDocuments = documents.filter(
      (document) => document.status === "processing"
    );

    if (processingDocuments.length === 0) {
      return;
    }

    const interval = setInterval(async () => {
      try {
        const updatedDocuments = await Promise.all(
          processingDocuments.map(async (document) => {
            const response = await fetch(
              `${API_URL}/documents/${document.id}`
            );

            if (!response.ok) {
              return document;
            }

            return await response.json();
          })
        );

        setDocuments((previousDocuments) =>
          previousDocuments.map((document) => {
            const updatedDocument = updatedDocuments.find(
              (updated) => updated.id === document.id
            );

            return updatedDocument
              ? {
                ...document,
                ...updatedDocument,
              }
              : document;
          })
        );

        setSelectedDocument((previousSelected) => {
          if (!previousSelected) {
            return null;
          }

          const updatedDocument = updatedDocuments.find(
            (document) =>
              document.id === previousSelected.id
          );

          return updatedDocument
            ? {
              ...previousSelected,
              ...updatedDocument,
            }
            : previousSelected;
        });
      } catch (error) {
        console.error(
          "Failed to update document status:",
          error
        );
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [documents]);

  // Auto-scroll to the newest message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages, asking]);

  // Upload PDF
  const handleUpload = async (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const file = event.target.files?.[0];

    if (!file) return;

    if (file.type !== "application/pdf") {
      alert("Please select a PDF file.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    try {
      setUploading(true);

      const response = await fetch(
        `${API_URL}/documents/upload`,
        {
          method: "POST",
          body: formData,
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Failed to upload document."
        );
      }

      const newDocument: Document = {
        id: data.document_id,
        filename: data.filename,
        status: data.status,
        pages: 0,
        chunks: 0,
        created_at: new Date().toISOString(),
      };

      setDocuments((previousDocuments) => [
        newDocument,
        ...previousDocuments,
      ]);

      setSelectedDocument(newDocument);

    } catch (error) {
      alert(
        error instanceof Error
          ? error.message
          : "Upload failed."
      );
    } finally {
      setUploading(false);

      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  // Ask a question
  const handleSendMessage = async () => {
    const trimmedQuery = query.trim();

    if (!trimmedQuery || !selectedDocument || asking) {
      return;
    }

    const userMessage: Message = {
      role: "user",
      content: trimmedQuery,
    };

    setMessages((previousMessages) => [
      ...previousMessages,
      userMessage,
    ]);

    setQuery("");
    setAsking(true);

    try {
      const params = new URLSearchParams({
        query: trimmedQuery,
        document_id: selectedDocument.id,
      });

      const response = await fetch(
        `${API_URL}/chat?${params.toString()}`
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Failed to get answer."
        );
      }

      const assistantMessage: Message = {
        role: "assistant",
        content: data.answer,
        sources: data.sources,
      };

      setMessages((previousMessages) => [
        ...previousMessages,
        assistantMessage,
      ]);

    } catch (error) {
      const errorMessage: Message = {
        role: "assistant",
        content:
          error instanceof Error
            ? error.message
            : "Something went wrong.",
      };

      setMessages((previousMessages) => [
        ...previousMessages,
        errorMessage,
      ]);

    } finally {
      setAsking(false);
    }
  };

  // Delete document
  const handleDeleteDocument = async (
    event: React.MouseEvent,
    documentId: string
  ) => {
    event.stopPropagation();

    const confirmed = window.confirm(
      "Are you sure you want to delete this document?"
    );

    if (!confirmed) return;

    try {
      const response = await fetch(
        `${API_URL}/documents/${documentId}`,
        {
          method: "DELETE",
        }
      );

      if (!response.ok) {
        throw new Error("Failed to delete document.");
      }

      setDocuments((previousDocuments) =>
        previousDocuments.filter(
          (document) => document.id !== documentId
        )
      );

      // Delete saved chat for this document
      localStorage.removeItem(`chat-${documentId}`);

      if (selectedDocument?.id === documentId) {
        setSelectedDocument(null);
      }

    } catch (error) {
      alert(
        error instanceof Error
          ? error.message
          : "Failed to delete document."
      );
    }
  };

  // Clear chat for current document
  const handleClearChat = () => {
    if (!selectedDocument) return;

    const confirmed = window.confirm(
      "Are you sure you want to clear this chat?"
    );

    if (!confirmed) return;

    setMessages([]);

    localStorage.removeItem(
      `chat-${selectedDocument.id}`
    );
  };

  // Send with Enter
  const handleKeyDown = (
    event: React.KeyboardEvent<HTMLInputElement>
  ) => {
    if (event.key === "Enter") {
      handleSendMessage();
    }
  };

  return (
    <div className="app">

      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <h2>Document QA</h2>
          <p>AI-powered PDF chat</p>
        </div>

        <button
          className="upload-button"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
        >
          {uploading ? "Uploading..." : "+ Upload PDF"}
        </button>

        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,application/pdf"
          onChange={handleUpload}
          hidden
        />

        <div className="documents-section">
          <p className="section-title">
            YOUR DOCUMENTS
          </p>

          {loadingDocuments ? (
            <p className="empty-text">
              Loading documents...
            </p>
          ) : documents.length === 0 ? (
            <p className="empty-text">
              No documents yet.
            </p>
          ) : (
            <div className="documents-list">
              {documents.map((document) => (
                <div
                  key={document.id}
                  className={`document-item ${selectedDocument?.id === document.id
                      ? "active"
                      : ""
                    }`}
                  onClick={() =>
                    setSelectedDocument(document)
                  }
                >
                  <div className="document-info">
                    <span className="document-icon">
                      📄
                    </span>

                    <div>
                      <p className="document-name">
                        {document.filename}
                      </p>

                      <span className="document-status">
                        {document.status}
                      </span>
                    </div>
                  </div>

                  <button
                    className="delete-button"
                    onClick={(event) =>
                      handleDeleteDocument(
                        event,
                        document.id
                      )
                    }
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </aside>

      {/* Main Chat Area */}
      <main className="main-content">

        {selectedDocument ? (
          <>
            <div className="chat-header">
              <div>
                <h1>
                  {selectedDocument.filename}
                </h1>

                <p>
                  Status:{" "}
                  <span
                    className={`status ${selectedDocument.status
                      }`}
                  >
                    {selectedDocument.status}
                  </span>
                </p>
              </div>

              <div className="document-stats">
                <span>
                  {selectedDocument.pages || 0} pages
                </span>

                <span>
                  {selectedDocument.chunks || 0} chunks
                </span>

                {messages.length > 0 && (
                  <button
                    onClick={handleClearChat}
                    className="clear-chat-button"
                  >
                    Clear Chat
                  </button>
                )}
              </div>
            </div>

            <div className="messages">

              {messages.length === 0 && (
                <div className="welcome-message">
                  <h2>
                    Ask anything about this document
                  </h2>

                  <p>
                    Ask questions and get answers based
                    only on the contents of the PDF.
                  </p>
                </div>
              )}

              {messages.map((message, index) => (
                <div
                  key={index}
                  className={`message ${message.role}`}
                >
                  <div className="message-label">
                    {message.role === "user"
                      ? "You"
                      : "AI Assistant"}
                  </div>

                  <div className="message-content">
                    {message.role === "assistant" ? (
                      <ReactMarkdown>
                        {message.content}
                      </ReactMarkdown>
                    ) : (
                      message.content
                    )}
                  </div>

                  {message.sources &&
                    message.sources.length > 0 && (
                      <div className="sources">
                        <p>Retrieved sources</p>

                        {message.sources.map(
                          (source, sourceIndex) => (
                            <div
                              key={sourceIndex}
                              className="source-card"
                            >
                              <div className="source-header">
                                <strong>
                                  {source.filename}
                                </strong>

                                <span>
                                  Page {source.page}
                                </span>
                              </div>

                              <p>
                                {source.text}
                              </p>
                            </div>
                          )
                        )}
                      </div>
                    )}
                </div>
              ))}

              {asking && (
                <div className="message assistant">
                  <div className="message-label">
                    AI Assistant
                  </div>

                  <div className="message-content typing">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                </div>
              )}

              {/* Auto-scroll target */}
              <div ref={messagesEndRef} />
            </div>

            <div className="chat-input-container">
              <input
                value={query}
                onChange={(event) =>
                  setQuery(event.target.value)
                }
                onKeyDown={handleKeyDown}
                placeholder="Ask a question about this document..."
                disabled={
                  asking ||
                  selectedDocument.status !== "completed"
                }
              />

              <button
                onClick={handleSendMessage}
                disabled={
                  !query.trim() ||
                  asking ||
                  selectedDocument.status !== "completed"
                }
              >
                Send
              </button>
            </div>
          </>
        ) : (
          <div className="no-document">
            <div>
              <h1>
                Select or upload a document
              </h1>

              <p>
                Choose a PDF from the sidebar to start
                asking questions.
              </p>
            </div>
          </div>
        )}

      </main>
    </div>
  );
}

export default App;