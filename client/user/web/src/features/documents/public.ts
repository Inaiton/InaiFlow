/**
 * Documents feature — public surface for other features (operations). Import only from here
 * (frontend counterpart of a module `interface.py`, skill enforcing-modular-architecture).
 */
export { DocumentPicker, DocumentMultiPicker } from "./components/shared/DocumentPicker";
export { useDocuments, useUploadDocument, useCreateDocument, type DocumentSummary } from "./api/documents";
export { useTemplates, REPORT_DOC } from "./api/templates";
export { saveBlob, ALLOWED_MIME, titleFromFile } from "./lib/transfer";
export { useDocsPath } from "./paths";
