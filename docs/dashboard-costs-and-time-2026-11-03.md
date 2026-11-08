# Costs and time handling — 3 November 2026

Status updated 7 November: the whole-model technology cost table is **temporarily
hidden** by commenting out its Planning layout. Its helper, callbacks and
reconciliation tests remain; it is not currently a visible dashboard section.
There is no custom CSV-export control. The implemented table's cost-class
selector uses the actual NetCDF classes, without objective weights or combining
different units. Rows keep raw technology IDs, including transmission, demand,
storage, unused technologies and negative costs. Numeric table data retain full
precision; display uses six decimal places. No additional export workflow is
required.

The full-horizon `cost` result is authoritative. Annualised investment, fixed
OPEX, variable OPEX and unitemized remainder reconcile to it. CAPEX stays separate
to avoid adding it again to annualised investment. Unexported components remain
blank. Selected-window estimates prorate fixed/unitemized costs by represented
hours (`timestep_resolution * timestep_weights`) and retain the selected actual
variable costs. The full-horizon column can be compared with the corresponding raw model cost
class summed over nodes and technologies.

Each node/technology belongs to exactly one accounting scope. Technologies
connected to multiple carriers are **Shared**; their undivided costs are excluded
from carrier-exclusive summaries and appear once in the underlying whole-model
ledger. Because that table is hidden, visible carrier summaries alone do not
show the complete total for models with Shared technologies.
Physical carrier views still include their applicable flows and capacities.
The dashboard does not invent an allocation between heat and electricity.

An independent check of the saved THD annual heat-pump scenario
(`thd_calliope_model/scenario_results/scenario_3_heat_pump.nc`, 8,760 timesteps)
gave monetary costs of **644994.6232335933**, consisting of carrier-exclusive
costs **611334.6758831537** and Shared heat-pump costs **33659.94735043961**.
Their difference from the raw NetCDF total was zero. The saved result was read
without rerunning the optimization or changing the model files.

Other changes:

- Energy/CO2 time aggregation sums values and uses readable calendar intervals.
- Transmission charts use received power in kW and sending-end loading; solved
  line capacities take precedence over input capacity bounds. On long windows,
  duration-weighted averages and original peaks are both retained.
- Storage charge/discharge bars sum energy. SOC shows end-of-interval state and
  original min/max on aggregated windows.
- Unexpected read/selection failures are logged and shown as “Data unavailable”
  while affected figures/tables are cleared. Optional omitted unmet-demand slack
  remains a defined zero. Missing input capacity bounds are unbounded, not zero.
- Exact date/time fields synchronize with the draft slider, validate the model
  range, snap to available timesteps and retain Apply and the calendar-year cap.

Tests compare costs for every enabled node/technology/class against raw results,
exercise Shared scopes and negative costs, test irregular/half-hour series,
preserve storage extrema, and exercise the Dash HTTP error handler and browser
date validation. Browser checks cover German model cost-class switching and the
saved THD year with a Shared heat pump.

## Subsequent checkpoint

The 7 November annual THD recalculation reproduced the Planning monetary total
above and also generated genuine fixed-fleet rolling Operate results. Operate
variable OPEX was EUR 568732.8225459721; it excludes investment and is not the
same quantity as Planning's full modeled cost. Missing `co2` is displayed as
unavailable, not measured zero. Operate errors now include a missing-run/export
hint, and switching tabs clears the shared banner. Coverage offers Auto ≤60
calendar bins, original/hourly mode, full screen, and hover/focus help. See
[the current report](dashboard-progress-2026-11-07.md) for scope and validation.
