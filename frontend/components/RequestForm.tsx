"use client";

import { FormEvent, useState } from "react";

import {
  PRIORITIES,
  SERVICE_TYPES,
  label,
  type Priority,
  type RequestInput,
  type ServiceType,
} from "@/lib/types";

type FieldErrors = Partial<Record<keyof RequestInput, string>>;

export function validate(values: RequestInput): FieldErrors {
  const errors: FieldErrors = {};
  const nameRule = (v: string) =>
    v.trim().length < 2 || v.trim().length > 200 ? "Must be 2-200 characters" : undefined;
  errors.client_name = nameRule(values.client_name);
  errors.contact_name = nameRule(values.contact_name);
  const description = values.description.trim().length;
  if (description < 10 || description > 5000) {
    errors.description = "Must be 10-5000 characters";
  }
  return Object.fromEntries(Object.entries(errors).filter(([, v]) => v)) as FieldErrors;
}

interface Props {
  initial?: RequestInput;
  showPriority?: boolean;
  submitLabel: string;
  onSubmit: (values: RequestInput) => Promise<void>;
}

const EMPTY: RequestInput = {
  client_name: "",
  contact_name: "",
  service_type: SERVICE_TYPES[0],
  priority: "medium",
  description: "",
};

export function RequestForm({ initial = EMPTY, showPriority = false, submitLabel, onSubmit }: Props) {
  const [values, setValues] = useState<RequestInput>(initial);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function set<K extends keyof RequestInput>(key: K, value: RequestInput[K]) {
    setValues((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const found = validate(values);
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    setSaving(true);
    setSubmitError(null);
    try {
      await onSubmit({
        ...values,
        client_name: values.client_name.trim(),
        contact_name: values.contact_name.trim(),
        description: values.description.trim(),
      });
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-4">
      <Field label="Client name" error={errors.client_name}>
        <input
          className="input"
          value={values.client_name}
          onChange={(e) => set("client_name", e.target.value)}
        />
      </Field>
      <Field label="Contact name" error={errors.contact_name}>
        <input
          className="input"
          value={values.contact_name}
          onChange={(e) => set("contact_name", e.target.value)}
        />
      </Field>
      <Field label="Service type">
        <select
          className="input"
          value={values.service_type}
          onChange={(e) => set("service_type", e.target.value as ServiceType)}
        >
          {SERVICE_TYPES.map((t) => (
            <option key={t} value={t}>
              {label(t)}
            </option>
          ))}
        </select>
      </Field>
      {showPriority && (
        <Field label="Priority">
          <select
            className="input"
            value={values.priority}
            onChange={(e) => set("priority", e.target.value as Priority)}
          >
            {PRIORITIES.map((p) => (
              <option key={p} value={p}>
                {label(p)}
              </option>
            ))}
          </select>
        </Field>
      )}
      <Field label="Description" error={errors.description}>
        <textarea
          className="input min-h-32"
          value={values.description}
          onChange={(e) => set("description", e.target.value)}
        />
      </Field>
      {submitError && (
        <p role="alert" className="text-sm text-red-600">
          {submitError}
        </p>
      )}
      <button type="submit" disabled={saving} className="btn-primary">
        {saving ? "Saving..." : submitLabel}
      </button>
    </form>
  );
}

function Field({
  label: text,
  error,
  children,
}: {
  label: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-slate-700">{text}</span>
      {children}
      {error && <span className="mt-1 block text-sm text-red-600">{error}</span>}
    </label>
  );
}
