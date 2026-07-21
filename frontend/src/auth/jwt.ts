/**
 * Rein clientseitige, unverifizierte Ableitung des username-Claims aus dem JWT-Payload - nur
 * fuer die Anzeige "Angemeldet als {username}" in der Kopfzeile (siehe
 * specs/features/0006-auth.md). Keine Signaturpruefung, keine Ablaufpruefung: das ist nicht der
 * Ort fuer eine Sicherheitsentscheidung, nur fuer eine Nutzeranzeige.
 */
export function decodeUsername(token: string): string | null {
  const parts = token.split('.')
  if (parts.length !== 3) {
    return null
  }

  try {
    const payload: unknown = JSON.parse(atob(parts[1]))
    if (
      payload !== null &&
      typeof payload === 'object' &&
      'username' in payload &&
      typeof (payload as { username: unknown }).username === 'string'
    ) {
      return (payload as { username: string }).username
    }
  } catch {
    return null
  }

  return null
}
