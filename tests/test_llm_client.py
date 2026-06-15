import pytest
from unittest.mock import patch, MagicMock
from openai import APIStatusError
from backend.llm_client import LLMClient


def test_single_chat():
    client = LLMClient(base_url='http://fake', api_key='test', model='test-model')
    with patch('backend.llm_client.OpenAI') as mock_openai:
        mock_instance = MagicMock()
        mock_openai.return_value = mock_instance
        mock_instance.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content='Hello!'))]
        )

        result = client.chat([{'role': 'user', 'content': 'Hi'}])
        assert result == 'Hello!'
        mock_instance.chat.completions.create.assert_called_once()


def test_stream_chat():
    client = LLMClient(base_url='http://fake', api_key='test', model='test-model')
    with patch('backend.llm_client.OpenAI') as mock_openai:
        mock_instance = MagicMock()
        mock_openai.return_value = mock_instance
        mock_instance.chat.completions.create.return_value = [
            MagicMock(choices=[MagicMock(delta=MagicMock(content='Hello'))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content=' world'))]),
        ]

        chunks = list(client.chat_stream([{'role': 'user', 'content': 'Hi'}]))
        assert chunks == ['Hello', ' world']


def test_stream_chat_skips_empty_choices():
    client = LLMClient(base_url='http://fake', api_key='test', model='test-model')
    with patch('backend.llm_client.OpenAI') as mock_openai:
        mock_instance = MagicMock()
        mock_openai.return_value = mock_instance
        mock_instance.chat.completions.create.return_value = [
            MagicMock(choices=[]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content='Hello'))]),
            MagicMock(choices=[]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content=' world'))]),
        ]

        chunks = list(client.chat_stream([{'role': 'user', 'content': 'Hi'}]))
        assert chunks == ['Hello', ' world']


def test_single_chat_empty_choices_returns_empty_string():
    client = LLMClient(base_url='http://fake', api_key='test', model='test-model')
    with patch('backend.llm_client.OpenAI') as mock_openai:
        mock_instance = MagicMock()
        mock_openai.return_value = mock_instance
        mock_instance.chat.completions.create.return_value = MagicMock(choices=[])

        result = client.chat([{'role': 'user', 'content': 'Hi'}])
        assert result == ''


def test_multi_turn_chat():
    client = LLMClient(base_url='http://fake', api_key='test', model='test-model')
    with patch('backend.llm_client.OpenAI') as mock_openai:
        mock_instance = MagicMock()
        mock_openai.return_value = mock_instance
        mock_instance.chat.completions.create.side_effect = [
            MagicMock(choices=[MagicMock(message=MagicMock(content='Turn 1'))]),
            MagicMock(choices=[MagicMock(message=MagicMock(content='Turn 2'))]),
        ]

        messages = [{'role': 'user', 'content': 'Start'}]
        r1 = client.chat(messages)
        messages.append({'role': 'assistant', 'content': r1})
        r2 = client.chat(messages)

        assert r1 == 'Turn 1'
        assert r2 == 'Turn 2'


def test_retry_on_429():
    client = LLMClient(base_url='http://fake', api_key='test', model='test-model',
                       max_retries=2, retry_min_wait=0.01)
    with patch('backend.llm_client.OpenAI') as mock_openai:
        mock_instance = MagicMock()
        mock_openai.return_value = mock_instance

        err429 = APIStatusError('Rate limit', response=MagicMock(status_code=429), body=None)
        success = MagicMock(choices=[MagicMock(message=MagicMock(content='ok'))])

        mock_instance.chat.completions.create.side_effect = [err429, success]
        result = client.chat([{'role': 'user', 'content': 'Hi'}])
        assert result == 'ok'
        assert mock_instance.chat.completions.create.call_count == 2


def test_retry_on_5xx():
    client = LLMClient(base_url='http://fake', api_key='test', model='test-model',
                       max_retries=2, retry_min_wait=0.01)
    with patch('backend.llm_client.OpenAI') as mock_openai:
        mock_instance = MagicMock()
        mock_openai.return_value = mock_instance

        err502 = APIStatusError('Server error', response=MagicMock(status_code=502), body=None)
        success = MagicMock(choices=[MagicMock(message=MagicMock(content='ok'))])

        mock_instance.chat.completions.create.side_effect = [err502, err502, success]
        result = client.chat([{'role': 'user', 'content': 'Hi'}])
        assert result == 'ok'
        assert mock_instance.chat.completions.create.call_count == 3


def test_no_retry_on_401():
    client = LLMClient(base_url='http://fake', api_key='test', model='test-model',
                       max_retries=2, retry_min_wait=0.01)
    with patch('backend.llm_client.OpenAI') as mock_openai:
        mock_instance = MagicMock()
        mock_openai.return_value = mock_instance

        err401 = APIStatusError('Unauthorized', response=MagicMock(status_code=401), body=None)
        mock_instance.chat.completions.create.side_effect = err401

        with pytest.raises(APIStatusError):
            client.chat([{'role': 'user', 'content': 'Hi'}])
        assert mock_instance.chat.completions.create.call_count == 1


def test_retry_exhaustion():
    client = LLMClient(base_url='http://fake', api_key='test', model='test-model',
                       max_retries=1, retry_min_wait=0.01)
    with patch('backend.llm_client.OpenAI') as mock_openai:
        mock_instance = MagicMock()
        mock_openai.return_value = mock_instance

        err429 = APIStatusError('Rate limit', response=MagicMock(status_code=429), body=None)
        mock_instance.chat.completions.create.side_effect = err429

        with pytest.raises(APIStatusError):
            client.chat([{'role': 'user', 'content': 'Hi'}])
        assert mock_instance.chat.completions.create.call_count == 2
