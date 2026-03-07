"""
llm.py
------
Simple LLM wrappers. Both take a prompt str, return a str.

Usage:
    llm = GeminiLLM(api_key="...")
    response = llm.answer("What do people think about the S24?")

    llm = BedrockLLM(aws_access_key="...", aws_secret_key="...", region="us-east-1")
    response = llm.answer("What do people think about the S24?")

Dependencies:
    pip install google-generativeai boto3
"""

import json
import re
import logging
import random
import os

from core.utils.logger import Logger, Verbosity
log = Logger(name=__name__, verbosity=Verbosity.TRACE)

# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------

class GeminiLLM:
    DEFAULT_MODEL = "gemini-2.5-flash"

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        self.model_name = model
        self.truncate_log = True 
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            self._model = genai.GenerativeModel(model)
            log.info(f"Succesfully Initialized GeminiLLM with model '{model}'")
        except ImportError:
            raise ImportError("pip install google-generativeai")

    def answer(self, prompt: str) -> str:
        try:
            log.trace(f"Gemini Prompt  : [green1]{self.prep_for_log(prompt)}[/]")
            response = self._model.generate_content(prompt)
            txt = response.text.strip()
            log.trace(f"Gemini Response: [magenta]{self.prep_for_log(txt)}[/]")
            return txt
        except Exception as exc:
            log.error(f"Gemini error: {exc}")
            raise

    def prep_for_log(self, text: str) -> str:
        if self.truncate_log and len(text) > 500:
            return text[:250] + " ... " + text[-250:]
        return text

# ---------------------------------------------------------------------------
# SUPER Gemini
# ---------------------------------------------------------------------------
class SuperGemini:
    DEFAULT_MODEL = "gemini-2.5-flash"

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        init_health_check: bool = True,
        api_key: str = None,
    ):
        self.model_name = model
        self.truncate_log = True 

        if api_key is not None:
            log.warn("Ignoring provided api_key — SuperGemini discovers all GEMINI* keys from environment variables")
        try:
            import google.generativeai as genai
            self._genai = genai
        except ImportError:
            raise ImportError("pip install google-generativeai")

        # --- discover keys ---
        self._healthy:   list[str] = []
        self._unhealthy: list[str] = []

        discovered = self._discover_keys()
        if not discovered:
            raise ValueError(
                "No Gemini API keys found. Set GEMINI, GEMINI1, GEMINI2, ... in your .env"
            )
        log.info(f"Discovered [cyan]{len(discovered)}[/cyan] Gemini key(s)")

        if init_health_check:
            self._run_health_checks(discovered)
        else:
            self._healthy = discovered
            log.info(f"Skipping health check — assuming all [cyan]{len(discovered)}[/cyan] keys healthy")

        if not self._healthy:
            raise RuntimeError("No healthy Gemini API keys found after health check")

        log.info(f"[bold green]{len(self._healthy)}[/bold green] healthy key(s) ready")

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def answer(self, prompt: str) -> str:
        if not self._healthy:
            raise RuntimeError("No healthy Gemini API keys remaining")

        key = random.choice(self._healthy)
        log.trace(f"Using key [...{key[-6:]}]")
        log.trace(f"Prompt: [green1]{self.prep_for_log(prompt)}[/]")

        try:
            self._genai.configure(api_key=key)
            model   = self._genai.GenerativeModel(self.model_name)
            response = model.generate_content(prompt)
            txt = response.text.strip()
            log.trace(f"Response: [magenta]{self.prep_for_log(txt)}[/]")
            return txt

        except Exception as exc:
            log.error(f"Key [...{key[-6:]}] failed: {exc} — marking unhealthy")
            self._mark_unhealthy(key)
            raise

    @property
    def healthy_count(self) -> int:
        return len(self._healthy)

    @property
    def unhealthy_count(self) -> int:
        return len(self._unhealthy)

    # ------------------------------------------------------------------
    # Key discovery
    # ------------------------------------------------------------------

    def prep_for_log(self, text: str) -> str:
        if self.truncate_log and len(text) > 500:
            return text[:250] + " ... " + text[-250:]
        return text
    
    def _discover_keys(self) -> list[str]:
        """
        Finds all env vars matching: GEMINI, GEMINI1, GEMINI2, GEMINI_1, GEMINI_2 ...
        Returns unique non-empty values.
        """
        pattern = re.compile(r'^GEMINI\d*$|^GEMINI_\d+$', re.IGNORECASE)
        seen    = set()
        keys    = []

        for var, val in os.environ.items():
            if pattern.match(var) and val.strip():
                if val not in seen:
                    seen.add(val)
                    keys.append(val.strip())
                    log.debug(f"  Found key via {var} [...{val.strip()[-6:]}]")

        return keys

    # ------------------------------------------------------------------
    # Health checks
    # ------------------------------------------------------------------

    def _run_health_checks(self, keys: list[str]) -> None:
        log.debug(f"Running health checks on [cyan]{len(keys)}[/cyan] key(s)...")
        for key in keys:
            if self._is_healthy(key):
                self._healthy.append(key)
                log.debug(f"  [...{key[-6:]}] [bold green]healthy[/bold green]")
            else:
                self._unhealthy.append(key)
                log.warn(f"  [...{key[-6:]}] [bold orange3]unhealthy[/bold orange3]")

    def _is_healthy(self, key: str) -> bool:
        try:
            self._genai.configure(api_key=key)
            model = self._genai.GenerativeModel(self.model_name)
            model.generate_content("hi")
            return True
        except Exception as exc:
            log.debug(f"  Health check failed for [...{key[-6:]}]: {exc}")
            return False

    def _mark_unhealthy(self, key: str) -> None:
        if key in self._healthy:
            self._healthy.remove(key)
            self._unhealthy.append(key)
            log.warn(
                f"Key [...{key[-6:]}] moved to unhealthy. "
                f"[cyan]{len(self._healthy)}[/cyan] key(s) remaining"
            )

