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

/** Room a tooltip needs on each side of its cell before it would be clipped (px). */
const EDGE_ROOM = 80;

/**
 * The scroll container clips anything outside the grid, so the tooltip flips below the cell
 * on the top rows and hugs the cell instead of centring on it near the left and right edges.
 */
function Tooltip({ cell, weeks }: { cell: Cell; weeks: number }) {
  const x = LEFT + cell.week * STEP;
  const below = cell.weekday <= 1;
  const nearLeft = cell.week * STEP < EDGE_ROOM;
  const nearRight = (weeks - 1 - cell.week) * STEP < EDGE_ROOM;

  const left = nearLeft ? x : nearRight ? x + CELL : x + CELL / 2;
  const shiftX = nearLeft ? "0" : nearRight ? "-100%" : "-50%";
  const top = below ? TOP + cell.weekday * STEP + CELL + 6 : TOP + cell.weekday * STEP - 6;
  const shiftY = below ? "0" : "-100%";

  return (
    <div
      role="tooltip"
      className="pointer-events-none absolute z-10 whitespace-nowrap rounded-md bg-fg px-2 py-1 text-xs font-medium text-bg shadow-sm"
      style={{ left, top, transform: `translate(${shiftX}, ${shiftY})` }}
    >
      {cellLabel(cell)}
    </div>
  );
}

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
          {active && <Tooltip cell={active} weeks={weeks} />}
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
