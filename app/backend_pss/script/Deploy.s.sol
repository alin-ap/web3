// SPDX-License-Identifier: MIT
pragma solidity ^0.8.30;

import "forge-std/Script.sol";
import "forge-std/console2.sol";

import {PunkStrategyStrategy} from "src/punkbuy/StrategyPunk.sol";
import {StrategyPunkHook} from "src/punkbuy/StrategyPunkHook.sol";
import {Hooks} from "@uniswap/v4-core/src/libraries/Hooks.sol";
import {IPoolManager} from "@uniswap/v4-core/src/interfaces/IPoolManager.sol";

/// @notice End-to-end deployment script for the Strategypunks fork.
///         Reads configuration from environment variables to stay in sync
///         with mainnet parameters.
contract Deploy is Script {
    uint160 internal constant _ALL_HOOK_MASK = uint160((1 << 14) - 1);
    uint160 internal constant _BEFORE_INITIALIZE_FLAG = 1 << 13;
    uint160 internal constant _AFTER_INITIALIZE_FLAG = 1 << 12;
    uint160 internal constant _BEFORE_ADD_LIQUIDITY_FLAG = 1 << 11;
    uint160 internal constant _AFTER_ADD_LIQUIDITY_FLAG = 1 << 10;
    uint160 internal constant _BEFORE_REMOVE_LIQUIDITY_FLAG = 1 << 9;
    uint160 internal constant _AFTER_REMOVE_LIQUIDITY_FLAG = 1 << 8;
    uint160 internal constant _BEFORE_SWAP_FLAG = 1 << 7;
    uint160 internal constant _AFTER_SWAP_FLAG = 1 << 6;
    uint160 internal constant _BEFORE_DONATE_FLAG = 1 << 5;
    uint160 internal constant _AFTER_DONATE_FLAG = 1 << 4;
    uint160 internal constant _BEFORE_SWAP_RETURNS_DELTA_FLAG = 1 << 3;
    uint160 internal constant _AFTER_SWAP_RETURNS_DELTA_FLAG = 1 << 2;
    uint160 internal constant _AFTER_ADD_LIQUIDITY_RETURNS_DELTA_FLAG = 1 << 1;
    uint160 internal constant _AFTER_REMOVE_LIQUIDITY_RETURNS_DELTA_FLAG = 1;
    address internal constant _CREATE2_DEPLOYER = 0x4e59b44847b379578588920cA78FbF26c0B4956C;

    struct DeployConfig {
        address posm;
        address permit2;
        address poolManager;
        address universalRouter;
        address v4Router;
        address feeRecipient;
        address strategyPunkFeeRecipient;
        uint256 strategyPunkLiquidityEth;
    }

    function run() external {
        DeployConfig memory cfg = _loadConfig();

        uint256 deployerPK = vm.envUint("PRIVATE_KEY2");
        vm.startBroadcast(deployerPK);

        console2.log("Deploying PunkStrategyStrategy and StrategyPunkHook...");

        _deployStrategyPunk(cfg);

        vm.stopBroadcast();
    }

    function _deployStrategyPunk(DeployConfig memory cfg) internal {
        PunkStrategyStrategy strategyPunk = new PunkStrategyStrategy(cfg.posm, cfg.permit2, cfg.poolManager, cfg.universalRouter, payable(cfg.v4Router));
        console2.log("PunkStrategyStrategy deployed at", address(strategyPunk));

        bytes32 hookInitCodeHash = keccak256(
            abi.encodePacked(
                type(StrategyPunkHook).creationCode, abi.encode(IPoolManager(cfg.poolManager), address(strategyPunk))
            )
        );

        (bytes32 hookSalt, address predictedHookAddress) =
            _findHookSalt(_CREATE2_DEPLOYER, hookInitCodeHash, _defaultHookPermissions());

        StrategyPunkHook hook =
            new StrategyPunkHook{salt: hookSalt}(IPoolManager(cfg.poolManager), address(strategyPunk));
        require(address(hook) == predictedHookAddress, "STRATEGY_PUNK_HOOK_ADDRESS_MISMATCH");
        console2.log("StrategyPunkHook salt", uint256(hookSalt));
        console2.log("StrategyPunkHook deployed at", address(hook));

        if (cfg.strategyPunkFeeRecipient != address(0) && hook.feeAddress() != cfg.strategyPunkFeeRecipient) {
            hook.updateFeeAddress(cfg.strategyPunkFeeRecipient);
            console2.log("StrategyPunkHook fee recipient", cfg.strategyPunkFeeRecipient);
        }

        require(cfg.strategyPunkLiquidityEth > 0, "STRATEGY_PUNK_LIQUIDITY_TOO_LOW");
        strategyPunk.loadLiquidity{value: cfg.strategyPunkLiquidityEth}(address(hook));
        console2.log("StrategyPunk liquidity (wei)", cfg.strategyPunkLiquidityEth);
    }

    function _loadConfig() internal view returns (DeployConfig memory cfg) {
        cfg.posm = vm.envAddress("POSM_ADDRESS");
        cfg.permit2 = vm.envAddress("PERMIT2_ADDRESS");
        cfg.poolManager = vm.envAddress("POOL_MANAGER_ADDRESS");
        cfg.universalRouter = vm.envAddress("UNIVERSAL_ROUTER_ADDRESS");
        cfg.v4Router = vm.envAddress("V4_ROUTER_ADDRESS");
        cfg.feeRecipient = vm.envAddress("FEE_RECIPIENT_ADDRESS");
        cfg.strategyPunkFeeRecipient = vm.envOr("STRATEGY_PUNK_FEE_RECIPIENT", cfg.feeRecipient);
        cfg.strategyPunkLiquidityEth = vm.envOr("STRATEGY_PUNK_LIQUIDITY_ETH", uint256(2));
    }

    function _defaultHookPermissions() private pure returns (Hooks.Permissions memory perms) {
        perms.beforeInitialize = true;
        perms.beforeAddLiquidity = true;
        perms.beforeSwap = true;
        perms.afterSwap = true;
        perms.afterSwapReturnDelta = true;
    }

    function _findHookSalt(address deployer, bytes32 initCodeHash, Hooks.Permissions memory perms)
        private
        pure
        returns (bytes32 salt, address hookAddress)
    {
        for (uint256 i; i < type(uint256).max; ++i) {
            bytes32 candidate = bytes32(i);
            address predicted = _computeCreate2Address(deployer, candidate, initCodeHash);
            if (_matchesPermissions(predicted, perms)) {
                return (candidate, predicted);
            }
        }
        revert("HOOK_SALT_NOT_FOUND");
    }

    function _computeCreate2Address(address deployer, bytes32 salt, bytes32 initCodeHash)
        private
        pure
        returns (address)
    {
        bytes32 hash = keccak256(abi.encodePacked(bytes1(0xff), deployer, salt, initCodeHash));
        return address(uint160(uint256(hash)));
    }

    function _matchesPermissions(address hook, Hooks.Permissions memory perms) private pure returns (bool) {
        uint160 flags = uint160(hook) & _ALL_HOOK_MASK;

        if (((flags & _BEFORE_INITIALIZE_FLAG) != 0) != perms.beforeInitialize) return false;
        if (((flags & _AFTER_INITIALIZE_FLAG) != 0) != perms.afterInitialize) return false;
        if (((flags & _BEFORE_ADD_LIQUIDITY_FLAG) != 0) != perms.beforeAddLiquidity) return false;
        if (((flags & _AFTER_ADD_LIQUIDITY_FLAG) != 0) != perms.afterAddLiquidity) return false;
        if (((flags & _BEFORE_REMOVE_LIQUIDITY_FLAG) != 0) != perms.beforeRemoveLiquidity) return false;
        if (((flags & _AFTER_REMOVE_LIQUIDITY_FLAG) != 0) != perms.afterRemoveLiquidity) return false;
        if (((flags & _BEFORE_SWAP_FLAG) != 0) != perms.beforeSwap) return false;
        if (((flags & _AFTER_SWAP_FLAG) != 0) != perms.afterSwap) return false;
        if (((flags & _BEFORE_DONATE_FLAG) != 0) != perms.beforeDonate) return false;
        if (((flags & _AFTER_DONATE_FLAG) != 0) != perms.afterDonate) return false;
        if (((flags & _BEFORE_SWAP_RETURNS_DELTA_FLAG) != 0) != perms.beforeSwapReturnDelta) return false;
        if (((flags & _AFTER_SWAP_RETURNS_DELTA_FLAG) != 0) != perms.afterSwapReturnDelta) return false;
        if (((flags & _AFTER_ADD_LIQUIDITY_RETURNS_DELTA_FLAG) != 0) != perms.afterAddLiquidityReturnDelta) {
            return false;
        }
        if (((flags & _AFTER_REMOVE_LIQUIDITY_RETURNS_DELTA_FLAG) != 0) != perms.afterRemoveLiquidityReturnDelta) {
            return false;
        }

        // require at least one flag set when hooks are enabled
        if (flags == 0) return false;

        return true;
    }
}
