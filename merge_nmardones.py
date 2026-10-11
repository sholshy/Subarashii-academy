from database import merge_players_db, init_db
from academy.sync_manager import SyncManager
from database import get_connection

def fix():
    print("Merging players...")
    merge_players_db(29, [60, 61])
    print("Done merging.")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Generate Snapshot
    sync_mgr = SyncManager()
    sync_mgr.generate_snapshot_and_manifest(cursor)
    conn.close()
    
    sync_mgr.publish()
    print("Snapshot published successfully.")

if __name__ == "__main__":
    fix()
