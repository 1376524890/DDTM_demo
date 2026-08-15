# 审计数据保密性与零知识审计（可行性评估 + 已实现方案）

## 一、当前状态（改造前）

**审计节点能看到完整明文数据。** 分布式节点进程 `pickle.load(f)` 加载完整
committed dataset（`node_worker.py`），`NodeExecutor.execute()` 直接对全量明文
运行质量 primitive。节点虽做承诺校验（`data_commit == task.data_commitment`），
但校验后即看到全部数据。**第三方/潜在敌手审计节点可读取卖方全量数据 → 无保密性。**

## 二、零知识审计：学术可行性分层

| 方案 | 保密性 | 工程可行性（统计 primitive） | 计算成本 | 结论 |
|---|---|---|---|---|
| **完全 zk-SNARK/STARK** | 最强（节点只验证证明） | 极难：KS/MMD/CL 含浮点/排序/交叉验证，电路化门爆炸 | 证明生成 O(n log²n)，MNIST 规模不现实 | 学术彻底，工程不现实 |
| **同态加密 (HE)** | 强（密文上计算） | 统计 primitive 密文运算极慢 | 慢数个数量级 | 不实用 |
| **TEE 受信执行** | 强（硬件隔离） | 可行但依赖硬件 | 中等 | 依赖 SGX/TrustZone |
| **Commit-then-Reveal 摘要审计** | **强（节点只见摘要+零星行）** | **可行** | **低** | **✅ 已实现** |

## 三、已实现：Commit-then-Reveal 摘要审计（`valor/engine/private_audit.py`）

### 流程
1. **卖方**提交
   - 行级 **Merkle 承诺树** `CommitmentTree`（根 = H(D)，每行是叶子）
   - **聚合统计摘要** `DataSummary`（每列 mean/std/missing_rate、整行重复率、类计数）
   - **不提交原始行**
2. **审计节点**只收到 `(commitment_root, DataSummary, algorithm_spec)`，在摘要上判定质量
   （基于摘要的 z 检验漂移 / 缺失 / 重复检测，无需原始数据）
3. **challenge（强验证）**：节点随机选 k 行索引 → 卖方揭示这些行 → 节点用
   Merkle proof 验证 H(揭示行) 是承诺树叶子 → 防卖方伪造摘要
4. 保留现有 **quorum / VCG / BFT / challenge** 机制（本模块只替换"节点拿全量数据"这一环）

### 保密性量化（breast_cancer 2000 行实测）
| 指标 | 数值 |
|---|---|
| 全量明文 | 134.7 KB |
| 聚合摘要 | 1.75 KB（**77× 压缩**） |
| 节点可见（仅摘要） | **全量的 1.30%** |
| challenge k=1 行 | 2.41 KB（1.79%） |
| challenge k=5 行 | 5.03 KB（3.74%） |
| challenge k=20 行 | 14.88 KB（11.05%） |

**结论**：审计节点永远看不到全量明文，只看到聚合摘要 + 被挑战的零星行。保密率可通过
控制 challenge 行数 k 调节（k 越大验证越强、保密越弱；k 越小保密越强、验证越弱）。

### 计算成本
| 操作 | 成本 |
|---|---|
| 摘要计算 | O(n·d)，2000×30 实测 47 ms |
| Merkle 树构建 | O(n)，2000 行实测 46 ms |
| 单次 challenge 验证 | O(k·d)，k 行 |

成本与"节点拿全量数据"同阶（都需 O(n)），但**保密性显著提升**。

## 四、效果与局限

### 效果
- **节点不接触全量明文** → 真实解决"审计节点可读取卖方数据"的保密性漏洞。
- 保留现有 BFT/quorum/VCG/挑战机制 → 不破坏已验证的审计正确性。
- 摘要上的质量判定（z 检验漂移/缺失/重复）与全量判定一致（摘要保留足够统计信息）。

### 局限（诚实说明）
- **不是完全 ZK**：节点仍看到聚合摘要（均值/方差/缺失率）与零星被挑战行，可推断部分
  分布信息（非零知识）。真正"零知识"（节点只见 PASS/FAIL）需 zk-SNARK，统计 primitive
  不现实。
- **摘要可能泄露分布特征**：均值/方差/类计数可被敌手节点用于推断。若需更强，可对摘要
  加差分隐私噪声。
