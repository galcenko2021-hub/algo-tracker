import { useEffect, useMemo, useRef, useState } from "react";
import type { HeatmapDay } from "../api/types";
import { monthShort } from "../lib/format";
import { addDays, buildGrid, cellLabel, monthLabels, type Cell } from "../lib/heatmap";

const CELL = 13;
const GAP = 3;
const STEP = CELL + GAP;
const LEFT = 30;
const TOP = 20;
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
  const scrollRef = useRef<HTMLDivElement>(null);
  const [tabStop, setTabStop] = useState(end);
  const [active, setActive] = useState<Cell | null>(null);

  // On narrow screens the grid scrolls: start at the most recent weeks, not a year ago.
  useEffect(() => {
    const box = scrollRef.current;
    if (box) box.scrollLeft = box.scrollWidth;
  }, [weeks, end]);

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
      <div ref={scrollRef} className="overflow-x-auto pb-2">
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
                fontSize={11}
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
                fontSize={11}
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
                rx={3}
                fill={`var(--heat-${cell.level})`}
                className="outline-none focus-visible:stroke-[var(--fg)]"
                strokeWidth={active?.date === cell.date ? 1.5 : 0}
                stroke="var(--fg)"
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
              className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-md bg-fg px-2 py-1 text-xs font-medium text-bg shadow-sm"
              style={{
                left: LEFT + active.week * STEP + CELL / 2,
                top: TOP + active.weekday * STEP - 6,
              }}
            >
              {cellLabel(active)}
            </div>
          )}
        </div>
      </div>
      <div
        className="mt-2 flex items-center justify-end gap-1.5 text-xs text-muted"
        aria-hidden="true"
      >
        <span>Меньше</span>
        {[0, 1, 2, 3, 4].map((level) => (
          <span
            key={level}
            className="inline-block h-[11px] w-[11px] rounded-[3px]"
            style={{ background: `var(--heat-${level})` }}
          />
        ))}
        <span>Больше</span>
      </div>
    </div>
  );
}
