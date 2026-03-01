from core.chains.llm import GeminiLLM, get_parsed_response
import json

def get_prethinking(llm, query: str) -> list[str]:
    example = {
        "thinking": "To generate effective search queries for reviews, I need to consider the product name and common review-related keywords. I should also think about different aspects of the product that users might be interested in, such as performance, durability, customer service, etc. The queries should be concise and focused on eliciting relevant reviews from platforms like Reddit, Twitter, and Google.",
        "queries": [
            "iPhone 15 performance reviews",
            "iPhone 15 durability feedback",
            "iPhone 15 user experience",
            "iPhone 15 vs iPhone 14 reviews",
            "iPhone 15 battery life reviews",
            "iPhone 15 camera quality feedback",
            "iPhone 15 customer service reviews"
        ]
    }
    prompt = f"""
    For the following product name, generate a list of 7 search queries that the user would like to searrch reddit/twitter/google reviews for.
    Example Input: "iPhone 15"
    Example Output: {example}
    Now generate the queries for this product:
    Input: "{query}"
    Output:
    """
    return get_parsed_response(llm, prompt)

#===========================================================================
#  GENERATE FINAL REPORT
#===========================================================================

def get_report(llm, product: str, comments: list[dict]) -> dict:
    """
    comments: [{"idx": "r1", "comments": ["text", ...]}, ...]
    Returns the full report dict matching the agreed frontend format.
    The caller merges url_map into the SSE event.
    """

    example_output = {
        "product": "Samsung Galaxy S26",
        "summary": {
            "verdict": "A performance-focused flagship with standout display quality, but mixed feedback on battery efficiency and thermals.",
            "confidence_score": 0.84
        },
        "sections": [
            {
                "title": "Performance & Thermals",
                "sentiment": "mixed",
                "paragraphs": [
                    {
                        "text": "Users consistently praise the Galaxy S26 for smooth performance and fast app launches. However, several discussions mention noticeable heating during extended gaming sessions.",
                        "references": ["r1", "r2", "t1"]
                    }
                ]
            },
            {
                "title": "Battery Life",
                "sentiment": "mixed",
                "paragraphs": [
                    {
                        "text": "Battery life appears solid for moderate use. That said, 5G usage and high brightness levels significantly impact endurance.",
                        "references": ["r3", "t2"]
                    }
                ]
            }
        ],
        "pros": [
            {"point": "Excellent AMOLED display with high brightness and smooth refresh rate", "references": ["r1", "y1"]},
            {"point": "Reliable camera system, especially in low light",                       "references": ["r2", "y2"]}
        ],
        "cons": [
            {"point": "Device heating under sustained heavy workloads", "references": ["r2", "t1"]},
            {"point": "Battery drain increases significantly with 5G",  "references": ["r3", "t2"]}
        ]
    }

    # build the comments block — each origin as a labelled section
    comments_block = ""
    for origin in comments:
        idx              = origin["idx"]
        origin_comments  = origin["comments"]
        if not origin_comments:
            continue
        comments_block += f"\n[{idx}]\n"
        for c in origin_comments:
            comments_block += f"  - {c}\n"

    prompt = f"""
You are a product review analyst. Below are real user comments about "{product}", grouped by source ID.
Each source ID (r1, r2, y1, y2, t1, t2 etc.) maps to a specific Reddit thread, YouTube video, or Twitter post.

Your task: generate a structured JSON report analysing what people are saying about this product.

RULES:
- Use ONLY the source IDs provided in the comments below inside "references" fields.
- Do NOT invent IDs. Do NOT use IDs that don't appear in the comments block.
- Every claim in sections, pros, and cons MUST cite at least one real reference ID.
- Be objective — reflect what comments actually say, don't embellish.
- Output ONLY valid JSON. No markdown fences, no explanation text, nothing else.

USER COMMENTS:
{comments_block}

REQUIRED OUTPUT FORMAT (follow this schema exactly):
{json.dumps(example_output, indent=2)}

Now generate the report for: "{product}"
Output:
"""

    return get_parsed_response(llm, prompt)
