export const COLORS = ['#315bdb', '#18a994', '#ef9b46', '#8158cb', '#db6482', '#5e7f90', '#a9b548']

export const PROVIDERS: Record<string, { label: string; model: string }> = {
  gemini: { label: 'Google Gemini', model: 'gemini-3.5-flash-lite' },
  groq: { label: 'Groq', model: 'openai/gpt-oss-20b' },
  cohere: { label: 'Cohere', model: 'command-a-plus-05-2026' },
  openrouter: { label: 'OpenRouter', model: 'xingchen-agi/xing4.0-29b-a4b:free' },
  anthropic: { label: 'Anthropic', model: 'claude-haiku-5-5' },
}
