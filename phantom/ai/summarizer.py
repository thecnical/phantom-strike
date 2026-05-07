"""
ConversationSummarizer — auto-compresses AI conversation history when context
approaches token limits, preserving the last 10 messages verbatim.

Requirements: 12.1–12.6
"""

from typing import List, Dict, Tuple


def estimate_tokens(messages: List[Dict]) -> int:
    """
    Rough token estimate: total character count of all message content divided by 4.

    Each message must be a dict with at least a "content" key.

    Requirements: 12.5
    """
    return sum(len(m["content"]) for m in messages) // 4


class ConversationSummarizer:
    """
    Auto-compresses AI conversation history when the estimated token count
    reaches or exceeds the configured threshold.

    The last 10 messages are always preserved verbatim; older messages are
    summarised into a single system message via the AI engine.

    Requirements: 12.1–12.6
    """

    def __init__(self, ai_engine=None, token_threshold: int = 4000):
        """
        Parameters
        ----------
        ai_engine:
            An AI engine instance used to generate the summary.  May be None;
            when None (or when the engine raises), compression is skipped
            gracefully.
        token_threshold:
            Estimated token count at or above which compression is attempted.
            Defaults to 4000.
        """
        self.ai_engine = ai_engine
        self.token_threshold = token_threshold

    def estimate_tokens(self, messages: List[Dict]) -> int:
        """Delegate to the module-level helper for convenience."""
        return estimate_tokens(messages)

    def maybe_compress(
        self, messages: List[Dict]
    ) -> Tuple[List[Dict], bool]:
        """
        Compress the conversation history if the estimated token count is at or
        above the threshold AND there are more than 10 messages.

        Returns
        -------
        (result_messages, compressed)
            result_messages — the (possibly compressed) message list
            compressed      — True if compression was performed, False otherwise

        Behaviour
        ---------
        * If ``estimate_tokens(messages) < token_threshold``:
            return (messages, False)                          [Req 12.1]
        * If ``len(messages) <= 10``:
            return (messages, False)                          [Req 12.2]
        * Otherwise (compression needed):
            - Summarise all messages except the last 10 via AI [Req 12.3]
            - Preserve the last 10 verbatim and in order       [Req 12.4]
            - If AI is unavailable or raises: return (messages, False) [Req 12.6]
        """
        # Requirement 12.1 — below threshold: no compression
        if estimate_tokens(messages) < self.token_threshold:
            return (messages, False)

        # Requirement 12.2 — 10 or fewer messages: no compression regardless
        if len(messages) <= 10:
            return (messages, False)

        # Compression is needed
        last_10 = messages[-10:]
        older = messages[:-10]

        # Requirement 12.6 — AI unavailable: graceful fallback
        if self.ai_engine is None:
            return (messages, False)

        try:
            summary = self._summarize_via_ai(older)
        except Exception:
            # Requirement 12.6 — any AI error: graceful fallback
            return (messages, False)

        summary_message: Dict = {
            "role": "system",
            "content": f"Previous conversation summary: {summary}",
        }

        # Requirement 12.3 & 12.4 — [summary] + last 10 verbatim in order
        return ([summary_message] + last_10, True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _summarize_via_ai(self, messages: List[Dict]) -> str:
        """
        Ask the AI engine to produce a concise summary of *messages*.

        The engine is called with a minimal prompt list so that the summariser
        itself does not consume excessive tokens.

        Raises whatever the AI engine raises — callers must handle exceptions.
        """
        prompt = (
            "Summarise the following conversation history concisely, "
            "preserving all important facts, findings, and decisions:\n\n"
            + "\n".join(
                f"[{m.get('role', 'unknown')}]: {m.get('content', '')}"
                for m in messages
            )
        )

        # Support both sync and async-style engines that expose a simple
        # chat/complete interface.  We try the most common patterns.
        if hasattr(self.ai_engine, "chat"):
            response = self.ai_engine.chat(
                [{"role": "user", "content": prompt}]
            )
        elif hasattr(self.ai_engine, "complete"):
            response = self.ai_engine.complete(prompt)
        elif callable(self.ai_engine):
            response = self.ai_engine(prompt)
        else:
            raise RuntimeError("AI engine has no recognised interface")

        # Normalise: some engines return a string, others a dict
        if isinstance(response, str):
            return response
        if isinstance(response, dict):
            # OpenAI-style response
            return (
                response.get("content")
                or response.get("text")
                or response.get("message", {}).get("content", "")
                or str(response)
            )
        return str(response)
