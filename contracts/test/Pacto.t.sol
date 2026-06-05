// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "forge-std/Test.sol";
import "../src/Pacto.sol";
import "../src/MockUSDC.sol";

contract PactoTest is Test {
    MockUSDC usdc;
    Pacto pacto;

    address owner = address(this);
    address oracle = makeAddr("oracle");
    address funder = makeAddr("funder");

    bytes32 constant CONCEPCION = keccak256("HN-Choluteca-ConcepcionDeMaria");
    uint256 constant PAYOUT = 96e6;     // $96 (≈ L.2,400) per beneficiary
    uint16 constant CYCLE_2023 = 2023;
    uint16 constant CONSENSUS = 20;
    int256 constant SEVERE = -260;      // 2-sensor consensus reading, well past -1.20
    int256 constant MILD   = -80;       // -0.80: above the -1.20 threshold, does NOT qualify

    // DROUGHT config — breachBelow=true. With this config Pacto is byte-for-byte the
    // original drought logic, so every ported assertion below must survive verbatim.
    bool    constant DROUGHT_BELOW   = true;
    int256  constant DROUGHT_THRESH  = -120; // signal <= -1.20
    uint16  constant DROUGHT_CONSDAYS = 20;
    uint32  constant DROUGHT_MAXGAP   = 14;
    uint16  constant DROUGHT_MINCONF  = 3;
    uint256 constant DROUGHT_MINSENS  = 2;
    uint16  constant CYCLE_MIN        = 2022;
    uint16  constant CYCLE_MAX        = 2100;

    address[] beneficiaries;

    function _newDroughtPacto() internal returns (Pacto) {
        return new Pacto(
            address(usdc),
            oracle,
            PAYOUT,
            DROUGHT_BELOW,
            DROUGHT_THRESH,
            DROUGHT_CONSDAYS,
            DROUGHT_MAXGAP,
            DROUGHT_MINCONF,
            DROUGHT_MINSENS,
            CYCLE_MIN,
            CYCLE_MAX
        );
    }

    function setUp() public {
        usdc = new MockUSDC();
        pacto = _newDroughtPacto();
        for (uint160 i = 1; i <= 20; i++) beneficiaries.push(address(i + 0x1000));
        pacto.enroll(CONCEPCION, beneficiaries);
        usdc.mint(funder, 100_000e6);
        vm.startPrank(funder);
        usdc.approve(address(pacto), type(uint256).max);
        pacto.fund(50_000e6);
        vm.stopPrank();
    }

    // feed `n` daily readings starting at `start`
    function _feed(uint16 cycle, uint32 start, uint256 n, int256 signal) internal {
        vm.startPrank(oracle);
        for (uint256 d = 0; d < n; d++) pacto.reportDaily(CONCEPCION, cycle, start + uint32(d), signal);
        vm.stopPrank();
    }

    // feed readings at explicit (irregular) day indices — mimics real Sentinel cadence
    function _feedDays(uint16 cycle, uint32[] memory days_, int256 signal) internal {
        vm.startPrank(oracle);
        for (uint256 i = 0; i < days_.length; i++) pacto.reportDaily(CONCEPCION, cycle, days_[i], signal);
        vm.stopPrank();
    }

    // a drought that spans >= 20 days (days 100..120) -> guaranteed to fire
    function _triggerDrought(uint16 cycle) internal { _feed(cycle, 100, 21, SEVERE); }

    function test_enrollment_dedupes() public {
        assertEq(pacto.beneficiariesOf(CONCEPCION).length, 20);
        pacto.enroll(CONCEPCION, beneficiaries); // duplicates must not grow the list
        assertEq(pacto.beneficiariesOf(CONCEPCION).length, 20);
    }

    // a single qualifying reading must NOT fire — 20-day rule is on-chain
    function test_noDisburse_onSingleReport() public {
        _feed(CYCLE_2023, 100, 1, SEVERE);
        assertFalse(pacto.disbursed(CONCEPCION, CYCLE_2023));
        assertEq(pacto.runStartDay(CONCEPCION, CYCLE_2023), 100); // run started, not yet fired
    }

    // CONSENSUS ENFORCED ON-CHAIN: a scene where only ONE sensor is below
    // threshold must REVERT — the contract itself refuses to advance the run on a
    // single sensor. This is the "2 independent sensors must agree" rule, proven
    // in Solidity (not in an off-chain script the oracle could fake).
    function test_consensus_singleSensor_reverts() public {
        int256[] memory one = new int256[](3);
        one[0] = SEVERE; // NDVI deep in drought
        one[1] = MILD;   // rainfall normal (above threshold)
        one[2] = MILD;   // SAR normal (above threshold)
        vm.prank(oracle);
        vm.expectRevert("consensus not met");
        pacto.reportDailyMulti(CONCEPCION, CYCLE_2023, 100, one);
        assertEq(pacto.runStartDay(CONCEPCION, CYCLE_2023), 0, "single sensor must not start a run");
    }

    // CONSENSUS ENFORCED ON-CHAIN: a scene where >=2 sensors agree IS accepted and
    // advances the 20-day run; sustained over 20 days via the array path, it fires.
    function test_consensus_twoSensors_firesOver20Days() public {
        int256[] memory two = new int256[](3);
        two[0] = SEVERE; // NDVI in drought
        two[1] = SEVERE; // rainfall in drought  → 2 sensors agree
        two[2] = MILD;   // SAR normal
        vm.startPrank(oracle);
        for (uint32 d = 0; d <= 20; d++) {
            pacto.reportDailyMulti(CONCEPCION, CYCLE_2023, 100 + d, two); // days 100..120 → span 20
        }
        vm.stopPrank();
        assertTrue(pacto.disbursed(CONCEPCION, CYCLE_2023), "2-sensor consensus did not fire at 20-day span");
        assertEq(pacto.claimable(beneficiaries[0]), PAYOUT);
    }

    // a below-threshold run that has spanned < 20 days must NOT fire
    function test_noDisburse_under20DaySpan() public {
        _feed(CYCLE_2023, 100, 20, SEVERE); // days 100..119 → span 19
        assertFalse(pacto.disbursed(CONCEPCION, CYCLE_2023), "fired before 20-day span");
    }

    // a run spanning exactly 20 days fires; payout is PULL (claim), not push
    function test_autoDisburse_at20DaySpan() public {
        _feed(CYCLE_2023, 100, 21, SEVERE); // days 100..120 → span 20
        assertTrue(pacto.disbursed(CONCEPCION, CYCLE_2023), "did not fire at 20-day span");
        assertEq(pacto.claimable(beneficiaries[0]), PAYOUT);
        assertEq(usdc.balanceOf(beneficiaries[0]), 0, "should be pull, not push");
        vm.prank(beneficiaries[0]);
        pacto.claim();
        assertEq(usdc.balanceOf(beneficiaries[0]), PAYOUT);
    }

    // THE FIX: real Sentinel cadence is irregular (~weekly). It must still fire.
    function test_irregularCadenceStillFires() public {
        uint32[] memory days_ = new uint32[](4);
        days_[0] = 100; days_[1] = 107; days_[2] = 114; days_[3] = 121; // weekly scenes, span 21
        _feedDays(CYCLE_2023, days_, SEVERE);
        assertTrue(pacto.disbursed(CONCEPCION, CYCLE_2023), "weekly cadence failed to fire - the bug");
    }

    // an above-threshold reading breaks the run; the 20-day clock restarts
    function test_brokenRunResets() public {
        _feed(CYCLE_2023, 100, 11, SEVERE);          // days 100..110, span 10
        _feed(CYCLE_2023, 111, 1, MILD);             // rain breaks the drought → reset
        assertEq(pacto.runStartDay(CONCEPCION, CYCLE_2023), 0, "run not reset");
        _feed(CYCLE_2023, 112, 20, SEVERE);          // days 112..131, span 19 → still short
        assertFalse(pacto.disbursed(CONCEPCION, CYCLE_2023), "fired without a fresh 20-day span");
        _feed(CYCLE_2023, 132, 1, SEVERE);           // day 132 → span 20 from 112
        assertTrue(pacto.disbursed(CONCEPCION, CYCLE_2023));
    }

    function test_cannotReplayDay() public {
        vm.startPrank(oracle);
        pacto.reportDaily(CONCEPCION, CYCLE_2023, 100, SEVERE);
        vm.expectRevert("stale or duplicate day");
        pacto.reportDaily(CONCEPCION, CYCLE_2023, 100, SEVERE);
        vm.stopPrank();
    }

    function test_noDoublePay_sameCycle() public {
        _triggerDrought(CYCLE_2023);
        assertEq(pacto.claimable(beneficiaries[0]), PAYOUT);
        _feed(CYCLE_2023, 200, 21, SEVERE); // more drought, already disbursed
        assertEq(pacto.claimable(beneficiaries[0]), PAYOUT, "double allocation same cycle");
    }

    function test_onlyOracleCanReport() public {
        vm.expectRevert("not oracle");
        pacto.reportDaily(CONCEPCION, CYCLE_2023, 100, SEVERE);
    }

    function test_pausedBlocksReport() public {
        pacto.setPaused(true);
        vm.prank(oracle);
        vm.expectRevert("paused");
        pacto.reportDaily(CONCEPCION, CYCLE_2023, 100, SEVERE);
    }

    function test_oracleCannotRedirectFunds() public {
        uint256 before = usdc.balanceOf(oracle);
        _triggerDrought(CYCLE_2023);
        assertEq(usdc.balanceOf(oracle), before, "oracle must never receive funds");
    }

    // one blacklisted beneficiary must not block the rest of the pool
    function test_blacklistedBeneficiaryDoesNotBrickPool() public {
        _triggerDrought(CYCLE_2023);
        usdc.setBlacklisted(beneficiaries[5], true);
        vm.prank(beneficiaries[5]);
        vm.expectRevert("blacklisted");
        pacto.claim();
        for (uint256 i = 0; i < beneficiaries.length; i++) {
            if (i == 5) continue;
            vm.prank(beneficiaries[i]);
            pacto.claim();
            assertEq(usdc.balanceOf(beneficiaries[i]), PAYOUT, "a beneficiary was bricked");
        }
    }

    // governance can sweep UNUSED escrow but never money owed to beneficiaries
    function test_withdrawOnlyFreeNotReserved() public {
        _triggerDrought(CYCLE_2023);
        uint256 reserved = pacto.reserved();
        assertEq(reserved, 20 * PAYOUT);
        uint256 free = usdc.balanceOf(address(pacto)) - reserved;
        vm.expectRevert("exceeds free balance");
        pacto.withdraw(owner, free + 1);
        pacto.withdraw(owner, free);
        assertEq(usdc.balanceOf(address(pacto)), reserved, "reserved not protected");
        vm.prank(beneficiaries[0]);
        pacto.claim();
        assertEq(usdc.balanceOf(beneficiaries[0]), PAYOUT);
    }

    // cannot replay an old/equal cycle to re-drain
    function test_cannotReplayOldCycle() public {
        _triggerDrought(CYCLE_2023);
        assertTrue(pacto.disbursed(CONCEPCION, CYCLE_2023));
        // an EARLIER cycle must not disburse afterwards
        vm.startPrank(oracle);
        for (uint256 d = 0; d < 20; d++) pacto.reportDaily(CONCEPCION, 2022, 100 + uint32(d), SEVERE);
        vm.expectRevert("cycle replay");
        pacto.reportDaily(CONCEPCION, 2022, 120, SEVERE); // day 120 → span 20 → tries _disburse → revert
        vm.stopPrank();
        // a LATER cycle works normally
        _feed(2024, 300, 21, SEVERE);
        assertTrue(pacto.disbursed(CONCEPCION, 2024));
        assertEq(pacto.claimable(beneficiaries[0]), 2 * PAYOUT); // 2023 + 2024
    }

    function test_ownerCannotBecomeOracle() public {
        vm.expectRevert("oracle==owner");
        pacto.setOracle(owner);
    }

    function test_constructorRejectsOwnerOracle() public {
        vm.expectRevert("oracle==owner");
        new Pacto(
            address(usdc),
            address(this),
            PAYOUT,
            DROUGHT_BELOW,
            DROUGHT_THRESH,
            DROUGHT_CONSDAYS,
            DROUGHT_MAXGAP,
            DROUGHT_MINCONF,
            DROUGHT_MINSENS,
            CYCLE_MIN,
            CYCLE_MAX
        );
    }

    // BUG 1 (a): two SEVERE readings 30 days apart with NOTHING observed between is
    // NOT a continuous 20-day drought — the unobserved gap must not pay out.
    function test_noDisburse_severeReadings30DaysApart() public {
        uint32[] memory days_ = new uint32[](2);
        days_[0] = 100; days_[1] = 130; // gap 30 > maxGapDays(14), nothing between
        _feedDays(CYCLE_2023, days_, SEVERE);
        assertFalse(pacto.disbursed(CONCEPCION, CYCLE_2023), "30-day gap must not disburse");
        // the second reading must have started a FRESH run, not extended the first
        assertEq(pacto.runStartDay(CONCEPCION, CYCLE_2023), 130, "gap did not reset the run");
        assertEq(pacto.confirmations(CONCEPCION, CYCLE_2023), 1, "confirmations not reset on gap");
    }

    // BUG 1 (b): two SEVERE readings 21 days apart (gap 21 > 14) — span looks like 21
    // but it's only 2 scenes over an unobserved gap. Must NOT disburse.
    function test_noDisburse_severeReadings21DaysApart() public {
        uint32[] memory days_ = new uint32[](2);
        days_[0] = 100; days_[1] = 121; // gap 21 > maxGapDays(14)
        _feedDays(CYCLE_2023, days_, SEVERE);
        assertFalse(pacto.disbursed(CONCEPCION, CYCLE_2023), "21-day gap (2 scenes) must not disburse");
        assertEq(pacto.runStartDay(CONCEPCION, CYCLE_2023), 121, "gap did not reset the run");
        assertEq(pacto.confirmations(CONCEPCION, CYCLE_2023), 1, "confirmations not reset on gap");
    }

    // BUG 2 (d): a cycle outside [minCycle, maxCycle] must be rejected so a bogus
    // value can never ratchet the monotonic-cycle guard and brick a pool.
    function test_cycleOutOfRangeReverts() public {
        vm.startPrank(oracle);
        vm.expectRevert("cycle range");
        pacto.reportDaily(CONCEPCION, 2021, 100, SEVERE); // below minCycle
        vm.expectRevert("cycle range");
        pacto.reportDaily(CONCEPCION, 2101, 100, SEVERE); // above maxCycle
        vm.stopPrank();
    }

    // BUG 2 (e): owner can clear a stuck cycle guard so a future legitimate cycle
    // can disburse again — recovery from a ratcheted lastCyclePlus1.
    function test_ownerResetCycleGuard() public {
        _triggerDrought(CYCLE_2023); // disburses 2023 → lastCyclePlus1 = 2024
        assertEq(pacto.lastCyclePlus1(CONCEPCION), uint256(CYCLE_2023) + 1);
        // an earlier-or-equal cycle would now be blocked by the monotonic guard;
        // owner clears it
        pacto.resetCycleGuard(CONCEPCION);
        assertEq(pacto.lastCyclePlus1(CONCEPCION), 0, "guard not cleared");
        // non-owner cannot reset
        vm.prank(oracle);
        vm.expectRevert("not owner");
        pacto.resetCycleGuard(CONCEPCION);
    }

    // =====================================================================
    // DIRECTION TESTS (new) — a SECOND pool configured breachBelow=false with a
    // HEAT/FLOOD ceiling. Breach fires on values ABOVE the threshold. Mirrors the
    // drought tests with sign flipped to prove the comparator respects breachBelow
    // at BOTH the consensus-count site and the run-advance site.
    // =====================================================================

    bool    constant HEAT_BELOW    = false;  // breach when signal >= threshold
    int256  constant HEAT_THRESH   = 120;    // +1.20 ceiling (e.g. heat / flood index)
    int256  constant HEAT_SEVERE   = 260;    // well ABOVE the +1.20 ceiling — breaches
    int256  constant HEAT_MILD     = 80;     // +0.80: below the ceiling, does NOT breach

    address[] heatBeneficiaries;

    function _newHeatPacto() internal returns (Pacto) {
        return new Pacto(
            address(usdc),
            oracle,
            PAYOUT,
            HEAT_BELOW,
            HEAT_THRESH,
            DROUGHT_CONSDAYS,   // 20
            DROUGHT_MAXGAP,     // 14
            DROUGHT_MINCONF,    // 3
            DROUGHT_MINSENS,    // 2
            CYCLE_MIN,
            CYCLE_MAX
        );
    }

    function _setUpHeatPool() internal returns (Pacto heat) {
        heat = _newHeatPacto();
        for (uint160 i = 1; i <= 20; i++) heatBeneficiaries.push(address(i + 0x2000));
        heat.enroll(CONCEPCION, heatBeneficiaries);
        // fund the heat pool from the funder
        vm.startPrank(funder);
        usdc.approve(address(heat), type(uint256).max);
        heat.fund(50_000e6);
        vm.stopPrank();
    }

    // sustained readings ABOVE the threshold over 20 days must FIRE (breachBelow=false)
    function test_direction_above_firesOver20Days() public {
        Pacto heat = _setUpHeatPool();
        vm.startPrank(oracle);
        for (uint32 d = 0; d <= 20; d++) {
            heat.reportDaily(CONCEPCION, CYCLE_2023, 100 + d, HEAT_SEVERE); // days 100..120 → span 20
        }
        vm.stopPrank();
        assertTrue(heat.disbursed(CONCEPCION, CYCLE_2023), "above-direction did not fire at 20-day span");
        assertEq(heat.claimable(heatBeneficiaries[0]), PAYOUT);
    }

    // readings BELOW the threshold must NOT breach in the above-direction —
    // sustained for well over the consensus window, nothing fires and no run starts.
    function test_direction_below_doesNotFire() public {
        Pacto heat = _setUpHeatPool();
        vm.startPrank(oracle);
        for (uint32 d = 0; d <= 30; d++) {
            heat.reportDaily(CONCEPCION, CYCLE_2023, 100 + d, HEAT_MILD); // below the +1.20 ceiling
        }
        vm.stopPrank();
        assertFalse(heat.disbursed(CONCEPCION, CYCLE_2023), "below-threshold reading must not fire in above-direction");
        assertEq(heat.runStartDay(CONCEPCION, CYCLE_2023), 0, "below-threshold reading must not start a run");
    }

    // CONSENSUS in the above-direction: a scene where only ONE sensor is above the
    // threshold must REVERT "consensus not met" — proves _breaches drives the
    // sensor count in reportDailyMulti too, not just the run-advance site.
    function test_direction_consensus_singleSensorAbove_reverts() public {
        Pacto heat = _setUpHeatPool();
        int256[] memory one = new int256[](3);
        one[0] = HEAT_SEVERE; // one sensor above the ceiling
        one[1] = HEAT_MILD;   // below
        one[2] = HEAT_MILD;   // below
        vm.prank(oracle);
        vm.expectRevert("consensus not met");
        heat.reportDailyMulti(CONCEPCION, CYCLE_2023, 100, one);
        assertEq(heat.runStartDay(CONCEPCION, CYCLE_2023), 0, "single sensor must not start a run (above-direction)");
    }

    // sanity: two sensors above the ceiling DO reach consensus and, sustained 20
    // days via the array path, fire — the positive counterpart to the revert above.
    function test_direction_consensus_twoSensorsAbove_firesOver20Days() public {
        Pacto heat = _setUpHeatPool();
        int256[] memory two = new int256[](3);
        two[0] = HEAT_SEVERE; // above
        two[1] = HEAT_SEVERE; // above → 2 sensors agree
        two[2] = HEAT_MILD;   // below
        vm.startPrank(oracle);
        for (uint32 d = 0; d <= 20; d++) {
            heat.reportDailyMulti(CONCEPCION, CYCLE_2023, 100 + d, two);
        }
        vm.stopPrank();
        assertTrue(heat.disbursed(CONCEPCION, CYCLE_2023), "2-sensor above-consensus did not fire at 20-day span");
        assertEq(heat.claimable(heatBeneficiaries[0]), PAYOUT);
    }
}
