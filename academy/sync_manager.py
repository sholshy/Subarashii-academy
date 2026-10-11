import os
import json
import sqlite3
import hashlib
import shutil
from datetime import datetime

from database import migrate_academy_schema
from academy.ranking_explainer import explain_player

class SyncManager:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.sync_dir = os.path.join(self.base_dir, "data", "academy", "sync")
        self.snapshots_dir = os.path.join(self.sync_dir, "snapshots")
        self.manifest_path = os.path.join(self.sync_dir, "manifest.json")
        self.mock_server_dir = os.path.join(self.base_dir, "mock_server", "public_api")
        
        os.makedirs(self.snapshots_dir, exist_ok=True)
        os.makedirs(self.mock_server_dir, exist_ok=True)
        
        # Initialize manifest if it doesn't exist
        if not os.path.exists(self.manifest_path):
            self._save_manifest({
                "current_version": 0,
                "latest_snapshot": None,
                "status": "NONE",
                "timestamp": None,
                "checksum": None
            })

    def _load_manifest(self):
        with open(self.manifest_path, 'r', encoding='utf-8') as f:
            return json.load(f)
            
    def _save_manifest(self, data):
        with open(self.manifest_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)

    def _compute_checksum(self, filepath):
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _generate_slug(self, name, seen):
        import re
        base = re.sub(r'[^a-zA-Z0-9 ]', '', name).lower().strip()
        parts = base.split()
        if len(parts) >= 2:
            slug_base = f"{parts[0][0]}{parts[-1]}"
        elif len(parts) == 1:
            slug_base = parts[0]
        else:
            slug_base = "unknown"
            
        slug = slug_base
        counter = 1
        while slug in seen:
            slug = f"{slug_base}{counter}"
            counter += 1
        seen.add(slug)
        return slug

    def generate_snapshot_and_manifest(self, cursor):
        """
        Extracts data from the DB, creates a JSON snapshot, and updates manifest to PENDING.
        """
        if hasattr(cursor, 'cursor'):
            cursor = cursor.cursor()
        migrate_academy_schema(cursor)
        # 1. Fetch Leaderboard & Enriched Stats
        cursor.execute("""
            SELECT a.id as profile_id, p.id as player_id, p.name, 
                   a.current_rating, a.highest_rating, a.dorm, 
                   a.xp, a.level, a.matches_played, a.wins, a.losses,
                   a.previous_rank
            FROM academy_profiles a
            JOIN players p ON a.player_id = p.id
            WHERE a.format_name = 'GLOBAL'
            ORDER BY a.current_rating DESC, a.xp DESC
        """)
        
        leaderboard = []
        slugs_seen = set()
        
        profiles_data = cursor.fetchall()
        for rank, row in enumerate(profiles_data, 1):
            mp = row['matches_played']
            wins = row['wins']
            wr = round((wins / mp * 100), 1) if mp > 0 else 0.0
            
            slug = self._generate_slug(row['name'], slugs_seen)
            
            prev_rank = row['previous_rank']
            if not prev_rank or prev_rank == 0:
                trend = "="
            elif rank < prev_rank:
                trend = "up"
            elif rank > prev_rank:
                trend = "down"
            else:
                trend = "="
            
            leaderboard.append({
                "rank": rank,
                "previous_rank": prev_rank,
                "trend": trend,
                "profile_id": row['profile_id'],
                "player_id": row['player_id'],
                "name": row['name'],
                "slug": slug,
                "dorm": row['dorm'],
                "level": row['level'],
                "xp": row['xp'],
                "current_rating": row['current_rating'],
                "highest_rating": row['highest_rating'],
                "matches_played": mp,
                "wins": wins,
                "losses": row['losses'],
                "win_rate": wr
            })
            
        # 2. Fetch Achievements & Missions globally
        cursor.execute("SELECT academy_profile_id, achievement_id, unlocked_at FROM academy_achievements")
        all_achievements = {}
        for r in cursor.fetchall():
            pid = r['academy_profile_id']
            if pid not in all_achievements: all_achievements[pid] = []
            all_achievements[pid].append({"id": r['achievement_id'], "date": r['unlocked_at']})
            
        cursor.execute("SELECT academy_profile_id, mission_id, progress, completed FROM academy_missions")
        all_missions = {}
        for r in cursor.fetchall():
            pid = r['academy_profile_id']
            if pid not in all_missions: all_missions[pid] = []
            all_missions[pid].append({
                "id": r['mission_id'], 
                "progress": r['progress'], 
                "completed": r['completed']
            })
            
        # 2.1 Fetch Rating History globally
        cursor.execute("SELECT academy_profile_id, match_id, new_rating, rating_change, timestamp FROM academy_rating_history ORDER BY id ASC")
        all_history = {}
        for r in cursor.fetchall():
            pid = r['academy_profile_id']
            if pid not in all_history: all_history[pid] = []
            all_history[pid].append({
                "match_id": r['match_id'],
                "new_rating": r['new_rating'],
                "rating_change": r['rating_change'],
                "timestamp": r['timestamp']
            })
            
        # 2.2 Fetch Format Stats (derived directly from processed tournament matches per format)
        cursor.execute("""
            SELECT a.player_id, t.format_name,
                   COUNT(*) AS matches_played,
                   SUM(CASE WHEN h.result = 1.0 THEN 1 ELSE 0 END) AS wins,
                   SUM(CASE WHEN h.result = 0.0 THEN 1 ELSE 0 END) AS losses
            FROM academy_rating_history h
            JOIN academy_profiles a ON a.id = h.academy_profile_id
            JOIN tournament_matches tm ON tm.id = h.match_id
            JOIN tournaments t ON t.id = tm.tournament_id
            WHERE a.format_name = 'GLOBAL' AND h.reason = 'MATCH_RESULT'
            GROUP BY a.player_id, t.format_name
        """)
        all_formats = {}
        for r in cursor.fetchall():
            pid = r['player_id']
            if pid not in all_formats: all_formats[pid] = {}
            all_formats[pid][r['format_name']] = {
                "matches_played": r['matches_played'],
                "wins": r['wins'],
                "losses": r['losses']
            }
            
        # 2.3 Fetch Tournaments (only completed tournaments processed in Academy)
        cursor.execute("""
            SELECT t.id, t.date, t.format_name, lp.player_id, tr.match_points, tr.placement_points
            FROM tournaments t
            JOIN tournament_results tr ON t.id = tr.tournament_id
            JOIN league_profiles lp ON tr.league_profile_id = lp.id
            WHERE t.id NOT IN (SELECT DISTINCT tournament_id FROM tournament_matches WHERE result_text = 'Pendiente')
            ORDER BY
                CASE WHEN substr(t.date, 3, 1) = '-' AND substr(t.date, 6, 1) = '-'
                     THEN '20' || substr(t.date, 7, 2) || '-' || substr(t.date, 4, 2) || '-' || substr(t.date, 1, 2)
                     ELSE t.date END DESC,
                t.id DESC
        """)
        all_tournaments = {}
        for r in cursor.fetchall():
            pid = r['player_id']
            if pid not in all_tournaments: all_tournaments[pid] = []
            all_tournaments[pid].append({
                "tournament_id": r['id'],
                "date": r['date'],
                "format_name": r['format_name'],
                "points": r['match_points'] + r['placement_points'],
                "rank": 1 if r['placement_points'] == 10 else (2 if r['placement_points'] == 5 else 0)
            })
            
        # 3. Assemble Snapshot
        manifest = self._load_manifest()
        new_version = manifest["current_version"] + 1
        timestamp = datetime.now().isoformat()
        
        # 2.4 Explicación del ranking (duelos, XP por origen, desempate, confiabilidad)
        explanations = {}
        for row in profiles_data:
            exp = explain_player(cursor, row['player_id'])
            if exp:
                explanations[row['profile_id']] = exp

        # 2.5 Temporadas (historial y temporada activa)
        cursor.execute("SELECT * FROM academy_seasons ORDER BY number ASC")
        all_seasons_raw = [dict(r) for r in cursor.fetchall()]
        
        from academy.season_manager import SeasonManager
        sm = SeasonManager()
        season_metrics = sm.get_season_metrics(cursor)
        
        seasons_data = {
            "all_seasons": all_seasons_raw,
            "active_metrics": {
                "season": season_metrics['season'],
                "days_elapsed": season_metrics['days_elapsed'],
                "tournaments_count": season_metrics['tournaments_count'],
                "total_matches": season_metrics['total_matches'],
                "active_players": season_metrics['active_players'],
                "first_date": season_metrics['first_tournament_date'],
                "last_date": season_metrics['last_tournament_date'],
                "progress_text": season_metrics['progress_text'],
                "is_ready_to_close": season_metrics['is_ready_to_close']
            }
        }

        from calendar_manager import CalendarManager
        cm = CalendarManager(cursor.connection if hasattr(cursor, 'connection') else None)
        calendar_events = cm.get_scheduled_tournaments(include_finished=True)

        snapshot = {
            "version": new_version,
            "generated_at": timestamp,
            "player_count": len(leaderboard),
            "leaderboard": leaderboard,
            "achievements_map": all_achievements,
            "missions_map": all_missions,
            "rating_history_map": all_history,
            "format_stats_map": all_formats,
            "tournaments_map": all_tournaments,
            "explanations_map": explanations,
            "seasons_data": seasons_data,
            "calendar": calendar_events
        }

        # 4. Save Snapshot File
        filename = f"snapshot_v{new_version}.json"
        filepath = os.path.join(self.snapshots_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, ensure_ascii=False)
            
        checksum = self._compute_checksum(filepath)
        
        # 5. Update Manifest
        manifest["current_version"] = new_version
        manifest["latest_snapshot"] = filename
        manifest["status"] = "PENDING"
        manifest["timestamp"] = timestamp
        manifest["checksum"] = checksum
        self._save_manifest(manifest)
        
        print(f"[SyncManager] Snapshot v{new_version} generated. Status: PENDING.")
        return new_version

    def publish(self, simulate_network_error=False, simulate_incomplete_upload=False, force_version=None):
        """
        Attempts to push the PENDING snapshot to the remote server (mock_server).
        Returns True if successful, False otherwise.
        """
        manifest = self._load_manifest()
        
        if manifest["status"] == "PUBLISHED" and force_version is None:
            print("[SyncManager] No pending updates. Already PUBLISHED.")
            return True
            
        if simulate_network_error:
            print("[SyncManager] NETWORK ERROR: Failed to connect to Duelorapido.cl")
            # State remains PENDING
            return False
            
        # Remote validation phase
        remote_manifest_path = os.path.join(self.mock_server_dir, "manifest.json")
        remote_version = 0
        if os.path.exists(remote_manifest_path):
            with open(remote_manifest_path, 'r', encoding='utf-8') as f:
                rm = json.load(f)
                remote_version = rm.get("current_version", 0)
                
        version_to_publish = force_version if force_version is not None else manifest["current_version"]
        
        if version_to_publish <= remote_version:
            print(f"[SyncManager] REJECTED_STALE: Local version {version_to_publish} is not newer than remote {remote_version}.")
            if force_version is None:
                manifest["status"] = "REJECTED_STALE"
                self._save_manifest(manifest)
            return False
            
        snapshot_filename = f"snapshot_v{version_to_publish}.json"
        local_snapshot_path = os.path.join(self.snapshots_dir, snapshot_filename)
        remote_snapshot_path = os.path.join(self.mock_server_dir, snapshot_filename)
        
        if not os.path.exists(local_snapshot_path):
            print("[SyncManager] ERROR: Local snapshot file missing.")
            return False
            
        # Simulate Upload
        print(f"[SyncManager] Uploading {snapshot_filename} to remote...")
        if simulate_incomplete_upload:
            print("[SyncManager] UPLOAD ERROR: File corrupted during transfer.")
            # We copy but corrupt it
            with open(remote_snapshot_path, "w") as f:
                f.write("INCOMPLETE_DATA_{" + "0"*1000)
        else:
            shutil.copy2(local_snapshot_path, remote_snapshot_path)
            
        # Remote Checksum Validation
        remote_checksum = self._compute_checksum(remote_snapshot_path)
        expected_checksum = self._compute_checksum(local_snapshot_path) # the real one
        
        if remote_checksum != expected_checksum:
            print("[SyncManager] REMOTE VALIDATION FAILED: Checksum mismatch (Incomplete upload).")
            # State remains PENDING locally
            # Remote manifest is NOT updated.
            return False
            
        # Upload successful, update remote manifest
        print("[SyncManager] Upload successful. Updating remote manifest...")
        with open(remote_manifest_path, 'w', encoding='utf-8') as f:
            # We construct a remote manifest representation
            json.dump({
                "current_version": version_to_publish,
                "latest_snapshot": snapshot_filename,
                "timestamp": datetime.now().isoformat(),
                "checksum": expected_checksum
            }, f, indent=4)
            
        # Update local manifest
        if not force_version:
            manifest["status"] = "PUBLISHED"
            self._save_manifest(manifest)
            print("[SyncManager] Local manifest updated to PUBLISHED.")
            
        return True
