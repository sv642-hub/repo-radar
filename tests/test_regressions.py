"""Regression coverage for live contracts, generated commands, and graph identity."""
import copy
import json
import shlex
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

import dashboard
import dashboard_github as github
import dashboard_graph as graph
import dashboard_page as page
import dashboard_watch as watch


def test_fetch_uses_cli_fields_and_enriches_relationships(monkeypatch):
    calls = []
    def gh(args):
        calls.append(args)
        if args[:2] == ['repo', 'view']:
            return {'nameWithOwner': 'o/r', 'url': 'https://github.com/o/r'}
        if args[:2] == ['api', 'graphql']:
            return {'data': {'nodes': [{'id': 'I_1', 'parent': {'number': 2, 'url': 'https://github.com/o/r/issues/2'}, 'blockedBy': {'nodes': []}}]}}
        if args[:2] == ['issue', 'list']:
            fields = args[args.index('--json') + 1].split(',')
            assert not {'parent', 'blockedBy'} & set(fields)
            return [{'id': 'I_1', 'number': 1}] if args[args.index('--state') + 1] == 'open' else []
        return []
    monkeypatch.setattr(github, '_gh', gh)
    data = github.fetch('o/r', 90, 500, set())
    assert data['open_issues'][0]['parent']['number'] == 2
    assert data['warnings'] == []
    assert any(c[:2] == ['api', 'graphql'] for c in calls)


def test_relationship_service_failure_keeps_lists(monkeypatch):
    def fail(_):
        raise RuntimeError('not available')
    monkeypatch.setattr(github, '_gh', fail)
    issues = [{'id': 'I_1', 'number': 1}]
    assert 'unavailable' in github.issue_relationships(issues)[0]
    assert issues == [{'id': 'I_1', 'number': 1}]


@pytest.mark.parametrize('key', [1, 'app/api'])
def test_invalid_group_is_isolated_and_next_repo_renders(key, demo_plan, demo_data):
    invalid = copy.deepcopy(demo_plan)
    old = next(iter(invalid['groups']))
    invalid['groups'][key] = invalid['groups'].pop(old)
    entries = watch.load_watch_list('repos: [o/bad, o/good]')
    pages, rows = watch.watch(entries, lambda repo, _: yaml.safe_dump(invalid if repo == 'o/bad' else demo_plan),
                              lambda *_: demo_data, page.render)
    assert 'group keys' in rows[0]['error']
    assert rows[1]['error'] is None
    assert set(pages) == {'o__good.html'}


def test_stack_requires_matching_repository():
    data = {'repo': 'o/r', 'open_issues': [], 'open_prs': [
        {'number': 1, 'headRefName': 'main', 'baseRefName': 'main',
         'headRepository': {'name': 'r'}, 'headRepositoryOwner': {'login': 'fork'}},
        {'number': 2, 'headRefName': 'feature', 'baseRefName': 'main'},
    ]}
    assert graph.edges(None, data) == []
    data['open_prs'][0].update(headRefName='base', headRepositoryOwner={'login': 'o'})
    data['open_prs'][1]['baseRefName'] = 'base'
    assert graph.edges(None, data) == [('pr:1', 'pr:2', 'stacked')]
    del data['open_prs'][0]['headRepositoryOwner']
    assert graph.edges(None, data) == []  # old snapshots cannot prove repository identity


@pytest.mark.parametrize('name', ['team plan.yaml', "team's plan.yaml", 'plan;echo nope.yaml', 'plan: final.yaml', 'plan #1.yaml'])
def test_generated_plan_argument_runs_with_shell_characters(tmp_path, name, demo_data):
    path = Path('docs') / name
    dashboard.init(tmp_path, path, True, '0 11 * * *', False)
    workflow = yaml.safe_load((tmp_path / dashboard.WORKFLOW).read_text())
    command = next(step['run'] for step in workflow['jobs']['build']['steps'] if 'build --out' in step.get('run', ''))
    args = shlex.split(command)[2:]
    assert args[args.index('--plan') + 1] == str(path)
    (tmp_path / 'data.json').write_text(json.dumps(demo_data))
    # Exercise the generated shell argument, using offline data and a temporary output.
    command = command.replace('python ', shlex.quote(sys.executable) + ' ', 1)
    command = command.replace('"$RUNNER_TEMP/index.html"', 'index.html') + ' --data data.json'
    result = subprocess.run(['bash', '-c', command], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / 'index.html').exists()


def test_html_has_accessible_tabs_and_visible_fetch_warning(demo_data):
    demo_data['warnings'] = ['Relationship links unavailable <retry>']
    html = page.render(demo_data, None)
    assert 'role="tablist"' in html and 'aria-controls="prs"' in html
    assert 'role="tabpanel" aria-labelledby="tab-prs"' in html
    assert 'Relationship links unavailable &lt;retry&gt;' in html
    assert 'id="no-results" role="status"' in html
