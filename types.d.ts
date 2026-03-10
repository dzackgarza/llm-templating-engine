export interface TemplateReference {
  path?: string;
  text?: string;
  name?: string;
}

export interface TextFileBinding {
  name: string;
  path: string;
}

export interface Bindings {
  data?: Record<string, unknown>;
  text_files?: TextFileBinding[];
}

export interface TemplateOptions {
  search_paths?: string[];
  render_mode?: "body" | "document";
  strict_undefined?: boolean;
}

export interface TemplateDocument {
  path?: string | null;
  name?: string | null;
  frontmatter: Record<string, unknown>;
  body_template: string;
}

export interface RenderedTemplate {
  body: string;
  document: string;
}

export interface InspectTemplateRequest {
  template: TemplateReference;
  options?: TemplateOptions;
}

export interface InspectTemplateResponse {
  template: TemplateDocument;
}

export interface RenderTemplateRequest {
  template: TemplateReference;
  bindings?: Bindings;
  options?: TemplateOptions;
}

export interface RenderTemplateResponse {
  template: TemplateDocument;
  rendered: RenderedTemplate;
}

export interface ValidateTemplateResponse {
  valid: boolean;
  missing_bindings: string[];
}

export interface ErrorDetail {
  type: string;
  message: string;
}

export interface ErrorResponse {
  error: ErrorDetail;
}
