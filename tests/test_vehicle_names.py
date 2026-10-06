import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vehicle_catalog import (
    apply_detected_nation,
    get_nation_profile,
    get_vehicle_profile,
)
from vehicle_names import (
    _CacheEntry,
    _WikiVehicleParser,
    _read_cache,
    _write_cache,
    VehicleWikiInfo,
    resolve_vehicle_info,
)


class WikiVehicleParserTests(unittest.TestCase):
    def test_reads_nation_from_research_country_card(self) -> None:
        parser = _WikiVehicleParser()
        parser.feed(
            """
            <title>Bardelas/60mm HVMS | War Thunder Wiki</title>
            <div class="game-unit_card-info_item">
              <div class="game-unit_card-info_value">
                <img src="/static/country_svg/country_israel.svg">
                <div>Israel</div>
              </div>
              <div class="game-unit_card-info_title">Research country</div>
            </div>
            """
        )
        parser.close()

        self.assertEqual(parser.title, "Bardelas/60mm HVMS")
        self.assertEqual(parser.nation_id, "israel")

    def test_does_not_guess_nation_from_page_text_or_unknown_country(self) -> None:
        parser = _WikiVehicleParser()
        parser.feed(
            """
            <title>Japanese vehicle | War Thunder Wiki</title>
            <p>The description mentions Japan.</p>
            <div class="game-unit_card-info_item">
              <div class="game-unit_card-info_value">
                <img src="/static/country_svg/country_unknown.svg">
                <div>Unknown</div>
              </div>
              <div class="game-unit_card-info_title">Research country</div>
            </div>
            """
        )
        parser.close()

        self.assertIsNone(parser.nation_id)


class VehicleNameCacheTests(unittest.TestCase):
    def test_resolves_and_caches_name_and_nation_together(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "vehicle_names.json"
            with (
                patch("vehicle_names._cache_path", return_value=path),
                patch(
                    "vehicle_names._fetch_wiki_vehicle_info",
                    return_value=VehicleWikiInfo("Wiki name", "israel"),
                ) as fetch,
            ):
                first = resolve_vehicle_info("tankModels/cache_test", "Fallback")
                second = resolve_vehicle_info("tankModels/cache_test", "Fallback")

        self.assertEqual(first, VehicleWikiInfo("Wiki name", "israel"))
        self.assertEqual(second, first)
        fetch.assert_called_once()

    def test_reads_legacy_name_only_and_new_nation_cache_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "vehicle_names.json"
            path.write_text(
                json.dumps(
                    {
                        "tankModels/legacy": "Legacy name",
                        "tankModels/current": {
                            "name": "Current name",
                            "nation": "israel",
                        },
                    }
                ),
                encoding="utf-8",
            )

            with patch("vehicle_names._cache_path", return_value=path):
                cache = _read_cache()

            self.assertEqual(cache["tankModels/legacy"].name, "Legacy name")
            self.assertFalse(cache["tankModels/legacy"].nation_checked)
            self.assertEqual(cache["tankModels/current"].nation_id, "israel")
            self.assertTrue(cache["tankModels/current"].nation_checked)

    def test_keeps_legacy_entries_compatible_when_saving_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "vehicle_names.json"
            cache = {
                "tankModels/legacy": _CacheEntry("Legacy name", None, False),
                "tankModels/current": _CacheEntry("Current name", "israel", True),
            }

            with patch("vehicle_names._cache_path", return_value=path):
                _write_cache(cache)

            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                {
                    "tankModels/legacy": "Legacy name",
                    "tankModels/current": {
                        "name": "Current name",
                        "nation": "israel",
                    },
                },
            )


