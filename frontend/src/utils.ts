export function splitQuestionCodes(value: string): string[] {
  return value.split(/[,\n]+/).map((code) => code.trim()).filter((code) => code && code !== '0')
}
