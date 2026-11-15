跨境流域临灾数据融合与预警复盘系统

运行验收：
python3 -m basin_warning run --fixture fixtures/acceptance.json --database /tmp/basin_warning.sqlite3 --output /tmp/basin_warning-output

核验：
python3 -m basin_warning verify --database /tmp/basin_warning.sqlite3 --output /tmp/basin_warning-output

全量测试：
python3 -m unittest discover -s tests -v

按模块测试：
python3 -m unittest tests.fusion.test_conflict_resolution -v

构建检查：
python3 -m compileall -q basin_warning tests
