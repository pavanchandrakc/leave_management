import os
import sys

# Ensure the backend directory is in sys.path
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from src.server import mcp, init_db

if __name__ == "__main__":
    init_db()
    mcp.run(transport="stdio")
