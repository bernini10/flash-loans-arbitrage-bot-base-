// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import "forge-std/Script.sol";
import "./contracts/FlashArbitrage.sol";

contract DeployScript is Script {
    function run() external {
        vm.startBroadcast();
        FlashArbitrage arbitrage = new FlashArbitrage(0xe20fCBdBfFC4Dd138cE8b2E6FBb6CB49777ad64D);
        console.log("FlashArbitrage deployed at:", address(arbitrage));
        vm.stopBroadcast();
    }
}
