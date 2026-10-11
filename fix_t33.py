import sqlite3
from academy.academy_engine import AcademyEngine
from database import get_connection
from academy.sync_manager import SyncManager

def fix():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Process tournament 33 that failed previously
    print("Processing tournament 33 in AcademyEngine...")
    AcademyEngine().process_tournament(cursor, 33)
    conn.commit()
    print("Processed successfully.")
    
    # Generate Snapshot
    sync_mgr = SyncManager()
    sync_mgr.generate_snapshot_and_manifest(cursor)
    conn.close()
    
    sync_mgr.publish()
    print("Snapshot published successfully.")

if __name__ == "__main__":
    fix()
