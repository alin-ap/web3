// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import {BaseHook} from "@uniswap/v4-periphery/src/utils/BaseHook.sol";
import {Hooks} from "@uniswap/v4-core/src/libraries/Hooks.sol";
import {IPoolManager} from "@uniswap/v4-core/src/interfaces/IPoolManager.sol";
import {PoolKey} from "@uniswap/v4-core/src/types/PoolKey.sol";
import {SafeCast} from "@uniswap/v4-core/src/libraries/SafeCast.sol";
import {PoolId, PoolIdLibrary} from "@uniswap/v4-core/src/types/PoolId.sol";
import {BalanceDelta} from "@uniswap/v4-core/src/types/BalanceDelta.sol";
import {Currency} from "@uniswap/v4-core/src/types/Currency.sol";
import {CurrencySettler} from "@uniswap/v4-core/test/utils/CurrencySettler.sol";
import {TickMath} from "@uniswap/v4-core/src/libraries/TickMath.sol";
import {IHooks} from "@uniswap/v4-core/src/interfaces/IHooks.sol";
import {StateLibrary} from "@uniswap/v4-core/src/libraries/StateLibrary.sol";
import {SafeTransferLib} from "solady/utils/SafeTransferLib.sol";
import {ReentrancyGuard} from "solady/utils/ReentrancyGuard.sol";
import {ModifyLiquidityParams, SwapParams} from "@uniswap/v4-core/src/types/PoolOperation.sol";
import {BeforeSwapDelta, BeforeSwapDeltaLibrary} from "@uniswap/v4-core/src/types/BeforeSwapDelta.sol";

interface IStrategyPunk {
    // View functions
    function loadingLiquidity() external view returns (bool);
    function owner() external view returns (address);
    function name() external pure returns (string memory);
    function symbol() external pure returns (string memory);
    function hookAddress() external view returns (address);
    function priceMultiplier() external view returns (uint256);
    function setMidSwap(bool value) external;
    function midSwap() external view returns (bool);
    function routerRestrict() external view returns (bool);

    // Mechanism functions
    function addFees() external payable;
    function buyPunkAndRelist(uint256 punkId) external returns (uint256);
    function processPunkSale() external returns (uint256);
    
    // Constants
    function MAX_SUPPLY() external pure returns (uint256);
    function DEADADDRESS() external pure returns (address);
}

interface IValidRouter {
    function msgSender() external view returns (address);
}


