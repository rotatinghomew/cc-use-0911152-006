跨境流域临灾数据融合与预警复盘系统

河段与通知：Repository.register_reach 登记有传播时间的下游关联，
assign_station 关联观测站与河段，issue_notice 把通知关联到当时的观测版本和河段。
update_notice 只能将待发通知送达或取消、送达后确认；已送达/确认事实不可撤销
或改派。reach_notices 可按河段追溯。风险分析计算站点聚合时窗。

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
