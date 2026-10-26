"use client";

import { VariableSpec } from "@/lib/api";
import clsx from "clsx";

/**
 * Inputs for a prompt's blanks (roadmap 29), shaped by each blank's spec: a dropdown for a choice,
 * yes or no for a boolean, a number field, a text area for long text. The description is the hint
 * and the default shows as the placeholder, used when the field is left empty.
 */
export default function BlankInputs({
  names, specs = {}, values, onChange, size = "sm",
}: {
  names: string[];
  specs?: Record<string, VariableSpec>;
  values: Record<string, string>;
  onChange: (values: Record<string, string>) => void;
  size?: "sm" | "xs";
}) {
  const field = clsx(
    "w-full rounded-md bg-gem-surface border border-gem-border text-slate-200 placeholder:text-slate-600 focus:outline-hidden focus:ring-1 focus:ring-blue-500",
    size === "xs" ? "px-2 py-1 text-xs" : "px-2.5 py-1.5 text-xs",
  );
  const set = (name: string, value: string) => onChange({ ...values, [name]: value });

  return (
    <div className="space-y-2">
      {names.map((name) => {
        const spec = specs[name];
        const value = values[name] ?? "";
        const hasDefault = spec?.default !== undefined && spec?.default !== null && spec.default !== "";
        const required = spec ? spec.required && !hasDefault : false;
        const placeholder = hasDefault ? `default: ${spec!.default}` : spec?.description || `Value for ${name}`;
        return (
          <div key={name} className="space-y-0.5">
            <label className="flex items-baseline gap-1.5 text-xs">
              <code className="text-blue-400">{"{" + name + "}"}</code>
              {required && <span className="text-red-400" title="Required">*</span>}
              {spec?.description && <span className="text-slate-500 truncate">{spec.description}</span>}
            </label>
            {spec?.type === "choice" ? (
              <select className={field} value={value} onChange={(e) => set(name, e.target.value)}>
                <option value="">{hasDefault ? `default: ${spec.default}` : "pick one"}</option>
                {spec.options.map((o) => <option key={o} value={o}>{o}</option>)}
              </select>
            ) : spec?.type === "boolean" ? (
              <select className={field} value={value} onChange={(e) => set(name, e.target.value)}>
                <option value="">{hasDefault ? `default: ${spec.default}` : "pick one"}</option>
                <option value="yes">yes</option>
                <option value="no">no</option>
              </select>
            ) : spec?.type === "long_text" ? (
              <textarea className={field} rows={3} placeholder={placeholder} value={value} onChange={(e) => set(name, e.target.value)} />
            ) : (
              <input className={field} type={spec?.type === "number" ? "number" : "text"} placeholder={placeholder} value={value} onChange={(e) => set(name, e.target.value)} />
            )}
          </div>
        );
      })}
    </div>
  );
}
