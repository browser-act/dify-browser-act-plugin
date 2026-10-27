import json

import pytest

from tools.run_my_bot import RunMyBotTool
from tools.run_official_template import RunOfficialTemplateTool


@pytest.mark.parametrize('cls,target,path', [
    (RunMyBotTool, 'bot_id', '/v3/bots/1'),
    (RunOfficialTemplateTool, 'template_id', '/v3/bots/templates/1'),
])
@pytest.mark.parametrize('mode', [{}, {'operation': 'run'}])
def test_default_or_explicit_run_submits_once_and_emits_named_outputs(http_api, cls, target, path, mode):
    reply, calls = http_api
    reply({target: '1', 'published_at': 'now', 'input_schema': {'properties': {'q': {'default': 'default'}}}})
    reply({'task_id': '10'})
    reply({'task_id': '10', 'status': 'finished'})
    detail = {'task_id': '10', 'status': 'finished', 'output': ['done']}
    reply(detail)
    messages = list(cls.from_credentials({'api_key': 'unit-test-key'}).invoke({target: '1', **mode}))
    assert messages[0].message.json_object == detail
    variables = {m.message.variable_name: m.message.variable_value for m in messages if m.type.value == 'variable'}
    assert variables['task_id'] == '10' and variables['output'] == ['done']
    assert [(c['method'], c['url']) for c in calls] == [
        ('GET', 'https://api.browseract.com' + path),
        ('POST', 'https://api.browseract.com' + path + '/runs'),
        ('GET', 'https://api.browseract.com/v3/bots/runs/10/status'),
        ('GET', 'https://api.browseract.com/v3/bots/runs/10'),
    ]
    assert json.loads(calls[1]['body']) == {'input': {'q': 'default'}}


@pytest.mark.parametrize('legacy_region', [None, '', 'US'])
def test_template_ignores_legacy_proxy_setting_but_preserves_business_input(http_api, legacy_region):
    reply, calls = http_api
    reply({'template_id': '1', 'input_schema': {}})
    reply({'task_id': '10'})
    reply({'task_id': '10', 'status': 'finished'})
    reply({'task_id': '10', 'status': 'finished'})
    list(RunOfficialTemplateTool.from_credentials({'api_key': 'unit-test-key'}).invoke({
        'template_id': '1', 'proxy_region': legacy_region,
        'input_json': '{"proxy_region":"business-value"}',
    }))
    assert len(calls) == 4
    assert json.loads(calls[1]['body']) == {'input': {'proxy_region': 'business-value'}}
    assert not any('/regions' in c['url'] for c in calls)


def test_removed_region_option_hook_does_not_query_api(http_api):
    _, calls = http_api
    with pytest.raises(ValueError, match='Unsupported'):
        RunOfficialTemplateTool.from_credentials({'api_key': 'unit-test-key'}).fetch_parameter_options('proxy_region')
    assert calls == []
