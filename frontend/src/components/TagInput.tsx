import { useId, useState, type KeyboardEvent } from "react";
import { useTagSuggestions } from "../hooks/queries";
import { inputClass } from "../lib/styles";
import { normalizeTag } from "../lib/tags";

interface TagInputProps {
  id: string;
  value: string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
}

/** Chip input: Enter or comma adds a tag, Backspace on an empty field removes the last one. */
export default function TagInput({ id, value, onChange, placeholder }: TagInputProps) {
  const [draft, setDraft] = useState("");
  const listId = useId();
  const suggestions = useTagSuggestions(normalizeTag(draft));

  function add(raw: string) {
    const tag = normalizeTag(raw);
    if (tag && tag.length <= 64 && !value.includes(tag)) onChange([...value, tag]);
    setDraft("");
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter" || event.key === ",") {
      event.preventDefault();
      add(draft);
    } else if (event.key === "Backspace" && draft === "" && value.length > 0) {
      onChange(value.slice(0, -1));
    }
  }

  return (
    <div>
      {value.length > 0 && (
        <ul className="mb-2 flex flex-wrap gap-1.5">
          {value.map((tag) => (
            <li
              key={tag}
              className="inline-flex items-center gap-1 rounded bg-accent-soft py-px pl-2 pr-1 text-xs leading-5 text-accent"
            >
              {tag}
              <button
                type="button"
                aria-label={`Удалить тег ${tag}`}
                className="rounded px-1 text-accent/70 transition-colors hover:bg-accent/10 hover:text-accent"
                onClick={() => onChange(value.filter((t) => t !== tag))}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
      <input
        id={id}
        className={inputClass}
        value={draft}
        list={listId}
        placeholder={placeholder ?? "Тег и Enter"}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={onKeyDown}
        onBlur={() => draft.trim() && add(draft)}
        autoComplete="off"
      />
      <datalist id={listId}>
        {(suggestions.data ?? [])
          .filter((tag) => !value.includes(tag))
          .map((tag) => (
            <option key={tag} value={tag} />
          ))}
      </datalist>
    </div>
  );
}
