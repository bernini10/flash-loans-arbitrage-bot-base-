// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@aave/core-v3/contracts/interfaces/IPool.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "./IFlashLoanSimpleReceiver.sol";

contract MockAAVEPool is IPool {
    function flashLoanSimple(address receiverAddress, address asset, uint256 amount, bytes calldata params, uint16 referralCode) external {
        IERC20(asset).transfer(receiverAddress, amount);
        IFlashLoanSimpleReceiver(receiverAddress).executeOperation(asset, amount, 0, msg.sender, params);
        IERC20(asset).transferFrom(receiverAddress, address(this), amount);
    }

    function supply(address asset, uint256 amount, address onBehalfOf, uint16 referralCode) external override {}
    function withdraw(address asset, uint256 amount, address to) external override returns (uint256) { return 0; }
    function borrow(address asset, uint256 amount, uint256 interestRateMode, uint16 referralCode, address onBehalfOf) external override {}
    function repay(address asset, uint256 amount, uint256 interestRateMode, address onBehalfOf) external override returns (uint256) { return 0; }
    function repayWithATokens(address asset, uint256 amount, uint256 interestRateMode) external override returns (uint256) { return 0; }
    function repayWithPermit(address asset, uint256 amount, uint256 interestRateMode, address onBehalfOf, uint256 deadline, uint8 permitV, bytes32 permitR, bytes32 permitS) external override returns (uint256) { return 0; }
    function swapBorrowRateMode(address asset, uint256 interestRateMode) external override {}
    function rebalanceStableBorrowRate(address asset, address user) external override {}
    function setUserUseReserveAsCollateral(address asset, bool useAsCollateral) external override {}
    function liquidationCall(address collateralAsset, address debtAsset, address user, uint256 debtToCover, bool receiveAToken) external override {}
    function flashLoan(address receiverAddress, address[] calldata assets, uint256[] calldata amounts, uint256[] calldata interestRateModes, address onBehalfOf, bytes calldata params, uint16 referralCode) external override {}
    function getReserveData(address asset) external view override returns (DataTypes.ReserveData memory) { DataTypes.ReserveData memory data; return data; }
    function getUserAccountData(address user) external view override returns (uint256, uint256, uint256, uint256, uint256, uint256) { return (0,0,0,0,0,0); }
    function getConfiguration(address asset) external view override returns (DataTypes.ReserveConfigurationMap memory) { DataTypes.ReserveConfigurationMap memory config; return config; }
    function getUserConfiguration(address user) external view override returns (DataTypes.UserConfigurationMap memory) { DataTypes.UserConfigurationMap memory config; return config; }
    function getReserveNormalizedIncome(address asset) external view override returns (uint256) { return 0; }
    function getReserveNormalizedVariableDebt(address asset) external view override returns (uint256) { return 0; }
    function getReservesList() external view override returns (address[] memory) { address[] memory a; return a; }
    function getReserveAddressById(uint16 id) external view override returns (address) { return address(0); }
    function ADDRESSES_PROVIDER() external view override returns (IPoolAddressesProvider) { return IPoolAddressesProvider(address(0)); }
    function backUnbacked(address asset, uint256 amount, uint256 fee) external override returns (uint256) { return 0; }
    function mintUnbacked(address asset, uint256 amount, address onBehalfOf, uint16 referralCode) external override {}
    function supplyWithPermit(address asset, uint256 amount, address onBehalfOf, uint16 referralCode, uint256 deadline, uint8 permitV, bytes32 permitR, bytes32 permitS) external override {}
    function deposit(address asset, uint256 amount, address onBehalfOf, uint16 referralCode) external override {}
    function finalizeTransfer(address asset, address from, address to, uint256 amount, uint256 balanceFromBefore, uint256 balanceToBefore) external override {}
    function initReserve(address asset, address aTokenAddress, address stableDebtAddress, address variableDebtAddress, address interestRateStrategyAddress) external override {}
    function dropReserve(address asset) external override {}
    function setReserveInterestRateStrategyAddress(address asset, address rateStrategyAddress) external override {}
    function setConfiguration(address asset, DataTypes.ReserveConfigurationMap calldata configuration) external override {}
    function configureEModeCategory(uint8 id, DataTypes.EModeCategory calldata config) external override {}
    function getEModeCategoryData(uint8 id) external view override returns (DataTypes.EModeCategory memory) { DataTypes.EModeCategory memory config; return config; }
    function setUserEMode(uint8 categoryId) external override {}
    function getUserEMode(address user) external view override returns (uint256) { return 0; }
    function resetIsolationModeTotalDebt(address asset) external override {}
    function MAX_STABLE_RATE_BORROW_SIZE_PERCENT() external view override returns (uint256) { return 0; }
    function FLASHLOAN_PREMIUM_TOTAL() external view override returns (uint128) { return 0; }
    function BRIDGE_PROTOCOL_FEE() external view override returns (uint256) { return 0; }
    function FLASHLOAN_PREMIUM_TO_PROTOCOL() external view override returns (uint128) { return 0; }
    function MAX_NUMBER_RESERVES() external view override returns (uint16) { return 0; }
    function mintToTreasury(address[] calldata assets) external override {}
    function rescueTokens(address token, address to, uint256 amount) external override {}
    function updateBridgeProtocolFee(uint256 bridgeProtocolFee) external override {}
    function updateFlashloanPremiums(uint128 flashLoanPremiumTotal, uint128 flashLoanPremiumToProtocol) external override {}
}
