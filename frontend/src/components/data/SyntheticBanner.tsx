import { SYNTHETIC_BANNER } from "@/lib/labels";

/** Shown wherever the selected dataset is synthetic. It cannot be dismissed. */
export function SyntheticBanner({ text = SYNTHETIC_BANNER }: { text?: string }) {
  return (
    <div
      role="note"
      aria-label="Synthetic data warning"
      className="flex gap-3 rounded-md border border-amber-500 border-l-4 bg-amber-50 p-4 text-sm text-amber-900"
    >
      <span aria-hidden="true" className="mt-0.5 font-bold">
        !
      </span>
      <div>
        <p className="font-semibold tracking-wide">SYNTHETIC DEMONSTRATION DATA</p>
        <p className="mt-1 text-amber-900/90">{text}</p>
      </div>
    </div>
  );
}