contract StrategyPunkHook is BaseHook, ReentrancyGuard {

    using PoolIdLibrary for PoolKey;
    using StateLibrary for IPoolManager;
    using SafeCast for uint256;
    using SafeCast for int128;
    using CurrencySettler for Currency;

    /* ™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™ */
    /*                      CONSTANTS                      */
    /* ™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™ */

    uint128 private constant TOTAL_BIPS = 10000;
    uint128 private constant DEFAULT_FEE = 1000; // 10%
    uint128 private constant STARTING_BUY_FEE = 9500; // 95%
    uint160 private constant MAX_PRICE_LIMIT = TickMath.MAX_SQRT_PRICE - 1;
    uint160 private constant MIN_PRICE_LIMIT = TickMath.MIN_SQRT_PRICE + 1;

    IStrategyPunk immutable strategyPunkFork;
    IPoolManager immutable manager;
    address public feeAddress;

    /* ™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™ */
    /*                   STATE VARIABLES                   */
    /* ™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™ */

    uint256 public deploymentBlock;

    /* ™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™ */
    /*                    CUSTOM ERRORS                    */
    /* ™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™ */

    error NotStrategyPunkFork();
    error NotStrategyPunkForkOwner();

    /* ™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™ */
    /*                    CUSTOM EVENTS                    */
    /* ™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™ */

    event HookFee(bytes32 indexed id, address indexed sender, uint128 feeAmount0, uint128 feeAmount1);
    event Trade(uint160 sqrtPriceX96, int128 ethAmount, int128 tokenAmount);

    /* ™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™ */
    /*                     CONSTRUCTOR                     */
    /* ™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™ */

    constructor(
        IPoolManager _poolManager,
        address _strategyPunkFork
    ) BaseHook(_poolManager) {
        manager = _poolManager;
        strategyPunkFork = IStrategyPunk(_strategyPunkFork);
        feeAddress = msg.sender;
    }

    /* ™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™ */
    /*                     FUNCTIONS                       */
    /* ™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™ */

    function updateFeeAddress(address _feeAddress) external {
        if (msg.sender != strategyPunkFork.owner()) revert NotStrategyPunkForkOwner();
        feeAddress = _feeAddress;
    }

    function _processFees(uint256 feeAmount) internal {
        if (feeAmount == 0) return;
        
        uint256 depositAmount = (feeAmount * 80) / 100;
        uint256 ownerAmount = feeAmount - depositAmount;

        strategyPunkFork.addFees{value: depositAmount}();
        
        SafeTransferLib.forceSafeTransferETH(feeAddress, ownerAmount);
    }

    function calculateFee(bool isBuying) public view returns (uint128) {
        if (!isBuying) return DEFAULT_FEE;

        uint256 deployedAt = deploymentBlock;
        if (deployedAt == 0) return DEFAULT_FEE;

        uint256 blocksPassed = block.number - deployedAt;
        uint256 feeReductions = (blocksPassed / 5) * 100; // bips to subtract

        uint256 maxReducible = STARTING_BUY_FEE - DEFAULT_FEE; // assumes invariant holds
        if (feeReductions >= maxReducible) return DEFAULT_FEE;

        return uint128(STARTING_BUY_FEE - feeReductions);
    }

    function getHookPermissions() public pure override returns (Hooks.Permissions memory) {
        return Hooks.Permissions({
            beforeInitialize: true,
            afterInitialize: false,
            beforeAddLiquidity: true,
            afterAddLiquidity: false,
            beforeRemoveLiquidity: false,
            afterRemoveLiquidity: false,
            beforeSwap: true,
            afterSwap: true,
            beforeDonate: false,
            afterDonate: false,
            beforeSwapReturnDelta: false,
            afterSwapReturnDelta: true,
            afterAddLiquidityReturnDelta: false,
            afterRemoveLiquidityReturnDelta: false
        });
    }

    function _beforeInitialize(address, PoolKey calldata key, uint160)
        internal
        override
        returns (bytes4)
    {        
        if(!strategyPunkFork.loadingLiquidity()) {
            revert NotStrategyPunkFork();
        }

        deploymentBlock = block.number;
        
        return BaseHook.beforeInitialize.selector;
    }

    /// @notice Validates liquidity addition to a pool
    function _beforeAddLiquidity(address, PoolKey calldata, ModifyLiquidityParams calldata, bytes calldata)
        internal
        view
        override
        returns (bytes4)
    {        
        // Ensure the call is coming from NFTStrategyFactory
        if(!strategyPunkFork.loadingLiquidity()) {
            revert NotStrategyPunkFork();
        }
        return BaseHook.beforeAddLiquidity.selector;
    }

    function _beforeSwap(
        address sender,
        PoolKey calldata key,
        SwapParams calldata params,
        bytes calldata data
    ) internal override returns (bytes4, BeforeSwapDelta, uint24) {
        // Set midSwap flag on NFTStrategy contract
        if (strategyPunkFork.routerRestrict()) {
            strategyPunkFork.setMidSwap(true);
        }
        return (BaseHook.beforeSwap.selector, BeforeSwapDeltaLibrary.ZERO_DELTA, 0);
    }

    function _afterSwap(
        address sender,
        PoolKey calldata key,
        SwapParams calldata params,
        BalanceDelta delta,
        bytes calldata
    ) internal override returns (bytes4, int128) {
        // Calculate fee based on the swap amount
        bool specifiedTokenIs0 = (params.amountSpecified < 0 == params.zeroForOne);
        (Currency feeCurrency, int128 swapAmount) =
            (specifiedTokenIs0) ? (key.currency1, delta.amount1()) : (key.currency0, delta.amount0());

        if (swapAmount < 0) swapAmount = -swapAmount;

        bool ethFee = Currency.unwrap(feeCurrency) == address(0);

        uint128 currentFee = calculateFee(params.zeroForOne);
        uint256 feeAmount = uint128(swapAmount) * currentFee / TOTAL_BIPS;

        if(feeAmount == 0) {
            return (BaseHook.afterSwap.selector, 0);
        }

        manager.take(feeCurrency, address(this), feeAmount);

        // Emit the HookFee event, after taking the fee
        emit HookFee(
            PoolId.unwrap(key.toId()),
            sender,
            ethFee ? uint128(feeAmount) : 0,
            ethFee ? 0 : uint128(feeAmount)
        );

        // Handle fee token deposit or conversion
        if (!ethFee) {
            uint256 feeInETH = _swapToEth(key, feeAmount);
            _processFees(feeInETH); 
        } else {
            // Fee amount is in ETH
            _processFees(feeAmount); 
        }

        // Get current price and emit 
        emit Trade(_getCurrentPrice(key), delta.amount0(), delta.amount1());

        // Set midSwap to false
        if (strategyPunkFork.routerRestrict()) {
            IStrategyPunk(Currency.unwrap(key.currency1)).setMidSwap(false);
        }
        return (BaseHook.afterSwap.selector, feeAmount.toInt128());
    }

    function _swapToEth(PoolKey memory key, uint256 amount) internal returns (uint256) {
        uint256 ethBefore = address(this).balance;
        
        BalanceDelta delta = manager.swap(
            key,
            SwapParams({
                zeroForOne: false,
                amountSpecified: -int256(amount),
                sqrtPriceLimitX96: MAX_PRICE_LIMIT
            }),
            bytes("")
        );

        // Handle token settlements
        if (delta.amount0() < 0) {
            key.currency0.settle(poolManager, address(this), uint256(int256(-delta.amount0())), false);
        } else if (delta.amount0() > 0) {
            key.currency0.take(poolManager, address(this), uint256(int256(delta.amount0())), false);
        }

        if (delta.amount1() < 0) {
            key.currency1.settle(poolManager, address(this), uint256(int256(-delta.amount1())), false);
        } else if (delta.amount1() > 0) {
            key.currency1.take(poolManager, address(this), uint256(int256(delta.amount1())), false);
        }

        return address(this).balance - ethBefore;
    }

    function _getCurrentPrice(PoolKey calldata key) internal view returns (uint160) {
        (uint160 sqrtPriceX96,,,) = poolManager.getSlot0(key.toId());
        return sqrtPriceX96;
    }

    /// @notice Allows the contract to receive ETH
    receive() external payable {}
}
