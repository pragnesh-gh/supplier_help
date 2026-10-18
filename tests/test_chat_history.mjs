import test from 'node:test';
import assert from 'node:assert/strict';
import { boundedChatHistory } from '../web/chat-history.js';

test('a 20-supplier radar retains all source references when saved', () => {
  const citations = Array.from({length:120}, (_,i) => ({id:`D${i+1}`, value:i}));
  const message = {role:'assistant', answer:'Evidence [D120]', citations,
    chart:{type:'radar',series:[{label:'Supplier',values:[null,1,2,3,4,5],citation_ids:['D120']} ]}};
  assert.deepEqual(boundedChatHistory([message]), [message]);
});

test('byte limit drops whole messages and preserves newer grounded answers', () => {
  const last = {role:'assistant', answer:'Value 7 [D1]',citations:[{id:'D1',value:7}]};
  const result = boundedChatHistory([{role:'assistant',answer:'界'.repeat(40000)},last]);
  assert.equal(result.length,2);
  assert.match(result[0].answer,/omitted/);
  assert.deepEqual(result[1],last);
  assert.ok(new TextEncoder().encode(JSON.stringify(result)).length <= 95000);
});
