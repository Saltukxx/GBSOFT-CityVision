"""FlightHub 2 client, trajectory conversion and the mock server.

The client talks real HTTP to the mock rather than a patched opener, so header auth,
the {code,message,data} envelope and media download are all exercised end to end.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cityvision.flighthub.client import FlightHubClient, FlightHubError, video_media
from cityvision.flighthub.config import (
    CONFIRMED_ENDPOINTS,
    PROVISIONAL_ENDPOINTS,
    config_for,
    load_flighthub_config,
)
from cityvision.flighthub.mock import MockFlightHub, _route_patterns
from cityvision.flighthub.trajectory import (
    extract_points,
    parse_trajectory,
    write_gps_sidecar,
)
from cityvision.geo.gps import interpolate_gps, load_gps_sidecar


class TestFlightHubConfig(unittest.TestCase):
    def test_url_builds_prefix_and_path_args(self):
        config = config_for("https://fh.example.com/", user_token="k", project_uuid="p")
        self.assertEqual(
            config.url("project"),
            "https://fh.example.com/openapi/v0.1/project",
        )
        self.assertEqual(
            config.url("flight_task", task_uuid="abc"),
            "https://fh.example.com/openapi/v0.1/flight-task/abc",
        )

    def test_project_header_only_when_scoped(self):
        config = config_for("http://x", user_token="k", project_uuid="p")
        self.assertEqual(config.headers(project_scoped=True)["X-Project-Uuid"], "p")
        self.assertNotIn("X-Project-Uuid", config.headers(project_scoped=False))
        self.assertEqual(config.headers(project_scoped=True)["X-User-Token"], "k")

    def test_unknown_endpoint_is_loud(self):
        config = config_for("http://x", user_token="k")
        with self.assertRaises(KeyError):
            config.url("no_such_endpoint")

    def test_missing_credentials_name_the_env_vars(self):
        config = config_for("", user_token="")
        with self.assertRaises(RuntimeError) as ctx:
            config.require()
        self.assertIn("CITYVISION_FH2_BASE_URL", str(ctx.exception))
        self.assertIn("CITYVISION_FH2_USER_TOKEN", str(ctx.exception))

    def test_endpoint_override_from_env(self):
        key = "CITYVISION_FH2_EP_FLIGHT_TASK_MEDIA"
        previous = os.environ.get(key)
        os.environ[key] = "/v2/task/{task_uuid}/files"
        try:
            config = load_flighthub_config()
            self.assertEqual(config.endpoints["flight_task_media"], "/v2/task/{task_uuid}/files")
        finally:
            if previous is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous

    def test_endpoint_groups_do_not_overlap(self):
        self.assertFalse(set(CONFIRMED_ENDPOINTS) & set(PROVISIONAL_ENDPOINTS))


class TestTrajectory(unittest.TestCase):
    def test_epoch_millis_rebased_onto_video_clock(self):
        payload = {
            "list": [
                {"timestamp": 1_755_000_001_000, "latitude": 39.9, "longitude": 41.2},
                {"timestamp": 1_755_000_002_000, "latitude": 39.91, "longitude": 41.21},
            ]
        }
        fixes = parse_trajectory(payload)
        self.assertEqual([f.timestamp_ms for f in fixes], [0.0, 1000.0])

    def test_epoch_seconds_scaled_to_millis(self):
        payload = [
            {"time": 1_755_000_000, "lat": 39.9, "lng": 41.2},
            {"time": 1_755_000_003, "lat": 39.9, "lng": 41.2},
        ]
        fixes = parse_trajectory(payload)
        self.assertEqual([f.timestamp_ms for f in fixes], [0.0, 3000.0])

    def test_explicit_start_ms_wins(self):
        payload = [{"timestamp": 1_755_000_005_000, "lat": 39.9, "lon": 41.2}]
        fixes = parse_trajectory(payload, start_ms=1_755_000_000_000)
        self.assertEqual(fixes[0].timestamp_ms, 5000.0)

    def test_points_before_start_are_dropped(self):
        payload = [
            {"timestamp": 1_755_000_000_000, "lat": 39.9, "lon": 41.2},
            {"timestamp": 1_755_000_004_000, "lat": 39.9, "lon": 41.2},
        ]
        fixes = parse_trajectory(payload, start_ms=1_755_000_002_000)
        self.assertEqual([f.timestamp_ms for f in fixes], [2000.0])

    def test_zero_island_and_incomplete_rows_skipped(self):
        payload = {
            "points": [
                {"timestamp": 1000, "latitude": 0.0, "longitude": 0.0},
                {"timestamp": 2000, "latitude": 39.9},
                {"timestamp": 3000, "latitude": 39.9, "longitude": 41.2},
            ]
        }
        fixes = parse_trajectory(payload)
        self.assertEqual(len(fixes), 1)
        self.assertEqual(fixes[0].lat, 39.9)

    def test_speed_and_heading_key_aliases(self):
        payload = [
            {"timestamp": 0, "lat": 39.9, "lon": 41.2, "horizontal_speed": 4.5, "yaw": 91.0}
        ]
        fix = parse_trajectory(payload)[0]
        self.assertEqual(fix.speed, 4.5)
        self.assertEqual(fix.heading, 91.0)

    def test_extract_points_walks_nested_envelope(self):
        self.assertEqual(len(extract_points({"data": {"list": [{"a": 1}, {"b": 2}]}})), 2)
        self.assertEqual(extract_points({"data": {}}), [])
        self.assertEqual(extract_points("nope"), [])

    def test_sidecar_roundtrips_through_pipeline_loader(self):
        payload = [
            {"timestamp": 1_755_000_000_000, "lat": 39.90, "lon": 41.20, "speed": 5.0},
            {"timestamp": 1_755_000_002_000, "lat": 39.92, "lon": 41.22, "speed": 5.0},
        ]
        fixes = parse_trajectory(payload)
        with tempfile.TemporaryDirectory() as tmp:
            dest = write_gps_sidecar(fixes, Path(tmp) / "gps.jsonl")
            reloaded = load_gps_sidecar(dest)
        self.assertEqual(len(reloaded), 2)
        middle = interpolate_gps(reloaded, 1000.0, max_gap_ms=2000.0)
        self.assertIsNotNone(middle)
        self.assertAlmostEqual(middle.lat, 39.91, places=5)


class TestMediaFilter(unittest.TestCase):
    def test_keeps_video_drops_stills(self):
        media = [
            {"name": "a", "file_type": "video", "suffix": ".mp4"},
            {"name": "b", "file_type": "image", "suffix": ".jpeg"},
            {"name": "c", "suffix": ".MOV"},
            {"name": "d.mp4"},
        ]
        self.assertEqual([m["name"] for m in video_media(media)], ["a", "c", "d.mp4"])


class TestClientAgainstMock(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.video = Path(cls.tmp.name) / "DJI_20260817_0001.mp4"
        cls.video.write_bytes(b"fake-mp4-payload" * 64)
        cls.mock = MockFlightHub(video_path=cls.video).start()
        cls.client = FlightHubClient(cls.mock.config())

    @classmethod
    def tearDownClass(cls):
        cls.mock.stop()
        cls.tmp.cleanup()

    def test_system_status_is_unscoped(self):
        self.assertEqual(self.client.system_status()["status"], "normal")

    def test_project_list_unwraps_data_list(self):
        projects = self.client.list_projects()
        self.assertEqual(projects[0]["uuid"], self.mock.project_uuid)

    def test_flight_task_and_media(self):
        task = self.client.get_flight_task(self.mock.task_uuid)
        self.assertEqual(task["status"], "success")
        self.assertEqual(task["dock_sn"], "MOCKDOCK0001")
        media = video_media(self.client.get_task_media(self.mock.task_uuid))
        self.assertEqual(len(media), 1)
        self.assertTrue(media[0]["original_url"].endswith(self.video.name))

    def test_trajectory_converts_to_video_clock(self):
        task = self.client.get_flight_task(self.mock.task_uuid)
        fixes = parse_trajectory(
            self.client.get_task_trajectory(self.mock.task_uuid),
            start_ms=task["begin_time"],
        )
        self.assertEqual(len(fixes), self.mock.trajectory_points)
        self.assertEqual(fixes[0].timestamp_ms, 0.0)
        self.assertEqual(fixes[1].timestamp_ms, float(self.mock.trajectory_step_ms))

    def test_media_download_matches_source_bytes(self):
        media = self.client.get_task_media(self.mock.task_uuid)[0]
        with tempfile.TemporaryDirectory() as tmp:
            dest = self.client.download_to(media["original_url"], Path(tmp) / "out.mp4")
            self.assertEqual(dest.read_bytes(), self.video.read_bytes())

    def test_bad_token_raises_flighthub_error(self):
        config = self.mock.config()
        config.user_token = "wrong"
        client = FlightHubClient(config)
        with self.assertRaises(FlightHubError) as ctx:
            client.list_projects()
        self.assertEqual(ctx.exception.http_status, 401)

    def test_unreachable_host_raises_flighthub_error(self):
        # Port 9 (discard) refuses connections without a DNS round trip.
        client = FlightHubClient(config_for("http://127.0.0.1:9", user_token="k"))
        with self.assertRaises(FlightHubError):
            client.system_status()

    def test_nonzero_envelope_code_raises(self):
        config = self.mock.config()
        config.endpoints["project"] = "/nope"
        client = FlightHubClient(config)
        with self.assertRaises(FlightHubError) as ctx:
            client.list_projects()
        self.assertEqual(ctx.exception.http_status, 404)

    def test_mock_routes_follow_config_overrides(self):
        mock = MockFlightHub(video_path=self.video)
        mock._config.endpoints["flight_task"] = "/custom/{task_uuid}"
        mock._routes = _route_patterns(mock._config)
        with mock:
            config = mock.config()
            config.endpoints["flight_task"] = "/custom/{task_uuid}"
            client = FlightHubClient(config)
            self.assertEqual(client.get_flight_task("t-9")["task_uuid"], "t-9")


if __name__ == "__main__":
    unittest.main()
