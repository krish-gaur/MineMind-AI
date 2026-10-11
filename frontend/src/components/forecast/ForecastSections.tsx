"use client";

import { ValueKindBadge } from "@/components/ui/Badges";
import { Card, CardHeader } from "@/components/ui/Card";
import { StatusPill, type Tone } from "@/components/ui/Badges";
import { EmptyState } from "@/components/ui/States";
import {
  formatDate,
  formatNumber,
  formatPercent,
  formatSignedTonnes,
} from "@/lib/format";
import type {
  ClassificationEvaluation,
  ForecastEvaluation,
  ForecastModelCard,
  ForecastResponse,
  ModelMetric,
} from "@/lib/types";

const VERDICT: Record<ForecastEvaluation["verdict"], { label: string; tone: Tone }> = {
  beats_best_baseline: { label: "Beats the best baseline", tone: "good" },
  no_reliable_difference: { label: "No reliable difference from the baseline", tone: "warn" },
  worse_than_best_baseline: { label: "Worse than the best baseline", tone: "bad" },
};

const CLASSIFIER_VERDICT: Record<ClassificationEvaluation["verdict"], { label: string; tone: Tone }> = {
  beats_base_rate: { label: "Adds skill over the base rate", tone: "good" },
  no_skill_over_base_rate: { label: "No skill over the base rate", tone: "bad" },
  not_evaluable: { label: "Not evaluable", tone: "neutral" },
};

export function ModelCardSection({ model, dataset }: { model: ForecastModelCard; dataset: ForecastResponse["dataset"] }) {
  const sourceText =
    model.source === "trained"
      ? "Trained now and saved"
      : model.source === "loaded"
        ? "Loaded from saved model (data unchanged)"
        : "Reused from this session";
  return (
    <Card labelledBy="model-title">
      <CardHeader
        id="model-title"
        title="Model"
        description="Regression forecast of daily output. Its outputs are forecasts, not measurements."
        actions={<ValueKindBadge kind="forecast" />}
      />
      <dl className="grid gap-4 p-5 text-sm sm:grid-cols-2 xl:grid-cols-4">
        <div className="sm:col-span-2 xl:col-span-2">
          <dt className="text-xs text-ink-500">Regressor</dt>
          <dd className="font-medium text-ink-900">{model.regressor}</dd>
          <dd className="mt-1 text-xs text-ink-500">Classifier: {model.classifier}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-500">Training data</dt>
          <dd className="font-medium text-ink-900">
            {formatNumber(model.trained_on.labelled_days)} complete days
          </dd>
          <dd className="text-xs text-ink-500">
            {formatDate(model.trained_on.first_day)} to {formatDate(model.trained_on.last_actual_day)}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-ink-500">Model state</dt>
          <dd className="font-medium text-ink-900">{sourceText}</dd>
          <dd className="font-mono text-xs text-ink-500">fingerprint {model.fingerprint.slice(0, 12)}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-500">Features</dt>
          <dd className="font-medium text-ink-900">{model.features.length} lagged and calendar inputs</dd>
          <dd className="text-xs text-ink-500">No same-day operational values are used.</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-500">Dataset</dt>
          <dd className="font-medium text-ink-900">{dataset.name}</dd>
          <dd className="text-xs text-ink-500">Trained {formatDate(model.trained_at.slice(0, 10))}</dd>
        </div>
      </dl>
    </Card>
  );
}

export function EvaluationSection({ evaluation }: { evaluation: ForecastEvaluation }) {
  const verdict = VERDICT[evaluation.verdict];
  const gap = evaluation.gap_to_best_baseline;
  const baselineName = evaluation.models.find((m) => m.name === evaluation.best_baseline)?.label ?? evaluation.best_baseline;
  return (
    <Card labelledBy="evaluation-title">
      <CardHeader
        id="evaluation-title"
        title="Backtest verdict"
        description={evaluation.method}
        actions={<StatusPill tone={verdict.tone}>{verdict.label}</StatusPill>}
      />
      <div className="grid gap-6 p-5 lg:grid-cols-3">
        <div className="space-y-3 text-sm lg:col-span-2">
          <p className="text-ink-900">{evaluation.verdict_text}</p>
          <p className="text-xs text-ink-500">
            Evaluated on {formatNumber(evaluation.n_evaluated_days)} out-of-sample days,{" "}
            {formatDate(evaluation.evaluation_start)} to {formatDate(evaluation.evaluation_end)}. Best baseline:{" "}
            {baselineName}.
          </p>
        </div>
        <dl className="grid grid-cols-2 gap-3 rounded-md border border-line bg-slate-100/60 p-4 text-sm">
          <div className="col-span-2">
            <dt className="text-xs text-ink-500">MAE vs best baseline (t/day)</dt>
            <dd className="tabular font-mono text-lg font-semibold text-ink-900">
              {formatSignedTonnes(gap.mae_difference, 1)}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-ink-500">95% interval</dt>
            <dd className="tabular font-mono text-xs text-ink-900">
              {formatNumber(gap.ci95_low, 1)} to {formatNumber(gap.ci95_high, 1)}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-ink-500">Skill vs baseline</dt>
            <dd className="tabular font-mono text-xs text-ink-900">
              {gap.skill_pct_vs_best_baseline === null ? "n/a" : formatPercent(gap.skill_pct_vs_best_baseline, 1)}
            </dd>
          </div>
          <p className="col-span-2 text-[11px] text-ink-500">{gap.bootstrap}. Negative means lower error than the baseline.</p>
        </dl>
      </div>
    </Card>
  );
}

