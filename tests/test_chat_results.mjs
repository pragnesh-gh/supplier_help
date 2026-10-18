import test from 'node:test';
import assert from 'node:assert/strict';
import { renderAnswer, renderChart, renderCharts, renderSources } from '../web/chat-results.js';

test('inline references resolve only matching citations and never accept unsafe HTML or URLs', () => {
  const result = renderAnswer('<img src=x onerror=alert(1)> score [D1] [S1] [D2]', [
    {id:'D1',kind:'dataset',supplier_id:'SUPP_00001',column:'Total_Risk_Index'},
    {id:'S1',url:'javascript:alert(1)',title:'<script>'},
  ]);
  assert.match(result, /&lt;img/);
  assert.match(result, /data-citation="SUPP_00001"/);
  assert.match(result, /\[D2\]/);
  assert.doesNotMatch(result, /href="javascript:|<img|<script/);
});
test('dossier references target a saved report', () => {
  assert.match(renderAnswer('Three findings [E1]', [{id:'E1',kind:'dossier',run_id:'r-1'}]), /data-dossier="r-1"/);
});
test('grouped citations resolve each known source and preserve unknown references', () => {
  const result = renderAnswer('Evidence [S1, S2, S3]', [{id:'S1',url:'https://example.org/one'},{id:'S2',url:'https://example.org/two'}]);
  assert.match(result, /href="https:\/\/example.org\/one"/);
  assert.match(result, /href="https:\/\/example.org\/two"/);
  assert.match(result, /\[S3\]/);
  assert.equal(renderAnswer('Unknown [S4, S5]',[]),'Unknown [S4, S5]');
});
test('supplier chart labels retain source inspection and out-of-range exact scores survive', () => {
  assert.match(renderChart({type:'bar',points:[{label:'SUPP_00012',value:12}]},'bar'), /data-chart-label="SUPP_00012"/);
  const result = renderChart({type:'radar',axes:Array.from({length:6},()=>({label:'Risk'})),series:[{label:'A',values:[101,0,null,4,5,6]}]},'range');
  assert.match(result, /101 \(outside 0-100\)/);
  assert.doesNotMatch(result, /class="radar-shape/);
  assert.equal((result.match(/class="radar-dot/g)||[]).length,4);
});
test('bar chart preserves missing values and escapes model supplied labels', () => {
  const result = renderChart({type:'bar',points:[{label:'Unknown',value:null},{label:'<svg onload=x>',value:4}]},'one');
  assert.match(result, /Unknown/);
  assert.match(result, /&lt;svg onload=x&gt;/);
  assert.doesNotMatch(result, /NaN|Infinity|<svg onload/);
  assert.equal(renderChart({type:'html',html:'<script>'},'bad'), '');
  assert.equal(renderChart({type:'radar',axes:null,series:null},'bad'), '');
});
test('incomplete radar has no filled polygon and preserves exact unknown values', () => {
  const axes = ['Financial','Legal','Country','People','Operations','Reputation'].map(label=>({label}));
  const incomplete = renderChart({type:'radar',axes,series:[{label:'Supplier',values:[10,20,null,40,50,60]}]},'radar');
  assert.doesNotMatch(incomplete, /class="radar-shape/);
  assert.equal((incomplete.match(/class="radar-dot/g)||[]).length,5);
  assert.match(incomplete, /<td>Unknown<\/td>/);
  const complete = renderChart({type:'radar',axes,series:[{label:'Supplier',values:[10,20,30,40,50,60]}]},'radar');
  assert.match(complete, /class="radar-shape/);
});
test('multiple cards have unique persistent disclosure keys; malformed inputs are ignored', () => {
  const chart = {type:'bar',points:[{label:'A',value:2}]};
  const result = renderCharts({charts:[chart,null,chart]},'message-1');
  assert.match(result, /data-detail-key="message-1-0"/);
  assert.match(result, /data-detail-key="message-1-2"/);
  assert.equal(renderSources(null,'x'), '');
  assert.equal(renderChart({type:'bar',points:[null,{}]},'x'), '');
});
test('radar discloses visual cap and retains every supplier in exact values', () => {
  const result = renderChart({type:'radar', axes:Array.from({length:6},(_,i)=>({label:`Axis ${i}`})), series:Array.from({length:20},(_,i)=>({label:`Supplier ${i}`,values:[1,2,3,4,5,6]}))},'many');
  assert.match(result, /Showing 5 of 20 suppliers/);
  assert.match(result, /<th>Supplier 19<\/th>/);
  assert.equal((result.match(/class="radar-shape/g)||[]).length,5);
});
