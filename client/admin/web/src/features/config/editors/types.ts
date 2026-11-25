export interface EditorProps {
  value: unknown;
  onChange: (next: unknown) => void;
  readOnly: boolean;
  /** Editors that can hold an unparseable intermediate state (JSON text) report validity here. */
  onValidityChange?: (ok: boolean) => void;
}
