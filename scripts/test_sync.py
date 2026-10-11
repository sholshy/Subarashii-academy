import sys
import os
import json
import sqlite3

# Adjust path to find modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_connection
from academy.sync_manager import SyncManager

def run_sync_tests():
    print("=== RUNNING SYNC MANAGER TESTS ===")
    
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    sync_mgr = SyncManager()
    
    # 1. Generate snapshot (simulate finalizing tournament)
    print("\n1. Generating Snapshot...")
    version = sync_mgr.generate_snapshot_and_manifest(cursor)
    
    manifest = sync_mgr._load_manifest()
    print(f"Manifest Status: {manifest['status']} (Expected: PENDING)")
    if manifest['status'] != "PENDING":
        print("FAIL: Status not PENDING after generation.")
        return
        
    # 2. Simulate Internet Failure
    print("\n2. PRUEBA DE FALLO DE INTERNET...")
    success = sync_mgr.publish(simulate_network_error=True)
    manifest = sync_mgr._load_manifest()
    if not success and manifest['status'] == "PENDING":
        print("PASS: Publish failed gracefully. Status is still PENDING.")
    else:
        print("FAIL: Publish should have failed due to network error and kept PENDING state.")
        return
        
    # 3. Simulate Incomplete Upload
    print("\n3. PRUEBA DE PUBLICACIÓN INCOMPLETA (Checksum mismatch)...")
    success = sync_mgr.publish(simulate_incomplete_upload=True)
    manifest = sync_mgr._load_manifest()
    if not success and manifest['status'] == "PENDING":
        print("PASS: Server rejected the incomplete payload. Status is still PENDING.")
    else:
        print("FAIL: Server should have rejected the incomplete upload.")
        return
        
    # 4. Successful Upload
    print("\n4. PRUEBA RECUPERACIÓN (Sincronizar Pendientes)...")
    success = sync_mgr.publish()
    manifest = sync_mgr._load_manifest()
    if success and manifest['status'] == "PUBLISHED":
        print("PASS: Sincronizar pendientes succeeded. Status updated to PUBLISHED.")
    else:
        print(f"FAIL: Expected PUBLISHED, got {manifest['status']}")
        return
        
    # 5. Simulate Stale Publication
    print("\n5. PRUEBA DE PUBLICACIÓN ANTIGUA (Stale)...")
    # Forcing publish of an older version when remote is already on `version`
    stale_version = version - 1
    # First we need a dummy file for the stale version just to avoid missing file error
    dummy_stale_path = os.path.join(sync_mgr.snapshots_dir, f"snapshot_v{stale_version}.json")
    with open(dummy_stale_path, 'w') as f:
        f.write("{}")
        
    success = sync_mgr.publish(force_version=stale_version)
    
    # Check local manifest status (wait, force_version in publish doesn't update local manifest, but it returns False)
    if not success:
        print("PASS: Stale publication was rejected by the server.")
    else:
        print("FAIL: Stale publication was accepted incorrectly.")
        return
        
    print("\n=== ALL TESTS PASSED SUCCESSFULLY ===")
    
if __name__ == "__main__":
    run_sync_tests()
