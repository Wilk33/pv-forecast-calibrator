from pathlib import Path
import unittest


ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/"pv-forecast-calibrator"


class PackagingTests(unittest.TestCase):
	def test_required_home_assistant_app_files_exist(self):
		for relative in (
			"repository.yaml",
			"pv-forecast-calibrator/config.yaml",
			"pv-forecast-calibrator/build.yaml",
			"pv-forecast-calibrator/Dockerfile",
			"pv-forecast-calibrator/run.sh",
			"pv-forecast-calibrator/DOCS.md",
			"pv-forecast-calibrator/CHANGELOG.md",
			"pv-forecast-calibrator/translations/pl.yaml",
			"pv-forecast-calibrator/translations/en.yaml",
			"pv-forecast-calibrator/rootfs/requirements.txt"
		):
			with self.subTest(path=relative):
				self.assertTrue((ROOT/relative).is_file())

	def test_config_has_version_api_mqtt_and_no_ingress(self):
		config=(APP/"config.yaml").read_text(encoding="utf-8")

		self.assertIn('version: "1.0.0"',config)
		self.assertIn("slug: pv-forecast-calibrator",config)
		self.assertIn("homeassistant_api: true",config)
		self.assertIn("hassio_api: true",config)
		self.assertIn("mqtt:need",config)
		self.assertNotIn("ingress:",config)

	def test_config_defaults_match_approved_schedule_and_model(self):
		config=(APP/"config.yaml").read_text(encoding="utf-8")

		for expected in (
			'timezone: Europe/Warsaw',
			'snapshot_time: "04:20"',
			'snapshot_deadline: "04:45"',
			'settlement_time: "23:00"',
			'overprediction_penalty: 2.0',
			'max_downward_correction_kwh: 1.0',
			'decay: 0.93'
		):
			with self.subTest(expected=expected):
				self.assertIn(expected,config)

	def test_addon_version_matches_python_package(self):
		config=(APP/"config.yaml").read_text(encoding="utf-8")
		package=(ROOT/"pv_forecast_calibrator"/"__init__.py").read_text(encoding="utf-8")

		self.assertIn('version: "1.0.0"',config)
		self.assertIn('__version__="1.0.0"',package)

	def test_container_runtime_copy_matches_tested_source(self):
		source=ROOT/"pv_forecast_calibrator"
		target=APP/"rootfs"/"usr"/"src"/"app"/"pv_forecast_calibrator"
		for path in source.rglob("*"):
			if not path.is_file() or "__pycache__" in path.parts:
				continue
			relative=path.relative_to(source)
			with self.subTest(path=str(relative)):
				self.assertEqual((target/relative).read_bytes(),path.read_bytes())

	def test_translations_cover_every_config_option(self):
		config=(APP/"config.yaml").read_text(encoding="utf-8")
		options_block=config.split("options:",1)[1].split("schema:",1)[0]
		keys=[line.strip().split(":",1)[0] for line in options_block.splitlines() if line.startswith("  ")]
		for language in ("pl","en"):
			translation=(APP/"translations"/f"{language}.yaml").read_text(encoding="utf-8")
			for key in keys:
				with self.subTest(language=language,key=key):
					self.assertIn(f"  {key}:",translation)


if __name__ == "__main__":
	unittest.main()
