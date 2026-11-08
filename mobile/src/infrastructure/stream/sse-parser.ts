export type SseMessage = { event: string; data: string }

/**
 * Incremental Server-Sent Events parser. Feed it text chunks; it returns the messages completed
 * by each chunk and keeps a partial trailing message for the next call.
 */
export function makeSseParser() {
  let buffer = ''
  return (chunk: string): SseMessage[] => {
    buffer += chunk.replace(/\r\n?/g, '\n')
    const blocks = buffer.split('\n\n')
    buffer = blocks.pop() ?? ''
    const messages: SseMessage[] = []
    for (const block of blocks) {
      let event = 'message'
      const data: string[] = []
      for (const line of block.split('\n')) {
        if (line === '' || line.startsWith(':')) continue
        const colon = line.indexOf(':')
        const field = colon === -1 ? line : line.slice(0, colon)
        const value = colon === -1 ? '' : line.slice(colon + 1).replace(/^ /, '')
        if (field === 'event') event = value
        else if (field === 'data') data.push(value)
      }
      if (data.length) messages.push({ event, data: data.join('\n') })
    }
    return messages
  }
}
