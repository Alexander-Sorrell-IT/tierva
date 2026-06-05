// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "forge-std/Script.sol";
import "../src/Pacto.sol";
import "../src/MockUSDC.sol";

/// Deploys the GENERALIZED Pacto demo stack — one substrate, any parametric trigger.
///
///   1. MockUSDC (test stablecoin)
///   2. Pacto escrow (owner = deployer/governance, oracle = SEPARATE key)
///   3. Mints 100k + funds the escrow with 50,000 USDC
///   4. Enrolls 20 deterministic demo beneficiaries under a poolId
///
/// EVERY threshold/window/bound is per-pool config read from the env, so the SAME
/// script deploys a drought pool (the defaults below), a heat pool, or a flood pool
/// WITHOUT editing a line. Just override the env vars.
///
/// Separation of powers: owner (governance) and oracle (signal reporter) MUST be
/// distinct addresses — the constructor enforces oracle != owner. Set ORACLE_ADDRESS
/// in the env; it falls back to a deterministic demo key derived from the deployer
/// (which can never equal the deployer).
///
/// Defaults = DROUGHT config (byte-for-byte the original logic):
///   breachBelow=true, triggerThreshold=-120, consensusDays=20, maxGapDays=14,
///   minConfirmations=3, minSensorConsensus=2, minCycle=2022, maxCycle=2100,
///   payoutPerBeneficiary=96e6 ($96 USDC, 6dp).
///
/// Env overrides (all optional except DEPLOYER_PRIVATE_KEY):
///   DEPLOYER_PRIVATE_KEY   (required) uint  — deployer/governance key
///   ORACLE_ADDRESS         address          — distinct oracle; default derived from deployer
///   POOL_ID                bytes32          — enrollment pool; default keccak256("tierva:concepcion:drought")
///                                              (matches oracle.py's default --pool so deploy+oracle run aligned at defaults)
///   PAYOUT_PER_BENEFICIARY uint256          — default 96e6
///   BREACH_BELOW           bool             — true=below floor (drought), false=above ceiling (heat/flood)
///   TRIGGER_THRESHOLD      int256           — signal threshold scaled x100; default -120
///   CONSENSUS_DAYS         uint (->uint16)  — default 20
///   MAX_GAP_DAYS           uint (->uint32)  — default 14
///   MIN_CONFIRMATIONS      uint (->uint16)  — default 3
///   MIN_SENSOR_CONSENSUS   uint256          — default 2
///   MIN_CYCLE              uint (->uint16)  — default 2022
///   MAX_CYCLE              uint (->uint16)  — default 2100
///   MINT_AMOUNT            uint256          — default 100_000e6
///   FUND_AMOUNT            uint256          — default 50_000e6
///
/// Works unchanged on local anvil AND any real testnet RPC — env-driven only, no
/// hardcoded chain assumptions.
///
/// Run (local anvil):
///   forge script script/DeployPacto.s.sol --rpc-url http://127.0.0.1:8545 --broadcast
/// Run (testnet):
///   forge script script/DeployPacto.s.sol --rpc-url $RPC_URL --broadcast
contract DeployPacto is Script {
    /// All per-pool config in one struct so run() stays under the stack-depth limit.
    struct Cfg {
        address oracle;
        bytes32 poolId;
        uint256 payout;
        bool    breachBelow;
        int256  triggerThreshold;
        uint16  consensusDays;
        uint32  maxGapDays;
        uint16  minConfirmations;
        uint256 minSensorConsensus;
        uint16  minCycle;
        uint16  maxCycle;
        uint256 mintAmount;
        uint256 fundAmount;
    }

    function _loadCfg(address deployer) internal view returns (Cfg memory c) {
        // Oracle is a DISTINCT key (Chainlink Functions / signed reporter in prod);
        // never the owner. The keccak fallback derives a deterministic address from
        // the deployer that can never collide with it, so oracle != owner always holds.
        c.oracle = vm.envOr(
            "ORACLE_ADDRESS",
            address(uint160(uint256(keccak256(abi.encodePacked("pacto-oracle", deployer)))))
        );
        // Enrollment pool — default matches oracle.py's default --pool label so the
        // canonical deploy+oracle demo runs aligned at pure defaults (override via env for any pool).
        c.poolId = vm.envOr("POOL_ID", keccak256("tierva:concepcion:drought"));

        // DROUGHT defaults; override via env for heat/flood pools.
        c.payout             = vm.envOr("PAYOUT_PER_BENEFICIARY", uint256(96e6));
        c.breachBelow        = vm.envOr("BREACH_BELOW", true);
        c.triggerThreshold   = vm.envOr("TRIGGER_THRESHOLD", int256(-120));
        c.consensusDays      = uint16(vm.envOr("CONSENSUS_DAYS", uint256(20)));
        c.maxGapDays         = uint32(vm.envOr("MAX_GAP_DAYS", uint256(14)));
        c.minConfirmations   = uint16(vm.envOr("MIN_CONFIRMATIONS", uint256(3)));
        c.minSensorConsensus = vm.envOr("MIN_SENSOR_CONSENSUS", uint256(2));
        c.minCycle           = uint16(vm.envOr("MIN_CYCLE", uint256(2022)));
        c.maxCycle           = uint16(vm.envOr("MAX_CYCLE", uint256(2100)));

        c.mintAmount = vm.envOr("MINT_AMOUNT", uint256(100_000e6));
        c.fundAmount = vm.envOr("FUND_AMOUNT", uint256(50_000e6));
    }

    function run() external {
        uint256 pk = vm.envUint("DEPLOYER_PRIVATE_KEY");
        address deployer = vm.addr(pk);
        Cfg memory c = _loadCfg(deployer);

        vm.startBroadcast(pk);

        MockUSDC usdc = new MockUSDC();
        Pacto pacto = new Pacto(
            address(usdc),
            c.oracle,
            c.payout,
            c.breachBelow,
            c.triggerThreshold,
            c.consensusDays,
            c.maxGapDays,
            c.minConfirmations,
            c.minSensorConsensus,
            c.minCycle,
            c.maxCycle
        );

        usdc.mint(deployer, c.mintAmount);
        usdc.approve(address(pacto), type(uint256).max);
        pacto.fund(c.fundAmount);

        // enroll 20 deterministic demo beneficiaries (distinct addresses)
        address[] memory bs = new address[](20);
        for (uint256 i = 0; i < 20; i++) {
            bs[i] = address(uint160(uint256(keccak256(abi.encodePacked("pacto-beneficiary", i)))));
        }
        pacto.enroll(c.poolId, bs);

        vm.stopBroadcast();

        _logResult(address(usdc), address(pacto), deployer, c);
    }

    function _logResult(address usdc, address pacto, address owner, Cfg memory c) internal pure {
        console.log("MockUSDC            :", usdc);
        console.log("Pacto               :", pacto);
        console.log("owner (governance)  :", owner);
        console.log("oracle (reporter)   :", c.oracle);
        console.log("poolId              :");
        console.logBytes32(c.poolId);
        console.log("--- per-pool config ---");
        console.log("payoutPerBeneficiary:", c.payout);
        console.log("breachBelow         :", c.breachBelow);
        console.log("triggerThreshold    :");
        console.logInt(c.triggerThreshold);
        console.log("consensusDays       :", uint256(c.consensusDays));
        console.log("maxGapDays          :", uint256(c.maxGapDays));
        console.log("minConfirmations    :", uint256(c.minConfirmations));
        console.log("minSensorConsensus  :", c.minSensorConsensus);
        console.log("minCycle            :", uint256(c.minCycle));
        console.log("maxCycle            :", uint256(c.maxCycle));
        console.log("--- escrow ---");
        console.log("minted to deployer  :", c.mintAmount);
        console.log("funded into escrow  :", c.fundAmount);
        console.log("enrolled            : 20 demo beneficiaries");
        console.log("note: oracle posts reportDaily()/reportDailyMulti() per scene;");
        console.log("a continuous breach run spanning consensusDays auto-disburses.");
    }
}
