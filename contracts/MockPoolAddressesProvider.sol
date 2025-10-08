// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@aave/core-v3/contracts/interfaces/IPoolAddressesProvider.sol";

contract MockPoolAddressesProvider is IPoolAddressesProvider {
    address private pool;

    constructor(address _pool) {
        pool = _pool;
    }

    function getPool() external view override returns (address) {
        return pool;
    }

    function setPool(address _pool) external {
        pool = _pool;
    }

    function getMarketId() external view override returns (string memory) { return ""; }
    function setMarketId(string calldata marketId) external override {} 
    function getAddress(bytes32 id) external view override returns (address) { return address(0); }
    function getACLManager() external view override returns (address) { return address(0); }
    function setACLManager(address aclManager) external override {} 
    function getPriceOracle() external view override returns (address) { return address(0); }
    function setPriceOracle(address priceOracle) external override {} 
    function getPriceOracleSentinel() external view override returns (address) { return address(0); }
    function setPriceOracleSentinel(address priceOracleSentinel) external override {} 
    function setAddress(bytes32 id, address newAddress) external override {} 
    function setAddressAsProxy(bytes32 id, address newImplementation) external override {}
    function getACLAdmin() external view override returns (address) { return address(0); }
    function getPoolConfigurator() external view override returns (address) { return address(0); }
    function getPoolDataProvider() external view override returns (address) { return address(0); }
    function setACLAdmin(address newAclAdmin) external override {}
    function setPoolConfiguratorImpl(address newPoolConfiguratorImpl) external override {}
    function setPoolDataProvider(address newDataProvider) external override {}
    function setPoolImpl(address newPoolImpl) external override {}
}
