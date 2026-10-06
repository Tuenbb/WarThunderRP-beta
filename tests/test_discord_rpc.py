import importlib
import sys
import types
import unittest
from unittest.mock import patch


class _FakePresence:
    def __init__(self) -> None:
        self.updates: list[dict[str, object]] = []

    def update(self, **kwargs: object) -> None:
        self.updates.append(kwargs)
        if len(self.updates) == 1:
            raise ValueError("remote image rejected")


class _AcceptingPresence:
    def __init__(self) -> None:
        self.updates: list[dict[str, object]] = []

    def update(self, **kwargs: object) -> None:
        self.updates.append(kwargs)


class _RejectingImagePresence:
    def __init__(self) -> None:
        self.updates: list[dict[str, object]] = []

    def update(self, **kwargs: object) -> None:
        self.updates.append(kwargs)
        if "large_image" in kwargs or "small_image" in kwargs:
            raise ValueError("asset key rejected")


class _RejectingLargeImagePresence:
    def __init__(self) -> None:
        self.updates: list[dict[str, object]] = []

    def update(self, **kwargs: object) -> None:
        self.updates.append(kwargs)
        if "large_image" in kwargs:
            raise ValueError("large image rejected")


class DiscordRpcFallbackTests(unittest.TestCase):
    def test_retries_presence_without_rejected_remote_vehicle_image(self) -> None:
        fake_module = types.ModuleType("pypresence")
        fake_module.Presence = lambda _client_id: None
        with patch.dict(sys.modules, {"pypresence": fake_module}):
            discord_rpc = importlib.import_module("discord_rpc")

        client = discord_rpc.DiscordRpcClient()
        presence = _FakePresence()
        client._client = presence
        client.connected = True

        self.assertTrue(
            client.update(
                "123",
                "In battle / USS Example",
                vehicle_name="USS Example",
                vehicle_image_url="https://example.invalid/ship.png",
                flag_asset_key="country_israel",
                flag_name="Izrael",
            )
        )

        self.assertEqual(len(presence.updates), 2)
        self.assertNotIn("details", presence.updates[0])
        self.assertEqual(
            presence.updates[0]["state"],
            "In battle / USS Example",
        )
        self.assertIn("large_image", presence.updates[0])
        self.assertEqual(presence.updates[0]["large_text"], "USS Example")
        self.assertEqual(presence.updates[0]["small_image"], "country_israel")
        self.assertEqual(presence.updates[0]["small_text"], "Izrael")
        self.assertNotIn("large_image", presence.updates[1])
        self.assertEqual(presence.updates[1]["small_image"], "country_israel")
        self.assertEqual(presence.updates[1]["small_text"], "Izrael")

    def test_hangar_swedish_vehicle_payload_and_fallback(self) -> None:
        fake_module = types.ModuleType("pypresence")
        fake_module.Presence = lambda _client_id: None
        with patch.dict(sys.modules, {"pypresence": fake_module}):
            discord_rpc = importlib.import_module("discord_rpc")

        client = discord_rpc.DiscordRpcClient()
        presence = _FakePresence()
        client._client = presence
        client.connected = True

        self.assertTrue(
            client.update(
                "123",
                None,
                details="W hangarze",
                vehicle_image_url=(
                    "https://static.encyclopedia.warthunder.com/"
                    "images/sw_t_80u.png"
                ),
                vehicle_name="T 80 U",
                flag_asset_key="country_sweden",
                flag_name="Szwecja",
            )
        )
        self.assertEqual(
            presence.updates[0],
            {
                "details": "W hangarze",
                "state": "\u2800",
                "large_image": (
                    "https://static.encyclopedia.warthunder.com/"
                    "images/sw_t_80u.png"
                ),
                "large_text": "T 80 U",
                "small_image": "country_sweden",
                "small_text": "Szwecja",
            },
        )
        self.assertEqual(
            presence.updates[1],
            {
                "details": "W hangarze",
                "state": "\u2800",
                "small_image": "country_sweden",
                "small_text": "Szwecja",
            },
        )
        self.assertEqual(
            client.last_update_warning,
            "częściowy fallback (flag)",
        )
        self.assertEqual(client.last_image_result, "flag")

    def test_fallback_keeps_flag_when_vehicle_image_is_rejected(self) -> None:
        fake_module = types.ModuleType("pypresence")
        fake_module.Presence = lambda _client_id: None
        with patch.dict(sys.modules, {"pypresence": fake_module}):
            discord_rpc = importlib.import_module("discord_rpc")

        client = discord_rpc.DiscordRpcClient()
        presence = _RejectingLargeImagePresence()
        client._client = presence
        client.connected = True

        self.assertTrue(
            client.update(
                "123",
                "T 80 U",
                details="W bitwie",
                vehicle_asset_key="t_80u",
                vehicle_image_url="https://example.invalid/tank.png",
                vehicle_name="T 80 U",
                flag_asset_key="country_sweden",
                flag_name="Szwecja",
            )
        )
        self.assertIn("large_image", presence.updates[0])
        self.assertEqual(
            presence.updates[-1]["small_image"],
            "country_sweden",
        )
        self.assertNotIn("large_image", presence.updates[-1])
        self.assertEqual(client.last_image_result, "flag")
        self.assertEqual(
            client.last_update_warning,
            "częściowy fallback (flag)",
        )

    def test_hangar_image_only_payload_without_state_line_is_sent(self) -> None:
        fake_module = types.ModuleType("pypresence")
        fake_module.Presence = lambda _client_id: None
        with patch.dict(sys.modules, {"pypresence": fake_module}):
            discord_rpc = importlib.import_module("discord_rpc")

        client = discord_rpc.DiscordRpcClient()
        presence = _AcceptingPresence()
        client._client = presence
        client.connected = True

        self.assertTrue(
            client.update(
                "123",
                None,
                details="W hangarze",
                vehicle_image_url=(
                    "https://static.encyclopedia.warthunder.com/"
                    "images/sw_t_80u.png"
                ),
                vehicle_name="T 80 U",
                flag_asset_key="country_sweden",
                flag_name="Szwecja",
            )
        )
        self.assertEqual(
            presence.updates,
            [
                {
                    "details": "W hangarze",
                    "state": "\u2800",
                    "large_image": (
                        "https://static.encyclopedia.warthunder.com/"
                        "images/sw_t_80u.png"
                    ),
                    "large_text": "T 80 U",
                    "small_image": "country_sweden",
                    "small_text": "Szwecja",
                }
            ],
        )

    def test_empty_state_is_sent_with_images_without_vehicle_text(self) -> None:
        fake_module = types.ModuleType("pypresence")
        fake_module.Presence = lambda _client_id: None
        with patch.dict(sys.modules, {"pypresence": fake_module}):
            discord_rpc = importlib.import_module("discord_rpc")

        client = discord_rpc.DiscordRpcClient()
        presence = _AcceptingPresence()
        client._client = presence
        client.connected = True

        self.assertTrue(
            client.update(
                "123",
                None,
                details="W hangarze",
                vehicle_image_url="https://example.invalid/tank.png",
                vehicle_name="T 80 U",
                flag_asset_key="country_sweden",
                flag_name="Szwecja",
            )
        )
        self.assertEqual(
            presence.updates,
            [
                {
                    "details": "W hangarze",
                    "state": "\u2800",
                    "large_image": "https://example.invalid/tank.png",
                    "large_text": "T 80 U",
                    "small_image": "country_sweden",
                    "small_text": "Szwecja",
                }
            ],
        )

    def test_rejected_image_assets_fall_back_to_text_presence(self) -> None:
        fake_module = types.ModuleType("pypresence")
        fake_module.Presence = lambda _client_id: None
        with patch.dict(sys.modules, {"pypresence": fake_module}):
            discord_rpc = importlib.import_module("discord_rpc")

        client = discord_rpc.DiscordRpcClient()
        presence = _RejectingImagePresence()
        client._client = presence
        client.connected = True

        self.assertTrue(
            client.update(
                "123",
                None,
                details="W hangarze",
                vehicle_image_url="https://example.invalid/tank.png",
                vehicle_name="T 80 U",
                flag_asset_key="country_sweden",
                flag_name="Szwecja",
            )
        )
        self.assertEqual(presence.updates[-1], {"details": "W hangarze"})

    def test_disabled_state_without_image_assets_is_omitted(self) -> None:
        fake_module = types.ModuleType("pypresence")
        fake_module.Presence = lambda _client_id: None
        with patch.dict(sys.modules, {"pypresence": fake_module}):
            discord_rpc = importlib.import_module("discord_rpc")

        client = discord_rpc.DiscordRpcClient()
        presence = _AcceptingPresence()
        client._client = presence
        client.connected = True

        self.assertTrue(
            client.update(
                "123",
                None,
                details="Loading",
            )
        )
        self.assertEqual(presence.updates, [{"details": "Loading"}])

    def test_publish_omits_each_disabled_line_and_preserves_images(self) -> None:
        fake_module = types.ModuleType("pypresence")
        fake_module.Presence = lambda _client_id: None
        with patch.dict(sys.modules, {"pypresence": fake_module}):
            discord_rpc = importlib.import_module("discord_rpc")

        client = discord_rpc.DiscordRpcClient()
        presence = _AcceptingPresence()
        client._client = presence
        client.connected = True

        self.assertTrue(
            client.update(
                "123",
                None,
                details=None,
                vehicle_asset_key="vehicle_key",
                flag_asset_key="country_israel",
                flag_name="Izrael",
            )
        )
        self.assertEqual(
            presence.updates,
            [
                {
                    "state": "\u2800",
                    "large_image": "vehicle_key",
                    "small_image": "country_israel",
                    "small_text": "Izrael",
                }
            ],
        )

    def test_custom_second_line_keeps_vehicle_and_nation_images(self) -> None:
        fake_module = types.ModuleType("pypresence")
        fake_module.Presence = lambda _client_id: None
        with patch.dict(sys.modules, {"pypresence": fake_module}):
            discord_rpc = importlib.import_module("discord_rpc")

        client = discord_rpc.DiscordRpcClient()
        presence = _AcceptingPresence()
        client._client = presence
        client.connected = True

        self.assertTrue(
            client.update(
                "123",
                "Custom second line",
                details="Custom first line",
                vehicle_asset_key="vehicle_key",
                vehicle_name="USS Example",
                flag_asset_key="country_israel",
                flag_name="Izrael",
            )
        )
        self.assertEqual(
            presence.updates,
            [
                {
                    "details": "Custom first line",
                    "state": "Custom second line",
                    "large_image": "vehicle_key",
                    "large_text": "USS Example",
                    "small_image": "country_israel",
                    "small_text": "Izrael",
                }
            ],
        )

    def test_publish_accepts_custom_first_and_second_lines(self) -> None:
        fake_module = types.ModuleType("pypresence")
        fake_module.Presence = lambda _client_id: None
        with patch.dict(sys.modules, {"pypresence": fake_module}):
            discord_rpc = importlib.import_module("discord_rpc")

        client = discord_rpc.DiscordRpcClient()
        presence = _AcceptingPresence()
        client._client = presence
        client.connected = True

        self.assertTrue(
            client.update(
                "123",
                "Custom state",
                details="Custom details",
            )
        )
        self.assertEqual(
            presence.updates,
            [{"details": "Custom details", "state": "Custom state"}],
        )


if __name__ == "__main__":
    unittest.main()
