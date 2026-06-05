// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function balanceOf(address) external view returns (uint256);
}

/// @title Pacto — the self-executing budget line (domain-agnostic)
/// @notice A consensus-gated parametric disbursement escrow. An oracle posts ONE
/// signal reading per day per pool. The contract itself counts the consecutive
/// qualifying days — and only when the pre-agreed multi-day consensus is reached
/// on-chain does it allocate the pre-agreed payout to every enrolled beneficiary.
/// No minister signs. No NGO appeal. The budget executes itself.
///
/// This is a GENERALIZED primitive. Every threshold/window/bound that used to be a
/// hardcoded drought constant is now PER-POOL immutable config set in the constructor,
/// so the same code serves any parametric trigger (drought below a floor, heat/flood
/// above a ceiling, …). The `breachBelow` direction flag chooses which side of the
/// threshold counts as a breach. With `breachBelow = true` and the drought config this
/// is byte-for-byte the original drought logic.
///
/// What makes it judiciable: the RULE lives in the code, not in a person.
///   • The multi-consecutive-day window is counted on-chain (consensusDays) — the
///     oracle cannot fire a payout with a single report; it must report a real
///     breach, day after day, and the contract is the one keeping score.
///   • The oracle can ONLY report signal state. It can never move money to an
///     arbitrary address — only the fixed payout, only to pre-enrolled beneficiaries.
///   • owner != oracle is enforced, so no single key both enrolls and triggers.
///   • Beneficiaries are paid by PULL (claim), so one frozen wallet can never block
///     the whole pool. Governance can recover only UNRESERVED funds, never money
///     already owed to a beneficiary.
contract Pacto {
    // The signal is reported scaled by 100 (e.g. -1.20 => -120) to stay integer
    // on-chain. The oracle posts the 2nd-most-extreme sensor anomaly (NDVI, rainfall
    // SPI-3, SAR, FAPAR, …): that value breaches the threshold IFF at least 2
    // independent sensors agree on the breach. So this single threshold check
    // encodes the multi-sensor CONSENSUS.
    int256 public immutable triggerThreshold; // signal breaches this (scaled by 100)
    // true  => breach when signalScaled <= triggerThreshold (drought / below a floor)
    // false => breach when signalScaled >= triggerThreshold (heat / flood / above a ceiling)
    bool public immutable breachBelow;
    uint16 public immutable consensusDays;    // run must span >= this many days
    // A continuous breach run must not contain an unobserved gap longer than this:
    // two extreme readings weeks apart with nothing between is NOT a sustained breach.
    uint32 public immutable maxGapDays;        // max days between consecutive scenes in a run
    uint16 public immutable minConfirmations;  // a run must have >= this many qualifying scenes to fire
    // At least this many independent sensors must breach the threshold in a single
    // scene for it to count when posted via reportDailyMulti. This is the multi-sensor
    // CONSENSUS, enforced on-chain (not in an off-chain script).
    uint256 public immutable minSensorConsensus;
    // Defensive cycle bounds: a bogus/out-of-range cycle must never be accepted
    // (a huge value would otherwise ratchet lastCyclePlus1 and brick the pool).
    uint16 public immutable minCycle;          // earliest acceptable cycle
    uint16 public immutable maxCycle;          // latest acceptable cycle

    address public owner;     // governance
    address public oracle;    // signal reporter
    IERC20  public token;     // payout token (e.g. USDC)
    uint256 public immutable payoutPerBeneficiary; // e.g. 96e6 = $96 in USDC(6dp)
    bool    public paused;
    uint256 public reserved;  // total allocated to beneficiaries but not yet claimed

    // poolId => enrolled beneficiary wallets
    mapping(bytes32 => address[]) private _beneficiaries;
    // poolId => beneficiary => enrolled (dedup guard)
    mapping(bytes32 => mapping(address => bool)) public isEnrolled;
    // poolId => cycle => already disbursed (prevents same-cycle double-pay)
    mapping(bytes32 => mapping(uint16 => bool)) public disbursed;
    // poolId => cycle => first day of the current continuous breach run (0 = none)
    mapping(bytes32 => mapping(uint16 => uint32)) public runStartDay;
    // poolId => cycle => last reported day index (strictly increasing; replay guard)
    mapping(bytes32 => mapping(uint16 => uint32)) public lastDay;
    // poolId => cycle => number of qualifying scenes in the current run (anti-gap)
    mapping(bytes32 => mapping(uint16 => uint16)) public confirmations;
    // poolId => cycle => most recent qualifying day index (gap detector)
    mapping(bytes32 => mapping(uint16 => uint32)) public lastQualifyingDay;
    // poolId => (highest disbursed cycle + 1); 0 = none yet (monotonic cycles)
    mapping(bytes32 => uint256) public lastCyclePlus1;
    // beneficiary => amount owed and claimable
    mapping(address => uint256) public claimable;

    event Enrolled(bytes32 indexed pool, uint256 added, uint256 total);
    event Funded(address indexed from, uint256 amount);
    event OracleChanged(address indexed oldOracle, address indexed newOracle);
    event PausedSet(bool paused);
    event DailyReported(bytes32 indexed pool, uint16 cycle, uint32 dayIndex, int256 signal, uint32 daysInBreach, bool fired);
    event Allocated(bytes32 indexed pool, address indexed beneficiary, uint256 amount);
    event Disbursed(bytes32 indexed pool, uint16 cycle, uint256 beneficiaries, uint256 total);
    event Claimed(address indexed beneficiary, uint256 amount);
    event Withdrawn(address indexed to, uint256 amount);
    event CycleGuardReset(bytes32 indexed pool);

    modifier onlyOwner()  { require(msg.sender == owner,  "not owner");  _; }
    modifier onlyOracle() { require(msg.sender == oracle, "not oracle"); _; }

    constructor(
        address _token,
        address _oracle,
        uint256 _payoutPerBeneficiary,
        bool _breachBelow,
        int256 _triggerThreshold,
        uint16 _consensusDays,
        uint32 _maxGapDays,
        uint16 _minConfirmations,
        uint256 _minSensorConsensus,
        uint16 _minCycle,
        uint16 _maxCycle
    ) {
        require(_token != address(0), "token=0");
        require(_oracle != address(0), "oracle=0");
        require(_oracle != msg.sender, "oracle==owner"); // separation of powers
        require(_payoutPerBeneficiary > 0, "payout=0");
        owner = msg.sender;
        token = IERC20(_token);
        oracle = _oracle;
        payoutPerBeneficiary = _payoutPerBeneficiary;
        breachBelow = _breachBelow;
        triggerThreshold = _triggerThreshold;
        consensusDays = _consensusDays;
        maxGapDays = _maxGapDays;
        minConfirmations = _minConfirmations;
        minSensorConsensus = _minSensorConsensus;
        minCycle = _minCycle;
        maxCycle = _maxCycle;
    }

    /// @dev THE direction comparator — single source of truth, used at BOTH the
    /// consensus-count site and the run-advance site so they can never drift.
    /// breachBelow=true: breach iff value <= threshold (drought / below a floor).
    /// breachBelow=false: breach iff value >= threshold (heat / flood / above ceiling).
    function _breaches(int256 v) internal view returns (bool) {
        return breachBelow ? v <= triggerThreshold : v >= triggerThreshold;
    }

    // ---- governance ----
    function enroll(bytes32 pool, address[] calldata beneficiaries) external onlyOwner {
        uint256 added;
        for (uint256 i = 0; i < beneficiaries.length; i++) {
            address b = beneficiaries[i];
            if (b == address(0) || isEnrolled[pool][b]) continue; // skip zero + duplicates
            isEnrolled[pool][b] = true;
            _beneficiaries[pool].push(b);
            added++;
        }
        emit Enrolled(pool, added, _beneficiaries[pool].length);
    }

    function fund(uint256 amount) external {
        require(token.transferFrom(msg.sender, address(this), amount), "fund failed");
        emit Funded(msg.sender, amount);
    }

    function setPaused(bool p) external onlyOwner { paused = p; emit PausedSet(p); }

    function setOracle(address o) external onlyOwner {
        require(o != address(0), "oracle=0");
        require(o != owner, "oracle==owner"); // never collapse the two keys
        emit OracleChanged(oracle, o);
        oracle = o;
    }

    /// @notice Governance escape hatch: clears the monotonic-cycle guard for a pool
    /// so a future legitimate cycle can disburse again. Recovers from a bogus high
    /// cycle value that would otherwise permanently brick the pool.
    function resetCycleGuard(bytes32 pool) external onlyOwner {
        lastCyclePlus1[pool] = 0;
        emit CycleGuardReset(pool);
    }

    /// @notice Recover funds NOT owed to beneficiaries. The reserved balance (already
    /// allocated, awaiting claim) is untouchable — governance can never rug a
    /// beneficiary's owed payout, only sweep the unused escrow.
    function withdraw(address to, uint256 amount) external onlyOwner {
        require(to != address(0), "to=0");
        uint256 free = token.balanceOf(address(this)) - reserved;
        require(amount <= free, "exceeds free balance");
        require(token.transfer(to, amount), "withdraw failed");
        emit Withdrawn(to, amount);
    }

    function beneficiariesOf(bytes32 pool) external view returns (address[] memory) {
        return _beneficiaries[pool];
    }

    // ---- the self-executing core ----
    /// @notice Oracle posts a signal reading for a pool+cycle as each new scene
    /// lands. Sentinel revisit + cloud gaps make this IRREGULAR (~5–10 days apart),
    /// so the contract does NOT require consecutive day indices. Instead it tracks
    /// the first day of the current continuous breaching run and fires once that run
    /// has SPANNED consensusDays — tolerating the gaps between scenes, exactly like
    /// the off-chain backtest. `dayIndex` is the calendar day index and must be >= 1
    /// (0 is the uninitialized sentinel) and must strictly increase. A non-breaching
    /// reading breaks the run and resets the clock.
    function reportDaily(bytes32 pool, uint16 cycle, uint32 dayIndex, int256 signalScaled)
        external
        onlyOracle
    {
        // Back-compat path: the caller has already reduced the sensors off-chain to
        // a single value (the 2nd-most-extreme anomaly). Kept so existing tooling
        // keeps working; new integrations should use the array overload, which
        // enforces the multi-sensor CONSENSUS inside the contract.
        _report(pool, cycle, dayIndex, signalScaled);
    }

    /// @notice CONSENSUS ENFORCED ON-CHAIN. The oracle posts the RAW per-sensor
    /// anomalies (NDVI, rainfall SPI-3, SAR, ...) for this scene. The contract itself
    /// counts how many breach the threshold and requires at least minSensorConsensus
    /// of them to AGREE before the reading can count toward the run. A single sensor
    /// in breach can NEVER fire a payout — the "independent sensors must agree" rule
    /// is verified here, in Solidity, not in an off-chain script the oracle could fake.
    function reportDailyMulti(bytes32 pool, uint16 cycle, uint32 dayIndex, int256[] calldata sensorAnomalies)
        external
        onlyOracle
    {
        uint256 inBreach;
        for (uint256 i = 0; i < sensorAnomalies.length; i++) {
            if (_breaches(sensorAnomalies[i])) inBreach++;
        }
        require(inBreach >= minSensorConsensus, "consensus not met");
        // The 2nd-most-extreme anomaly breaches the threshold IFF >=2 sensors agree;
        // once consensus is proven on-chain we carry that into the run as a qualifying
        // reading. Use the threshold itself as the qualifying value (it breaches in
        // either direction, since t<=t and t>=t both hold) so a single strong sensor
        // can never substitute for genuine multi-sensor agreement.
        _report(pool, cycle, dayIndex, triggerThreshold);
    }

    function _report(bytes32 pool, uint16 cycle, uint32 dayIndex, int256 signalScaled)
        internal
    {
        require(!paused, "paused");
        require(cycle >= minCycle && cycle <= maxCycle, "cycle range");
        require(dayIndex > lastDay[pool][cycle], "stale or duplicate day");
        lastDay[pool][cycle] = dayIndex;

        bool fired = false;
        if (_breaches(signalScaled)) {
            uint32 runStart = runStartDay[pool][cycle];
            // Start a FRESH run if there is none, or if the gap since the last
            // qualifying scene exceeds maxGapDays — an unobserved gap is NOT a
            // continuous breach, so it cannot count toward the consensus window.
            if (runStart == 0 || dayIndex - lastQualifyingDay[pool][cycle] > maxGapDays) {
                runStartDay[pool][cycle] = dayIndex;
                runStart = dayIndex;
                confirmations[pool][cycle] = 1;
            } else {
                confirmations[pool][cycle] += 1;
            }
            lastQualifyingDay[pool][cycle] = dayIndex;
            // Fire only on a genuine continuous run: spans >= consensusDays AND has
            // been confirmed by >= minConfirmations separate scenes (no
            // two-readings-far-apart payout).
            if (
                !disbursed[pool][cycle] &&
                dayIndex - runStart >= consensusDays &&
                confirmations[pool][cycle] >= minConfirmations
            ) {
                _disburse(pool, cycle);
                fired = true;
            }
        } else {
            runStartDay[pool][cycle] = 0; // breach broke — reset the run
            confirmations[pool][cycle] = 0;
        }
        uint32 cur = runStartDay[pool][cycle];
        emit DailyReported(pool, cycle, dayIndex, signalScaled, cur == 0 ? 0 : dayIndex - cur, fired);
    }

    function _disburse(bytes32 pool, uint16 cycle) internal {
        // monotonic cycles: a cycle can only ever disburse once, and only forward —
        // blocks an oracle from replaying old cycles to drain escrow.
        require(uint256(cycle) + 1 > lastCyclePlus1[pool], "cycle replay");
        lastCyclePlus1[pool] = uint256(cycle) + 1;

        disbursed[pool][cycle] = true; // effects before interactions

        address[] storage bs = _beneficiaries[pool];
        uint256 n = bs.length;
        require(n > 0, "no beneficiaries");
        uint256 total = n * payoutPerBeneficiary;
        require(token.balanceOf(address(this)) >= reserved + total, "escrow underfunded");

        reserved += total;
        for (uint256 i = 0; i < n; i++) {
            claimable[bs[i]] += payoutPerBeneficiary; // allocate (pull-payment)
            emit Allocated(pool, bs[i], payoutPerBeneficiary);
        }
        emit Disbursed(pool, cycle, n, total);
    }

    /// @notice Beneficiary pulls its allocated payout. Independent per beneficiary —
    /// one frozen/blacklisted wallet can never block anyone else.
    function claim() external {
        uint256 amt = claimable[msg.sender];
        require(amt > 0, "nothing to claim");
        claimable[msg.sender] = 0; // effects
        reserved -= amt;
        require(token.transfer(msg.sender, amt), "transfer failed"); // interaction (CEI)
        emit Claimed(msg.sender, amt);
    }
}
