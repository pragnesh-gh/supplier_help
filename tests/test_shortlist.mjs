import test from 'node:test';
import assert from 'node:assert/strict';
import { suggestShortlist, cartAdd, cartRemove, quickRequest, CART_LIMIT, QUICK_DEFAULTS } from '../web/approval.js';
import { renderSupplierRing } from '../web/supplier-ring.js';

const supplier = (score, index) => ({supplierID: `SUPP_${index}`, Total_Risk_Index: score});
test('suggestion keeps three, includes close alternatives, and caps at five', () => {
  assert.deepEqual(suggestShortlist([10, 12, 13, 17, 19, 20].map(supplier)), ['SUPP_0', 'SUPP_1', 'SUPP_2', 'SUPP_3']);
  assert.equal(suggestShortlist([10, 11, 12, 13, 14, 15].map(supplier)).length, 5);
  assert.equal(suggestShortlist([10, 11, 12, 18, 19].map(supplier)).length, 3);
  assert.deepEqual(suggestShortlist([null, undefined, NaN, 8].map(supplier)), ['SUPP_3']);
});

test('shortlist cart adds, de-duplicates, removes and caps at the limit', () => {
  let {cart, status} = cartAdd([], 'SUPP_1');
  assert.deepEqual([cart, status], [['SUPP_1'], 'added']);
  ({cart, status} = cartAdd(cart, 'SUPP_1'));
  assert.deepEqual([cart, status], [['SUPP_1'], 'duplicate']);
  ({cart} = cartAdd(cart, 'SUPP_2'));
  assert.deepEqual(cartRemove(cart, 'SUPP_1'), ['SUPP_2']);
  assert.deepEqual(cart, ['SUPP_1', 'SUPP_2'], 'cart helpers do not mutate their input');
  const full = Array.from({length: CART_LIMIT}, (_, i) => `SUPP_${i}`);
  assert.equal(CART_LIMIT, 20);
  const over = cartAdd(full, 'SUPP_X');
  assert.equal(over.status, 'full');
  assert.equal(over.cart.length, 20);
  assert.equal(cartAdd(full, 'SUPP_0').status, 'duplicate');
});

test('one-click approval payload fills every backend-required field with defaults', () => {
  const body = quickRequest({ids: ['A', 'B', 'C'], scope: 'Doors', project: 'Shortlist · Doors'});
  assert.equal(body.requester, 'Demo buyer');
  assert.equal(body.reviewer, 'Sourcing lead');
  assert.equal(body.project, 'Shortlist · Doors');
  assert.equal(body.scope, 'Doors');
  assert.equal(body.rationale, 'Shortlist comparison of 3 candidates.');
  assert.deepEqual(body.candidates.map(c => c.supplier_id), ['A', 'B', 'C']);
  for (const c of body.candidates) {
    assert.equal(c.tradeoffs, QUICK_DEFAULTS.tradeoffs);
    assert.equal(c.negotiation_questions, QUICK_DEFAULTS.negotiation_questions);
  }
  for (const key of ['requester', 'reviewer', 'project', 'rationale']) assert.ok(body[key].trim());
  assert.match(quickRequest({ids: ['A', 'B', 'C', 'D'], note: '  Prefer EU '}).rationale, /4 candidates\. Note: Prefer EU$/);
  assert.equal(quickRequest({ids: ['A', 'B', 'C']}).project, 'Shortlist comparison');
  assert.throws(() => quickRequest({ids: ['A', 'B']}), /3 to 5/);
  assert.throws(() => quickRequest({ids: ['A', 'B', 'C', 'D', 'E', 'F']}), /3 to 5/);
  assert.throws(() => quickRequest({ids: ['A', 'A', 'B']}), /distinct/);
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