class VehicleNationTests(unittest.TestCase):
    def test_detected_nation_selects_registered_asset_key_and_flag_label(self) -> None:
        profile = get_vehicle_profile("tankModels/example_without_prefix")
        self.assertIsNotNone(profile)

        detected = apply_detected_nation(profile, "israel")

        self.assertEqual(detected.flag_asset_key, "country_israel")
        self.assertEqual(detected.flag_name, "Izrael")
        self.assertEqual(detected.flag_emoji, "🇮🇱")
        self.assertEqual(
            detected.flag_image_path.name if detected.flag_image_path else None,
            "country_israel.png",
        )

    def test_catalogued_israeli_vehicle_uses_canonical_discord_flag_key(self) -> None:
        profile = get_vehicle_profile("tankModels/il_m113_hvms")

        self.assertIsNotNone(profile)
        self.assertEqual(profile.flag_asset_key, "country_israel")
        self.assertIsNotNone(profile.flag_image_path)
        self.assertEqual(profile.flag_image_path.stem, profile.flag_asset_key)

    def test_israel_flag_key_matches_conventional_asset_filename(self) -> None:
        nation = get_nation_profile("country_israel")

        self.assertIsNotNone(nation)
        self.assertEqual(nation.flag_asset_key, "country_israel")
        self.assertIsNotNone(nation.flag_image_path)
        self.assertEqual(nation.flag_asset_key, nation.flag_image_path.stem)

    def test_supported_local_flag_keys_do_not_require_image_files(self) -> None:
        for nation_id, expected_key in (
            ("usa", "country_usa"),
            ("germany", "country_germany"),
            ("ussr", "country_ussr"),
            ("britain", "country_britain"),
            ("japan", "country_japan"),
            ("china", "country_china"),
            ("italy", "country_italy"),
            ("france", "country_france"),
            ("sweden", "country_sweden"),
            ("israel", "country_israel"),
        ):
            with self.subTest(nation=nation_id):
                nation = get_nation_profile(nation_id)
                self.assertIsNotNone(nation)
                self.assertEqual(nation.flag_asset_key, expected_key)
                self.assertIsNotNone(nation.flag_image_path)
                self.assertEqual(nation.flag_image_path.stem, expected_key)

    def test_vehicle_id_prefix_does_not_infer_nation(self) -> None:
        profile = get_vehicle_profile("tankModels/germ_example_vehicle")

        self.assertIsNotNone(profile)
        self.assertIsNone(profile.flag_asset_key)
        self.assertIsNone(profile.flag_name)


class VehicleClassTests(unittest.TestCase):
    def test_category_ids_cover_supported_vehicle_classes(self) -> None:
        cases = (
            ("tankModels/ussr_t_34_85", "ground"),
            ("aircraft/usa_p_51d_30", "aircraft"),
            ("helicopters/ussr_mi_24v", "helicopter"),
            ("ships/ussr_pr_7u", "naval"),
            ("boats/usa_pbr", "naval"),
        )
        for vehicle_id, expected_class in cases:
            with self.subTest(vehicle_id=vehicle_id):
                profile = get_vehicle_profile(vehicle_id)
                self.assertIsNotNone(profile)
                self.assertEqual(profile.vehicle_class, expected_class)
                self.assertEqual(profile.model_id, vehicle_id.rsplit("/", 1)[1])
                self.assertIsNotNone(profile.vehicle_image_url)

    def test_army_classifies_bare_ids_without_guessing_air_subtype(self) -> None:
        cases = (
            ("vehicle_1", "tank", "ground"),
            ("vehicle_2", "air", "air"),
            ("vehicle_3", "helicopter", "helicopter"),
            ("vehicle_4", "ship", "naval"),
        )
        for vehicle_id, army, expected_class in cases:
            with self.subTest(army=army):
                profile = get_vehicle_profile(vehicle_id, army)
                self.assertIsNotNone(profile)
                self.assertEqual(profile.vehicle_class, expected_class)
                self.assertIsNotNone(profile.vehicle_image_url)

    def test_missing_type_keeps_known_class_and_unknown_image_gracefully(self) -> None:
        profile = get_vehicle_profile(None, "ship")

        self.assertIsNotNone(profile)
        self.assertEqual(profile.display_name, "Nieznany okręt")
        self.assertEqual(profile.vehicle_class, "naval")
        self.assertIsNone(profile.vehicle_image_url)
        self.assertIsNone(get_vehicle_profile(None, "unsupported"))

    def test_multi_segment_ids_use_validated_category_and_last_model(self) -> None:
        profile = get_vehicle_profile("vehicles/aircraft/usa_f_16a")

        self.assertIsNotNone(profile)
        self.assertEqual(profile.vehicle_class, "aircraft")
        self.assertEqual(profile.model_id, "usa_f_16a")
        self.assertIsNone(get_vehicle_profile("a/b/c/d"))


if __name__ == "__main__":
    unittest.main()
