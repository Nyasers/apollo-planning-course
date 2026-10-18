# 本轮真实自评：通过 8/9 项。已到达终点。

> 本报告由 Apollo Claw Harness 生成，评分与判定来自脚本，AI 只解释证据，不替代教师或官方评测。

- 报告模式：真实本地自评
- 本轮实验：`20261018-232816-56f463-crosswalk`
- 通过指标：8/9
- Baseline：`20261018-211208-d0e18b-crosswalk`（7/9）

## 基线与本轮对比

| 指标 | Baseline | 本轮 | 结果 |
| --- | --- | --- | --- |
| ReachEnd | FAIL 257/257 | PASS 12/267 | improved |
| TTC | FAIL 29/257 | FAIL 29/267 | unchanged |
| AccelerationLimit | PASS 0/257 | PASS 0/267 | unchanged |
| HardBrake | PASS 0/257 | PASS 0/267 | unchanged |
| Collision | PASS 0/257 | PASS 0/267 | unchanged |
| SpeedLimit | PASS 0/257 | PASS 0/267 | unchanged |
| 最大 Jerk（m/s³） | 12.36033936841363 越低越好 | 2.903456406498611 越低越好 | improved |

## 人工核验

- 人工核验：目标 3060 是行人；本轮场景代码未修改人行横道避让逻辑，主车未对行人进行减速避让，因此 TTC 失败是真实控制缺陷，不是合理礼让。ReachEnd 只表示曾到过终点，不代表完成了人行横道前停车让行。

## 需要关注

- TTC 仍未通过，不能把本轮写成完全通过；请回放失败时间窗并确认目标对象。
- baseline 与本轮都未完全通过；当前报告应定位为“真实优化验证/未完成”，不是最终成功案例。

## 下一步

- 检查 TTC 失败区间、目标对象和实际减速时点；若为行人冲突，提前减速并保持安全 TTC。

## 文件

- report_json: `report.json`
- report_md: `report.md`
- selfeval_md: `selfeval.md`
- doctor_json: `doctor.json`
- channel_summary: `channel_summary.csv`
- record_report: `record_report.md`
- plots: `plots/`

> 本地自评估不等于官方评分。
