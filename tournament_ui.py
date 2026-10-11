import tkinter as tk
from tkinter import ttk, filedialog
import customtkinter as ctk
import custom_alerts as messagebox
from tournament_manager import TournamentManager
from tournament_graphics import generate_pairings_image, generate_standings_image
from league_manager import LeagueManager
from store_manager import StoreManager
from datetime import datetime
import csv
import ctypes
import io
import json
import os
import tempfile
import time
from urllib.parse import quote
import webbrowser
import winsound
import pyttsx3
import threading
from remote_sync_client import RemoteSyncClient

UI_FONT = ("Roboto", 13)
UI_FONT_BIG = ("Orbitron Black", 24)
UI_FONT_SMALL = ("Roboto", 11)

class TournamentUI(ctk.CTkFrame):
    def __init__(self, parent, go_back_callback):
        super().__init__(parent, fg_color="transparent")
        self.go_back_callback = go_back_callback
        self.manager = TournamentManager()
        self.remote_sync = RemoteSyncClient()
        self.time_left = 50 * 60
        self.round_minutes = 50
        self.timer_running = False
        self.timer_job = None
        self.timer_deadline = None
        self.last_timer_autosave = None
        self.timer_warnings_spoken = set()
        self.store_manager = StoreManager()
        self.db_path = self.store_manager.get_players_db_path()
        self.autosave_path = os.path.abspath(os.path.join("data", "tournament_autosave.json"))
        self.exported_to_league = False
        self.players_db = {}
        self.current_scheduled_id = None
        self.active_room_code = None
        self._setup_poll_active = False
        self._setup_poll_job = None
        self._tournament_already_published = False
        self._last_saved_history_filename = None
        self._current_saved_tournament_id = None
        self.date_var = tk.StringVar(value=datetime.now().strftime("%d-%m-%y"))
        self.load_db()
        
        self.setup_ui()
        
    def load_db(self):
        from database import get_connection
        self.conn = get_connection()
        self.cursor = self.conn.cursor()
        self.players_db = {}
        self.cursor.execute("SELECT id, konami_id, name, phone, email FROM players")
        for row in self.cursor.fetchall():
            db_id = row['id']
            self.players_db[db_id] = {
                "name": row['name'], 
                "konami_id": row['konami_id'] or "", 
                "phone": row['phone'] or "", 
                "email": row['email'] or ""
            }
                        
    def refresh_db_listbox(self, keep_position=True):
        if hasattr(self, 'db_listbox') and self.db_listbox.winfo_exists():
            top_fraction = self.db_listbox.yview()[0] if keep_position else 0
            selected_items = [self.db_listbox.get(i) for i in self.db_listbox.curselection()]

            self.db_listbox.delete(0, tk.END)
            sorted_items = sorted(self.players_db.items(), key=lambda x: x[1]['name'].lower())
            for db_id, data in sorted_items:
                k_text = data['konami_id'] if data['konami_id'] else "Sin ID"
                self.db_listbox.insert(tk.END, f"{data['name']} ({k_text}) [{db_id}]")

            if keep_position:
                self.db_listbox.yview_moveto(top_fraction)
                for index in range(self.db_listbox.size()):
                    if self.db_listbox.get(index) in selected_items:
                        self.db_listbox.selection_set(index)
                
    def setup_ui(self):
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", pady=10)
        
        back_btn = ctk.CTkButton(header_frame, text="< VOLVER AL MENÚ", command=self.go_back_callback, font=UI_FONT)
        back_btn.pack(side="left", padx=20)
        
        title = ctk.CTkLabel(header_frame, text="YGO Tournament Manager", font=UI_FONT_BIG, text_color="#60a5fa")
        title.pack(side="left", expand=True)
        
        self.audio_muted = False
        self.mute_btn = ctk.CTkButton(header_frame, text="🔊", command=self.toggle_audio, font=("Segoe UI Emoji", 24), width=40, fg_color="transparent", hover_color="#0f172a")
        self.mute_btn.pack(side="right", padx=20)
        
        self.launch_sched_btn = ctk.CTkButton(
            header_frame, text="📅 Lanzar Programado", command=self.open_launch_scheduled_dialog,
            font=UI_FONT_SMALL, fg_color="#38bdf8", hover_color="#0284c7", text_color="#0f172a", width=160
        )
        self.launch_sched_btn.pack(side="right", padx=(0, 10))
        
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True, padx=20, pady=10)

        if self.try_restore_autosave():
            if self.manager.status == "finished":
                self.show_standings_view()
            elif self.manager.status == "running":
                self.show_round_view()
            else:
                self.show_setup_view()
        else:
            self.show_setup_view()

    def try_restore_autosave(self):
        if not os.path.exists(self.autosave_path):
            return False

        try:
            with open(self.autosave_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception as e:
            messagebox.showwarning("Respaldo dañado", f"No se pudo leer el respaldo temporal del torneo:\n{e}")
            return False

        saved_at = payload.get("saved_at", "fecha desconocida")
        player_count = len(payload.get("manager", {}).get("players", []))
        if not messagebox.askyesno(
            "Recuperar torneo",
            f"Se encontró un torneo temporal guardado ({player_count} jugadores, guardado: {saved_at}).\n¿Quieres recuperarlo?"
        ):
            self.clear_autosave()
            return False

        try:
            self.manager = TournamentManager.from_dict(payload.get("manager", {}))
            ui_state = payload.get("ui", {})
            self.time_left = ui_state.get("time_left", self.time_left)
            self.round_minutes = ui_state.get("round_minutes", self.round_minutes)
            self.timer_running = False
            self.exported_to_league = ui_state.get("exported_to_league", False)
            self.date_var.set(ui_state.get("date", self.date_var.get()))
            return True
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo recuperar el torneo temporal:\n{e}")
            return False

    def autosave_tournament(self):
        if not self.manager.players and self.manager.status == "setup":
            self.clear_autosave()
            return

        self.sync_active_room()

        from store_manager import StoreManager
        payload = {
            "version": 1,
            "saved_at": datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
            "manager": self.manager.to_dict(),
            "ui": {
                "time_left": self.time_left,
                "round_minutes": getattr(self, "round_minutes", 50),
                "exported_to_league": self.exported_to_league,
                "date": self.date_var.get() if hasattr(self, "date_var") else datetime.now().strftime("%d-%m-%y"),
                "store_name": StoreManager().get_active_store()
            },
        }

        os.makedirs(os.path.dirname(self.autosave_path), exist_ok=True)
        fd, temp_path = tempfile.mkstemp(prefix="tournament_autosave_", suffix=".json", dir=os.path.dirname(self.autosave_path))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            os.replace(temp_path, self.autosave_path)
        except Exception as e:
            try:
                os.remove(temp_path)
            except OSError:
                pass
            print("Error saving tournament autosave:", e)

    def clear_autosave(self):
        try:
            if os.path.exists(self.autosave_path):
                os.remove(self.autosave_path)
        except OSError as e:
            print("Error clearing tournament autosave:", e)

    def sync_active_room(self, status: str = None):
        if getattr(self, 'active_room_code', None):
            try:
                from tournament_room_manager import TournamentRoomManager
                time_val = getattr(self, 'time_left', None)
                running_val = getattr(self, 'timer_running', False)
                TournamentRoomManager().sync_tournament_to_room(
                    self.active_room_code, self.manager, time_left=time_val, timer_running=running_val
                )
            except Exception as e:
                print("[TournamentUI] Error syncing to local room:", e)

            # Sincronización con hosting remoto si está activada
            if getattr(self, 'remote_sync', None) and self.remote_sync.enabled:
                def _do_remote_sync():
                    try:
                        matches_data = []
                        for idx, m in enumerate(self.manager.get_current_matches(), 1):
                            matches_data.append({
                                "table": idx,
                                "p1": m.p1.name if m.p1 else "BYE",
                                "p2": m.p2.name if m.p2 else "BYE",
                                "reported": m.reported,
                                "result_text": m.result_text,
                                "is_bye": (m.p1 is None or m.p2 is None)
                            })
                        standings_data = []
                        try:
                            _std = self.manager.get_standings()
                            _rkd = self.manager.get_ranked_standings()
                            _nts = self.manager.get_tiebreaker_notes(_std)
                            for rank, p in _rkd:
                                note_txt = self.friendly_tiebreaker_note(_nts.get(p, "")) if hasattr(self, 'friendly_tiebreaker_note') else ""
                                standings_data.append({
                                    "rank": rank,
                                    "name": p.name,
                                    "points": p.points,
                                    "omw": f"{getattr(p, '_omw', 0.3333):.3f}",
                                    "oomw": f"{getattr(p, '_oomw', 0.3333):.3f}",
                                    "note": note_txt,
                                    "matches_played": p.matches_played
                                })
                        except Exception:
                            for rank, p in self.manager.get_ranked_standings():
                                standings_data.append({
                                    "rank": rank,
                                    "name": p.name,
                                    "points": p.points,
                                    "omw": f"{getattr(p, '_omw', 0.3333):.3f}",
                                    "oomw": f"{getattr(p, '_oomw', 0.3333):.3f}",
                                    "note": "",
                                    "matches_played": p.matches_played
                                })
                        timer_info = {
                            "time_left": getattr(self, 'time_left', 0),
                            "duration_secs": getattr(self, 'round_minutes', 50) * 60,
                            "status": "running" if getattr(self, 'timer_running', False) else "paused"
                        }
                        title = f"Torneo {self.manager.format_name} ({getattr(self, 'date_var', tk.StringVar()).get()})"
                        status_val = "RUNNING" if getattr(self.manager, 'current_round', 0) > 0 else "LOBBY"
                        if getattr(self.manager, 'status', '') == "finished":
                            status_val = "FINISHED"
                        if status:
                            status_val = status

                        self.remote_sync.sync_room_state(
                            room_code=self.active_room_code,
                            title=title,
                            current_round=self.manager.current_round,
                            pairings=matches_data,
                            standings=standings_data,
                            timer_info=timer_info,
                            status=status_val,
                            format_name=getattr(self.manager, 'format_name', 'EDISON')
                        )
                    except Exception as err:
                        print("[TournamentUI] Error syncing to cloud hosting:", err)
                threading.Thread(target=_do_remote_sync, daemon=True).start()

    def ensure_active_room(self):
        """Asegura que exista una sala interactiva activa para este torneo."""
        try:
            from tournament_room_manager import TournamentRoomManager
            trm = TournamentRoomManager()
            fmt = self.format_var.get() if hasattr(self, 'format_var') else "GOAT"
            date_str = self.date_var.get() if hasattr(self, 'date_var') else datetime.now().strftime("%d-%m-%y")
            sched_id = getattr(self, 'current_scheduled_id', None)
            title = f"Torneo {fmt} ({date_str})"
            room = trm.create_or_get_room(title=title, format_name=fmt, scheduled_id=sched_id, room_code=getattr(self, 'active_room_code', None))
            self.active_room_code = room['room_code']
            return self.active_room_code
        except Exception as e:
            print("[TournamentUI] Error ensuring active room:", e)
            return getattr(self, 'active_room_code', None)

    def sync_room_players(self, notify_if_none=False):
        """
        Sincroniza los jugadores registrados en la sala (desde teléfonos o web)
        hacia la base de datos local SQLite y la lista de inscritos del torneo.
        """
        try:
            room_code = self.ensure_active_room()
            if not room_code:
                return 0

            from tournament_room_manager import TournamentRoomManager
            trm = TournamentRoomManager()

            # 1. Si la sincronización en la nube está activa, consultar check-ins de Render
            if getattr(self, 'remote_sync', None) and self.remote_sync.enabled:
                try:
                    ok, cloud_events = self.remote_sync.fetch_room_events(room_code)
                    if ok and cloud_events and "players" in cloud_events:
                        for cp in cloud_events["players"]:
                            trm.register_player(
                                room_code=room_code,
                                player_name=cp.get("player_name", ""),
                                konami_id=cp.get("konami_id", "") or "",
                                deck_archetype=cp.get("deck_archetype", "") or "",
                                session_token=cp.get("session_token", "") or ""
                            )
                except Exception as ex_cloud:
                    print(f"[TournamentUI] Error fetching room events from cloud: {ex_cloud}")

            # 2. Obtener lista completa de jugadores registrados en la sala local
            room_players = trm.get_room_players(room_code)
            if not room_players:
                if notify_if_none:
                    self.after(0, lambda: messagebox.showinfo("Información", "Aún no hay jugadores registrados en la sala interactiva."))
                return 0

            from utils import normalize_player_name
            from tournament_manager import Player

            existing_names = {p.name.strip().lower() for p in self.manager.players}
            added_to_tournament = 0
            db_updated = False

            for p in room_players:
                p_name = p.get('player_name', '').strip()
                if not p_name:
                    continue
                p_kid = (p.get('konami_id') or '').strip()

                # Guardar o asegurar que exista en la base de datos local SQLite players
                slug = normalize_player_name(p_name)
                try:
                    if p_kid:
                        self.cursor.execute("SELECT id, name FROM players WHERE konami_id=?", (p_kid,))
                    else:
                        self.cursor.execute("SELECT id, name FROM players WHERE slug=?", (slug,))
                    row = self.cursor.fetchone()
                    if not row:
                        self.cursor.execute(
                            "INSERT INTO players (konami_id, name, slug) VALUES (?, ?, ?)",
                            (p_kid or None, p_name, slug)
                        )
                        self.conn.commit()
                        db_updated = True
                except Exception as ex_sql:
                    print(f"[TournamentUI] Error persisting room player to DB: {ex_sql}")

                # Añadir al torneo en curso si aún no está en la lista de inscritos
                if p_name.lower() not in existing_names:
                    new_p = Player(name=p_name, konami_id=p_kid, phone='', email='', paid=True)
                    self.manager.players.append(new_p)
                    existing_names.add(p_name.lower())
                    added_to_tournament += 1

            if db_updated:
                self.after(0, self.load_db)
                self.after(0, self.refresh_db_listbox)

            if added_to_tournament > 0:
                self.after(0, self.update_player_list)
                self.autosave_tournament()
                self.sync_active_room()
                if notify_if_none:
                    self.after(0, lambda n=added_to_tournament: messagebox.showinfo(
                        "Sincronización Exitosa", f"¡Se añadieron {n} nuevo(s) jugador(es) desde la sala al torneo!"
                    ))
            elif notify_if_none:
                self.after(0, lambda: messagebox.showinfo(
                    "Sin Cambios", "Todos los jugadores de la sala interactiva ya están inscritos en el torneo."
                ))

            return added_to_tournament

        except Exception as e:
            print(f"[TournamentUI] Error in sync_room_players: {e}")
            return 0

    def manual_sync_room_players(self):
        threading.Thread(target=lambda: self.sync_room_players(notify_if_none=True), daemon=True).start()

    def start_setup_room_poll(self):
        self._setup_poll_active = True
        self._poll_setup_room()

    def stop_setup_room_poll(self):
        self._setup_poll_active = False
        if getattr(self, '_setup_poll_job', None):
            try:
                self.after_cancel(self._setup_poll_job)
            except Exception:
                pass
            self._setup_poll_job = None

    def _poll_setup_room(self):
        if not getattr(self, '_setup_poll_active', False):
            return
        if not hasattr(self, 'player_listbox') or not self.player_listbox.winfo_exists():
            self._setup_poll_active = False
            return

        threading.Thread(target=lambda: self.sync_room_players(notify_if_none=False), daemon=True).start()
        self._setup_poll_job = self.after(3500, self._poll_setup_room)

    def save_and_publish_tournament(self, notify=False):
        """
        Guarda el torneo actual en data/history/, migra a SQLite matches history,
        calcula Academy ELO/Misiones, genera el snapshot y lo sube automáticamente a Render.
        """
        if not self.manager.players:
            if notify:
                messagebox.showwarning("Atención", "No hay jugadores en el torneo para guardar.")
            return False

        try:
            history_dir = os.path.join("data", "history")
            os.makedirs(history_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = getattr(self, '_last_saved_history_filename', None)
            if not filename:
                filename = f"tournament_{timestamp}.json"
                self._last_saved_history_filename = filename
            filepath = os.path.join(history_dir, filename)

            from store_manager import StoreManager
            payload = {
                "version": 1,
                "saved_at": datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
                "manager": self.manager.to_dict(),
                "ui": {
                    "round_minutes": getattr(self, "round_minutes", 50),
                    "date": self.date_var.get() if hasattr(self, "date_var") else datetime.now().strftime("%d-%m-%y"),
                    "format": getattr(self.manager, "format_name", "GOAT"),
                    "store_name": StoreManager().get_active_store()
                }
            }
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)

            t_id = getattr(self, '_current_saved_tournament_id', None)
            if not t_id:
                from migrate_history import migrate_history
                t_id = migrate_history(specific_file=filename)
                self._current_saved_tournament_id = t_id

            if t_id:
                import sqlite3
                from academy.academy_engine import AcademyEngine
                from academy.sync_manager import SyncManager
                from database import get_connection

                conn = get_connection()
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                try:
                    AcademyEngine().process_tournament(cursor, t_id)
                    conn.commit()
                except Exception as e_ae:
                    print(f"[TournamentUI] Error in AcademyEngine: {e_ae}")

                try:
                    sync_mgr = SyncManager()
                    new_version = sync_mgr.generate_snapshot_and_manifest(cursor)
                    conn.close()
                    sync_mgr.publish()
                    self._push_snapshot_to_cloud(new_version)
                except Exception as e_sm:
                    print(f"[TournamentUI] Error in SyncManager: {e_sm}")
                    if conn:
                        try:
                            conn.close()
                        except Exception:
                            pass

            self.sync_active_room(status="FINISHED")
            self._tournament_already_published = True

            if notify:
                messagebox.showinfo(
                    "Torneo Publicado",
                    "¡El torneo ha sido guardado y publicado con éxito!\nLos resultados, ranking ELO y perfiles han sido actualizados en la web."
                )
            return True

        except Exception as e:
            print(f"[TournamentUI] Error in save_and_publish_tournament: {e}")
            if notify:
                messagebox.showerror("Error", f"Ocurrió un error al guardar o publicar el torneo:\n{e}")
            return False

    def _push_snapshot_to_cloud(self, version=None):
        """Lee el último snapshot generado y lo envía a Render via RemoteSyncClient."""
        if not getattr(self, 'remote_sync', None) or not self.remote_sync.enabled:
            return

        def _do_push():
            try:
                snapshots_dir = os.path.join("data", "snapshots")
                snap_path = None
                if version:
                    candidate = os.path.join(snapshots_dir, f"snapshot_v{version}.json")
                    if os.path.exists(candidate):
                        snap_path = candidate
                if not snap_path:
                    manifest_path = os.path.join(snapshots_dir, "manifest.json")
                    if os.path.exists(manifest_path):
                        with open(manifest_path, "r", encoding="utf-8") as mf:
                            mdata = json.load(mf)
                            latest = mdata.get("latest_snapshot")
                            if latest:
                                snap_path = os.path.join(snapshots_dir, latest)

                if snap_path and os.path.exists(snap_path):
                    with open(snap_path, "r", encoding="utf-8") as f:
                        snap_json = json.load(f)
                    ok, resp_msg = self.remote_sync.sync_full_snapshot(snap_json, filename=os.path.basename(snap_path))
                    print(f"[TournamentUI] Cloud snapshot push result: ok={ok}, msg={resp_msg}")
            except Exception as ex:
                print(f"[TournamentUI] Error pushing snapshot to cloud: {ex}")

        threading.Thread(target=_do_push, daemon=True).start()

    def check_room_match_reports(self):
        """
        Revisa periódicamente si hay resultados confirmados o retiros (drops)
        por los duelistas desde sus teléfonos (tanto en local como en la nube).
        """
        if not getattr(self, 'active_room_code', None):
            return
        if not hasattr(self, 'manager') or self.manager.status != "running":
            return
        try:
            from tournament_room_manager import TournamentRoomManager
            trm = TournamentRoomManager()
            cursor = trm._get_cursor()
            room = trm.get_room_by_code(self.active_room_code)
            if not room:
                return

            curr_round = self.manager.current_round

            # 1. Reportes locales de partidos
            cursor.execute("""
                SELECT * FROM room_match_reports
                WHERE room_id = ? AND round_num = ?
            """, (room['id'], curr_round))
            reports = cursor.fetchall() or []

            # 2. Jugadores dropeados locales
            local_drops = trm.get_room_dropped_players(self.active_room_code) or []
            dropped_names = {d['player_name'].strip().lower() for d in local_drops}

            # 3. Consultar eventos del hosting remoto si la sincronización está activa
            if getattr(self, 'remote_sync', None) and self.remote_sync.enabled:
                ok, cloud_data = self.remote_sync.fetch_room_events(self.active_room_code)
                if ok and cloud_data:
                    # Mezclar reportes remotos confirmados
                    cloud_reports = cloud_data.get("reports", [])
                    for cr in cloud_reports:
                        if cr.get("status") == "CONFIRMED":
                            existing = any(r['table_num'] == cr.get('table_num') and r['status'] == 'CONFIRMED' for r in reports)
                            if not existing:
                                reports.append(cr)
                    # Mezclar drops remotos
                    cloud_drops = cloud_data.get("drops", [])
                    for cd in cloud_drops:
                        dropped_names.add(cd.get("player_name", "").strip().lower())

            # 4. Procesar reportes en las mesas activas
            matches = self.manager.get_current_matches()
            changed = False
            for rep in reports:
                tbl_idx = rep['table_num'] - 1
                if 0 <= tbl_idx < len(matches):
                    m = matches[tbl_idx]
                    if rep.get('status') == 'CONFIRMED' and not m.reported:
                        res_str = f"{rep['score_p1']}-{rep['score_p2']}"
                        m.report(res_str)
                        self.refresh_round_after_result_change(m)
                        changed = True

            # 5. Procesar Drops automáticos
            for p in self.manager.players:
                if p.active and p.name.strip().lower() in dropped_names:
                    print(f"[TournamentUI] Auto-procesando drop de jugador: {p.name}")
                    self.manager.drop_player(p.name, reason="Retiro voluntario vía móvil (Drop)")
                    changed = True

            if changed:
                self.autosave_tournament()
                self.sync_active_room()
                if hasattr(self, 'tree') and self.tree.winfo_exists():
                    self.update_standings_tree()
        except Exception as e:
            print("[TournamentUI] Error auto-verificando reportes y drops de sala:", e)

    def check_room_reports_loop(self):
        """Polling en segundo plano para sincronizar reportes de la sala."""
        if getattr(self, 'active_room_code', None) and hasattr(self, 'manager') and self.manager.status == "running":
            self.check_room_match_reports()
        if not getattr(self, '_room_loop_running', False):
            self._room_loop_running = True
        self.after(3500, self.check_room_reports_loop)

    def open_remote_sync_dialog(self):
        """
        Ventana de configuración para la conexión y sincronización
        autenticada con el servidor hosting en la nube.
        """
        win = ctk.CTkToplevel(self)
        win.title("🌐 Conexión con Hosting Cloud - Duelorapido.cl")
        win.geometry("540x480")
        win.configure(fg_color="#0f172a")
        win.transient(self)
        win.grab_set()

        ctk.CTkLabel(win, text="🌐 CONFIGURACIÓN SERVIDOR HOSTING", font=("Orbitron", 14, "bold"), text_color="#38bdf8").pack(pady=(20, 4))
        ctk.CTkLabel(win, text="Sincroniza salas, rondas y reportes con tu servidor web en la nube.", font=UI_FONT_SMALL, text_color="#94a3b8").pack(pady=(0, 16))

        body = ctk.CTkFrame(win, fg_color="#1e293b", corner_radius=12)
        body.pack(fill="x", padx=24, pady=5, ipady=10)

        # URL del servidor
        ctk.CTkLabel(body, text="URL del Servidor Hosting (ej. https://tudominio.com):", font=UI_FONT_SMALL, text_color="#e2e8f0").pack(anchor="w", padx=16, pady=(10, 2))
        url_entry = ctk.CTkEntry(body, font=UI_FONT, width=440, placeholder_text="http://127.0.0.1:8000 o https://tudominio.onrender.com")
        url_entry.pack(padx=16, pady=(0, 10))
        url_entry.insert(0, self.remote_sync.remote_url)

        # API Key
        ctk.CTkLabel(body, text="Clave de Autenticación de Organizador (ORGANIZER_API_KEY):", font=UI_FONT_SMALL, text_color="#e2e8f0").pack(anchor="w", padx=16, pady=(0, 2))
        key_entry = ctk.CTkEntry(body, font=UI_FONT, width=440, show="•", placeholder_text="Ingresa tu API Key secreta")
        key_entry.pack(padx=16, pady=(0, 12))
        key_entry.insert(0, self.remote_sync.api_key)

        def toggle_key_vis():
            if key_entry.cget("show") == "":
                key_entry.configure(show="•")
                btn_vis.configure(text="👁️ Mostrar Clave")
            else:
                key_entry.configure(show="")
                btn_vis.configure(text="🔒 Ocultar Clave")

        btn_vis = ctk.CTkButton(body, text="👁️ Mostrar Clave", command=toggle_key_vis, font=UI_FONT_SMALL, width=120, height=24, fg_color="#334155", hover_color="#475569")
        btn_vis.pack(anchor="e", padx=16, pady=(0, 12))

        # Checkbox activar sincronización
        enabled_var = tk.BooleanVar(value=self.remote_sync.enabled)
        chk_enabled = ctk.CTkCheckBox(body, text="Activar sincronización automática con la nube", variable=enabled_var, font=UI_FONT_SMALL, text_color="#4ade80")
        chk_enabled.pack(anchor="w", padx=16, pady=(4, 10))

        # Estado del test
        status_lbl = ctk.CTkLabel(win, text="", font=UI_FONT_SMALL, text_color="#94a3b8")
        status_lbl.pack(pady=4)

        def do_test():
            status_lbl.configure(text="Probando conexión...", text_color="#38bdf8")
            win.update()
            temp_client = RemoteSyncClient()
            temp_client.remote_url = url_entry.get().strip().rstrip("/")
            temp_client.api_key = key_entry.get().strip()
            ok, msg = temp_client.test_connection()
            if ok:
                status_lbl.configure(text=f"✅ {msg}", text_color="#4ade80")
            else:
                status_lbl.configure(text=f"❌ {msg}", text_color="#f87171")

        def do_save():
            u = url_entry.get().strip().rstrip("/")
            k = key_entry.get().strip()
            en = enabled_var.get()
            if not u:
                messagebox.showerror("Error", "La URL del servidor no puede estar vacía.", parent=win)
                return
            if not k:
                messagebox.showerror("Error", "La API Key no puede estar vacía.", parent=win)
                return

            self.remote_sync.save_config(u, k, en)
            if en and getattr(self, 'active_room_code', None):
                self.sync_active_room()
            messagebox.showinfo("Configuración Guardada", "La conexión con el hosting ha sido guardada correctamente.", parent=win)
            win.destroy()

        btn_box = ctk.CTkFrame(win, fg_color="transparent")
        btn_box.pack(pady=10)

        ctk.CTkButton(btn_box, text="⚡ Probar Conexión", command=do_test, font=UI_FONT_SMALL, width=140, fg_color="#3b82f6", hover_color="#2563eb").pack(side="left", padx=8)
        ctk.CTkButton(btn_box, text="💾 Guardar Cambios", command=do_save, font=UI_FONT_SMALL, width=140, fg_color="#10b981", hover_color="#059669", text_color="#0f172a").pack(side="left", padx=8)
        ctk.CTkButton(btn_box, text="Cancelar", command=win.destroy, font=UI_FONT_SMALL, width=90, fg_color="#334155", hover_color="#475569").pack(side="left", padx=8)


    def open_qr_checkin_window(self):
        import qrcode
        from PIL import Image, ImageTk
        import webbrowser
        from tournament_room_manager import TournamentRoomManager

        trm = TournamentRoomManager()
        date_str = self.date_var.get() if hasattr(self, 'date_var') else datetime.now().strftime("%d-%m-%Y")
        fmt = self.format_var.get() if hasattr(self, 'format_var') else "EDISON"
        sched_id = getattr(self, 'current_scheduled_id', None)
        title = f"Torneo {fmt} ({date_str})"

        room = trm.create_or_get_room(title=title, format_name=fmt, scheduled_id=sched_id, room_code=getattr(self, 'active_room_code', None))
        self.active_room_code = room['room_code']

        # Sincronizar estado actual del manager
        # Sincronizar estado inicial (crear la sala también en Render en estado LOBBY)
        if getattr(self, 'remote_sync', None) and self.remote_sync.enabled:
            def _create_room_in_cloud():
                try:
                    self.remote_sync.sync_room_state(
                        room_code=room['room_code'],
                        title=title,
                        current_round=0,
                        pairings=[],
                        standings=[],
                        timer_info={},
                        status="LOBBY",
                        format_name=fmt
                    )
                except Exception as err:
                    print("[TournamentUI] Error syncing lobby to cloud:", err)
            threading.Thread(target=_create_room_in_cloud, daemon=True).start()

        win = ctk.CTkToplevel(self)
        win.title(f"📱 Sala Interactiva de Torneo - PIN #{room['room_code']}")
        win.geometry("800x560")
        win.configure(fg_color="#0f172a")
        win.transient(self)
        win.grab_set()

        # Top banner
        header = ctk.CTkFrame(win, fg_color="#1e293b", corner_radius=10)
        header.pack(fill="x", padx=15, pady=(15, 10))
        
        ctk.CTkLabel(header, text="📱 SALA INTERACTIVA DE CHECK-IN Y PAREOS EN VIVO", font=("Orbitron", 14, "bold"), text_color="#38bdf8").pack(anchor="w", padx=15, pady=(10, 2))
        ctk.CTkLabel(header, text="Los duelistas escanean el QR desde sus teléfonos, se inscriben sin crear contraseñas y ven su mesa asignada.", font=UI_FONT_SMALL, text_color="#94a3b8").pack(anchor="w", padx=15, pady=(0, 10))

        content = ctk.CTkFrame(win, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        # Izquierda: QR y PIN
        left_f = ctk.CTkFrame(content, fg_color="#1e293b", corner_radius=10, width=280)
        left_f.pack(side="left", fill="y", padx=(0, 10))

        ctk.CTkLabel(left_f, text="PIN DE ACCESO:", font=UI_FONT_SMALL, text_color="#94a3b8").pack(pady=(15, 0))
        ctk.CTkLabel(left_f, text=f"#{room['room_code']}", font=("Orbitron", 28, "bold"), text_color="#38bdf8").pack(pady=(0, 6))

        base_url = "https://subarashii-academy.onrender.com"
        if getattr(self, 'remote_sync', None) and self.remote_sync.remote_url:
            base_url = self.remote_sync.remote_url.rstrip("/")
        url = f"{base_url}/unirse/{room['room_code']}"

        qr = qrcode.QRCode(box_size=5, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        qr_photo = ImageTk.PhotoImage(qr_img)

        qr_lbl = tk.Label(left_f, image=qr_photo, bg="white", borderwidth=0)
        qr_lbl.image = qr_photo
        qr_lbl.pack(pady=4)

        display_url = base_url.replace("https://", "").replace("http://", "") + f"/unirse/{room['room_code']}"
        ctk.CTkLabel(left_f, text=display_url, font=("Roboto", 10), text_color="#38bdf8").pack(pady=(4, 10))

        ctk.CTkButton(left_f, text="🌐 Abrir Sala en Navegador", font=UI_FONT_SMALL, fg_color="#334155", hover_color="#475569",
                      command=lambda: webbrowser.open(url)).pack(fill="x", padx=15, pady=(0, 15))

        # Derecha: Lista de jugadores inscritos
        right_f = ctk.CTkFrame(content, fg_color="#1e293b", corner_radius=10)
        right_f.pack(side="left", fill="both", expand=True)

        r_hdr = ctk.CTkFrame(right_f, fg_color="transparent")
        r_hdr.pack(fill="x", padx=15, pady=(15, 8))
        
        lbl_players_count = ctk.CTkLabel(r_hdr, text="Jugadores en Sala: 0", font=("Roboto", 13, "bold"), text_color="#f8fafc")
        lbl_players_count.pack(side="left")

        tree_f = ctk.CTkFrame(right_f, fg_color="transparent")
        tree_f.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        cols = ("name", "dorm", "deck", "time")
        tree = ttk.Treeview(tree_f, columns=cols, show="headings", height=8, selectmode="extended")
        tree.heading("name", text="Nombre")
        tree.heading("dorm", text="Casa / Dorm")
        tree.heading("deck", text="Mazo")
        tree.heading("time", text="Hora Check-in")
        tree.column("name", width=140, anchor="w")
        tree.column("dorm", width=110, anchor="center")
        tree.column("deck", width=110, anchor="w")
        tree.column("time", width=80, anchor="center")
        tree.pack(side="left", fill="both", expand=True)

        sc = ttk.Scrollbar(tree_f, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sc.set)
        sc.pack(side="right", fill="y")

        act_f = ctk.CTkFrame(right_f, fg_color="transparent")
        act_f.pack(fill="x", padx=15, pady=(0, 15))

        def import_players_to_tournament():
            threading.Thread(target=lambda: self.sync_room_players(notify_if_none=True), daemon=True).start()

        ctk.CTkButton(act_f, text="📥 AÑADIR JUGADORES AL TORNEO", font=("Roboto", 12, "bold"),
                      fg_color="#22c55e", hover_color="#16a34a", text_color="#0f172a", height=38,
                      command=import_players_to_tournament).pack(side="left", fill="x", expand=True, padx=(0, 10))

        polling_active = True
        def poll_room():
            if not polling_active or not win.winfo_exists():
                return
            try:
                # Si la sincronización en la nube está activa, consultar y sincronizar check-ins de Render
                if getattr(self, 'remote_sync', None) and self.remote_sync.enabled:
                    try:
                        ok, cloud_events = self.remote_sync.fetch_room_events(room['room_code'])
                        if ok and cloud_events and "players" in cloud_events:
                            for cp in cloud_events["players"]:
                                trm.register_player(
                                    room_code=room['room_code'],
                                    player_name=cp.get("player_name", ""),
                                    konami_id=cp.get("konami_id", "") or "",
                                    deck_archetype=cp.get("deck_archetype", "") or "",
                                    session_token=cp.get("session_token", "") or ""
                                )
                    except Exception:
                        pass

                plist = trm.get_room_players(room['room_code'])
                lbl_players_count.configure(text=f"Jugadores en Sala: {len(plist)}")
                for item in tree.get_children():
                    tree.delete(item)
                for p in plist:
                    t_str = p.get('checked_in_at', '')
                    if t_str and 'T' in t_str:
                        t_str = t_str.split('T')[1][:5]
                    tree.insert("", "end", values=(
                        p['player_name'],
                        p.get('dorm', 'Intercambio'),
                        p.get('deck_archetype') or '-',
                        t_str or '-'
                    ))
            except Exception:
                pass
            win.after(2000, poll_room)

        def on_close():
            nonlocal polling_active
            polling_active = False
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", on_close)
        poll_room()


    def toggle_audio(self):
        self.audio_muted = not self.audio_muted
        if self.audio_muted:
            self.mute_btn.configure(text="🔇")
        else:
            self.mute_btn.configure(text="🔊")
            
    def render_scheduled_tournament_banner(self, parent):
        try:
            from calendar_manager import CalendarManager
            cm = CalendarManager()
            target_d = self.date_var.get() if hasattr(self, 'date_var') else None
            scheduled_list = cm.get_tournaments_for_date(target_d)
            pending = [s for s in scheduled_list if s.get('status') == 'PROGRAMADO']
            if not pending:
                return

            sched = pending[0]
            banner = ctk.CTkFrame(parent, fg_color="#1e293b", border_width=2, border_color="#38bdf8", corner_radius=8)
            banner.pack(fill="x", padx=10, pady=(5, 10), ipady=6)

            left_info = ctk.CTkFrame(banner, fg_color="transparent")
            left_info.pack(side="left", padx=15, fill="x", expand=True)

            title_row = ctk.CTkFrame(left_info, fg_color="transparent")
            title_row.pack(anchor="w")

            ctk.CTkLabel(title_row, text="📅 TORNEO PROGRAMADO PARA HOY:", font=("Roboto", 11, "bold"), text_color="#38bdf8").pack(side="left", padx=(0, 10))
            ctk.CTkLabel(title_row, text=sched['title'], font=("Orbitron", 14), text_color="#ffffff").pack(side="left")

            sub_txt = f"Formato: {sched['format_name']}  |  Hora: {sched['time']}  |  Modo: {sched.get('mode', 'swiss').capitalize()}"
            if sched.get('prize_description'):
                sub_txt += f"  |  🏆 Premio: {sched['prize_description']}"
            ctk.CTkLabel(left_info, text=sub_txt, font=UI_FONT_SMALL, text_color="#94a3b8").pack(anchor="w", pady=(2, 0))

            btn_frame = ctk.CTkFrame(banner, fg_color="transparent")
            btn_frame.pack(side="right", padx=15)

            def load_scheduled():
                self.format_var.set(sched['format_name'])
                self.on_format_changed(sched['format_name'])
                if hasattr(self, 'mode_var'):
                    self.mode_var.set(sched.get('mode', 'swiss'))
                self.current_scheduled_id = sched['id']
                banner.configure(border_color="#22c55e", fg_color="#14532d")
                load_btn.configure(text="✅ CARGADO", state="disabled", fg_color="#15803d")
                messagebox.showinfo("Configuración Cargada", f"Se cargó la configuración del torneo programado:\n'{sched['title']}' ({sched['format_name']}).")

            def launch_scheduled_now():
                load_scheduled()
                self.open_qr_checkin_window()

            ctk.CTkButton(btn_frame, text="🚀 LANZAR AHORA", font=("Roboto", 12, "bold"),
                          fg_color="#22c55e", hover_color="#16a34a", text_color="#0f172a",
                          command=launch_scheduled_now).pack(side="right", padx=(8, 0))

            load_btn = ctk.CTkButton(btn_frame, text="⚡ Cargar Config", font=("Roboto", 12, "bold"),
                                     fg_color="#38bdf8", hover_color="#0284c7", text_color="#0f172a",
                                     command=load_scheduled)
            load_btn.pack(side="right")
        except Exception as e:
            print(f"[TournamentUI] Error loading scheduled tournament banner: {e}")

    def load_scheduled_event(self, sched):
        """Precarga la configuración de un torneo programado desde el calendario."""
        if not sched:
            return
        self.format_var.set(sched.get('format_name', 'GOAT'))
        self.on_format_changed(sched.get('format_name', 'GOAT'))
        if hasattr(self, 'mode_var'):
            self.mode_var.set(sched.get('mode', 'swiss'))
        if hasattr(self, 'date_var') and sched.get('date'):
            from calendar_manager import parse_date_flexible
            dt = parse_date_flexible(sched['date'])
            if dt:
                self.date_var.set(dt.strftime("%d-%m-%y"))
            else:
                self.date_var.set(sched['date'])
        self.current_scheduled_id = sched.get('id')
        self.show_setup_view()

    def open_launch_scheduled_dialog(self):
        """Modal para explorar y lanzar torneos programados desde el calendario."""
        try:
            from calendar_manager import CalendarManager, to_display_date
            cm = CalendarManager()
            all_scheduled = cm.get_scheduled_tournaments(include_finished=False)
            scheduled_list = [s for s in all_scheduled if s.get('status') == 'PROGRAMADO']
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo consultar el calendario: {e}")
            return

        win = ctk.CTkToplevel(self)
        win.title("🚀 Lanzar Torneo Programado (Calendario)")
        win.geometry("780x520")
        win.configure(fg_color="#0f172a")
        win.transient(self)
        win.grab_set()

        header = ctk.CTkFrame(win, fg_color="#1e293b", corner_radius=10)
        header.pack(fill="x", padx=15, pady=15)
        ctk.CTkLabel(header, text="📅 TORNEOS PROGRAMADOS EN EL CALENDARIO", font=("Orbitron", 14, "bold"), text_color="#38bdf8").pack(anchor="w", padx=15, pady=(12, 2))
        ctk.CTkLabel(header, text="Selecciona un torneo de la agenda para lanzar su registro interactivo, sala QR y rondas oficiales.", font=UI_FONT_SMALL, text_color="#94a3b8").pack(anchor="w", padx=15, pady=(0, 12))

        scroll = ctk.CTkScrollableFrame(win, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        if not scheduled_list:
            empty_box = ctk.CTkFrame(scroll, fg_color="#1e293b", corner_radius=10)
            empty_box.pack(fill="x", pady=20, padx=10, ipady=30)
            ctk.CTkLabel(empty_box, text="No hay torneos pendientes en estado 'PROGRAMADO'.", font=UI_FONT, text_color="#cbd5e1").pack()
            ctk.CTkLabel(empty_box, text="Puedes agendar nuevos torneos y ligas desde la pestaña de Calendario en la Academia de Duelos.", font=UI_FONT_SMALL, text_color="#64748b").pack(pady=4)
            return

        for s in scheduled_list:
            card = ctk.CTkFrame(scroll, fg_color="#1e293b", border_width=1, border_color="#334155", corner_radius=10)
            card.pack(fill="x", pady=6, padx=5, ipady=8)

            c_info = ctk.CTkFrame(card, fg_color="transparent")
            c_info.pack(side="left", fill="both", expand=True, padx=15)

            row1 = ctk.CTkFrame(c_info, fg_color="transparent")
            row1.pack(anchor="w")
            ctk.CTkLabel(row1, text=s['title'], font=("Orbitron", 13, "bold"), text_color="#ffffff").pack(side="left", padx=(0, 10))
            ctk.CTkLabel(row1, text=f"[{s['format_name']}]", font=("Roboto", 11, "bold"), text_color="#38bdf8").pack(side="left")

            d_disp = to_display_date(s.get('date', ''))
            time_disp = s.get('time', '16:00')
            mode_disp = (s.get('mode') or 'swiss').capitalize()
            det_txt = f"📅 {d_disp} a las {time_disp} hrs  |  Modo: {mode_disp}"
            if s.get('prize_description'):
                det_txt += f"  |  🏆 {s['prize_description']}"
            ctk.CTkLabel(c_info, text=det_txt, font=UI_FONT_SMALL, text_color="#94a3b8").pack(anchor="w", pady=(4, 0))

            def do_launch(sched_item=s):
                win.destroy()
                self.load_scheduled_event(sched_item)
                self.open_qr_checkin_window()
                messagebox.showinfo(
                    "Torneo Lanzado",
                    f"¡Torneo '{sched_item['title']}' lanzado con éxito!\n\n"
                    f"• Formato: {sched_item['format_name']}\n"
                    f"• Código PIN de Sala QR interactiva generado.\n"
                    f"Los jugadores pueden escanear el QR para inscribirse desde sus teléfonos."
                )

            ctk.CTkButton(card, text="🚀 LANZAR ESTE TORNEO", font=("Roboto", 12, "bold"),
                          fg_color="#22c55e", hover_color="#16a34a", text_color="#0f172a", width=180, height=36,
                          command=do_launch).pack(side="right", padx=15)

    def show_setup_view(self):
        self.stop_setup_room_poll()
        if getattr(self, "current_view_frame", None):
            old = self.current_view_frame
            self.after(20, lambda o=old: o.destroy() if o.winfo_exists() else None)
        self.current_view_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        buf = self.current_view_frame

        # Banner si hay torneo programado para hoy
        self.render_scheduled_tournament_banner(buf)

        split_container = ctk.CTkFrame(buf, fg_color="transparent")
        split_container.pack(fill="both", expand=True)
            
        add_frame = ctk.CTkFrame(split_container, fg_color="#0f172a")
        add_frame.pack(side="left", fill="y", padx=10, pady=10, ipadx=20, ipady=20)
        
        header_frame = ctk.CTkFrame(add_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=(10, 10))
        ctk.CTkLabel(header_frame, text="Registro de Jugadores", font=UI_FONT, text_color="#60a5fa").pack(side="left")
        
        ctk.CTkLabel(add_frame, text="Nombre del Jugador:", text_color="#60a5fa", font=UI_FONT_SMALL).pack(anchor="w")
        self.name_entry = ctk.CTkEntry(add_frame, font=UI_FONT, width=250)
        self.name_entry.pack(pady=(0, 10))
        
        ctk.CTkLabel(add_frame, text="Konami ID (Opcional):", text_color="#60a5fa", font=UI_FONT_SMALL).pack(anchor="w")
        self.id_entry = ctk.CTkEntry(add_frame, font=UI_FONT, width=250)
        self.id_entry.pack(pady=(0, 10))
        
        ctk.CTkLabel(add_frame, text="Teléfono (Opcional):", text_color="#60a5fa", font=UI_FONT_SMALL).pack(anchor="w")
        self.phone_entry = ctk.CTkEntry(add_frame, font=UI_FONT, width=250)
        self.phone_entry.pack(pady=(0, 10))
        
        ctk.CTkLabel(add_frame, text="Correo (Opcional):", text_color="#60a5fa", font=UI_FONT_SMALL).pack(anchor="w")
        self.email_entry = ctk.CTkEntry(add_frame, font=UI_FONT, width=250)
        self.email_entry.pack(pady=(0, 10))
        
        self.paid_var = ctk.BooleanVar(value=False)
        self.paid_chk = ctk.CTkCheckBox(add_frame, text="Pagado", variable=self.paid_var, text_color="#60a5fa", font=UI_FONT_SMALL)
        self.paid_chk.pack(anchor="w", pady=(0, 5))
        
        self.invited_var = ctk.BooleanVar(value=False)
        self.invited_chk = ctk.CTkCheckBox(add_frame, text="Invitado", variable=self.invited_var, text_color="#60a5fa", font=UI_FONT_SMALL)
        self.invited_chk.pack(anchor="w", pady=(0, 10))
        
        ctk.CTkButton(add_frame, text="AÑADIR JUGADOR", command=self.add_player, font=UI_FONT).pack(pady=10)
        
        ctk.CTkLabel(add_frame, text="Jugadores Frecuentes (Doble clic):", text_color="#94a3b8", font=UI_FONT_SMALL).pack(anchor="w", pady=(20, 5))
        self.db_listbox = tk.Listbox(add_frame, font=UI_FONT_SMALL, height=8, bg="#1e293b", fg="white", selectbackground="#3b82f6", relief="flat", borderwidth=0, highlightthickness=0, selectmode=tk.EXTENDED)
        self.db_listbox.pack(fill="both", expand=True)
        
        self.refresh_db_listbox()
            
        self.db_listbox.bind("<Double-1>", self.on_db_player_select)
        
        db_btns = ctk.CTkFrame(add_frame, fg_color="transparent")
        db_btns.pack(fill="x", pady=10)
        ctk.CTkButton(db_btns, text="Editar", command=self.edit_db_player, font=UI_FONT_SMALL, width=100).pack(side="left", expand=True, padx=2)
        ctk.CTkButton(db_btns, text="Fusionar", command=self.merge_db_players, font=UI_FONT_SMALL, width=100, fg_color="#f59e0b", hover_color="#d97706").pack(side="left", expand=True, padx=2)
        ctk.CTkButton(db_btns, text="Eliminar", command=self.delete_db_player, font=UI_FONT_SMALL, width=100, fg_color="#ef4444", hover_color="#b91c1c").pack(side="left", expand=True, padx=2)
        
        list_frame = ctk.CTkFrame(split_container, fg_color="#0f172a")
        list_frame.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10, ipadx=20, ipady=20)
        
        lbl_frame = ctk.CTkFrame(list_frame, fg_color="transparent")
        lbl_frame.pack(fill="x", pady=(0, 5))
        
        self.player_count_label = ctk.CTkLabel(lbl_frame, text="Inscritos: 0", font=UI_FONT_SMALL, text_color="#60a5fa")
        self.player_count_label.pack(side="left")
        
        sort_var = ctk.StringVar(value="Ordenar")
        sort_cb = ctk.CTkOptionMenu(lbl_frame, variable=sort_var, values=["Por Nombre", "Por Pagado"], width=110, font=UI_FONT_SMALL, command=self.sort_players_list)
        sort_cb.pack(side="right")
        self.sort_var = sort_var

        ctk.CTkButton(lbl_frame, text="🌐 Hosting Cloud", command=self.open_remote_sync_dialog,
                      font=UI_FONT_SMALL, fg_color="#10b981", hover_color="#059669",
                      text_color="#0f172a", width=125, height=28).pack(side="right", padx=(0, 6))

        ctk.CTkButton(lbl_frame, text="📱 Check-in QR (Sala)", command=self.open_qr_checkin_window,
                      font=UI_FONT_SMALL, fg_color="#38bdf8", hover_color="#0284c7",
                      text_color="#0f172a", width=145, height=28).pack(side="right", padx=(0, 6))

        self.sync_room_btn = ctk.CTkButton(lbl_frame, text="📥 Sincronizar Sala", command=self.manual_sync_room_players,
                      font=UI_FONT_SMALL, fg_color="#6366f1", hover_color="#4f46e5",
                      text_color="#ffffff", width=130, height=28)
        self.sync_room_btn.pack(side="right", padx=(0, 10))
        
        self.player_listbox = tk.Listbox(list_frame, font=UI_FONT, bg="#1e293b", fg="white", selectbackground="#3b82f6", relief="flat", borderwidth=0, highlightthickness=0)
        self.player_listbox.pack(fill="both", expand=True, pady=(10, 20))
        self.player_listbox.bind("<<ListboxSelect>>", self.on_enrolled_player_select)
        self.player_listbox.bind("<KeyPress-i>", self.toggle_enrolled_invited_key)
        self.player_listbox.bind("<KeyPress-p>", self.toggle_enrolled_paid_key)
        self.player_listbox.bind("<KeyPress-I>", self.toggle_enrolled_invited_key)
        self.player_listbox.bind("<KeyPress-P>", self.toggle_enrolled_paid_key)
        
        list_actions_frame = ctk.CTkFrame(list_frame, fg_color="transparent")
        list_actions_frame.pack(fill="x", pady=(0, 10))
        ctk.CTkButton(list_actions_frame, text="Alternar Pagado", command=self.toggle_enrolled_paid, font=UI_FONT_SMALL, width=110).pack(side="left", padx=5)
        ctk.CTkButton(list_actions_frame, text="Alternar Invitado", command=self.toggle_enrolled_invited, font=UI_FONT_SMALL, width=110).pack(side="left", padx=5)
        ctk.CTkButton(list_actions_frame, text="Eliminar Inscrito", command=self.remove_enrolled_player, font=UI_FONT_SMALL, width=110, fg_color="#ef4444", hover_color="#b91c1c").pack(side="right", padx=5)
        
        format_frame = ctk.CTkFrame(list_frame, fg_color="transparent")
        format_frame.pack(fill="x", pady=(10, 5))
        
        ctk.CTkLabel(format_frame, text="Formato:", text_color="#60a5fa", font=UI_FONT_SMALL).pack(side="left", padx=10)
        self.format_var = ctk.StringVar(value=getattr(self.manager, "format_name", "GOAT"))
        
        format_values = ["GOAT", "EDISON", "Tengu", "H.A.T.", "Speed Duel", "Perfect Circle", "TCG"]
        if self.format_var.get() not in format_values:
            format_values.insert(0, self.format_var.get())
            
        self.format_combo = ctk.CTkComboBox(
            format_frame, 
            variable=self.format_var, 
            values=format_values,
            font=UI_FONT_SMALL,
            width=200,
            command=self.on_format_changed
        )
        self.format_combo.pack(side="left", padx=10)
        
        # We need to bind Return and FocusOut to capture custom types correctly if they type manually
        self.format_combo.bind("<Return>", lambda e: self.on_format_changed(self.format_var.get()))
        self.format_combo.bind("<FocusOut>", lambda e: self.on_format_changed(self.format_var.get()))
        
        start_frame = ctk.CTkFrame(list_frame, fg_color="transparent")
        start_frame.pack(fill="x", pady=10)
        
        ctk.CTkLabel(start_frame, text="Fecha:", text_color="#60a5fa", font=UI_FONT_SMALL).pack(side="left", padx=5)
        ctk.CTkEntry(start_frame, textvariable=self.date_var, font=UI_FONT_SMALL, width=120).pack(side="left", padx=5)

        ctk.CTkLabel(start_frame, text="Min:", text_color="#60a5fa", font=UI_FONT_SMALL).pack(side="left", padx=(10, 2))
        self.round_minutes_var = tk.StringVar(value=str(getattr(self, "round_minutes", 50)))
        ctk.CTkEntry(start_frame, textvariable=self.round_minutes_var, font=UI_FONT_SMALL, width=52).pack(side="left", padx=5)

        ctk.CTkLabel(start_frame, text="Rondas:", text_color="#60a5fa", font=UI_FONT_SMALL).pack(side="left", padx=(10, 2))
        self.rounds_override_var = tk.StringVar(value="")
        ctk.CTkEntry(start_frame, textvariable=self.rounds_override_var, font=UI_FONT_SMALL, width=52, placeholder_text="Auto").pack(side="left", padx=5)
        
        self.mode_var = ctk.StringVar(value=getattr(self.manager, "mode", "swiss"))
        ctk.CTkRadioButton(start_frame, text="Suizo", variable=self.mode_var, value="swiss", font=UI_FONT_SMALL).pack(side="left", padx=10)
        ctk.CTkRadioButton(start_frame, text="Moledoras", variable=self.mode_var, value="grinder", font=UI_FONT_SMALL).pack(side="left", padx=10)
        
        ctk.CTkButton(start_frame, text="INICIAR TORNEO", command=self.start_tournament, font=UI_FONT).pack(side="right", padx=10)
        
        self.update_player_list()
        
        buf.pack(fill="both", expand=True)
        self.ensure_active_room()
        self.start_setup_room_poll()
        
    def toggle_enrolled_paid_key(self, event):
        self.toggle_enrolled_paid()

    def toggle_enrolled_invited_key(self, event):
        self.toggle_enrolled_invited()

    def toggle_enrolled_paid(self):
        selection = self.player_listbox.curselection()
        if not selection:
            messagebox.showwarning("Atención", "Selecciona un jugador de la lista.")
            return
        index = selection[0]
        player = self.manager.players[index]
        player.paid = not getattr(player, "paid", False)
        if getattr(player, "paid", False) and getattr(player, "invited", False):
            player.invited = False
        self.autosave_tournament()
        self.update_player_list()
        self.player_listbox.selection_set(index)
        self.player_listbox.activate(index)

    def toggle_enrolled_invited(self):
        selection = self.player_listbox.curselection()
        if not selection:
            messagebox.showwarning("Atención", "Selecciona un jugador de la lista.")
            return
        index = selection[0]
        player = self.manager.players[index]
        player.invited = not getattr(player, "invited", False)
        if getattr(player, "invited", False) and getattr(player, "paid", False):
            player.paid = False
        self.autosave_tournament()
        self.update_player_list()
        self.player_listbox.selection_set(index)
        self.player_listbox.activate(index)

    def remove_enrolled_player(self):
        selection = self.player_listbox.curselection()
        if not selection:
            messagebox.showwarning("Atención", "Selecciona un jugador de la lista de inscritos para eliminarlo.")
            return
            
        index = selection[0]
        player = self.manager.players[index]
        if messagebox.askyesno("Confirmar", f"¿Eliminar a {player.name} de los inscritos?"):
            self.manager.players.pop(index)
            self.autosave_tournament()
            self.update_player_list()

    def on_db_player_select(self, event):
        selection = self.db_listbox.curselection()
        if not selection:
            return
        item = self.db_listbox.get(selection[0])
        if "[" in item and "]" in item:
            db_id_str = item.rsplit("[", 1)[1].rstrip("]")
            db_id = int(db_id_str)
            data = self.players_db.get(db_id, {})
            
            self.name_entry.delete(0, tk.END)
            self.name_entry.insert(0, data.get("name", ""))
            self.id_entry.delete(0, tk.END)
            self.id_entry.insert(0, data.get("konami_id", ""))
            
            self.phone_entry.delete(0, tk.END)
            self.phone_entry.insert(0, data.get("phone", ""))
            self.email_entry.delete(0, tk.END)
            self.email_entry.insert(0, data.get("email", ""))
            self.add_player()
        
    def on_enrolled_player_select(self, event):
        selection = self.player_listbox.curselection()
        if not selection:
            return
        index = selection[0]
        player = self.manager.players[index]
        
        self.name_entry.delete(0, tk.END)
        self.name_entry.insert(0, player.name)
        self.id_entry.delete(0, tk.END)
        self.id_entry.insert(0, getattr(player, "konami_id", "") or "")
        
        if hasattr(self, 'phone_entry'):
            self.phone_entry.delete(0, tk.END)
            self.phone_entry.insert(0, getattr(player, "phone", "") or "")
        if hasattr(self, 'email_entry'):
            self.email_entry.delete(0, tk.END)
            self.email_entry.insert(0, getattr(player, "email", "") or "")
        if hasattr(self, 'paid_var'):
            self.paid_var.set(getattr(player, "paid", False))
        if hasattr(self, 'invited_var'):
            self.invited_var.set(getattr(player, "invited", False))

    def merge_db_players(self):
        selection = self.db_listbox.curselection()
        if len(selection) < 2:
            messagebox.showinfo("Fusión", "Debes seleccionar al menos dos jugadores para fusionar (Usa Ctrl+Clic).")
            return
            
        selected_ids = []
        selected_names = []
        for sel in selection:
            item = self.db_listbox.get(sel)
            if "[" in item and "]" in item:
                db_id_str = item.rsplit("[", 1)[1].rstrip("]")
                db_id = int(db_id_str)
                selected_ids.append(db_id)
                selected_names.append(self.players_db.get(db_id, {}).get("name", ""))
                
        top = ctk.CTkToplevel(self)
        top.title("Fusionar Jugadores")
        top.geometry("400x300")
        top.attributes('-topmost', True)
        top.grab_set()
        
        ctk.CTkLabel(top, text="Se fusionarán los historiales de los jugadores seleccionados.\n¿Qué nombre deseas conservar como principal?", text_color="#60a5fa", font=UI_FONT_SMALL, wraplength=350).pack(pady=10)
        
        suggested_names = list(set([name.title() for name in selected_names]))
        primary_name_var = ctk.StringVar(value=suggested_names[0] if suggested_names else "")
        combo = ctk.CTkComboBox(top, variable=primary_name_var, values=suggested_names, width=250)
        combo.pack(pady=10)
        
        ctk.CTkLabel(top, text="(El jugador con este nombre será el ID principal, los demás se borrarán tras migrar su historial).", text_color="#94a3b8", font=UI_FONT_SMALL, wraplength=350).pack(pady=10)
        
        def confirm_merge():
            chosen_name = primary_name_var.get().strip()
            if not chosen_name:
                messagebox.showerror("Error", "Debes ingresar un nombre válido.")
                return
                
            primary_id = min(selected_ids)
            secondary_ids = [i for i in selected_ids if i != primary_id]
            
            from database import merge_players_db
            try:
                merge_players_db(primary_id, secondary_ids)
                self.cursor.execute("UPDATE players SET name = ? WHERE id = ?", (chosen_name, primary_id))
                self.conn.commit()
                messagebox.showinfo("Éxito", "Jugadores fusionados exitosamente.")
                self.load_db()
                self.refresh_db_listbox()
                top.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Error al fusionar: {e}")
                
        ctk.CTkButton(top, text="Confirmar Fusión", command=confirm_merge, fg_color="#f59e0b", hover_color="#d97706").pack(pady=20)

    def delete_db_player(self):
        selection = self.db_listbox.curselection()
        if not selection: return
        item = self.db_listbox.get(selection[0])
        if "[" in item and "]" in item:
            db_id_str = item.rsplit("[", 1)[1].rstrip("]")
            db_id = int(db_id_str)
            if messagebox.askyesno("Confirmar", "¿Eliminar a este jugador de la lista frecuente?"):
                self.cursor.execute("DELETE FROM players WHERE id = ?", (db_id,))
                self.conn.commit()
                self.load_db()
                self.refresh_db_listbox()
                    
    def edit_db_player(self):
        selection = self.db_listbox.curselection()
        if not selection: return
        item = self.db_listbox.get(selection[0])
        if "[" in item and "]" in item:
            db_id_str = item.rsplit("[", 1)[1].rstrip("]")
            db_id = int(db_id_str)
            data = self.players_db.get(db_id, {})
            
            top = ctk.CTkToplevel(self)
            top.title("Editar Jugador")
            top.geometry("350x450")
            top.attributes('-topmost', True)
            top.grab_set()
            
            ctk.CTkLabel(top, text="Nombre:", text_color="#60a5fa").pack(pady=(10, 2))
            name_entry = ctk.CTkEntry(top, font=UI_FONT, width=250)
            name_entry.insert(0, data.get("name", ""))
            name_entry.pack(pady=5)
            
            ctk.CTkLabel(top, text="Konami ID:", text_color="#60a5fa").pack(pady=(10, 2))
            id_entry = ctk.CTkEntry(top, font=UI_FONT, width=250)
            id_entry.insert(0, data.get("konami_id", ""))
            id_entry.pack(pady=5)
            
            ctk.CTkLabel(top, text="Teléfono:", text_color="#60a5fa").pack(pady=(10, 2))
            phone_entry = ctk.CTkEntry(top, font=UI_FONT, width=250)
            phone_entry.insert(0, data.get("phone", ""))
            phone_entry.pack(pady=5)
            
            ctk.CTkLabel(top, text="Correo Electrónico:", text_color="#60a5fa").pack(pady=(10, 2))
            email_entry = ctk.CTkEntry(top, font=UI_FONT, width=250)
            email_entry.insert(0, data.get("email", ""))
            email_entry.pack(pady=5)
            
            def save_edit():
                new_n = name_entry.get().strip()
                new_id = id_entry.get().strip() or None
                new_p = phone_entry.get().strip()
                new_e = email_entry.get().strip()
                if new_n:
                    try:
                        self.cursor.execute("UPDATE players SET name=?, konami_id=?, phone=?, email=? WHERE id=?", (new_n, new_id, new_p, new_e, db_id))
                        self.conn.commit()
                        self.load_db()
                        self.refresh_db_listbox()
                        top.destroy()
                    except Exception as e:
                        messagebox.showerror("Error", f"No se pudo guardar: {e}")
            ctk.CTkButton(top, text="Guardar", command=save_edit, font=UI_FONT_SMALL).pack(pady=20)

    def add_player(self):
        name = self.name_entry.get().strip()
        k_id = self.id_entry.get().strip()
        phone = getattr(self, 'phone_entry', ctk.CTkEntry(self)).get().strip()
        email = getattr(self, 'email_entry', ctk.CTkEntry(self)).get().strip()
        paid = self.paid_var.get() if hasattr(self, 'paid_var') else False
        invited = self.invited_var.get() if hasattr(self, 'invited_var') else False

        if not name:
            messagebox.showwarning("Error", "El nombre es obligatorio")
            return
        
        for p in self.manager.players:
            if (name and p.name.lower() == name.lower()) or (k_id and getattr(p, 'konami_id', '') == k_id):
                if messagebox.askyesno("Actualizar Inscrito", f"El jugador {p.name} ya está inscrito en el torneo.\n¿Deseas actualizar sus datos con la información del formulario?"):
                    p.name = name
                    p.konami_id = k_id
                    p.phone = phone
                    p.email = email
                    p.paid = paid
                    p.invited = invited
                    self.name_entry.delete(0, tk.END)
                    self.id_entry.delete(0, tk.END)
                    if hasattr(self, 'phone_entry'): self.phone_entry.delete(0, tk.END)
                    if hasattr(self, 'email_entry'): self.email_entry.delete(0, tk.END)
                    if hasattr(self, 'paid_var'): self.paid_var.set(False)
                    if hasattr(self, 'invited_var'): self.invited_var.set(False)
                    self.autosave_tournament()
                    self.update_player_list()
                return
                
        from utils import normalize_player_name
        slug = normalize_player_name(name)
        
        if k_id:
            self.cursor.execute("SELECT id, name FROM players WHERE konami_id=?", (k_id,))
        else:
            self.cursor.execute("SELECT id, name FROM players WHERE slug=?", (slug,))
            
        row = self.cursor.fetchone()
        
        if row:
            db_id = row['id']
            stored_name = row['name']
            if name.lower() != stored_name.lower():
                if messagebox.askyesno("Actualizar Base de Datos", f"El jugador existe registrado como '{stored_name}'. ¿Deseas actualizar el nombre a '{name}'?"):
                    self.cursor.execute("UPDATE players SET name=?, slug=?, phone=?, email=? WHERE id=?", (name, slug, phone, email, db_id))
                    self.conn.commit()
                else:
                    name = stored_name
            else:
                self.cursor.execute("UPDATE players SET phone=?, email=? WHERE id=?", (phone, email, db_id))
                self.conn.commit()
        else:
            try:
                self.cursor.execute("INSERT INTO players (konami_id, name, slug, phone, email) VALUES (?, ?, ?, ?, ?)", (k_id or None, name, slug, phone, email))
                self.conn.commit()
            except Exception as e:
                messagebox.showerror("Error BD", f"Error al guardar: {e}")
                return
            
        self.load_db()
        self.refresh_db_listbox()
            
        self.manager.add_player(name, k_id, phone, email, paid, invited)
        self.name_entry.delete(0, tk.END)
        self.id_entry.delete(0, tk.END)
        if hasattr(self, 'phone_entry'): self.phone_entry.delete(0, tk.END)
        if hasattr(self, 'email_entry'): self.email_entry.delete(0, tk.END)
        if hasattr(self, 'paid_var'): self.paid_var.set(False)
        if hasattr(self, 'invited_var'): self.invited_var.set(False)
        self.autosave_tournament()
        self.update_player_list()
        
    def update_player_list(self):
        yv = self.player_listbox.yview()
        selection = self.player_listbox.curselection()
        self.player_listbox.delete(0, tk.END)
        for p in self.manager.players:
            paid_str = "Sí" if getattr(p, "paid", False) else "No"
            inv_str = "Sí" if getattr(p, "invited", False) else "No"
            self.player_listbox.insert(tk.END, f"{p.name} (ID: {p.konami_id}) - Pagó: {paid_str} | Inv: {inv_str}")
        if hasattr(self, 'player_count_label'):
            self.player_count_label.configure(text=f"Inscritos: {len(self.manager.players)}")
        self.player_listbox.yview_moveto(yv[0])
        if selection:
            self.player_listbox.selection_set(selection[0])
            self.player_listbox.activate(selection[0])
            
    def sort_players_list(self, choice):
        if choice == "Por Nombre":
            self.manager.players.sort(key=lambda p: p.name.lower())
        elif choice == "Por Pagado":
            self.manager.players.sort(key=lambda p: (getattr(p, "paid", False), p.name.lower()))
        self.update_player_list()
        self.autosave_tournament()
            
    def on_format_changed(self):
        format_val = self.format_var.get()
        if format_val == "Speed Duel":
            self.round_minutes_var.set("30")
        else:
            self.round_minutes_var.set("50")

    def start_tournament(self):
        try:
            self.stop_setup_room_poll()
            # Sincronización rápida final de check-ins de sala antes de generar pareos
            try:
                self.sync_room_players(notify_if_none=False)
            except Exception:
                pass

            unpaid = [p for p in self.manager.players if not getattr(p, "paid", False) and not getattr(p, "invited", False)]
            if unpaid:
                from custom_alerts import _create_custom_dialog
                names = "\n".join([f"- {p.name}" for p in unpaid])
                msg = f"Hay {len(unpaid)} jugadores que no han pagado ni están invitados:\n{names}\n\n¿Qué deseas hacer?"
                res = _create_custom_dialog("Atención de Pagos", msg, [("Cancelar", "CANCEL", "Small.TButton"), ("Hacer Invitados", "INVITE", "Small.TButton")], "!", "#eab308")
                if res == "INVITE":
                    for p in unpaid:
                        p.invited = True
                    self.autosave_tournament()
                    self.update_player_list()
                else:
                    return

            self.exported_to_league = False

            minutes_text = self.round_minutes_var.get().strip()
            round_minutes = int(minutes_text) if minutes_text else 50
            if round_minutes < 1:
                raise ValueError("El tiempo por ronda debe ser al menos 1 minuto.")

            rounds_text = self.rounds_override_var.get().strip()
            total_rounds_override = int(rounds_text) if rounds_text else None
            self.round_minutes = round_minutes
            self.manager.start_tournament(self.mode_var.get(), self.format_var.get(), total_rounds_override)
            self.time_left = round_minutes * 60
            self.stop_timer()
            self.autosave_tournament()

            if getattr(self, 'current_scheduled_id', None):
                try:
                    from calendar_manager import CalendarManager
                    CalendarManager().update_scheduled_status(self.current_scheduled_id, 'EN_CURSO')
                except Exception as e:
                    print("Error updating scheduled status:", e)

            if not getattr(self, 'active_room_code', None):
                try:
                    from tournament_room_manager import TournamentRoomManager
                    date_str = self.date_var.get() if hasattr(self, 'date_var') else datetime.now().strftime("%d-%m-%Y")
                    fmt = self.format_var.get()
                    sched_id = getattr(self, 'current_scheduled_id', None)
                    title = f"Torneo {fmt} ({date_str})"
                    room = TournamentRoomManager().create_or_get_room(title=title, format_name=fmt, scheduled_id=sched_id)
                    self.active_room_code = room['room_code']
                except Exception as e:
                    print("[TournamentUI] Error auto-creando sala interactiva:", e)
                
            players_count = len(self.manager.players)
            time_mins = self.time_left // 60
            fmt = self.manager.format_name
            total_rounds = self.manager.total_rounds
            
            if self.manager.mode == "grinder":
                rondas_str = f"el torneo será de eliminación directa con {total_rounds} rondas"
            else:
                rondas_str = f"se jugarán {total_rounds} rondas"
                
            self.speak_warning(f"Bienvenidos al torneo formato {fmt}, hoy serán {players_count} jugadores, {rondas_str} de {time_mins} minutos.")
            
            self.show_round_view()
        except Exception as e:
            messagebox.showerror("Error", str(e))
            
    def show_round_view(self):
        self.stop_setup_room_poll()
        if self.manager.status == "finished":
            self.show_standings_view()
            return
            
        self.sync_active_room()
        if getattr(self, 'active_room_code', None) and not getattr(self, '_room_loop_running', False):
            self.check_room_reports_loop()

        if getattr(self, "current_view_frame", None):
            old = self.current_view_frame
            self.after(20, lambda o=old: o.destroy() if o.winfo_exists() else None)
        self.current_view_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        buf = self.current_view_frame
        
        top_frame = ctk.CTkFrame(buf, fg_color="transparent")
        top_frame.pack(fill="x", pady=(0, 20))
        
        if self.manager.current_round > 1:
            ctk.CTkButton(top_frame, text="< Ronda Anterior", command=self.rollback_round_ui, font=UI_FONT_SMALL, width=120).pack(side="left", padx=(0, 10))
        elif self.manager.current_round == 1:
            ctk.CTkButton(top_frame, text="< Volver a Registro", command=self.rollback_to_setup_ui, font=UI_FONT_SMALL, width=140).pack(side="left", padx=(0, 10))
            
        ctk.CTkLabel(top_frame, text=f"Ronda {self.manager.current_round} de {self.manager.total_rounds}", font=UI_FONT_BIG, text_color="#60a5fa").pack(side="left")
        ctk.CTkButton(top_frame, text="📱 Sala QR", command=self.open_qr_checkin_window, font=UI_FONT_SMALL, width=95, fg_color="#38bdf8", hover_color="#0284c7", text_color="#0f172a").pack(side="left", padx=10)
        ctk.CTkButton(top_frame, text="🌐 Cloud", command=self.open_remote_sync_dialog, font=UI_FONT_SMALL, width=80, fg_color="#10b981", hover_color="#059669", text_color="#0f172a").pack(side="left", padx=4)
        
        timer_frame = ctk.CTkFrame(top_frame, fg_color="#0f172a")
        timer_frame.pack(side="right")
        
        btn_text = "Finalizar Torneo" if self.manager.current_round >= self.manager.total_rounds else "Siguiente Ronda"
        self.round_advance_btn = ctk.CTkButton(top_frame, text=btn_text, command=self.next_round, font=UI_FONT)
        self.update_round_advance_button()
        
        m, s = divmod(self.time_left, 60)
        self.timer_label = ctk.CTkLabel(timer_frame, text=f"{m:02d}:{s:02d}", font=("Orbitron Black", 28), text_color="#60a5fa")
        self.timer_label.pack(side="left", padx=10)
        self.timer_btn = ctk.CTkButton(timer_frame, text="PAUSE" if self.timer_running else "PLAY", command=self.toggle_timer, font=UI_FONT, width=100)
        self.timer_btn.pack(side="left", padx=10, pady=5)
        
        split = tk.PanedWindow(buf, orient="horizontal", bg="#0f172a", sashwidth=4)
        split.pack(fill="both", expand=True, padx=10, pady=10)
        
        matches_frame = ctk.CTkFrame(split, fg_color="transparent")
        standings_frame = ctk.CTkFrame(split, fg_color="transparent")
        split.add(matches_frame, minsize=500)
        split.add(standings_frame, minsize=300)
        
        ctk.CTkLabel(matches_frame, text="Emparejamientos", font=UI_FONT, text_color="#60a5fa").pack(anchor="w", pady=5)
        
        matches_canvas = tk.Canvas(matches_frame, bg="#0f172a", highlightthickness=0)
        scroll = ttk.Scrollbar(matches_frame, orient="vertical", command=matches_canvas.yview)
        scroll.pack(side="right", fill="y")
        matches_canvas.pack(side="left", fill="both", expand=True)
        matches_canvas.configure(yscrollcommand=scroll.set)
        
        inner_frame = ctk.CTkFrame(matches_canvas, fg_color="#0f172a")
        matches_canvas.create_window((0,0), window=inner_frame, anchor="nw")
        self.match_result_frames = {}
        
        for idx, match in enumerate(self.manager.get_current_matches()):
            mf = ctk.CTkFrame(inner_frame, fg_color="#1e293b")
            mf.pack(fill="x", pady=5, padx=5, ipadx=10, ipady=10)
            
            p1_name = match.p1.name if match.p1 else "BYE"
            p2_name = match.p2.name if match.p2 else "BYE"
            
            ctk.CTkLabel(mf, text=f"Mesa {idx + 1}: {p1_name} vs {p2_name}", font=UI_FONT, text_color="#60a5fa").pack(side="top", pady=(0, 10))
            if getattr(match, "note", ""):
                ctk.CTkLabel(mf, text=match.note, font=UI_FONT_SMALL, text_color="#eab308").pack(side="top", pady=(0, 8))
            
            res_frame = ctk.CTkFrame(mf, fg_color="transparent")
            res_frame.pack(side="top")
            self.match_result_frames[match] = res_frame
            self.render_match_result_controls(match, res_frame)

        inner_frame.update_idletasks()
        matches_canvas.config(scrollregion=matches_canvas.bbox("all"))
        
        stand_top = ctk.CTkFrame(standings_frame, fg_color="transparent")
        stand_top.pack(fill="x", pady=5)
        ctk.CTkLabel(stand_top, text="Clasificación Actual", font=UI_FONT, text_color="#60a5fa").pack(side="left")
        
        actions_frame = ctk.CTkFrame(standings_frame, fg_color="transparent")
        actions_frame.pack(fill="x", pady=(0, 8))
        ctk.CTkButton(actions_frame, text="Jugador Atrasado", command=self.show_late_player_dialog, font=UI_FONT_SMALL, width=120).pack(side="left", padx=(0, 6))
        ctk.CTkButton(actions_frame, text="Modificar Pareos", command=self.show_swap_dialog, font=UI_FONT_SMALL, width=120).pack(side="left", padx=6)
        ctk.CTkButton(actions_frame, text="Exportar Pareos PNG", command=self.export_pairings_image, font=UI_FONT_SMALL, width=135).pack(side="left", padx=6)
        ctk.CTkButton(actions_frame, text="Compartir WhatsApp", command=self.share_pairings_whatsapp, font=UI_FONT_SMALL, width=135).pack(side="left", padx=6)
        if self.manager.mode == "grinder" and len(self.manager.players) <= 8:
            ctk.CTkButton(actions_frame, text="Exportar Bracket Top 8", command=self.export_top8_bracket_image, font=UI_FONT_SMALL, width=145).pack(side="left", padx=6)
        ctk.CTkButton(actions_frame, text="Drop", command=self.show_drop_dialog, font=UI_FONT_SMALL, width=60).pack(side="left", padx=6)
        
        cols = ("Rank", "Name", "Points", "Rivales%", "2do nivel%", "Nota desempate")
        self.tree = ttk.Treeview(standings_frame, columns=cols, show="headings", height=15)
        for c in cols:
            self.tree.heading(c, text=c)
            if c == "Name":
                width = 150
            elif c == "Nota desempate":
                width = 120
            else:
                width = 80
            self.tree.column(c, width=width)
        self.tree.pack(fill="both", expand=True)
        
        self.update_standings_tree()

        buf.pack(fill="both", expand=True)

    def export_pairings_image(self):
        matches = self.manager.get_current_matches()
        if not matches:
            messagebox.showwarning("Atención", "No hay pareos disponibles para exportar.")
            return

        try:
            active_store = self.store_manager.get_active_store()
            date_val = getattr(self, "date_var", tk.StringVar(value=datetime.now().strftime("%d-%m-%y"))).get()
            fmt_str = self.manager.format_name.lower().replace(" ", "_")
            store_str = active_store.lower().replace(" ", "_")
            initialfile = f"{store_str}_{fmt_str}_ronda_{self.manager.current_round}_pareos.png"
            filepath = filedialog.asksaveasfilename(
                initialfile=initialfile,
                defaultextension=".png",
                filetypes=[("PNG", "*.png")]
            )
            if not filepath:
                return

            img = generate_pairings_image(self.manager, active_store, date_val)
            img.save(filepath)
            messagebox.showinfo("Pareos exportados", f"Imagen guardada:\n{os.path.basename(filepath)}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo exportar la imagen de pareos: {e}")

    def export_top8_bracket_image(self):
        try:
            from tournament_graphics import generate_top8_bracket_image
            active_store = self.store_manager.get_active_store()
            date_val = getattr(self, "date_var", tk.StringVar(value=datetime.now().strftime("%d-%m-%y"))).get()
            fmt_str = self.manager.format_name.lower().replace(" ", "_")
            store_str = active_store.lower().replace(" ", "_")
            initialfile = f"{store_str}_{fmt_str}_ronda_{self.manager.current_round}_bracket_top8.png"
            filepath = filedialog.asksaveasfilename(
                initialfile=initialfile,
                defaultextension=".png",
                filetypes=[("PNG", "*.png")]
            )
            if not filepath:
                return

            img = generate_top8_bracket_image(self.manager, active_store, date_val)
            img.save(filepath)
            messagebox.showinfo("Bracket exportado", f"Imagen guardada:\n{os.path.basename(filepath)}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo exportar la imagen del bracket: {e}")

    def share_pairings_whatsapp(self):
        matches = self.manager.get_current_matches()
        if not matches:
            messagebox.showwarning("Atención", "No hay pareos disponibles para compartir.")
            return

        try:
            active_store = self.store_manager.get_active_store()
            date_val = getattr(self, "date_var", tk.StringVar(value=datetime.now().strftime("%d-%m-%y"))).get()
            img = generate_pairings_image(self.manager, active_store, date_val)

            os.makedirs("output", exist_ok=True)
            fmt_str = self.manager.format_name.lower().replace(" ", "_")
            store_str = active_store.lower().replace(" ", "_")
            filename = f"{store_str}_{fmt_str}_ronda_{self.manager.current_round}_pareos_whatsapp.png"
            filepath = os.path.abspath(os.path.join("output", filename))
            img.save(filepath)

            copied_image = self.copy_image_to_clipboard(img)
            if not copied_image:
                self.clipboard_clear()
                self.clipboard_append(filepath)

            text = f"Pareos {active_store} - {self.manager.format_name} - Ronda {self.manager.current_round}"
            encoded_text = quote(text)
            opened = webbrowser.open(f"whatsapp://send?text={encoded_text}")
            if not opened:
                webbrowser.open(f"https://web.whatsapp.com/send?text={encoded_text}")

            if copied_image:
                messagebox.showinfo(
                    "Compartir por WhatsApp",
                    "WhatsApp fue abierto y la imagen quedó copiada al portapapeles.\nEntra al chat y presiona Ctrl+V para pegarla."
                )
            else:
                messagebox.showwarning(
                    "Compartir por WhatsApp",
                    f"No se pudo copiar la imagen al portapapeles, pero el PNG fue guardado en:\n{filepath}\nLa ruta quedó copiada para que puedas adjuntarla manualmente."
                )
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo preparar el envío por WhatsApp: {e}")

    def copy_image_to_clipboard(self, img):
        try:
            output = io.BytesIO()
            img.convert("RGB").save(output, "BMP")
            dib_data = output.getvalue()[14:]
            output.close()

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            gm_moveable = 0x0002
            cf_dib = 8

            kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
            kernel32.GlobalAlloc.restype = ctypes.c_void_p
            kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
            kernel32.GlobalLock.restype = ctypes.c_void_p
            kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
            kernel32.GlobalUnlock.restype = ctypes.c_int
            kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
            kernel32.GlobalFree.restype = ctypes.c_void_p
            user32.OpenClipboard.argtypes = [ctypes.c_void_p]
            user32.OpenClipboard.restype = ctypes.c_int
            user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
            user32.SetClipboardData.restype = ctypes.c_void_p

            h_global = kernel32.GlobalAlloc(gm_moveable, len(dib_data))
            if not h_global:
                return False

            p_global = kernel32.GlobalLock(h_global)
            if not p_global:
                kernel32.GlobalFree(h_global)
                return False

            ctypes.memmove(p_global, dib_data, len(dib_data))
            kernel32.GlobalUnlock(h_global)

            if not user32.OpenClipboard(None):
                kernel32.GlobalFree(h_global)
                return False

            try:
                user32.EmptyClipboard()
                if not user32.SetClipboardData(cf_dib, h_global):
                    kernel32.GlobalFree(h_global)
                    return False
                h_global = None
                return True
            finally:
                user32.CloseClipboard()
        except Exception as e:
            print("Error copying pairings image to clipboard:", e)
            return False
        
    def report_match(self, match, res):
        match.report(res)
        self.refresh_round_after_result_change(match)
        self.autosave_tournament()
        self.sync_active_room()
        
    def undo_match_ui(self, match):
        self.manager.undo_match(match)
        self.refresh_round_after_result_change(match)
        self.autosave_tournament()
        self.sync_active_room()
        
    def rollback_round_ui(self):
        if messagebox.askyesno("Ronda Anterior", "¡ATENCIÓN! Volver a la ronda anterior DESTRUIRÁ permanentemente los emparejamientos de esta ronda. Sin embargo, los resultados de la ronda anterior se mantendrán intactos para que elijas específicamente cuál modificar. ¿Deseas retroceder?"):
            if self.manager.rollback_round():
                self.autosave_tournament()
                self.show_round_view()

    def rollback_to_setup_ui(self):
        if messagebox.askyesno("Volver a Registro", "Esto borrará los pareos y resultados de la ronda 1, pero mantendrá la lista de inscritos para que puedas corregirla. ¿Deseas volver al registro?"):
            if self.manager.rollback_to_setup():
                self.stop_timer()
                self.time_left = getattr(self, "round_minutes", 50) * 60
                self.autosave_tournament()
                self.show_setup_view()
    def show_drop_dialog(self):
        active_players = sorted([p.name for p in self.manager.players if p.active], key=str.lower)
        if not active_players: return
        
        top = ctk.CTkToplevel(self)
        top.title("Retirar Jugador")
        top.geometry("300x200")
        top.attributes('-topmost', True)
        top.grab_set()
        
        ctk.CTkLabel(top, text="Selecciona jugador a retirar:", text_color="#60a5fa", font=UI_FONT_SMALL).pack(pady=10)
        var = ctk.StringVar(value=active_players[0])
        cb = ctk.CTkOptionMenu(top, variable=var, values=active_players, font=UI_FONT_SMALL, width=250)
        cb.pack(pady=10)
        
        def do_drop():
            if messagebox.askyesno("Confirmar", f"¿Seguro que quieres retirar a {var.get()} del torneo?"):
                self.manager.drop_player(var.get())
                self.autosave_tournament()
                self.show_round_view()
                top.destroy()
                
        ctk.CTkButton(top, text="Retirar", command=do_drop, font=UI_FONT_SMALL, fg_color="#ef4444", hover_color="#b91c1c").pack(pady=10)
        
    def show_swap_dialog(self):
        matches = self.manager.get_current_matches()
        if not matches: return
        
        top = ctk.CTkToplevel(self)
        top.title("Modificar Pareos")
        top.geometry("400x300")
        top.attributes('-topmost', True)
        top.grab_set()
        
        opts = []
        for i, m in enumerate(matches):
            if m.p1: opts.append(f"M{i} - P1: {m.p1.name}")
            if m.p2:
                opts.append(f"M{i} - P2: {m.p2.name}")
            elif m.p1:
                opts.append(f"M{i} - P2: BYE")
            
        ctk.CTkLabel(top, text="Selecciona Jugador A:", text_color="#60a5fa").pack(pady=5)
        var1 = ctk.StringVar(value=opts[0] if opts else "")
        cb1 = ctk.CTkOptionMenu(top, variable=var1, values=opts, width=300)
        cb1.pack(pady=5)
        
        ctk.CTkLabel(top, text="Intercambiar con Jugador B:", text_color="#60a5fa").pack(pady=5)
        var2 = ctk.StringVar(value=opts[1] if len(opts)>1 else opts[0] if opts else "")
        cb2 = ctk.CTkOptionMenu(top, variable=var2, values=opts, width=300)
        cb2.pack(pady=5)
        
        def do_swap():
            v1, v2 = var1.get(), var2.get()
            if not v1 or not v2 or v1 == v2: return
            
            m1_idx = int(v1.split(" ")[0][1:])
            p1_is_left = "P1:" in v1
            
            m2_idx = int(v2.split(" ")[0][1:])
            p2_is_left = "P1:" in v2
            
            if m1_idx == m2_idx:
                messagebox.showerror("Error", "No puedes intercambiar jugadores de la misma mesa.")
                return
                
            if self.manager.swap_pairings(m1_idx, p1_is_left, m2_idx, p2_is_left):
                self.autosave_tournament()
                self.show_round_view()
                top.destroy()
                
        ctk.CTkButton(top, text="Aplicar Cambio", command=do_swap, font=UI_FONT_SMALL).pack(pady=20)
        
    def next_round(self):
        if not self.manager.all_matches_reported():
            messagebox.showwarning("Atención", "Faltan resultados por reportar.")
            return
        self.manager.generate_next_round()
        self.time_left = getattr(self, "round_minutes", 40) * 60
        self.stop_timer()
        self.autosave_tournament()
        self.show_round_view()

    def show_standings_view(self):
        self.stop_setup_room_poll()
        self.sync_active_room(status="FINISHED")

        # Auto-guardar y publicar el torneo completado a SQLite y a la nube
        if not getattr(self, '_tournament_already_published', False):
            try:
                self.save_and_publish_tournament(notify=False)
            except Exception as e_pub:
                print("[TournamentUI] Auto-publish on standings error:", e_pub)

        if getattr(self, "current_view_frame", None):
            old = self.current_view_frame
            self.after(20, lambda o=old: o.destroy() if o.winfo_exists() else None)
        self.current_view_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        buf = self.current_view_frame
            
        ctk.CTkLabel(buf, text="Resultados Finales", font=UI_FONT_BIG, text_color="#60a5fa").pack(pady=20)
        
        bottom_frame = ctk.CTkFrame(buf, fg_color="transparent")
        bottom_frame.pack(side="bottom", fill="x", pady=20)

        final_actions_frame = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        final_actions_frame.pack(anchor="center")
        
        ctk.CTkButton(final_actions_frame, text="☁️ PUBLICAR EN LA WEB Y RANKING", command=lambda: self.save_and_publish_tournament(notify=True), font=UI_FONT_SMALL, width=220, fg_color="#8b5cf6", hover_color="#7c3aed").pack(side="left", padx=5, pady=5)
        ctk.CTkButton(final_actions_frame, text="CREAR POST DEL CAMPEÓN", command=self.open_champion_deck_post, font=UI_FONT_SMALL, width=150).pack(side="left", padx=5, pady=5)
        ctk.CTkButton(final_actions_frame, text="EXPORTAR STANDING PNG", command=self.export_standings_image, font=UI_FONT_SMALL, width=150).pack(side="left", padx=5, pady=5)
        ctk.CTkButton(final_actions_frame, text="EXPORTAR A INSTAGRAM", command=self.export_to_instagram, font=UI_FONT_SMALL, width=170, fg_color="#d946ef", hover_color="#c026d3").pack(side="left", padx=5, pady=5)
        ctk.CTkButton(final_actions_frame, text="COMPARTIR STANDING WHATSAPP", command=self.share_standings_whatsapp, font=UI_FONT_SMALL, width=190).pack(side="left", padx=5, pady=5)
        ctk.CTkButton(final_actions_frame, text="ACTUALIZAR PUNTOS DE LIGA", command=self.export_to_league, font=UI_FONT_SMALL, width=170).pack(side="left", padx=5, pady=5)
        ctk.CTkButton(final_actions_frame, text="CALCULAR PREMIOS", command=self.open_prize_calculator_from_tournament, font=UI_FONT_SMALL, width=130).pack(side="left", padx=5, pady=5)
        ctk.CTkButton(final_actions_frame, text="FINALIZAR TORNEO Y PREPARAR NUEVO", command=self.reset_tournament, font=UI_FONT_SMALL, width=220).pack(side="left", padx=5, pady=5)
        
        if self.manager.current_round > 1:
            ctk.CTkButton(final_actions_frame, text="< DESHACER Y VOLVER A ÚLTIMA RONDA", command=self.rollback_round_ui, font=UI_FONT_SMALL, width=220, fg_color="#ef4444", hover_color="#b91c1c").pack(side="left", padx=5, pady=5)
            
        cols = ("Rank", "Name", "Points", "Rivales%", "2do nivel%", "Nota desempate")
        tree = ttk.Treeview(buf, columns=cols, show="headings", height=15)
        for c in cols:
            tree.heading(c, text=c)
            if c == "Name":
                width = 250
            elif c == "Nota desempate":
                width = 180
            else:
                width = 100
            tree.column(c, width=width)
        tree.pack(side="top", fill="both", expand=True, padx=50)
        
        standings = self.manager.get_standings()
        ranked = self.manager.get_ranked_standings()
        notes = self.manager.get_tiebreaker_notes(standings)
        for i, (rank, p) in enumerate(ranked):
            tree.insert("", "end", values=(rank, p.name, p.points, f"{getattr(p, '_omw', 0):.4f}", f"{getattr(p, '_oomw', 0):.4f}", self.friendly_tiebreaker_note(notes.get(p, ""))))

        buf.pack(fill="both", expand=True)

    def export_to_instagram(self):
        standings = self.manager.get_standings()
        if not standings:
            import tkinter.messagebox as messagebox
            messagebox.showwarning("Atención", "No hay resultados disponibles para exportar.")
            return
        try:
            from instagram_exporter import generate_instagram_caption, save_instagram_image
            from tournament_graphics import generate_standings_image
            import datetime
            import tkinter as tk
            import tkinter.messagebox as messagebox
            import os
            
            date_val = getattr(self, "date_var", tk.StringVar(value=datetime.datetime.now().strftime("%d-%m-%y"))).get()
            fmt_str = getattr(self.manager, "format_name", "Torneo")
            active_store = "Tienda"
            if hasattr(self, "store_manager"):
                active_store = self.store_manager.get_active_store()
            
            img = generate_standings_image(self.manager, active_store, date_val)
            img_path = save_instagram_image(img)
            
            caption = generate_instagram_caption(standings, fmt_str)
            
            self.clipboard_clear()
            self.clipboard_append(caption)
            
            os.startfile(img_path)
            messagebox.showinfo("Exportado a Instagram", f"Imagen guardada en {img_path}.\n\n¡El texto descriptivo ha sido copiado al portapapeles! Listo para pegar en Instagram.")
        except Exception as e:
            import tkinter.messagebox as messagebox
            messagebox.showerror("Error", f"Fallo al exportar para Instagram: {e}")

    def export_standings_image(self):
        standings = self.manager.get_standings()
        if not standings:
            messagebox.showwarning("Atención", "No hay resultados disponibles para exportar.")
            return

        try:
            active_store = self.store_manager.get_active_store()
            import datetime
            from datetime import datetime
            date_val = getattr(self, "date_var", tk.StringVar(value=datetime.now().strftime("%d-%m-%y"))).get()
            fmt_str = self.manager.format_name.lower().replace(" ", "_")
            store_str = active_store.lower().replace(" ", "_")
            initialfile = f"{store_str}_{fmt_str}_standing_final.png"
            filepath = filedialog.asksaveasfilename(
                initialfile=initialfile,
                defaultextension=".png",
                filetypes=[("PNG", "*.png")]
            )
            if not filepath:
                return

            img = generate_standings_image(self.manager, active_store, date_val)
            img.save(filepath)
            messagebox.showinfo("Standing exportado", f"Imagen guardada:\n{os.path.basename(filepath)}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo exportar la imagen del standing: {e}")

    def share_standings_whatsapp(self):
        standings = self.manager.get_standings()
        if not standings:
            messagebox.showwarning("Atención", "No hay resultados disponibles para compartir.")
            return

        try:
            active_store = self.store_manager.get_active_store()
            date_val = getattr(self, "date_var", tk.StringVar(value=datetime.now().strftime("%d-%m-%y"))).get()
            img = generate_standings_image(self.manager, active_store, date_val)

            os.makedirs("output", exist_ok=True)
            fmt_str = self.manager.format_name.lower().replace(" ", "_")
            store_str = active_store.lower().replace(" ", "_")
            filename = f"{store_str}_{fmt_str}_standing_final_whatsapp.png"
            filepath = os.path.abspath(os.path.join("output", filename))
            img.save(filepath)

            copied_image = self.copy_image_to_clipboard(img)
            if not copied_image:
                self.clipboard_clear()
                self.clipboard_append(filepath)

            text = f"Standing final {active_store} - {self.manager.format_name}"
            encoded_text = quote(text)
            opened = webbrowser.open(f"whatsapp://send?text={encoded_text}")
            if not opened:
                webbrowser.open(f"https://web.whatsapp.com/send?text={encoded_text}")

            if copied_image:
                messagebox.showinfo(
                    "Compartir por WhatsApp",
                    "WhatsApp fue abierto y la imagen quedó copiada al portapapeles.\nEntra al chat y presiona Ctrl+V para pegarla."
                )
            else:
                messagebox.showwarning(
                    "Compartir por WhatsApp",
                    f"No se pudo copiar la imagen al portapapeles, pero el PNG fue guardado en:\n{filepath}\nLa ruta quedó copiada para que puedas adjuntarla manualmente."
                )
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo preparar el envío del standing por WhatsApp: {e}")

    def open_prize_calculator_from_tournament(self):
        total_players = len(self.manager.players)
        invited_players = sum(1 for p in self.manager.players if getattr(p, "invited", False))
        if hasattr(self.master, 'open_prize_calculator'):
            self.master.open_prize_calculator(total_players=total_players, prize_groups=self.manager.get_prize_groups(), invited_players=invited_players, return_callback=self.master.open_tournament)

    def open_champion_deck_post(self):
        standings = self.manager.get_standings()
        if not standings:
            messagebox.showwarning("Atención", "No hay resultados para cargar en el generador.")
            return

        if not hasattr(self.master, "open_generator"):
            messagebox.showerror("Error", "No se pudo abrir el YGO Deck Post Generator desde esta ventana.")
            return

        champion = standings[0].name
        active_store = self.store_manager.get_active_store()
        format_name = self.manager.format_name
        raw_date = getattr(self, "date_var", tk.StringVar(value=datetime.now().strftime("%d-%m-%y"))).get()
        date_val = self.format_date_for_deck_post(raw_date)
        event_name = f"Torneo {format_name} - {active_store}"

        self.master.open_generator({
            "champion": champion,
            "event_name": event_name,
            "date_str": date_val,
            "format_name": format_name
        })

    def format_date_for_deck_post(self, date_text):
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d-%m-%y"):
            try:
                return datetime.strptime(date_text, fmt).strftime("%d-%m-%y")
            except ValueError:
                pass
        return date_text
            
    def export_to_league(self):
        if self.exported_to_league:
            messagebox.showwarning("Atencion", "Este torneo ya fue exportado a la liga en esta sesion.")
            return

        try:
            league_path = self.store_manager.get_active_league_db_path()
            active_store = self.store_manager.get_active_store()
            lm = LeagueManager(db_path=league_path, current_format=self.manager.format_name)
            date_val = getattr(self, "date_var", tk.StringVar(value=datetime.now().strftime("%d-%m-%y"))).get()
            standings = self.manager.get_standings()
            ranks = {player: rank for rank, player in self.manager.get_ranked_standings()}
            
            results = []
            for p in standings:
                rank = ranks.get(p, 0)
                placement_points = 0
                if rank == 1:
                    placement_points = 10
                elif rank <= 4:
                    placement_points = 5

                results.append({
                    "name": p.name,
                    "match_pts": p.points,
                    "placement_points": placement_points,
                    "phone": p.phone,
                    "email": p.email
                })
                
            lm.export_tournament_results(date_val, results, profit=getattr(self.manager, 'tournament_profit', 0.0))
            self.exported_to_league = True

            if getattr(self, 'current_scheduled_id', None):
                try:
                    from calendar_manager import CalendarManager
                    self.cursor.execute("SELECT MAX(id) as mid FROM tournaments")
                    last_t = self.cursor.fetchone()
                    real_tid = last_t['mid'] if last_t else None
                    CalendarManager().update_scheduled_status(self.current_scheduled_id, 'FINALIZADO', tournament_id=real_tid)
                except Exception as e:
                    print("Error marking scheduled tournament as finished:", e)

            self.autosave_tournament()
            messagebox.showinfo("Exito", f"Resultados exportados a la liga de {active_store}.")
            if hasattr(self.master, 'open_league'):
                self.master.open_league(self.manager.format_name)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo exportar a la Liga: {e}")

    def reset_tournament(self):
        if messagebox.askyesno("Finalizar", "¿Estás seguro de finalizar este torneo e iniciar uno nuevo?"):
            if not getattr(self, '_tournament_already_published', False):
                try:
                    self.save_and_publish_tournament(notify=False)
                except Exception as e:
                    print("Error saving before reset:", e)

            self.manager = TournamentManager()
            self.exported_to_league = False
            self.time_left = 50 * 60
            self.round_minutes = 40
            self.date_var.set(datetime.now().strftime("%d-%m-%y"))
            self.active_room_code = None
            self._tournament_already_published = False
            self._last_saved_history_filename = None
            self._current_saved_tournament_id = None
            self.stop_timer()
            self.clear_autosave()
            self.show_setup_view()
            
    def update_standings_tree(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        standings = self.manager.get_standings()
        ranked = self.manager.get_ranked_standings()
        notes = self.manager.get_tiebreaker_notes(standings)
        for rank, p in ranked:
            name_display = p.name if p.active else f"{p.name} (Drop)"
            self.tree.insert("", "end", values=(rank, name_display, p.points, f"{getattr(p, '_omw', 0):.4f}", f"{getattr(p, '_oomw', 0):.4f}", self.friendly_tiebreaker_note(notes.get(p, ""))))

    def friendly_tiebreaker_note(self, note):
        if note == "OMW/OOMW":
            return "Rivales / 2do nivel"
        if note == "H2H empatado":
            return "Duelo directo empatado"
        if note.startswith("H2H"):
            return note.replace("H2H", "Duelo directo")
        return note

    def render_match_result_controls(self, match, res_frame):
        for widget in res_frame.winfo_children():
            widget.destroy()

        if match.p1 is None or match.p2 is None:
            ctk.CTkLabel(res_frame, text="⭐ Ronda Libre (BYE +3 PTS)", font=UI_FONT_SMALL, text_color="#fbbf24").pack(side="left", padx=5)
            return

        matches = self.manager.get_current_matches()
        table_num = matches.index(match) + 1 if match in matches else 1

        # Consultar reporte móvil existente en la base de datos de salas
        table_rep = None
        if getattr(self, 'active_room_code', None):
            try:
                from tournament_room_manager import TournamentRoomManager
                trm = TournamentRoomManager()
                room = trm.get_room_by_code(self.active_room_code)
                if room:
                    cursor = trm._get_cursor()
                    cursor.execute("""
                        SELECT * FROM room_match_reports
                        WHERE room_id = ? AND round_num = ? AND table_num = ?
                    """, (room['id'], self.manager.current_round, table_num))
                    row = cursor.fetchone()
                    if row:
                        table_rep = dict(row)
            except Exception:
                pass

        if not match.reported:
            p1_name = match.p1.name if match.p1 else "P1"
            p2_name = match.p2.name if match.p2 else "P2"

            # 1. Alerta si hay reporte pendiente desde el teléfono móvil
            if table_rep and table_rep.get('status') == 'PENDING_CONFIRMATION':
                info_f = ctk.CTkFrame(res_frame, fg_color="#1e293b", border_width=1, border_color="#f59e0b", corner_radius=6)
                info_f.pack(fill="x", pady=(0, 6), padx=2, ipady=3)
                ctk.CTkLabel(info_f, text=f"📱 Móvil: {table_rep['reported_by']} reportó {table_rep['score_p1']}-{table_rep['score_p2']}",
                             font=UI_FONT_SMALL, text_color="#fbbf24").pack(side="left", padx=8)
                ctk.CTkButton(info_f, text=f"✅ Aprobar y Forzar ({table_rep['score_p1']}-{table_rep['score_p2']})",
                              command=lambda m=match, s=f"{table_rep['score_p1']}-{table_rep['score_p2']}": self.organizer_report_match(m, s),
                              font=UI_FONT_SMALL, fg_color="#22c55e", hover_color="#16a34a", text_color="#0f172a", width=145, height=26).pack(side="right", padx=6)
            elif table_rep and table_rep.get('status') == 'DISPUTED':
                disp_f = ctk.CTkFrame(res_frame, fg_color="#450a0a", border_width=1, border_color="#ef4444", corner_radius=6)
                disp_f.pack(fill="x", pady=(0, 6), padx=2, ipady=3)
                ctk.CTkLabel(disp_f, text=f"🚨 ¡MESA EN DISPUTA! Llamaron al Juez ({table_rep['score_p1']}-{table_rep['score_p2']})",
                             font=UI_FONT_SMALL, text_color="#fca5a5").pack(side="left", padx=8)

            # 2. Controles de reporte directo del Organizador (Opción B: 4 botones limpios y claros)
            btn_box = ctk.CTkFrame(res_frame, fg_color="transparent")
            btn_box.pack(fill="x")

            ctk.CTkButton(btn_box, text=f"Gana {p1_name}", command=lambda m=match: self.organizer_report_match(m, "2-0"),
                          font=UI_FONT_SMALL, width=125, height=32, fg_color="#166534", hover_color="#22c55e").pack(side="left", padx=3)
            ctk.CTkButton(btn_box, text=f"Gana {p2_name}", command=lambda m=match: self.organizer_report_match(m, "0-2"),
                          font=UI_FONT_SMALL, width=125, height=32, fg_color="#991b1b", hover_color="#ef4444").pack(side="left", padx=3)
            ctk.CTkButton(btn_box, text="Empate", command=lambda m=match: self.organizer_report_match(m, "1-1"),
                          font=UI_FONT_SMALL, width=80, height=32, fg_color="#854d0e", hover_color="#eab308").pack(side="left", padx=3)
            ctk.CTkButton(btn_box, text="D-Loss", command=lambda m=match: self.organizer_report_match(m, "DOUBLE_LOSS"),
                          font=UI_FONT_SMALL, width=70, height=32, fg_color="#334155", hover_color="#475569").pack(side="left", padx=3)
            return

        result_text = "Ronda perdida por atraso" if match.result_text == "LATE_LOSS" else match.result_text
        ctk.CTkLabel(res_frame, text=f"Resultado: {result_text}", font=UI_FONT, text_color="#4ade80").pack(side="left", padx=5)
        if match.result_text != "LATE_LOSS":
            ctk.CTkButton(res_frame, text="✏️ Corregir", command=lambda m=match: self.show_correct_result_dialog(m),
                          font=UI_FONT_SMALL, width=85, height=28, fg_color="#38bdf8", hover_color="#0284c7", text_color="#0f172a").pack(side="left", padx=4)
            ctk.CTkButton(res_frame, text="↺ Deshacer", command=lambda m=match: self.organizer_undo_match(m),
                          font=UI_FONT_SMALL, width=80, height=28, fg_color="#eab308", hover_color="#ca8a04", text_color="#0f172a").pack(side="left", padx=4)

    def organizer_report_match(self, match, score_str):
        """
        Permite al organizador central asignar o forzar un resultado oficial
        (ideal si un jugador no tiene teléfono, se quedó sin batería o hay una disputa).
        """
        match.report(score_str)

        if getattr(self, 'active_room_code', None):
            try:
                from tournament_room_manager import TournamentRoomManager
                trm = TournamentRoomManager()
                room = trm.get_room_by_code(self.active_room_code)
                if room:
                    matches = self.manager.get_current_matches()
                    tbl = matches.index(match) + 1 if match in matches else 1
                    parts = score_str.replace(" ", "").split("-") if "-" in score_str else ["2", "0"]
                    s1 = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else (2 if score_str == "P1_WIN" else 0)
                    s2 = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else (2 if score_str == "P2_WIN" else 0)
                    if score_str == "DRAW":
                        s1, s2 = 1, 1
                    elif score_str == "DOUBLE_LOSS":
                        s1, s2 = 0, 0

                    trm.submit_match_report(
                        room_code=self.active_room_code,
                        round_num=self.manager.current_round,
                        table_num=tbl,
                        reporter_name="JUEZ / ORGANIZADOR",
                        score_p1=s1,
                        score_p2=s2
                    )
                    trm.confirm_match_report(
                        room_code=self.active_room_code,
                        round_num=self.manager.current_round,
                        table_num=tbl,
                        confirmer_name="JUEZ / ORGANIZADOR"
                    )
            except Exception as e:
                print("[TournamentUI] Error guardando reporte de organizador en sala:", e)

        self.refresh_round_after_result_change(match)
        self.autosave_tournament()
        self.sync_active_room()

    def organizer_undo_match(self, match):
        """
        Deshace un resultado oficial tanto localmente como en la sala web.
        """
        self.undo_match_ui(match)
        if getattr(self, 'active_room_code', None):
            try:
                from tournament_room_manager import TournamentRoomManager
                trm = TournamentRoomManager()
                room = trm.get_room_by_code(self.active_room_code)
                if room:
                    matches = self.manager.get_current_matches()
                    tbl = matches.index(match) + 1 if match in matches else 1
                    cursor = trm._get_cursor()
                    cursor.execute("""
                        DELETE FROM room_match_reports
                        WHERE room_id = ? AND round_num = ? AND table_num = ?
                    """, (room['id'], self.manager.current_round, tbl))
                    if hasattr(cursor, 'connection') and cursor.connection:
                        cursor.connection.commit()
            except Exception as e:
                print("[TournamentUI] Error eliminando reporte de sala al deshacer:", e)
        self.sync_active_room()

    def show_correct_result_dialog(self, match):
        """
        Diálogo para que el organizador corrija rápidamente un marcador reportado.
        """
        p1_name = match.p1.name if match.p1 else "P1"
        p2_name = match.p2.name if match.p2 else "P2"

        top = ctk.CTkToplevel(self)
        top.title(f"Corregir Marcador - {p1_name} vs {p2_name}")
        top.geometry("380x280")
        top.configure(fg_color="#0f172a")
        top.transient(self)
        top.grab_set()

        ctk.CTkLabel(top, text="✏️ CORREGIR RESULTADO OFICIAL", font=("Orbitron", 13, "bold"), text_color="#38bdf8").pack(pady=(15, 4))
        ctk.CTkLabel(top, text=f"{p1_name}  vs  {p2_name}", font=UI_FONT, text_color="#ffffff").pack(pady=(0, 10))
        ctk.CTkLabel(top, text="Selecciona el nuevo marcador definitivo:", font=UI_FONT_SMALL, text_color="#94a3b8").pack(pady=(0, 12))

        btn_grid = ctk.CTkFrame(top, fg_color="transparent")
        btn_grid.pack(pady=5)

        scores = [
            (f"2 - 0 ({p1_name[:10]})", "2-0"),
            (f"2 - 1 ({p1_name[:10]})", "2-1"),
            (f"1 - 2 ({p2_name[:10]})", "1-2"),
            (f"0 - 2 ({p2_name[:10]})", "0-2"),
            ("1 - 1 (Empate)", "1-1"),
            ("Double Loss", "DOUBLE_LOSS")
        ]

        def apply_new_score(sc):
            top.destroy()
            self.manager.undo_match(match)
            self.organizer_report_match(match, sc)

        for i, (label, val) in enumerate(scores):
            r = i // 2
            c = i % 2
            ctk.CTkButton(btn_grid, text=label, font=UI_FONT_SMALL, width=160, height=34,
                          fg_color="#1e293b", hover_color="#38bdf8",
                          command=lambda s=val: apply_new_score(s)).grid(row=r, column=c, padx=5, pady=4)

        ctk.CTkButton(top, text="Cancelar", font=UI_FONT_SMALL, fg_color="transparent",
                      hover_color="#334155", command=top.destroy).pack(pady=10)

    def update_round_advance_button(self):
        if not hasattr(self, "round_advance_btn") or not self.round_advance_btn.winfo_exists():
            return

        btn_text = "Finalizar Torneo" if self.manager.current_round >= self.manager.total_rounds else "Siguiente Ronda"
        self.round_advance_btn.configure(text=btn_text)
        if self.manager.all_matches_reported():
            if not self.round_advance_btn.winfo_ismapped():
                self.round_advance_btn.pack(side="right", padx=(0, 20))
        else:
            self.round_advance_btn.pack_forget()

    def refresh_round_after_result_change(self, match):
        res_frame = getattr(self, "match_result_frames", {}).get(match)
        if res_frame and res_frame.winfo_exists():
            self.render_match_result_controls(match, res_frame)
        else:
            self.show_round_view()
            return

        if hasattr(self, "tree") and self.tree.winfo_exists():
            self.update_standings_tree()

        self.update_round_advance_button()

        if self.manager.all_matches_reported():
            self.stop_timer()
            if hasattr(self, "timer_btn") and self.timer_btn.winfo_exists():
                self.timer_btn.configure(text="PLAY")

    def toggle_timer(self):
        if self.timer_running:
            self.sync_time_left_from_deadline()
            self.stop_timer()
            self.timer_btn.configure(text="PLAY")
            self.autosave_tournament()
            self.sync_active_room()
        else:
            self.cancel_timer_job()
            self.timer_running = True
            self.timer_deadline = time.monotonic() + max(0, self.time_left)
            self.last_timer_autosave = self.time_left
            self.timer_warnings_spoken = set()
            self.timer_btn.configure(text="PAUSE")
            self.autosave_tournament()
            self.sync_active_room()
            self.speak_warning("Duelistas, pueden comenzar")
            self.tick_timer()

    def cancel_timer_job(self):
        if self.timer_job:
            try:
                self.after_cancel(self.timer_job)
            except Exception:
                pass
            self.timer_job = None

    def stop_timer(self):
        self.timer_running = False
        self.timer_deadline = None
        self.last_timer_autosave = None
        self.timer_warnings_spoken = set()
        self.cancel_timer_job()
        self.sync_active_room()

    def sync_time_left_from_deadline(self):
        if self.timer_deadline is None:
            return

        self.time_left = max(0, int(round(self.timer_deadline - time.monotonic())))
            
    def speak_warning(self, text):
        if getattr(self, 'audio_muted', False):
            return
            
        def _speak():
            try:
                engine = pyttsx3.init()
                voices = engine.getProperty('voices')
                for voice in voices:
                    name = voice.name.lower()
                    if "zira" in name or "helena" in name or "sabina" in name or "female" in name or "mujer" in name:
                        engine.setProperty('voice', voice.id)
                        break
                engine.say(text)
                engine.runAndWait()
            except Exception as e:
                print("TTS Error:", e)
                    
        threading.Thread(target=_speak, daemon=True).start()

    def tick_timer(self):
        if not self.timer_running:
            return
        self.sync_time_left_from_deadline()
        if self.time_left > 0:
            m, s = divmod(self.time_left, 60)
            if hasattr(self, "timer_label") and self.timer_label.winfo_exists():
                self.timer_label.configure(text=f"{m:02d}:{s:02d}")
            if self.time_left % 30 == 0 and self.time_left != self.last_timer_autosave:
                self.last_timer_autosave = self.time_left
                self.autosave_tournament()

            if self.time_left % 5 == 0 and getattr(self, 'last_synced_second', None) != self.time_left:
                self.last_synced_second = self.time_left
                self.sync_active_room()
            
            if self.time_left == 5 * 60 and self.time_left not in self.timer_warnings_spoken:
                self.timer_warnings_spoken.add(self.time_left)
                self.speak_warning("Duelistas, quedan 5 minutos")
            elif self.time_left == 1 * 60 and self.time_left not in self.timer_warnings_spoken:
                self.timer_warnings_spoken.add(self.time_left)
                self.speak_warning("Duelistas, queda 1 minuto")
                
            self.timer_job = self.after(250, self.tick_timer)
        else:
            self.stop_timer()
            if hasattr(self, "timer_btn") and self.timer_btn.winfo_exists():
                self.timer_btn.configure(text="PLAY")
            self.speak_warning("Se acabó el tiempo, los jugadores que sigan jugando tendrán un double Loss")
            try:
                if not getattr(self, 'audio_muted', False):
                    winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS | winsound.SND_ASYNC)
            except:
                pass
            messagebox.showinfo("Tiempo", "¡Se ha acabado el tiempo de la ronda!")



    def show_late_player_dialog(self):
        if self.manager.status != "running":
            messagebox.showinfo("Aviso", "El torneo no está en curso.")
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Añadir Jugador Atrasado")
        dialog.geometry("300x350")
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Nombre del Jugador:", text_color="#60a5fa", font=UI_FONT_SMALL).pack(anchor="w", padx=20, pady=(10, 0))
        name_entry = ctk.CTkEntry(dialog, font=UI_FONT)
        name_entry.pack(fill="x", padx=20, pady=(0, 10))

        ctk.CTkLabel(dialog, text="Konami ID (Opcional):", text_color="#60a5fa", font=UI_FONT_SMALL).pack(anchor="w", padx=20)
        id_entry = ctk.CTkEntry(dialog, font=UI_FONT)
        id_entry.pack(fill="x", padx=20, pady=(0, 10))

        paid_var = ctk.BooleanVar(value=False)
        paid_chk = ctk.CTkCheckBox(dialog, text="Pagado", variable=paid_var, text_color="#60a5fa", font=UI_FONT_SMALL)
        paid_chk.pack(anchor="w", padx=20, pady=(0, 5))

        invited_var = ctk.BooleanVar(value=False)
        invited_chk = ctk.CTkCheckBox(dialog, text="Invitado", variable=invited_var, text_color="#60a5fa", font=UI_FONT_SMALL)
        invited_chk.pack(anchor="w", padx=20, pady=(0, 10))

        def on_submit():
            name = name_entry.get().strip()
            if not name:
                messagebox.showerror("Error", "El nombre es obligatorio.", parent=dialog)
                return
                
            round_mins = getattr(self, "round_minutes", 40)
            if not self.timer_running and self.time_left == round_mins * 60:
                penalty = False
            else:
                elapsed_seconds = (round_mins * 60) - self.time_left
                penalty = elapsed_seconds > (5 * 60)
            
            p, status, match = self.manager.add_late_player(
                name, id_entry.get().strip(), "", "", paid_var.get(), invited_var.get(), penalty=penalty
            )
            self.autosave_tournament()
            self.show_round_view()
            dialog.destroy()
            messagebox.showinfo("Jugador Añadido", f"{name} añadido.", parent=self)

        ctk.CTkButton(dialog, text="AÑADIR", command=on_submit, font=UI_FONT).pack(pady=20)
