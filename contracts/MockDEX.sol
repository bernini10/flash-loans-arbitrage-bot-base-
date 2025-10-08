// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./IUnifiedDEX.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

contract MockDEX is IUnifiedDEX {
    mapping(address => mapping(address => uint256)) public prices;

    function swapExactTokensForTokens(uint amountIn, uint amountOutMin, address[] calldata path, address to, uint deadline) external override returns (uint[] memory amounts) {
        require(path.length == 2, "MockDEX: Invalid path");
        uint256 amountOut = (amountIn * prices[path[0]][path[1]]) / 1e18;
        require(amountOut >= amountOutMin, "MockDEX: Slippage");
        amounts = new uint[](2);
        amounts[0] = amountIn;
        amounts[1] = amountOut;

        IERC20(path[0]).transferFrom(msg.sender, address(this), amountIn);
        IERC20(path[1]).transfer(to, amountOut);

        return amounts;
    }

    function getAmountsOut(uint amountIn, address[] calldata path) external view override returns (uint[] memory amounts) {
        require(path.length == 2, "MockDEX: Invalid path");
        uint256 amountOut = (amountIn * prices[path[0]][path[1]]) / 1e18;
        amounts = new uint[](2);
        amounts[0] = amountIn;
        amounts[1] = amountOut;
        return amounts;
    }

    function setPrice(address tokenA, address tokenB, uint256 price) external {
        prices[tokenA][tokenB] = price;
    }
}
