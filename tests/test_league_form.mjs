import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';

const source = await readFile(new URL('../js/squad-stats.js', import.meta.url), 'utf8');
const styles = await readFile(new URL('../css/components.css', import.meta.url), 'utf8');

function harness() {
    const elements = new Map([
        ['leagueTablesFormToggle', { checked: false }],
        ['leagueTablesFormControl', {}],
        ['leagueTablesFormStatus', {}],
    ]);
    const cells = [
        { tagName: 'TH' },
        { tagName: 'TD', dataset: { squad: '1st', team: 'Club A' } },
        { tagName: 'TD', dataset: { squad: '2nd', team: 'Club A' } },
    ];
    const errors = [];
    const context = vm.createContext({
        document: {
            addEventListener() {},
            getElementById: id => elements.get(id),
            querySelectorAll: () => cells,
        },
        console: { error: (...args) => errors.push(args) },
        Date,
        getCurrentSeasonLabel: () => '2026/27',
        escapeHtml: value => String(value).replace(/[&<>"']/g, char => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
        })[char]),
    });
    vm.runInContext(source, context);
    context._ltGetCurrentSeason = () => '2026/27';
    return { context, elements, cells, errors };
}

function game(overrides = {}) {
    return {
        match_id: 'one', season: '2026/27', tracked_squad: '1st', date: '2026-09-01',
        home_team: 'Club A', away_team: 'Club B', home_score: 10, away_score: 7,
        home_walkover: false, away_walkover: false, ...overrides,
    };
}

test('form keeps the last five completed results oldest to newest, for both teams', () => {
    const { context } = harness();
    const games = Array.from({ length: 7 }, (_, index) => game({
        match_id: String(index), date: `2026-09-0${index + 1}`,
        home_score: [10, 10, 0, 7, 5, 0, 12][index],
        away_score: [7, 7, 0, 10, 0, 9, 3][index],
    })).reverse();
    const before = JSON.stringify(games);
    const form = context._ltBuildFormMap(games, '2026/27', '2026-11-02');
    assert.equal(form.get('1st:Club A').map(row => row.result).join(''), 'DLWLW');
    assert.equal(form.get('1st:Club B').map(row => row.result).join(''), 'DWLWL');
    assert.equal(form.get('1st:Club A').at(-1).date, '2026-09-07');
    assert.equal(JSON.stringify(games), before);
});

test('form ignores future, unscored and other-season games; deduplicates and isolates squads', () => {
    const { context } = harness();
    const games = [
        game(), game(),
        game({ match_id: 'future', date: '2026-11-03' }),
        game({ match_id: 'missing', home_score: null }),
        game({ match_id: 'strings', home_score: '', away_score: '' }),
        game({ match_id: 'old', season: '2025/26' }),
        game({ match_id: 'undated', date: null }),
        game({ tracked_squad: '2nd', home_score: 0, away_score: 7 }),
    ];
    const form = context._ltBuildFormMap(games, '2026/27', '2026-11-02');
    assert.equal(form.get('1st:Club A').length, 1);
    assert.equal(form.get('2nd:Club A')[0].result, 'L');
});

test('awarded walkovers have correct results and subtle WO labels without outlines', () => {
    const { context } = harness();
    const form = context._ltBuildFormMap([
        game({ home_score: null, away_score: null, home_walkover: true }),
        game({ match_id: 'two', date: '2026-09-02', home_score: null, away_score: null, away_walkover: true }),
    ], '2026/27', '2026-11-02');
    assert.equal(form.get('1st:Club A').map(row => row.result).join(''), 'WL');
    assert.equal(form.get('1st:Club B').map(row => row.result).join(''), 'LW');
    const html = context._ltRenderFormSquares(form.get('1st:Club A'));
    assert.equal((html.match(/league-form-square--walkover/g) || []).length, 2);
    assert.equal((html.match(/>WO</g) || []).length, 2);
    assert.match(html, /Win by walkover/);
    assert.match(html, /Loss by walkover/);
    const rule = styles.match(/\.league-form-square--walkover\s*\{([^}]+)\}/)[1];
    assert.match(rule, /font-size:\s*8px/);
    assert.match(rule, /font-weight:\s*400/);
    assert.doesNotMatch(rule, /outline|border/);
});

