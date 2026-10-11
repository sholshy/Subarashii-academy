import unittest
import json
import os
from public_web import app
from tournament_room_manager import TournamentRoomManager
from remote_sync_client import RemoteSyncClient

class TestRemoteAndDropFlow(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.trm = TournamentRoomManager()
        self.room_code = "TESTDROP"
        self.trm.create_or_get_room(title="Torneo Test Drops & Hosting", format_name="EDISON", room_code=self.room_code)

    def test_drop_flow_and_rules(self):
        # 1. Registrar a dos jugadores en la sala
        ok1, res1 = self.trm.register_player(self.room_code, "Yugi Muto", session_token="tok_yugi_123")
        self.assertTrue(ok1)
        ok2, res2 = self.trm.register_player(self.room_code, "Seto Kaiba", session_token="tok_kaiba_456")
        self.assertTrue(ok2)

        # 2. Intentar dropear sin credenciales (debe fallar 400)
        resp_bad = self.app.post(f'/api/room/{self.room_code}/drop', json={})
        self.assertEqual(resp_bad.status_code, 400)

        # 3. Yugi solicita Drop con credenciales válidas
        drop_payload = {
            "player_name": "Yugi Muto",
            "session_token": "tok_yugi_123",
            "round_num": 1
        }
        resp_drop = self.app.post(f'/api/room/{self.room_code}/drop', json=drop_payload)
        self.assertEqual(resp_drop.status_code, 200)
        data = resp_drop.get_json()
        self.assertTrue(data['success'])
        self.assertIn("retirado", data['message'].lower())

        # 4. Verificar que aparezca en la lista de jugadores dropeados de la sala
        drops = self.trm.get_room_dropped_players(self.room_code)
        dropped_names = [d['player_name'] for d in drops]
        self.assertIn("Yugi Muto", dropped_names)

        # 5. Endpoint público de status de la sala debe incluir los drops
        resp_status = self.app.get(f'/api/room/{self.room_code}/status')
        self.assertEqual(resp_status.status_code, 200)
        status_data = resp_status.get_json()['data']
        self.assertIn("dropped_players", status_data)
        status_dropped_names = [d['player_name'] for d in status_data['dropped_players']]
        self.assertIn("Yugi Muto", status_dropped_names)

    def test_organizer_authentication_security(self):
        # 1. Ping sin autenticación -> debe dar 401
        resp_unauth = self.app.get('/api/organizer/ping')
        self.assertEqual(resp_unauth.status_code, 401)

        # 2. Ping con token incorrecto -> debe dar 401
        headers_bad = {"Authorization": "Bearer clave_totalmente_falsa"}
        resp_bad_token = self.app.get('/api/organizer/ping', headers=headers_bad)
        self.assertEqual(resp_bad_token.status_code, 401)

        # 3. Ping con token correcto de organizador -> debe dar 200
        correct_token = os.environ.get("ORGANIZER_API_KEY", "subarashii_secret_organizer_key_2026")
        headers_good = {"Authorization": f"Bearer {correct_token}"}
        resp_good = self.app.get('/api/organizer/ping', headers=headers_good)
        self.assertEqual(resp_good.status_code, 200)
        ping_data = resp_good.get_json()
        self.assertTrue(ping_data['success'])

        # 4. Sincronización de sala autenticada
        sync_payload = {
            "type": "room_sync",
            "room_code": self.room_code,
            "title": "Torneo Sincronizado",
            "current_round": 2,
            "pairings": [{"table": 1, "p1": "Kaiba", "p2": "Joey"}],
            "standings": [{"rank": 1, "name": "Kaiba", "points": 3}]
        }
        resp_sync = self.app.post('/api/organizer/sync', json=sync_payload, headers=headers_good)
        self.assertEqual(resp_sync.status_code, 200)

        # 5. Consulta de eventos de sala autenticada
        resp_events = self.app.get(f'/api/organizer/events/{self.room_code}', headers=headers_good)
        self.assertEqual(resp_events.status_code, 200)
        events_data = resp_events.get_json()
        self.assertTrue(events_data['success'])
        self.assertEqual(events_data['room_code'], self.room_code)

if __name__ == '__main__':
    unittest.main()
