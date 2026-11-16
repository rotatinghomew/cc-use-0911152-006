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

--------------------------------------------------------------------------
历史回放与替代规则比较（试运行，与线上隔离）

值班人员无需替换线上规则即可评估替代规则组合。试运行使用独立的 SQLite
（默认在业务库旁生成 *.trial.sqlite3）与独立审计哈希链，回放、评议、撤回
都不写业务库，不影响正在处置的告警。

1) 规则包 basin_warning/replay/rule_package.py
   RulePackage 是不可变、带内容指纹的版本化规则集，描述上下文覆盖项
   （check_*_threshold 规则阈值、guard_*_floor 守卫底线、metric_*_offset、
   *_weight、approve/review/transition_threshold）以及哪些决策结果算作告警
   （alert_outcomes）。baseline_rule_package 表示当前线上规则，空覆盖。
   规则包可按 station_ids / event_types 限定作用域。

2) 历史回放 basin_warning/replay/replay_engine.py
   replay_candidate 把冻结的历史观测分别用基线包和候选包重放，依据地面真值
   标签（labels，每条观测必须给出 actual_event，可带 event_type、event_time）
   计算混淆矩阵：误报(false positive)、漏报(false negative)、命中、正确静默、
   precision/recall/F1，以及命中事件的提前量(lead time)。结果按站点和事件类型
   分组对比，并把每条发生翻转的规则/守卫记录为 RuleFlip，汇总成
   RuleContribution，说明每条被改规则的贡献(benefit)与代价(cost)。
   回放是纯函数、确定性的，报告自身带指纹（指纹不包含其自身字段）。

3) 多准则启用门控，不能只挑误报最少
   TrialPolicy/evaluate_eligibility 同时要求：不新增漏报、recall 不回退、
   提前量中位数不回退、每个站点和每类事件都不新增漏报、误报确有下降、证据
   完整。一个把告警全部静默、误报为零但漏报全部事件的方案会被拒绝。
   select_evidence_backed 只在合格候选中选择，绝不返回仅靠误报取胜的方案。

4) 启用评议与撤回 basin_warning/replay/trial_store.py
   状态机：candidate -> in_review -> approved/rejected -> enabled；
   另有 withdrawn / revoked / superseded。
   - 只有合格候选能 submit-for-review，评议需给出基于证据的理由。
   - enable 前只读核对业务库：回放引用的每条观测指纹与版本必须仍与线上一致，
     规则版本仍有效；不一致即拒绝启用（不修改业务库）。
   - 切换后新告警的 Decision 带 rule_basis（规则包 id/version/指纹），
     alert_notices 新增 rule_basis_json 列；旧通知仍按原依据追溯，其送达与
     确认流程不变。老数据库该列可为空，启动时幂等迁移。
   - 观测更正(record_observation_correction)会把引用旧指纹的回放标记为
     失效；若已启用候选的试运行结论因此被推翻，revoke_invalid_enabled 自动
     撤回（状态 revoked），旧候选不得继续启用，review_history 记录撤回原因、
     失效证据与线上不一致标记，供复盘说明。

5) 报告与核验 basin_warning/replay/trial_report.py
   export_replay_bundle 写出哈希校验的回放对比、站点/事件类型贡献、规则贡献、
   评议与观测更正清单及 manifest；verify_replay_bundle 检测任何事后篡改。

命令行：
  回放比较：
  python3 -m basin_warning replay --fixture <obs.json> --labels <labels.json> \
      --candidates <packages.json> --database <live.sqlite3> --output <trial-dir>
  查看评议： python3 -m basin_warning review --database <live.sqlite3>
  送评议：   python3 -m basin_warning submit-review --database <live.sqlite3> \
      --package <package.json> --replay-id <id> --actor <人> --rationale <证据理由>
  评议决定： python3 -m basin_warning decide-review --database <live.sqlite3> \
      --review-id <id> (--approve|--reject) --actor <人> --rationale <理由>
  启用：     python3 -m basin_warning enable --database <live.sqlite3> \
      --package <package.json> --actor <人>
  撤回：     python3 -m basin_warning withdraw --database <live.sqlite3> \
      --package <package.json> --actor <人> --reason <理由>
  观测更正： python3 -m basin_warning correct-observation --database <live.sqlite3> \
      --record <corrected.json> --reason <理由>
  校验试运行产物： python3 -m basin_warning verify-trial --output <trial-dir>/<replay-id>

标签文件 labels.json 以 record_id 为键，值为布尔值或
{"actual_event": bool, "event_type": str, "event_time": ISO8601}，必须覆盖
全部回放观测。候选文件为单个规则包对象或规则包对象数组。
