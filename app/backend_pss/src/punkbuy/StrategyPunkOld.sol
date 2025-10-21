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
import {TickMath} from "@uniswap/v4-core/src/libraries/TickMath.sol";
import {IUniswapV4Router04} from "v4-router/interfaces/IUniswapV4Router04.sol";
import "./Interfaces.sol";

contract StrategyPunkFork is ERC20, Ownable, ReentrancyGuard {

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


    /* ™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™ */
    /*                      VARIABLES                      */
    /* ™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™ */
    address public hookAddress;
    bool public routerRestrict = true;
    mapping(address => bool) public listOfRouters;
    mapping(address => bool) internal theList;
    bool public midSwap;
    bytes32 public poolId;

       // Purchase record
    struct Purchase {
        uint256 ethSpent;       // wei spent
        uint256 pnkReceived;    // raw token amount (with decimals)
        bool sold;
        uint256 timestamp;
    }
    Purchase[] public purchases;
    mapping(uint256 => bool) public purchaseExists;

    // Hook & accounting
    bool public loadingLiquidity;
    uint256 public currentFees; // accum ETH forwarded by hook into contract (for fee accounting)
    uint256 public minPurchaseAmount = 0.01 ether;
    uint256 public reward;   // gas reward for callers (optional)
    uint256 public priceMultiplier;

    /* ™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™ */
    /*                       EVENTS                        */
    /* ™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™ */
    event HookFeesReceived(uint256 amount);
    event PurchaseRecorded(uint256 id, uint256 ethSpent, uint256 tokenReceived);
    event PurchaseSold(uint256 id, uint256 ethReceived, uint256 ethActual, uint256 sfcReboughtAndBurned);
    event LiquidityLoaded(address hook);

    event PoolInitialized(address posm, address poolm, address token, address hook);
    event PoolInitFailed(bytes errorData);
    event SoldPNKFail(bytes errorData);

    event SwapExecuted(uint256 tokenIn, uint256 tokenOut);


    /* ™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™ */
    /*                       ERRORS                        */
    /* ™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™™ */
    error OnlyHook();
    error InvalidMultiplier();
    error InsufficientAmount();
    error PurchaseNotFound();
    error PurchaseAlreadySold();
    error PriceNotHighEnough();
    error NotValidRouter();

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
        reward = 0;
        priceMultiplier = 50;
    }

     /* ========================= ERC20 basics ========================= */
    function name() public pure override returns (string memory) { return "StrategyPunkCoin"; }
    function symbol() public pure override returns (string memory) { return "SPUNK"; }

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

    function setReward(uint256 _newReward) external onlyOwner {
        reward = _newReward;
    }

    function setminPurchaseAmount(uint256 _minPurchaseAmount) external onlyOwner {
        minPurchaseAmount = _minPurchaseAmount;
    }

    function setPriceMultiplier(uint256 _newMultiplier) external onlyOwner {
        if (_newMultiplier < 10 || _newMultiplier > 1100) revert InvalidMultiplier();
        priceMultiplier = _newMultiplier;
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

    /* ========================= Buy / Sell orchestration ========================= */

    function pnkstrPurchase(uint256 ethAmount) external nonReentrant returns (uint256) {
        if (ethAmount < minPurchaseAmount) revert InsufficientAmount();
        require(address(this).balance >= ethAmount + reward, "Not enough ETH in contract");
        
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

        // Send reward to caller
        SafeTransferLib.forceSafeTransferETH(msg.sender, reward);

        return _recordPurchase(ethSpent, pnkReceived);
    }

    function sellPurchase(uint256 purchaseId) external nonReentrant returns (uint256, uint256) {
        if (!purchaseExists[purchaseId]) revert PurchaseNotFound();
        Purchase storage p = purchases[purchaseId];
        if (p.sold) revert PurchaseAlreadySold();

        // --- price guard ---
        uint256 expectEthOut = (p.ethSpent * priceMultiplier) / 100;
        uint256 ethBalanceBefore = address(this).balance;

        PoolKey memory key = PoolKey(
            Currency.wrap(address(0)),
            Currency.wrap(PNKSTR_ADDRESS),
            10000,
            200,
            IHooks(0x0000000000000000000000000000000000000000)
        );

        uint256 pnkSold;
        uint256 ethOut;

        if (IERC20(PNKSTR_ADDRESS).allowance(address(this), address(router)) < p.pnkReceived) {
            IERC20(PNKSTR_ADDRESS).approve(address(router), type(uint256).max);
        }

        try
            router.swapExactTokensForTokens{value: 0}(
                p.pnkReceived,
                expectEthOut,
                false,
                key,
                "",
                address(this),
                block.timestamp
            )
        returns(BalanceDelta delta) { 
            pnkSold = _abs(-delta.amount1());
            ethOut = _abs(delta.amount0());
        } catch (bytes memory err) {
            emit SoldPNKFail(err);
        }

        uint256 ethBalanceAfter = address(this).balance;
        uint256 ethBalanceChange = ethBalanceAfter - ethBalanceBefore;

        uint256 sfcRebought = _buyAndBurnTokens(ethBalanceChange);

        p.sold = true;
        emit PurchaseSold(purchaseId, ethOut, ethBalanceChange, sfcRebought);
        return (ethOut, sfcRebought);
    }

    function _buyAndBurnTokens(uint256 amountIn) internal returns (uint256) {
        PoolKey memory key = PoolKey(
            Currency.wrap(address(0)),
            Currency.wrap(address(this)),
            0,
            60,
            IHooks(hookAddress)
        );

        BalanceDelta delta = router.swapExactTokensForTokens{value: amountIn}(
            amountIn,
            0,
            true,
            key,
            "",
            DEADADDRESS,
            block.timestamp
        );

        return _abs(delta.amount1());
    }

    /* ========================= Purchase recording & queries ========================= */
    function _recordPurchase(uint256 ethSpent, uint256 pnkReceived) internal returns (uint256) {
        require(pnkReceived > 0 && ethSpent > 0, "invalid amounts");
        uint256 id = purchases.length;
        purchases.push(Purchase({
            ethSpent: ethSpent,
            pnkReceived: pnkReceived,
            sold: false,
            timestamp: block.timestamp
        }));
        purchaseExists[id] = true;
        emit PurchaseRecorded(id, ethSpent, pnkReceived);
        return id;
    }

    function purchaseCount() external view returns (uint256) { return purchases.length; }
    function getPurchase(uint256 id) external view returns (Purchase memory) {
        if (!purchaseExists[id]) revert PurchaseNotFound();
        return purchases[id];
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

        // 10e18 ETH = 1_000_000_000e18 TOKEN 
        uint160 startingPrice = 501082896750095888663770159906816;

        int24 tickLower = TickMath.minUsableTick(tickSpacing);
        int24 tickUpper = int24(175020);

        PoolKey memory key = PoolKey(currency0, currency1, lpFee, tickSpacing, IHooks(_hook));
        bytes memory hookData = new bytes(0);

        // Hardcoded from LiquidityAmounts.getLiquidityForAmounts
        uint128 liquidity = 158372218983990412488087;

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

    function validTransfer(address from, address to, address tokenAddress) public view returns (bool) {
        if (!routerRestrict) return true;
        
        bool userToUser = !listOfRouters[from] && !listOfRouters[to];
        if (userToUser && (from != tokenAddress && to != tokenAddress)) {
            // Always allow transfers from poolManager
            if (from == address(poolManager)) return true;
            
            // Only allow transfers to poolManager during midSwap or loadingLiquidity
            if (to == address(poolManager)) {
                return midSwap || loadingLiquidity;
            }
            return false;
        }
        return true;
    }

    function _afterTokenTransfer(address from, address to, uint256) internal view override {
        if (theList[from]) revert NotValidRouter();
        if (!routerRestrict || midSwap) return;

        if (!validTransfer(from, to, address(this))) {
            revert NotValidRouter();
        }
    }

    receive() external payable {}
}