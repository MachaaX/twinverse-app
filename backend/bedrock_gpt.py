"""GPT text requests through Bedrock's OpenAI-compatible Responses API.

Adapt the existing patient tools and input blocks to Responses, retaining the
generator's structured-result contract and grounding checks.
"""
import json
from types import SimpleNamespace


def is_gpt(model):
    return 'openai.' in model


def input_content(content):
    if isinstance(content, str):
        return content
    blocks = []
    for block in content:
        kind = block['type']
        if kind == 'text':
            blocks.append({'type': 'input_text', 'text': block['text']})
        elif kind in ('document', 'image'):
            source = block['source']
            data = f"data:{source['media_type']};base64,{source['data']}"
            if kind == 'document':
                blocks.append({'type': 'input_file', 'filename': block['title'], 'file_data': data})
            else:
                blocks.append({'type': 'input_image', 'image_url': data})
        else:
            raise ValueError('Unsupported generator input block')
    return blocks


def call(api, model, **kwargs):
    import openai
    from .generator import GeneratorError, ModelUnavailable, _detail
    request = {'model': model, 'temperature': 0, 'reasoning': {'effort': 'none'},
               'max_output_tokens': kwargs['max_tokens'], 'store': False,
               'input': [{'role': m['role'], 'content': input_content(m['content'])}
                         for m in kwargs['messages']]}
    if kwargs.get('system'):
        request['instructions'] = kwargs['system']
    tools = kwargs.get('tools') or []
    if tools:
        request['tools'] = [{'type': 'function', 'name': t['name'], 'description': t['description'],
                             'parameters': t['input_schema'], 'strict': False} for t in tools]
        request['tool_choice'] = {'type': 'function', 'name': tools[0]['name']}
        request['parallel_tool_calls'] = False
    try:
        response = api.responses.create(**request)
    except (openai.AuthenticationError, openai.PermissionDeniedError, openai.NotFoundError) as e:
        raise ModelUnavailable(f'{e.status_code} {_detail(e)}') from None
    except openai.RateLimitError:
        raise GeneratorError('Bedrock is rate limiting requests. Wait a minute and try again.') from None
    except openai.APIStatusError as e:
        if e.status_code == 400:
            raise ModelUnavailable(f'400 {_detail(e)}') from None
        raise GeneratorError(f'Bedrock returned an error ({e.status_code}): {_detail(e)}') from None
    except openai.APIConnectionError:
        raise GeneratorError('Could not reach Bedrock. Check the internet connection, or use the static example.') from None
    if response.status == 'incomplete':
        raise GeneratorError('The response was incomplete. Shorten the input and try again.')
    if response.status != 'completed':
        raise GeneratorError('Bedrock did not complete the response. Try again.')
    blocks = []
    for item in response.output:
        if item.type == 'message' and any(b.type == 'refusal' for b in item.content):
            return SimpleNamespace(stop_reason='refusal', content=[])
        if item.type == 'function_call':
            try:
                data = json.loads(item.arguments)
            except (ValueError, TypeError):
                raise GeneratorError('The model returned malformed tool data. Try again.') from None
            if not isinstance(data, dict):
                raise GeneratorError('The model returned malformed tool data. Try again.')
            blocks.append(SimpleNamespace(type='tool_use', name=item.name, input=data))
    return SimpleNamespace(stop_reason='tool_use' if blocks else 'end_turn', content=blocks)