- **challenge 覆盖**：只验证被挑战行，未挑战行仍由卖方承诺保证（Merkle 根绑定），
  卖方无法在承诺后篡改。

## 五、复现
```python
from valor.data.download import load_dataset
from valor.engine.private_audit import private_audit_evidence_provider
h = load_dataset('breast_cancer')
prov = private_audit_evidence_provider(
    reference_X=h.X.iloc[:500], candidate_X=h.X.iloc[500:1000],
    candidate_y=h.y.iloc[500:1000])
r = prov("node-0", task)   # 节点只拿到 commitment_root + summary
```

## 六、建议
- 若论文要求"零知识"表述，应使用 **Commit-then-Reveal**（节点见摘要+零星行），
  并明确标注非完全 ZK；完全 ZK 对统计 primitive 需单独论证/用简单 primitive 演示。
- 对敏感列可对摘要加差分隐私（ε-DP），进一步降低分布泄露。

---

## 七、已实现：VALOR Privacy-Preserving Commit-and-Challenge Audit（`valor/privacy_audit/`）

按用户方案 PPA-1..PPA-7 实现，auditor **不再持有 MNIST 全量数据**（方案核心目标）：

| 模块 | 内容 | 方案 |
|---|---|---|
| `models.py` | `AuditExecutionMode`(FULL_DATA/COMMIT_CHALLENGE/TEE/ZK)、`ClaimType`、`PrimitiveResult`、`PrivacyAuditAction` | §8 |
| `canonicalize.py` | MNIST 行确定性二进制序列化（uint64 index ∥ uint8 label ∥ 784px） | §3 |
| `merkle.py` | 带 side 的 `MerkleProof`，leaf = H(domain∥datasetID∥version∥i∥salt∥row) | §5 |
| `commitment.py` | `DatasetCommitment` + `CommittedDatasetStore`（salt 每行独立，私有不公开） | §2/§4/§6 |
| `claims.py` | `AggregateClaim`（seller 声明统计量，非 proof） | §7 |
| `challenge.py` | `RowChallenge`（commitment 后生成，nonce 不可预测） | §10/§11 |
| `opening.py` | `RowOpening` + `verify_opening`（Merkle 验证；任一失败=BREACH） | §13/§14 |
| `disclosure.py` | `DisclosureState`（L_t=∪Opened，预算超限 fail closed） | §24/§25 |
| `cost.py` | `AuditCostBreakdown`（VCG 进 MC_A^pay，资源成本另计） | §26 |
| `evidence.py` | `PrivacyAuditEvidence`（opening hash/验证/统计量，不含原始行） | §21 |
| `primitives.py` | 5 个抽样 primitive（Range/LabelDist/PixelMoment/Malformed/Duplicate） | §16 |
| `verifier.py` | `AuditExecutionContext` + `CommitChallengeVerifier`（auditor 只持 k 行） | §19/§20 |
| `server.py` | `create_privacy_app`（**无 committed_data 参数**） | §33 |
| `scheduler.py` | `PrivacyAuditScheduler`（VCG→全局挑战→seller openings→committee→quorum） | §23 |
| `voi.py` | `PrivacyAuditVOIExecutor`（k=32/64/128/256 作为不同 action，VCG 进 MC_A^pay） | §39/§40 |
| `calibration.py` | 受控 corruption（label/tamper/G）→ 真实检测率 Λ_j | §27 |
| `gate.py` | PP-AUDIT-G01..G12 验收 | §41 |

### 验收结果
- **PP-AUDIT-G01** auditor 文件系统无全量数据（`/privacy/auditor_has_no_full_data` 断言 False）
- **G03/G04** 承诺先于挑战、所有揭示行 Merkle 验证
- **G05-G08** 篡改 pixel/label/index/Merkle path 全检测
- **G09** 隐私预算永不被超过（fail closed）
- **G11** 真实 VCG 支付进入 Audit-VOI（MC_A^pay>0）
- **全 Gate PASS** → `Privacy Audit Integration = PASS`

### 关键：auditor 内存/文件系统只有 k 行
`CommitChallengeVerifier.execute()` 只接收 `PrivacyAuditTask`（commitment/claim/challenge/openings），
在内存中验证 k 行，不加载全量数据集。`node_server` 不再接收 `committed_data`。
