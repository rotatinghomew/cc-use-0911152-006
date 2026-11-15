from __future__ import annotations

import unittest
from basin_warning.observations.hydro_event import DomainRecord
from basin_warning.fusion.watermark import alert_level, delivery_risk, event_watermark, station_signal


class WatermarkTests(unittest.TestCase):
    def record(self, key, water=5, age=5):
        return DomainRecord(key, {"station_id": key, "rainfall_mm": 120, "water_level_m": water, "flow_rate": 900,
            "gate_opening": .4, "forecast_horizon_h": 24, "sensor_age_min": age, "quality_flag": .9,
            "upstream_delay": 2, "population_exposure": 20000, "delivery_channels": 3, "ack_rate": .8})

    def test_watermark_and_hysteresis(self):
        result = event_watermark([self.record("a"), self.record("b", water=12)])
        self.assertGreater(result["risk"], 0.0)
        self.assertIn(alert_level(result), {"observing", "watch", "warning", "critical"})
        self.assertGreater(station_signal(self.record("a")).freshness, station_signal(self.record("b", age=170)).freshness)

    def test_delivery_risk_is_bounded(self):
        self.assertTrue(0.0 <= delivery_risk(self.record("a")) <= 1.0)
