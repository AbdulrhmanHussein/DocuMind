from __future__ import annotations
from typing import Any
from urllib.parse import quote
import time
import requests
import streamlit as st


# -----------------------------------------------------------------------------
# Page setup
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="DocuMind | Document Chat",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

DEFAULT_API_URL = "http://127.0.0.1:8000"
DOCS_CACHE_TTL_SECONDS = 15


# -----------------------------------------------------------------------------
# HTTP helpers
# -----------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def get_http_session() -> requests.Session:
    """Reuse a Session so HTTP connections can be reused between Streamlit reruns."""
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    return session


def make_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def response_error(response: requests.Response) -> str:
    """Extract a readable FastAPI or HTTP error message."""
    try:
        body = response.json()
        if isinstance(body, dict):
            detail = body.get("detail") or body.get("message") or body.get("error")
            if isinstance(detail, list):
                return "; ".join(
                    str(item.get("msg", item)) if isinstance(item, dict) else str(item)
                    for item in detail
                )
            if detail:
                return str(detail)
        return str(body)
    except (ValueError, requests.exceptions.JSONDecodeError):
        text = (response.text or "").strip()
        return text[:800] if text else f"HTTP {response.status_code} error"


def request_json(
    method: str,
    base_url: str,
    path: str,
    *,
    connect_timeout: float = 3,
    read_timeout: float = 30,
    **kwargs: Any,
) -> Any:
    response = get_http_session().request(
        method,
        make_url(base_url, path),
        timeout=(connect_timeout, read_timeout),
        **kwargs,
    )
    if not response.ok:
        raise RuntimeError(f"API returned HTTP {response.status_code}: {response_error(response)}")
    if not response.content:
        return {}
    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError("The API returned a non-JSON response.") from exc


@st.cache_data(ttl=DOCS_CACHE_TTL_SECONDS, show_spinner=False)
def fetch_documents(base_url: str) -> list[dict[str, Any]]:
    """Cache the document list briefly; upload/delete explicitly clear this cache."""
    payload = request_json("GET", base_url, "/api/v1/documents", read_timeout=15)

    if isinstance(payload, list):
        raw_documents = payload
    elif isinstance(payload, dict):
        raw_documents = []
        for key in ("documents", "items", "results", "data"):
            candidate = payload.get(key)
            if isinstance(candidate, list):
                raw_documents = candidate
                break
        if not raw_documents and any(
            key in payload for key in ("document_id", "_id", "id", "filename", "file_name")
        ):
            raw_documents = [payload]
    else:
        raw_documents = []

    documents: list[dict[str, Any]] = []
    for item in raw_documents:
        if isinstance(item, dict):
            documents.append(item)
    return documents


def first_value(item: dict[str, Any], keys: tuple[str, ...], default: Any = "") -> Any:
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return default


def document_id(document: dict[str, Any]) -> str:
    value = first_value(document, ("document_id", "id", "_id"), "")
    return str(value) if value is not None else ""


def document_name(document: dict[str, Any]) -> str:
    return str(
        first_value(
            document,
            ("filename", "original_filename", "file_name", "name", "title"),
            "Untitled document",
        )
    )


