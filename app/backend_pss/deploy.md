# 部署记录

> 所有交易均由部署者 `0x64924DdDD4bF7ca9659D7D2Ceb2eD7618b226dc5` 在以太坊主网上执行。

> 说明：以下首先给出主网部署结果的结构化概要，文末保留原始操作流程日志以便比对与追溯。

## 实现合约预部署

| 合约 | 地址 | 交易哈希 |
|------|------|----------|
| `NFTStrategy` 实现 (`PUNK_STRATEGY_IMPL`) | `0xf7aF0d5beF6f8FC3970710F348876D99b03b3d02` | `0x75904407a7729a28ea238655632c8a2f8d7c5e153ffb55b091e1fcab45bbc432` |
| `NFTStrategyRange` 实现 (`PUNK_STRATEGY_RANGE_IMPL`) | `0x42C62AC2a06F9CcECb48aEEC0850E0787d345986` | `0x26a9fd1888d0f178ad43602633be62cffd08e8d380813855bc0b5388f5bbb116` |

## 主网批量部署（`forge script script/Deploy.s.sol:Deploy --broadcast --via-ir`）

| 合约 | 地址 | 构造参数（按顺序列出） | CREATE2 Salt | 交易哈希 | 验证 |
|------|------|----------------------|--------------|----------|------|
| `STRPNK` | `0xF03eD529F0057D2143B2eE0Efa61a15d9Aa22074` | 无 | — | `0xafbe1722f2c7dcbb40b01a25b392c262b96317480913fe0834d45d4473e17be1` | [Etherscan](https://etherscan.io/address/0xf03ed529f0057d2143b2ee0efa61a15d9aa22074)
| `NFTStrategyFactory` | `0xB583e3eE67c02B64E599fbd777AC57e717cAFCE2` | `_posm = 0xbd216513d74c8cf14cf4747e6aaa6420ff64ee9e`<br>`_permit2 = 0x000000000022d473030f116ddee9f6b43ac78ba3`<br>`_poolManager = 0x000000000004444c5dc75cb358380d2e3de08a90`<br>`_universalRouter = 0x66a9893cC07D91D95644AEDD05D03f95e1DBA8AF`<br>`_router = 0x00000000000044a361Ae3cAc094c9D1b14Eece97`<br>`_feeAddress = 0x64924DdDD4bF7ca9659D7D2Ceb2eD7618b226dc5` | — | `0x88ffd210673add61b174ff47422a82beb92aeb30d832f596bed982eb26660b0a` | [Etherscan](https://etherscan.io/address/0xb583e3ee67c02b64e599fbd777ac57e717cafce2)
| `NFTStrategyRangeFactory` | `0xf8C515B79022AF5814c202E5a8344Ba8e5Bd939f` | `_posm = 0xbd216513d74c8cf14cf4747e6aaa6420ff64ee9e`<br>`_permit2 = 0x000000000022d473030f116ddee9f6b43ac78ba3`<br>`_poolManager = 0x000000000004444c5dc75cb358380d2e3de08a90`<br>`_universalRouter = 0x66a9893cC07D91D95644AEDD05D03f95e1DBA8AF`<br>`_router = 0x00000000000044a361Ae3cAc094c9D1b14Eece97`<br>`_feeAddress = 0x64924DdDD4bF7ca9659D7D2Ceb2eD7618b226dc5` | — | `0xba512355032d89c67ef13a595d3b79da1ce9652fcaf81d292bafabb61d16f5d4` | [Etherscan](https://etherscan.io/address/0xf8c515b79022af5814c202e5a8344ba8e5bd939f)
| `NFTStrategyHook` | `0x4105f6339849E9Ba7CA7c0cA4b762803341328c4` | `_poolManager = 0x000000000004444c5dc75cb358380d2e3de08a90`<br>`_punkStrategy = 0xf7aF0d5beF6f8FC3970710F348876D99b03b3d02`<br>`_nftStrategyFactory = 0xB583e3eE67c02B64E599fbd777AC57e717cAFCE2`<br>`_feeAddress = 0x64924DdDD4bF7ca9659D7D2Ceb2eD7618b226dc5` | `8426` (十进制) | `0xa4a99df6bcb223b97ca3308797c02311afb4792021095c77f94ba2682b2cf196` | [Etherscan](https://etherscan.io/address/0x4105f6339849e9ba7ca7c0ca4b762803341328c4)
| `NFTStrategyRangeHook` | `0xbcFd8C6C4a6869544b8b5450A6592473C9DE68c4` | `_poolManager = 0x000000000004444c5dc75cb358380d2e3de08a90`<br>`_punkStrategy = 0x42C62AC2a06F9CcECb48aEEC0850E0787d345986`<br>`_nftStrategyFactory = 0xf8C515B79022AF5814c202E5a8344Ba8e5Bd939f`<br>`_feeAddress = 0x64924DdDD4bF7ca9659D7D2Ceb2eD7618b226dc5` | `10270` (十进制) | `0x7594b17b97462ffd7151f5c2419c5d2051bd8f0e9c1bdbfe33e7aa12455c62ba` | [Etherscan](https://etherscan.io/address/0xbcfd8c6c4a6869544b8b5450a6592473c9de68c4)

> 另有两笔交易（`0x933968b9…` 与 `0x4f00754a…`）分别调用 `NFTStrategyFactory.updateHookAddress` 与 `NFTStrategyRangeFactory.updateHookAddress`，已将上述 Hook 地址写入工厂状态。

## 状态检查

- `NFTStrategyFactory.owner() = 0x64924DdDD4bF7ca9659D7D2Ceb2eD7618b226dc5`
- `NFTStrategyFactory.hookAddress() = 0x4105f6339849E9Ba7CA7c0cA4b762803341328c4`
- `NFTStrategyRangeFactory.owner() = 0x64924DdDD4bF7ca9659D7D2Ceb2eD7618b226dc5`
- `NFTStrategyRangeFactory.hookAddress() = 0xbcFd8C6C4a6869544b8b5450A6592473C9DE68c4`
- `NFTStrategyFactory.routerRestrict() = true`

## 后续事项

1. 若需要更新收益地址或 Router 白名单，请通过工厂治理函数处理，并补充到本档案。
2. 依据业务需要准备测试网演练或集成测试报告。
3. 将本文件中信息同步到公开文档或团队知识库，便于后续运营与审计。

---

# 原始操作记录

以下内容保留了先前的命令执行与终端输出，方便还原完整上下文：

## 1. 实现合约部署命令

```
FOUNDRY_AUTO_INSTALL=0 forge create src/strategy/NFTStrategy.sol:NFTStrategy \
    --rpc-url $RPC_URL \
    --private-key $PRIVATE_KEY \
    --broadcast

[⠊] Compiling...
No files changed, compilation skipped
Deployer: 0x64924DdDD4bF7ca9659D7D2Ceb2eD7618b226dc5
Deployed to: 0xf7aF0d5beF6f8FC3970710F348876D99b03b3d02
Transaction hash: 0x75904407a7729a28ea238655632c8a2f8d7c5e153ffb55b091e1fcab45bbc432


FOUNDRY_AUTO_INSTALL=0 forge create src/strategy/NFTStrategyRange.sol:NFTStrategyRange \
    --rpc-url $RPC_URL \
    --private-key $PRIVATE_KEY \
    --broadcast \
    --constructor-args \
      0x05852ed6b0397F252969Ec6A92b26C725Bd975ff \
      0x5D8A61Fa2ceD43eeABfFc00C85F705E3e08C28c4 \
      0x00000000000044a361Ae3cAc094c9D1b14Eece97 \
      0x059EDD72Cd353dF5106D2B9cC5ab83a52287aC3a \
      0 \
      9999 \
      "SquiggleStrategy" \
      "SQUIGSTR"
[⠊] Compiling...
No files changed, compilation skipped
Deployer: 0x64924DdDD4bF7ca9659D7D2Ceb2eD7618b226dc5
Deployed to: 0x42C62AC2a06F9CcECb48aEEC0850E0787d345986
Transaction hash: 0x26a9fd1888d0f178ad43602633be62cffd08e8d380813855bc0b5388f5bbb116
```

## 2. Dry-run 输出

```
forge script script/Deploy.s.sol:Deploy --rpc-url $RPC_URL --via-ir

[⠊] Compiling...
No files changed, compilation skipped
Script ran successfully.

== Logs ==
  STRPNK deployed at 0xF03eD529F0057D2143B2eE0Efa61a15d9Aa22074
  NFTStrategyFactory deployed at 0xB583e3eE67c02B64E599fbd777AC57e717cAFCE2
  NFTStrategyRangeFactory deployed at 0xf8C515B79022AF5814c202E5a8344Ba8e5Bd939f
  NFTStrategyHook salt 8426
  NFTStrategyHook deployed at 0x4105f6339849E9Ba7CA7c0cA4b762803341328c4
  NFTStrategyRangeHook salt 10270
  NFTStrategyRangeHook deployed at 0xbcFd8C6C4a6869544b8b5450A6592473C9DE68c4
  Hook addresses wired into factories

## Setting up 1 EVM.

==========================

Chain 1

Estimated gas price: 1.297318457 gwei

Estimated total gas used for script: 14645572

Estimated amount required: 0.018999970868922404 ETH

==========================

SIMULATION COMPLETE. To broadcast these transactions, add --broadcast and wallet configuration(s) to the previous command. See forge script --help for more.

Transactions saved to: /Users/bobbyding/Desktop/strpunk_fork/broadcast/Deploy.s.sol/1/dry-run/run-latest.json

Sensitive values saved to: /Users/bobbyding/Desktop/strpunk_fork/cache/Deploy.s.sol/1/dry-run/run-latest.json
```

## 3. 正式部署输出节选

```
forge script script/Deploy.s.sol:Deploy \
  --rpc-url $RPC_URL \
  --via-ir \
  --broadcast

STRPNK deployed at 0xF03eD529F0057D2143B2eE0Efa61a15d9Aa22074
NFTStrategyFactory deployed at 0xB583e3eE67c02B64E599fbd777AC57e717cAFCE2
NFTStrategyRangeFactory deployed at 0xf8C515B79022AF5814c202E5a8344Ba8e5Bd939f
NFTStrategyHook salt 8426
NFTStrategyHook deployed at 0x4105f6339849E9Ba7CA7c0cA4b762803341328c4
NFTStrategyRangeHook salt 10270
NFTStrategyRangeHook deployed at 0xbcFd8C6C4a6869544b8b5450A6592473C9DE68c4
Hook addresses wired into factories

✅  [Success] Hash: 0xafbe1722f2c7dcbb40b01a25b392c262b96317480913fe0834d45d4473e17be1 ...
✅  [Success] Hash: 0x88ffd210673add61b174ff47422a82beb92aeb30d832f596bed982eb26660b0a ...
✅  [Success] Hash: 0xba512355032d89c67ef13a595d3b79da1ce9652fcaf81d292bafabb61d16f5d4 ...
✅  [Success] Hash: 0xa4a99df6bcb223b97ca3308797c02311afb4792021095c77f94ba2682b2cf196 ...
✅  [Success] Hash: 0x7594b17b97462ffd7151f5c2419c5d2051bd8f0e9c1bdbfe33e7aa12455c62ba ...
✅  [Success] Hash: 0x933968b90ea8f991ea241b7ae98a9034cf599c1458a0e1fdc1a01f1fc6d82f61 ...
✅  [Success] Hash: 0x4f00754adbdbcb63f5849fbd29bc1ad3ef09be742238638faacc0ac3eb522337 ...
```
