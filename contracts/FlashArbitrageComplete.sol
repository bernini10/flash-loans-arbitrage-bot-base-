// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";

interface IUniswapV2Router {
    function swapExactTokensForTokens(
        uint amountIn,
        uint amountOutMin,
        address[] calldata path,
        address to,
        uint deadline
    ) external returns (uint[] memory amounts);
    
    function getAmountsOut(uint amountIn, address[] calldata path)
        external view returns (uint[] memory amounts);
}

interface IFlashLoanReceiver {
    function executeOperation(
        address[] calldata assets,
        uint256[] calldata amounts,
        uint256[] calldata premiums,
        address initiator,
        bytes calldata params
    ) external returns (bool);
}

interface ILendingPoolAddressesProvider {
    function getLendingPool() external view returns (address);
}

interface ILendingPool {
    function flashLoan(
        address receiverAddress,
        address[] calldata assets,
        uint256[] calldata amounts,
        uint256[] calldata modes,
        address onBehalfOf,
        bytes calldata params,
        uint16 referralCode
    ) external;
}

contract FlashArbitrageComplete is IFlashLoanReceiver, Ownable, ReentrancyGuard, Pausable {
    
    struct ArbitrageParams {
        address tokenA;
        address tokenB;
        address dexBuy;
        address dexSell;
        uint256 amountIn;
        uint256 minProfitBps;
        uint256 maxSlippageBps;
        uint256 deadline;
    }

    // State variables
    ILendingPoolAddressesProvider public immutable ADDRESSES_PROVIDER;
    ILendingPool public immutable LENDING_POOL;
    
    mapping(address => bool) public authorizedCallers;
    mapping(address => bool) public supportedDEXs;
    mapping(address => bool) public supportedTokens;
    
    uint256 public constant MAX_BPS = 10000;
    uint256 public maxSlippageBps = 300; // 3%
    uint256 public minProfitThreshold = 50; // 0.5%
    uint256 public maxGasPrice = 50 gwei;
    uint256 public emergencyWithdrawDelay = 24 hours;
    uint256 public emergencyWithdrawRequestTime;

    // Events
    event ArbitrageExecuted(
        address indexed tokenA,
        address indexed tokenB,
        address indexed dexBuy,
        address dexSell,
        uint256 amountBorrowed,
        uint256 profit,
        address executor
    );
    
    event ProfitWithdrawn(address indexed token, uint256 amount, address indexed to);
    event ConfigurationUpdated(uint256 maxSlippageBps, uint256 minProfitThreshold);
    event EmergencyWithdrawRequested(uint256 executeTime);
    event FlashLoanFailed(string reason);

    // Modifiers
    modifier onlyAuthorized() {
        require(authorizedCallers[msg.sender] || msg.sender == owner(), "Not authorized");
        _;
    }

    modifier validGasPrice() {
        require(tx.gasprice <= maxGasPrice, "Gas price too high");
        _;
    }

    constructor(address _addressesProvider) Ownable(msg.sender) {
        require(_addressesProvider != address(0), "Invalid addresses provider");
        
        ADDRESSES_PROVIDER = ILendingPoolAddressesProvider(_addressesProvider);
        LENDING_POOL = ILendingPool(ADDRESSES_PROVIDER.getLendingPool());
        
        authorizedCallers[owner()] = true;
        
        // Add common Base network tokens
        supportedTokens[0x4200000000000000000000000000000000000006] = true; // WETH
        supportedTokens[0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913] = true; // USDC
        
        // Add common Base DEXs
        supportedDEXs[0xd0b53D9277642d899DF5C87A3966A349A798F224] = true; // Uniswap V3
        supportedDEXs[0x57713F7716e0b0F65ec116912F834E49805480d2] = true; // SushiSwap V3
        supportedDEXs[0xcDAC0d6c6C59727a65F871236188350531885C43] = true; // Aerodrome
    }

    function executeArbitrage(ArbitrageParams calldata params) 
        external 
        onlyAuthorized 
        nonReentrant 
        whenNotPaused 
        validGasPrice 
    {
        require(_validateParams(params), "Invalid parameters");
        
        // Calculate expected profit before executing
        uint256 expectedProfit = calculateProfit(params);
        require(expectedProfit >= (params.amountIn * params.minProfitBps) / MAX_BPS, "Insufficient profit");
        
        // Prepare flash loan
        address[] memory assets = new address[](1);
        assets[0] = params.tokenA;
        
        uint256[] memory amounts = new uint256[](1);
        amounts[0] = params.amountIn;
        
        uint256[] memory modes = new uint256[](1);
        modes[0] = 0; // No open debt
        
        bytes memory data = abi.encode(params, msg.sender);
        
        try LENDING_POOL.flashLoan(
            address(this),
            assets,
            amounts,
            modes,
            address(this),
            data,
            0
        ) {
            // Flash loan executed successfully
        } catch Error(string memory reason) {
            emit FlashLoanFailed(reason);
            revert(string(abi.encodePacked("Flash loan failed: ", reason)));
        }
    }

    function executeOperation(
        address[] calldata assets,
        uint256[] calldata amounts,
        uint256[] calldata premiums,
        address initiator,
        bytes calldata params
    ) external override returns (bool) {
        require(msg.sender == address(LENDING_POOL), "Invalid caller");
        require(initiator == address(this), "Invalid initiator");
        
        (ArbitrageParams memory arbParams, address executor) = abi.decode(params, (ArbitrageParams, address));
        
        uint256 profit = _performArbitrage(arbParams, amounts[0]);
        uint256 amountOwed = amounts[0] + premiums[0];
        
        require(IERC20(assets[0]).balanceOf(address(this)) >= amountOwed, "Insufficient funds to repay");
        
        // Approve repayment
        IERC20(assets[0]).approve(address(LENDING_POOL), amountOwed);
        
        // Transfer profit to executor
        if (profit > 0) {
            IERC20(assets[0]).transfer(executor, profit);
        }
        
        emit ArbitrageExecuted(
            arbParams.tokenA,
            arbParams.tokenB,
            arbParams.dexBuy,
            arbParams.dexSell,
            amounts[0],
            profit,
            executor
        );
        
        return true;
    }

    function _performArbitrage(ArbitrageParams memory params, uint256 amount) internal returns (uint256 profit) {
        // Step 1: Buy tokenB with tokenA on dexBuy
        IERC20(params.tokenA).approve(params.dexBuy, amount);
        
        address[] memory path1 = new address[](2);
        path1[0] = params.tokenA;
        path1[1] = params.tokenB;
        
        uint256 minAmountOut1 = _calculateMinAmountOut(amount, path1, params.dexBuy, params.maxSlippageBps);
        
        uint256[] memory amounts1 = IUniswapV2Router(params.dexBuy).swapExactTokensForTokens(
            amount,
            minAmountOut1,
            path1,
            address(this),
            params.deadline
        );
        
        uint256 tokenBReceived = amounts1[1];
        
        // Step 2: Sell tokenB for tokenA on dexSell
        IERC20(params.tokenB).approve(params.dexSell, tokenBReceived);
        
        address[] memory path2 = new address[](2);
        path2[0] = params.tokenB;
        path2[1] = params.tokenA;
        
        uint256 minAmountOut2 = _calculateMinAmountOut(tokenBReceived, path2, params.dexSell, params.maxSlippageBps);
        
        uint256[] memory amounts2 = IUniswapV2Router(params.dexSell).swapExactTokensForTokens(
            tokenBReceived,
            minAmountOut2,
            path2,
            address(this),
            params.deadline
        );
        
        uint256 tokenAFinal = amounts2[1];
        
        // Calculate profit
        profit = tokenAFinal > amount ? tokenAFinal - amount : 0;
    }

    function calculateProfit(ArbitrageParams calldata params) public view returns (uint256) {
        try this._simulateArbitrage(params) returns (uint256 profit) {
            return profit;
        } catch {
            return 0;
        }
    }

    function _simulateArbitrage(ArbitrageParams calldata params) external view returns (uint256) {
        address[] memory path1 = new address[](2);
        path1[0] = params.tokenA;
        path1[1] = params.tokenB;
        
        uint256[] memory amounts1 = IUniswapV2Router(params.dexBuy).getAmountsOut(params.amountIn, path1);
        
        address[] memory path2 = new address[](2);
        path2[0] = params.tokenB;
        path2[1] = params.tokenA;
        
        uint256[] memory amounts2 = IUniswapV2Router(params.dexSell).getAmountsOut(amounts1[1], path2);
        
        return amounts2[1] > params.amountIn ? amounts2[1] - params.amountIn : 0;
    }

    function _calculateMinAmountOut(
        uint256 amountIn,
        address[] memory path,
        address dex,
        uint256 slippageBps
    ) internal view returns (uint256) {
        uint256[] memory amounts = IUniswapV2Router(dex).getAmountsOut(amountIn, path);
        return amounts[1] * (MAX_BPS - slippageBps) / MAX_BPS;
    }

    function _validateParams(ArbitrageParams calldata params) internal view returns (bool) {
        return (
            params.tokenA != address(0) &&
            params.tokenB != address(0) &&
            params.tokenA != params.tokenB &&
            params.dexBuy != address(0) &&
            params.dexSell != address(0) &&
            params.dexBuy != params.dexSell &&
            params.amountIn > 0 &&
            params.deadline > block.timestamp &&
            params.maxSlippageBps <= 1000 && // Max 10% slippage
            supportedTokens[params.tokenA] &&
            supportedTokens[params.tokenB] &&
            supportedDEXs[params.dexBuy] &&
            supportedDEXs[params.dexSell]
        );
    }

    // Admin functions
    function addAuthorizedCaller(address caller) external onlyOwner {
        authorizedCallers[caller] = true;
    }

    function removeAuthorizedCaller(address caller) external onlyOwner {
        authorizedCallers[caller] = false;
    }

    function addSupportedDEX(address dex) external onlyOwner {
        supportedDEXs[dex] = true;
    }

    function removeSupportedDEX(address dex) external onlyOwner {
        supportedDEXs[dex] = false;
    }

    function addSupportedToken(address token) external onlyOwner {
        supportedTokens[token] = true;
    }

    function removeSupportedToken(address token) external onlyOwner {
        supportedTokens[token] = false;
    }

    function updateConfiguration(
        uint256 _maxSlippageBps,
        uint256 _minProfitThreshold,
        uint256 _maxGasPrice
    ) external onlyOwner {
        require(_maxSlippageBps <= 1000, "Slippage too high");
        require(_minProfitThreshold <= 1000, "Profit threshold too high");
        
        maxSlippageBps = _maxSlippageBps;
        minProfitThreshold = _minProfitThreshold;
        maxGasPrice = _maxGasPrice;
        
        emit ConfigurationUpdated(_maxSlippageBps, _minProfitThreshold);
    }

    function pause() external onlyOwner {
        _pause();
    }

    function unpause() external onlyOwner {
        _unpause();
    }

    function requestEmergencyWithdraw() external onlyOwner {
        emergencyWithdrawRequestTime = block.timestamp;
        emit EmergencyWithdrawRequested(block.timestamp + emergencyWithdrawDelay);
    }

    function emergencyWithdraw(address token, address to) external onlyOwner {
        require(
            emergencyWithdrawRequestTime != 0 && 
            block.timestamp >= emergencyWithdrawRequestTime + emergencyWithdrawDelay,
            "Emergency withdraw not ready"
        );
        
        uint256 balance = IERC20(token).balanceOf(address(this));
        if (balance > 0) {
            IERC20(token).transfer(to, balance);
            emit ProfitWithdrawn(token, balance, to);
        }
        
        emergencyWithdrawRequestTime = 0;
    }

    function withdrawProfit(address token, address to, uint256 amount) external onlyOwner {
        require(amount > 0, "Amount must be greater than 0");
        require(IERC20(token).balanceOf(address(this)) >= amount, "Insufficient balance");
        
        IERC20(token).transfer(to, amount);
        emit ProfitWithdrawn(token, amount, to);
    }

    // View functions
    function getContractBalance(address token) external view returns (uint256) {
        return IERC20(token).balanceOf(address(this));
    }

    function isAuthorizedCaller(address caller) external view returns (bool) {
        return authorizedCallers[caller];
    }

    function isSupportedDEX(address dex) external view returns (bool) {
        return supportedDEXs[dex];
    }

    function isSupportedToken(address token) external view returns (bool) {
        return supportedTokens[token];
    }

    // Fallback functions
    receive() external payable {}
    
    fallback() external payable {}
}
