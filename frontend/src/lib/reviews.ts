import type { NextIntervals } from "../api/types";

/** Answer buttons: hotkey, label, SM-2 quality grade and the interval key to preview. */
export const ANSWERS: {
  key: string;
  label: string;
  quality: number;
  interval: keyof NextIntervals;
}[] = [
  { key: "1", label: "Снова", quality: 1, interval: "again" },
  { key: "2", label: "Трудно", quality: 3, interval: "hard" },
  { key: "3", label: "Хорошо", quality: 4, interval: "good" },
  { key: "4", label: "Легко", quality: 5, interval: "easy" },
];
