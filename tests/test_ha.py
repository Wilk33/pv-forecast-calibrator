from datetime import datetime,timezone
import unittest

from pv_forecast_calibrator.ha import history_maximum,parse_numeric_state


class HomeAssistantParserTests(unittest.TestCase):
	def test_numeric_state_accepts_decimal_comma(self):
		self.assertEqual(parse_numeric_state({"state":"12,34"}),12.34)

	def test_numeric_state_rejects_unavailable_negative_and_nan(self):
		for value in ("unavailable","unknown","nan","inf","-1"):
			with self.subTest(value=value):
				self.assertIsNone(parse_numeric_state({"state":value}))

	def test_history_maximum_ignores_invalid_states(self):
		payload=[
			[
				{"state":"unknown"},
				{"state":"1.5"},
				{"state":"unavailable"},
				{"state":"12.7"},
				{"state":"3.0"}
			]
		]

		self.assertEqual(history_maximum(payload),12.7)

	def test_empty_history_has_no_maximum(self):
		self.assertIsNone(history_maximum([[]]))


if __name__ == "__main__":
	unittest.main()
