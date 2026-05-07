import random
import time
from openai import OpenAI, APIStatusError, APITimeoutError, APIConnectionError


_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


class LLMClient:
    def __init__(self, base_url, api_key, model,
                 max_retries=3, retry_min_wait=1.0, retry_max_wait=10.0):
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.max_retries = max_retries
        self.retry_min_wait = retry_min_wait
        self.retry_max_wait = retry_max_wait
        self.client = None

    def _get_client(self):
        if self.client is None:
            self.client = OpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                max_retries=0,
            )
        return self.client

    def _backoff_delay(self, attempt):
        base = min(self.retry_max_wait, self.retry_min_wait * (2 ** attempt))
        return base * (0.5 + random.random() * 0.5)

    def _is_retryable(self, exc):
        if isinstance(exc, APIStatusError):
            return exc.status_code in _RETRYABLE_STATUSES
        if isinstance(exc, (APITimeoutError, APIConnectionError)):
            return True
        return False

    def _chat_impl(self, messages, max_tokens, temperature, stream):
        client = self._get_client()
        return client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=stream,
        )

    def chat(self, messages, max_tokens=4096, temperature=0.7):
        last_err = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self._chat_impl(messages, max_tokens, temperature, False)
                return resp.choices[0].message.content
            except (APIStatusError, APITimeoutError, APIConnectionError) as e:
                last_err = e
                if not self._is_retryable(e) or attempt >= self.max_retries:
                    raise
                delay = self._backoff_delay(attempt)
                time.sleep(delay)

        raise last_err

    def chat_stream(self, messages, max_tokens=4096, temperature=0.7):
        last_err = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self._chat_impl(messages, max_tokens, temperature, True)
                for chunk in resp:
                    content = chunk.choices[0].delta.content
                    if content:
                        yield content
                return
            except (APIStatusError, APITimeoutError, APIConnectionError) as e:
                last_err = e
                if not self._is_retryable(e) or attempt >= self.max_retries:
                    raise
                delay = self._backoff_delay(attempt)
                time.sleep(delay)

        raise last_err
