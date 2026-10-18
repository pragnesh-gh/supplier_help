// Keep answers, chart payloads and their citations together when bounding history.
export function boundedChatHistory(input) {
  const messages = input.slice(-199);
  let removed = input.length > messages.length;
  const notice = {
    role: 'assistant',
    answer: 'Earlier conversation turns were omitted from saved history to keep workspace storage bounded.',
  };
  const bytes = value => new TextEncoder().encode(JSON.stringify(value)).length;
  while (messages.length && bytes([notice, ...messages]) > 95000) {
    messages.shift();
    removed = true;
  }
  return removed ? [notice, ...messages] : messages;
}
