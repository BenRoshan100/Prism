import argparse
import shutil
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server.ingest import run_ingestion_pipeline


def main():
    parser = argparse.ArgumentParser(description="Ingest documents into ChromaDB")
    parser.add_argument("--data-dir", type=str, default="data/raw", help="Directory containing documents")
    parser.add_argument("--reset", action="store_true", help="Wipe ChromaDB and re-ingest from scratch")
    args = parser.parse_args()

    if args.reset:
        chroma_path = Path("./chroma_db")
        if chroma_path.exists():
            shutil.rmtree(chroma_path)
            print("ChromaDB wiped.")

    run_ingestion_pipeline(args.data_dir)


if __name__ == "__main__":
    main()
