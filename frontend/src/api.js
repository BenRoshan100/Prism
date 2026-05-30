import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "/api",
});

export async function sendMessage(question, webSearch = false) {
  const { data } = await api.post("/chat", { question, web_search: webSearch });
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

export async function uploadFiles(fileList) {
  const formData = new FormData();
  for (const file of fileList) {
    formData.append("files", file);
  }
  const { data } = await api.post("/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 300000,
  });
  return data;
}

export async function getDocuments() {
  const { data } = await api.get("/documents");
  return data;
}

export async function deleteDocument(filename) {
  const { data } = await api.delete(`/documents/${encodeURIComponent(filename)}`);
  return data;
}

