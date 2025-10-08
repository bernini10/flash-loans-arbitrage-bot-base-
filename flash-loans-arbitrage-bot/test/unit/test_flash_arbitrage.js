/**
 * Testes Unitários para o Contrato FlashArbitrage
 *
 * Estes testes verificam a lógica do contrato FlashArbitrage de forma isolada,
 * utilizando mocks para as dependências externas como DEXs e o Pool da Aave.
 */

const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("FlashArbitrage", function () {
  let flashArbitrage, owner, addr1, addr2;
  let mockPoolAddressesProvider, mockAAVEPool, mockDEXBuy, mockDEXSell, tokenA, tokenB;

  beforeEach(async function () {
    // Get signers
    [owner, addr1, addr2] = await ethers.getSigners();

    // Deploy Mocks
    const MockAAVEPoolFactory = await ethers.getContractFactory("MockAAVEPool");
    mockAAVEPool = await MockAAVEPoolFactory.deploy();
    await mockAAVEPool.waitForDeployment();

    const MockPoolAddressesProviderFactory = await ethers.getContractFactory("MockPoolAddressesProvider");
    mockPoolAddressesProvider = await MockPoolAddressesProviderFactory.deploy(mockAAVEPool.target);
    await mockPoolAddressesProvider.waitForDeployment();

    const MockDEXFactory = await ethers.getContractFactory("MockDEX");
    mockDEXBuy = await MockDEXFactory.deploy();
    await mockDEXBuy.waitForDeployment();
    mockDEXSell = await MockDEXFactory.deploy();
    await mockDEXSell.waitForDeployment();

    const MockERC20Factory = await ethers.getContractFactory("MockERC20");
    tokenA = await MockERC20Factory.deploy("Token A", "TKA");
    await tokenA.waitForDeployment();
    tokenB = await MockERC20Factory.deploy("Token B", "TKB");
    await tokenB.waitForDeployment();

    // Deploy o contrato FlashArbitrage
    const FlashArbitrageFactory = await ethers.getContractFactory("FlashArbitrage");
    flashArbitrage = await FlashArbitrageFactory.deploy(mockPoolAddressesProvider.target);
    await flashArbitrage.waitForDeployment();

    // Initial setup
    await flashArbitrage.addSupportedDEX(mockDEXBuy.target);
    await flashArbitrage.addSupportedDEX(mockDEXSell.target);
    await flashArbitrage.addAuthorizedCaller(owner.address);
  });

  describe("Deployment and Configuration", function () {
    it("Should set the right owner", async function () {
      expect(await flashArbitrage.owner()).to.equal(owner.address);
    });

    it("Should correctly set supported DEXs", async function () {
      expect(await flashArbitrage.supportedDEXs(mockDEXBuy.target)).to.be.true;
      expect(await flashArbitrage.supportedDEXs(mockDEXSell.target)).to.be.true;
    });

    it("Should allow owner to add and remove authorized callers", async function () {
      await flashArbitrage.addAuthorizedCaller(addr1.address);
      expect(await flashArbitrage.authorizedCallers(addr1.address)).to.be.true;

      await flashArbitrage.removeAuthorizedCaller(addr1.address);
      expect(await flashArbitrage.authorizedCallers(addr1.address)).to.be.false;
    });
  });

  describe("Arbitrage Execution", function () {
    it("Should execute arbitrage successfully with profit", async function () {
      // Setup prices for arbitrage
      await mockDEXBuy.setPrice(tokenA.target, tokenB.target, ethers.parseEther("1.1"));
      await mockDEXSell.setPrice(tokenB.target, tokenA.target, ethers.parseEther("0.95"));

      const amountIn = ethers.parseEther("100");

      const arbitrageParams = {
        tokenA: tokenA.target,
        tokenB: tokenB.target,
        dexBuy: mockDEXBuy.target,
        dexSell: mockDEXSell.target,
        amountIn: amountIn,
        minProfitBps: 100, // 1%
        deadline: (await ethers.provider.getBlock("latest")).timestamp + 60,
      };

      await tokenA.mint(mockAAVEPool.target, amountIn);
      await tokenA.mint(mockDEXSell.target, ethers.parseEther("1000"));
      await tokenB.mint(mockDEXBuy.target, ethers.parseEther("1000"));

      await expect(flashArbitrage.executeArbitrage(arbitrageParams))
        .to.emit(flashArbitrage, "ArbitrageExecuted");
    });
  });
});
