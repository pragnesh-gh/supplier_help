import test from 'node:test';
import assert from 'node:assert/strict';
import { suggestShortlist } from '../web/approval.js';
import { renderSupplierRing } from '../web/supplier-ring.js';

const supplier = (score, index) => ({supplierID: `SUPP_${index}`, Total_Risk_Index: score});
test('suggestion keeps three, includes close alternatives, and caps at five', () => {
  assert.deepEqual(suggestShortlist([10, 12, 13, 17, 19, 20].map(supplier)), ['SUPP_0', 'SUPP_1', 'SUPP_2', 'SUPP_3']);
  assert.equal(suggestShortlist([10, 11, 12, 13, 14, 15].map(supplier)).length, 5);
  assert.equal(suggestShortlist([10, 11, 12, 18, 19].map(supplier)).length, 3);
  assert.deepEqual(suggestShortlist([null, undefined, NaN, 8].map(supplier)), ['SUPP_3']);
});

test('ring reports full counts while sampling and keeps unknown separate', () => {
  const rows = Array.from({length: 100}, (_, i) => ({...supplier(10, i), Total_Risk_Index_Level:'Low', 'Supplier Name':'Example <script>', 'Purchase Order Volume (EUR)':100}));
  rows.push({...supplier(null, 100), Total_Risk_Index_Level:'Low'});
  const html = renderSupplierRing({rows, regionLabel:'Doors'});
  assert.match(html, /101 suppliers/);
  assert.match(html, /7 of 100 scored(?: suppliers)? shown/);
  assert.match(html, /Discover 100 low risk suppliers/);
  assert.match(html, /Discover 1 unscored suppliers/);
  assert.equal((html.match(/data-ring-supplier=/g)||[]).length, 7);
  assert.ok(!html.includes('<script>'));
});
