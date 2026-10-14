import { useEffect, useRef, useState, type FormEvent } from "react";
import type { Platform, Solve } from "../api/types";
import { useCreateSolve, useUpdateSolve } from "../hooks/queries";
import { useAuth } from "../lib/auth-context";
import { todayIn } from "../lib/format";
import { inputClass } from "../lib/styles";
import {
  emptySolveForm,
  PLATFORM_LABELS,
  toCreatePayload,
  toPatchPayload,
  validateSolveForm,
  valuesFromSolve,
  type SolveFormErrors,
  type SolveFormValues,
} from "../lib/validation";
import TagInput from "./TagInput";
import { Button, ErrorMessage, Field } from "./ui";

interface Props {
  /** Pass a solve to edit it, omit to add a new one. */
  solve?: Solve;
  onClose: () => void;
}

export default function SolveFormModal({ solve, onClose }: Props) {
  const { user } = useAuth();
  const timezone = user?.timezone ?? "UTC";
  const today = todayIn(timezone);
  const isEdit = solve !== undefined;

  const [values, setValues] = useState<SolveFormValues>(() =>
    solve
      ? valuesFromSolve(solve, localDay(solve.solved_at, timezone))
      : { ...emptySolveForm, solvedDate: today },
  );
  const [errors, setErrors] = useState<SolveFormErrors>({});
  const create = useCreateSolve();
  const update = useUpdateSolve();
  const mutation = isEdit ? update : create;
  const titleRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    titleRef.current?.focus();
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  function set<K extends keyof SolveFormValues>(key: K, value: SolveFormValues[K]) {
    setValues((prev) => ({ ...prev, [key]: value }));
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const found = validateSolveForm(values);
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    const done = { onSuccess: onClose };
    if (solve) {
      const body = toPatchPayload(values);
      if (values.solvedDate !== localDay(solve.solved_at, timezone)) {
        body.solved_at = `${values.solvedDate}T12:00:00Z`;
      }
      update.mutate({ id: solve.id, body }, done);
    } else {
      create.mutate(toCreatePayload(values, today), done);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-[#1f2528]/40 p-4 backdrop-blur-[2px]"
      onMouseDown={(event) => event.target === event.currentTarget && onClose()}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="solve-form-title"
        className="my-10 w-full max-w-xl rounded-xl border border-line bg-surface p-6 shadow-[0_24px_60px_-20px_rgb(20_28_36/0.35)]"
      >
        <h2 id="solve-form-title" className="mb-5 text-lg font-semibold">
          {isEdit ? "Редактировать решение" : "Добавить решение"}
        </h2>
        <form onSubmit={onSubmit} noValidate className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Платформа" htmlFor="platform">
            <select
              id="platform"
              className={inputClass}
              value={values.platform}
              disabled={isEdit}
              onChange={(e) => set("platform", e.target.value as Platform)}
            >
              {(Object.keys(PLATFORM_LABELS) as Platform[]).map((p) => (
                <option key={p} value={p}>
                  {PLATFORM_LABELS[p]}
                </option>
              ))}
            </select>
          </Field>
          <Field label="ID задачи (например 1700A)" htmlFor="externalId" error={errors.externalId}>
            <input
              id="externalId"
              className={inputClass}
              value={values.externalId}
              disabled={isEdit}
              onChange={(e) => set("externalId", e.target.value)}
            />
          </Field>
          <div className="sm:col-span-2">
            <Field label="Название *" htmlFor="title" error={errors.title}>
              <input
                id="title"
                ref={titleRef}
                className={inputClass}
                value={values.title}
                onChange={(e) => set("title", e.target.value)}
              />
            </Field>
          </div>
          <div className="sm:col-span-2">
            <Field label="Ссылка" htmlFor="url" error={errors.url}>
              <input
                id="url"
                className={inputClass}
                placeholder="https://"
                value={values.url}
                onChange={(e) => set("url", e.target.value)}
              />
            </Field>
          </div>
          <Field label="Рейтинг" htmlFor="rating" error={errors.rating}>
            <input
              id="rating"
              inputMode="numeric"
              className={inputClass}
              value={values.rating}
              onChange={(e) => set("rating", e.target.value)}
            />
          </Field>
          <Field label="Потрачено минут" htmlFor="timeSpent" error={errors.timeSpent}>
            <input
              id="timeSpent"
              inputMode="numeric"
              className={inputClass}
              value={values.timeSpent}
              onChange={(e) => set("timeSpent", e.target.value)}
            />
          </Field>
          <div className="sm:col-span-2">
            <Field label="Теги" htmlFor="tags">
              <TagInput id="tags" value={values.tags} onChange={(tags) => set("tags", tags)} />
            </Field>
          </div>
          <Field label="Дата решения" htmlFor="solvedDate">
            <input
              id="solvedDate"
              type="date"
              max={today}
              className={inputClass}
              value={values.solvedDate}
              onChange={(e) => set("solvedDate", e.target.value)}
            />
          </Field>
          <div className="sm:col-span-2">
            <Field label="Заметка (до 2000 символов)" htmlFor="notes" error={errors.notes}>
              <textarea
                id="notes"
                rows={3}
                className={inputClass}
                value={values.notes}
                onChange={(e) => set("notes", e.target.value)}
              />
            </Field>
          </div>
          {mutation.isError && (
            <div className="sm:col-span-2">
              <ErrorMessage error={mutation.error} />
            </div>
          )}
          <div className="mt-1 flex justify-end gap-2 border-t border-line pt-4 sm:col-span-2">
            <Button variant="secondary" onClick={onClose}>
              Отмена
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Сохранение…" : "Сохранить"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

/** The local calendar day (YYYY-MM-DD) of an ISO instant in the given time zone. */
function localDay(iso: string, timezone: string): string {
  return todayIn(timezone, new Date(iso));
}
