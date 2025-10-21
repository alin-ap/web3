# Strategypunks Fork

## 快速开始

### 1. 克隆仓库并初始化子模块

⚠️ **重要**：本项目使用 Git 子模块管理依赖，克隆后必须初始化子模块！

```bash
# 方式一：克隆时同时拉取子模块（推荐）
git clone --recurse-submodules https://github.com/alin-ap/strategypunks-fork.git
cd strategypunks-fork

# 方式二：如果已经克隆，手动初始化子模块
git clone https://github.com/alin-ap/strategypunks-fork.git
cd strategypunks-fork
git submodule update --init --recursive
```

### 2. 编译项目

```bash
forge build
```

### 3. 运行测试

```bash
forge test
```

---

## 已获取源码
- [x] token/STRPNK.sol → 0x24b5664083b89ae7c2b7a4a6efea472a6d47314c
- [x] strategy/NFTStrategy.sol → 0xdCE9a59F3a8F6dceDc753A4C95A72C0fA75fC049
- [x] strategy/src/NFTStrategyRange.sol （随 Range Factory 包）
- [x] hooks/NFTStrategyHook.sol → 0xE3C63A9813ac03BE0E8618B627cB8170CfA468c4
- [x] hooks/NFTStrategyRangeHook.sol → 0x5D8A61Fa2ceD43eeABfFc00C85F705E3e08C28c4
- [x] factory/NFTStrategyFactory.sol → 0xA1a196B5Be89be04A2c1Dc71643689ce013C22e5
- [x] factory/src/NFTStrategyRangeFactory.sol （含 NFTStrategyRange.sol & Interfaces.sol）
- [x] Interfaces.sol（多处引用，暂保留原目录）

## 下一步（按顺序执行）
1. **整理目录**：
   - [x] 把 `project/`、`npm/` 等中间层移入目标结构 (`src/token/STRPNK.sol` 等)。
   - [x] 合理保留 `lib/` 下依赖，删除重复副本。
2. **Foundry 配置**：
   - [x] 依据各 `metadata.json` 校对 `solc` 版本，`foundry.toml` 启用 `auto_detect_solc` 与合适的 `evm_version`。
   - [x] 新建 `.env.example`，列出 `RPC_URL`、`PRIVATE_KEY` 等。
3. **安装依赖 / Remapping**：
   - [x] `forge install OpenZeppelin/openzeppelin-contracts@v5.0.0`
   - [x] `forge install Uniswap/v4-core`
   - [x] `forge install Uniswap/v4-periphery`
   - [x] `forge install Uniswap/v4-router`
   - [x] `forge install Uniswap/permit2`
   - [x] `forge install Vectorized/solady`
   - [x] 在 `foundry.toml` 写入 remappings：
     ```toml
     auto_detect_solc = true
     remappings = [
       "@openzeppelin/contracts/=lib/openzeppelin-contracts/contracts/",
       "@uniswap/v4-core/=lib/v4-core/",
       "@uniswap/v4-periphery/=lib/v4-periphery/",
       "v4-router/=lib/v4-router/",
       "permit2/=lib/permit2/",
       "solady/=lib/solady/src/",
     ]
     ```
4. **编译**：
   - [x] `source ~/.zshenv && forge build`，根据报错补齐缺失依赖或 remapping。
5. **部署准备**：
   - [x] 梳理各合约的构造参数 / 初始化调用顺序，可参考链上实例或业务需求。
   - [x] 在 `script/Deploy.s.sol` 中编排部署逻辑，读取 `.env` 中的 `RPC_URL`、`PRIVATE_KEY`。
   - [x] 使用 `forge script script/Deploy.s.sol:Deploy --rpc-url $RPC_URL --broadcast --via-ir` 广播部署交易。
   - [x] 建议先 `cp .env.example .env` 并填充各依赖地址，再执行 Dry-run（省略 `--broadcast`）验证逻辑。
   - [x] 运行 `forge verify-contract`（或 Etherscan UI）提交源码与编译参数，完成链上验证。



