---
name: vsdd-specify
description: 把已澄清的 Feature 转换为实现无关、可评审、可验证的行为规格和验收场景。
---
# Feature Spec 编写

## 输入
feature brief、source-register.md、capability map、已批准基线规格、客户需求源、术语表、接口契约与相关缺陷证据。

## 步骤
1. 保留来源身份：每项要求标注客户来源，或标为带有理由的推导建议。
2. 分配稳定 FR-* 与 AC-* ID。写可观察行为与约束，不提前塞入类名、框架或代码实现，除非它们是正式约束。
3. 为每项 FR 创建可重复判定的验收场景。按适用情况考虑正常、边界、无效/过期输入、状态切换、交互、恢复与异常。
4. 只有在权威资料中明确或被批准后，才能定义单位、范围、阈值、时序、迟滞/防抖、默认值、持久化、优先级、失效处理和降级行为。否则列出问题。
5. 写明范围/非目标、依赖、成功度量、质量检查项和未决决策。
6. 检查与已有基线、能力契约的冲突。提议 delta，不得静默改写已批准基线。
7. 检查原子性、明确性、可测试性、来源状态、追溯链接和隐藏假设。
8. 完成 feature-spec.md 中 normal、boundary、invalid-input、state-transition、failure、recovery、timing-performance、interface-semantics、safety-security-diagnostics 完备性清单；适用项关联 FR/AC，不适用项填写理由，并记录真实评审引用。
9. 确保每个范围内 SRC 都映射到 FR，每个 FR 都有 FB 来源和 AC；运行 vsdd trace-check <change-id> 发现缺口后不得靠删边或更改 ID 来消除错误。

## 放行条件
每项范围内 FR 都有可测试验收路径或有批准的例外理由；高影响未知项已解决或明确阻塞审批；产品/领域负责人批准当前版本。

## 输出
feature-spec.md、source-register.md 评审状态、更新后的 change-record.md、SRC/FB→FR→AC 追溯关系、待澄清问题及门禁状态。
