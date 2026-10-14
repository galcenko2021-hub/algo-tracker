/** Wordmark: a 3×3 patch of the activity heatmap next to the product name. */
const LEVELS = [1, 0, 2, 3, 1, 4, 0, 2, 3];

export default function Logo({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
        {LEVELS.map((level, i) => (
          <rect
            key={i}
            x={(i % 3) * 6.5}
            y={Math.floor(i / 3) * 6.5}
            width="5"
            height="5"
            rx="1.2"
            fill={`var(--heat-${level})`}
          />
        ))}
      </svg>
      <span className="text-[15px] font-semibold tracking-tight">algo-tracker</span>
    </span>
  );
}
