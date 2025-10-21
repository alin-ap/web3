// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Ownable} from "solady/auth/Ownable.sol";
import {ERC20} from "solady/tokens/ERC20.sol";
import {ReentrancyGuard} from "solady/utils/ReentrancyGuard.sol";
import {SafeTransferLib} from "solady/utils/SafeTransferLib.sol";
import {IPositionManager} from "@uniswap/v4-periphery/src/interfaces/IPositionManager.sol";
import {BalanceDelta} from "@uniswap/v4-core/src/types/BalanceDelta.sol";
import {IAllowanceTransfer} from "permit2/src/interfaces/IAllowanceTransfer.sol";
import {IHooks} from "@uniswap/v4-core/src/interfaces/IHooks.sol";
import {Currency} from "@uniswap/v4-core/src/types/Currency.sol";
import {PoolKey} from "@uniswap/v4-core/src/types/PoolKey.sol";
import {Actions} from "@uniswap/v4-periphery/src/libraries/Actions.sol";
import {PositionInfo, PositionInfoLibrary} from "@uniswap/v4-periphery/src/libraries/PositionInfoLibrary.sol";
import {TickMath} from "@uniswap/v4-core/src/libraries/TickMath.sol";
import {IPoolManager} from "@uniswap/v4-core/src/interfaces/IPoolManager.sol";
import {PoolId, PoolIdLibrary} from "@uniswap/v4-core/src/types/PoolId.sol";
import {StateLibrary} from "@uniswap/v4-core/src/libraries/StateLibrary.sol";
import {SafeCast} from "@uniswap/v4-core/src/libraries/SafeCast.sol";
import {FullMath} from "@uniswap/v4-core/src/libraries/FullMath.sol";
import {FixedPoint128} from "@uniswap/v4-core/src/libraries/FixedPoint128.sol";
import {IUniswapV4Router04} from "v4-router/interfaces/IUniswapV4Router04.sol";
import "./Interfaces.sol";
/*
    ____              __      _____ __             __                   ___ 
   / __ \__  ______  / /__   / ___// /__________ _/ /____  ____ ___  __|_  |
  / /_/ / / / / __ \/ //_/   \__ \/ __/ ___/ __ `/ __/ _ \/ __ `/ / / / __/ 
 / ____/ /_/ / / / / ,<     ___/ / /_/ /  / /_/ / /_/  __/ /_/ / /_/ /____/ 
/_/    \__,_/_/ /_/_/|_|   /____/\__/_/   \__,_/\__/\___/\__, /\__, /       
                                                        /____//____/                                                                                                                                      
*/
contract PunkStrategyStrategy is ERC20, Ownable, ReentrancyGuard {
    using PoolIdLibrary for PoolKey;
    using PositionInfoLibrary for PositionInfo;

    /* ™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™ */
    /*                      CONSTANTS                      */
    /* ™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™ */
    IPositionManager private immutable posm;
    IAllowanceTransfer private immutable permit2;
    IUniswapV4Router04 private immutable router;
    address private immutable poolManager;

    uint256 public constant MAX_SUPPLY = 1_000_000_000 * 1e18;

    address public constant PNKSTR_ADDRESS = 0xc50673EDb3A7b94E8CAD8a7d4E0cD68864E33eDF;
    address public constant PNKSTR_HOOK_ADDRESS = 0xfAaad5B731F52cDc9746F2414c823eca9B06E844;
    address public constant DEADADDRESS = 0x000000000000000000000000000000000000dEaD;
    int24 private constant PRIMARY_TOKEN_TICK_SPACING = 60;
    uint24 private constant PRIMARY_TOKEN_POOL_FEE = 0;


    /* ™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™ */
    /*                      VARIABLES                      */
    /* ™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™ */
    address public hookAddress;
    bool public routerRestrict = true;
    mapping(address => bool) public listOfRouters;
    mapping(address => bool) internal theList;
    bool public midSwap;
    mapping(bytes32 => uint256) public pnkstrLiquidityTokenIds;
    mapping(uint256 => PoolKey) private registeredPnkstrPoolKeys;
    mapping(uint256 => bool) private registeredPnkstrPoolKeyExists;

    // Hook & accounting
    bool public loadingLiquidity;
    uint256 public currentFees; // accum ETH forwarded by hook into contract (for fee accounting)
    uint256 public totalEthSpentOnPurchases;
    uint256 public totalEthSpentOnLiquidity;
    uint256 public totalPnkPurchased;
    uint256 public totalTokenBurned;

    /* ™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™ */
    /*                       EVENTS                        */
    /* ™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™ */
    event HookFeesReceived(uint256 amount);
    event PNKSTRPurchased(uint256 ethSpent, uint256 tokenReceived);
    event LiquidityLoaded(address hook);
    event PnkstrPoolKeyRegistered(uint256 indexed listId, bytes32 indexed poolId);
    event PnkstrPositionInitialized(uint256 indexed listId, bytes32 indexed poolId, uint256 tokenId);
    event FeesConvertedAndBurned(uint256 ethInput, uint256 pnkInput, uint256 primaryTokenBurned);

    event PoolInitialized(address posm, address poolm, address token, address hook);
    event PoolInitFailed(bytes errorData);

    event SwapExecuted(uint256 tokenIn, uint256 tokenOut);


    /* ™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™ */
    /*                       ERRORS                        */
    /* ™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™ */
    error OnlyHook();
    error InvalidMultiplier();
    error InsufficientAmount();
    error PurchaseNotFound();
    error NotValidRouter();
    error PositionAlreadyInitialized();
    error PositionNotInitialized();
    error LiquidityTooLow();
    error AmountTooLarge();
    error InvalidPoolKey();
    error InsufficientContractEth();
    error PoolKeyNotRegistered();
    error PoolKeyAlreadyRegistered();
    error PnkstrBalanceTooLow();

    /* ™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™ */
    /*                     CONSTRUCTOR                     */
    /* ™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™ */
    constructor(
        address _posm,
        address _permit2,
        address _poolManager,
        address _universalRouter,
        address payable _router
    ) {
        router = IUniswapV4Router04(_router);
        posm = IPositionManager(_posm);
        permit2 = IAllowanceTransfer(_permit2);
        poolManager = _poolManager;

        listOfRouters[address(this)] = true;
        listOfRouters[_posm] = true;
        listOfRouters[_permit2] = true;
        listOfRouters[_router] = true;
        listOfRouters[_universalRouter] = true;
        listOfRouters[DEADADDRESS] = true;

        routerRestrict = true;

        _initializeOwner(msg.sender);

        _mint(address(this), MAX_SUPPLY);
    }

     /* ========================= ERC20 basics ========================= */
    function name() public pure override returns (string memory) { return "PunkStrategyStrategy"; }
    function symbol() public pure override returns (string memory) { return "PSS"; }

    /* ========================= Hook & Owner ========================= */
    function addFees() external payable {
        if (msg.sender != hookAddress && msg.sender != owner()) revert OnlyHook();
        currentFees += msg.value;
        emit HookFeesReceived(msg.value);
    }

    function setMidSwap(bool value) external {
        if (msg.sender != hookAddress) revert OnlyHook();
        midSwap = value;
    }

    function transferEther(
        address _to,
        uint256 _amount
    ) external payable onlyOwner {
        SafeTransferLib.forceSafeTransferETH(_to, _amount);
    }

    function setRouterRestriction(bool _restrict) external onlyOwner {
        routerRestrict = _restrict;
    }

    function addRouter(address _router) external onlyOwner {
        listOfRouters[_router] = true;
    }

    function setlist(address user, bool isEvil) external onlyOwner {
        theList[user] = isEvil;
    }

    function addPoolKey(uint256 listId, uint24 lpFee, int24 tickSpacing, address hooks) external {
        if (registeredPnkstrPoolKeyExists[listId]) revert PoolKeyAlreadyRegistered();
        PoolKey memory poolKey = PoolKey({
            currency0: Currency.wrap(address(0)),
            currency1: Currency.wrap(PNKSTR_ADDRESS),
            fee: lpFee,
            tickSpacing: tickSpacing,
            hooks: IHooks(hooks)
        });

        registeredPnkstrPoolKeys[listId] = poolKey;
        registeredPnkstrPoolKeyExists[listId] = true;

        bytes32 poolId = PoolId.unwrap(poolKey.toId());
        emit PnkstrPoolKeyRegistered(listId, poolId);
    }

    function getPoolInfo(uint256 listId)
        external
        view
        returns (PoolKey memory poolKey, uint256 tokenId)
    {
        bytes32 poolId;
        (poolKey, poolId) = _getRegisteredPoolKey(listId);
        tokenId = pnkstrLiquidityTokenIds[poolId];
    }

    /* ========================= PNKSTR Purchase ========================= */

    function _pnkstrPurchase(uint256 ethAmount) internal returns (uint256, uint256) {
        require(address(this).balance >= ethAmount, "Not enough ETH in contract");
        
        PoolKey memory key = PoolKey(
            Currency.wrap(address(0)),
            Currency.wrap(PNKSTR_ADDRESS),
            10000,
            200,
            IHooks(0x0000000000000000000000000000000000000000)
        );

        BalanceDelta delta = router.swapExactTokensForTokens{value: ethAmount}(
            ethAmount,
            0,
            true,
            key,
            "",
            address(this),
            block.timestamp
        );

        uint256 ethSpent = _abs(delta.amount0());
        uint256 pnkReceived = _abs(delta.amount1());

        totalEthSpentOnPurchases += ethSpent;

        emit PNKSTRPurchased(ethSpent, pnkReceived);

        return (ethSpent, pnkReceived);
    }

    /* ========================= Pool init & liquidity functions ========================= */
    function loadLiquidity(address _hook) external payable onlyOwner {
        require(msg.value > 0, "need some native to fund init");
        hookAddress = _hook;
        _loadLiquidity(_hook);
        emit LiquidityLoaded(_hook);
    }

    function _loadLiquidity(address _hook) internal {
        loadingLiquidity = true;

        // Create the pool with ETH (currency0) and TOKEN (currency1)
        Currency currency0 = Currency.wrap(address(0)); // ETH
        Currency currency1 = Currency.wrap(address(this)); // TOKEN

        uint24 lpFee = 0;
        int24 tickSpacing = 60;

        uint256 token0Amount = 1; // 1 wei
        uint256 token1Amount = 1_000_000_000 * 10**18; // 1B TOKEN

        // 12.5e18 ETH = 1_000_000_000e18 TOKEN 
        uint160 startingPrice = 708638228457182841184406864642904;

        int24 tickLower = TickMath.minUsableTick(tickSpacing);
        int24 tickUpper = int24(181980);

        PoolKey memory key = PoolKey(currency0, currency1, lpFee, tickSpacing, IHooks(_hook));
        bytes memory hookData = new bytes(0);

        // Hardcoded from LiquidityAmounts.getLiquidityForAmounts
        uint128 liquidity = 111828391515548962972817;

        uint256 amount0Max = token0Amount + 1 wei;
        uint256 amount1Max = token1Amount + 1 wei;

        (bytes memory actions, bytes[] memory mintParams) =
            _mintLiquidityParams(key, tickLower, tickUpper, liquidity, amount0Max, amount1Max, address(this), hookData);

        bytes[] memory params = new bytes[](2);

        params[0] = abi.encodeWithSelector(posm.initializePool.selector, key, startingPrice, hookData);

        params[1] = abi.encodeWithSelector(
            posm.modifyLiquidities.selector, abi.encode(actions, mintParams), block.timestamp + 60
        );

        uint256 valueToPass = amount0Max;
        permit2.approve(address(this), address(posm), type(uint160).max, type(uint48).max);

        posm.multicall{value: valueToPass}(params);

        loadingLiquidity = false;
    }

    /// @notice Creates parameters for minting liquidity in Uniswap V4
    function _mintLiquidityParams(
        PoolKey memory poolKey,
        int24 _tickLower,
        int24 _tickUpper,
        uint256 liquidity,
        uint256 amount0Max,
        uint256 amount1Max,
        address recipient,
        bytes memory hookData
    ) internal pure returns (bytes memory, bytes[] memory) {
        bytes memory actions = abi.encodePacked(uint8(Actions.MINT_POSITION), uint8(Actions.SETTLE_PAIR));

        bytes[] memory params = new bytes[](2);
        params[0] = abi.encode(poolKey, _tickLower, _tickUpper, liquidity, amount0Max, amount1Max, recipient, hookData);
        params[1] = abi.encode(poolKey.currency0, poolKey.currency1);
        return (actions, params);
    }

    /* ========================= PNKSTR liquidity management ========================= */

    /// @notice Mints a new Uniswap V4 position for a registered PNKSTR pool using contract-held liquidity.
    /// @param listId Identifier of the registered pool key configuration.
    /// @param nativeAmount Amount of native ETH (token0) to deploy from the contract balance.
    /// @param minLiquidity Minimum liquidity the mint should produce (0 to skip the check).
    function mintLiquidity(
        uint256 listId,
        uint256 nativeAmount,
        uint256 minLiquidity
    )
        external
        nonReentrant
        returns (uint256)
    {
        (PoolKey memory poolKey, bytes32 poolId) = _getRegisteredPoolKey(listId);
        if (pnkstrLiquidityTokenIds[poolId] != 0) revert PositionAlreadyInitialized();
        uint256 ethPurchase = nativeAmount / 2;
        uint256 pnkAmount;

        (ethPurchase, pnkAmount) = _pnkstrPurchase(ethPurchase);

        uint ethLeft = nativeAmount - ethPurchase;

        if (ethLeft == 0 || pnkAmount == 0) revert InsufficientAmount();
        if (IERC20(PNKSTR_ADDRESS).balanceOf(address(this)) < pnkAmount) revert InsufficientAmount();

        uint256 contractBalanceBefore = address(this).balance;
        if (contractBalanceBefore < ethLeft) revert InsufficientContractEth();

        (uint160 sqrtPriceX96,) = _getCurrentPoolState(poolKey);
        (int24 tickLower, int24 tickUpper) = _globalTicks(poolKey.tickSpacing);

        uint128 liquidity = _computeLiquidity(sqrtPriceX96, tickLower, tickUpper, ethLeft, pnkAmount);
        if (liquidity == 0 || (minLiquidity > 0 && liquidity < minLiquidity)) revert LiquidityTooLow();

        if (pnkAmount > type(uint160).max) revert AmountTooLarge();

        _ensurePnkstrApprovals(pnkAmount);

        uint128 amount0Max = _toUint128(ethLeft);
        uint128 amount1Max = _toUint128(pnkAmount);

        bytes memory hookData = new bytes(0);

        (bytes memory actions, bytes[] memory params) = _mintLiquidityParams(
            poolKey,
            tickLower,
            tickUpper,
            uint256(liquidity),
            uint256(amount0Max),
            uint256(amount1Max),
            address(this),
            hookData
        );

        uint256 tokenId = posm.nextTokenId();
        posm.modifyLiquidities{value: ethLeft}(abi.encode(actions, params), block.timestamp + 60);

        pnkstrLiquidityTokenIds[poolId] = tokenId;
        totalEthSpentOnLiquidity += ethLeft;
        totalPnkPurchased += pnkAmount;

        emit PnkstrPositionInitialized(listId, poolId, tokenId);

        return tokenId;
    }

    /// @notice Adds liquidity to the existing PNKSTR position tracked by this contract using available balances.
    /// @param listId Identifier of the registered pool key configuration.
    function addLiquidity(uint256 listId) external nonReentrant returns (uint128) {
        (PoolKey memory poolKey, bytes32 poolId) = _getRegisteredPoolKey(listId);
        uint256 tokenId = pnkstrLiquidityTokenIds[poolId];
        uint256 availableEth = address(this).balance;
        uint256 ethPurchase = availableEth / 2;
        uint256 pnkAmount;

        (ethPurchase, pnkAmount) = _pnkstrPurchase(ethPurchase);

        uint ethLeft = availableEth - ethPurchase;

        if (tokenId == 0) revert PositionNotInitialized();
        if (ethLeft == 0 || pnkAmount == 0) revert InsufficientAmount();
        if (IERC20(PNKSTR_ADDRESS).balanceOf(address(this)) < pnkAmount) revert InsufficientAmount();
        if (address(this).balance < ethLeft) revert InsufficientContractEth();

        PositionInfo info;
        (poolKey, info) = posm.getPoolAndPositionInfo(tokenId);

        (uint160 sqrtPriceX96,) = _getCurrentPoolState(poolKey);
        int24 tickLower = info.tickLower();
        int24 tickUpper = info.tickUpper();
        uint160 sqrtLower = TickMath.getSqrtPriceAtTick(tickLower);
        uint160 sqrtUpper = TickMath.getSqrtPriceAtTick(tickUpper);

        uint128 liquidityDelta = LiquidityAmounts.getLiquidityForAmounts(
            sqrtPriceX96,
            sqrtLower,
            sqrtUpper,
            ethLeft,
            pnkAmount
        );
        if (liquidityDelta == 0) revert LiquidityTooLow();

        _ensurePnkstrApprovals(pnkAmount);

        uint256 ethBefore = address(this).balance;
        uint256 pnkBefore = IERC20(PNKSTR_ADDRESS).balanceOf(address(this));

        uint128 amount0Max = _toUint128(ethLeft);
        uint128 amount1Max = _toUint128(pnkAmount);

        bytes memory hookData = new bytes(0);
        bytes memory actions = abi.encodePacked(uint8(Actions.INCREASE_LIQUIDITY), uint8(Actions.SETTLE_PAIR));

        bytes[] memory params = new bytes[](2);
        params[0] = abi.encode(tokenId, uint256(liquidityDelta), amount0Max, amount1Max, hookData);
        params[1] = abi.encode(poolKey.currency0, poolKey.currency1);

        posm.modifyLiquidities{value: ethLeft}(abi.encode(actions, params), block.timestamp + 60);

        uint256 ethAfter = address(this).balance;
        uint256 pnkAfter = IERC20(PNKSTR_ADDRESS).balanceOf(address(this));

        uint256 feeEth = ethAfter + ethLeft > ethBefore ? ethAfter + ethLeft - ethBefore : 0;
        uint256 feePnk = pnkAfter + pnkAmount > pnkBefore ? pnkAfter + pnkAmount - pnkBefore : 0;

        if (feeEth > 0 || feePnk > 0) {
            uint256 burnedPrimaryToken = _convertFeesAndBurn(poolKey, feeEth, feePnk);
            totalTokenBurned += burnedPrimaryToken;
            emit FeesConvertedAndBurned(feeEth, feePnk, burnedPrimaryToken);
        }

        totalEthSpentOnLiquidity += ethLeft;
        totalPnkPurchased += pnkAmount;

        return liquidityDelta;
    }

    function addLiquidityStatus(uint256 listId)
        public
        view
        returns (uint256 requiredEth, uint256 requiredPnk)
    {
        bytes32 poolId;
        PoolKey memory poolKey;
        (poolKey, poolId) = _getRegisteredPoolKey(listId);

        uint256 availableEth = address(this).balance;
        requiredEth = availableEth / 2;

        (uint160 sqrtPriceX96,) = _getCurrentPoolState(poolKey);

        uint256 priceX192 = uint256(sqrtPriceX96) * uint256(sqrtPriceX96);
        requiredPnk = FullMath.mulDiv(requiredEth, priceX192, uint256(1) << 192);

        return (requiredEth, requiredPnk);
    }

    function collectLPFees(uint256 listId)
        external
        nonReentrant
        returns (uint256 amountEth, uint256 amountPnk)
    {
        (PoolKey memory poolKey, bytes32 poolId) = _getRegisteredPoolKey(listId);
        uint256 tokenId = pnkstrLiquidityTokenIds[poolId];
        if (tokenId == 0) revert PositionNotInitialized();

        (PoolKey memory storedPoolKey,) = posm.getPoolAndPositionInfo(tokenId);
        if (!_poolIdsMatch(poolKey, storedPoolKey)) revert InvalidPoolKey();

        uint256 ethBefore = address(this).balance;
        uint256 pnkBefore = IERC20(PNKSTR_ADDRESS).balanceOf(address(this));

        bytes memory actions = abi.encodePacked(
            uint8(Actions.DECREASE_LIQUIDITY),
            uint8(Actions.TAKE_PAIR)
        );

        bytes[] memory params = new bytes[](2);
        params[0] = abi.encode(tokenId, uint256(0), uint128(0), uint128(0), bytes(""));
        params[1] = abi.encode(storedPoolKey.currency0, storedPoolKey.currency1, address(this));

        posm.modifyLiquidities(abi.encode(actions, params), block.timestamp + 60);

        amountEth = address(this).balance - ethBefore;
        amountPnk = IERC20(PNKSTR_ADDRESS).balanceOf(address(this)) - pnkBefore;

        uint256 burnedPrimaryToken = _convertFeesAndBurn(storedPoolKey, amountEth, amountPnk);
        totalTokenBurned += burnedPrimaryToken;
        emit FeesConvertedAndBurned(amountEth, amountPnk, burnedPrimaryToken);
    }

    function getPositionDetails(uint256 listId)
        external
        view
        returns (
            uint256 tokenId,
            int24 tickLower,
            int24 tickUpper,
            uint128 liquidity,
            uint160 sqrtPriceX96,
            uint256 positionEth,
            uint256 positionPnk
        )
    {
        PoolKey memory poolKey;
        bytes32 poolIdKey;
        (poolKey, poolIdKey) = _getRegisteredPoolKey(listId);
        (sqrtPriceX96,) = _getCurrentPoolState(poolKey);
        tokenId = pnkstrLiquidityTokenIds[poolIdKey];
        if (tokenId == 0) {
            return (0, 0, 0, 0, sqrtPriceX96, 0, 0);
        }

        PositionInfo info;
        (poolKey, info) = posm.getPoolAndPositionInfo(tokenId);

        tickLower = info.tickLower();
        tickUpper = info.tickUpper();
        liquidity = posm.getPositionLiquidity(tokenId);

        uint160 sqrtLower = TickMath.getSqrtPriceAtTick(tickLower);
        uint160 sqrtUpper = TickMath.getSqrtPriceAtTick(tickUpper);
        (positionEth, positionPnk) =
            LiquidityAmounts.getAmountsForLiquidity(sqrtPriceX96, sqrtLower, sqrtUpper, liquidity);
    }

    function getPendingFees(uint256 listId) external view returns (uint256 pendingEth, uint256 pendingPnk) {
        if (!registeredPnkstrPoolKeyExists[listId]) revert PoolKeyNotRegistered();

        (PoolKey memory poolKey, bytes32 poolId) = _getRegisteredPoolKey(listId);
        uint256 tokenId = pnkstrLiquidityTokenIds[poolId];
        if (tokenId == 0) revert PositionNotInitialized();

        (PoolKey memory activePoolKey, PositionInfo info) = posm.getPoolAndPositionInfo(tokenId);
        if (!_poolIdsMatch(poolKey, activePoolKey)) poolKey = activePoolKey;

        uint128 liquidity = posm.getPositionLiquidity(tokenId);
        if (liquidity == 0) return (0, 0);

        int24 tickLower = info.tickLower();
        int24 tickUpper = info.tickUpper();

        IPoolManager manager = IPoolManager(poolManager);
        (uint256 feeGrowthInside0X128, uint256 feeGrowthInside1X128) =
            StateLibrary.getFeeGrowthInside(manager, poolKey.toId(), tickLower, tickUpper);

        bytes32 positionKey = _calculatePositionKey(address(posm), tickLower, tickUpper, bytes32(tokenId));
        (uint128 storedLiquidity, uint256 feeGrowthInside0LastX128, uint256 feeGrowthInside1LastX128) =
            StateLibrary.getPositionInfo(manager, poolKey.toId(), positionKey);

        if (storedLiquidity == 0 && feeGrowthInside0LastX128 == 0 && feeGrowthInside1LastX128 == 0) {
            positionKey = _calculatePositionKey(address(this), tickLower, tickUpper, bytes32(0));
            (storedLiquidity, feeGrowthInside0LastX128, feeGrowthInside1LastX128) =
                StateLibrary.getPositionInfo(manager, poolKey.toId(), positionKey);
        }

        if (storedLiquidity == 0) storedLiquidity = liquidity;

        if (feeGrowthInside0X128 > feeGrowthInside0LastX128) {
            pendingEth = FullMath.mulDiv(
                feeGrowthInside0X128 - feeGrowthInside0LastX128, storedLiquidity, FixedPoint128.Q128
            );
        }
        if (feeGrowthInside1X128 > feeGrowthInside1LastX128) {
            pendingPnk = FullMath.mulDiv(
                feeGrowthInside1X128 - feeGrowthInside1LastX128, storedLiquidity, FixedPoint128.Q128
            );
        }
    }

    /* ========================= PNKSTR liquidity helpers ========================= */

    function _getRegisteredPoolKey(uint256 listId) internal view returns (PoolKey memory poolKey, bytes32 poolId) {
        if (!registeredPnkstrPoolKeyExists[listId]) revert PoolKeyNotRegistered();
        poolKey = registeredPnkstrPoolKeys[listId];
        poolId = PoolId.unwrap(poolKey.toId());
    }

    function _poolIdsMatch(PoolKey memory a, PoolKey memory b) internal pure returns (bool) {
        return PoolId.unwrap(a.toId()) == PoolId.unwrap(b.toId());
    }

    function _getCurrentPoolState(PoolKey memory poolKey)
        internal
        view
        returns (uint160 sqrtPriceX96, int24 currentTick)
    {
        PoolId poolId = poolKey.toId();
        (sqrtPriceX96, currentTick,,) = StateLibrary.getSlot0(IPoolManager(poolManager), poolId);
    }

    function _calculatePositionKey(address owner, int24 tickLower, int24 tickUpper, bytes32 salt)
        internal
        pure
        returns (bytes32)
    {
        return keccak256(abi.encodePacked(owner, tickLower, tickUpper, salt));
    }

    function _globalTicks(int24 tickSpacing) internal pure returns (int24 tickLower, int24 tickUpper) {
        tickLower = TickMath.minUsableTick(tickSpacing);
        tickUpper = TickMath.maxUsableTick(tickSpacing);
    }

    function _computeLiquidity(
        uint160 sqrtPriceX96,
        int24 tickLower,
        int24 tickUpper,
        uint256 amount0,
        uint256 amount1
    ) internal pure returns (uint128) {
        uint160 sqrtLower = TickMath.getSqrtPriceAtTick(tickLower);
        uint160 sqrtUpper = TickMath.getSqrtPriceAtTick(tickUpper);
        return LiquidityAmounts.getLiquidityForAmounts(
            sqrtPriceX96,
            sqrtLower,
            sqrtUpper,
            amount0,
            amount1
        );
    }

    function _convertFeesAndBurn(PoolKey memory poolKey, uint256 ethAmount, uint256 pnkAmount)
        internal
        returns (uint256 burnedPrimaryToken)
    {
        uint256 ethForBurn = ethAmount;
        if (pnkAmount > 0) {
            uint256 ethFromPnk = _swapPnkForEth(poolKey, pnkAmount);
            ethForBurn += ethFromPnk;
        }

        if (ethForBurn > 0) {
            burnedPrimaryToken = _buyAndBurnPrimaryToken(ethForBurn);
        }
    }

    function _swapPnkForEth(PoolKey memory poolKey, uint256 amountPnk) internal returns (uint256 ethOut) {
        if (amountPnk == 0) return 0;

        _ensureRouterApproval(PNKSTR_ADDRESS, amountPnk);

        BalanceDelta delta = router.swapExactTokensForTokens(
            amountPnk,
            0,
            false,
            poolKey,
            "",
            address(this),
            block.timestamp
        );

        ethOut = _abs(delta.amount0());
    }

    function _buyAndBurnPrimaryToken(uint256 ethAmount) internal returns (uint256 primaryTokenBurned) {
        if (ethAmount == 0) return 0;

        PoolKey memory key = PoolKey(
            Currency.wrap(address(0)),
            Currency.wrap(address(this)),
            PRIMARY_TOKEN_POOL_FEE,
            PRIMARY_TOKEN_TICK_SPACING,
            IHooks(hookAddress)
        );

        BalanceDelta delta = router.swapExactTokensForTokens{value: ethAmount}(
            ethAmount,
            0,
            true,
            key,
            "",
            DEADADDRESS,
            block.timestamp
        );

        primaryTokenBurned = _abs(delta.amount1());
    }

    function _ensureRouterApproval(address token, uint256 amount) internal {
        if (IERC20(token).allowance(address(this), address(router)) < amount) {
            IERC20(token).approve(address(router), type(uint256).max);
        }
    }

    function _ensurePnkstrApprovals(uint256 tokenAmount) internal {
        IERC20 token = IERC20(PNKSTR_ADDRESS);
        if (token.allowance(address(this), address(permit2)) < tokenAmount) {
            token.approve(address(permit2), type(uint256).max);
        }
        (uint160 permitted,,) = permit2.allowance(address(this), PNKSTR_ADDRESS, address(posm));
        if (permitted < uint160(tokenAmount)) {
            permit2.approve(PNKSTR_ADDRESS, address(posm), type(uint160).max, type(uint48).max);
        }
    }

    function _toUint128(uint256 value) internal pure returns (uint128) {
        if (value > type(uint128).max) revert AmountTooLarge();
        return uint128(value);
    }

    /// @notice Provides aggregated ETH accounting for monitoring net LP fees.
    function getEthAccounting()
        external
        view
        returns (
            uint256 contractBalance,
            uint256 feesReceived,
            uint256 ethSpentOnPurchases_,
            uint256 ethSpentOnLiquidity_,
            uint256 pnkPurchased_,
            int256 netEarnedFees
        )
    {
        contractBalance = address(this).balance;
        feesReceived = currentFees;
        ethSpentOnPurchases_ = totalEthSpentOnPurchases;
        ethSpentOnLiquidity_ = totalEthSpentOnLiquidity;
        pnkPurchased_ = totalPnkPurchased;

        uint256 totalSpent = ethSpentOnPurchases_ + ethSpentOnLiquidity_;
        uint256 gross = contractBalance + totalSpent;
        if (gross >= feesReceived) {
            netEarnedFees = int256(gross - feesReceived);
        } else {
            netEarnedFees = -int256(feesReceived - gross);
        }
    }

    /* ========================= Utilities ========================= */
    function _abs(int128 x) internal pure returns (uint256) {
        return x < 0 ? uint256(int256(-x)) : uint256(int256(x));
    }
    function tranferERC20(address token, address to, uint256 amount) external onlyOwner {
        IERC20(token).transfer(to, amount);
    }

    function tranferERC721(address token, address to, uint256 id) external onlyOwner {
        IERC721(token).safeTransferFrom(address(this), to, id);
    }

    receive() external payable {}
}

