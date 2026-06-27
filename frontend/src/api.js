import axios from "axios";

const API_BASE = import.meta.env.VITE_API_URL || "/api";

const api = axios.create({
  baseURL: API_BASE,
});

export async function sendMessage(question, webSearch = false, workspaceId = "default") {
  const { data } = await api.post(`/chat?workspace=${encodeURIComponent(workspaceId)}`, {
    question,
    web_search: webSearch,
  });
  return data;
}

export async function clearMemory() {
  const { data } = await api.delete("/chat/memory");
  return data;
}

export async function getSessionEvalLog() {
  const { data } = await api.get("/eval/session");
  return data;
}

export async function runPrecisionEval() {
  const { data } = await api.post("/eval/precision");
  return data;
}

export async function uploadFiles(fileList, workspaceId = "default") {
  const formData = new FormData();
  for (const file of fileList) {
    formData.append("files", file);
  }
  formData.append("workspace", workspaceId);
  const { data } = await api.post("/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 30000,
  });
  return data;
}

export async function getUploadStatus(jobId) {
  const { data } = await api.get(`/upload/status/${jobId}`);
  return data;
}

export async function getDocuments(workspaceId = "default") {
  const { data } = await api.get(`/documents?workspace=${encodeURIComponent(workspaceId)}`);
  return data;
}

export async function uploadUrl(url, workspaceId = "default") {
  const { data } = await api.post("/upload/url", { url, workspace: workspaceId }, { timeout: 60000 });
  return data;
}

export async function getWorkspaces() {
  const { data } = await api.get("/workspaces");
  return data;
}

export async function deleteWorkspace(workspaceId) {
  const { data } = await api.delete(`/workspaces/${encodeURIComponent(workspaceId)}`);
  return data;
}

export async function deleteDocument(filename, workspaceId = "default") {
  const { data } = await api.delete(
    `/documents/${encodeURIComponent(filename)}?workspace=${encodeURIComponent(workspaceId)}`
  );
  return data;
}

export async function streamChat(question, workspaceId = "default", { onToken, onDone, onError }, filterDocs = null) {
  let response;
  try {
    response = await fetch(
      `${API_BASE}/chat?workspace=${encodeURIComponent(workspaceId)}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question,
          filter_docs: filterDocs && filterDocs.length > 0 ? filterDocs : null,
        }),
      }
    );
  } catch (err) {
    onError(err.message || "Network error");
    return;
  }

  if (!response.ok) {
    const text = await response.text().catch(() => "");
    onError(text || `HTTP ${response.status}`);
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? ""; // keep incomplete line
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        try {
          const event = JSON.parse(line.slice(6));
          if (event.type === "token") onToken(event.content);
          else if (event.type === "done") onDone(event);
          else if (event.type === "error") onError(event.message ?? "Unknown error");
        } catch {
          // malformed SSE line — skip
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

