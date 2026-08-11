# GeNewWord Engine

[English](README.md) / [中文](README.zh-CN.md)

GeNewWord Engine 是一个可玩的、以连续场为核心的世界引擎研究预览。它围绕一条可审计的因果链构建：

**Field → Constraint → Pattern → Trace → Agent → Feedback → 后续 Field**

Viewer 不是世界权威，也不是预录动画播放器。权威状态由本地运行时持有；有符号、局部且有边界的交互可以激励或抑制 Field。Pattern 与 Agent Feedback 只有在应用时通过 fail-closed 的基线比较，才可能影响后续 Field。

## 当前状态

`v0.1.0-alpha.1` 是一个**仅限本机的研究预览**，不是完成态游戏、普适物理理论或可直接上公网的服务。参见[公开状态](docs/status.zh-CN.md)和[架构与权威边界](docs/architecture.zh-CN.md)。

## 三分钟启动

需要 Python 3.12+ 和现代浏览器；只有运行浏览器验收时才需要 Node.js 18+。Python 运行时没有第三方依赖。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .

python scripts/serve_implicit_3d_field_window.py \
  --host 127.0.0.1 \
  --port 8766 \
  --max-advance-ticks 8
```

打开 `http://127.0.0.1:8766/viewer.html`，选择 `interact`，再选 `local_excite` 或 `local_dampen` 并点击画布。`Run World` 推进权威状态，`/export` 提供权威读回。

服务器会主动拒绝非 loopback 地址。它没有认证与 TLS，绝不能暴露到公网或不可信网络。

## 重现因果结论

```bash
python scripts/run_continuous_local_energy_response_validation.py \
  --output /tmp/geneword-continuous.json

python scripts/run_five_phase_causal_closed_loop_validation.py \
  --ticks 8 \
  --source-package-name source-a \
  --output-dir /tmp/geneword-causal

python scripts/run_five_phase_live_world_validation.py \
  --ticks 8 \
  --output-dir /tmp/geneword-live

python scripts/run_five_phase_pattern_trace_feedback_validation.py \
  --output-dir /tmp/geneword-five-phase
```

这些是有界工程验证，不是热力学能量守恒或普适定律的宣称。

## 测试

```bash
python -m unittest discover -s tests -p "test_*.py"
python -m compileall -q world_engine scripts tests tools

npm ci
npx playwright install chromium
npm run test:browser
```

验证输出只使用专门的 `/tmp/geneword-*` 目录；部分 runner 会重建收到的输出目录。

## 文档

- [英文主指南](docs/continuous-local-energy-response-guide.md) / [中文完整译文](docs/continuous-local-energy-response-guide.zh-CN.md)
- [Architecture and authority model](docs/architecture.md) / [架构与权威边界](docs/architecture.zh-CN.md)
- [安全策略](SECURITY.md)
- [贡献指南](CONTRIBUTING.md)

## 仓库边界与许可证

公开仓库只含原创引擎代码、测试和文档，不含下载论文、文章镜像、视频元数据、内部实验归档、模型权重或生成的验证产物。原创代码与文档采用 [Apache License 2.0](LICENSE)，依赖保留各自许可证，详见[第三方声明](THIRD_PARTY_NOTICES.md)。