# ---------------------------------------------------------------------------
# AWS Bedrock
# ---------------------------------------------------------------------------

class BedrockLLM:
    DEFAULT_MODEL = "amazon.titan-text-express-v1"

    def __init__(
        self,
        aws_access_key: str,
        aws_secret_key: str,
        region: str = "us-east-1",
        model: str = DEFAULT_MODEL,
    ):
        self.model_id = model
        try:
            import boto3, json
            self._json = json
            self._client = boto3.client(
                "bedrock-runtime",
                region_name=region,
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key,
            )
        except ImportError:
            raise ImportError("pip install boto3")

    def answer(self, prompt: str) -> str:
        try:
            body = self._json.dumps({
                "inputText": prompt,
                "textGenerationConfig": {
                    "maxTokenCount": 2048,
                    "temperature": 0.7,
                }
            })
            response = self._client.invoke_model(
                modelId=self.model_id,
                body=body,
                contentType="application/json",
                accept="application/json",
            )
            result = self._json.loads(response["body"].read())
            return result["results"][0]["outputText"].strip()
        except Exception as exc:
            log.error(f"Bedrock error: {exc}")
            raise


class BedrockWithGeminiFallback:
    """Primary: Bedrock. Fallback: Gemini if Bedrock fails."""
    
    def __init__(
        self,
        aws_access_key: str,
        aws_secret_key: str,
        bedrock_region: str = "us-east-1",
        bedrock_model: str = "amazon.titan-text-express-v1",
    ):
        self._bedrock_available = False
        self._gemini_available = False
        self._active_provider = None
        
        try:
            self._bedrock = BedrockLLM(
                aws_access_key=aws_access_key,
                aws_secret_key=aws_secret_key,
                region=bedrock_region,
                model=bedrock_model,
            )
            self._bedrock_available = True
            self._active_provider = "bedrock"
        except Exception as exc:
            log.warn(f"Bedrock unavailable: {exc}")
        
        try:
            self._gemini = SuperGemini(init_health_check=True)
            self._gemini_available = True
            if not self._bedrock_available:
                self._active_provider = "gemini"
        except Exception as exc:
            log.warn(f"Gemini unavailable: {exc}")
        
        if not self._bedrock_available and not self._gemini_available:
            raise RuntimeError("No LLM providers available")
    
    def answer(self, prompt: str) -> str:
        """Try Bedrock first, fall back to Gemini if needed."""
        if self._bedrock_available:
            try:
                response = self._bedrock.answer(prompt)
                self._active_provider = "bedrock"
                return response
            except Exception as exc:
                log.warn(f"Bedrock failed, trying Gemini: {exc}")
                self._bedrock_available = False
        
        if self._gemini_available:
            try:
                response = self._gemini.answer(prompt)
                self._active_provider = "gemini"
                return response
            except Exception as exc:
                raise RuntimeError(f"Both providers failed: {exc}")
        
        raise RuntimeError("No LLM providers available")
    
    @property
    def active_provider(self) -> str:
        return self._active_provider


