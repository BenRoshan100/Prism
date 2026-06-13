import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "/api",
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
    timeout: 300000,
  });
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

