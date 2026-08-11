# 架构与权威边界

[English](architecture.md) / [中文](architecture.zh-CN.md)

## 一个世界，一个普通状态写方

权威世界是 `ImplicitFieldState`：建立在空间基底记录上的有限、多通道系数向量。`advance_implicit_field_state` 是普通转移的唯一 owner。用户控制和通过门控的 Feedback 都只是这一个转移的输入，不是并列的世界写方。

```text
浏览器中的真实操作者
  -> 带当前 frame/state/ray lineage 的同源 JSON 请求
  -> ImplicitFieldSession 事务
  -> 权威 implicit Field 转移
  -> energy ledger 与 projection frame
  -> Pattern -> Trace -> Agent -> 候选 Feedback
  -> 后续转移的应用时比较
  -> export、replay、completion 与 Viewer 读回
```

移动相机只生成观察 frame，不推进世界 tick。Viewer 消费 frame 和审计记录；像素、标签、浏览器 sidecar 与 FivePhase 记录都不是权威状态。

## 连续局部控制

`local_excite` 与 `local_dampen` 是同一有符号 density 控制轴的正负方向。radius 产生平滑、紧支撑的空间权重；小数 duration 被物化成有限调度，其权重总和等于请求 dose。运行时先约束用户输入，再相对当前 density 阶段约束 Feedback，并同时记录 raw 与 realized projection。

energy ledger 是有限系数模型上的有界工程代理，记录先前能量、内部耦合、跨边界耦合、耗散、实际输入、裁剪和残差；它不是热力学守恒宣称。

## 派生因果闭环

FivePhase 是 Field 上的测量词汇：

1. 从权威状态派生 phase projection；
2. Pattern 识别持续存在的有界支撑；
3. Trace 携带观察损失与记忆；
4. Agent 比较当前支撑能量与 episode setpoint；
5. Feedback 提出有符号、基底局部的修正；
6. 下一次转移在真实 post-user baseline 上重算 sensitivity；
7. 只有固定支撑误差严格下降才提交，否则 Feedback 被消费为空 projection。

Feedback on/off 分支可从同一可信 snapshot 恢复。Completion 不相信 summary，而会独立重放转移、ledger、lineage、落盘 artifact 与 counterfactual episode。

## 明确边界

本版本没有认证、TLS、多用户隔离、持久数据库、公网部署、分布式共识，也不宣称普适物理定律。本地服务器会拒绝非 loopback bind；网络产品必须是另一条能力纵切与独立威胁模型。

v0.1 的真实闭包仍包含较大的生成式 Viewer 和当前调用链所需的 legacy readout helper。为了保留已测试行为，本预览暂不冒险拆分；未来解耦也不能制造第二条权威路径。
