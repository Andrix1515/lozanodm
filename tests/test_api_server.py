import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api.server import app, command_logger, server_state


class TestAPIServer(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        server_state.update(
            connected=False,
            mode="GESTURE",
            gesture="NONE",
            gripper="OPEN",
            fps=0.0,
            joints={f"joint{i}": 0.0 for i in range(1, 7)},
            last_command="",
        )

    def test_dashboard_route_returns_html(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Robot Dashboard", response.data)

    def test_api_state_returns_expected_fields(self):
        response = self.client.get("/api/state")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("connected", data)
        self.assertIn("mode", data)
        self.assertIn("gesture", data)
        self.assertIn("gripper", data)
        self.assertIn("fps", data)
        self.assertIn("joints", data)
        self.assertIn("last_command", data)
        self.assertIn("uptime_seconds", data)

    def test_api_log_limit_works(self):
        for i in range(12):
            command_logger.log(action=f"test{i}", result="ok", duration_ms=1)
        response = self.client.get("/api/log?limit=5")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(len(data), 5)
        self.assertEqual(data[0]["action"], "test7")

    def test_start_and_stop_macro_record(self):
        response = self.client.post("/api/macro/start_record")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(server_state.recording)

        response = self.client.post("/api/macro/stop_record", json={"name": "test_macro"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(server_state.recording)
        self.assertTrue(os.path.exists(os.path.join(os.path.dirname(__file__), "..", "macros", "test_macro.json")))
        os.remove(os.path.join(os.path.dirname(__file__), "..", "macros", "test_macro.json"))


if __name__ == "__main__":
    unittest.main()