test('fewer than five results are right-aligned with blank spaces and accessible descriptions', () => {
    const { context } = harness();
    const html = context._ltRenderFormSquares([
        { result: 'D', date: '2026-09-01', opposition: 'Club "B" <II>', walkover: false },
    ]);
    assert.equal((html.match(/league-form-square--empty/g) || []).length, 4);
    assert.ok(html.indexOf('league-form-square--empty') < html.indexOf('league-form-square--D'));
    assert.match(html, /role="img" aria-label="Draw vs Club &quot;B&quot; &lt;II&gt;/);
    assert.equal((context._ltRenderFormSquares([]).match(/league-form-square--empty/g) || []).length, 5);
    const rule = styles.match(/\.league-form-square--empty\s*\{([^}]+)\}/)[1];
    assert.match(rule, /visibility:\s*hidden/);
    assert.doesNotMatch(rule, /background|border/);
});

test('toggle is off by default, only reveals current-season form, and caches the fetch', async () => {
    const { context, elements, cells } = harness();
    let fetches = 0;
    context.fetch = async () => {
        fetches += 1;
        return { ok: true, json: async () => [game()] };
    };
    await context._ltUpdateFormColumns();
    assert.equal(fetches, 0);
    assert.ok(cells.every(cell => cell.hidden));
    elements.get('leagueTablesFormToggle').checked = true;
    await context._ltUpdateFormColumns();
    assert.equal(fetches, 1);
    assert.ok(cells.every(cell => !cell.hidden));
    assert.match(cells[1].innerHTML, /league-form-square--W/);
    assert.match(cells[2].innerHTML, /No league results available/);
    await context._ltUpdateFormColumns();
    assert.equal(fetches, 1);
    context._ltGetCurrentSeason = () => '2024/25';
    await context._ltUpdateFormColumns();
    assert.equal(elements.get('leagueTablesFormControl').hidden, true);
    assert.ok(cells.every(cell => cell.hidden));
    context._ltGetCurrentSeason = () => '2026/27';
    await context._ltUpdateFormColumns();
    assert.equal(elements.get('leagueTablesFormControl').hidden, false);
    assert.ok(cells.every(cell => !cell.hidden));
});

test('failed loads surface an error and can be retried', async () => {
    const { context, elements, cells, errors } = harness();
    elements.get('leagueTablesFormToggle').checked = true;
    context.fetch = async () => ({ ok: false, status: 503 });
    await context._ltUpdateFormColumns();
    assert.equal(errors.length, 1);
    assert.equal(elements.get('leagueTablesFormStatus').hidden, false);
    assert.match(elements.get('leagueTablesFormStatus').textContent, /Unable to load league form/);
    assert.ok(cells.every(cell => cell.hidden));
    context.fetch = async () => ({ ok: true, json: async () => [game()] });
    await context._ltUpdateFormColumns();
    assert.equal(elements.get('leagueTablesFormStatus').hidden, true);
    assert.ok(cells.every(cell => !cell.hidden));
});

test('switching to a historical season during a load does not reveal form there', async () => {
    const { context, elements, cells } = harness();
    elements.get('leagueTablesFormToggle').checked = true;
    let finish;
    context.fetch = () => new Promise(resolve => { finish = resolve; });
    const loading = context._ltUpdateFormColumns();
    context._ltGetCurrentSeason = () => '2024/25';
    await context._ltUpdateFormColumns();
    finish({ ok: true, json: async () => [game()] });
    await loading;
    assert.ok(cells.every(cell => cell.hidden));
    assert.equal(elements.get('leagueTablesFormControl').hidden, true);
    assert.equal(elements.get('leagueTablesFormStatus').hidden, true);
});
