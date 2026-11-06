"""OpenAI-based news summarization for Bilaspur News Intelligence."""

import os
import logging

logger = logging.getLogger(__name__)


def summarize_items(items: list) -> list:
    """Summarize news items using OpenAI API.

    If OpenAI API key is not configured, returns items unchanged.
    """
    api_key = os.environ.get("OPENCODE_API_KEY") or os.environ.get("OPENAI_API_KEY")

    if not api_key:
        logger.warning("OpenAI API key not configured, skipping summarization")
        return items

    try:
        import openai

        client = openai.OpenAI(api_key=api_key)

        for item in items:
            if not item.summary or len(item.summary) < 20:
                try:
                    response = client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": "Summarize this news item in 2-3 sentences in Hindi/English mix (Hinglish) for Bilaspur, Chhattisgarh readers. Keep it concise and factual."},
                            {"role": "user", "content": f"Title: {item.title}\nContent: {item.summary or item.title}\nSource: {item.source}"}
                        ],
                        max_tokens=100,
                        temperature=0.3,
                    )
                    item.summary = response.choices[0].message.content.strip()
                except Exception as e:
                    logger.warning(f"Failed to summarize item: {e}")
                    item.summary = item.summary or item.title

    except ImportError:
        logger.warning("openai package not installed, skipping summarization")
    except Exception as e:
        logger.error(f"Summarization error: {e}")

    return items
