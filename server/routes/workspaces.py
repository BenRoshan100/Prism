import chromadb
from fastapi import APIRouter, HTTPException

from server.bm25_index import delete_workspace_index
from server.utils import setup_logger

logger = setup_logger(__name__)
router = APIRouter()

_PROTECTED_WORKSPACES = {"default", "prism"}


def _get_chroma_client():
    return chromadb.PersistentClient(path="./chroma_db")


@router.get("/workspaces")
async def list_workspaces():
    """List all workspaces (one per ChromaDB collection)."""
    try:
        client = _get_chroma_client()
        collections = client.list_collections()
        return {"workspaces": [c.name for c in collections]}
    except Exception as e:
        raise HTTPException(500, f"Failed to list workspaces: {e}")


@router.delete("/workspaces/{workspace_id}")
async def delete_workspace(workspace_id: str):
    """Delete a workspace — removes ChromaDB collection and BM25 index entry."""
    if workspace_id in _PROTECTED_WORKSPACES:
        raise HTTPException(400, f"Cannot delete protected workspace '{workspace_id}'")
    try:
        client = _get_chroma_client()
        client.delete_collection(workspace_id)
        delete_workspace_index(workspace_id)
        logger.info("Deleted workspace: %s", workspace_id)
        return {"deleted": workspace_id}
    except Exception as e:
        raise HTTPException(500, f"Failed to delete workspace '{workspace_id}': {e}")
