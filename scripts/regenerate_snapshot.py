import sys
import os
import sqlite3

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_connection
from academy.sync_manager import SyncManager
from academy.preseason import run_preseason

def regenerate_snapshot():
    print("Regenerating snapshot from latest DB state...")
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    sync_mgr = SyncManager()
    version = sync_mgr.generate_snapshot_and_manifest(cursor)
    
    # We force publish to push to mock_server
    sync_mgr.publish(force_version=version)
    
    print(f"Snapshot v{version} pushed to mock_server successfully.")

if __name__ == "__main__":
    regenerate_snapshot()
