// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./IUnifiedDEX.sol";

import "@aave/core-v3/contracts/interfaces/IPoolAddressesProvider.sol";
import "@aave/core-v3/contracts/interfaces/IPool.sol";
import "@aave/core-v3/contracts/flashloan/base/FlashLoanSimpleReceiverBase.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

contract FlashArbitrage is FlashLoanSimpleReceiverBase, Ownable, ReentrancyGuard {
    struct ArbitrageParams {
        address tokenA;
        address tokenB;
        address dexBuy;
        address dexSell;
        uint256 amountIn;
        uint256 minProfitBps;
        uint256 deadline;
    }

    mapping(address => bool) public authorizedCallers;
    mapping(address => bool) public supportedDEXs;
    uint256 public maxSlippageBps = 300;
    uint256 public minProfitThreshold = 50;

    event ArbitrageExecuted(address indexed tokenA, address indexed tokenB, address indexed dexBuy, address dexSell, uint256 amountBorrowed, uint256 profit, address executor);
    event ProfitWithdrawn(address indexed token, uint256 amount, address indexed to);
    event ConfigurationUpdated(uint256 maxSlippageBps, uint256 minProfitThreshold);

    modifier onlyAuthorized() {
        require(authorizedCallers[msg.sender] || msg.sender == owner(), "FlashArbitrage: Not authorized");
        _;
    }

        constructor(address _addressProvider) FlashLoanSimpleReceiverBase(IPoolAddressesProvider(_addressProvider)) Ownable(msg.sender) {
        authorizedCallers[owner()] = true;
    }

    function executeArbitrage(ArbitrageParams calldata params) external onlyAuthorized nonReentrant {
        require(params.tokenA != address(0) && params.tokenB != address(0) && params.amountIn > 0 && params.deadline > block.timestamp, "FlashArbitrage: Invalid params");
        require(supportedDEXs[params.dexBuy] && supportedDEXs[params.dexSell], "FlashArbitrage: Unsupported DEX");
        uint256 expectedProfit = calculateProfit(params);
        require(expectedProfit >= (params.amountIn * params.minProfitBps) / 10000, "FlashArbitrage: Insufficient profit");
        bytes memory data = abi.encode(params, msg.sender);
        POOL.flashLoanSimple(address(this), params.tokenA, params.amountIn, data, 0);
    }

    function executeOperation(address asset, uint256 amount, uint256 premium, address initiator, bytes calldata params) external override returns (bool) {
        require(msg.sender == address(POOL) && initiator == address(this), "FlashArbitrage: Invalid call");
        (ArbitrageParams memory arbParams, address executor) = abi.decode(params, (ArbitrageParams, address));
        uint256 profit = _performArbitrage(arbParams, amount);
        uint256 amountOwed = amount + premium;
        require(IERC20(asset).balanceOf(address(this)) >= amountOwed, "FlashArbitrage: Insufficient funds");
        IERC20(asset).approve(address(POOL), amountOwed);
        if (profit > 0) {
            IERC20(asset).transfer(executor, profit);
        }
        emit ArbitrageExecuted(arbParams.tokenA, arbParams.tokenB, arbParams.dexBuy, arbParams.dexSell, amount, profit, executor);
        return true;
    }

    function _performArbitrage(ArbitrageParams memory params, uint256 amount) internal returns (uint256 profit) {
        IERC20(params.tokenA).approve(params.dexBuy, amount);
        address[] memory path1 = new address[](2); path1[0] = params.tokenA; path1[1] = params.tokenB;
        uint[] memory amounts1 = IUnifiedDEX(params.dexBuy).swapExactTokensForTokens(amount, _calculateMinAmountOut(amount, path1, params.dexBuy), path1, address(this), params.deadline);
        uint256 tokenBReceived = amounts1[1];
        IERC20(params.tokenB).approve(params.dexSell, tokenBReceived);
        address[] memory path2 = new address[](2); path2[0] = params.tokenB; path2[1] = params.tokenA;
        uint[] memory amounts2 = IUnifiedDEX(params.dexSell).swapExactTokensForTokens(tokenBReceived, amount, path2, address(this), params.deadline);
        uint256 tokenAFinal = amounts2[1];
        profit = tokenAFinal > amount ? tokenAFinal - amount : 0;
    }

    function calculateProfit(ArbitrageParams calldata params) public view returns (uint256) {
        try this._simulateArbitrage(params) returns (uint256 profit) { return profit; } catch { return 0; }
    }

    function _simulateArbitrage(ArbitrageParams calldata params) external view returns (uint256) {
        address[] memory path1 = new address[](2); path1[0] = params.tokenA; path1[1] = params.tokenB;
        uint[] memory amounts1 = IUnifiedDEX(params.dexBuy).getAmountsOut(params.amountIn, path1);
        address[] memory path2 = new address[](2); path2[0] = params.tokenB; path2[1] = params.tokenA;
        uint[] memory amounts2 = IUnifiedDEX(params.dexSell).getAmountsOut(amounts1[1], path2);
        return amounts2[1] > params.amountIn ? amounts2[1] - params.amountIn : 0;
    }

    function _calculateMinAmountOut(uint256 amountIn, address[] memory path, address dex) internal view returns (uint256) {
        uint[] memory amounts = IUnifiedDEX(dex).getAmountsOut(amountIn, path);
        return amounts[1] * (10000 - maxSlippageBps) / 10000;
    }

    function addAuthorizedCaller(address caller) external onlyOwner { authorizedCallers[caller] = true; }
    function removeAuthorizedCaller(address caller) external onlyOwner { authorizedCallers[caller] = false; }
    function addSupportedDEX(address dex) external onlyOwner { supportedDEXs[dex] = true; }
    function removeSupportedDEX(address dex) external onlyOwner { supportedDEXs[dex] = false; }
    function updateConfiguration(uint256 _maxSlippageBps, uint256 _minProfitThreshold) external onlyOwner {
        maxSlippageBps = _maxSlippageBps;
        minProfitThreshold = _minProfitThreshold;
        emit ConfigurationUpdated(_maxSlippageBps, _minProfitThreshold);
    }
    function emergencyWithdraw(address token, address to) external onlyOwner {
        uint256 balance = IERC20(token).balanceOf(address(this));
        if (balance > 0) { IERC20(token).transfer(to, balance); emit ProfitWithdrawn(token, balance, to); }
    }
    receive() external payable {}
}
