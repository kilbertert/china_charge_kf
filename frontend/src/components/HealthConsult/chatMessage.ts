export type ChatMessageItem = {
  id: string
  role: 'user' | 'assistant'
  text?: string
  fileNames?: string[]
}

function generateId(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID()
  return 'id-' + Date.now() + '-' + Math.floor(Math.random() * 1e6)
}

export function newChatMessage(
  role: 'user' | 'assistant',
  payload: { text?: string; fileNames?: string[] },
): ChatMessageItem {
  return { id: generateId(), role, ...payload }
}
