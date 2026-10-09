import { formatHours, formatNumber, formatPercent, formatSignedPercent, formatSignedTonnes } from "@/lib/format";
import type { ZoneSummary } from "@/lib/types";

export function ZoneTable({ zones }: { zones: ZoneSummary[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[860px] text-left text-sm">
        <caption className="sr-only">
          Production by mine and zone for the selected period, sorted by gap to plan (largest shortfall first).
        </caption>
        <thead className="bg-slate-100 text-xs uppercase tracking-wide text-ink-700">
          <tr>
            <th scope="col" className="px-4 py-2.5 font-semibold">Mine</th>
            <th scope="col" className="px-4 py-2.5 font-semibold">Zone</th>
            <th scope="col" className="px-4 py-2.5 text-right font-semibold">Planned (t)</th>
            <th scope="col" className="px-4 py-2.5 text-right font-semibold">Actual (t)</th>
            <th scope="col" className="px-4 py-2.5 text-right font-semibold">Gap (t)</th>
            <th scope="col" className="px-4 py-2.5 text-right font-semibold">Attainment</th>
            <th scope="col" className="px-4 py-2.5 text-right font-semibold">Downtime (h)</th>
            <th scope="col" className="px-4 py-2.5 text-right font-semibold">Weather (h)</th>
            <th scope="col" className="px-4 py-2.5 text-right font-semibold">Blasting (h)</th>
            <th scope="col" className="px-4 py-2.5 text-right font-semibold">Pending rows</th>
          </tr>
        </thead>
        <tbody>
          {zones.map((zone) => {
            const gapNegative = zone.gap_t !== null && zone.gap_t < 0;
            return (
              <tr key={`${zone.mine_id}/${zone.zone_id}`} className="border-t border-line">
                <td className="px-4 py-2.5 font-mono text-xs text-ink-700">{zone.mine_id}</td>
                <td className="px-4 py-2.5 font-mono text-xs font-medium text-ink-900">{zone.zone_id}</td>
                <td className="tabular px-4 py-2.5 text-right">{formatNumber(zone.planned_t, 0)}</td>
                <td className="tabular px-4 py-2.5 text-right">{formatNumber(zone.actual_t, 0)}</td>
                <td className={`tabular px-4 py-2.5 text-right font-medium ${gapNegative ? "text-brick-700" : "text-forest-800"}`}>
                  {formatSignedTonnes(zone.gap_t, 0)}
                  <span className="block text-xs font-normal text-ink-500">{formatSignedPercent(zone.variance_pct)}</span>
                </td>
                <td className="tabular px-4 py-2.5 text-right">{formatPercent(zone.attainment_pct)}</td>
                <td className="tabular px-4 py-2.5 text-right">{formatHours(zone.equipment_downtime_h_total, 0)}</td>
                <td className="tabular px-4 py-2.5 text-right">{formatHours(zone.weather_delay_h_total, 0)}</td>
                <td className="tabular px-4 py-2.5 text-right">{formatHours(zone.blasting_delay_h_total, 0)}</td>
                <td className="tabular px-4 py-2.5 text-right text-ink-500">{formatNumber(zone.pending_rows)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