def source_list(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    sources = payload.get("sources") or payload.get("retrieved_sources") or payload.get("citations") or []
    return [source for source in sources if isinstance(source, dict)] if isinstance(sources, list) else []


def answer_text(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        for key in ("answer", "response", "output", "message", "result"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return "The API returned a response, but no answer field was found. Inspect the response schema in FastAPI /docs."
    return str(payload)


def render_sources(sources: list[dict[str, Any]], prefix: str) -> None:
    if not sources:
        return
    with st.expander(f"Sources ({len(sources)})", expanded=False):
        for index, source in enumerate(sources, start=1):
            source_name = first_value(source, ("filename", "source", "file_name", "document_name"), "Unknown file")
            source_id = first_value(source, ("source_id",), f"S{index}")
            page = source.get("page")
            chunk_index = first_value(source, ("chunk_index", "chunk_id"), None)
            distance = source.get("distance")
            st.markdown(f"**[{source_id}] {source_name}**")
            metadata = []
            if page is not None:
                metadata.append(f"Page: {page}")
            if chunk_index is not None:
                metadata.append(f"Chunk: {chunk_index}")
            if distance is not None:
                try:
                    metadata.append(f"Distance: {float(distance):.4f}")
                except (TypeError, ValueError):
                    metadata.append(f"Distance: {distance}")
            if metadata:
                st.caption(" · ".join(metadata))
            snippet = first_value(source, ("text", "chunk_text", "content", "excerpt"), "")
            if snippet:
                st.write(str(snippet))
            if index < len(sources):
                st.divider()


# -----------------------------------------------------------------------------
# Session state
# -----------------------------------------------------------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "api_url" not in st.session_state:
    st.session_state.api_url = DEFAULT_API_URL
if "notice" not in st.session_state:
    st.session_state.notice = None


# -----------------------------------------------------------------------------
# Sidebar: configuration, document upload and management
# -----------------------------------------------------------------------------
with st.sidebar:
    st.title("📚 DocuMind")
    st.caption("Bilingual document intelligence")

    base_url = st.text_input(
        "FastAPI base URL",
        value=st.session_state.api_url,
        help="Local default: http://127.0.0.1:8000",
    ).strip().rstrip("/")
    if not base_url:
        base_url = DEFAULT_API_URL
    if base_url != st.session_state.api_url:
        st.session_state.api_url = base_url
        fetch_documents.clear()

    col_health1, col_health2 = st.columns(2)
    with col_health1:
        if st.button("Test API", use_container_width=True):
            try:
                result = request_json("GET", base_url, "/api/v1/health/ready", read_timeout=5)
                st.success("API reachable")
                if result:
                    with st.expander("Health response"):
                        st.json(result)
            except Exception as exc:
                st.error(f"API connection failed: {exc}")
    with col_health2:
        if st.button("Refresh list", use_container_width=True):
            fetch_documents.clear()
            st.rerun()

    st.divider()
    st.subheader("Upload a document")
    uploaded_file = st.file_uploader(
        "Choose a PDF, TXT, DOCX or MD file",
        type=["pdf", "txt", "docx", "md"],
        accept_multiple_files=False,
        help="Upload one file at a time. The backend performs extraction, chunking and indexing.",
    )
    if st.button(
        "Upload and index",
        type="primary",
        use_container_width=True,
        disabled=uploaded_file is None,
    ):
        try:
            with st.spinner("Uploading and indexing document…"):
                upload_response = request_json(
                    "POST",
                    base_url,
                    "/api/v1/documents/upload",
                    files={
                        "file": (
                            uploaded_file.name,
                            uploaded_file.getvalue(),
                            uploaded_file.type or "application/octet-stream",
                        )
                    },
                    connect_timeout=3,
                    read_timeout=180,
                )
            fetch_documents.clear()
            st.session_state.notice = ("success", f"Uploaded {uploaded_file.name} successfully.")
            st.rerun()
        except Exception as exc:
            st.error(f"Upload failed: {exc}")

    if st.session_state.notice:
        notice_type, notice_text = st.session_state.notice
        if notice_type == "success":
            st.success(notice_text)
        else:
            st.error(notice_text)
        st.session_state.notice = None

    st.divider()
    st.subheader("Your documents")
    try:
        documents = fetch_documents(base_url)
        if not documents:
            st.caption("No documents found yet. Upload a PDF or TXT file above.")
        else:
            st.caption(f"{len(documents)} document(s)")
            for index, document in enumerate(documents):
                name = document_name(document)
                doc_id = document_id(document)
                status = first_value(document, ("status", "processing_status"), "")
                with st.expander(name, expanded=False):
                    if status:
                        st.caption(f"Status: {status}")
                    if doc_id:
                        st.caption(f"ID: {doc_id}")
                    created_at = first_value(document, ("created_at", "uploaded_at"), "")
                    if created_at:
                        st.caption(f"Created: {created_at}")
                    if doc_id:
                        if st.button("Delete document", key=f"delete_doc_{doc_id}_{index}", use_container_width=True):
                            try:
                                with st.spinner(f"Deleting {name}…"):
                                    request_json(
                                        "DELETE",
                                        base_url,
                                        f"/api/v1/documents/{quote(doc_id, safe='')}",
                                        connect_timeout=3,
                                        read_timeout=30,
                                    )
                                fetch_documents.clear()
                                st.session_state.notice = ("success", f"Deleted {name}.")
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Delete failed: {exc}")
    except Exception as exc:
        documents = []
        st.warning(f"Could not load documents: {exc}")

    st.divider()
    st.subheader("Retrieval settings")
    top_k = st.slider(
        "Chunks to retrieve",
        min_value=1,
        max_value=10,
        value=5,
        help="Lower values can reduce generation context and latency, but may miss relevant evidence.",
    )

    if st.button("Clear chat history", use_container_width=True):
        st.session_state.chat_history = []
        st.rerun()


# -----------------------------------------------------------------------------
# Main chat UI
# -----------------------------------------------------------------------------
st.title("Chat with your documents")
st.write("Ask questions in English or Arabic. Answers should be grounded in the uploaded files.")

try:
    current_documents = fetch_documents(base_url)
except Exception:
    current_documents = []

# Document scope filter: the backend must accept `document_id` for this option to work.
doc_options: list[str] = ["All documents"]
doc_label_by_id: dict[str, str] = {}
for doc in current_documents:
    doc_id = document_id(doc)
    if doc_id:
        label = document_name(doc)
        if label in doc_label_by_id.values():
            label = f"{label} ({doc_id[:8]})"
        doc_label_by_id[doc_id] = label
        doc_options.append(doc_id)

filter_col, status_col = st.columns([3, 2])
with filter_col:
    selected_document = st.selectbox(
        "Search scope",
        options=doc_options,
        format_func=lambda value: "All documents" if value == "All documents" else doc_label_by_id.get(value, value),
        help="Select a document to restrict retrieval, if your chat endpoint implements document_id filtering.",
    )
with status_col:
    st.metric("Documents available", len(current_documents))

if not current_documents:
    st.info("Upload a PDF or TXT document from the sidebar to get started.")

# Render previous turns from session state. No network calls are made for prior turns.
for turn_index, message in enumerate(st.session_state.chat_history):
    role = message.get("role", "assistant")
    with st.chat_message(role):
        st.markdown(message.get("content", ""))
        if role == "assistant":
            latency = message.get("latency_seconds")
            if latency is not None:
                st.caption(f"API round-trip: {latency:.2f} sec")
            render_sources(message.get("sources", []), prefix=f"history_{turn_index}")

prompt = st.chat_input("Ask a question about your documents…")
if prompt and prompt.strip():
    clean_prompt = prompt.strip()
    st.session_state.chat_history.append({"role": "user", "content": clean_prompt})

    with st.chat_message("user"):
        st.markdown(clean_prompt)

    with st.chat_message("assistant"):
        started = time.perf_counter()
        try:
            payload: dict[str, Any] = {"question": clean_prompt, "top_k": top_k}
            if selected_document != "All documents":
                payload["document_id"] = selected_document

            with st.spinner("Searching documents and generating an answer…"):
                result = request_json(
                    "POST",
                    base_url,
                    "/api/v1/chat",
                    json=payload,
                    connect_timeout=3,
                    read_timeout=180,
                )
            elapsed = time.perf_counter() - started
            answer = answer_text(result)
            sources = source_list(result)
            st.markdown(answer)
            st.caption(f"API round-trip: {elapsed:.2f} sec")
            render_sources(sources, prefix="latest")
            st.session_state.chat_history.append(
                {
                    "role": "assistant",
                    "content": answer,
                    "sources": sources,
                    "latency_seconds": elapsed,
                }
            )
        except Exception as exc:
            elapsed = time.perf_counter() - started
            error_message = f"I couldn't get a response from DocuMind.\n\n`{exc}`"
            st.error(error_message)
            st.session_state.chat_history.append(
                {
                    "role": "assistant",
                    "content": error_message,
                    "sources": [],
                    "latency_seconds": elapsed,
                }
            )
