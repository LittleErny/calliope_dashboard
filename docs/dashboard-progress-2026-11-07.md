# Dashboard checkpoint — 7 November 2026

This checkpoint records the working-tree progress since dashboard commit
`a225d7a` (21 September 2026), on `migration/calliope-0.7.0-dev7`. The application
remains a viewer of solved Calliope exports; neither filter changes nor starting
the dashboard runs optimisation.

## User-facing changes

- Scenario and Carrier sit to the right of the model title on wide screens,
  stacking below it on square windows. A separate top-right time panel contains
  From/To date-time inputs, Apply, sparse slider marks, draft validation,
  and Applied/Not applied status. Draft edits run in the browser; Python charts
  consume the last applied interval. Available dates snap to source timesteps.
- A selected interval can span at most one calendar year, accounting for the
  duration of the final included timestep and leap years. Longer model exports
  remain usable through different year-long selections. Long datasets initially
  open with 48 selected steps; datasets up to 168 steps initially show all steps.
- Demand coverage defaults to Auto with at most 60 nonempty bins. It tries
  1/2/3/4/6/12-hour, day, Monday–Sunday week, month, quarter and year intervals,
  skips intervals finer than the source step, and chooses the first that fits.
  Allocation is calculated before grouping so aggregation preserves energy.
  Partial edge bins contain only the selected data and expose covered bounds.
- Hourly (all) retains original timestep bars; full screen expands the coverage
  card and Escape exits. A circled question mark in the card's upper-right
  corner shows the proportional-allocation explanation on hover/keyboard focus.
  Contributions are estimates, not physical energy-origin tracing.
- Square desktop and laptop layouts resize maps, cards, plots and tables without
  horizontal page overflow in the recorded checks. Wide tables scroll internally.
  A separate mobile design was not part of this update.
- Input and Operate arrowheads are near receiving markers, with zoom-aware
  clearance and Mercator-plane alignment. Links follow true input/output
  direction, SVG paths no longer receive the rectangular selection outline,
  nodes remain clickable above lines, and initial zoom fits the coordinate extent.

## Scenarios and carriers

The fictional German example now has electricity and heat plus Baseline and
High demand (+20%). The two-week horizon is 1–14 July 2025. Heat demand is an
illustrative 35% of the original electric demand; high demand multiplies both
profiles by 1.2. Heat uses local boilers/solar thermal; there are no heat links
between cities. These are dashboard demonstration assumptions, not measured
German heat profiles.

The generator writes four solved NetCDF files and `dashboard_scenarios.json`.
The app preloads compatible scenario bundles and resolves scenario/carrier for
each callback, without mutating another session's active model. Startup checks
node/technology/carrier/time axes and definition matrices. A single pair without
a manifest still works. The German Operate fleet is independently specified in
`operate_fixed`, not transferred automatically from its Planning optimum.

## Numerical fixes and cost interpretation

- Installed generation/storage power excludes demand sinks and transmission.
  Production excludes transmission and includes storage discharge; it is gross
  technology output rather than unique primary energy.
- Input supply curves apply source units, capacity/area limits and efficiencies.
  Input cards include flow operating costs. One-way link direction follows the
  carrier definitions instead of alphabetical endpoint order.
- Line power converts energy using actual timestep hours. Loading uses sending-
  end flow and solved/fixed capacity; receiving-end flow reports delivered energy.
  Long plots retain duration-aware averages and original peaks.
- Energy, emissions and charge/discharge aggregation sums source values. SOC is
  a state: display uses end-of-period values and preserves original min/max.
- CAPEX is upfront investment. Modeled cost reconciles to raw `cost`, including
  annualised investment, fixed/variable components and any remainder. CAPEX is
  kept separate to avoid counting upfront and annualised investment together.
- Window estimates allocate fixed/annualised components by represented hours
  (`timestep_resolution * timestep_weights`); variable costs use selected actual
  values. Custom cost classes and negative costs remain separate and unweighted.
- Each enabled node/technology has one accounting scope: a single carrier or
  Shared. Shared undivided costs are excluded from carrier-exclusive summaries;
  physical flows and capacities stay in applicable views. No heat/electricity
  allocation is invented. For the complete model cost, use raw
  `results.cost.sel(costs=...).sum()` or the reconciling ledger.
- The **All technology costs · whole model** UI is temporarily commented out.
  Its helper, callbacks and reconciliation tests remain available. Visible
  carrier totals do not include Shared costs; no custom CSV workflow was added.
- Missing CO2 classes are labeled unavailable. Unexpected required-data errors
  log details and clear affected outputs instead of silently displaying zeros.
  Optional omitted unmet-demand slack is treated as zero. The shared error
  banner includes a possible missing Operate run/export explanation and clears
  its text and visibility on tab changes or Dismiss.

## Calliope source and export provenance

The Conda package built on 7 September 2025 and the newer local fork both report
`0.7.0.dev7`. Upstream commit `8b9ba5d3` (16 December 2025, Bryn Pickering and
Ivan Ruiz Manuel) renamed data-table `data` to `table` and `parameters` to
`inputs`. German YAML and its DataFrame generator now use the newer schema. The tested
local Calliope checkout is `30d64b7c`. Install a compatible checkout after `make
setup`, verify `calliope.__file__` as well as its version, and restart processes
that already imported Calliope. See [environment setup](environments.md).