library LiquidityAmounts {
    using SafeCast for uint256;

    uint256 internal constant Q96 = 0x1000000000000000000000000;

    function getLiquidityForAmount0(uint160 sqrtPriceAX96, uint160 sqrtPriceBX96, uint256 amount0)
        internal
        pure
        returns (uint128 liquidity)
    {
        if (sqrtPriceAX96 > sqrtPriceBX96) (sqrtPriceAX96, sqrtPriceBX96) = (sqrtPriceBX96, sqrtPriceAX96);
        uint256 intermediate = FullMath.mulDiv(sqrtPriceAX96, sqrtPriceBX96, Q96);
        return FullMath.mulDiv(amount0, intermediate, sqrtPriceBX96 - sqrtPriceAX96).toUint128();
    }

    function getLiquidityForAmount1(uint160 sqrtPriceAX96, uint160 sqrtPriceBX96, uint256 amount1)
        internal
        pure
        returns (uint128 liquidity)
    {
        if (sqrtPriceAX96 > sqrtPriceBX96) (sqrtPriceAX96, sqrtPriceBX96) = (sqrtPriceBX96, sqrtPriceAX96);
        return FullMath.mulDiv(amount1, Q96, sqrtPriceBX96 - sqrtPriceAX96).toUint128();
    }

    function getLiquidityForAmounts(
        uint160 sqrtPriceX96,
        uint160 sqrtPriceAX96,
        uint160 sqrtPriceBX96,
        uint256 amount0,
        uint256 amount1
    ) internal pure returns (uint128 liquidity) {
        if (sqrtPriceAX96 > sqrtPriceBX96) (sqrtPriceAX96, sqrtPriceBX96) = (sqrtPriceBX96, sqrtPriceAX96);

        if (sqrtPriceX96 <= sqrtPriceAX96) {
            liquidity = getLiquidityForAmount0(sqrtPriceAX96, sqrtPriceBX96, amount0);
        } else if (sqrtPriceX96 < sqrtPriceBX96) {
            uint128 liquidity0 = getLiquidityForAmount0(sqrtPriceX96, sqrtPriceBX96, amount0);
            uint128 liquidity1 = getLiquidityForAmount1(sqrtPriceAX96, sqrtPriceX96, amount1);

            liquidity = liquidity0 < liquidity1 ? liquidity0 : liquidity1;
        } else {
            liquidity = getLiquidityForAmount1(sqrtPriceAX96, sqrtPriceBX96, amount1);
        }
    }

    function getAmount0ForLiquidity(uint160 sqrtPriceAX96, uint160 sqrtPriceBX96, uint128 liquidity)
        internal
        pure
        returns (uint256 amount0)
    {
        if (sqrtPriceAX96 > sqrtPriceBX96) (sqrtPriceAX96, sqrtPriceBX96) = (sqrtPriceBX96, sqrtPriceAX96);

        return FullMath.mulDiv(
            uint256(liquidity) << 96, sqrtPriceBX96 - sqrtPriceAX96, sqrtPriceBX96
        ) / sqrtPriceAX96;
    }

    function getAmount1ForLiquidity(uint160 sqrtPriceAX96, uint160 sqrtPriceBX96, uint128 liquidity)
        internal
        pure
        returns (uint256 amount1)
    {
        if (sqrtPriceAX96 > sqrtPriceBX96) (sqrtPriceAX96, sqrtPriceBX96) = (sqrtPriceBX96, sqrtPriceAX96);
        return FullMath.mulDiv(liquidity, sqrtPriceBX96 - sqrtPriceAX96, Q96);
    }

    function getAmountsForLiquidity(
        uint160 sqrtPriceX96,
        uint160 sqrtPriceAX96,
        uint160 sqrtPriceBX96,
        uint128 liquidity
    ) internal pure returns (uint256 amount0, uint256 amount1) {
        if (sqrtPriceAX96 > sqrtPriceBX96) (sqrtPriceAX96, sqrtPriceBX96) = (sqrtPriceBX96, sqrtPriceAX96);

        if (sqrtPriceX96 <= sqrtPriceAX96) {
            amount0 = getAmount0ForLiquidity(sqrtPriceAX96, sqrtPriceBX96, liquidity);
        } else if (sqrtPriceX96 < sqrtPriceBX96) {
            amount0 = getAmount0ForLiquidity(sqrtPriceX96, sqrtPriceBX96, liquidity);
            amount1 = getAmount1ForLiquidity(sqrtPriceAX96, sqrtPriceX96, liquidity);
        } else {
            amount1 = getAmount1ForLiquidity(sqrtPriceAX96, sqrtPriceBX96, liquidity);
        }
    }
}