# German-scale dashboard validation — 2 November 2026

This snapshot predates the heat/high-demand extension. See
[the scenario validation](german-scale-scenarios-2026-11-02.md) for the extended model
and [the 7 November checkpoint](dashboard-progress-2026-11-07.md) for current UI,
accounting, environment and the 83-test suite. The 20-test result below is historical.

Scope: the local Calliope 0.7 German-scale model, all three dashboard sections,
the shared time filter, and square/laptop window sizes. Mobile layouts were
explicitly outside the requested scope.

## Source data and reproducibility

- Model: `models/1_german_scale/model.yaml`, its imported YAML files, and the
  original city CSV files loaded by `calliope_to_netcdf.py`.
- Environment: `calliope-dashboard-070`, Calliope `0.7.0.dev7`, CBC.
- Horizon: 1–14 July 2025, 336 hourly timesteps; eight cities and eight links.
- Independently loaded and solved both planning and `operate_fixed` from the
  current source files, writing audit copies under `/tmp/german-audit-*.nc`.
- Compared fresh results with the checked-in NetCDF files. Maximum absolute
  difference was **zero** for `flow_out`, `flow_in`, `storage`, `unmet_demand`,
  `cost_operation_variable`, and `cost`, in both modes.
- Preprocessed inputs also match after NetCDF serialization. A direct in-memory
  comparison of `source_unit` differs in missing-string representation; the
  serialized values are identical.

## Independent numeric checks

The regression suite compares dashboard values against direct xarray sums,
without using the helper's aggregation tables as the expected result.

- Planning: all locations together, every city, and every selectable technology.
  Checks cover monetary costs, upfront investment, operating costs, CO2,
  installed asset capacity, production, table totals, cost breakdowns, and
  grouped production/operational-CO2 time series.
- Four windows: the complete horizon, the first 48 hours, a later 24-hour
  window, and the final single hour.
- Operate: every city's demand, unmet demand, output and variable costs; storage
  state; every directed link's received energy, sending-end utilization, and
  the modeled 98% transmission efficiency.
- Inputs: every city's demand and supply upper bounds, including PV/wind
  efficiency and hydro's area-based resource constraints.
- All Inputs, Planning and Operate content builders are exercised for every
  city; Planning is also exercised by technology and in both cost units;
  Operate line panels and both map modes are exercised.

Full-horizon planning reference values:

| Metric | Value |
| --- | ---: |
| Monetary modeled cost | EUR 493,994,235.60 |
| Upfront investment | EUR 70,785,074,773.60 |
| Operating costs | EUR 201,107,220.38 |
| Installed supply/storage power | 45,695,700.66 kW |
| Local output, including storage discharge | 4,258,154,184.77 kWh |
| Modeled CO2 | 1,289,364,364.52 kg |

The balance residual in the saved CBC output is at most 0.12 kWh per
node/carrier/timestep, consistent with rounding of flows of millions of kWh.

## Corrected issues

1. Demand-sink capacity was included in installed capacity. This overstated the
   aggregate by 15,057,063.50 kW. Demand and transmission capacities are now
   excluded from generation/storage capacity, while their modeled costs remain.
2. Input supply curves ignored parasitic efficiency and treated area-based
   hydro availability as capacity-based availability. They now apply the
   resource and delivered-output constraints together.
3. Input supply cards omitted production operating costs; these now read
   `cost_flow_out`.
4. Transmission loading used received energy, understating sending-end
   utilization by the line losses. It now uses sending-end energy divided by
   capacity and timestep duration.
5. Inputs arrows could reverse one-way links when endpoints were sorted
   alphabetically. Directions now follow `carrier_in` / `carrier_out`; both
   directions are shown for bidirectional links.
6. A campus-scale initial zoom hid most of Germany. Initial zoom now depends
   on the coordinate extent.
7. Lines could intercept clicks on Operate nodes. Node circles now use the
   higher marker pane.
8. Clicking Leaflet SVG paths showed a rectangular browser focus outline. The
   outline is suppressed for those paths, preserving their click actions.

## Time controls and browser checks

- The shared slider shows four sparse date marks and separate From/To labels.
- Editing the draft updates labels locally in the browser. Only **Apply**
  updates the store consumed by Python graph/map callbacks. Switching other
  filters also uses the previously applied interval.
- Verified in the browser that extending the interval leaves the displayed
  totals unchanged until Apply, then updates them to the direct NetCDF totals.
- The Operate hour slider has sparse date labels as well.
- Browser checks covered selecting an Inputs city and link, Planning location
  and technology modes, absolute and per-kW costs, Operate city/link panels,
  SOC and charge/discharge, Critical and Timestep modes, and hour changes.
- All three sections were inspected at 900×900, 1024×1024, 1366×768 and
  1600×900. No horizontal page overflow was present after layout settled.
  Charts resize with their containers; the wide detail table scrolls internally.
- Square windows stack map/details and use two summary-chart columns; wider
  windows keep map/details side by side and use three summary-chart columns.

Validation command:

```bash
conda run -n calliope-dashboard-070 python -m pytest -q
```

Result: **20 tests passed**. No application errors were observed in the browser
console during the checked interactions.

## Interpretation limits

This validates consistency with the fictional model and its data, not the
accuracy of a real German energy-system study. The scenario intentionally
permits unmet demand: planning contains 49,563,154.54 kWh (1.159% of demand),
and `operate_fixed` contains 41,811,642.86 kWh (0.978%). An optimal solver status
does not imply that all demand was served.

Planning and `operate_fixed` are separate model configurations, so their
capacities and dispatch need not agree. The Operate demand-coverage chart
allocates served demand proportionally to local output and imports; it does
not perform physical electricity-origin tracing. This explanation is now in
the card's upper-right hover/focus help icon rather than permanent body text.
Time-window allocations of fixed costs and embodied CO2 are proportional to
the selected share of this hourly horizon.
