/**
 * Type definitions for template-parsing-engine
 * 
 * Use these types when calling the template-parsing-engine CLI from TypeScript/Node.js
 */

/** File variable specification */
export interface FileVariable {
  /** Variable name for template substitution */
  name: string;
  /** Path to file containing variable content */
  path: string;
}

/** Variable specification combining string and file variables */
export interface VariableSpec {
  /** String variables for template substitution */
  string_vars?: Record<string, string>;
  /** File variables to read and substitute */
  file_vars?: FileVariable[];
}

/** Request to render a template */
export interface RenderRequest {
  /** Path to the template file (absolute or relative to PROMPTS_DIR) */
  template_path: string;
  /** Output mode: 'full' includes frontmatter, 'body' is template body only */
  output_mode?: 'full' | 'body';
  /** Variables for template substitution */
  variables?: VariableSpec;
  /** Additional paths to search for includes/imports */
  search_paths?: string[];
}

/** Rendered template result data */
export interface RenderResultData {
  /** Rendered template content */
  content: string;
  /** Parsed YAML frontmatter from the template */
  frontmatter: Record<string, any>;
}

/** Successful render response */
export interface RenderResponseSuccess {
  /** Always true for success */
  ok: true;
  /** Rendered template result */
  result: RenderResultData;
}

/** Error render response */
export interface RenderResponseError {
  /** Always false for errors */
  ok: false;
  /** Error message */
  error: string;
  /** Error type for programmatic handling */
  error_type: 'MissingVariablesError' | 'TemplateFormatError' | 'FileNotFoundError' | 'TemplateNotFound' | 'UnknownError';
}

/** Union type for responses */
export type RenderResponse = RenderResponseSuccess | RenderResponseError;

/**
 * Helper function to call template-parsing-engine from TypeScript
 * 
 * @param request - The render request
 * @returns Promise resolving to the render response
 */
export async function renderTemplate(request: RenderRequest): Promise<RenderResponse> {
  const { spawn } = await import('child_process');
  
  return new Promise((resolve, reject) => {
    const proc = spawn('uv', ['run', 'template-parsing-engine']);
    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (data: Buffer) => stdout += data.toString());
    proc.stderr.on('data', (data: Buffer) => stderr += data.toString());
    proc.on('close', (code: number | null) => {
      if (code !== 0) {
        reject(new Error(stderr || `Process exited with code ${code}`));
      } else {
        try {
          resolve(JSON.parse(stdout) as RenderResponse);
        } catch (e) {
          reject(new Error(`Failed to parse JSON response: ${stdout}`));
        }
      }
    });

    proc.stdin.write(JSON.stringify(request));
    proc.stdin.end();
  });
}

export default renderTemplate;
