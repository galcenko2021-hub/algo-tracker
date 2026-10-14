import { useMemo, useRef, useState } from "react";
import type { HeatmapDay } from "../api/types";
import { monthShort } from "../lib/format";
import { addDays, buildGrid, cellLabel, monthLabels, type Cell } from "../lib/heatmap";

const CELL = 12;
const GAP = 3;
const STEP = CELL + GAP;
const LEFT = 28;
const TOP = 18;
const WEEKDAY_LABELS: [number, string][] = [
  [0, "Пн"],
  [2, "Ср"],
  [4, "Пт"],
];

interface HeatmapProps {
  days: HeatmapDay[];
  /** Last day shown (the user's local "today"), YYYY-MM-DD. */
  end: string;
  /** Number of week columns: 53 for a full year. */
  weeks?: number;
}

export default function Heatmap({ days, end, weeks = 53 }: HeatmapProps) {
  const cells = useMemo(() => buildGrid(days, end, weeks), [days, end, weeks]);
  const byDate = useMemo(() => new Map(cells.map((c) => [c.date, c])), [cells]);
  const months = useMemo(() => monthLabels(cells), [cells]);
  const svgRef = useRef<SVGSVGElement>(null);
  const [tabStop, setTabStop] = useState(end);
  const [active, setActive] = useState<Cell | null>(null);

  const width = LEFT + weeks * STEP;
  const height = TOP + 7 * STEP;

  function moveFocus(from: Cell, key: string): void {
    const delta: Record<string, number> = {
      ArrowLeft: -7,
      ArrowRight: 7,
      ArrowUp: -1,
      ArrowDown: 1,
    };
    const step = delta[key];
    if (step === undefined) return;
    const target = byDate.get(addDays(from.date, step));
    if (!target) return;
    setTabStop(target.date);
    svgRef.current?.querySelector<SVGElement>(`[data-date="${target.date}"]`)?.focus();
  }

  return (
    <div>
      <div className="overflow-x-auto pb-2">
        <div className="relative inline-block" style={{ width, height }}>
          <svg
            ref={svgRef}
            width={width}
            height={height}
            role="group"
            aria-label="Теплокарта активности"
            className="block"
          >
            {months.map(({ week, month }) => (
              <text
                key={`${week}-${month}`}
                x={LEFT + week * STEP}
                y={11}
                fontSize={10}
                fill="var(--muted)"
              >
                {monthShort(month)}
              </text>
            ))}
            {WEEKDAY_LABELS.map(([row, label]) => (
              <text
                key={label}
                x={0}
                y={TOP + row * STEP + CELL - 2}
                fontSize={10}
                fill="var(--muted)"
              >
                {label}
              </text>
            ))}
            {cells.map((cell) => (
              <rect
                key={cell.date}
                data-date={cell.date}
                data-level={cell.level}
                role="img"
                aria-label={cellLabel(cell)}
                tabIndex={cell.date === tabStop ? 0 : -1}
                x={LEFT + cell.week * STEP}
                y={TOP + cell.weekday * STEP}
                width={CELL}
                height={CELL}
                rx={2}
                fill={`var(--heat-${cell.level})`}
                className="outline-none focus-visible:stroke-[var(--accent)]"
                strokeWidth={active?.date === cell.date ? 2 : 0}
                stroke="var(--accent)"
                onMouseEnter={() => setActive(cell)}
                onMouseLeave={() => setActive(null)}
                onFocus={() => {
                  setTabStop(cell.date);
                  setActive(cell);
                }}
                onBlur={() => setActive(null)}
                onKeyDown={(event) => {
                  if (event.key.startsWith("Arrow")) {
                    event.preventDefault();
                    moveFocus(cell, event.key);
                  }
                }}
              />
            ))}
          </svg>
          {active && (
            <div
              role="tooltip"
              className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-full whitespace-nowrap rounded border border-line bg-surface-2 px-2 py-1 font-mono text-xs"
              style={{
                left: LEFT + active.week * STEP + CELL / 2,
                top: TOP + active.weekday * STEP - 4,
              }}
            >
              {cellLabel(active)}
            </div>
          )}
        </div>
      </div>
      <div
        className="mt-1 flex items-center justify-end gap-1 text-xs text-muted"
        aria-hidden="true"
      >
        <span>Меньше</span>
        {[0, 1, 2, 3, 4].map((level) => (
          <span
            key={level}
            className="inline-block h-3 w-3 rounded-sm"
            style={{ background: `var(--heat-${level})` }}
          />
        ))}
        <span>Больше</span>
      </div>
    </div>
  );
}