def get_parsed_response(llm, query):
        """Get a parsed response from the LLM using the provided parser."""
        try:
            raw_response = llm.answer(query)
            json = parse_llm_json(raw_response)
            return json
        except Exception as e:
            log.error(f"LLM error during generation: {e}")
            return None
        
"""
parse_json.py
-------------
Robust JSON parser for LLM-generated text.

Handles:
  - ```json ... ``` and ``` ... ``` code fences
  - Leading / trailing prose around the JSON
  - Newlines, extra spaces, weird indentation
  - Single quotes instead of double quotes
  - Trailing commas  (e.g.  {"a": 1,} or [1, 2, 3,])
  - Python literals: True/False/None → true/false/null

Usage:
    from parse_json import parse_llm_json

    result = parse_llm_json(llm_response)   # returns dict | list
    # raises ValueError if nothing parseable found
"""

def parse_llm_json(text: str) -> dict | list:
    """
    Parse JSON from an LLM response string.
    Returns a dict or list.
    Raises ValueError if no valid JSON can be extracted.
    """
    if not text or not text.strip():
        raise ValueError("Empty response")

    strategies = [
        _try_direct,
        _try_strip_fence,
        _try_extract_braces,
        _try_extract_brackets,
        _try_clean_and_parse,
    ]

    last_exc = None
    for strategy in strategies:
        try:
            result = strategy(text)
            if result is not None:
                return result
        except Exception as exc:
            last_exc = exc
            continue

    raise ValueError(
        f"Could not extract valid JSON from LLM response.\n"
        f"Last error: {last_exc}\n"
        f"Response preview: {text[:200]!r}"
    )


# ---------------------------------------------------------------------------
# Strategies — tried in order, first win returns
# ---------------------------------------------------------------------------

def _try_direct(text: str):
    """Maybe it's already clean JSON."""
    return json.loads(text.strip())


def _try_strip_fence(text: str):
    """Strip ```json ... ``` or ``` ... ``` code fences."""
    # greedy match between fences
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if match:
        return json.loads(match.group(1).strip())
    return None


def _try_extract_braces(text: str):
    """Find the outermost { ... } block and parse it."""
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start:end + 1])
    return None


def _try_extract_brackets(text: str):
    """Find the outermost [ ... ] block and parse it."""
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start:end + 1])
    return None


def _try_clean_and_parse(text: str):
    """
    Aggressive cleaning pass — handles the messy stuff:
      - Python literals (True/False/None)
      - Single-quoted strings
      - Trailing commas before } or ]
    Then tries brace/bracket extraction again.
    """
    cleaned = _clean(text)

    # try the whole cleaned string
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # try extracting braces/brackets from the cleaned string
    for extractor in (_try_extract_braces, _try_extract_brackets):
        try:
            result = extractor(cleaned)
            if result is not None:
                return result
        except Exception:
            continue

    return None


# ---------------------------------------------------------------------------
# Cleaning helpers
# ---------------------------------------------------------------------------

def _clean(text: str) -> str:
    # strip code fences if present
    text = re.sub(r"```(?:json)?", "", text, flags=re.IGNORECASE)
    text = text.replace("```", "")

    # Python literals → JSON literals
    text = re.sub(r'\bTrue\b',  'true',  text)
    text = re.sub(r'\bFalse\b', 'false', text)
    text = re.sub(r'\bNone\b',  'null',  text)

    # trailing commas before } or ]
    text = re.sub(r",\s*(\})", r"\1", text)
    text = re.sub(r",\s*(\])", r"\1", text)

    # single-quoted strings → double-quoted
    # careful: only replace quotes that are acting as string delimiters
    text = _single_to_double_quotes(text)

    return text.strip()


def _single_to_double_quotes(text: str) -> str:
    """
    Best-effort conversion of single-quoted JSON strings to double-quoted.
    Handles escaped single quotes inside strings.
    Not perfect for all edge cases but covers 95% of LLM output.
    """
    result = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "'" :
            # start of a single-quoted string — find its end
            result.append('"')
            i += 1
            while i < len(text):
                c = text[i]
                if c == "\\":
                    # escaped char — pass through
                    result.append(c)
                    i += 1
                    if i < len(text):
                        result.append(text[i])
                        i += 1
                elif c == "'":
                    result.append('"')
                    i += 1
                    break
                elif c == '"':
                    # escape any double quotes inside the string
                    result.append('\\"')
                    i += 1
                else:
                    result.append(c)
                    i += 1
        else:
            result.append(ch)
            i += 1
    return "".join(result)
        