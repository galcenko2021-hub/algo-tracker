import { useState, type FormEvent } from "react";
import { api } from "../api/endpoints";
import { Button, Card, ErrorMessage, Field, PageTitle } from "../components/ui";
import { useImportCodeforces } from "../hooks/queries";
import { useAuth } from "../lib/auth-context";
import { errorMessage } from "../lib/errors";
import { inputClass } from "../lib/styles";

function timeZones(): string[] {
  const fallback = ["Europe/Moscow", "Europe/Kyiv", "Europe/Minsk", "Asia/Almaty", "UTC"];
  const intl = Intl as unknown as { supportedValuesOf?: (key: string) => string[] };
  try {
    return intl.supportedValuesOf?.("timeZone") ?? fallback;
  } catch {
    return fallback;
  }
}

export default function SettingsPage() {
  const { user, refreshUser } = useAuth();
  const [handle, setHandle] = useState(user?.cf_handle ?? "");
  const [timezone, setTimezone] = useState(user?.timezone ?? "Europe/Moscow");
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<unknown>(null);
  const [saving, setSaving] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<unknown>(null);
  const importer = useImportCodeforces();

  async function onSave(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setSaved(false);
    setSaveError(null);
    try {
      await api.updateMe({ cf_handle: handle.trim() || null, timezone });
      await refreshUser();
      setSaved(true);
    } catch (error) {
      setSaveError(error);
    } finally {
      setSaving(false);
    }
  }

  async function onExport() {
    setExporting(true);
    setExportError(null);
    try {
      const me = await api.me();
      const solves = [];
      for (let page = 1; ; page++) {
        const chunk = await api.solves({ page, page_size: 100 });
        solves.push(...chunk.items);
        if (solves.length >= chunk.total || chunk.items.length === 0) break;
      }
      const blob = new Blob(
        [JSON.stringify({ exported_at: new Date().toISOString(), user: me, solves }, null, 2)],
        { type: "application/json" },
      );
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `algo-tracker-export-${new Date().toISOString().slice(0, 10)}.json`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      setExportError(error);
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="flex max-w-2xl flex-col gap-6">
      <PageTitle>Настройки</PageTitle>

      <Card>
        <form onSubmit={onSave} className="flex flex-col gap-4">
          <h2 className="font-mono text-base">Профиль</h2>
          <p className="text-sm text-muted">Аккаунт: {user?.email}</p>
          <Field label="Хэндл на Codeforces" htmlFor="cf-handle">
            <input
              id="cf-handle"
              className={inputClass}
              value={handle}
              onChange={(e) => setHandle(e.target.value)}
              placeholder="tourist"
            />
          </Field>
          <Field label="Часовой пояс (даты, серии и теплокарта считаются в нём)" htmlFor="timezone">
            <input
              id="timezone"
              className={inputClass}
              list="timezones"
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
            />
            <datalist id="timezones">
              {timeZones().map((zone) => (
                <option key={zone} value={zone} />
              ))}
            </datalist>
          </Field>
          {saveError !== null && <ErrorMessage error={saveError} />}
          {saved && (
            <p role="status" className="text-sm text-ok">
              Сохранено
            </p>
          )}
          <div>
            <Button type="submit" disabled={saving}>
              {saving ? "Сохранение…" : "Сохранить"}
            </Button>
          </div>
        </form>
      </Card>

      <Card>
        <h2 className="mb-2 font-mono text-base">Импорт с Codeforces</h2>
        <p className="mb-3 text-sm text-muted">
          Загружает ваши принятые посылки как решения и все попытки для рекомендаций. Повторный
          запуск ничего не дублирует. Хэндл берётся из профиля (сначала сохраните его выше).
        </p>
        <Button
          disabled={importer.isPending || !user?.cf_handle}
          onClick={() => importer.mutate(undefined)}
        >
          {importer.isPending ? "Импортируем…" : "Импортировать с Codeforces"}
        </Button>
        {!user?.cf_handle && (
          <p className="mt-2 text-xs text-muted">Сначала укажите и сохраните хэндл.</p>
        )}
        {importer.isError && (
          <div className="mt-3">
            <ErrorMessage error={importer.error} />
          </div>
        )}
        {importer.data && (
          <p role="status" className="mt-3 text-sm">
            Готово: добавлено решений — <span className="font-mono">{importer.data.imported}</span>,
            пропущено (уже были) — <span className="font-mono">{importer.data.skipped}</span>,
            записано попыток — <span className="font-mono">{importer.data.attempts_recorded}</span>.
          </p>
        )}
      </Card>

      <Card>
        <h2 className="mb-2 font-mono text-base">Экспорт данных</h2>
        <p className="mb-3 text-sm text-muted">Скачать профиль и все решения одним JSON-файлом.</p>
        <Button variant="secondary" disabled={exporting} onClick={() => void onExport()}>
          {exporting ? "Готовим файл…" : "Скачать JSON"}
        </Button>
        {exportError !== null && (
          <p role="alert" className="mt-2 text-sm text-danger">
            {errorMessage(exportError)}
          </p>
        )}
      </Card>
    </div>
  );
}
