# German-scale heat and scenario validation — 2 November 2026

The model now includes `electricity` and `heat`, with separately solved
**Baseline** and **High demand (+20%)** datasets. Heat demand is an illustrative
35% of each city's original electricity profile; the stress scenario multiplies
both demand profiles by 1.2 without changing availability. Heat comes from local
gas boilers and solar thermal. These are demonstration assumptions, not measured
German heating data. See the [model README](../models/1_german_scale/README.md).

Four Calliope/CBC calculations completed with optimal termination: planning and
fixed-fleet operate for both scenarios. Their files and labels are listed in
`models/1_german_scale/dashboard_scenarios.json`. The dashboard preloads separate
bundles and passes the selected scenario/carrier to each data callback; it does
not change a process-wide active model when a user changes a dropdown.

## Full-horizon planning checks

The browser figures for 1–14 July 2025 agree with direct NetCDF aggregations:

| Scenario | Carrier | Modeled monetary cost | Installed power | Output | CO2 |
| --- | --- | ---: | ---: | ---: | ---: |
| Baseline | electricity | EUR 493.99M | 45.70M kW | 4.26B kWh | 1.29B kg |
| Baseline | heat | EUR 95.72M | 10.64M kW | 1.50B kWh | 218.65M kg |
| High demand | electricity | EUR 598.12M | 51.30M kW | 5.04B kWh | 1.68B kg |
| High demand | heat | EUR 114.79M | 12.47M kW | 1.80B kWh | 266.88M kg |

Electricity and heat monetary cost/CO2 slices sum to the complete model totals.
No technology in this example spans both carriers, so this reconciliation is
unambiguous. Planning and operate remain different capacity configurations.

## Coverage

- Numerical comparisons cover both scenarios/carriers, every city, each
  applicable technology, full/48-hour/24-hour/single-hour windows, planning
  KPIs/tables/plots, operate KPIs/storage/lines, and input supply/demand curves.
- The stress inputs are checked against exactly 1.2 times baseline demand, with
  identical source availability. Scenario IDs are checked in both result files.
- All content builders run for both scenarios/carriers, both map modes and both
  planning cost normalizations.
- Map tests ensure electricity connections disappear in heat mode; heat has no
  transmission links and no electric battery cards.
- Every data callback is checked for a dependency on the scenario selector.
  Optional map controls are checked during initial loading so switching a
  scenario before markers mount does not cause a missing-component error.
- A single NetCDF pair without a scenario manifest still loads, preserving the
  existing standalone dashboard workflow.
- Browser checks exercised all four scenario/carrier combinations, heat
  technology selection, input cards, operate city summaries, and switching back
  to baseline. For example Berlin's operate heat demand changes from 521.25M
  to 625.51M kWh when selecting high demand.
- The Demand coverage explanation is hidden behind a circled question mark,
  aligned to the card's upper-right corner and shown on hover or keyboard focus.
  It describes proportional allocation, not
  physical energy-origin tracing.

The shared Apply time filter and the existing square/laptop layouts are retained.
The original electricity-only audit is kept as a historical snapshot.

Final automated validation: **59 tests passed**. The final browser check also
confirmed that the explanation starts hidden, appears over the question mark,
and disappears after moving away. No new browser errors were recorded after
fixing the initial marker-loading dependency.

## Status on 7 November 2026

The 59-test result above records this earlier checkpoint; the current complete
suite has **83 passing tests**. Subsequent changes added Auto ≤60 calendar bins,
Hourly/full-screen coverage, a one-calendar-year applied interval, exact date
fields, end-of-link arrowheads, duration-aware cost/line/storage checks and
clear-on-tab-change errors. Whole-model technology cost UI is temporarily hidden.
The source generator now uses the local fork's `table` / `inputs` schema.
See [current progress](dashboard-progress-2026-11-07.md) and
[environment setup](environments.md); the historical numerical table above is
retained as a dated audit, not a new solve performed for each documentation edit.