Historical NetCDF contains a snapshot of inputs. In the sibling THD model, the
8 September 2026 heat-pump export predates coordinates added on 21 September;
those YAML edits cannot populate its old map. Newly exported coordinates fix
that case. Some THD node coordinates are approximate or represent virtual nodes;
the dashboard does not independently certify geographic accuracy.

The Python single-solution API currently copies its selected solution to
both `planning.nc` and `operate.nc`. It does not perform a separate dispatch
solve. Genuine Planning/Operate comparison uses an externally solved pair.

## Independent annual THD check

The separate THD repository's `scenario_3_heat_pump` was solved on the installed
fork for all 8760 hourly steps of 2025. New Planning and genuine rolling Operate
exports live in that repository's `scenario_results/dashboard_heat_pump_2026-11-07/`;
they are not part of this dashboard commit. Operate fixes capacities from
Planning, uses a 168-hour window / 336-hour horizon (53 windows), and disables
cyclic storage within windows while carrying storage state forward.

A problematic Operate preparation reproduced nighttime PV and zero import costs
despite optimal status. Masked irrelevant carrier capacities received the
standard infinite `flow_cap` default, producing invalid resource limits. The
external THD runner overrides that Operate default to zero for its fully defined
fleet and validates resource bounds before export. This is a local model-runner
workaround; this dashboard does not patch the library or change model math.

| Annual check | Result |
| --- | ---: |
| Planning termination | optimal |
| Operate termination | optimal |
| Planning full monetary cost | EUR 644994.6232335933 |
| Carrier-exclusive monetary cost | EUR 611334.6758831537 |
| Shared heat-pump monetary cost | EUR 33659.94735043961 |
| Operate variable monetary cost | EUR 568732.8225459721 |
| Operate imported electricity | 2031188.6519499 kWh |
| Maximum Operate unmet demand | 0 |
| Maximum absolute node balance residual | approximately 0.000016 |

Capacities match Planning exactly. All three PV resource bounds were checked
across the year; residuals are below 0.001. Variable OPEX equals grid imports ×
EUR 0.28/kWh. Planning cost includes annualised investment and is not comparable
to variable-only Operate OPEX as the same metric. Both final exports reload
through the fork. The recalculated Planning cost and capacities exactly match
the preliminary published-package solution.

## Validation and remaining boundaries

The complete suite passes **83 tests** on the fork. It checks both German
scenarios/carriers, direct NetCDF agreement, Shared/negative/custom cost
accounting, half-hour/irregular time axes, storage extrema, coverage conservation,
calendar-year limits, browser date logic, map arrows, missing data and the actual
Dash HTTP error handler. The environment smoke check solves the built-in
national example for 24 steps; `pip check` reports no broken requirements.

Recorded browser checks cover Inputs/Planning/Operate, both THD carriers, scenario
switching in the German fixture, the annual 53-week coverage view, desktop
900×900 / 1024×1024 / 1366×768 / 1600×900 layouts, and no visible data-error banner
in the final working view. These are targeted regressions and consistency checks,
not a guarantee for every possible Calliope model or independent calibration of
source assumptions. The German fixture intentionally permits unmet demand.

Earlier [electricity audit](german-scale-validation-2026-11-02.md),
[scenario audit](german-scale-scenarios-2026-11-02.md), and
[cost/time audit](dashboard-costs-and-time-2026-11-03.md) are retained with explicit
current-status notes rather than rewriting historical test counts.

## Later on 7 November: native THD investment scenarios

Scenario loading now permits different technology/carrier definitions while
requiring common nodes, coordinates, map connections and time axes. Carrier
choices follow the selected scenario, and stale carrier requests wait for the
selector update. This supports all six native THD scenarios without adding fake
heat or inactive technologies to their exported data. A regression test loads
exports with different carrier/technology sets and exercises all three tabs,
including an HTTP check that stale carrier requests do not surface a data error.
The full regression suite after this extension passes 84 tests.

The sibling THD runner prepares each scenario's annual Planning and genuine
rolling Operate pair in `scenario_results/dashboard_all_scenarios_2026-11-07/`.
It preserves the source scenario definitions. In particular, the native
`baseline` currently does not enable the registered historical battery math,
and only `scenario_3_heat_pump` enables heat demand; the viewer does not silently
change these modeling assumptions. See the runner's `validation.json` for actual
solve status, source carriers, balances, PV resource checks, grid energy and costs.

## Final Inputs and header checks

The final suite passes **91 tests**. Inputs distinguishes absent local demand
(explicit zero), defined all-zero profiles, undefined fixed profiles and partial
missing data. Selecting a node with no technology for the current carrier still
opens its card. Missing data remains a gap rather than being converted to zero;
valid windows remain usable. Conversion cards show both carriers. Storage
energy-capacity cost is shown separately in EUR/kWh, alongside flow-capacity
cost in EUR/kW. Header checks cover 1920×1080, 1366×768 and 900×900 without
horizontal page overflow.

All six native THD Planning/Operate pairs completed and were checked through
every dashboard section for their available carriers. The input export contains
a source-profile gap at 2025-12-31 23:00; the viewer reports incomplete input
coverage for windows containing it. No source values were invented or filled.
Successful optimisation checks establish consistency with the configured model,
not completeness of the original measurements.
