import sqlite3
from database import get_connection

class StoreManager:
    def __init__(self, data_dir="data"):
        self.conn = get_connection()
        self.cursor = self.conn.cursor()

    def get_stores(self):
        self.cursor.execute("SELECT name FROM stores")
        return [row['name'] for row in self.cursor.fetchall()]

    @property
    def stores(self):
        return self.get_stores()

    def get_active_store(self):
        self.cursor.execute("SELECT name FROM stores WHERE is_active = 1")
        row = self.cursor.fetchone()
        if row:
            return row['name']
        stores = self.get_stores()
        if stores:
            self.set_active_store(stores[0])
            return stores[0]
        else:
            self.add_store("Tienda Principal")
            self.set_active_store("Tienda Principal")
            return "Tienda Principal"

    @property
    def active_store(self):
        return self.get_active_store()

    def add_store(self, store_name):
        store_name = store_name.strip()
        if not store_name:
            raise ValueError("El nombre de la tienda no puede estar vacio.")
        try:
            self.cursor.execute("INSERT INTO stores (name, is_active) VALUES (?, 0)", (store_name,))
            self.conn.commit()
            if not self.get_active_store():
                self.set_active_store(store_name)
        except sqlite3.IntegrityError:
            raise ValueError("La tienda ya existe.")

    def remove_store(self, store_name):
        self.cursor.execute("DELETE FROM stores WHERE name = ?", (store_name,))
        self.conn.commit()
        if self.get_active_store() is None:
            stores = self.get_stores()
            if stores:
                self.set_active_store(stores[0])

    def rename_store(self, old_name, new_name):
        new_name = new_name.strip()
        if not new_name:
            raise ValueError("El nuevo nombre no puede estar vacio.")
        try:
            self.cursor.execute("UPDATE stores SET name = ? WHERE name = ?", (new_name, old_name))
            self.conn.commit()
        except sqlite3.IntegrityError:
            raise ValueError("Ya existe una tienda con ese nombre.")

    def set_active_store(self, store_name):
        if store_name not in self.get_stores():
            raise ValueError("La tienda seleccionada no existe.")
        self.cursor.execute("UPDATE stores SET is_active = 0")
        self.cursor.execute("UPDATE stores SET is_active = 1 WHERE name = ?", (store_name,))
        self.conn.commit()

    def get_active_league_db_path(self):
        return "data/ygo_data.db"
    
    def get_players_db_path(self, store_name=None):
        return "data/ygo_data.db"

    def get_store_stats(self, store_name):
        import os, json
        stats = {'total_tournaments': 0, 'unique_players': 0, 'by_format': {}, 'top_players': []}
        history_dir = os.path.join("data", "history")
        if not os.path.exists(history_dir): return stats
        
        unique_names = set()
        attendance_counts = {}
        
        for file in os.listdir(history_dir):
            if not file.endswith(".json"): continue
            try:
                with open(os.path.join(history_dir, file), "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                ui_data = data.get("ui", {})
                file_store = ui_data.get("store_name")
                
                if not file_store:
                    file_store = ui_data.get("store") or self.get_active_store()
                    
                if file_store != store_name: continue
                
                stats['total_tournaments'] += 1
                fmt = ui_data.get("format") or data.get("manager", {}).get("format_name") or "GOAT"
                stats['by_format'][fmt] = stats['by_format'].get(fmt, 0) + 1
                
                players = data.get("manager", {}).get("players", [])
                for p in players:
                    pname = p.get("name", "").strip()
                    if pname:
                        unique_names.add(pname)
                        attendance_counts[pname] = attendance_counts.get(pname, 0) + 1
            except:
                pass
                
        stats['unique_players'] = len(unique_names)
        sorted_players = sorted(attendance_counts.items(), key=lambda x: x[1], reverse=True)
        stats['top_players'] = [{'name': name, 'count': count} for name, count in sorted_players[:3]]
            
        return stats
        
    def get_attendance_timeline(self, store_name):
        import os, json
        timeline = []
        
        # 1. Intentar consultar directamente desde la base de datos SQLite (fuente de verdad oficial)
        try:
            from database import get_connection
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT t.id, t.date, t.format_name,
                       (SELECT COUNT(*) FROM tournament_results tr WHERE tr.tournament_id = t.id) as result_players
                FROM tournaments t
                JOIN stores s ON s.id = t.store_id
                WHERE s.name = ?
                  AND t.id NOT IN (SELECT DISTINCT tournament_id FROM tournament_matches WHERE result_text = 'Pendiente')
                ORDER BY
                    CASE WHEN substr(t.date, 3, 1) = '-' AND substr(t.date, 6, 1) = '-'
                         THEN '20' || substr(t.date, 7, 2) || '-' || substr(t.date, 4, 2) || '-' || substr(t.date, 1, 2)
                         ELSE t.date END ASC,
                    t.id ASC
            """, (store_name,))
            rows = cur.fetchall()
            if rows:
                for r in rows:
                    cnt = r['result_players'] if r['result_players'] > 0 else 0
                    if cnt == 0:
                        cur.execute("""
                            SELECT COUNT(DISTINCT pid) as cnt FROM (
                                SELECT p1_id as pid FROM tournament_matches WHERE tournament_id = ? AND p1_id IS NOT NULL
                                UNION
                                SELECT p2_id as pid FROM tournament_matches WHERE tournament_id = ? AND p2_id IS NOT NULL
                            )
                        """, (r['id'], r['id']))
                        cnt = cur.fetchone()['cnt']
                    timeline.append({
                        "date": r['date'],
                        "format_name": r['format_name'],
                        "player_count": cnt
                    })
                conn.close()
                return timeline
            conn.close()
        except Exception:
            pass

        # 2. Fallback a archivos JSON en data/history
        history_dir = os.path.join("data", "history")
        if not os.path.exists(history_dir): return timeline
        
        for file in os.listdir(history_dir):
            if not file.endswith(".json"): continue
            try:
                filepath = os.path.join(history_dir, file)
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                ui_data = data.get("ui", {})
                file_store = ui_data.get("store_name") or ui_data.get("store") or self.get_active_store()
                if file_store != store_name: continue
                
                date_str = ui_data.get("date", "Desconocido")
                fmt = ui_data.get("format") or data.get("manager", {}).get("format_name") or "GOAT"
                players = data.get("manager", {}).get("players", [])
                
                timeline.append({
                    "date": date_str,
                    "format_name": fmt,
                    "player_count": len(players),
                    "_mtime": os.path.getmtime(filepath)
                })
            except:
                pass
                
        timeline.sort(key=lambda x: x["_mtime"])
        for item in timeline:
            del item["_mtime"]
            
        return timeline

    def get_monthly_profits(self, store_name):
        import os, json
        results = []
        history_dir = os.path.join("data", "history")
        if not os.path.exists(history_dir): return results
        
        from datetime import datetime
        def get_month_str(date_str):
            for fmt_str in ("%Y-%m-%d", "%d-%m-%y", "%d/%m/%Y", "%d-%m-%Y", "%y-%m-%d"):
                try:
                    dt = datetime.strptime(date_str, fmt_str)
                    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
                    return f"{meses[dt.month - 1]} {dt.year}"
                except ValueError:
                    pass
            return "Desconocido"
            
        profits_data = []
        for file in os.listdir(history_dir):
            if not file.endswith(".json"): continue
            try:
                filepath = os.path.join(history_dir, file)
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                ui_data = data.get("ui", {})
                file_store = ui_data.get("store_name") or ui_data.get("store") or self.get_active_store()
                if file_store != store_name: continue
                
                date_str = ui_data.get("date", "Desconocido")
                fmt = ui_data.get("format") or data.get("manager", {}).get("format_name") or "GOAT"
                profit = data.get("manager", {}).get("tournament_profit", 0.0)
                
                profits_data.append({
                    "month": get_month_str(date_str),
                    "format_name": fmt,
                    "profit": profit,
                    "_mtime": os.path.getmtime(filepath)
                })
            except:
                pass
                
        profits_data.sort(key=lambda x: x["_mtime"])
        for item in profits_data:
            del item["_mtime"]
            results.append(item)
            
        return results