export function ModelComparisonSection({ evaluation }: { evaluation: ForecastEvaluation }) {
  const best = evaluation.models.reduce((min, m) => (m.mae < min.mae ? m : min), evaluation.models[0] as ModelMetric);
  const rows = [...evaluation.models].sort((a, b) => a.mae - b.mae);
  return (
    <Card labelledBy="comparison-title">
      <CardHeader
        id="comparison-title"
        title="Model and baseline comparison"
        description="Same out-of-sample days for every row. Lower is better. MAE is the average absolute error in tonnes per day."
      />
      <div className="space-y-5 p-5">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <caption className="sr-only">Forecast error by model and baseline on the backtest</caption>
            <thead className="bg-slate-100 text-xs uppercase tracking-wide text-ink-700">
              <tr>
                <th scope="col" className="px-4 py-2.5 font-semibold">Method</th>
                <th scope="col" className="px-4 py-2.5 font-semibold">Type</th>
                <th scope="col" className="px-4 py-2.5 text-right font-semibold">MAE (t/day)</th>
                <th scope="col" className="px-4 py-2.5 text-right font-semibold">RMSE (t/day)</th>
                <th scope="col" className="px-4 py-2.5 text-right font-semibold">Days</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.name} className={`border-t border-line ${row.name === best.name ? "bg-forest-50/60" : ""}`}>
                  <td className="px-4 py-2.5">
                    <span className="font-medium text-ink-900">{row.label}</span>
                    {row.name === best.name ? <span className="ml-2 text-xs font-semibold text-forest-800">LOWEST MAE</span> : null}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-ink-700">{row.kind === "model" ? "Model" : "Baseline"}</td>
                  <td className="tabular px-4 py-2.5 text-right font-mono">{formatNumber(row.mae, 1)}</td>
                  <td className="tabular px-4 py-2.5 text-right font-mono">{formatNumber(row.rmse, 1)}</td>
                  <td className="tabular px-4 py-2.5 text-right">{formatNumber(row.n)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div>
          <h3 className="mb-2 text-sm font-semibold text-ink-900">Stability across backtest folds</h3>
          <div className="overflow-x-auto rounded border border-line">
            <table className="w-full min-w-[560px] text-left text-xs">
              <caption className="sr-only">Mean absolute error for each backtest fold</caption>
              <thead className="bg-slate-100 text-ink-700">
                <tr>
                  <th scope="col" className="px-3 py-2 font-semibold">Fold</th>
                  <th scope="col" className="px-3 py-2 font-semibold">Test window</th>
                  <th scope="col" className="px-3 py-2 text-right font-semibold">Train days</th>
                  <th scope="col" className="px-3 py-2 text-right font-semibold">Gradient boosting MAE</th>
                  <th scope="col" className="px-3 py-2 text-right font-semibold">Plan MAE</th>
                  <th scope="col" className="px-3 py-2 text-right font-semibold">Seasonal naive MAE</th>
                </tr>
              </thead>
              <tbody>
                {evaluation.folds.map((fold) => {
                  const perFold = evaluation.per_fold.find((row) => row.fold === fold.fold);
                  return (
                    <tr key={fold.fold} className="border-t border-line">
                      <td className="px-3 py-2">{fold.fold}</td>
                      <td className="px-3 py-2">
                        {formatDate(fold.test_start)} to {formatDate(fold.test_end)}
                      </td>
                      <td className="tabular px-3 py-2 text-right">{formatNumber(fold.train_days)}</td>
                      <td className="tabular px-3 py-2 text-right font-mono">{formatNumber(fold.gradient_boosting_mae, 1)}</td>
                      <td className="tabular px-3 py-2 text-right font-mono">{formatNumber(perFold?.plan_mae ?? null, 1)}</td>
                      <td className="tabular px-3 py-2 text-right font-mono">
                        {formatNumber(perFold?.seasonal_naive_7_mae ?? null, 1)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-xs text-ink-500">
            Mean fold MAE (gradient boosting): {formatNumber(evaluation.mae_by_fold.gradient_boosting?.mean ?? null, 1)} t/day, standard deviation{" "}
            {formatNumber(evaluation.mae_by_fold.gradient_boosting?.std ?? null, 1)}.
          </p>
        </div>
      </div>
    </Card>
  );
}

export function ClassificationSection({ classification }: { classification: ClassificationEvaluation }) {
  const verdict = CLASSIFIER_VERDICT[classification.verdict];
  return (
    <Card labelledBy="classifier-title">
      <CardHeader
        id="classifier-title"
        title="Daily shortfall classifier"
        description={`${classification.target} Model: ${classification.model}.`}
        actions={
          <>
            <ValueKindBadge kind="probability" />
            <StatusPill tone={verdict.tone}>{verdict.label}</StatusPill>
          </>
        }
      />
      <div className="grid gap-6 p-5 lg:grid-cols-3">
        <dl className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <dt className="text-xs text-ink-500">Base rate (days below target)</dt>
            <dd className="tabular font-mono font-semibold">{formatPercent(classification.base_rate * 100, 1)}</dd>
          </div>
          <div>
            <dt className="text-xs text-ink-500">ROC AUC</dt>
            <dd className="tabular font-mono font-semibold">
              {classification.roc_auc === null ? "n/a" : classification.roc_auc.toFixed(2)}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-ink-500">Brier score</dt>
            <dd className="tabular font-mono font-semibold">{classification.brier.toFixed(3)}</dd>
          </div>
          <div>
            <dt className="text-xs text-ink-500">Brier skill vs base rate</dt>
            <dd className="tabular font-mono font-semibold">
              {classification.brier_skill_pct === null ? "n/a" : formatPercent(classification.brier_skill_pct, 1)}
            </dd>
          </div>
          <p className="col-span-2 text-xs text-ink-500">
            n = {formatNumber(classification.n)} out-of-sample days. {classification.verdict_text}
          </p>
        </dl>
        <div className="lg:col-span-2">
          <h3 className="mb-2 text-sm font-semibold text-ink-900">Calibration (predicted vs observed)</h3>
          {classification.calibration.length === 0 ? (
            <EmptyState title="Too few days to bin predictions." />
          ) : (
            <table className="w-full text-left text-xs">
              <caption className="sr-only">Predicted shortfall probability against observed rate, in quintiles</caption>
              <thead className="bg-slate-100 text-ink-700">
                <tr>
                  <th scope="col" className="px-3 py-2 font-semibold">Probability range</th>
                  <th scope="col" className="px-3 py-2 text-right font-semibold">Days</th>
                  <th scope="col" className="px-3 py-2 text-right font-semibold">Mean predicted</th>
                  <th scope="col" className="px-3 py-2 text-right font-semibold">Observed rate</th>
                </tr>
              </thead>
              <tbody>
                {classification.calibration.map((bin) => (
                  <tr key={bin.bin} className="border-t border-line">
                    <td className="px-3 py-2 font-mono">{bin.bin}</td>
                    <td className="tabular px-3 py-2 text-right">{formatNumber(bin.n)}</td>
                    <td className="tabular px-3 py-2 text-right">{formatPercent(bin.mean_predicted * 100, 0)}</td>
                    <td className="tabular px-3 py-2 text-right">{formatPercent(bin.observed_rate * 100, 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </Card>
  );
}

export function DriversSection({ drivers }: { drivers: ForecastResponse["drivers"] }) {
  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <Card labelledBy="forecast-drivers-title">
        <CardHeader
          id="forecast-drivers-title"
          title="What the forecast relies on"
          description={drivers.forecast_drivers_method ?? ""}
        />
        <ol className="space-y-2 p-5 text-sm">
          {drivers.forecast_drivers.map((item) => (
            <li key={item.feature} className="flex items-center justify-between gap-3 border-b border-line pb-2 last:border-0">
              <span className="text-ink-900">{item.label}</span>
              <span className="tabular font-mono text-xs text-ink-700">+{formatNumber(item.importance_t, 1)} t MAE if shuffled</span>
            </li>
          ))}
        </ol>
      </Card>
      <Card labelledBy="shortfall-drivers-title">
        <CardHeader
          id="shortfall-drivers-title"
          title="Factors associated with shortfall days"
          description={drivers.shortfall_method}
          actions={<ValueKindBadge kind="estimate" />}
        />
        <ul className="space-y-2 p-5 text-sm">
          {drivers.shortfall_coefficients.map((item) => (
            <li key={item.feature} className="flex items-center justify-between gap-3 border-b border-line pb-2 last:border-0">
              <span className="text-ink-900">{item.label}</span>
              <span className="text-right text-xs text-ink-700">
                {item.direction} ({item.standardised_coefficient >= 0 ? "+" : ""}
                {item.standardised_coefficient.toFixed(2)})
              </span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
